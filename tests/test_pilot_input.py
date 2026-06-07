"""
Tests de las mejoras de fiabilidad del Pilot:
  - _should_use_clipboard: decide pegar (no-ASCII/multilínea) vs teclear.
  - enable_dpi_awareness: idempotente y sin excepciones en cualquier plataforma.

No se ejercita el tecleo/clic real (requeriría una ventana con foco): solo la
lógica pura, segura en CI.
"""

from loombit_operator.pilot.input_control import _should_use_clipboard
from loombit_operator.pilot.system import enable_dpi_awareness


def test_should_use_clipboard_plain_ascii_is_false():
    assert _should_use_clipboard("") is False
    assert _should_use_clipboard("hello world 123") is False
    assert _should_use_clipboard("invoice F-2026/118") is False


def test_should_use_clipboard_accents_and_symbols_is_true():
    assert _should_use_clipboard("café") is True
    assert _should_use_clipboard("niño") is True
    assert _should_use_clipboard("Importe: 1.250 €") is True
    assert _should_use_clipboard("¿Confirmas? ¡Sí!") is True


def test_should_use_clipboard_multiline_or_tab_is_true():
    assert _should_use_clipboard("línea1\nlínea2") is True
    assert _should_use_clipboard("col1\tcol2") is True


def test_enable_dpi_awareness_is_idempotent_and_safe():
    first = enable_dpi_awareness()
    second = enable_dpi_awareness()
    for result in (first, second):
        assert isinstance(result, dict)
        assert "enabled" in result
        assert "mode" in result
