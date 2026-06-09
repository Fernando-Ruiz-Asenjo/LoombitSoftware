"""
Comprensión de la bandeja (Skill D · Comprensión). Cognición, no extracción: entiende el hilo
(quién, de qué va, estado) y de ahí salen reuniones reconciliadas, notificaciones oficiales, plazos.
FIABLE: cacheada + segundo plano; ante fallo del LLM conserva lo último bueno, nunca el calendario crudo.
"""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from loombit_operator import comprension as cp

LUNES = date(2026, 6, 8)


class _LLM:
    def __init__(self, content):
        self._c = content

    def chat(self, messages, **_):
        return SimpleNamespace(content=self._c)


class _Boom:
    def chat(self, *a, **k):
        raise RuntimeError("LLM caído")


@pytest.fixture(autouse=True)
def _cache_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(cp, "_cache_path", lambda: tmp_path / "comprension.json")


def test_comprende_reunion_confirmada_y_notificacion_oficial():
    llm = _LLM(
        json.dumps(
            [
                {
                    "tipo": "reunion",
                    "titulo": "Reunión con David Valentín",
                    "con": "David Valentín",
                    "resumen": "ambos confirmasteis",
                    "estado": "confirmada",
                    "fecha": "2026-06-11",
                    "hora": "9:00",
                    "lugar": "Calle Manzana, 8 Local, Getafe",
                    "importancia": 3,
                    "accion": "",
                    "origen": "RE: BAREMOS",
                },
                {
                    "tipo": "notificacion",
                    "titulo": "Notificación de la Policía",
                    "con": "DGP",
                    "resumen": "trámite del DNI",
                    "estado": "requiere_accion",
                    "importancia": 3,
                    "accion": "revisar la notificación",
                    "origen": "Notificación Dirección General de la Policía",
                },
            ]
        )
    )
    out = cp.comprender([{"subject": "x"}], [], LUNES, llm=llm)
    assert len(out) == 2
    r = next(a for a in out if a["tipo"] == "reunion")
    assert r["fecha"] == "2026-06-11" and r["hora"] == "09:00" and r["estado"] == "confirmada"
    assert "Getafe" in r["lugar"] and r["dia_semana"] == "jueves"
    n = next(a for a in out if a["tipo"] == "notificacion")
    assert n["importancia"] == 3 and n["estado"] == "requiere_accion"


def test_descarta_pasado_y_normaliza_tipos():
    llm = _LLM(
        json.dumps(
            [
                {
                    "tipo": "reunion",
                    "titulo": "vieja",
                    "fecha": "2026-06-01",
                    "origen": "x",
                },  # pasada
                {"tipo": "raro", "titulo": "sin tipo válido", "origen": "y"},  # tipo→gestion
            ]
        )
    )
    out = cp.comprender([{"subject": "x"}], [], LUNES, llm=llm)
    assert [a["titulo"] for a in out] == ["sin tipo válido"]
    assert out[0]["tipo"] == "gestion"


def test_comprender_devuelve_none_si_el_llm_falla():
    # None = "no pude"; el llamador conserva lo último bueno. NUNCA cae al calendario crudo.
    assert cp.comprender([{"subject": "x"}], [], LUNES, llm=_Boom()) is None


def test_cache_persistencia_round_trip(tmp_path):
    cp._guardar([{"tipo": "reunion", "titulo": "T"}])
    asuntos, edad = cp.comprension_cacheada()
    assert asuntos == [{"tipo": "reunion", "titulo": "T"}]
    assert edad < 5  # recién guardado


def test_refrescar_conserva_lo_bueno_si_el_llm_falla():
    cp._guardar([{"tipo": "reunion", "titulo": "BUENO"}])  # último resultado bueno
    out = cp.refrescar(
        [{"subject": "x"}], [], LUNES, llm=_Boom()
    )  # LLM falla → conserva lo cacheado
    assert any(a.get("titulo") == "BUENO" for a in out)


def test_comprension_vacia_sin_entradas():
    assert cp.comprender([], [], LUNES, llm=_LLM("[]")) == []


