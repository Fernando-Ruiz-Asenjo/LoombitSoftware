"""
Consolidación de memoria — dedup de lecciones por NEAR-DUPLICADO (estilo Mem0), en el daemon (D-95).

`agent/memory_dedup.py` aporta el dedup determinista (exacto + near-duplicado por solape de tokens);
`aprendizaje.consolidar` lo usa para no acumular variantes casi idénticas. Sin embeddings ni red. El
dedup SEMÁNTICO por paráfrasis (otro vocabulario) es 🟠 declarado. Temas de viaje para no colisionar
con las lecciones fundacionales (fiscal/correo).
"""

from __future__ import annotations

from types import SimpleNamespace

from loombit_operator.agent.memory import AgentMemory
from loombit_operator.agent.memory_dedup import (
    leccion_duplicada,
    solape_jaccard,
    tokens_de,
)
from loombit_operator.aprendizaje import consolidar

_VUELO = "Confirma el número de vuelo con el pasajero antes de reservar"
_VUELO_NEAR = "Confirma el número de vuelo con el pasajero antes de reservar el asiento"
_HOTEL = "Guarda el justificante del hotel en la carpeta del viaje"


# ── Funciones puras del dedup ─────────────────────────────────────────────────


def test_jaccard():
    assert solape_jaccard({"a", "b", "c"}, {"a", "b", "c"}) == 1.0
    assert solape_jaccard({"a", "b"}, {"c", "d"}) == 0.0
    assert solape_jaccard(set(), {"a"}) == 0.0
    assert tokens_de("hola el mundo") == {"hola", "mundo"}  # "el" <4 se descarta


def test_near_duplicada_se_detecta():
    dup = leccion_duplicada(_VUELO_NEAR, [], [{"text": _VUELO, "tags": []}])
    assert dup is not None


def test_exacta_se_detecta():
    dup = leccion_duplicada(_HOTEL, [], [{"text": _HOTEL, "tags": []}])
    assert dup is not None


def test_distinta_no_es_duplicada():
    dup = leccion_duplicada(_HOTEL, [], [{"text": _VUELO, "tags": []}])
    assert dup is None


# ── El daemon de consolidación omite el near-duplicado ────────────────────────


class _FakeIndex:
    def reindexar_memoria(self, memoria=None):
        return {"count": 0, "dim": 0, "indexados": 0}


def test_daemon_omite_near_duplicado(tmp_path):
    mem = AgentMemory(store_path=tmp_path / "mem.json")
    mem.add_lesson(_VUELO, source="manual")
    n_antes = sum(1 for le in mem.lessons if "número de vuelo" in le.text.lower())
    store_runs = SimpleNamespace(list=lambda: [SimpleNamespace(task="reservar vuelo")])
    r = consolidar(
        index=_FakeIndex(),
        memoria=mem,
        store_runs=store_runs,
        reflexionar_fn=lambda run, llm: _VUELO_NEAR,  # near-dup de la existente
        etiquetas_fn=lambda task: [],
        llm=object(),
        max_runs=5,
    )
    # near-dup → no se añade lección nueva, y sigue habiendo UNA sola del vuelo.
    assert r["lecciones_nuevas"] == 0
    n_despues = sum(1 for le in mem.lessons if "número de vuelo" in le.text.lower())
    assert n_despues == n_antes == 1


def test_daemon_si_anade_leccion_distinta(tmp_path):
    mem = AgentMemory(store_path=tmp_path / "mem.json")
    mem.add_lesson(_VUELO, source="manual")
    store_runs = SimpleNamespace(list=lambda: [SimpleNamespace(task="hotel")])
    r = consolidar(
        index=_FakeIndex(),
        memoria=mem,
        store_runs=store_runs,
        reflexionar_fn=lambda run, llm: _HOTEL,  # distinta → sí se añade
        etiquetas_fn=lambda task: [],
        llm=object(),
        max_runs=5,
    )
    assert r["lecciones_nuevas"] == 1
    assert any("justificante del hotel" in le.text.lower() for le in mem.lessons)
