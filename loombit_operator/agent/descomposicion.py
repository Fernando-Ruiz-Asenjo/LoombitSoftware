"""
descomposicion.py — Gate de ambigüedad INTERNO + descomposición multi-intención (A1).

El force-tool (`intencion.py`) es single-intent: una petición con varias métricas/intenciones solo
dispara UNA y responde a medias (el pendiente P2). Aquí está la pieza que falta, aplicando el método
Ouroboros PERO sin preguntar nunca al usuario (brújula: «Loombit acierta, no pregunta»):

  1. DESCOMPONER la frase en N sub-intenciones (el LLM clasifica QUÉ pide; las CIFRAS las siguen
     calculando las tools deterministas — el LLM no inventa números).
  2. PUNTUAR la confianza de cada una; claridad ponderada = Σ(peso·confianza)/Σpeso (Ouroboros).
  3. GATE: ejecutar las claras; las DUDOSAS → 2ª pasada de destilado con el LLM (NUNCA regex, NUNCA
     se pregunta al usuario), no respuestas a medias.
  4. COMPONER una sola respuesta que cubra todas las métricas pedidas.

Solo entran sub-intenciones de LECTURA (sin efecto externo) → auto-ejecutarlas es seguro, no necesita
aprobación. Las que tienen efecto (registrar/enviar/crear) se quedan fuera (follow-up). El caso
financiero-puro («cuánto facturé y cuánto me deben») ya lo cubre `resumen_financiero`; A1 añade el
cross-domain («cuánto me deben Y qué reuniones tengo esta semana» = financiero + agenda).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _MenuItem:
    tool: str  # nombre de la tool ejecutora (registrada), de LECTURA
    peso: float  # peso en la claridad ponderada (Ouroboros)
    desc: str  # descripción para que el LLM clasifique


# Menú de sub-intenciones de LECTURA que A1 sabe componer. Ampliable; por seguridad NADA con efecto
# externo (eso necesitaría aprobación y no se auto-ejecuta).
MENU: dict[str, _MenuItem] = {
    "financiero": _MenuItem(
        "resumen_financiero",
        1.0,
        "dinero del negocio: cuánto ha facturado/ingresado, cuánto ha gastado, su beneficio, el "
        "IVA/303, o cuánto le deben (cobros pendientes)",
    ),
    "agenda": _MenuItem(
        "calendar_semana",
        1.0,
        "su agenda/calendario: qué reuniones, citas o eventos tiene (esta semana, un día concreto…)",
    ),
    "buscar_correo": _MenuItem(
        "gmail_search",
        1.0,
        "buscar correos/emails en su bandeja sobre alguien o algo (devuelve 'termino' a buscar)",
    ),
}

# Umbrales del gate (confianza por sub-intención).
UMBRAL_EJEC = 0.6  # ≥ → se ejecuta
UMBRAL_DUDA = 0.35  # [DUDA, EJEC) → re-destilar (2ª pasada); < DUDA → se ignora


@dataclass
class Sub:
    intencion: str
    confianza: float
    args: dict = field(default_factory=dict)


# Señal BARATA de multi-intención (solo decide si vale la pena la descomposición LLM; NO clasifica).
# Requiere ≥2 FAMILIAS distintas + coordinación → así una compuesta de UNA sola familia (p.ej.
# financiera-pura, que ya resuelve resumen_financiero) NO dispara A1.
_F_FINANCIERO = re.compile(
    r"\b(factur\w+|ingres\w+|gast\w+|benefici\w+|me deben|me debe|cobr\w+|iva|303|pendiente\w*)\b"
)
_F_AGENDA = re.compile(r"\b(reuni\w+|cita\w*|agenda|evento\w*|calendario)\b|esta semana")
_F_CORREO = re.compile(r"\b(correo\w*|email\w*|e-mail|mensaje\w*|bandeja|gmail)\b")
_COORD = re.compile(r"\b(y|e|tambi[eé]n|adem[aá]s)\b|;|,")


def parece_multi_intent(task: str) -> bool:
    """True si la petición cruza ≥2 FAMILIAS de intención y hay coordinación → merece descomponer."""
    t = (task or "").lower()
    familias = sum(bool(rx.search(t)) for rx in (_F_FINANCIERO, _F_AGENDA, _F_CORREO))
    return familias >= 2 and bool(_COORD.search(t))


def claridad(subs: list[Sub]) -> float:
    """Claridad ponderada Σ(peso·confianza)/Σpeso sobre las sub-intenciones del menú (Ouroboros).
    1.0 = todas clarísimas; 0.0 = nada claro. La «ambigüedad» Ouroboros sería 1 − claridad."""
    detect = [s for s in subs if s.confianza > 0 and s.intencion in MENU]
    if not detect:
        return 0.0
    num = sum(MENU[s.intencion].peso * s.confianza for s in detect)
    den = sum(MENU[s.intencion].peso for s in detect)
    return num / den if den else 0.0


def clasificar(subs: list[Sub]) -> tuple[list[Sub], list[Sub]]:
    """Parte las sub-intenciones en (a_ejecutar ≥ UMBRAL_EJEC, dudosas en [DUDA, EJEC))."""
    a_ejecutar = [s for s in subs if s.intencion in MENU and s.confianza >= UMBRAL_EJEC]
    dudosas = [s for s in subs if s.intencion in MENU and UMBRAL_DUDA <= s.confianza < UMBRAL_EJEC]
    return a_ejecutar, dudosas


def _parse_json(texto: str) -> dict:
    """Parse robusto del JSON del 14B: quita fences markdown y aísla el primer objeto {...}."""
    t = (texto or "").strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.IGNORECASE | re.MULTILINE).strip()
    m = re.search(r"\{.*\}", t, flags=re.DOTALL)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


_SISTEMA = (
    "Eres un CLASIFICADOR de intención para un operador administrativo de un autónomo español. "
    "Te doy el mensaje del usuario y debes decir QUÉ pide, eligiendo del menú. Puede pedir VARIAS "
    "cosas a la vez. NO inventes intenciones que no estén; sé conservador con la confianza.\n"
    "Menú de intenciones:\n"
    + "\n".join(f"- {k}: {m.desc}" for k, m in MENU.items())
    + "\n\nDevuelve SOLO un JSON, sin texto alrededor, con esta forma EXACTA:\n"
    '{"intenciones": [{"id": "<financiero|agenda|buscar_correo>", "confianza": <0..1>, '
    '"termino": "<solo para buscar_correo: a quién/qué buscar; si no, vacío>"}]}'
)


def descomponer(task: str, llm, afilar: bool = False) -> list[Sub]:
    """UNA llamada al LLM para clasificar las sub-intenciones de la frase. `afilar`=2ª pasada con
    instrucción más estricta (re-destilado de las dudosas). Devuelve [] si falla (→ cae al single-intent).
    """
    extra = (
        "\n\nIMPORTANTE: el mensaje parecía ambiguo. Reléelo y marca confianza ALTA (≥0.6) solo en "
        "lo que el usuario pide CLARAMENTE; si una intención no está clara, baja su confianza."
        if afilar
        else ""
    )
    msgs = [
        {"role": "system", "content": _SISTEMA + extra},
        {"role": "user", "content": task or ""},
    ]
    try:
        resp = llm.chat(messages=msgs, temperature=0.0)
        data = _parse_json(resp.content)
    except Exception as exc:  # noqa: BLE001 — sin descomposición se cae al single-intent
        logger.info("descomponer: fallo LLM/parse (%s)", exc)
        return []
    subs: list[Sub] = []
    for it in data.get("intenciones", []) if isinstance(data, dict) else []:
        if not isinstance(it, dict):
            continue
        iid = str(it.get("id", "")).strip()
        if iid not in MENU:
            continue
        try:
            conf = float(it.get("confianza", 0))
        except (ValueError, TypeError):
            conf = 0.0
        args: dict = {}
        if iid == "buscar_correo":
            term = str(it.get("termino", "")).strip()
            if term:
                args["query"] = term
        subs.append(Sub(iid, max(0.0, min(1.0, conf)), args))
    return subs


def resolver(task: str, llm) -> list[Sub]:
    """Devuelve las sub-intenciones A EJECUTAR si la petición es multi-intención (≥2 claras); si no,
    [] (que siga el flujo single-intent). Las dudosas se re-destilan con una 2ª pasada del LLM."""
    if not parece_multi_intent(task):
        return []
    subs = descomponer(task, llm)
    a_ejec, dudosas = clasificar(subs)
    logger.info(
        "A1 descompone task=%r claridad=%.2f ejec=%s dudosas=%s",
        (task or "")[:60],
        claridad(subs),
        [s.intencion for s in a_ejec],
        [s.intencion for s in dudosas],
    )
    if dudosas:  # re-destilar (NUNCA preguntar al usuario): 2ª pasada más estricta
        subs2 = descomponer(task, llm, afilar=True)
        a_ejec2, _ = clasificar(subs2)
        # una sub se ejecuta si CUALQUIER pasada la dio clara; conserva args (preferir los de la 2ª)
        por_id: dict[str, Sub] = {s.intencion: s for s in a_ejec}
        for s in a_ejec2:
            por_id[s.intencion] = s if s.args else por_id.get(s.intencion, s)
        a_ejec = list(por_id.values())
    # A1 solo aplica a MULTI-métrica (≥2). Una sola → que la resuelva el single-intent (no duplicar).
    return a_ejec if len(a_ejec) >= 2 else []
