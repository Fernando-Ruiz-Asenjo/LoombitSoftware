"""
OCR de facturas escaneadas con el VL local. Clave: el VL solo TRANSCRIBE; el número lo
saca el extractor determinista (regla nº1). Honesto: si el VL no está, error claro.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from loombit_operator import docs_intel_vision as viz

_SETTINGS = SimpleNamespace(llm_base_url="http://localhost:1234/v1")


class _Resp:
    def __init__(self, content="", status=200):
        self.status_code = status
        self.text = ""
        self._content = content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def test_ocr_image_construye_payload_de_vision_y_transcribe() -> None:
    capt = {}

    def fake_post(url, json=None, timeout=None):
        capt["url"] = url
        capt["json"] = json
        return _Resp("Factura 42\nTotal: 121,00 €")

    out = viz.ocr_image(b"\x89PNG...", _SETTINGS, http_post=fake_post)
    assert out.startswith("Factura 42")
    # Es una llamada de visión: imagen como data URI + temperatura 0 (determinista).
    content = capt["json"]["messages"][0]["content"]
    assert any(c.get("type") == "image_url" for c in content)
    assert capt["json"]["temperature"] == 0
    assert capt["json"]["model"] == "qwen/qwen2.5-vl-7b"


def test_ocr_image_sin_modelo_lanza_claro() -> None:
    with pytest.raises(RuntimeError, match="vision_unavailable"):
        viz.ocr_image(b"x", _SETTINGS, http_post=lambda *a, **k: _Resp(status=404))


def test_ocr_document_formato_no_soportado(tmp_path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("hola")
    with pytest.raises(RuntimeError, match="no soportado"):
        viz.ocr_document(f, _SETTINGS)


def test_ocr_document_imagen_devuelve_texto_y_procedencia(tmp_path) -> None:
    img = tmp_path / "factura.png"
    img.write_bytes(b"\x89PNG fake")
    out = viz.ocr_document(img, _SETTINGS, http_post=lambda *a, **k: _Resp("Total: 50,00 €"))
    assert out["source"] == "vision_ocr"
    assert out["pages"] == 1
    assert "50,00" in out["text"]


def test_render_pdf_sin_pypdfium2_avisa() -> None:
    # pypdfium2 no está instalado en el entorno → mensaje claro (no crash silencioso).
    import builtins

    real_import = builtins.__import__

    def no_pdfium(name, *a, **k):
        if name == "pypdfium2":
            raise ImportError("no")
        return real_import(name, *a, **k)

    builtins.__import__ = no_pdfium
    try:
        with pytest.raises(RuntimeError, match="pdf_render_unavailable"):
            viz.render_pdf_to_images("x.pdf")
    finally:
        builtins.__import__ = real_import


# ── Router: la escalada a visión + el determinismo del importe ──────────────────


def test_router_imagen_escala_a_vision_y_extrae_importe_por_codigo(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    import loombit_operator.routers.docs as docs_mod

    # El VL "transcribe" un texto; el IMPORTE lo saca el regex determinista, no el LLM.
    monkeypatch.setattr(
        docs_mod,
        "ocr_document",
        lambda path, settings, **k: {
            "text": "FACTURA Nº 7\nProveedor: ACME SL\nTotal: 121,00 EUR",
            "pages": 1,
            "source": "vision_ocr",
            "model": "qwen/qwen2.5-vl-7b",
        },
    )
    from loombit_operator.main import app

    client = TestClient(app)
    r = client.post("/docs-intel/invoice", json={"path": "C:/scan/factura.png", "learn": False})
    assert r.status_code == 200
    body = r.json()
    assert body["via_ocr"] is True
    assert body["fields"]["total"] == 121.0  # del regex sobre el texto OCR
    assert any("OCR" in w for w in body["warnings"])  # avisa de verificar


def test_router_vision_caida_devuelve_error_honesto(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    import loombit_operator.routers.docs as docs_mod

    def _boom(path, settings, **k):
        raise RuntimeError("vision_unavailable: 404")

    monkeypatch.setattr(docs_mod, "ocr_document", _boom)
    from loombit_operator.main import app

    client = TestClient(app)
    r = client.post("/docs-intel/invoice", json={"path": "C:/scan/factura.jpg"})
    body = r.json()
    assert body["needs_ocr"] is True
    assert body["fields"] is None  # abstención honesta, no inventa
