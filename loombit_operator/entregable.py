"""
entregable.py — Skill W Administration Core: el **entregable autónomo**.

Convierte un Expediente (CaseFile neutro) en un **dossier HTML autónomo y offline**: un único
fichero, con CSS embebido, **sin una sola llamada de red ni recurso externo**. El cliente se lo
queda y lo abre para siempre sin Loombit delante.

Patrón destilado de las herramientas IA de proyectodescartes.org (artefacto autocontenido que el
usuario descarga), pero **adaptado al foso de Loombit**: local-first (los datos NO salen de la
máquina), determinista (lo construye CÓDIGO, no el LLM) y con **sello de integridad** — incrusta el
resultado de `verify_chain`, de modo que cualquiera puede comprobar que el dossier no se alteró.

Núcleo **blanco y neutro**: no sabe de "303" ni de "IVA". Renderiza lo que haya en el expediente
(título, estado, datos, documentos, trazabilidad). El dominio vive aguas arriba (skills/routers).

Ver `expedientes.py` (motor CaseFile) y `routers/entregable.py` (descarga + recibo).
"""

from __future__ import annotations

import hashlib
import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .expedientes import Document, Expediente, ExpedienteEvent, ExpedienteStore

_esc = html.escape

# CSS embebido (sin recursos externos: el dossier funciona en cualquier máquina, sin conexión).
_ESTILO = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; line-height: 1.55;
  margin: 0; padding: 2.2rem 1.2rem; color: #1f2430; background: #f4f5f8; }
