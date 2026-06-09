"""Tests del aprendizaje proactivo (cierra Fase 5): consolidación de memoria programada.

Deterministas: se inyectan índice/memoria/runs/reflexión falsos (sin LM Studio ni embeddings). Se
prueba que reindexa, destila lecciones nuevas, es IDEMPOTENTE (dedup por texto) y nunca rompe.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from loombit_operator import aprendizaje
from loombit_operator.agent.memory import AgentMemory


class _FakeIndex:
    def __init__(self, count=5, dim=768):
        self.calls = 0
        self._info = {"count": count, "dim": dim, "indexados": count}

    def reindexar_memoria(self, memoria=None):
        self.calls += 1
        return self._info


def _store(runs):
    return SimpleNamespace(list=lambda: runs)


def _run(task):
    return SimpleNamespace(task=task, status="completed", steps=[])


def test_consolidar_reindexa_y_destila_lecciones(tmp_path):
    mem = AgentMemory(store_path=tmp_path / "mem.json")
    base = len(mem.lessons)
    runs = [_run("enviar correo a Ana"), _run("crear evento"), _run("nada útil")]
    # reflexión: las dos primeras dan lección; la tercera no (devuelve None) → no se añade.
    refl = lambda run, llm: None if "nada" in run.task else f"Lección de: {run.task}"  # noqa: E731
    res = aprendizaje.consolidar(
        index=_FakeIndex(),
        memoria=mem,
        store_runs=_store(runs),
        reflexionar_fn=refl,
        etiquetas_fn=lambda t: ["tag"],
        llm=None,
        max_runs=3,  # reflexión OPT-IN (el daemon va reindex-only por defecto)
    )
    assert res["docs"] == 5 and res["dim"] == 768
    assert res["runs_revisados"] == 3
    assert res["lecciones_nuevas"] == 2
    assert not res["errores"]
    assert len(mem.lessons) == base + 2
    assert "Aprendizaje:" in res["resumen"]


def test_consolidar_es_idempotente(tmp_path):
    mem = AgentMemory(store_path=tmp_path / "mem.json")
    runs = [_run("tarea A")]
    refl = lambda run, llm: "Una lección concreta y reutilizable"  # noqa: E731
    args = dict(
        index=_FakeIndex(),
        store_runs=_store(runs),
        reflexionar_fn=refl,
        etiquetas_fn=lambda t: [],
        llm=None,
        max_runs=1,
    )
    r1 = aprendizaje.consolidar(memoria=mem, **args)
    n = len(mem.lessons)
    r2 = aprendizaje.consolidar(memoria=mem, **args)  # otra vez: no duplica
    assert r1["lecciones_nuevas"] == 1
    assert r2["lecciones_nuevas"] == 0
    assert len(mem.lessons) == n


def test_reindex_only_por_defecto_no_toca_el_14b(tmp_path):
    """El daemon (max_runs=0) reindexa y NO llama a la reflexión (rápido y fiable)."""

    def _no_llamar(run, llm):
        raise AssertionError("reindex-only NO debe reflexionar (no tocar el 14B)")

    mem = AgentMemory(store_path=tmp_path / "mem.json")
    res = aprendizaje.consolidar(
        index=_FakeIndex(), memoria=mem, store_runs=_store([_run("x")]), reflexionar_fn=_no_llamar
    )
    assert res["docs"] == 5 and res["lecciones_nuevas"] == 0 and res["runs_revisados"] == 0
    assert not res["errores"]


def test_consolidar_nunca_rompe_si_el_indice_falla(tmp_path):
    class _Boom:
        def reindexar_memoria(self, memoria=None):
            raise RuntimeError("sin embeddings")

    mem = AgentMemory(store_path=tmp_path / "mem.json")
    res = aprendizaje.consolidar(
        index=_Boom(),
        memoria=mem,
        store_runs=_store([]),
        reflexionar_fn=lambda r, llm: None,
        etiquetas_fn=lambda t: [],
        llm=None,
    )
    assert res["docs"] == 0 and res["errores"] and "índice" in res["errores"][0]


def test_routine_aprendizaje_esta_sembrada_y_se_despacha(monkeypatch):
    from loombit_operator import routine_executors as rx

    r = rx.aprendizaje_routine()
    assert r.name == "Aprendizaje" and r.output_kind == "aprendizaje"
    assert r.safety.name == "PASSIVE" and r.enabled is True
    monkeypatch.setattr(aprendizaje, "consolidar", lambda **_kw: {"resumen": "OK-TEST"})
    assert rx.default_executor(r, datetime.now()) == "OK-TEST"
