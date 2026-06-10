"""
RC·Cerebro — ALG-1.3/1.4: parsers y validación deterministas. Golden 100% CI.
Las cifras/fechas/IBAN/NIF las saca CÓDIGO, no el LLM → fiables por construcción.
"""

from datetime import date

from loombit_operator.agent.parsers import (
    parsear_fecha,
    parsear_importe,
    parsear_tipo_iva,
    tipo_iva_valido,
    validar_iban,
    validar_nif,
)

_HOY = date(2026, 6, 9)  # martes


def test_parsear_importe_separadores_es_e_en():
    assert parsear_importe("1.500€") == 1500.0
    assert parsear_importe("1.500,75 €") == 1500.75
    assert parsear_importe("1,500.75") == 1500.75
    assert parsear_importe("2000") == 2000.0
    assert parsear_importe("1500,50") == 1500.50
    assert parsear_importe("el total son 1.234,56 euros") == 1234.56
    assert parsear_importe("") is None
    assert parsear_importe("sin números") is None


def test_parsear_tipo_iva_y_validez():
    assert parsear_tipo_iva("21%") == 0.21
    assert parsear_tipo_iva("0,21") == 0.21
    assert parsear_tipo_iva("10") == 0.10
    assert parsear_tipo_iva("40%") == 0.40  # se parsea…
    assert tipo_iva_valido(0.40) is False  # …pero NO es válido
    assert tipo_iva_valido(0.21) is True
    assert tipo_iva_valido(None) is False
    assert parsear_tipo_iva("nada") is None


def test_parsear_fecha_formatos_y_relativas():
    assert parsear_fecha("2026-05-01") == date(2026, 5, 1)
    assert parsear_fecha("01/05/2026") == date(2026, 5, 1)
    assert parsear_fecha("1 de mayo de 2026") == date(2026, 5, 1)
    assert parsear_fecha("mañana", _HOY) == date(2026, 6, 10)
    assert parsear_fecha("pasado mañana", _HOY) == date(2026, 6, 11)
    assert parsear_fecha("el jueves", _HOY) == date(2026, 6, 11)  # martes → jueves de esta semana
    assert parsear_fecha("hoy", _HOY) == _HOY
    assert parsear_fecha("pronto") is None
    assert parsear_fecha("32/13/2026") is None  # fecha imposible → None, no se inventa


def test_validar_iban_checksum():
    assert validar_iban("ES91 2100 0418 4502 0005 1332") is True  # IBAN español válido
    assert validar_iban("ES9121000418450200051332") is True  # sin espacios, mismo
    assert validar_iban("ES9121000418450200051333") is False  # checksum manipulado
    assert validar_iban("hola") is False
    assert validar_iban("") is False


def test_validar_nif_dni():
    assert validar_nif("12345678Z") is True  # letra de control correcta
    assert validar_nif("12345678A") is False  # letra incorrecta
    assert validar_nif("1234") is False  # formato inválido
