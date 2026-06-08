"""
docs_intel_vision.py — OCR de facturas ESCANEADAS con el modelo de visión local (Qwen2.5-VL).

`docs_intel.extract_text_from_pdf` marca `needs_ocr=True` cuando un PDF no tiene capa de
texto (escaneado). Aquí está la escalada pendiente: el VL **transcribe literalmente** la
imagen a texto y luego el extractor DETERMINISTA (`extract_invoice_fields`) saca los
importes/IBAN/fechas por regex.

Regla nº1 (D-09/D-14): **el número NUNCA lo decide el LLM**. El VL solo hace de OCR
(imagen → texto), igual que un escáner; las cifras las extrae el regex y se cruzan
(base+IVA=total). Como el OCR puede equivocarse, todo lo leído por visión se marca para
**verificación humana** (la capa de arriba avisa). Si el VL no está cargado o no devuelve
texto legible → error claro y abstención; nunca se inventa nada.

El VL está descargado pero se carga on-demand (ver `docs/MODELOS_LOOMBIT.md`):
    lms load qwen/qwen2.5-vl-7b -c 8192 --gpu max -y
PDFs escaneados requieren `pypdfium2` (import perezoso); las imágenes sueltas no.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any, Callable

import httpx

_DEFAULT_VISION_MODEL = "qwen/qwen2.5-vl-7b"
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

_OCR_PROMPT = (
    "Transcribe LITERALMENTE todo el texto de este documento (es una factura o albarán). "
    "Respeta EXACTAMENTE los números, importes, fechas, IBAN, NIF/CIF y referencias tal y "
    "como aparecen, sin interpretar, resumir ni completar nada. Si algo es ilegible, escribe "
    "[ilegible]. Devuelve solo el texto transcrito, sin comentarios."
)


def _vision_cfg(settings: Any) -> tuple[str, str]:
    """(base_url, model) del modelo de visión. Override opcional por settings; si no, el 14B-VL."""
    base = getattr(settings, "llm_vision_base_url", "") or settings.llm_base_url
    model = getattr(settings, "llm_vision_model_name", "") or _DEFAULT_VISION_MODEL
    return base.rstrip("/"), model


def ocr_image(
    image_bytes: bytes,
    settings: Any,
    mime: str = "image/png",
    http_post: Callable[..., Any] | None = None,
) -> str:
    """Transcribe (OCR literal) una imagen con el VL local. Lanza si el modelo no responde."""
    base, model = _vision_cfg(settings)
    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _OCR_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 1800,
    }
    post = http_post or httpx.post
    resp = post(f"{base}/chat/completions", json=payload, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(
            f"vision_unavailable: {resp.status_code} — ¿está cargado el VL en LM Studio? "
            f"({resp.text[:150]})"
        )
    data = resp.json()
    return str(data["choices"][0]["message"].get("content") or "").strip()


def render_pdf_to_images(path: str | Path, scale: float = 2.0) -> list[bytes]:
    """Renderiza cada página de un PDF a PNG. Requiere `pypdfium2` (import perezoso)."""
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError(
            "pdf_render_unavailable: para PDFs escaneados instala 'pypdfium2'"
        ) from exc

    out: list[bytes] = []
    pdf = pdfium.PdfDocument(str(path))
    try:
        for page in pdf:
            pil = page.render(scale=scale).to_pil()
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            out.append(buf.getvalue())
            page.close()
    finally:
        pdf.close()
    return out


def ocr_document(
    path: str | Path,
    settings: Any,
    http_post: Callable[..., Any] | None = None,
    max_pages: int = 5,
) -> dict[str, Any]:
    """OCR de un documento escaneado (imagen o PDF) → texto, con el VL local.

    Devuelve `{text, pages, source, model}`. Honesto: lanza claro si el VL no está cargado,
    si falta el renderer de PDF o si el formato no se soporta; nunca inventa texto.
    """
    p = Path(path)
    if not p.exists():
        raise RuntimeError(f"no existe: {path}")
    suffix = p.suffix.lower()
    _, model = _vision_cfg(settings)

    if suffix in _IMAGE_EXTS:
        mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
        text = ocr_image(p.read_bytes(), settings, mime=mime, http_post=http_post)
        pages = 1
    elif suffix == ".pdf":
        images = render_pdf_to_images(p)[:max_pages]
        text = "\n\n".join(ocr_image(img, settings, http_post=http_post) for img in images)
        pages = len(images)
    else:
        raise RuntimeError(f"formato no soportado para OCR de visión: {suffix}")

    return {"text": text, "pages": pages, "source": "vision_ocr", "model": model}
