"""Tests de la cortesía instantánea (fricción cero): el fast-path NO debe interceptar tareas reales.

El riesgo de un fast-path es comerse una tarea de verdad. Aquí se fija: solo cortesías puras y cortas
devuelven respuesta; cualquier intención real (correo, agenda, datos, @, cifras) cae a None → agente.
"""

from __future__ import annotations

import pytest

from loombit_operator.agent.smalltalk import respuesta_social


@pytest.mark.parametrize(
    "msg",
    [
        "hola",
        "Hola",
        "  hola  ",
        "buenas",
        "Buenas!",
        "hey",
        "qué tal",
        "buenos días",
        "gracias",
        "muchas gracias",
        "ok gracias",
        "vale",
        "perfecto",
        "ok",
        "genial",
        "adiós",
        "hasta luego",
        "chao",
        "hola loombit",
        "hola, ¿qué tal?",
        "buenas, ¿qué tal?",
        "muy buenas",
    ],
)
def test_cortesia_pura_responde_al_instante(msg):
    assert respuesta_social(msg) is not None


@pytest.mark.parametrize(
    "msg",
    [
        "hola, envíame el informe a ana@ejemplo.com",
        "envía un correo a Marta",
        "necesito que agendes una reunión mañana a las 10",
        "gracias, ahora paga la factura 2026-0042",
        "resúmeme el día",
        "buenas, ¿puedes buscar el correo de David?",
        "ok, crea el evento del martes",
        "",
        "   ",
        "hola hola hola hola hola hola",  # demasiado largo / repetido
        "perfecto, transfiere 100 euros",
    ],
)
def test_no_intercepta_tareas_reales(msg):
    assert respuesta_social(msg) is None


def test_categorias_dan_respuesta_apropiada():
    assert "operador" in respuesta_social("hola").lower()
    assert (
        "mandar" in respuesta_social("gracias").lower()
        or "más" in respuesta_social("gracias").lower()
    )
    assert (
        "luego" in respuesta_social("adiós").lower()
        or "necesites" in respuesta_social("adiós").lower()
    )
