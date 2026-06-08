"""
expedientes.py — Skill W Administration Core: motor de Expedientes (CaseFile).

Núcleo **blanco y neutro** (sin vocabulario de dominio: no sabe de "303" ni "IVA"). Es la
base reutilizable de cualquier trámite oficial (fiscal, laboral, mercantil, DGT…).

Solidez:
- **Multi-tenant por aislamiento físico:** una BD SQLite por entidad en
  `runtime/local/entities/<entity_id>/expedientes.db`. Un store solo ve UNA entidad.
- **Trazabilidad inmutable:** los eventos forman una **cadena de hashes** (cada evento
  encadena el hash del anterior); `verify_chain` detecta cualquier manipulación.
- **Documentos con huella:** cada documento adjunto guarda su `sha256`.

Ver `docs/PLATAFORMA_FISCAL_ANALISIS.md` y `docs/ARQUITECTURA_SKILLS.md`.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import AppSettings, get_settings


class ExpedienteNotFoundError(KeyError):
    pass


class ExpedienteStatus(StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    PENDING_APPROVAL = "pending_approval"
    CLOSED = "closed"
    FAILED = "failed"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


@dataclass
class ExpedienteEvent:
    ts: str
    kind: str
    detail: dict[str, Any]
    actor: str  # "loombit" | "human" | "<nombre>"
    prev_hash: str
    hash: str

    @staticmethod
    def compute_hash(prev_hash: str, ts: str, kind: str, detail: dict[str, Any], actor: str) -> str:
        payload = (
            prev_hash + ts + kind + json.dumps(detail, sort_keys=True, ensure_ascii=False) + actor
        )
        return _sha256_text(payload)


@dataclass
class Document:
    kind: str
    path: str
    sha256: str
    meta: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    added_at: str = field(default_factory=_now)


@dataclass
class Expediente:
    entity_id: str
    kind: str  # neutro: "factura_intake", "fiscal_303", ...
    title: str
    status: ExpedienteStatus = ExpedienteStatus.OPEN
    data: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


class ExpedienteStore:
    """Store SQLite de expedientes de UNA entidad (aislamiento físico multi-tenant)."""

    def __init__(
        self,
        entity_id: str,
        base_dir: Path | None = None,
        settings: AppSettings | None = None,
    ) -> None:
        if not entity_id or "/" in entity_id or "\\" in entity_id or entity_id in {".", ".."}:
            raise ValueError(f"entity_id inválido: {entity_id!r}")
        active = settings or get_settings()
        self.entity_id = entity_id
        root = base_dir or active.entities_dir
        self.db_path = Path(root) / entity_id / "expedientes.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── conexión por operación (contextmanager: commit + close; evita locks) ──
    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS expedientes (
                    id TEXT PRIMARY KEY, entity_id TEXT, kind TEXT, title TEXT,
                    status TEXT, data TEXT, created_at TEXT, updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, expediente_id TEXT,
                    ts TEXT, kind TEXT, detail TEXT, actor TEXT, prev_hash TEXT, hash TEXT
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, expediente_id TEXT, kind TEXT, path TEXT,
                    sha256 TEXT, meta TEXT, added_at TEXT
                );
                """)

    # ── expedientes ───────────────────────────────────────────────────────────
    def create(self, kind: str, title: str, data: dict[str, Any] | None = None) -> Expediente:
        exp = Expediente(entity_id=self.entity_id, kind=kind, title=title, data=data or {})
        with self._conn() as c:
            c.execute(
                "INSERT INTO expedientes VALUES (?,?,?,?,?,?,?,?)",
                (
                    exp.id,
                    exp.entity_id,
                    exp.kind,
                    exp.title,
                    exp.status.value,
                    json.dumps(exp.data, ensure_ascii=False),
                    exp.created_at,
                    exp.updated_at,
                ),
            )
        self.add_event(exp.id, "created", {"kind": kind, "title": title}, actor="loombit")
        return exp

    def get(self, expediente_id: str) -> Expediente:
        with self._conn() as c:
            row = c.execute("SELECT * FROM expedientes WHERE id = ?", (expediente_id,)).fetchone()
        if row is None:
            raise ExpedienteNotFoundError(expediente_id)
        return self._row_to_expediente(row)

    def list(
        self, status: ExpedienteStatus | None = None, kind: str | None = None
    ) -> list[Expediente]:
        query = "SELECT * FROM expedientes"
        clauses, params = [], []
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at"
        with self._conn() as c:
            rows = c.execute(query, params).fetchall()
        return [self._row_to_expediente(r) for r in rows]

    def set_status(
        self, expediente_id: str, status: ExpedienteStatus, actor: str = "loombit"
    ) -> Expediente:
        exp = self.get(expediente_id)  # valida existencia
        ts = _now()
        with self._conn() as c:
            c.execute(
                "UPDATE expedientes SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, ts, expediente_id),
            )
        self.add_event(
            expediente_id, "status_changed", {"from": exp.status.value, "to": status.value}, actor
        )
        return self.get(expediente_id)

    def update_data(
        self, expediente_id: str, data: dict[str, Any], actor: str = "loombit"
    ) -> Expediente:
        exp = self.get(expediente_id)
        merged = {**exp.data, **data}
        with self._conn() as c:
            c.execute(
                "UPDATE expedientes SET data = ?, updated_at = ? WHERE id = ?",
                (json.dumps(merged, ensure_ascii=False), _now(), expediente_id),
            )
        self.add_event(expediente_id, "data_updated", {"keys": sorted(data.keys())}, actor)
        return self.get(expediente_id)

    # ── trazabilidad (cadena de hashes, append-only) ──────────────────────────
    def add_event(
        self, expediente_id: str, kind: str, detail: dict[str, Any], actor: str = "loombit"
    ) -> ExpedienteEvent:
        prev = self._last_hash(expediente_id)
        ts = _now()
        h = ExpedienteEvent.compute_hash(prev, ts, kind, detail, actor)
        with self._conn() as c:
            c.execute(
                "INSERT INTO events (expediente_id, ts, kind, detail, actor, prev_hash, hash) "
                "VALUES (?,?,?,?,?,?,?)",
                (expediente_id, ts, kind, json.dumps(detail, ensure_ascii=False), actor, prev, h),
            )
        return ExpedienteEvent(ts=ts, kind=kind, detail=detail, actor=actor, prev_hash=prev, hash=h)

    def events(self, expediente_id: str) -> list[ExpedienteEvent]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM events WHERE expediente_id = ? ORDER BY seq", (expediente_id,)
            ).fetchall()
        return [
            ExpedienteEvent(
                ts=r["ts"],
                kind=r["kind"],
                detail=json.loads(r["detail"]),
                actor=r["actor"],
                prev_hash=r["prev_hash"],
                hash=r["hash"],
            )
            for r in rows
        ]

    def verify_chain(self, expediente_id: str) -> bool:
        """Recalcula la cadena de hashes; False si algo se manipuló."""
        prev = ""
        for ev in self.events(expediente_id):
            if ev.prev_hash != prev:
                return False
            expected = ExpedienteEvent.compute_hash(prev, ev.ts, ev.kind, ev.detail, ev.actor)
            if expected != ev.hash:
                return False
            prev = ev.hash
        return True

    def _last_hash(self, expediente_id: str) -> str:
        with self._conn() as c:
            row = c.execute(
                "SELECT hash FROM events WHERE expediente_id = ? ORDER BY seq DESC LIMIT 1",
                (expediente_id,),
            ).fetchone()
        return row["hash"] if row else ""

    # ── documentos ────────────────────────────────────────────────────────────
    def attach_document(
        self, expediente_id: str, kind: str, path: Path, meta: dict[str, Any] | None = None
    ) -> Document:
        self.get(expediente_id)  # valida
        path = Path(path)
        doc = Document(kind=kind, path=str(path), sha256=_sha256_file(path), meta=meta or {})
        with self._conn() as c:
            c.execute(
                "INSERT INTO documents VALUES (?,?,?,?,?,?,?)",
                (
                    doc.id,
                    expediente_id,
                    doc.kind,
                    doc.path,
                    doc.sha256,
                    json.dumps(doc.meta, ensure_ascii=False),
                    doc.added_at,
                ),
            )
        self.add_event(
            expediente_id, "document_attached", {"kind": kind, "sha256": doc.sha256}, "loombit"
        )
        return doc

    def documents(self, expediente_id: str) -> list[Document]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM documents WHERE expediente_id = ? ORDER BY added_at",
                (expediente_id,),
            ).fetchall()
        return [
            Document(
                id=r["id"],
                kind=r["kind"],
                path=r["path"],
                sha256=r["sha256"],
                meta=json.loads(r["meta"]),
                added_at=r["added_at"],
            )
            for r in rows
        ]

    @staticmethod
    def _row_to_expediente(row: sqlite3.Row) -> Expediente:
        return Expediente(
            id=row["id"],
            entity_id=row["entity_id"],
            kind=row["kind"],
            title=row["title"],
            status=ExpedienteStatus(row["status"]),
            data=json.loads(row["data"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
