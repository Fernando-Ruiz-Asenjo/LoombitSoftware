"""
Tests del motor de cobros (Ley 3/2004), alineados con los supuestos del banco:
S-01 (no reclamar si está cobrada), S-02 (interés no inventado, judicial→humano+MASC),
S-03 (cobro parcial → reclamar solo el saldo).
"""

from loombit_operator.cobros import (
    LATE_FEE_FIXED_EUR,
    days_overdue,
    dunning_plan,
    escalation_stage,
    late_interest,
)


def test_days_overdue_accepts_formats():
    assert days_overdue("2026-05-01", "2026-06-07") == 37
    assert days_overdue("01/05/2026", "07/06/2026") == 37
    assert days_overdue("2026-06-10", "2026-06-07") == -3


def test_escalation_stages():
    assert escalation_stage(-5) == "por_vencer"
    assert escalation_stage(0) == "vence_hoy"
    assert escalation_stage(5) == "recordatorio_amistoso"
    assert escalation_stage(15) == "recordatorio_firme"
    assert escalation_stage(40) == "reclamacion_formal"
    assert escalation_stage(70) == "via_judicial"


def test_late_interest_not_invented_without_rate():
    r = late_interest(1000.0, 30, annual_rate_pct=None)
    assert r["amount"] is None
    assert r["rate_required"] is True


def test_late_interest_with_rate():
    r = late_interest(1000.0, 365, annual_rate_pct=10.0)
    assert r["amount"] == 100.0
    assert r["rate_required"] is False


def test_dunning_paid_invoice_not_claimed():  # S-01 trampa
    plan = dunning_plan(total=1250.0, due_date="2026-05-01", today="2026-06-07", paid=1250.0)
    assert plan["action"] == "no_reclamar"
    assert plan["reason"] == "factura_cobrada"


def test_dunning_overdue_claims_with_fee_and_unknown_rate():  # S-02 trampa 1
    plan = dunning_plan(total=1250.0, due_date="2026-05-01", today="2026-06-07")
    assert plan["action"] == "reclamar"
    assert plan["outstanding"] == 1250.0
    assert plan["fixed_compensation_eur"] == LATE_FEE_FIXED_EUR
    assert plan["interest"]["rate_required"] is True  # no se inventa el tipo


def test_dunning_partial_payment_claims_only_balance():  # S-03 trampa
    plan = dunning_plan(
        total=1000.0, due_date="2026-05-01", today="2026-05-31", paid=400.0, annual_rate_pct=10.0
    )
    assert plan["partial_payment"] is True
    assert plan["outstanding"] == 600.0
    # el interés se calcula sobre el saldo, no sobre el total
    assert plan["interest"]["amount"] < 100.0


def test_dunning_judicial_escalates_to_human_with_masc():  # S-02 trampa 2
    plan = dunning_plan(total=5000.0, due_date="2026-01-01", today="2026-06-07")
    assert plan["stage"] == "via_judicial"
    assert plan["escalate_to_human"] is True
    assert plan["requires_masc"] is True


def test_dunning_not_due_yet_waits():
    plan = dunning_plan(total=500.0, due_date="2026-12-01", today="2026-06-07")
    assert plan["action"] == "esperar"
    assert plan["stage"] == "por_vencer"
