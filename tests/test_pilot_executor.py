"""
Tests del motor de secuencias del Pilot, incluyendo los pasos nuevos
(wait_for_window, click_accessibility, screen_changed).

dry_run no toca el escritorio; la ejecución real se mockea en la capa pilot.
"""

import asyncio
from unittest.mock import patch

from loombit_operator.pilot import executor as ex


def _run(coro):
    return asyncio.run(coro)


def test_new_steps_are_supported():
    for step in ("wait_for_window", "click_accessibility", "screen_changed"):
        assert step in ex.SUPPORTED_STEPS


def test_dry_run_recognises_new_steps_without_touching_desktop():
    steps = [
        {"type": "wait_for_window", "title": "Bloc de notas", "timeout": 5},
        {"type": "click_accessibility", "name": "Guardar"},
        {"type": "screen_changed", "threshold": 0.02},
    ]
    receipt = _run(ex.execute_sequence("prueba", steps, dry_run=True))
    assert receipt["error_halted"] is False
    assert receipt["steps_executed"] == 3
    assert all(r.get("dry_run") for r in receipt["results"])


def test_unsupported_step_halts():
    receipt = _run(ex.execute_sequence("x", [{"type": "no_existe"}], dry_run=True))
    # dry_run igualmente valida el tipo antes de simular
    assert receipt["error_halted"] is True
    assert "no soportado" in receipt["results"][0]["error"]


def test_execute_new_steps_dispatches_to_pilot_layer():
    steps = [
        {"type": "wait_for_window", "title": "Notepad", "timeout": 3},
        {"type": "click_accessibility", "name": "OK", "window_title": "Notepad"},
        {"type": "screen_changed", "threshold": 0.05},
    ]
    with (
        patch.object(
            ex, "wait_for_window", return_value={"found": True, "window_title": "Notepad"}
        ) as m_wait,
        patch.object(ex, "click_accessibility", return_value={"clicked": True}) as m_click,
        patch.object(
            ex, "screen_changed", return_value={"changed": True, "fraction": 0.2}
        ) as m_screen,
    ):
        receipt = _run(ex.execute_sequence("real", steps, dry_run=False))

    assert receipt["error_halted"] is False
    assert receipt["steps_executed"] == 3
    m_wait.assert_called_once()
    m_click.assert_called_once()
    m_screen.assert_called_once()
