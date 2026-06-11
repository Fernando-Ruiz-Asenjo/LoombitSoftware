"""Test HONESTO del calculo de IVA.

golden-source: Ley 37/1992 del IVA, art. 90 (tipo general 21 %).
El valor ESPERADO esta calculado A MANO desde la ley, NO copiado de la salida
del codigo:
    - 21 % de 1000 = 210,00  (cuota repercutida)
    - 21 % de  500 = 105,00  (cuota soportada)
    - modelo 303 a ingresar = 210,00 - 105,00 = 105,00

Por eso este test MATA mutantes: si alguien cambia el codigo (un '*' por '/',
un '-' por '+'), el resultado dejara de coincidir con el valor de la ley y el
test se pondra ROJO. Tiene poder real.

Ejecutable como script (exit != 0 si falla) y como test de pytest.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from iva import cuota_iva, iva_a_ingresar  # noqa: E402


def test_cuota_repercutida():
    # 21 % de 1000 segun la ley = 210,00
    assert cuota_iva(1000) == 210.00


def test_cuota_soportada():
    # 21 % de 500 segun la ley = 105,00
    assert cuota_iva(500) == 105.00


def test_modelo_303_a_ingresar():
    # 210,00 - 105,00 = 105,00 a ingresar
    assert iva_a_ingresar(1000, 500) == 105.00


if __name__ == "__main__":
    test_cuota_repercutida()
    test_cuota_soportada()
    test_modelo_303_a_ingresar()
    print("OK honesto")