def test_dedup_un_asunto_por_hilo_aunque_el_llm_lo_repita():
    """El LLM a veces emite un asunto por CADA correo del hilo → el telar mostraba la misma deuda
    4 veces. DEDUP determinista: una sola entrada por (titulo, tipo, con)."""
    item = {
        "tipo": "notificacion",
        "titulo": "Deuda no reconocida de Abogados CEA",
        "con": "Abogados CEA",
        "resumen": "reclaman pago",
        "estado": "requiere_accion",
        "importancia": 3,
        "origen": "Email notificacion",
    }
    # incluye una reunión con tilde y sin tilde (el LLM varía el acento) → mismo asunto
    r1 = {
        "tipo": "reunion",
        "titulo": "Reunión con David Valentín",
        "con": "David Valentín",
        "estado": "confirmada",
        "importancia": 2,
        "fecha": "2026-06-11",
        "hora": "9:00",
        "origen": "a",
    }
    # mismo día/hora/persona pero el LLM redacta otro título y varía la tilde → mismo evento
    r2 = dict(
        r1, titulo="Reunión con David Valentin sobre baremos", con="David Valentin", origen="b"
    )
    # 3 redacciones reales de la MISMA deuda: distinto titulo y 'con', mismo origen -> 1
    d2 = dict(item, titulo="No reconozco esta deuda", con="")
    d3 = dict(item, titulo="Deuda no reconocida por WiBLE", con="wible.recobros@abogadoscea.es")
    llm = _LLM(json.dumps([item, d2, d3, r1, r2]))
    out = cp.comprender([{"subject": "x"}], [], LUNES, llm=llm)
    assert len([a for a in out if "deuda" in (a["titulo"] + a["resumen"]).lower()]) == 1
    assert len([a for a in out if "valent" in a["titulo"].lower()]) == 1  # tilde-insensible


def test_deuda_no_reconocida_escala_a_fraude_aunque_el_llm_la_minimice():
    """Guard DETERMINISTA: aunque el LLM la marque 'informativa'/poco importante, una deuda que NO
    se reconoce es posible fraude → importancia 3 + requiere_accion, con acción de VERIFICAR."""
    llm = _LLM(
        json.dumps(
            [
                {
                    "tipo": "notificacion",
                    "titulo": "Deuda no reconocida de Abogados CEA",
                    "con": "Abogados CEA",
                    "resumen": "reclaman una deuda que no reconoces",
                    "estado": "informativa",  # el LLM la minimiza…
                    "importancia": 1,  # …y la baja
                    "accion": "",
                    "origen": "Email notificacion",
                },
            ]
        )
    )
    out = cp.comprender([{"subject": "x"}], [], LUNES, llm=llm)
    assert len(out) == 1
    a = out[0]
    assert a["importancia"] == 3
    assert a["estado"] == "requiere_accion"
    assert a["accion"]  # ya no está vacía: dice VERIFICAR, no pagar a ciegas
    assert "verifica" in a["accion"].lower()


def test_salva_objetos_de_array_truncado():
    """El 14B corta a max_tokens y deja el último objeto a medias. No debemos perder TODO (eso caía
    al caché viejo = no-determinismo): se recuperan los objetos completos."""
    truncado = (
        '[\n{"tipo":"reunion","titulo":"A","origen":"a"},\n'
        '{"tipo":"plazo","titulo":"B","origen":"b"},\n'
        '{"tipo":"notificacion","titulo":"C cortad'  # ← truncado a media cadena
    )
    objs = cp._salvar_objetos(truncado)
    assert [o["titulo"] for o in objs] == ["A", "B"]


def test_comprender_recupera_aunque_el_array_venga_truncado():
    llm = _LLM(
        '[\n{"tipo":"reunion","titulo":"Reunión A","origen":"a","importancia":2},\n'
        '{"tipo":"plazo","titulo":"Plazo B","origen":"b","importancia":2},\n'
        '{"tipo":"notificacion","titulo":"C a medio gener'  # truncado
    )
    out = cp.comprender([{"subject": "x"}], [], LUNES, llm=llm)
    assert out is not None
    assert {a["titulo"] for a in out} == {"Reunión A", "Plazo B"}


def test_informe_automatico_sin_fecha_se_baja_a_informativa():
    """Guard DETERMINISTA: un informe automático/marketing sin fecha no debe pedir acción ni colarse
    como urgente, aunque el LLM lo sobre-escale."""
    llm = _LLM(
        json.dumps(
            [
                {
                    "tipo": "notificacion",
                    "titulo": "Informe de rendimiento Google Business Profile",
                    "resumen": "informe de rendimiento de mayo de 2026",
                    "estado": "requiere_accion",  # el LLM lo sobre-escala
                    "importancia": 2,
                    "origen": "Google Business Profile",
                },
            ]
        )
    )
    out = cp.comprender([{"subject": "x"}], [], LUNES, llm=llm)
    assert len(out) == 1
    assert out[0]["estado"] == "informativa"
    assert out[0]["importancia"] == 1
