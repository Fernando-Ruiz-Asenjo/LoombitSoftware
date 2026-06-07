"""
Tests de contrato 🟡 para los endpoints de pilot añadidos en la tarea #4:
  POST /computer-use/wait_for_window
  POST /computer-use/click_accessibility
  POST /computer-use/screen_changed

La capa pilot se mockea para no necesitar un escritorio real. Se añaden además
tests de la lógica pura de wait_for_window y screen_changed que no requieren
Windows ni una pantalla activa.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from loombit_operator.main import app

client = TestClient(app)


# ── /wait_for_window ────────────────────────────────────────────────────────


def test_wait_for_window_found():
    fake = {"found": True, "window_title": "Bloc de notas", "waited_seconds": 0.5}
    with patch("loombit_operator.pilot.windows_control.wait_for_window", return_value=fake) as m:
        resp = client.post("/computer-use/wait_for_window", json={"title": "notas", "timeout": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["window_title"] == "Bloc de notas"
    assert "Bloc de notas" in data["result"]
    m.assert_called_once()


def test_wait_for_window_not_found():
    fake = {"found": False, "waited_seconds": 3.0, "error": "La ventana 'X' no apareció en 3s"}
    with patch("loombit_operator.pilot.windows_control.wait_for_window", return_value=fake):
        resp = client.post("/computer-use/wait_for_window", json={"title": "X", "timeout": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is False
    assert data["result"].startswith("ERROR")


# ── /click_accessibility ────────────────────────────────────────────────────


def test_click_accessibility_ok():
    fake = {"clicked": True, "control_name": "Guardar"}
    with patch("loombit_operator.pilot.windows_control.click_accessibility", return_value=fake):
        resp = client.post("/computer-use/click_accessibility", json={"name": "Guardar"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["clicked"] is True
    assert "Guardar" in data["result"]


def test_click_accessibility_error():
    fake = {"clicked": False, "error": "Control no encontrado"}
    with patch("loombit_operator.pilot.windows_control.click_accessibility", return_value=fake):
        resp = client.post("/computer-use/click_accessibility", json={"name": "Nope"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["clicked"] is False
    assert data["result"].startswith("ERROR")


# ── /screen_changed ─────────────────────────────────────────────────────────


def test_screen_changed_true():
    fake = {"changed": True, "fraction": 0.25, "threshold": 0.02, "interval": 0.5}
    with patch("loombit_operator.pilot.screen.screen_changed", return_value=fake):
        resp = client.post("/computer-use/screen_changed", json={"threshold": 0.02})
    assert resp.status_code == 200
    data = resp.json()
    assert data["changed"] is True
    assert "cambió" in data["result"]


def test_screen_changed_false():
    fake = {"changed": False, "fraction": 0.0, "threshold": 0.02}
    with patch("loombit_operator.pilot.screen.screen_changed", return_value=fake):
        resp = client.post("/computer-use/screen_changed", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["changed"] is False
    assert "sin cambios" in data["result"]


def test_screen_changed_pillow_missing():
    with patch(
        "loombit_operator.pilot.screen.screen_changed",
        return_value={"error": "Pillow no instalado"},
    ):
        resp = client.post("/computer-use/screen_changed", json={})
    assert resp.status_code == 200
    assert resp.json()["result"].startswith("ERROR")


# ── Lógica pura (sin escritorio) ────────────────────────────────────────────


def test_wait_for_window_logic_returns_on_match():
    from loombit_operator.pilot import windows_control as wc

    with patch.object(wc, "_match_window_title", return_value="Bloc de notas"):
        result = wc.wait_for_window("notas", timeout=1, poll_interval=0.1)
    assert result["found"] is True
    assert result["window_title"] == "Bloc de notas"


def test_wait_for_window_logic_timeout():
    from loombit_operator.pilot import windows_control as wc

    with patch.object(wc, "_match_window_title", return_value=None):
        result = wc.wait_for_window("inexistente", timeout=0.0, poll_interval=0.1)
    assert result["found"] is False
    assert "no apareció" in result["error"]


def test_click_accessibility_requires_target():
    from loombit_operator.pilot import windows_control as wc

    result = wc.click_accessibility()
    assert result["clicked"] is False
    assert "name" in result["error"]


def test_screen_changed_logic_detects_difference():
    from PIL import Image

    from loombit_operator.pilot import screen as screen_mod

    black = Image.new("RGB", (100, 100), (0, 0, 0))
    quarter = Image.new("RGB", (100, 100), (0, 0, 0))
    for x in range(50):
        for y in range(50):
            quarter.putpixel((x, y), (255, 255, 255))

    with patch("PIL.ImageGrab.grab", side_effect=[black, quarter]):
        result = screen_mod.screen_changed(threshold=0.1, interval=0.0)
    assert result["changed"] is True
    assert 0.24 < result["fraction"] < 0.26


def test_screen_changed_logic_no_difference():
    from PIL import Image

    from loombit_operator.pilot import screen as screen_mod

    grey = Image.new("RGB", (80, 80), (120, 120, 120))

    with patch("PIL.ImageGrab.grab", side_effect=[grey, grey.copy()]):
        result = screen_mod.screen_changed(threshold=0.02, interval=0.0)
    assert result["changed"] is False
    assert result["fraction"] == 0.0
