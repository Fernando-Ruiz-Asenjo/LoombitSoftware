"""Self-test de los gates de verificacion (que el vigilante no sea hueco).

Corre con pytest (CI) y como script (`python tests/test_loombit_verify.py`).
golden-source: comportamiento esperado definido por el diseno de los gates en
docs/BRUJULA_ALGORITMO.md (spec interna), no por la salida del propio codigo.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from loombit_verify import anti_loop, check_golden_source, check_language, mutation  # noqa: E402


def test_mutation_genera_mutantes():
    src = "def f(a, b):\n    return a + b * 2\n"
    mutants = mutation.generate_mutants(src)
    pares = {(m.original, m.mutated) for m in mutants}
    assert ("+", "-") in pares
    assert ("*", "/") in pares


def test_mutation_ignora_strings():
    # un '+' dentro de un string NO debe generar mutante
    src = 'def f():\n    return "a + b"\n'
    assert mutation.generate_mutants(src) == []


def test_golden_detecta_assert_literal():
    assert check_golden_source.has_golden_assertion("def t():\n    assert x == 210.0\n")
    assert not check_golden_source.has_golden_assertion("def t():\n    assert x is not None\n")


def test_golden_cita_real_vs_mencion():
    # cita real
    assert check_golden_source.cita_fuente("golden-source: Ley 37/1992")
    # mencion en prosa (comilla detras) NO cuenta
    assert not check_golden_source.cita_fuente("no cita 'golden-source:'.")


def test_language_caza_exito_absoluto():
    hits = check_language.scan_text("Esta perfecto, 0 bugs, 5-cero", "x")
    assert len(hits) >= 3
    assert check_language.scan_text("cobertura parcial, faltan casos", "x") == []


def test_anti_loop_halt_sin_progreso(tmp_path=None):
    import tempfile

    ledger = Path(tempfile.mkdtemp()) / "l.json"
    a1, _ = anti_loop.decidir(ledger, "obj", 5.0, "h1")
    a2, _ = anti_loop.decidir(ledger, "obj", 5.0, "h2")
    a3, _ = anti_loop.decidir(ledger, "obj", 5.0, "h3")
    assert a1 == "CONTINUE"
    assert a3 == "HALT"  # 2 intentos sin bajar la metrica -> HALT


def test_anti_loop_halt_repeticion():
    import tempfile

    ledger = Path(tempfile.mkdtemp()) / "l.json"
    anti_loop.decidir(ledger, "obj", 5.0, "mismo")
    accion, _ = anti_loop.decidir(ledger, "obj", 3.0, "mismo")  # mismo enfoque
    assert accion == "HALT"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"OK {fn.__name__}")
    print(f"\n{len(fns)} self-tests verdes")
