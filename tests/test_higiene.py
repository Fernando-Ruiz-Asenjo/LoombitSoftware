"""F6 — higiene del radar (lección OpenClaw): las afirmaciones numéricas/superlativas de los hallazgos
de la RED se marcan 'sin verificar' y bajan de prioridad; lo de DENTRO no se toca. Determinista."""

from __future__ import annotations

from loombit_operator.fabrica.higiene import afirmacion_sin_verificar, higienizar
from loombit_operator.fabrica.modelos import Fuente, Necesidad


def test_detecta_afirmaciones():
    assert afirmacion_sin_verificar("90% menos tokens, 43% mejores resultados")
    assert afirmacion_sin_verificar("3-5x más rápido")
    assert afirmacion_sin_verificar("levanta ronda de $252 millones")
    assert afirmacion_sin_verificar("el mejor agente, supera a todos (SOTA)")
    assert not afirmacion_sin_verificar("Framework de skills para agentes")


def test_higieniza_solo_red_con_cifras():
    red = Necesidad(titulo="Startup X levanta $50 millones", fuente=Fuente.RED, prioridad=3)
    interno = Necesidad(titulo="bug en x.py:5", fuente=Fuente.COGNICION, prioridad=5)
    out = higienizar([red, interno])
    assert out[0].titulo.startswith("⚠️ sin verificar") and out[0].prioridad == 2
    assert "fuente primaria" in out[0].descripcion
    assert out[1].titulo == "bug en x.py:5" and out[1].prioridad == 5


def test_red_sin_cifras_no_se_marca():
    red = Necesidad(titulo="Framework de skills para agentes", fuente=Fuente.RED, prioridad=3)
    out = higienizar([red])
    assert not out[0].titulo.startswith("⚠️") and out[0].prioridad == 3


def test_idempotente():
    red = Necesidad(titulo="X crece 10x este año", fuente=Fuente.RED, prioridad=3)
    una = higienizar([red])
    dos = higienizar(una)
    assert dos[0].titulo.count("sin verificar") == 1 and dos[0].prioridad == 2
