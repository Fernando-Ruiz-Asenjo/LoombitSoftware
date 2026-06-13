"""
pilot/browser.py — Núcleo GOBERNADO del adaptador de navegador del Skill W Pilot.

Gobierna el control de Chrome para órdenes complejas (login → formulario → reserva → checkout,
tipo "comprar billetes de avión"), batiendo a Gemini Spark en el cuadrante LOCAL. Mismo contrato de
seguridad que `executor.py`: local, no sube datos, **NO ejecuta efectos sin aprobación**, recibos
locales, dry_run.

Decisión de arquitectura (barrido SOTA 2026, D-93): **accessibility-tree-FIRST + visión SELECTIVA**
(AgentOccam y la práctica de producción: el a11y-tree iguala o bate a visión y AHORRA TOKENS — clave
para el 14B local; visión solo para lo no-accesible). El espacio de acciones se inspira en
`browser-use`; la robustez por visión-fallback, en `Skyvern`; la cascada de permisos, en `OpenClaw`.

ESTA CAPA es DETERMINISTA y SIN RED: valida la secuencia (allowlist de dominios, cerrado por defecto)
y marca qué pasos son CONSECUENTES (pago/compra/envío/borrado) → exigen GATE humano ANTES de
ejecutarse. El *driving* real (Playwright/CDP) es inyectable y queda FUERA de esta capa: frontera 🟠
DECLARADA (necesita la dependencia Playwright + verificación en vivo). El LLM PROPONE la secuencia;
este código DISPONE qué se bloquea y qué pausa (Ley Fundacional).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

# Espacio de acciones del navegador (a11y-first). Mismo patrón que SUPPORTED_STEPS del executor.
BROWSER_STEPS = [
    "navigate",  # ir a una URL (sujeto a allowlist)
    "a11y_snapshot",  # leer el árbol de accesibilidad → elementos accionables (texto, barato)
    "click_element",  # clic por índice/rol/nombre del a11y-tree (no por coordenadas frágiles)
    "type_text",  # escribir en el elemento con foco
    "select_option",  # elegir en un desplegable
    "extract",  # extraer datos estructurados (JSON schema) — estilo Skyvern
    "scroll",
    "wait",
]

SAFETY_CONTRACT = {
    "local_only": True,
    "does_not_upload": True,
    "does_not_execute_without_approval": True,  # los pasos consecuentes pausan en el gate
    "no_login_bypass": True,
    "no_captcha_bypass": True,
    "receipts_local": True,
    "dry_run_available": True,
    "domain_allowlist": True,  # cerrado por defecto: el navegador no va a cualquier sitio
}

# Pasos CONSECUENTES (efecto externo / dinero / envío) → GATE humano ANTES de ejecutar.
# "Comprar billetes" pausa ANTES del pago; Loombit nunca paga solo (la diferencia vs Spark/OpenClaw).
_PAGO = re.compile(
    r"\b(pagar|paga|pago|comprar|compra|checkout|realizar\s+pago|confirmar\s+(pedido|reserva|compra|pago)"
    r"|finaliz\w+\s+(compra|pedido|pago)|tarjeta|cvv|cvc|place\s+order|buy\s+now|\bpay\b|purchase|book\s+now)\b",
    re.IGNORECASE,
)
_ENVIO = re.compile(
    r"\b(enviar|env[ií]a|submit|publicar|borrar|eliminar|transferir|firmar)\b", re.IGNORECASE
)


@dataclass
class ElementoA11y:
    """Un elemento accionable del árbol de accesibilidad (no coordenadas frágiles)."""

    idx: int
    rol: str  # button, textbox, link, combobox…
    nombre: str  # texto/label accesible
    valor: str = ""

    @classmethod
    def desde_dict(cls, d: dict, idx: int) -> "ElementoA11y":
        return cls(
            idx=idx,
            rol=str(d.get("role") or d.get("rol") or ""),
            nombre=str(d.get("name") or d.get("nombre") or d.get("text") or "").strip()[:120],
            valor=str(d.get("value") or d.get("valor") or ""),
        )


def parse_a11y(snapshot: list[dict]) -> list[ElementoA11y]:
    """Convierte un snapshot del árbol de accesibilidad en elementos accionables indexados.
    Determinista; la entrada es lo que devolvería Playwright/CDP (inyectado), no toca la red."""
    return [ElementoA11y.desde_dict(d, i) for i, d in enumerate(snapshot) if isinstance(d, dict)]


def dominio_permitido(url: str, allowlist: list[str]) -> bool:
    """True si el host de `url` está en la allowlist (subdominios incluidos). Sin allowlist → False
    (CERRADO por defecto: el navegador no navega a cualquier sitio)."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    if not host or not allowlist:
        return False
    for dom in allowlist:
        d = dom.lower().lstrip("*").lstrip(".").strip()
        if d and (host == d or host.endswith("." + d)):
            return True
    return False


def es_paso_consecuente(step: dict) -> bool:
    """True si el paso tiene EFECTO externo/dinero (pago, compra, envío, borrado) → exige GATE humano
    ANTES de ejecutarse. Conservador: ante la duda en un pago, mejor pausar que pagar solo."""
    if step.get("type") not in ("click_element", "navigate", "type_text"):
        return False
    texto = " ".join(
        str(step.get(k, "")) for k in ("nombre", "name", "objetivo", "url", "text", "label")
    )
    return bool(_PAGO.search(texto) or _ENVIO.search(texto))


@dataclass
class PlanNavegacion:
    """Resultado de validar una secuencia de navegación: qué se bloquea y qué exige gate."""

    pasos: list[dict]
    bloqueados: list[dict] = field(
        default_factory=list
    )  # dominio fuera de allowlist / paso inválido
    requieren_gate: list[int] = field(default_factory=list)  # índices de pasos consecuentes
    ok: bool = True

    def to_dict(self) -> dict:
        return {
            "pasos_total": len(self.pasos),
            "bloqueados": self.bloqueados,
            "requieren_gate": self.requieren_gate,
            "ok": self.ok,
        }


def validar_secuencia(steps: list[dict], allowlist: list[str]) -> PlanNavegacion:
    """Guardia DETERMINISTA antes de tocar el navegador real (que va aparte, inyectable):
      - `navigate` a dominio fuera de la allowlist → BLOQUEADO (cerrado por defecto).
      - paso no soportado → BLOQUEADO.
      - paso consecuente (pago/compra/envío) → marcado para GATE humano.
    El navegador NO se ejecuta si `ok` es False o sin resolver el gate de los pasos marcados.
    """
    plan = PlanNavegacion(pasos=steps)
    for i, step in enumerate(steps):
        tipo = step.get("type")
        if tipo not in BROWSER_STEPS:
            plan.bloqueados.append({"i": i, "motivo": f"paso no soportado: {tipo!r}"})
            plan.ok = False
            continue
        if tipo == "navigate" and not dominio_permitido(step.get("url", ""), allowlist):
            plan.bloqueados.append(
                {"i": i, "motivo": f"dominio fuera de la allowlist: {step.get('url', '')}"}
            )
            plan.ok = False
        if es_paso_consecuente(step):
            plan.requieren_gate.append(i)
    return plan
