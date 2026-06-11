"""
RECIBOS DE CONDUCTA (D-70) — el método que vuelve contabilizable lo "no testeable".

Golden del validador: un recibo cuantificable y por encima del suelo PASA; uno vago, sin números o de
bajo valor se RECHAZA. Y valida que TODOS los recibos commiteados en `docs/RECIBOS_CONDUCTA.jsonl` son
válidos (un recibo de mentira no entra en verde).
"""

from __future__ import annotations

import json
from pathlib import Path

from loombit_operator.conducta import ReciboInvalido, exigir_recibo, validate_recibo

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "docs" / "RECIBOS_CONDUCTA.jsonl"


# ── Lo bueno pasa ─────────────────────────────────────────────────────────────


def test_innovacion_cuantificada_pasa():
    ok, errores = validate_recibo(
        {
            "tipo": "innovacion",
            "que": "Recibos de conducta cuantificables",
            "por_que": "Evita propuestas de bajo valor sin evidencia",
            "fase": "Gobierno META-1",
            "como_se_prueba": "tests/test_conducta.py golden",
            "valor": 4,
        }
    )
    assert ok, errores


def test_mejora_prompt_con_delta_real_pasa():
    ok, errores = validate_recibo(
        {
            "tipo": "mejora_prompt",
            "antes_score": 0.80,
            "despues_score": 0.92,
            "eval": "eval de comportamiento F1-F8 contra el 14B",
            "n_casos": 8,
        }
    )
    assert ok, errores


# ── Lo de bajo valor / sin evidencia se RECHAZA ──────────────────────────────


def test_innovacion_de_bajo_valor_se_rechaza():
    ok, errores = validate_recibo(
        {
            "tipo": "innovacion",
            "que": "un cambio menor cualquiera",
            "por_que": "porque sí, mejora algo",
            "fase": "x",
            "como_se_prueba": "se ve",
            "valor": 1,
        }
    )
    assert not ok
    assert any("BAJO VALOR" in e for e in errores)


def test_innovacion_sin_mecanismo_de_prueba_se_rechaza():
    ok, errores = validate_recibo(
        {
            "tipo": "innovacion",
            "que": "Una idea con texto suficiente para parecer seria",
            "por_que": "Un motivo con longitud suficiente para pasar el mínimo",
            "fase": "Gobierno, una fase con texto",
            "como_se_prueba": "lo iremos viendo con el tiempo, ya se notara",
            "valor": 3,
        }
    )
    assert not ok
    assert any("verificable" in e for e in errores)


def test_mejora_prompt_que_no_mejora_se_rechaza():
    ok, errores = validate_recibo(
        {
            "tipo": "mejora_prompt",
            "antes_score": 0.90,
            "despues_score": 0.88,
            "eval": "eval F1-F8",
            "n_casos": 8,
        }
    )
    assert not ok
    assert any("NO es una mejora" in e for e in errores)


def test_mejora_prompt_anecdotica_se_rechaza():
    ok, _ = validate_recibo(
        {
            "tipo": "mejora_prompt",
            "antes_score": 0.5,
            "despues_score": 0.9,
            "eval": "lo probé a mano",
            "n_casos": 1,  # < N_CASOS_MIN
        }
    )
    assert not ok


def test_veredicto_fuerte_exige_lectura_integra():
    # adopt sin lectura íntegra → rechazado (D-58)
    ok, errores = validate_recibo(
        {
            "tipo": "veredicto",
            "fuente": "alguna/libreria",
            "leido_integro": False,
            "veredicto": "adopt",
        }
    )
    assert not ok and any("D-58" in e for e in errores)
    # con lectura íntegra → pasa
    ok2, _ = validate_recibo(
        {
            "tipo": "veredicto",
            "fuente": "alguna/libreria",
            "leido_integro": True,
            "veredicto": "adopt",
        }
    )
    assert ok2


def test_tipo_desconocido_se_rechaza():
    assert not validate_recibo({"tipo": "lo_que_sea"})[0]
    try:
        exigir_recibo({"tipo": "lo_que_sea"})
        raise AssertionError("debía lanzar ReciboInvalido")
    except ReciboInvalido:
        pass


# ── Los recibos commiteados deben ser TODOS válidos ──────────────────────────


def test_recibos_commiteados_son_validos():
    assert LOG.exists(), "falta docs/RECIBOS_CONDUCTA.jsonl"
    lineas = [ln for ln in LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert lineas, "el log de recibos está vacío (dogfood: registra al menos uno)"
    for i, ln in enumerate(lineas):
        recibo = json.loads(ln)
        ok, errores = validate_recibo(recibo)
        assert ok, f"recibo[{i}] inválido: {errores}"
