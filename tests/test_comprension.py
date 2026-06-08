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
