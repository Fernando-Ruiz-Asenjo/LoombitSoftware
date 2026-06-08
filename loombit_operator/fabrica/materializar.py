"""
materializar.py — convierte una propuesta APROBADA en una tool usable (gate sagrado intacto).

Escribe el código (ya validado y aprobado por un humano) en `fabrica/generadas/<nombre>.py`, un
módulo en cuarentena que se RE-VERIFICA con el gate de seguridad antes de importarse y que se
auto-registra en el tool_registry al cargarse. Es el único punto donde la Fábrica toca el sistema
en vivo — y solo lo hace con estado APROBADA. La carga al arrancar es opt-in
(`settings.fabrica_autocargar_generadas`, off por defecto).
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from .modelos import EstadoPropuesta, PropuestaSkill
from .seguridad import analizar_seguridad

DIR_GENERADAS = Path(__file__).parent / "generadas"
_PAQUETE = "loombit_operator.fabrica.generadas"

_CABECERA = (
    '"""Tool auto-generada por la Fábrica de Skills — propuesta {pid}.\n'
    "APROBADA por un humano. Pasó: seguridad AST + black + ruff + eval + sin regresión.\n"
    'NO editar a mano (producto de runtime, regenerable desde el store)."""\n\n'
    "from loombit_operator.tools.registry import ToolDefinition, tool_registry\n\n"
)

_PIE = (
    "\n\n_PARAMETROS = {parametros!r}\n\n"
    "if {nombre!r} not in {{t.name for t in tool_registry.list()}}:\n"
    "    tool_registry.register(\n"
    "        ToolDefinition(\n"
    "            name={nombre!r},\n"
    "            description={descripcion!r},\n"
    "            parameters=_PARAMETROS,\n"
    "            fn={nombre},\n"
    '            category="fabrica",\n'
    "        )\n"
    "    )\n"
)


def _modulo_texto(propuesta: PropuestaSkill) -> str:
    b = propuesta.borrador
    cabecera = _CABECERA.format(pid=propuesta.id)
    pie = _PIE.format(
        parametros=b.parametros,
        nombre=b.nombre,
        descripcion=b.descripcion,
    )
    return cabecera + b.source.strip() + "\n" + pie


def escribir_tool_aprobada(propuesta: PropuestaSkill) -> Path:
    """Materializa la tool aprobada en `generadas/`. Re-verifica seguridad (defensa en profundidad)
    y exige estado APROBADA: la Fábrica no escribe nada que un humano no haya autorizado."""
    if propuesta.estado != EstadoPropuesta.APROBADA:
        raise ValueError(
            f"No se materializa una propuesta {propuesta.estado.value} (debe estar aprobada)"
        )
    seg = analizar_seguridad(propuesta.borrador.source)
    if not seg.ok:
        raise ValueError(f"Rechazada al materializar (seguridad): {'; '.join(seg.violaciones)}")
    DIR_GENERADAS.mkdir(parents=True, exist_ok=True)
    destino = DIR_GENERADAS / f"{propuesta.borrador.nombre}.py"
    destino.write_text(_modulo_texto(propuesta), encoding="utf-8")
    return destino


def cargar_tools_aprobadas(store: Any = None, registry: Any = None) -> list[str]:
    """Importa (registrando) las tools de las propuestas APROBADAS. Escribe el módulo si falta,
    re-verifica seguridad antes de importar y tolera las ya registradas. Devuelve los nombres."""
    if store is None:
        from .propuesta import PropuestaStore

        store = PropuestaStore()

    cargadas: list[str] = []
    for prop in store.list(EstadoPropuesta.APROBADA):
        nombre = prop.borrador.nombre
        try:
            destino = DIR_GENERADAS / f"{nombre}.py"
            if not destino.exists():
                escribir_tool_aprobada(prop)
            elif not analizar_seguridad(prop.borrador.source).ok:
                continue  # el código aprobado ya no pasa seguridad → no se carga
            importlib.import_module(f"{_PAQUETE}.{nombre}")
            cargadas.append(nombre)
        except Exception:  # noqa: BLE001 — una tool que no carga no debe tumbar el arranque
            continue
    return cargadas
