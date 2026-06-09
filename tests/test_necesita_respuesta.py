"""Cognición: una confirmación/acuse ya cerrado no pide respuesta (no proponer responderla).

Fernando: «la reunión con David ya está confirmada; deberías destilarlo y no pedir más confirmaciones.»
"""

from __future__ import annotations

from loombit_operator.routine_executors import _necesita_respuesta


def test_aceptacion_de_calendar_no_pide_respuesta() -> None:
    # El caso REAL: el correo de aceptación de la reunión con David.
    assert _necesita_respuesta("Aceptado: Reunión con David Valentin") is False
    assert _necesita_respuesta("Re: Aceptado: Reunión con David Valentin") is False


def test_automaticos_y_acuses_no_piden_respuesta() -> None:
    assert _necesita_respuesta("Respuesta automática: fuera de la oficina") is False
    assert _necesita_respuesta("Estoy de vacaciones", "Respuesta automática") is False
    assert _necesita_respuesta("Boletín semanal", "...darse de baja / unsubscribe") is False
    assert _necesita_respuesta("Confirmación de tu cita") is False


def test_correo_normal_si_pide_respuesta() -> None:
    assert _necesita_respuesta("¿Me pasas la factura de mayo?") is True
    assert _necesita_respuesta("Propuesta de reunión el jueves", "¿te viene bien a las 9?") is True
    # "Reunión" a secas (sin acuse) sigue pudiendo necesitar respuesta.
    assert _necesita_respuesta("Reunión proyecto Generali") is True
