"""
LD-3 «Loombit Decide» — autonomía GRADUADA y capada (§14B).

Golden: `observa` cuenta pero NO encola; `propone`/`actua_con_gate` encolan (idempotente); el
generador NUNCA actúa solo (`auto_actuado == 0`) ni dispara efectos — solo sube decisiones a la cola.
"""

from __future__ import annotations

from datetime import date, timedelta

from loombit_operator.autonomy import (
    AutonomyLevel,
    generar_decisiones_cobro,
    parse_level,
)
from loombit_operator.cuentas_cobrar import CuentaCobrar
from loombit_operator.decisions import DecisionStore


def _store(tmp_path):
    return DecisionStore(store_path=tmp_path / "decisions.json")


def _vencidas(n=2):
    base = date.today() - timedelta(days=20)
    return [
        CuentaCobrar(cliente=f"Cliente{i}", importe=1000 + i, vencimiento=base.isoformat())
        for i in range(n)
    ]


def test_observa_no_encola(tmp_path):
    s = _store(tmp_path)
    r = generar_decisiones_cobro(s, _vencidas(2), level=AutonomyLevel.OBSERVA)
    assert r["observadas"] == 2
    assert r["encoladas"] == 0
    assert s.cola() == []  # observa: ve el trabajo, no molesta


def test_propone_encola(tmp_path):
    s = _store(tmp_path)
    r = generar_decisiones_cobro(s, _vencidas(2), level=AutonomyLevel.PROPONE)
    assert r["encoladas"] == 2
    assert len(s.cola()) == 2


def test_encolado_idempotente(tmp_path):
    s = _store(tmp_path)
    cuentas = _vencidas(2)
    generar_decisiones_cobro(s, cuentas, level=AutonomyLevel.PROPONE)
    # mismas cuentas → no duplica (idempotente por cuenta_id)
    r2 = generar_decisiones_cobro(s, cuentas, level=AutonomyLevel.PROPONE)
    assert r2["encoladas"] == 0
    assert len(s.cola()) == 2


def test_actua_solo_no_actua_sola(tmp_path):
    """§14B: `actua_solo` NO está construido — encola como `propone`, pero NUNCA auto-actúa."""
    s = _store(tmp_path)
    r = generar_decisiones_cobro(s, _vencidas(1), level=AutonomyLevel.ACTUA_SOLO)
    assert r["auto_actuado"] == 0  # invariante: cero efectos autónomos
    assert r["encoladas"] == 1  # sube la decisión; el humano + el gate siguen mandando


def test_parse_level_tolerante():
    assert parse_level("observa") == AutonomyLevel.OBSERVA
    assert parse_level("desconocido") == AutonomyLevel.PROPONE  # cae al seguro por defecto
    assert parse_level(None) == AutonomyLevel.PROPONE
    assert parse_level(AutonomyLevel.ACTUA_CON_GATE) == AutonomyLevel.ACTUA_CON_GATE


def test_executor_encola_en_background(tmp_path, monkeypatch):
    """El executor de la routine (dispatch real) encola decisiones de cobro. El executor importa los
    stores de sus módulos fuente → se parchean ahí (capturando las clases reales antes)."""
    from datetime import datetime

    import loombit_operator.cuentas_cobrar as cc_mod
    import loombit_operator.decisions as dec_mod
    from loombit_operator.cuentas_cobrar import CuentasCobrarStore
    from loombit_operator.decisions import DecisionStore as RealDecisionStore
    from loombit_operator.routine_executors import (
        decisiones_cobro_executor,
        decisiones_cobro_routine,
    )

    ccpath = tmp_path / "cc.json"
    dpath = tmp_path / "decisions.json"
    CuentasCobrarStore(path=ccpath).add(_vencidas(1)[0])  # siembra con la clase real
    monkeypatch.setattr(cc_mod, "CuentasCobrarStore", lambda: CuentasCobrarStore(path=ccpath))
    monkeypatch.setattr(dec_mod, "DecisionStore", lambda: RealDecisionStore(store_path=dpath))

    out = decisiones_cobro_executor(decisiones_cobro_routine(), datetime(2026, 6, 11, 8, 0))
    assert "Encoladas 1" in out
    assert len(RealDecisionStore(store_path=dpath).cola()) == 1
