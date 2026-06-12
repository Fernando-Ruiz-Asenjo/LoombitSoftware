"""
Seguimiento de cobros (cuentas vencidas → decisión de cobro) — golden de la PROMESA firmada.

Un test por criterio del contrato (docs/PROMESAS.jsonl · seguimiento-cobros): detecta vencidas, una
decisión por cobro, cifras por código, gate humano (no envía), lazo e2e desde intake, y las no vencidas
no molestan. Determinista; sin red ni LLM (el plan legal lo calcula cobros.py). `today` fijo.
"""

from __future__ import annotations

from loombit_operator.cuentas_cobrar import CuentaCobrar, CuentasCobrarStore
from loombit_operator.decisions import OptionKind
from loombit_operator.expedientes import ExpedienteStore
from loombit_operator.skill_d_fiscal.intake_batch import intake_carpeta
from loombit_operator.skill_d_fiscal.seguimiento_cobros import decisiones_pendientes

HOY = "2026-07-01"  # fijo: posterior a los vencimientos de prueba

FACTURA_VENCIDA = """Cliente Uno SL
NIF: B12345678
Factura nº F-2026-001
Fecha de factura: 2026-05-10
Vencimiento: 2026-06-09
Base imponible: 1.000,00 EUR
IVA: 210,00 EUR
Total a pagar: 1.210,00 EUR"""


def _cc(tmp_path) -> CuentasCobrarStore:
    return CuentasCobrarStore(path=tmp_path / "cc.json")


def _add(cc, cliente, importe, venc):
    cc.add(CuentaCobrar(cliente=cliente, importe=importe, vencimiento=venc))


# ── Criterio 1: detecta vencidas ──────────────────────────────────────────────


def test_detecta_vencidas(tmp_path):
    cc = _cc(tmp_path)
    _add(cc, "A", 1210.0, "2026-06-09")
    assert len(decisiones_pendientes(cc, HOY)) == 1


# ── Criterio 2: una decisión por cobro ────────────────────────────────────────


def test_una_decision_por_cobro(tmp_path):
    cc = _cc(tmp_path)
    _add(cc, "A", 1210.0, "2026-06-09")
    _add(cc, "B", 500.0, "2026-05-01")
    assert len(decisiones_pendientes(cc, HOY)) == 2


# ── Criterio 3: cifras por CÓDIGO ─────────────────────────────────────────────


def test_cifras_por_codigo(tmp_path):
    cc = _cc(tmp_path)
    _add(cc, "A", 1210.0, "2026-06-09")
    plan = decisiones_pendientes(cc, HOY)[0].payload["plan"]
    assert plan["outstanding"] == 1210.0  # el saldo es el exacto, no una estimación
    assert plan["fixed_compensation_eur"] == 40  # 40 € art. 8 Ley 3/2004, por código


# ── Criterio 4: gate humano (no envía) ────────────────────────────────────────


def test_gate_humano_no_envia(tmp_path):
    cc = _cc(tmp_path)
    _add(cc, "A", 1210.0, "2026-06-09")
    d = decisiones_pendientes(cc, HOY)[0]
    task = d.payload["agent_task"].lower()
    assert "no" in task and "aprueb" in task  # "no lo envíes sin que lo apruebe"
    assert any(o.kind == OptionKind.APROBAR for o in d.options)  # hay opción de aprobar


# ── Criterio 5: lazo e2e (intake → cobro) ─────────────────────────────────────


def test_e2e_intake_a_cobro(tmp_path):
    exp = ExpedienteStore("test_segui", base_dir=tmp_path / "ent")
    cc = _cc(tmp_path)
    carpeta = tmp_path / "facturas"
    carpeta.mkdir()
    (carpeta / "f1.txt").write_text(FACTURA_VENCIDA, encoding="utf-8")
    intake_carpeta(carpeta, exp, cc)  # la factura entra como cuenta a cobrar
    ds = decisiones_pendientes(cc, HOY)  # y de ahí sale su decisión de cobro
    assert len(ds) == 1
    assert "Cliente Uno SL" in ds[0].title


# ── Criterio 6: las NO vencidas no generan decisión ───────────────────────────


def test_no_vencidas_no_generan(tmp_path):
    cc = _cc(tmp_path)
    _add(cc, "Futuro", 1000.0, "2026-12-31")  # vence después de HOY
    assert decisiones_pendientes(cc, HOY) == []
