"""§GOB-1 — Capability Policy Plane.

Superficie ÚNICA de autoridad consecuente. El LLM propone `tool(intención, datos)`; el plano decide
con código determinista. Reúne en un solo sitio las políticas que antes vivían dispersas en el loop:
el **gate de efecto** (todo efecto externo pasa por aprobación humana), la **resolución de
destinatario** (un identificador no se confía al modelo), la **no auto-revelación de bot**, la
**rehúsa ante manipulación** y —como política gemela en la frontera de datos— **datos ≠ órdenes**.

Diseño (para no introducir un ciclo de import): los *predicados* puros (`_recipiente_resuelto`,
`_intento_manipulacion`, …) viven hoy en `agent/loop.py` y se importan de forma diferida dentro de los
métodos. El plano es la superficie de DECISIÓN; migrar los predicados a `policy/policies.py` es un
follow-up limpio que no cambia el comportamiento.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..agent.run import AgentRun


class Accion(str, Enum):
    """Qué dispone el plano ante una tool-call propuesta por el LLM."""

    EJECUTAR = "ejecutar"  # adelante: ejecuta la tool
    APROBAR = "aprobar"  # efecto externo: PENDING_APPROVAL (gate humano)
    CORREGIR = "corregir"  # no ejecuta; devuelve `mensaje` al LLM para que reintente
    REHUSAR = "rehusar"  # no ejecuta; devuelve `mensaje` (rehúsa duro, p.ej. manipulación)


@dataclass(frozen=True)
class Decision:
    accion: Accion
    motivo: str = ""
    mensaje: str | None = None  # texto de vuelta para CORREGIR / REHUSAR


# Mensajes de política (idénticos a los que el loop devolvía inline, para no cambiar comportamiento).
_MSG_DESTINATARIO_NO_RESUELTO = (
    "[SISTEMA: No envíes a «{to}»: no es un email que el "
    "usuario te haya dado ni uno resuelto con contacts_find. NO inventes destinatarios. "
    "Llama a contacts_find con el nombre y usa el email del contacto correcto; si hay "
    "varios, elige el más probable o pregunta; si no aparece, pregunta al usuario.]"
)
_MSG_DELATA_BOT = (
    "[SISTEMA: El correo se presenta como IA/agente/automático. Reescríbelo COMO el "
    "usuario (primera persona), sin mencionar que eres un asistente, agente o bot ni "
    "que el correo es automático. Fírmalo con el nombre del usuario.]"
)


class AuthorityPlane:
    """La superficie única. `autorizar` decide sobre una tool-call; `sanear_dato` aplica la política
    de datos≠órdenes sobre el contenido leído (frontera de datos)."""

    def autorizar(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        run: "AgentRun",
        requires_approval: bool,
    ) -> Decision:
        # Import diferido: rompe el ciclo policy<->loop (el loop importa el plano arriba).
        from ..agent.loop import (
            _DELATA_BOT,
            _MSG_MANIPULACION,
            _destinatario_claro,
            _intento_manipulacion,
            _recipiente_resuelto,
        )

        if tool_name == "gmail_send":
            to = str(arguments.get("to", ""))
            # 1) El destinatario es un IDENTIFICADOR: no se confía al modelo (F2).
            if not _recipiente_resuelto(to, run):
                return Decision(
                    Accion.CORREGIR,
                    "destinatario no resuelto",
                    _MSG_DESTINATARIO_NO_RESUELTO.format(to=to),
                )
            # 2) El correo no puede auto-revelarse como bot (F4).
            if _DELATA_BOT.search(f"{arguments.get('subject', '')} {arguments.get('body', '')}"):
                return Decision(Accion.CORREGIR, "el correo se delata como bot", _MSG_DELATA_BOT)
            # 3) Manipulación en la petición del usuario: se rehúsa el envío (no se dibuja siquiera).
            if _intento_manipulacion(run.task):
                return Decision(
                    Accion.REHUSAR, "intento de manipulación en la petición", _MSG_MANIPULACION
                )
            # 4) Gate de efecto: auto-envío SOLO si el usuario lo pidió con destinatario inequívoco y
            #    no es una acción proactiva; en otro caso, tarjeta de aprobación.
            auto = (not getattr(run, "proactive", False)) and _destinatario_claro(to, run)
            if requires_approval and not auto:
                return Decision(Accion.APROBAR, "correo: destinatario ambiguo o acción proactiva")
            return Decision(Accion.EJECUTAR, "correo pedido por el usuario con destinatario claro")

        # Cualquier otra tool consecuente (calendar_create, run_shell, …): gate de efecto humano.
        if requires_approval:
            return Decision(Accion.APROBAR, "efecto externo: requiere gate humano")
        # Lectura / efecto nulo: adelante.
        return Decision(Accion.EJECUTAR, "lectura o efecto nulo")

    def sanear_dato(self, texto: str) -> tuple[str, bool]:
        """Política datos≠órdenes (§SEG-1) en la frontera de datos: neutraliza órdenes incrustadas en
        el contenido LEÍDO (correos/documentos/web) antes de que el LLM lo vea. Devuelve
        (texto_saneado, detectado)."""
        from ..agent.loop import _sanear_dato_no_confiable

        return _sanear_dato_no_confiable(texto)


# Instancia única: el plano es un singleton de proceso.
AUTHORITY_PLANE = AuthorityPlane()
