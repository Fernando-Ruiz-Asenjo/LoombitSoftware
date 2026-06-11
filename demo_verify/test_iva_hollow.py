"""Test HUECO: el "teatro de verde" (la mentira plantada a proposito).

NO tiene golden-source. NO comprueba el VALOR contra la ley. Solo verifica
cosas triviales (que devuelve algo, que es un numero, que no peta). Pasa
siempre en verde y PARECE cobertura, pero no prueba nada del comportamiento.

Este es exactamente el patron que confeso el agente: un test que da verde sin
validar la verdad. El gate de mutacion lo destapa: casi ningun mutante muere,
porque romper el calculo no rompe estas aserciones.

(Ademas, check_golden_source.py lo rechazaria por no citar fuente externa.)
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from iva import cuota_iva, iva_a_ingresar  # noqa: E402


def test_devuelve_algo():
    assert cuota_iva(1000) is not None


def test_es_numero():
    assert isinstance(cuota_iva(1000), float)


def test_no_peta():
    iva_a_ingresar(1000, 500)
    assert True


if __name__ == "__main__":
    test_devuelve_algo()
    test_es_numero()
    test_no_peta()
    print("OK hueco")
