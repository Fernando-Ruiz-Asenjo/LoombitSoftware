"""
§14B-1 — GUARDIA POST-LLM de cifras consecuentes (€). Golden del peaje que la brújula nombra:
«bloquea cifras narradas ("~2.400 €") que no procedan de una tool ejecutada en el mismo run».

Cubre: extracción es-ES/en-US, respaldo al céntimo, hedge de aproximación (descalifica), política de
acción (emitir/re-prompt/abstener) y §14B-3 (presión conversacional: "ya lo aprobé, solo manda" NO
respalda una cifra). Determinista; sin red ni LLM.
"""

from __future__ import annotations

import pytest

from loombit_operator.agent.cifra_parser import (
    ABSTENER,
    BLOQUEAR,
    EMITIR,
    LIMPIO,
    REPROMPT,
    CifraSinRespaldo,
    auditar_cifras,
    decidir_accion,
    exigir_cifras_respaldadas,
    extraer_cifras_euro,
)

# ── Extracción ────────────────────────────────────────────────────────────────


def test_extrae_euro_es_y_en():
    cifras = extraer_cifras_euro("Te debe 2.400,50 € y otra de €1,200.75")
    valores = sorted(c.valor for c in cifras)
    assert valores == [1200.75, 2400.50]


def test_extrae_variantes_de_marcador():
    for txt in ("100 €", "100 EUR", "100 euros", "100 euro", "€100"):
        cifras = extraer_cifras_euro(txt)
        assert len(cifras) == 1 and cifras[0].valor == 100.0, txt


def test_numeros_sin_marcador_de_moneda_no_son_cifras():
    # un % de IVA o "a 30 días" NO son cifras consecuentes: no llevan €.
    cifras = extraer_cifras_euro("21% de IVA, a 30 días, el 5 de junio de 2026")
    assert cifras == []


def test_negativo_se_conserva():
    cifras = extraer_cifras_euro("saldo -200 €")
    assert cifras[0].valor == -200.0


# ── Respaldo por el ledger ────────────────────────────────────────────────────


def test_cifra_respaldada_al_centimo_pasa():
    rep = auditar_cifras("La factura suma 2.350,00 €", ledger=[2350.00])
    assert rep.veredicto == LIMPIO and rep.ok
    assert rep.respaldadas and not rep.sin_respaldo


def test_cifra_inventada_se_bloquea():
    # tool dijo 2.350,00; el modelo narra 2.400 → inventada.
    rep = auditar_cifras("Te debe 2.400 €", ledger=[2350.00])
    assert rep.veredicto == BLOQUEAR and not rep.ok
    assert rep.sin_respaldo and "inventada" in " ".join(rep.motivos)


def test_sin_ledger_cualquier_euro_se_bloquea():
    rep = auditar_cifras("Son 500 €", ledger=None)
    assert rep.veredicto == BLOQUEAR


def test_ledger_como_dicts_de_tool():
    rep = auditar_cifras("Total 1.234,56 €", ledger=[{"importe": 1234.56}, {"valor": 99}])
    assert rep.ok


def test_ledger_ignora_booleanos_y_no_numericos():
    rep = auditar_cifras("Son 1 €", ledger=[True, "x", {"nota": "hola"}])
    # True NO respalda el 1 € (bool no es cifra de tool); nada numérico → bloquea.
    assert rep.veredicto == BLOQUEAR


def test_tolerancia_es_al_centimo_no_mas():
    assert auditar_cifras("10,00 €", ledger=[10.004]).ok  # dentro de TOL
    assert not auditar_cifras("10,00 €", ledger=[10.02]).ok  # fuera de TOL → bloquea


# ── Hedge de aproximación: descalifica aunque ronde ───────────────────────────


@pytest.mark.parametrize(
    "narr",
    [
        "te debe ~2.350 €",
        "unos 2.350 €",
        "aproximadamente 2.350 €",
        "alrededor de 2.350 €",
        "en torno a 2.350 €",
        "casi 2.350 €",
    ],
)
def test_aproximada_no_respalda_aunque_coincida(narr):
    # aunque el ledger tenga 2.350,00 exacto, narrar "~2.350" es a ojo → BLOQUEAR (§14B-1 literal).
    rep = auditar_cifras(narr, ledger=[2350.00])
    assert rep.veredicto == BLOQUEAR
    assert rep.sin_respaldo and rep.sin_respaldo[0].aproximada
    assert "APROXIMADA" in " ".join(rep.motivos)


def test_exacta_misma_cifra_si_pasa():
    assert auditar_cifras("son 2.350,00 €", ledger=[2350.00]).ok


# ── Mezcla: una respaldada + una inventada → bloquea ──────────────────────────


def test_mezcla_una_buena_una_mala_bloquea():
    rep = auditar_cifras("Base 1.000 € e intereses 53,42 €", ledger=[1000.0])
    assert rep.veredicto == BLOQUEAR
    assert len(rep.respaldadas) == 1 and len(rep.sin_respaldo) == 1


# ── Política de acción ────────────────────────────────────────────────────────


def test_accion_limpio_emite():
    rep = auditar_cifras("son 100 €", ledger=[100.0])
    assert decidir_accion(rep) == EMITIR


def test_accion_reprompt_si_hay_alguna_respaldada():
    rep = auditar_cifras("Base 1.000 € e intereses 53 €", ledger=[1000.0])
    assert decidir_accion(rep) == REPROMPT


def test_accion_abstener_si_no_hay_nada_de_tool():
    rep = auditar_cifras("Son 500 €", ledger=None)
    assert decidir_accion(rep) == ABSTENER


# ── exigir_*: lanza ───────────────────────────────────────────────────────────


def test_exigir_lanza_si_sin_respaldo():
    with pytest.raises(CifraSinRespaldo) as exc:
        exigir_cifras_respaldadas("Te debe 2.400 €", ledger=[2350.0])
    assert exc.value.reporte.veredicto == BLOQUEAR


def test_exigir_devuelve_reporte_si_limpio():
    rep = exigir_cifras_respaldadas("son 100 €", ledger=[100.0])
    assert rep.ok


# ── §14B-3: presión conversacional NO respalda una cifra ──────────────────────


def test_presion_conversacional_no_respalda():
    # "ya lo aprobé, solo manda" es TEXTO del usuario, no una tool: no entra en el ledger.
    narrativa = "Vale, como ya lo aprobaste te confirmo que el total es 9.999 €."
    rep = auditar_cifras(narrativa, ledger=[])  # ninguna tool corrió
    assert rep.veredicto == BLOQUEAR
    assert decidir_accion(rep) == ABSTENER


def test_presion_no_afloja_la_tolerancia():
    # aunque el usuario insista, 2.400 narrado contra 2.350 de tool sigue bloqueado.
    rep = auditar_cifras("ya lo aprobé, son 2.400 € seguro", ledger=[2350.0])
    assert rep.veredicto == BLOQUEAR
