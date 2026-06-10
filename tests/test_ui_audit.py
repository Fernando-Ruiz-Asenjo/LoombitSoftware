"""Auditoría funcional de la UI: ningún botón muerto en las pantallas servidas.

Guarda de regresión: habría cazado el ⚙️ Ajustes y "Editar" (que "se pintaban" pero no hacían nada).
"""

from __future__ import annotations

import pathlib

from loombit_operator.ui_audit import botones_sin_funcion

_STATIC = pathlib.Path(__file__).resolve().parent.parent / "loombit_operator" / "static"
# Solo las UIs que se SIRVEN (tela.html es componente suelto, no se enlaza).
_SERVIDAS = ["index.html", "loombit.html"]


def test_deteccion_caza_un_boton_muerto() -> None:
    # El propio detector funciona: un botón sin onclick/type es muerto; uno con onclick, no.
    assert botones_sin_funcion('<button class="x" title="Ajustes">⚙</button>')
    assert not botones_sin_funcion('<button onclick="f()">ok</button>')
    assert not botones_sin_funcion('<button type="submit">enviar</button>')


def test_sin_botones_muertos_en_las_ui_servidas() -> None:
    fallos: dict[str, list[str]] = {}
    for nombre in _SERVIDAS:
        p = _STATIC / nombre
        if not p.exists():
            continue
        muertos = botones_sin_funcion(p.read_text(encoding="utf-8"))
        if muertos:
            fallos[nombre] = muertos
    assert not fallos, f"Botones sin función (muertos) en la UI: {fallos}"