.dossier { max-width: 880px; margin: 0 auto; background: #fff; border-radius: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,.08), 0 8px 30px rgba(0,0,0,.05); overflow: hidden; }
header { padding: 1.8rem 2rem 1.4rem; border-bottom: 1px solid #eceef2; }
h1 { font-size: 1.5rem; margin: 0 0 .6rem; }
h2 { font-size: 1.05rem; margin: 1.8rem 0 .7rem; color: #3a4153; }
section { padding: 0 2rem; }
section:last-of-type { padding-bottom: 1.6rem; }
.badges { display: flex; flex-wrap: wrap; gap: .4rem; margin: .3rem 0 .2rem; }
.badge { font-size: .75rem; font-weight: 600; padding: .18rem .55rem; border-radius: 999px;
  background: #eef1f6; color: #3a4153; }
.meta { font-size: .82rem; color: #6b7280; margin-top: .5rem; }
table { width: 100%; border-collapse: collapse; font-size: .9rem; }
th, td { text-align: left; padding: .5rem .6rem; border-bottom: 1px solid #f0f1f4;
  vertical-align: top; }
th { width: 32%; color: #6b7280; font-weight: 600; }
.timeline { list-style: none; margin: 0; padding: 0; }
.timeline li { padding: .55rem 0 .55rem 1.1rem; border-left: 2px solid #e3e6ec; position: relative; }
.timeline li::before { content: ""; position: absolute; left: -5px; top: .85rem; width: 8px;
  height: 8px; border-radius: 50%; background: #9aa3b2; }
.ev-head { font-weight: 600; font-size: .9rem; }
.ev-sub { font-size: .78rem; color: #6b7280; }
.ev-detail { font-size: .8rem; color: #4b5263; margin-top: .15rem; }
code, pre, .hash { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
pre.json { background: #f6f7f9; border: 1px solid #eceef2; border-radius: 8px; padding: .6rem .8rem;
  overflow-x: auto; font-size: .8rem; margin: .2rem 0; }
.hash { font-size: .74rem; color: #8a93a3; }
.seal { margin: 1.6rem 2rem 0; padding: 1rem 1.2rem; border-radius: 10px; font-size: .85rem;
  border: 1px solid; }
.seal.ok { background: #ecfdf3; border-color: #abefc6; color: #08743b; }
.seal.bad { background: #fef3f2; border-color: #fecdc9; color: #b42318; }
footer { padding: 1.2rem 2rem 1.8rem; color: #8a93a3; font-size: .78rem; }
.empty { color: #9aa3b2; font-style: italic; font-size: .88rem; }
"""


def _fmt_value(value: Any) -> str:
    """Escala/contenedor: escalares como texto; dict/list como JSON legible. Todo escapado."""
    if isinstance(value, (dict, list)):
        return (
            '<pre class="json">' + _esc(json.dumps(value, ensure_ascii=False, indent=2)) + "</pre>"
        )
    if value is None:
        return '<span class="empty">—</span>'
    return _esc(str(value))


def _resumen_html(data: dict[str, Any]) -> str:
    if not data:
        return '<p class="empty">Sin datos registrados.</p>'
    filas = "".join(
        f"<tr><th>{_esc(str(k))}</th><td>{_fmt_value(v)}</td></tr>" for k, v in data.items()
    )
    return f"<table>{filas}</table>"


def _documentos_html(documents: list[Document]) -> str:
    if not documents:
        return '<p class="empty">Sin documentos adjuntos.</p>'
    filas = []
    for d in documents:
        nombre = _esc(Path(d.path).name)
        sha = _esc(d.sha256)
        filas.append(
            "<tr>"
            f"<th>{_esc(d.kind)}</th>"
            f'<td>{nombre}<br><span class="hash" title="{sha}">sha256: {sha[:16]}…</span>'
            f'<br><span class="ev-sub">{_esc(d.added_at)}</span></td>'
            "</tr>"
        )
    return f"<table>{''.join(filas)}</table>"


def _trazabilidad_html(events: list[ExpedienteEvent]) -> str:
    if not events:
        return '<p class="empty">Sin eventos.</p>'
    items = []
    for ev in events:
        detalle = _esc(json.dumps(ev.detail, ensure_ascii=False)) if ev.detail else ""
        detalle_html = f'<div class="ev-detail">{detalle}</div>' if detalle else ""
        items.append(
            "<li>"
            f'<div class="ev-head">{_esc(ev.kind)}</div>'
            f'<div class="ev-sub">{_esc(ev.ts)} · {_esc(ev.actor)} · '
            f'<span class="hash">{_esc(ev.hash[:12])}…</span></div>'
            f"{detalle_html}"
            "</li>"
        )
    return f'<ul class="timeline">{"".join(items)}</ul>'


def _sello_html(chain_ok: bool, generated_at: str) -> str:
    if chain_ok:
        return (
            '<div class="seal ok"><strong>✔ Integridad verificada.</strong> La cadena de hashes de '
            "este expediente es consistente: el contenido no se ha alterado. "
            f"Copia generada el {_esc(generated_at)}.</div>"
        )
    return (
        '<div class="seal bad"><strong>✗ Integridad NO verificada.</strong> La cadena de hashes no '
        "cuadra: este expediente pudo manipularse. No lo tomes como prueba sin revisar el original. "
        f"Copia generada el {_esc(generated_at)}.</div>"
    )


def render_dossier_html(
    exp: Expediente,
    events: list[ExpedienteEvent],
    documents: list[Document],
    *,
    chain_ok: bool,
    generated_at: str | None = None,
) -> str:
    """Renderiza el dossier como un único HTML autónomo (sin red ni recursos externos)."""
    generated_at = generated_at or datetime.now(UTC).isoformat()
    title = _esc(exp.title)
    badges = (
        f'<span class="badge">{_esc(exp.kind)}</span>'
        f'<span class="badge">{_esc(exp.status.value)}</span>'
        f'<span class="badge">entidad: {_esc(exp.entity_id)}</span>'
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="es"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<meta name="generator" content="Loombit Operator">'
        f"<title>{title}</title>"
        f"<style>{_ESTILO}</style></head><body>"
        '<div class="dossier">'
        f"<header><h1>{title}</h1>"
        f'<div class="badges">{badges}</div>'
        f'<div class="meta">Expediente <code>{_esc(exp.id)}</code><br>'
        f"Creado: {_esc(exp.created_at)} · Actualizado: {_esc(exp.updated_at)}</div></header>"
        f"<section><h2>Resumen</h2>{_resumen_html(exp.data)}</section>"
        f"<section><h2>Documentos</h2>{_documentos_html(documents)}</section>"
        f"<section><h2>Trazabilidad</h2>{_trazabilidad_html(events)}</section>"
        f"{_sello_html(chain_ok, generated_at)}"
        "<footer>Copia autónoma generada por Loombit. Funciona sin conexión y sin que los datos "
        "salgan de tu equipo. La cadena de hashes permite comprobar que no se ha alterado."
        "</footer></div></body></html>"
    )


def build_dossier(
    store: ExpedienteStore, expediente_id: str, *, generated_at: str | None = None
) -> str:
    """Reúne expediente + eventos + documentos + verificación de cadena y devuelve el HTML."""
    exp = store.get(expediente_id)  # lanza ExpedienteNotFoundError si no existe
    events = store.events(expediente_id)
    documents = store.documents(expediente_id)
    chain_ok = store.verify_chain(expediente_id)
    return render_dossier_html(exp, events, documents, chain_ok=chain_ok, generated_at=generated_at)


def export_dossier(store: ExpedienteStore, expediente_id: str, *, log_event: bool = True) -> Path:
    """Escribe el dossier a disco (dentro del aislamiento de la entidad) con su recibo auditable.

    Devuelve la ruta del `.html`. Junto a él deja un `.recibo.json` (sha256, generated_at,
    chain_ok, bytes): rastro de que el entregable se produjo, alineado con la regla de no mentir.
    """
    generated_at = datetime.now(UTC).isoformat()
    html_text = build_dossier(store, expediente_id, generated_at=generated_at)
    sha256 = hashlib.sha256(html_text.encode("utf-8")).hexdigest()

    out_dir = store.db_path.parent / "entregables"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    html_path = out_dir / f"{expediente_id}_{slug}.html"
    html_path.write_text(html_text, encoding="utf-8")

    recibo = {
        "expediente_id": expediente_id,
        "entity_id": store.entity_id,
        "generated_at": generated_at,
        "sha256": sha256,
        "bytes": len(html_text.encode("utf-8")),
        "chain_ok": store.verify_chain(expediente_id),
        "html_path": str(html_path),
    }
    html_path.with_suffix(".recibo.json").write_text(
        json.dumps(recibo, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if log_event:
        store.add_event(
            expediente_id, "entregable_exportado", {"sha256": sha256, "bytes": recibo["bytes"]}
        )
    return html_path
