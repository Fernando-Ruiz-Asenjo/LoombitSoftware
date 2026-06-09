"""Tests del chat de la Fábrica — COGNICIÓN (14B entiende) + red de seguridad determinista.

El chat nunca depende de LM Studio para no quedarse mudo: si el modelo cae, el router por palabras
clave clasifica igual. Si el modelo responde, ENTIENDE la intención aunque no se use la palabra exacta.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from loombit_operator.fabrica import chat


def _stub_caido():
    """Simula LM Studio caído: cualquier .chat() lanza."""

    def _boom(**_kw):
        raise RuntimeError("LM Studio no responde")

    return SimpleNamespace(chat=_boom)


def _stub_listo(intent: dict, narracion: str = "NARRADO"):
    """Stub que distingue la llamada de enrutado (devuelve el intent JSON) de la de narración."""

    def _chat(messages, **_kw):
        sistema = messages[0]["content"] if messages else ""
        if "enrutador COGNITIVO" in sistema:
            return SimpleNamespace(content=json.dumps(intent, ensure_ascii=False))
        return SimpleNamespace(content=narracion)

    return SimpleNamespace(chat=_chat)


# ── Capa 2: red de seguridad determinista (sin modelo) ──────────────────────────
def test_router_keywords_clasifica_estado():
    assert chat._router_keywords("dame el estado", "dame el estado")["accion"] == "estado"


def test_router_keywords_extrae_query_de_radar():
    intent = chat._router_keywords("busca competidores de fyle", "busca competidores de fyle")
    assert intent["accion"] == "radar"
    assert "fyle" in intent["query"]


def test_router_keywords_reparar_extrae_fichero():
    msg = "arregla loombit_operator/agent/prompts.py"
    intent = chat._router_keywords(msg.lower(), msg)
    assert intent["accion"] == "reparar"
    assert intent["ref"].endswith("prompts.py")


def test_router_keywords_gepa():
    assert chat._router_keywords("optimiza el prompt", "optimiza el prompt")["accion"] == "gepa"


def test_router_charla_por_defecto():
    assert chat._router_keywords("qué tal", "qué tal")["accion"] == "charla"


# ── Capa 1: cognición (el modelo entiende aunque no use la palabra exacta) ──────
def test_entender_parsea_intent_json():
    stub = _stub_listo({"accion": "radar", "query": "lonki"})
    intent = chat._entender("¿qué hace lonki por ahí?", None, stub)
    assert intent and intent["accion"] == "radar" and intent["query"] == "lonki"


def test_entender_devuelve_none_si_modelo_cae():
    assert chat._entender("hola", None, _stub_caido()) is None


def test_entender_rechaza_accion_inventada():
    stub = _stub_listo({"accion": "lanzar_misiles"})
    assert chat._entender("haz algo raro", None, stub) is None


def test_json_de_extrae_objeto_envuelto():
    assert chat._json_de('texto antes {"accion": "estado"} basura después') == {"accion": "estado"}
    assert chat._json_de("sin json aquí") is None


# ── Extremo a extremo: el chat nunca rompe y enruta bien ───────────────────────
def test_responder_charla_narra_con_modelo():
    res = chat.responder(
        "hola, ¿quién eres?", llm=_stub_listo({"accion": "charla"}, "Soy la Fábrica.")
    )
    assert res["accion"] == "charla"
    assert "Fábrica" in res["respuesta"]


def test_responder_estado_da_cifras_por_codigo():
    # accion=estado: la respuesta la fija el CÓDIGO (cifras reales), no el modelo.
    res = chat.responder("¿cómo vamos?", llm=_stub_listo({"accion": "estado"}))
    assert res["accion"] == "estado"
    assert "pendientes de tu gate" in res["respuesta"]


def test_responder_sin_modelo_usa_red_de_seguridad():
    # Modelo caído → router por palabras clave → handler estado, sin lanzar.
    res = chat.responder("dame el estado", llm=_stub_caido())
    assert res["accion"] == "estado"


def test_responder_vacio_da_ayuda():
    assert chat.responder("", llm=_stub_caido())["accion"] == "ayuda"


def test_responder_nunca_lanza_aunque_el_handler_falle(monkeypatch):
    def _explota(*_a, **_k):
        raise ValueError("boom")

    monkeypatch.setitem(chat._HANDLERS, "estado", _explota)
    res = chat.responder("estado", llm=_stub_caido())
    assert res["accion"] == "error" and "No pude" in res["respuesta"]
