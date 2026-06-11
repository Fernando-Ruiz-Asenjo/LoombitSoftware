"""
Lector de adjuntos PDF de Gmail (intake real, Fase 3): núcleo de parseo DETERMINISTA y testeable.
Detecta las partes PDF de un mensaje (incl. multipart anidado) y decodifica el base64url de Gmail.
La descarga en vivo necesita token real (tu máquina); aquí se cierra la lógica de parseo.
"""

import base64

from loombit_operator.gmail_adjuntos import decodificar_adjunto, partes_pdf


def test_detecta_partes_pdf_en_multipart_anidado():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": "aG9sYQ"}},
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    {
                        "mimeType": "application/pdf",
                        "filename": "factura.pdf",
                        "body": {"attachmentId": "ATT-1"},
                    }
                ],
            },
            {
                "mimeType": "application/octet-stream",
                "filename": "otra-FACTURA.PDF",  # por extensión, aunque el mime no sea pdf
                "body": {"attachmentId": "ATT-2"},
            },
        ],
    }
    partes = partes_pdf(payload)
    assert [(p["filename"], p["attachment_id"]) for p in partes] == [
        ("factura.pdf", "ATT-1"),
        ("otra-FACTURA.PDF", "ATT-2"),
    ]


def test_sin_pdf_lista_vacia():
    payload = {"mimeType": "text/plain", "body": {"data": "aG9sYQ"}}
    assert partes_pdf(payload) == []


def test_decodifica_base64url_de_gmail():
    original = b"%PDF-1.4 contenido binario \xff\xfe con + y /"
    data = base64.urlsafe_b64encode(original).decode()  # Gmail usa base64 URL-safe
    assert decodificar_adjunto(data) == original
