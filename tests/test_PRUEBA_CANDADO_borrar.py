"""PRUEBA DEL CANDADO (BORRAR) — un test que FALLA a propósito para ver si GitHub bloquea el merge.
Si el check `quality` es OBLIGATORIO en la protección de `main`, este PR NO se podrá fundir.
"""


def test_falla_a_proposito():
    # Esto pone el gate (pytest) en ROJO → el check `quality` en ROJO.
    assert False, "fallo deliberado: ¿bloquea GitHub el merge?"
