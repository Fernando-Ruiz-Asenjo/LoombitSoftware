"""Arnés del centinela de El Muro (el miembro always-on): salud pura + routine + dispatch."""

from datetime import datetime

from loombit_operator.el_muro_centinela import (
    CENTINELA_KIND,
    CENTINELA_NOMBRE,
    centinela_executor,
    centinela_routine,
    ensure_centinela,
    salud_muro,
)
from loombit_operator.routines import RoutineStore
from loombit_operator.skills import SkillSafetyClass


def test_salud_muro_todo_sano():
    sano, lineas = salud_muro([], [], 44, 2)
    assert sano is True
    assert "SANO" in lineas[0]
    assert any("RADAR OK" in ln for ln in lineas)
    assert any("CADENA OK" in ln for ln in lineas)


def test_salud_muro_radar_caducado_no_esta_sano():
    sano, lineas = salud_muro(["radar caducado (60 > 45 dias)"], [], 5, 2)
    assert sano is False
    assert "ATENCIÓN" in lineas[0]
    assert any("RADAR FALLO" in ln for ln in lineas)


def test_salud_muro_cadena_rota_no_esta_sano():
    sano, lineas = salud_muro([], ["bloque 1: hash no cuadra"], 44, 2)
    assert sano is False
    assert any("CADENA FALLO" in ln for ln in lineas)


def test_salud_muro_ambos_rotos():
    sano, _ = salud_muro(["x"], ["y"], 0, 0)
    assert sano is False


def test_centinela_routine_es_passive_readonly():
    r = centinela_routine()
    assert r.name == CENTINELA_NOMBRE
    assert r.output_kind == CENTINELA_KIND
    assert r.safety == SkillSafetyClass.PASSIVE  # read-only: sin gate
    assert r.enabled is True


def test_ensure_centinela_idempotente(tmp_path):
    store = RoutineStore(store_path=tmp_path / "routines.json")
    ensure_centinela(store)
    ensure_centinela(store)
    cent = [r for r in store.list() if r.name == CENTINELA_NOMBRE]
    assert len(cent) == 1


def test_build_scheduler_despacha_por_tipo(tmp_path, monkeypatch):
    import loombit_operator.el_muro_centinela as cen
    import loombit_operator.routine_executors as rx

    monkeypatch.setattr(rx, "default_executor", lambda routine, now: "DEFAULT")
    monkeypatch.setattr(cen, "centinela_executor", lambda routine, now: "CENT")
    store = RoutineStore(store_path=tmp_path / "routines.json")
    sched = cen.build_scheduler_con_centinela(store=store)
    now = datetime(2026, 6, 14, 7, 0)

    cent = next(r for r in sched.store.list() if r.output_kind == CENTINELA_KIND)
    otra = next(r for r in sched.store.list() if r.output_kind != CENTINELA_KIND)
    assert sched.executor(cent, now) == "CENT"
    assert sched.executor(otra, now) == "DEFAULT"


def test_centinela_executor_reporta_estructura():
    # Integración ligera contra los ficheros reales: el reporte menciona ambos chequeos,
    # sea cual sea el veredicto (robusto a la fecha).
    out = centinela_executor(centinela_routine(), datetime(2026, 6, 14, 7, 0))
    assert "El Muro" in out
    assert "RADAR" in out
    assert "CADENA" in out
