"""
GET /habitos — hace VISIBLE lo que Loombit ha aprendido de ti (transparencia = confianza).
Cada patrón fuerte con su nivel de anticipación A0–A3. Editable/desactivable es trabajo futuro;
aquí se expone, honesto: si no hay datos, lista vacía (no inventa hábitos).
"""

from fastapi.testclient import TestClient

from loombit_operator.habitos import HabitLedger
from loombit_operator.main import app


def test_habitos_endpoint_lista_patrones_con_nivel(tmp_path, monkeypatch):
    import loombit_operator.routers.habitos as rh

    led = HabitLedger(path=tmp_path / "h.json", racha_autonomia=5)
    for _ in range(5):
        led.registrar("respuesta", "javier@x.com", "aceptada")  # → A3
    for _ in range(4):
        led.registrar("respuesta", "news@x.com", "rechazada")  # → silenciado
    monkeypatch.setattr(rh, "get_habits", lambda: led)

    body = TestClient(app).get("/habitos").json()
    por_sujeto = {h["sujeto"]: h for h in body["habitos"]}
    assert por_sujeto["javier@x.com"]["anticipacion"] == "A3"
    assert por_sujeto["javier@x.com"]["veredicto"] == "sueles_aceptar"
    assert por_sujeto["news@x.com"]["veredicto"] == "sueles_ignorar"


def test_habitos_endpoint_vacio_es_honesto(monkeypatch, tmp_path):
    import loombit_operator.routers.habitos as rh

    monkeypatch.setattr(rh, "get_habits", lambda: HabitLedger(path=tmp_path / "vacio.json"))
    body = TestClient(app).get("/habitos").json()
    assert body["count"] == 0
    assert body["habitos"] == []
