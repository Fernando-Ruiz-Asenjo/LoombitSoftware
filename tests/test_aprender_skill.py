"""
S2 (paridad Spark): "Enséñale" — de una orden en lenguaje natural a una Routine reutilizable
y auto-disparada. El horario lo dispone el CÓDIGO de forma determinista (no el LLM); el efecto
externo pasa por aprobación. Aquí se verifica el parseo y la creación (reproducible, sin LLM).
"""

import pytest

from loombit_operator.aprender_skill import (
    DEFAULT_POLL,
    crear_skill_desde_texto,
    interpretar_horario,
)
from loombit_operator.routines import RoutineStore
from loombit_operator.skills import SkillSafetyClass


def _store(tmp_path):
    return RoutineStore(store_path=tmp_path / "routines.json")


# ── Parseo determinista de horario (texto español → cron de 5 campos) ────────


def test_interpretar_dia_semana_con_hora():
    assert interpretar_horario("cada lunes a las 9")["cron"] == "0 9 * * 1"
    assert interpretar_horario("los viernes a las 14:30")["cron"] == "30 14 * * 5"


def test_interpretar_diario():
    assert interpretar_horario("todos los días a las 8")["cron"] == "0 8 * * *"
    assert interpretar_horario("cada mañana")["cron"] == "0 8 * * *"  # mañana = 08:00 por defecto


def test_interpretar_frecuencias():
    assert interpretar_horario("cada 15 minutos")["cron"] == "*/15 * * * *"
    assert interpretar_horario("cada hora")["cron"] == "0 * * * *"
    assert interpretar_horario("cada 2 horas")["cron"] == "0 */2 * * *"


def test_interpretar_hora_sola_es_diaria():
    assert interpretar_horario("recuérdamelo a las 18:00")["cron"] == "0 18 * * *"


def test_interpretar_tarde_pm():
    assert interpretar_horario("cada día a las 5 de la tarde")["cron"] == "0 17 * * *"


def test_interpretar_sin_horario_es_none():
    assert interpretar_horario("cuando entre una factura de Telefónica") is None


# ── Creación de la skill enseñada ────────────────────────────────────────────


def test_crear_skill_programada(tmp_path):
    store = _store(tmp_path)
    texto = "cada lunes a las 9 mándame el resumen de cobros vencidos"
    res = crear_skill_desde_texto(texto, store)
    assert res["cron"] == "0 9 * * 1"
    assert res["evento"] is False
    r = res["routine"]
    assert r["objective"] == texto
    assert r["safety"] == SkillSafetyClass.ASSISTED  # todo efecto externo PAUSA para aprobación
    assert r["output_kind"] == "agente"
    assert r["enabled"] is True
    # persistida y recuperable
    assert any(
        x.objective == texto for x in RoutineStore(store_path=tmp_path / "routines.json").list()
    )


def test_crear_skill_por_evento_usa_sondeo(tmp_path):
    res = crear_skill_desde_texto(
        "cuando entre una factura de Telefónica, regístrala", _store(tmp_path)
    )
    assert res["evento"] is True
    assert res["cron"] == DEFAULT_POLL


def test_texto_vacio_se_rechaza(tmp_path):
    with pytest.raises(ValueError):
        crear_skill_desde_texto("   ", _store(tmp_path))


def test_endpoint_aprender_crea_y_lista(tmp_path, monkeypatch):
    """POST /routines/aprender crea la skill y aparece luego en GET /routines."""
    from fastapi.testclient import TestClient

    import loombit_operator.routers.routines as rr
    from loombit_operator.routine_executors import ensure_default_routines

    # Aísla el store del router en tmp (no toca el de producción).
    monkeypatch.setattr(
        rr, "_store", lambda: ensure_default_routines(RoutineStore(store_path=tmp_path / "r.json"))
    )

    from loombit_operator.main import app

    client = TestClient(app)
    r = client.post("/routines/aprender", json={"texto": "cada lunes a las 9 dame los cobros"})
    assert r.status_code == 200
    assert r.json()["cron"] == "0 9 * * 1"

    objetivos = [x["objective"] for x in client.get("/routines").json()["routines"]]
    assert "cada lunes a las 9 dame los cobros" in objetivos

    bad = client.post("/routines/aprender", json={"texto": "   "})
    assert bad.status_code == 400
