"""
Detección DETERMINISTA de intención que EXIGE herramienta — para forzar la tool CORRECTA.

El 14B a veces (a) calcula a ojo y fabrica cifras (cobro/303), (b) dice que buscó sin buscar. Para
esas intenciones forzamos `tool_choice` Y enfocamos las tools a la(s) correcta(s), de modo que:
  - en cobro/303/factura NO pueda calcular a mano NI elegir la tool equivocada;
  - PERO solo si la petición trae el DATO (un número): si faltan datos, NO forzamos → que pregunte,
    no que invente (regresión observada: forzar sin datos hacía que Qwen inventara importes).

Puro y testeable. Ver docs/ALGORITMO_CEREBRO.md.
"""

from __future__ import annotations

import re

_COBRO = re.compile(r"\b(cobro|cobrar|reclam\w+|moros\w+|impag\w+|deuda|deudas|vencid\w+|demora)\b")
_F303 = re.compile(r"\b(303|iva|trimestral|repercutid\w+|soportad\w+|devengad\w+|liquidaci[oó]n)\b")
_FACTURA = re.compile(
    r"\b(emit\w+|reg[ií]str\w+|fact[uú]rame|emp[ií]te|apunta(?:me)? una factura)\b"
)
_BUSCAR_CORREO = re.compile(
    r"\b(busca\w*|b[uú]scame|encuentra|revisa|mira)\b[^\n]{0,25}\b"
    r"(correo|correos|email|e-mail|mail|bandeja|mensaje\w*|inbox)\b"
)
# Hay un DATO numérico (cifra o número en palabras) → tiene sentido calcular; si no, hay que preguntar.
_TIENE_DATO = re.compile(
    r"\d|\b(mil|cien|ciento|doscient\w+|trescient\w+|cuatrocient\w+|quinient\w+|"
    r"seiscient\w+|setecient\w+|ochocient\w+|novecient\w+)\b"
)

# Tools a las que se LIMITA la llamada forzada (+ ask_user/task_done para poder preguntar o terminar).
_TOOLS_POR_INTENCION: dict[str, set[str]] = {
    "cobro": {"plan_cobro"},
    "303": {"calcular_303", "calcular_303_registradas"},
    "factura": {"registrar_factura"},
    "buscar": {"gmail_search"},
}
_SIEMPRE = {"ask_user", "task_done"}


def intencion_consecuente(task: str) -> str | None:
    """Intención que EXIGE herramienta: 'cobro'|'303'|'factura'|'buscar', o None.
    Para cobro/303/factura exige además un DATO numérico (si no, None → que pregunte)."""
    t = (task or "").lower()
    if _BUSCAR_CORREO.search(t):
        return "buscar"
    tiene_dato = bool(_TIENE_DATO.search(t))
    # factura ANTES que 303: "regístrame una factura … más IVA" menciona IVA pero es factura.
    if _FACTURA.search(t) and tiene_dato:
        return "factura"
    if _COBRO.search(t) and tiene_dato:
        return "cobro"
    if _F303.search(t) and tiene_dato:
        return "303"
    return None


def tools_foco(intencion: str | None) -> set[str]:
    """Conjunto de nombres de tool al que limitar la llamada forzada para esa intención."""
    if not intencion:
        return set()
    return _TOOLS_POR_INTENCION.get(intencion, set()) | _SIEMPRE


# Todas las tools de DOMINIO (cálculo/registro): durante una intención, se excluyen las de OTRAS
# intenciones para que el agente no divague (p.ej. en un cobro NO registre una factura fantasma).
_DOMINIO_TODAS = {"plan_cobro", "calcular_303", "calcular_303_registradas", "registrar_factura"}


def tools_excluir(intencion: str | None) -> set[str]:
    """Tools de dominio de OTRAS intenciones, a quitar del run completo (evita divagar de tool)."""
    if not intencion:
        return set()
    return _DOMINIO_TODAS - _TOOLS_POR_INTENCION.get(intencion, set())


# Pregunta sobre la agenda ("¿qué reuniones tengo?", "¿tengo algo el jueves?") = LECTURA. El 14B a
# veces la confunde con CREAR un evento → excluimos calendar_create de forma determinista.
_LECTURA_AGENDA = re.compile(
    r"\b(qu[eé]|cu[aá]l\w*|tengo|hay|tienes)\b[^\n]{0,45}"
    r"\b(reuni\w+|cita\w*|agenda|evento\w*|calendario)\b"
)


def es_lectura_agenda(task: str) -> bool:
    """True si es una PREGUNTA sobre la agenda (lectura): no debe crear eventos."""
    return bool(_LECTURA_AGENDA.search((task or "").lower()))
