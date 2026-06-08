"""Tests del motor de Expedientes (Skill W Core): multi-tenant + trazabilidad inmutable."""

import hashlib
import sqlite3

import pytest

from loombit_operator.expedientes import (
    ExpedienteNotFoundError,
    ExpedienteStatus,
    ExpedienteStore,
)


def _store(tmp_path, entity="acme"):
    return ExpedienteStore(entity_id=entity, base_dir=tmp_path)


def test_create_and_get(tmp_path):
    s = _store(tmp_path)
    exp = s.create("factura_intake", "Factura proveedor X", {"total": 121.0})
    got = s.get(exp.id)
    assert got.title == "Factura proveedor X"
    assert got.entity_id == "acme"
    assert got.data["total"] == 121.0
    assert got.status == ExpedienteStatus.OPEN


def test_multitenant_isolation(tmp_path):
    a = _store(tmp_path, "acme")
    b = _store(tmp_path, "globex")
    ea = a.create("k", "A")
    b.create("k", "B")
    assert [e.title for e in a.list()] == ["A"]
    assert [e.title for e in b.list()] == ["B"]
    with pytest.raises(ExpedienteNotFoundError):
        b.get(ea.id)  # no se ve el expediente de otra entidad
    assert (tmp_path / "acme" / "expedientes.db").exists()
    assert (tmp_path / "globex" / "expedientes.db").exists()


def test_event_chain_verifies(tmp_path):
    s = _store(tmp_path)
    exp = s.create("k", "t")  # ya registra 'created'
    s.add_event(exp.id, "note", {"x": 1}, actor="human")
    s.add_event(exp.id, "note", {"x": 2}, actor="loombit")
    assert len(s.events(exp.id)) >= 3
    assert s.verify_chain(exp.id) is True


def test_tamper_is_detected(tmp_path):
    s = _store(tmp_path)
    exp = s.create("k", "t")
    s.add_event(exp.id, "note", {"x": 1})
    assert s.verify_chain(exp.id) is True
    # manipular un evento directamente en la BD rompe la cadena
    conn = sqlite3.connect(s.db_path)
    try:
        conn.execute(
            "UPDATE events SET detail = ? WHERE expediente_id = ? AND kind = 'note'",
            ('{"x": 999}', exp.id),
        )
        conn.commit()
    finally:
        conn.close()
    assert s.verify_chain(exp.id) is False


def test_attach_document_hashes(tmp_path):
    s = _store(tmp_path)
    exp = s.create("k", "t")
    f = tmp_path / "factura.pdf"
    f.write_bytes(b"contenido de prueba")
    doc = s.attach_document(exp.id, "factura", f)
    assert doc.sha256 == hashlib.sha256(b"contenido de prueba").hexdigest()
    assert [d.kind for d in s.documents(exp.id)] == ["factura"]


def test_set_status_logs_event(tmp_path):
    s = _store(tmp_path)
    exp = s.create("k", "t")
    s.set_status(exp.id, ExpedienteStatus.PENDING_APPROVAL, actor="human")
    assert s.get(exp.id).status == ExpedienteStatus.PENDING_APPROVAL
    assert "status_changed" in [e.kind for e in s.events(exp.id)]
    assert s.verify_chain(exp.id) is True


def test_list_filters(tmp_path):
    s = _store(tmp_path)
    s.create("fiscal_303", "A")
    e2 = s.create("factura_intake", "B")
    s.set_status(e2.id, ExpedienteStatus.CLOSED)
    assert [e.title for e in s.list(kind="fiscal_303")] == ["A"]
    assert [e.title for e in s.list(status=ExpedienteStatus.CLOSED)] == ["B"]


def test_invalid_entity_id_rejected(tmp_path):
    with pytest.raises(ValueError):
        ExpedienteStore(entity_id="../escape", base_dir=tmp_path)
