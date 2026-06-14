"""
Frontera de Pareto para GEPA (D-97) — primitiva PURA y DETERMINISTA, sin LM Studio.

Verifica el principio que diferencia a GEPA del "mejor por media": dos candidatos COMPLEMENTARIOS
(uno gana F2, otro gana F7) sobreviven AMBOS en la frontera; un candidato dominado se descarta; la
elección determinista prefiere al de mayor cobertura. El cableado en `optimizar_prompt` es 🟠 (D-97):
`gepa.py` está en deuda de tamaño y no puede engordar.
"""

from __future__ import annotations

from loombit_operator.fabrica.gepa_pareto import (
    CandidatoPareto,
    agregado,
    domina,
    elegir_de_frontera,
    frontera_pareto,
    instancias_ganadas,
    pesos_de_frontera,
    vector_de,
)


def test_vector_de_desde_detalle():
    det = [{"id": "F2", "ok": True}, {"id": "F7", "ok": False}]
    assert vector_de(det) == {"F2": 1.0, "F7": 0.0}
    assert agregado(vector_de(det)) == 0.5


def test_domina():
    a = {"F2": 1.0, "F7": 1.0}
    b = {"F2": 1.0, "F7": 0.0}
    assert domina(a, b) is True  # ≥ en todas y > en F7
    assert domina(b, a) is False
    assert domina(a, a) is False  # iguales → no domina (no hay > estricto)


def test_frontera_conserva_complementarios():
    # c1 gana F2, c2 gana F7: ninguno domina al otro → AMBOS en la frontera (lo que la media perdería).
    c1 = CandidatoPareto("c1", {"F2": 1.0, "F7": 0.0})
    c2 = CandidatoPareto("c2", {"F2": 0.0, "F7": 1.0})
    dominado = CandidatoPareto("d", {"F2": 0.0, "F7": 0.0})  # peor o igual en todo → fuera
    frontera = frontera_pareto([c1, c2, dominado])
    claves = {c.clave for c in frontera}
    assert claves == {"c1", "c2"}


def test_frontera_excluye_dominado():
    mejor = CandidatoPareto("mejor", {"F2": 1.0, "F7": 1.0})
    peor = CandidatoPareto("peor", {"F2": 1.0, "F7": 0.0})  # dominado por 'mejor'
    frontera = frontera_pareto([mejor, peor])
    assert [c.clave for c in frontera] == ["mejor"]


def test_instancias_ganadas_y_pesos():
    c1 = CandidatoPareto("c1", {"F2": 1.0, "F7": 0.0})
    c2 = CandidatoPareto("c2", {"F2": 0.0, "F7": 1.0})
    cands = [c1, c2]
    assert instancias_ganadas(c1, cands) == {"F2"}
    assert instancias_ganadas(c2, cands) == {"F7"}
    pesos = dict((c.clave, p) for c, p in pesos_de_frontera(cands))
    assert pesos == {"c1": 1, "c2": 1}


def test_elegir_prefiere_mayor_cobertura():
    amplio = CandidatoPareto("amplio", {"F2": 1.0, "F7": 1.0, "PROACT": 0.0})  # gana 2
    estrecho = CandidatoPareto("estrecho", {"F2": 0.0, "F7": 0.0, "PROACT": 1.0})  # gana 1
    elegido = elegir_de_frontera([amplio, estrecho])
    assert elegido is not None and elegido.clave == "amplio"


def test_elegir_vacio_es_none():
    assert elegir_de_frontera([]) is None
