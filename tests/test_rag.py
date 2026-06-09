"""Tests del índice semántico local (RAG, P1).

Deterministas: se inyecta un embedder bag-of-words estable (sin LM Studio), de modo que dos textos
que comparten palabras quedan más cerca en coseno → se prueba la recuperación por SIGNIFICADO, la
persistencia, el dedup por id y la construcción del corpus desde la memoria operativa real.
"""

from __future__ import annotations

import re

from loombit_operator.agent.memory import AgentMemory
from loombit_operator.rag import SemanticIndex, _coseno

_DIM = 96


def _fake_embed(texts: list[str]) -> list[list[float]]:
    """Embedding bag-of-words estable (hash por suma de ords → bucket). Determinista entre procesos."""
    out: list[list[float]] = []
    for t in texts:
        v = [0.0] * _DIM
        for w in re.findall(r"[a-záéíóúñ0-9]+", t.lower()):
            v[sum(ord(c) for c in w) % _DIM] += 1.0
        out.append(v)
    return out


def _idx(tmp_path) -> SemanticIndex:
    return SemanticIndex(path=tmp_path / "rag.json", embed_fn=_fake_embed)


def test_coseno_basico():
    assert _coseno([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert _coseno([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert _coseno([], [1.0]) == 0.0


def test_busqueda_recupera_por_significado(tmp_path):
    idx = _idx(tmp_path)
    idx.add("a", "enviar un correo a un cliente importante")
    idx.add("b", "calcular el IVA del trimestre para el 303")
    idx.add("c", "agendar una reunión en el calendario")
    res = idx.search("redactar un email para ese cliente", k=2)
    assert res and res[0]["id"] == "a"  # comparte 'cliente'/'un' → gana al IVA y a la reunión


def test_dedup_por_id_no_duplica(tmp_path):
    idx = _idx(tmp_path)
    idx.add("x", "primer texto")
    idx.add("x", "texto actualizado del mismo id")
    assert idx.stats()["count"] == 1


def test_filtra_por_fuente(tmp_path):
    idx = _idx(tmp_path)
    idx.add("h", "factura del proveedor", meta={"fuente": "history"})
    idx.add("l", "lección sobre la factura recibida", meta={"fuente": "lesson"})
    res = idx.search("factura", k=5, fuente="lesson")
    assert all(r["meta"]["fuente"] == "lesson" for r in res) and res


def test_persistencia(tmp_path):
    idx = _idx(tmp_path)
    idx.add("p", "algo memorable que persiste")
    otro = SemanticIndex(path=tmp_path / "rag.json", embed_fn=_fake_embed)
    assert otro.stats()["count"] == 1
    assert otro.search("memorable", k=1)[0]["id"] == "p"


def test_busqueda_vacia_no_rompe(tmp_path):
    idx = _idx(tmp_path)
    assert idx.search("lo que sea", k=3) == []  # índice vacío
    idx.add("a", "hola")
    assert idx.search("", k=3) == []  # query vacía


def test_reindexar_memoria_indexa_todas_las_fuentes(tmp_path):
    mem = AgentMemory(store_path=tmp_path / "mem.json")
    mem.add_history("Enviar informe a Jana", "✅ enviado", tools_used=["gmail_send"], run_id="r1")
    mem.add_lesson("No inventes el email del destinatario", tags=["correo"])
    mem.upsert_entity("Acme SL", nif="B12345678", iban="ES7600000000000000000000")
    mem.add_contact("Jana Wall", "jana@acme.com", company="Acme")
    mem.add_procedure("enviar_correo", steps=["contacts_find", "gmail_send"], tools=["gmail_send"])

    idx = _idx(tmp_path)
    info = idx.reindexar_memoria(memoria=mem)
    assert info["indexados"] >= 5
    fuentes = info["por_fuente"]
    for f in ("history", "lesson", "entity", "contact", "procedure"):
        assert fuentes.get(f, 0) >= 1
    # y se puede recuperar por significado lo indexado
    assert idx.search("correo a Jana", k=3)


def test_reindexar_es_idempotente(tmp_path):
    mem = AgentMemory(store_path=tmp_path / "mem.json")
    mem.add_history("tarea uno", "ok", run_id="r1")
    idx = _idx(tmp_path)
    idx.reindexar_memoria(memoria=mem)
    n1 = idx.stats()["count"]
    idx.reindexar_memoria(memoria=mem)  # otra vez: no debe duplicar
    assert idx.stats()["count"] == n1
