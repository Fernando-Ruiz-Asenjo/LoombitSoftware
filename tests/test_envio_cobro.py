"""
Envío real del recordatorio de cobro — golden de la PROMESA firmada (`envio-cobro`), con GATE DE EFECTO.

Un test por criterio: sin aprobación NO sale nada, destinatario seguro, cifras por código (un € sin
respaldo se bloquea), recibo auditable, y no envía sola. Determinista; el envío se inyecta o va a outbox.
"""

from __future__ import annotations

import pytest

from loombit_operator.cuentas_cobrar import CuentaCobrar
from loombit_operator.decisions_cobros import decision_de_cuenta
from loombit_operator.skill_d_fiscal.envio_cobro import (
    EnvioBloqueado,
    cuerpo_recordatorio,
    enviar_recordatorio,
)

HOY = "2026-07-01"


def _decision():
    c = CuentaCobrar(cliente="Cliente Uno SL", importe=1210.0, vencimiento="2026-06-09")
    d = decision_de_cuenta(c, HOY)
    assert d is not None  # vencida → hay decisión
    return d


# ── Criterio 1: sin aprobación, NO sale nada (el sagrado) ─────────────────────


def test_sin_aprobacion_no_envia(tmp_path):
    with pytest.raises(EnvioBloqueado) as exc:
        enviar_recordatorio(_decision(), aprobada=False, outbox_dir=tmp_path)
    assert "aprobaci" in str(exc.value).lower()


# ── Criterio 5: no envía sola → el outbox queda vacío ─────────────────────────


def test_no_envia_sola_outbox_vacio(tmp_path):
    with pytest.raises(EnvioBloqueado):
        enviar_recordatorio(_decision(), aprobada=False, outbox_dir=tmp_path)
    assert list(tmp_path.glob("*.eml")) == []  # NADA escrito


# ── Criterio 2: destinatario seguro + Criterio 4: recibo auditable ────────────


def test_destinatario_seguro_y_recibo(tmp_path):
    r = enviar_recordatorio(_decision(), aprobada=True, outbox_dir=tmp_path)
    assert r["enviado"] is True and r["via"] == "outbox"
    assert r["destino"] == "outbox-local"  # seguro por defecto, no arbitrario
    eml = list(tmp_path.glob("*.eml"))
    assert len(eml) == 1  # recibo auditable
    assert "reclamable" in eml[0].read_text(encoding="utf-8").lower()


# ── Criterio 3: cifras por CÓDIGO (un € sin respaldo se bloquea) ──────────────


def test_cifra_sin_respaldo_bloquea(tmp_path):
    with pytest.raises(EnvioBloqueado) as exc:
        enviar_recordatorio(
            _decision(), aprobada=True, cuerpo="Te debe 9999 €", outbox_dir=tmp_path
        )
    assert "sin respaldo" in str(exc.value).lower()
    assert list(tmp_path.glob("*.eml")) == []  # no se mandó nada


def test_cuerpo_lleva_el_importe_por_codigo():
    d = _decision()
    cuerpo = cuerpo_recordatorio(d)
    saldo = d.payload["plan"]["outstanding"]
    assert f"{saldo:.2f} €" in cuerpo  # la cifra es la del plan, exacta


# ── El piloto en vivo (Gmail inyectado) usa el mismo cuerpo seguro ────────────


def test_via_gmail_inyectada():
    enviados = {}

    def fake_send(*, to, subject, body_text):
        enviados.update(to=to, subject=subject, body=body_text)
        return {"message_id": "abc123"}

    r = enviar_recordatorio(_decision(), aprobada=True, enviar_fn=fake_send)
    assert r["via"] == "gmail" and r["recibo"]["message_id"] == "abc123"
    assert "reclamable" in enviados["body"].lower()  # el cuerpo por código


# ── e2e: de la decisión aprobada → recordatorio en el outbox ──────────────────


def test_e2e_decision_a_outbox(tmp_path):
    r = enviar_recordatorio(_decision(), aprobada=True, outbox_dir=tmp_path)
    contenido = (tmp_path / r["ruta"].split("/")[-1]).read_text(encoding="utf-8")
    assert "Cliente Uno SL" in contenido
