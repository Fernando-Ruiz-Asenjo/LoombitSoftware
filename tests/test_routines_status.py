"""
S1: el endpoint de estado del agente proactivo ('Loombit está trabajando…').

Expone el latido del daemon + el inventario de routines + el recuento de novedades,
para que la UI muestre que Loombit trabaja solo en segundo plano.
"""

from fastapi.testclient import TestClient

from loombit_operator.main import app


def test_status_sin_daemon_reporta_reposo():
    """En tests el daemon está apagado (opt-in): el estado debe ser legible y honesto,
    no 'trabajando', y listar las routines sembradas por defecto."""
    client = TestClient(app)
    r = client.get("/routines/status")
    assert r.status_code == 200
    body = r.json()
    assert body["trabajando"] is False
    assert "daemon" in body and body["daemon"]["running"] is False
    nombres = {x["name"] for x in body["routines"]}
    assert "Brief diario" in nombres  # routine por defecto
    assert isinstance(body["novedades"], int)


def test_status_expone_latido_cuando_hay_daemon():
    """Si hay un daemon en app.state con latido, el estado lo refleja como 'trabajando'."""

    class _FakeDaemon:
        def status(self):
            return {
                "running": True,
                "interval_seconds": 60,
                "started_at": "2026-06-11T08:00:00+00:00",
                "last_tick_at": "2026-06-11T08:01:00+00:00",
                "tick_count": 1,
                "last_fired_count": 0,
                "last_error": None,
            }

    app.state.daemon = _FakeDaemon()
    try:
        body = TestClient(app).get("/routines/status").json()
        assert body["trabajando"] is True
        assert "trabajando" in body["mensaje"].lower()
        assert body["daemon"]["tick_count"] == 1
    finally:
        app.state.daemon = None
