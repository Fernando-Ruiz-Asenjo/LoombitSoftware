"""
galaxia_actions.py — el cerebro del "drag-to-act" de la Galaxia.

Idea (visión de Fernando): la Galaxia no es solo un mapa que se mira; es un tablero
donde ARRASTRAS cosas (una conversación, un documento, un contacto) y las SUELTAS
sobre un planeta (un contacto, una cuenta a cobrar) o el Sol (el negocio), y Loombit
hace la acción que toca — fluido, humano y con sentido.

Este módulo es el RESOLUTOR determinista: dado *qué arrastras* × *dónde lo sueltas*,
devuelve la acción propuesta. NO ejecuta efectos: los **propone** (la UI muestra
"¿Quieres que haga esto?") y, si hay efecto externo, lo enruta como TAREA al agente,
que ya aplica el gate de aprobación + la firma del usuario + la proactividad. Así
reutilizamos toda la maquinaria de seguridad en vez de duplicarla.

Determinista, sin LLM. Puro y testeable: source/target son dicts que la UI ya tiene
(salen de `GET /galaxia`).

Tipos de origen (lo que se arrastra):   conversacion | documento | contacto
Tipos de destino (sobre lo que se suelta): contacto | cuenta | sol

Modos de acción devueltos:
  - "agent_task" → se manda al agente como tarea (efectos pasan por aprobación).
  - "navigate"   → la UI navega/abre algo (sin efecto externo).
  - "local"      → acción local determinista (sin efecto externo, sin agente).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DropAction:
    """Acción propuesta para un arrastre. La UI la muestra como '¿Quieres que…?'."""

    action_id: str
    titulo: str  # texto humano para el usuario ("Enviar la factura a Jana")
    explicacion: str  # una línea de por qué / qué pasará
    modo: str  # agent_task | navigate | local
    efecto_externo: bool  # True = sale al mundo → pasará por aprobación del agente
    params: dict[str, Any] = field(default_factory=dict)
    task: str = ""  # si modo == agent_task: la orden en lenguaje natural para el agente

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "titulo": self.titulo,
            "explicacion": self.explicacion,
            "modo": self.modo,
            "efecto_externo": self.efecto_externo,
            "params": self.params,
            "task": self.task,
        }


def _nombre(d: dict[str, Any], *claves: str, defecto: str = "esto") -> str:
    for k in claves:
        v = d.get(k)
        if v:
            return str(v)
    return defecto


def _no_aplica(source: dict[str, Any], target: dict[str, Any]) -> DropAction:
    return DropAction(
        action_id="no_aplica",
        titulo="No sé qué hacer con eso ahí",
        explicacion=(
            f"Soltar «{_nombre(source, 'etiqueta', 'titulo', 'nombre')}» sobre "
            f"«{_nombre(target, 'etiqueta', 'nombre')}» no tiene una acción clara todavía."
        ),
        modo="local",
        efecto_externo=False,
    )


# ── Reglas por (origen → destino) ──────────────────────────────────────────────


def _doc_a_contacto(s: dict, t: dict) -> DropAction:
    doc = _nombre(s, "etiqueta", "nombre", "path", defecto="el documento")
    quien = _nombre(t, "etiqueta", "nombre")
    email = t.get("email", "")
    return DropAction(
        action_id="enviar_documento",
        titulo=f"Enviar «{doc}» a {quien}",
        explicacion="Prepararé un correo con el documento adjunto; lo apruebas antes de enviarlo.",
        modo="agent_task",
        efecto_externo=True,
        params={"path": s.get("path", ""), "to": email},
        task=(
            f"Envía el documento que está en «{s.get('path', doc)}» a {email or quien} "
            f"con un correo breve y natural en mi nombre."
        ),
    )


def _doc_a_cuenta(s: dict, t: dict) -> DropAction:
    doc = _nombre(s, "etiqueta", "nombre", "path", defecto="el documento")
    cliente = _nombre(t, "etiqueta", "nombre")
    return DropAction(
        action_id="adjuntar_doc_cuenta",
        titulo=f"Vincular «{doc}» a la cuenta de {cliente}",
        explicacion="Lo registro como soporte de ese cobro (factura/albarán). Acción local, sin envíos.",
        modo="local",
        efecto_externo=False,
        params={"path": s.get("path", ""), "cuenta_id": t.get("id", "")},
    )


def _doc_a_sol(s: dict, t: dict) -> DropAction:
    doc = _nombre(s, "etiqueta", "nombre", "path", defecto="el documento")
    return DropAction(
        action_id="intake_documento",
        titulo=f"Leer y archivar «{doc}»",
        explicacion="Extraigo sus datos (importe, fechas, IBAN…) y lo coloco donde corresponda.",
        modo="agent_task",
        efecto_externo=False,
        params={"path": s.get("path", "")},
        task=f"Lee la factura/documento en «{s.get('path', doc)}» y resume sus datos clave.",
    )


def _conv_a_contacto(s: dict, t: dict) -> DropAction:
    quien = _nombre(t, "etiqueta", "nombre")
    email = t.get("email", "")
    return DropAction(
        action_id="continuar_conversacion_contacto",
        titulo=f"Retomar esta conversación con {quien}",
        explicacion="Preparo el siguiente mensaje con el contexto de la conversación; lo apruebas antes de enviar.",
        modo="agent_task",
        efecto_externo=True,
        params={"conversacion_id": s.get("id", ""), "to": email},
        task=(
            f"Retoma la conversación «{_nombre(s, 'etiqueta', 'titulo', defecto='en curso')}» y "
            f"redacta el siguiente correo a {email or quien} en mi nombre, breve y natural."
        ),
    )


def _conv_a_cuenta(s: dict, t: dict) -> DropAction:
    cliente = _nombre(t, "etiqueta", "nombre")
    importe = t.get("importe")
    detalle = f" de {importe:.0f} €" if isinstance(importe, (int, float)) else ""
    return DropAction(
        action_id="recordatorio_cobro",
        titulo=f"Preparar recordatorio de cobro a {cliente}",
        explicacion=f"Redacto un recordatorio cordial del cobro pendiente{detalle}; lo apruebas antes de enviar.",
        modo="agent_task",
        efecto_externo=True,
        params={"conversacion_id": s.get("id", ""), "cuenta_id": t.get("id", "")},
        task=(
            f"Prepara un recordatorio de cobro cordial para {cliente} sobre la cuenta pendiente"
            f"{detalle}, en mi nombre, breve y profesional."
        ),
    )


def _navegar_conversacion(s: dict, _t: dict) -> DropAction:
    return DropAction(
        action_id="abrir_conversacion",
        titulo="Volver a esta conversación",
        explicacion="Te llevo a la conversación en el chat para seguirla.",
        modo="navigate",
        efecto_externo=False,
        params={"conversacion_id": s.get("id", "")},
    )


def _contacto_a_cuenta(s: dict, t: dict) -> DropAction:
    quien = _nombre(s, "etiqueta", "nombre")
    cliente = _nombre(t, "etiqueta", "nombre")
    return DropAction(
        action_id="asignar_pagador",
        titulo=f"Marcar a {quien} como pagador de la cuenta de {cliente}",
        explicacion="Aprende la relación contacto↔cobro para futuras conciliaciones. Acción local.",
        modo="local",
        efecto_externo=False,
        params={"contacto_email": s.get("email", ""), "cuenta_id": t.get("id", "")},
    )


# (origen, destino) → constructor
_REGLAS: dict[tuple[str, str], Any] = {
    ("documento", "contacto"): _doc_a_contacto,
    ("documento", "cuenta"): _doc_a_cuenta,
    ("documento", "sol"): _doc_a_sol,
    ("conversacion", "contacto"): _conv_a_contacto,
    ("conversacion", "cuenta"): _conv_a_cuenta,
    ("conversacion", "sol"): _navegar_conversacion,
    ("contacto", "cuenta"): _contacto_a_cuenta,
}


def resolve_drop(source: dict[str, Any], target: dict[str, Any]) -> DropAction:
    """Dado lo que se arrastra (`source`) y dónde se suelta (`target`), propone la acción.

    `source.kind` ∈ {conversacion, documento, contacto}.
    `target.kind` ∈ {contacto, cuenta, sol}. (Para nodos de la galaxia, `kind` se deduce
    de `tipo` si no viene explícito.)
    """
    s_kind = str(source.get("kind") or source.get("tipo") or "").lower()
    t_kind = str(target.get("kind") or target.get("tipo") or "").lower()
    regla = _REGLAS.get((s_kind, t_kind))
    if regla is None:
        return _no_aplica(source, target)
    return regla(source, target)
