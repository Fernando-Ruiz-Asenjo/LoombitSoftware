"""
RADAR ACTIVO · slice 1 (`fabrica/mejora_prompt.py`) — golden de 'propón → mide → dispón'.

El panel multi-persona PROPONE; el CÓDIGO mide y DISPONE. Aquí se fija: una mejora real pasa y deja un
recibo de conducta válido; un candidato que no supera al original se RECHAZA (se conserva el original);
y un "lo mejoré" sin número suficiente (n_casos < suelo) lo tumba el gate del recibo (D-70).
"""

from __future__ import annotations

import pytest

from loombit_operator.conducta import ReciboInvalido, validate_recibo
from loombit_operator.fabrica.mejora_prompt import (
    PERSONAS,
    construir_brief_panel,
    mejorar_prompt,
)


def _evaluador_por_longitud(prompt: str) -> float:
    """Eval-juguete determinista: 'mejor' = más largo. Sirve para fijar la mecánica sin LLM."""
    return float(len(prompt))


def test_mejora_real_pasa_y_deja_recibo_valido():
    res = mejorar_prompt(
        original="Haz una factura.",
        objetivo="Generar una factura correcta para un autónomo español",
        proponer=lambda _brief: "Haz una factura VeriFactu con NIF, base, IVA y total.",
        evaluar=_evaluador_por_longitud,
        n_casos=5,
        eval_nombre="eval-juguete por longitud (golden)",
    )
    assert res.mejoro is True
    assert res.prompt.startswith("Haz una factura VeriFactu")
    assert res.despues_score > res.antes_score
    ok, errores = validate_recibo(res.recibo)
    assert ok, errores


def test_candidato_que_no_supera_se_rechaza_y_conserva_el_original():
    original = "Un prompt original ya bastante largo y bueno."
    res = mejorar_prompt(
        original=original,
        objetivo="No empeorar",
        proponer=lambda _brief: "corto",  # peor según el eval-juguete
        evaluar=_evaluador_por_longitud,
        n_casos=5,
        eval_nombre="eval-juguete por longitud (golden)",
    )
    assert res.mejoro is False
    assert res.prompt == original  # el código dispone: se queda el original
    assert res.recibo is None


def test_n_casos_por_debajo_del_suelo_lo_tumba_el_gate_del_recibo():
    with pytest.raises(ReciboInvalido):
        mejorar_prompt(
            original="corto",
            objetivo="Mejorar",
            proponer=lambda _brief: "una versión claramente más larga y mejor",
            evaluar=_evaluador_por_longitud,
            n_casos=1,  # < N_CASOS_MIN: un eval anecdótico no cuenta
            eval_nombre="eval-juguete por longitud (golden)",
        )


def test_el_brief_del_panel_nombra_las_personas_cerradas():
    brief = construir_brief_panel("X", "objetivo de prueba")
    for persona in PERSONAS:
        assert persona in brief
    assert "objetivo de prueba" in brief
