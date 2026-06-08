"""
Tests del gestor de overlay (señal visible mientras el Pilot controla por /computer-use/*).

El halo corre en su propio proceso; aquí se monkeypatchea `_spawn` por un doble que
simula el subproceso. Cubre: el filtro de rutas (solo acciones encienden el halo), que
`touch()` enciende y refresca el keepalive, que reutiliza el proceso vivo y rearranca si
murió, y que `force_stop()` limpia.
"""

import loombit_operator.pilot.overlay_manager as om
from loombit_operator.routers.computer import _is_action_path


class _FakeProc:
    def __init__(self) -> None:
        self._alive = True

    def poll(self):
        return None if self._alive else 0

    def terminate(self) -> None:
        self._alive = False


def test_is_action_path_only_for_acting_endpoints():
    for action in ("click", "type", "key", "open_application", "batch", "click_accessibility"):
        assert _is_action_path(f"/computer-use/{action}") is True
    for read in ("screenshot", "ui_snapshot", "read_page", "find", "status", "cursor_position"):
        assert _is_action_path(f"/computer-use/{read}") is False


def _wire(monkeypatch, tmp_path):
    om.force_stop()
    monkeypatch.setattr(om, "_disabled", lambda: False)  # el conftest lo apaga; aquí lo ejercemos
    monkeypatch.setattr(om, "_KEEPALIVE", tmp_path / "alive")
    procs: list[_FakeProc] = []

    def _fake_spawn() -> _FakeProc:
        p = _FakeProc()
        procs.append(p)
        return p

    monkeypatch.setattr(om, "_spawn", _fake_spawn)
    return procs


def test_touch_spawns_process_and_refreshes_keepalive(monkeypatch, tmp_path):
    procs = _wire(monkeypatch, tmp_path)
    assert om.is_active() is False

    om.touch()
    assert om.is_active() is True
    assert (tmp_path / "alive").exists()
    assert len(procs) == 1

    om.touch()  # una segunda acción reutiliza el proceso vivo (no rearranca)
    assert len(procs) == 1

    om.force_stop()
    assert om.is_active() is False
    assert procs[0].poll() == 0  # terminado
    assert not (tmp_path / "alive").exists()  # keepalive limpiado


def test_touch_respawns_if_process_died(monkeypatch, tmp_path):
    procs = _wire(monkeypatch, tmp_path)
    om.touch()
    procs[0]._alive = False  # el proceso del halo murió
    om.touch()  # debe rearrancar
    assert len(procs) == 2
    om.force_stop()


def test_session_keeps_overlay_active(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path)
    om.start_session()
    assert om.is_active() is True
    assert om._session_active is True

    om.stop_session()
    assert om._session_active is False  # el halo se apaga solo tras IDLE_TIMEOUT

    om.force_stop()
    assert om.is_active() is False


def test_force_stop_is_safe_when_idle():
    om.force_stop()
    om.force_stop()  # idempotente, no lanza
    assert om.is_active() is False
