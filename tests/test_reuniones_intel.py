"""
Destilación inteligente de reuniones (el caso David: calendario lunes 15 vs correo jueves 11).
Loombit debe ACERTAR (jueves 11, 09:00, Calle Manzana 8) sin pedirle al usuario que revise.
"""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

from loombit_operator import reuniones_intel as ri

LUNES = date(2026, 6, 8)


class _LLM:
    """LLM falso: devuelve un `content` fijo (lo que el modelo real devolvería)."""

    def __init__(self, content: str):
        self._content = content

    def chat(self, messages, **_):
        return SimpleNamespace(content=self._content)


def test_caso_david_correo_manda_sobre_calendario():
    llm = _LLM(
        json.dumps(
            [
                {
                    "con": "David Valentín",
                    "fecha": "2026-06-11",
                    "hora": "09:00",
                    "lugar": "Calle Manzana, 8 Local, Getafe",
                    "fuente": "correo",
                    "conflicto": True,
                    "nota": "tu calendario la tiene el lunes 15",
                    "origen": "RE: BAREMOS BRICOS Y MANTENIMIENTOS",
                }
            ]
        )
    )
    out = ri.destilar_reuniones(
        correos=[
            {"from": "David", "subject": "RE: BAREMOS", "snippet": "nos vemos el jueves 11 a las 9"}
        ],
        eventos=[{"start": "2026-06-15T09:00:00", "summary": "Reunión con David"}],
        hoy=LUNES,
        llm=llm,
        usar_cache=False,
    )
    assert len(out) == 1
    r = out[0]
    assert (
        r["fecha"] == "2026-06-11" and r["hora"] == "09:00"
    )  # la VERDAD del correo, no el calendario
    assert r["dia_semana"] == "jueves"
    assert "Getafe" in r["lugar"]
    assert r["fuente"] == "correo" and r["conflicto"] is True
    assert "15" in r["nota"]


def test_descarta_fechas_pasadas_e_invalidas():
    llm = _LLM(
        json.dumps(
            [
                {"con": "X", "fecha": "2026-06-01", "hora": "09:00", "origen": "vieja"},  # pasada
                {"con": "Y", "fecha": "ayer", "hora": "10:00", "origen": "basura"},  # inválida
                {
                    "con": "Z",
                    "fecha": "2026-06-20",
                    "hora": "1057",
                    "origen": "buena",
                },  # válida, hora 4 díg
            ]
        )
    )
    out = ri.destilar_reuniones([{"subject": "algo"}], [], LUNES, llm=llm, usar_cache=False)
    assert [m["con"] for m in out] == ["Z"]
    assert out[0]["hora"] == "10:57"  # normaliza 1057 -> 10:57


def test_fallback_al_calendario_si_el_llm_falla():
    class _Boom:
        def chat(self, *a, **k):
            raise RuntimeError("LLM caído")

    out = ri.destilar_reuniones(
        correos=[],
        eventos=[
            {
                "start": "2026-06-15T11:00:00",
                "summary": "Reunión con David Valentin",
                "location": "Getafe",
            }
        ],
        hoy=LUNES,
        llm=_Boom(),
        usar_cache=False,
    )
    # sin LLM: el calendario tal cual (autoritativo), SIN la regex ruidosa
    assert len(out) == 1
    assert out[0]["fecha"] == "2026-06-15" and out[0]["con"] == "David Valentin"
    assert out[0]["fuente"] == "calendario" and out[0]["conflicto"] is False


def test_extraer_json_tolera_fences_y_texto():
    data = ri._extraer_json('Claro, aquí tienes:\n```json\n[{"con":"A","fecha":"2026-06-20"}]\n```')
    assert data == [{"con": "A", "fecha": "2026-06-20"}]


def test_contraparte_saca_el_nombre():
    assert ri._contraparte("Reunión con David Valentin") == "David Valentin"
    assert ri._contraparte("Cita con Gestoría") == "Gestoría"
    assert ri._contraparte("Comida de equipo") == ""


def test_recopilar_contexto_busca_al_interlocutor_de_cada_reunion():
    # El hilo donde se acordó la fecha real puede ser MÁS VIEJO que la bandeja reciente: por eso se
    # busca al interlocutor de la reunión en TODO el Gmail y se mete en contexto.
    correos = [{"from": "x@y.com", "subject": "factura"}]
    eventos = [{"summary": "Reunión con David"}]
    llamadas = []

    def buscar(nombre):
        llamadas.append(nombre)
        return [{"from": "David", "subject": "RE: BAREMOS", "snippet": "el jueves 11 a las 9"}]

    ctx = ri._recopilar_contexto(correos, eventos, buscar)
    asuntos = [c["subject"] for c in ctx]
    assert llamadas == ["David"]  # buscó al interlocutor del evento
    assert "RE: BAREMOS" in asuntos and "factura" in asuntos  # junta reciente + búsqueda
