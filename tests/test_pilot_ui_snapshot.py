"""
Tests del snapshot de accesibilidad (UIA) del Pilot.

La lógica pura (_describe_control, _is_actionable) se prueba con controles
falsos; ui_snapshot se prueba en el camino sin pywinauto; el endpoint se
prueba mockeando la capa pilot.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from loombit_operator.main import app
from loombit_operator.pilot import windows_control as wc

client = TestClient(app)


class _Rect:
    def __init__(self, left, top, right, bottom):
        self.left, self.top, self.right, self.bottom = left, top, right, bottom


class _Info:
    def __init__(self, control_type, automation_id, enabled=True):
        self.control_type = control_type
        self.automation_id = automation_id
        self.enabled = enabled


class _Ctrl:
    def __init__(self, text, control_type, aid, rect, enabled=True, value=None):
        self._text = text
        self.element_info = _Info(control_type, aid, enabled)
        self._rect = rect
        self._value = value

    def window_text(self):
        return self._text

    def rectangle(self):
        return self._rect

    def get_value(self):
        if self._value is None:
            raise RuntimeError("no value pattern")
        return self._value


def test_describe_control_basic():
    ctrl = _Ctrl("Guardar", "Button", "saveBtn", _Rect(10, 20, 110, 60))
    desc = wc._describe_control(ctrl)
    assert desc["name"] == "Guardar"
    assert desc["control_type"] == "Button"
    assert desc["automation_id"] == "saveBtn"
    assert desc["center"] == [60, 40]
    assert desc["enabled"] is True
    assert desc["offscreen"] is False
    assert "value" not in desc


def test_describe_control_with_value_and_disabled():
    ctrl = _Ctrl("Importe", "Edit", "amount", _Rect(0, 0, 50, 20), enabled=False, value="1.250 €")
    desc = wc._describe_control(ctrl)
    assert desc["value"] == "1.250 €"
    assert desc["enabled"] is False


def test_describe_control_offscreen_zero_size():
    ctrl = _Ctrl("hidden", "Button", "", _Rect(5, 5, 5, 5))
    desc = wc._describe_control(ctrl)
    assert desc["offscreen"] is True


def test_is_actionable():
    assert wc._is_actionable({"control_type": "Button"}) is True
    assert wc._is_actionable({"control_type": "Edit"}) is True
    assert wc._is_actionable({"control_type": "Text"}) is False


def test_ui_snapshot_without_pywinauto(monkeypatch):
    monkeypatch.setattr(wc, "_PYWINAUTO_OK", False)
    result = wc.ui_snapshot(title="cualquiera")
    assert result["controls"] == []
    assert "error" in result
    assert "hint" in result


def test_ui_snapshot_endpoint_formats_controls():
    fake = {
        "controls": [
            {
                "name": "Guardar",
                "control_type": "Button",
                "automation_id": "saveBtn",
                "center": [60, 40],
                "enabled": True,
            }
        ],
        "total": 1,
        "window_title": "Bloc de notas",
    }
    with patch("loombit_operator.pilot.windows_control.ui_snapshot", return_value=fake):
        resp = client.post("/computer-use/ui_snapshot", json={"title": "Bloc"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert "Guardar" in data["result"]
    assert data["controls"][0]["automation_id"] == "saveBtn"
