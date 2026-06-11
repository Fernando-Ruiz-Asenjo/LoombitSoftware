"""
Priorizador determinista del telar (Generative Agents: recency·importance·relevance), donde la
'relevance' la aportan los HÁBITOS del usuario. El ORDEN lo decide código; el LLM no interviene.
Objetivo #3 del backlog del asistente proactivo (docs/INVESTIGACION_ASISTENTE_PROACTIVO_2026.md).
"""

from loombit_operator.habitos import HabitLedger
from loombit_operator.priorizador import (
    normaliza_importancia,
    ordenar,
    puntuar,
    recency_por_plazo,
)


def test_recency_vencido_o_hoy_es_maxima():
    assert recency_por_plazo(0) == 1.0
    assert recency_por_plazo(-5) == 1.0  # ya vencido → urgencia máxima
    # decae con los días futuros: a una vida media, la mitad
    assert recency_por_plazo(3, vida_media=3) == 0.5
    assert recency_por_plazo(6, vida_media=3) == 0.25


def test_normaliza_importancia_clampa():
    assert normaliza_importancia(3) == 1.0
    assert normaliza_importancia(2) == round(2 / 3, 4)
    assert normaliza_importancia(1) == round(1 / 3, 4)
    assert normaliza_importancia(9) == 1.0  # fuera de rango → clamp
    assert normaliza_importancia(0) == round(1 / 3, 4)


def test_puntuar_combina_los_tres_componentes():
    # pesos iguales: (imp=1.0 + recency=1.0 + relevancia=0.5) / 3
    s = puntuar(importancia=3, recency=1.0, relevancia=0.5)
    assert s == round((1.0 + 1.0 + 0.5) / 3, 4)
    # a igualdad de importancia/recency, más relevancia → más score
    assert puntuar(importancia=2, recency=0.5, relevancia=0.9) > puntuar(
        importancia=2, recency=0.5, relevancia=0.1
    )


def test_ordenar_cobro_vencido_por_encima_de_reunion_lejana():
    hilos = [
        {"id": "reunion", "tipo": "reunion", "urgencia": 1, "dias_hasta": 10},
        {"id": "cobro", "tipo": "cobro", "urgencia": 3, "dias_hasta": -2},
    ]
    out = ordenar(hilos, habitos=None)
    assert [h["id"] for h in out] == ["cobro", "reunion"]
    assert out[0]["score"] >= out[1]["score"]


def test_los_habitos_suben_lo_que_sueles_aceptar(tmp_path):
    h = HabitLedger(path=tmp_path / "h.json")
    for _ in range(4):
        h.registrar("respuesta", "javier@x.com", "aceptada")  # patrón: sueles aceptar a Javier
    hilos = [
        {
            "id": "neutro",
            "tipo": "respuesta",
            "sujeto": "otro@x.com",
            "urgencia": 2,
            "dias_hasta": 1,
        },
        {
            "id": "javier",
            "tipo": "respuesta",
            "sujeto": "javier@x.com",
            "urgencia": 2,
            "dias_hasta": 1,
        },
    ]
    out = ordenar(hilos, habitos=h)
    assert [x["id"] for x in out] == ["javier", "neutro"]  # el hábito desempata hacia arriba


def test_los_habitos_bajan_lo_que_sueles_ignorar(tmp_path):
    h = HabitLedger(path=tmp_path / "h.json")
    for _ in range(4):
        h.registrar("respuesta", "news@x.com", "rechazada")  # sueles ignorar
    hilos = [
        {"id": "news", "tipo": "respuesta", "sujeto": "news@x.com", "urgencia": 2, "dias_hasta": 1},
        {
            "id": "neutro",
            "tipo": "respuesta",
            "sujeto": "otro@x.com",
            "urgencia": 2,
            "dias_hasta": 1,
        },
    ]
    out = ordenar(hilos, habitos=h)
    assert [x["id"] for x in out] == ["neutro", "news"]


def test_ordenar_es_estable_y_no_pierde_hilos():
    hilos = [{"id": str(i), "urgencia": 2, "dias_hasta": 1} for i in range(5)]
    out = ordenar(hilos, habitos=None)
    assert len(out) == 5
    assert {h["id"] for h in out} == {"0", "1", "2", "3", "4"}
