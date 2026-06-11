"""
preferencias_correo.py — aprender de las EDICIONES del usuario (PRELUDE). Núcleo blanco, determinista.

Cuando el usuario retoca un borrador antes de aprobarlo, ese diff es la señal de preferencia más
honesta que existe (gratis, sin pedir nada). Aquí se extraen señales DETERMINISTAS del diff —
longitud (más corto/largo), firma (última línea), tratamiento (tuteo/usted)— y se persisten como
preferencia, para que el próximo borrador salga más a su gusto. El LLM no interviene; el envío
sigue requiriendo aprobación. Ref: docs/INVESTIGACION_ASISTENTE_PROACTIVO_2026.md (#2, PRELUDE).
"""

from __future__ import annotations

import re
from typing import Any

# Marcadores de tratamiento (heurística determinista, español).
_TUTEO = re.compile(r"\b(tú|te|tu|tus|tuyo|tuya|contigo|hola)\b", re.IGNORECASE)
_USTED = re.compile(
    r"\b(usted|ustedes|le|les|su|sus|suyo|suya|estimad[oa]|atentamente)\b", re.IGNORECASE
)


def _ultima_linea(texto: str) -> str:
    for linea in reversed((texto or "").splitlines()):
        if linea.strip():
            return linea.strip()
    return ""


def _tratamiento(texto: str) -> str | None:
    """'tuteo' / 'usted' / None según qué marcadores predominan (determinista)."""
    tu = len(_TUTEO.findall(texto or ""))
    ud = len(_USTED.findall(texto or ""))
    if tu > ud:
        return "tuteo"
    if ud > tu:
        return "usted"
    return None


def aprender_de_edicion(original: str, editado: str) -> dict[str, Any]:
    """Señales DETERMINISTAS del diff de una edición. {} si no hay cambio relevante (no inventa)."""
    o, e = (original or "").strip(), (editado or "").strip()
    senales: dict[str, Any] = {}
    if not o or not e or o == e:
        return senales

    lo, le = len(o), len(e)
    if le < 0.8 * lo:
        senales["longitud"] = "mas_corto"
    elif le > 1.25 * lo:
        senales["longitud"] = "mas_largo"

    firma_o, firma_e = _ultima_linea(o), _ultima_linea(e)
    if firma_e and firma_e != firma_o:
        senales["firma"] = firma_e

    trat_e = _tratamiento(e)
    if trat_e and trat_e != _tratamiento(o):
        senales["tratamiento"] = trat_e

    return senales


def aplicar_a_memoria(memory: Any, senales: dict[str, Any]) -> dict[str, Any]:
    """Persiste las señales aprendidas como preferencias del usuario. Devuelve lo aplicado."""
    aplicado: dict[str, Any] = {}
    if not senales:
        return aplicado
    mapa = {"firma": "firma", "tratamiento": "tratamiento", "longitud": "longitud_correo"}
    for clave, pref in mapa.items():
        if senales.get(clave):
            memory.set_preference(pref, senales[clave])
            aplicado[pref] = senales[clave]
    return aplicado


def aprender_y_aplicar(memory: Any, original: str, editado: str) -> dict[str, Any]:
    """Atajo: extrae las señales del diff y las persiste en la memoria. Devuelve lo aplicado."""
    return aplicar_a_memoria(memory, aprender_de_edicion(original, editado))
