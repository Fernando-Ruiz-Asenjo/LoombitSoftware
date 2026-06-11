"""Test TAUTOLOGICO: afirma el valor correcto pero SIN fuente externa.

Este es el golden tautologico que confeso el agente: el esperado (210.0) se
copio de ejecutar el codigo, no se calculo desde la ley. Pasa la mutacion
(porque afirma el literal), asi que la mutacion NO lo caza. Lo caza
check_golden_source.py: tiene aserciones golden (== literal) y NO cita
'golden-source:'. Por eso hacen falta los dos gates.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from iva import cuota_iva  # noqa: E402


def test_cuota():
    # 210.0 copiado de la salida del codigo (no de la ley) -> tautologico
    assert cuota_iva(1000) == 210.0


if __name__ == "__main__":
    test_cuota()
    print("OK tautologico")
