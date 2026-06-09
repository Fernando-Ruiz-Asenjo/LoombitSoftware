"""
Tests del entregable autónomo (Skill W Core): dossier HTML autocontenido + descarga + recibo.

Cubre: contenido fiel, escapado de seguridad (Skill C), autocontención (sin red), sello de
integridad coherente con verify_chain, persistencia con recibo auditable, y el cableado del router.
"""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from loombit_operator.entregable import (
    build_dossier,
    export_dossier,
    listar_exportables,
    render_dossier_html,
)
from loombit_operator.expedientes import ExpedienteStatus, ExpedienteStore
from loombit_operator.main import app
from loombit_operator.routers import entregable as entregable_router


def _store(tmp_path, entity="acme"):
    return ExpedienteStore(entity_id=entity, base_dir=tmp_path)


# ── render / contenido ────────────────────────────────────────────────────────
def test_dossier_incluye_lo_esencial(tmp_path):
    s = _store(tmp_path)
    exp = s.create("fiscal_303", "Modelo 303 — 2T", {"resultado": 1234.5, "periodo": "2T"})
    f = tmp_path / "justificante.pdf"
    f.write_bytes(b"pdf de prueba")
    s.attach_document(exp.id, "justificante", f)

    html = build_dossier(s, exp.id)

    assert html.startswith("<!DOCTYPE html>")
    assert "Modelo 303 — 2T" in html
    assert "fiscal_303" in html  # kind como badge
    assert "1234.5" in html and "2T" in html  # datos
    assert "justificante" in html  # documento
    assert "created" in html  # evento de trazabilidad
    assert "Integridad verificada" in html  # sello OK


def test_es_autocontenido_sin_red(tmp_path):
    """El dossier NO debe referenciar recursos externos: funciona offline (foso local-first)."""
    s = _store(tmp_path)
    exp = s.create("k", "t", {"x": 1})
    html = build_dossier(s, exp.id)
    assert "http://" not in html and "https://" not in html
    assert "<script" not in html.lower()  # nada de JS (ni de red ni de ejecución)
    assert "src=" not in html.lower()


def test_escapa_contenido_peligroso(tmp_path):
    """Skill C: un título/dato con HTML no debe inyectarse crudo (anti-XSS al abrir el fichero)."""
    s = _store(tmp_path)
    exp = s.create("k", "<script>alert(1)</script>", {"nota": "<img src=x onerror=alert(2)>"})
    html = build_dossier(s, exp.id)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    # el <img onerror> queda neutralizado: el tag va escapado, no es un elemento real
    assert "<img" not in html
    assert "&lt;img" in html


def test_sello_refleja_manipulacion(tmp_path):
    s = _store(tmp_path)
    exp = s.create("k", "t")
    s.add_event(exp.id, "note", {"x": 1})
    conn = sqlite3.connect(s.db_path)
    try:
        conn.execute(
            "UPDATE events SET detail = ? WHERE expediente_id = ? AND kind = 'note'",
            ('{"x": 999}', exp.id),
        )
        conn.commit()
    finally:
        conn.close()
    html = build_dossier(s, exp.id)
    assert "Integridad NO verificada" in html
    assert "Integridad verificada" not in html


def test_render_directo_acepta_status(tmp_path):
    s = _store(tmp_path)
    exp = s.create("k", "t")
    s.set_status(exp.id, ExpedienteStatus.CLOSED)
    exp = s.get(exp.id)
    html = render_dossier_html(exp, s.events(exp.id), s.documents(exp.id), chain_ok=True)
    assert "closed" in html


# ── export a disco + recibo ───────────────────────────────────────────────────
def test_export_escribe_html_y_recibo(tmp_path):
    s = _store(tmp_path)
    exp = s.create("k", "t", {"x": 1})
    path = export_dossier(s, exp.id)

    assert path.exists() and path.suffix == ".html"
    recibo_path = path.with_suffix(".recibo.json")
    assert recibo_path.exists()
    recibo = json.loads(recibo_path.read_text(encoding="utf-8"))
    assert recibo["expediente_id"] == exp.id
    assert recibo["entity_id"] == "acme"
    assert recibo["chain_ok"] is True
    assert len(recibo["sha256"]) == 64
    assert recibo["bytes"] > 0
    # el export deja rastro en la trazabilidad del expediente
    assert "entregable_exportado" in [e.kind for e in s.events(exp.id)]


def test_listar_exportables(tmp_path):
    s = _store(tmp_path)
    e1 = s.create("fiscal_303", "Uno")
    e2 = s.create("conciliacion_bancaria", "Dos")
    items = listar_exportables(s)
    ids = {i["id"] for i in items}
    assert {e1.id, e2.id} == ids
    por_id = {i["id"]: i for i in items}
    assert por_id[e1.id]["title"] == "Uno"
    assert por_id[e1.id]["chain_ok"] is True
    assert por_id[e1.id]["dossier_url"] == f"/entregable/acme/{e1.id}"


def test_export_sin_log_no_anade_evento(tmp_path):
    s = _store(tmp_path)
    exp = s.create("k", "t")
    n_antes = len(s.events(exp.id))
    export_dossier(s, exp.id, log_event=False)
    assert len(s.events(exp.id)) == n_antes


# ── router ────────────────────────────────────────────────────────────────────
@pytest.fixture
def store_aislado(tmp_path, monkeypatch):
    """Apunta el router a una entidad en tmp_path para no tocar el runtime real."""
    monkeypatch.setattr(
        entregable_router,
        "ExpedienteStore",
        lambda entity_id: ExpedienteStore(entity_id=entity_id, base_dir=tmp_path),
    )
    return tmp_path


def test_router_descarga_adjunto(store_aislado):
    s = ExpedienteStore(entity_id="acme", base_dir=store_aislado)
    exp = s.create("k", "Mi expediente", {"x": 1})
    client = TestClient(app)

    r = client.get(f"/entregable/acme/{exp.id}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "attachment" in r.headers.get("content-disposition", "")
    assert "Mi expediente" in r.text

    # inline (sin forzar descarga)
    r2 = client.get(f"/entregable/acme/{exp.id}", params={"descargar": "false"})
    assert r2.status_code == 200
    assert "content-disposition" not in {k.lower() for k in r2.headers}


def test_router_export_persiste(store_aislado):
    s = ExpedienteStore(entity_id="acme", base_dir=store_aislado)
    exp = s.create("k", "t", {"x": 1})
    client = TestClient(app)
    r = client.post(f"/entregable/acme/{exp.id}/export")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["path"].endswith(".html")


def test_router_lista_expedientes(store_aislado):
    s = ExpedienteStore(entity_id="acme", base_dir=store_aislado)
    e1 = s.create("k", "Uno", {"x": 1})
    client = TestClient(app)
    r = client.get("/entregable/acme")
    assert r.status_code == 200
    body = r.json()
    assert body["entity_id"] == "acme"
    assert body["count"] == 1
    item = body["expedientes"][0]
    assert item["id"] == e1.id
    assert item["dossier_url"] == f"/entregable/acme/{e1.id}"


def test_router_404_si_no_existe(store_aislado):
    client = TestClient(app)
    assert client.get("/entregable/acme/noexiste").status_code == 404


def test_router_entity_invalida_es_400(store_aislado):
    client = TestClient(app)
    # un entity_id con separador de ruta es rechazado por el store (anti path-traversal)
    assert client.get("/entregable/..%2Fescape/x").status_code in (400, 404)
