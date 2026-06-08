"""
Tests del overlay del Pilot (señal visible de marca Loombit).

Solo lógica pura y segura en CI: la interpolación de color, el degradado del marco
y que `PilotOverlay` se construye con los colores de marca. NO se arranca tkinter
(eso requiere un display y se verifica EN VIVO, no en CI).
"""

from loombit_operator.pilot.overlay import (
    CYAN,
    NAVY,
    PURPLE_BRIGHT,
    PilotOverlay,
    _gradient,
    _lerp,
)


def test_lerp_endpoints_and_midpoint():
    assert _lerp("#000000", "#ffffff", 0.0) == "#000000"
    assert _lerp("#000000", "#ffffff", 1.0) == "#ffffff"
    assert _lerp("#000000", "#ffffff", 0.5) == "#808080"


def test_lerp_uses_brand_channels():
    # #06b6d4 → #8b5cf6 a mitad: cada canal es la media de los extremos.
    mid = _lerp("#06b6d4", "#8b5cf6", 0.5)
    assert mid == "#4889e5"


def test_gradient_length_and_bounds():
    g = _gradient(10, CYAN, PURPLE_BRIGHT)
    assert len(g) == 10
    assert g[0] == CYAN
    assert g[-1] == PURPLE_BRIGHT
    assert _gradient(1, CYAN, PURPLE_BRIGHT) == [CYAN]


def test_overlay_constructs_without_starting_tk():
    ov = PilotOverlay("LOOMBIT PILOTANDO")
    assert ov.texto == "LOOMBIT PILOTANDO"
    assert ov.perimetro and ov.cursor and ov.cartel
    assert not ov._stop.is_set()
    ov.stop()
    assert ov._stop.is_set()


def test_overlay_flags_are_configurable():
    ov = PilotOverlay("X", perimetro=False, cursor=False, cartel=True)
    assert ov.perimetro is False
    assert ov.cursor is False
    assert ov.cartel is True


def test_brand_colors_are_loombit_palette():
    # Anti-regresión: el overlay usa la paleta de marca (violeta/cian), no el teal viejo.
    assert CYAN == "#06b6d4"
    assert PURPLE_BRIGHT == "#a78bfa"
    assert NAVY == "#0b0f1a"
