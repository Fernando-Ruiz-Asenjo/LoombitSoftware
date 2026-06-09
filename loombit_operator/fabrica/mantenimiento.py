"""
mantenimiento.py — cierra el lazo de la "herramienta de errores de código": de MARCAR a PROPONER.

`interno.py` DETECTA señales (bugs, seguridad, TODO) con su `file:line`. Aquí, para las señales
ARREGLABLES (FIX), se le pide a `reparar.py` un DIFF VALIDADO (guard de API en uso + opcional tests
en repo aislado), consultando el Playbook (ACE), y se devuelven como propuestas para el gate humano.

NUNCA escribe: solo trae la reparación lista para tu OK. Best-effort y presupuestado (`max_items`):
pensado para correr en 2º plano (el daemon F4 lo invoca con cupo).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .interno import marcar
from .modelos import Necesidad, TipoNecesidad
from .reparar import proponer_parche

_LINEA_RE = re.compile(r":\d+$")
_EXT_REPARABLES = (".py", ".html", ".js", ".css")


def _archivo_de(necesidad: Necesidad) -> str:
    """Ruta de fichero (sin `:línea`) de la procedencia de una señal de interno. '' si no apunta a un
    fichero (p. ej. 'run:r2', 'interno:prompts')."""
    for proc in necesidad.procedencia:
        if not proc:
            continue
        ruta = _LINEA_RE.sub("", proc)
        if ruta.endswith(_EXT_REPARABLES):
            return ruta
    return ""


def proponer_reparaciones(
    necesidades: list[Necesidad] | None = None,
    *,
    llm: Any = None,
    playbook: Any = None,
    raiz_repo: Path | None = None,
    max_items: int = 3,
    validar_tests: bool = False,
) -> list[dict[str, Any]]:
    """Para cada señal FIX con fichero conocido, propone un parche VALIDADO (no escribe nada).
    Si `necesidades` es None, las saca de `interno.marcar()`. Devuelve la lista de propuestas
    (cada una con su diff y veredicto) para revisión humana."""
    raiz_repo = raiz_repo or Path(__file__).resolve().parents[2]
    if necesidades is None:
        necesidades = marcar()
    fixes = [n for n in necesidades if n.tipo == TipoNecesidad.FIX]
    out: list[dict[str, Any]] = []
    for nec in fixes[:max_items]:
        archivo = _archivo_de(nec)
        if not archivo:
            continue
        instruccion = f"{nec.titulo}. {nec.descripcion}".strip()
        parche = proponer_parche(
            archivo,
            instruccion,
            llm=llm,
            raiz=raiz_repo,
            playbook=playbook,
            validar_tests=validar_tests,
        )
        if parche:
            parche["necesidad"] = nec.titulo
            out.append(parche)
    return out
