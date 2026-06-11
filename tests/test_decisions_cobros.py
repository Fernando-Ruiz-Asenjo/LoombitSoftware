"""
LD-2 «Loombit Decide» — el compositor de DECISIONES de cobro (Skill D).

Golden: una cuenta vencida → una decisión con su plan legal (cifras por código, Ley 3/2004), su
acción preparada y opciones aprobar/editar/posponer. Una cuenta NO vencida no genera decisión. La
spec resultante es válida contra el contrato gobernado (LD-1).
"""

from __future__ import annotations

from datetime import date, timedelta

from loombit_operator.cuentas_cobrar import CuentaCobrar
from loombit_operator.decisions import DecisionKind, OptionKind
from loombit_operator.decisions_cobros import decision_de_cuenta, decisiones_de_cobros
from loombit_operator.ui_spec import decision_to_spec, validate_spec


def _vencida(dias: int, importe: float = 1250.0, cliente: str = "Acme") -> CuentaCobrar:
    venc = (date.today() - timedelta(days=dias)).isoformat()
    return CuentaCobrar(cliente=cliente, importe=importe, vencimiento=venc)


def test_cuenta_vencida_genera_decision():
    d = decision_de_cuenta(_vencida(20))
    assert d is not None
    assert d.kind == DecisionKind.COBRO
    assert "Acme" in d.title and "VENCIDA" in d.title
    # cifras por código en el payload (no del LLM)
    assert d.payload["plan"]["action"] == "reclamar"
    assert d.payload["plan"]["fixed_compensation_eur"] == 40.0
    assert "Saldo" in d.detail and "reclamable" in d.detail
    # acción preparada para el gate (no se envía aquí)
    assert "recordatorio" in d.payload["agent_task"].lower()
    assert "no lo envíes" in d.payload["agent_task"].lower()
    # opciones de «tú solo decides»
    assert [o.kind for o in d.options] == [
        OptionKind.APROBAR,
        OptionKind.EDITAR,
        OptionKind.POSPONER,
    ]


def test_cuenta_no_vencida_no_genera_decision():
    futura = CuentaCobrar(
        cliente="Beta", importe=100, vencimiento=(date.today() + timedelta(days=10)).isoformat()
    )
    assert decision_de_cuenta(futura) is None


def test_sin_vencimiento_no_genera_decision():
    assert decision_de_cuenta(CuentaCobrar(cliente="X", importe=10, vencimiento="")) is None


def test_decision_de_cobro_produce_spec_valida():
    d = decision_de_cuenta(_vencida(35))
    spec = decision_to_spec(d)
    ok, errores = validate_spec(spec)
    assert ok, errores  # el detalle legal (€, art. 8, BOE) no dispara el filtro de markup


def test_via_judicial_escala_con_riesgo_alto():
    # muy vencida → etapa judicial → opción de escalar, riesgo alto
    d = decision_de_cuenta(_vencida(400))
    assert d is not None
    assert d.payload["plan"]["stage"] == "via_judicial"
    assert d.options[0].label == "Escalar a un profesional"
    assert d.risk.value == "alto"


def test_lista_omite_las_que_no_proceden():
    cuentas = [_vencida(20), CuentaCobrar(cliente="Z", importe=5, vencimiento="")]
    ds = decisiones_de_cobros(cuentas)
    assert len(ds) == 1
