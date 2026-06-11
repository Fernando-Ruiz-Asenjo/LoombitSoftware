"""
S1: la Tela (static/loombit.html) cablea el badge del agente proactivo ("Loombit está
trabajando…") contra /routines/status. Regresión: que el cableado no desaparezca en silencio.
(La verificación VISUAL en vivo queda para el escritorio real; aquí se comprueba que la página
se sirve y contiene el enganche.)
"""

from fastapi.testclient import TestClient

from loombit_operator.main import app


def test_tela_sirve_y_cablea_estado_proactivo():
    r = TestClient(app).get("/static/loombit.html")
    assert r.status_code == 200
    html = r.text
    assert 'id="estado-chip"' in html  # el chip de estado existe
    assert "/routines/status" in html  # lo sondea contra el endpoint real
    assert "Loombit trabajando" in html  # el texto del latido activo
