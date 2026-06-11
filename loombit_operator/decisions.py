"""
decisions.py — LD-0 de «Loombit Decide»: la `Decision` de primera clase + la COLA.

La dirección (D-57): **el usuario solo DECIDE; Loombit hace el resto.** Lo único que sube al humano
es una decisión bien planteada — su porqué, sus opciones, su reversibilidad y su riesgo — y las
decisiones se **acumulan en una cola**, no en un chat.

Separación de Autoridades (Ley Fundacional): el cerebro/LLM **PROPONE** una decisión; el código la
**encola** y la resuelve; el efecto externo se dispara SOLO por el gate `PENDING_APPROVAL` que ya
existe (lo cablea LD-2). Aquí no hay LLM en el camino de control: este módulo es modelo + store
deterministas. Las cifras del `payload` las pone código de dominio (cobros, fiscal…), nunca el LLM.

Sigue el patrón de `agent/run.py` (JSON atómico tmp+replace, `to_dict`/`from_dict`, resiliente a
filas corruptas: una decisión malformada no tumba la cola entera).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import AppSettings, get_settings


class DecisionKind(StrEnum):
    """De qué trata la decisión (gobierna el icono/encuadre; el vocabulario de UI es aparte)."""

    COBRO = "cobro"
    CORREO = "correo"
    FISCAL = "fiscal"
    AGENDA = "agenda"
    GENERICO = "generico"


class DecisionStatus(StrEnum):
    PENDIENTE = "pendiente"  # en la cola, esperando al humano
    RESUELTA = "resuelta"  # el humano eligió una opción
    DESCARTADA = "descartada"  # retirada sin resolver (caducó / ya no aplica)


class OptionKind(StrEnum):
    """Los verbos de «tú solo decides». El efecto de cada uno lo cablea LD-2 sobre el gate."""

    APROBAR = "aprobar"  # adelante con la acción preparada (pasa por el gate de efecto)
    EDITAR = "editar"  # ajustar antes de aprobar
    POSPONER = "posponer"  # más tarde (vuelve a la cola)
    RECHAZAR = "rechazar"  # no hacerlo


class Risk(StrEnum):
    BAJO = "bajo"
    MEDIO = "medio"
    ALTO = "alto"


_RISK_VALUES = {r.value for r in Risk}
_OPTION_KIND_VALUES = {k.value for k in OptionKind}


@dataclass(frozen=True)
class DecisionOption:
    """Una opción que el humano puede elegir. `id` es estable (lo referencia `resolve`)."""

    id: str
    label: str
    kind: OptionKind = OptionKind.APROBAR

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "kind": self.kind.value}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DecisionOption":
        kind = str(d.get("kind", OptionKind.APROBAR.value))
        return cls(
            id=str(d["id"]),
            label=str(d["label"]),
            kind=OptionKind(kind) if kind in _OPTION_KIND_VALUES else OptionKind.APROBAR,
        )


@dataclass
class Decision:
    """Lo que sube al humano. `payload` lleva los datos de dominio (cifras por código); `source`
    enlaza con el origen (un AgentRun en `PENDING_APPROVAL`, una cuenta a cobrar, etc.)."""

    title: str
    why: str = ""  # el PORQUÉ: una línea causal (por qué te lo subo, ahora)
    detail: str = ""  # contexto adicional (texto, nunca HTML)
    kind: DecisionKind = DecisionKind.GENERICO
    options: list[DecisionOption] = field(default_factory=list)
    risk: Risk = Risk.BAJO
    reversible: bool = True
    status: DecisionStatus = DecisionStatus.PENDIENTE
    chosen_option: str = ""  # id de la opción elegida al resolver
    source: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    resolved_at: str = ""

    def resolve(self, option_id: str) -> None:
        """Marca la decisión como resuelta con la opción elegida. NO dispara el efecto externo
        (eso es del gate, lo cablea LD-2): aquí solo se registra la decisión del humano."""
        if self.status != DecisionStatus.PENDIENTE:
            raise ValueError(f"Decisión no está pendiente: {self.status}")
        if option_id not in {o.id for o in self.options}:
            raise ValueError(f"Opción desconocida: {option_id}")
        self.status = DecisionStatus.RESUELTA
        self.chosen_option = option_id
        self.resolved_at = datetime.now(UTC).isoformat()

    def dismiss(self) -> None:
        """Retira la decisión de la cola sin resolverla (caducó / ya no aplica)."""
        self.status = DecisionStatus.DESCARTADA
        self.resolved_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "why": self.why,
            "detail": self.detail,
            "kind": self.kind.value,
            "options": [o.to_dict() for o in self.options],
            "risk": self.risk.value,
            "reversible": self.reversible,
            "status": self.status.value,
            "chosen_option": self.chosen_option,
            "source": self.source,
            "payload": self.payload,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Decision":
        kind = str(d.get("kind", DecisionKind.GENERICO.value))
        risk = str(d.get("risk", Risk.BAJO.value))
        status = str(d.get("status", DecisionStatus.PENDIENTE.value))
        return cls(
            id=str(d["id"]),
            title=str(d["title"]),
            why=str(d.get("why", "")),
            detail=str(d.get("detail", "")),
            kind=(
                DecisionKind(kind)
                if kind in {k.value for k in DecisionKind}
                else DecisionKind.GENERICO
            ),
            options=[DecisionOption.from_dict(o) for o in d.get("options", [])],
            risk=Risk(risk) if risk in _RISK_VALUES else Risk.BAJO,
            reversible=bool(d.get("reversible", True)),
            status=(
                DecisionStatus(status)
                if status in {s.value for s in DecisionStatus}
                else DecisionStatus.PENDIENTE
            ),
            chosen_option=str(d.get("chosen_option", "")),
            source=dict(d.get("source", {})),
            payload=dict(d.get("payload", {})),
            created_at=str(d.get("created_at", "")),
            resolved_at=str(d.get("resolved_at", "")),
        )


# ── DecisionStore ───────────────────────────────────────────────────────────────


class DecisionStore:
    """La cola persistente. JSON atómico (tmp+replace); una fila corrupta se omite, no tumba la
    cola (la cola es la pantalla de inicio del usuario: nunca puede quedar en blanco por un dato malo).
    """

    def __init__(self, store_path: Path | None = None, settings: AppSettings | None = None) -> None:
        active = settings or get_settings()
        self.store_path = store_path or active.decision_store_path
        self._decisions: dict[str, Decision] = {}
        self.load_error: str | None = None
        self._load()

    def add(self, decision: Decision) -> Decision:
        self._decisions[decision.id] = decision
        self._save()
        return decision

    def get(self, decision_id: str) -> Decision:
        try:
            return self._decisions[decision_id]
        except KeyError as exc:
            raise KeyError(f"Decisión no encontrada: {decision_id}") from exc

    def resolve(self, decision_id: str, option_id: str) -> Decision:
        d = self.get(decision_id)
        d.resolve(option_id)
        self._save()
        return d

    def dismiss(self, decision_id: str) -> Decision:
        d = self.get(decision_id)
        d.dismiss()
        self._save()
        return d

    def list(self, status: DecisionStatus | None = None) -> list[Decision]:
        ds = list(self._decisions.values())
        if status is not None:
            ds = [d for d in ds if d.status == status]
        # Más recientes primero (la cola se lee de arriba abajo).
        return sorted(ds, key=lambda d: d.created_at, reverse=True)

    def cola(self) -> list[Decision]:
        """Las decisiones PENDIENTES — lo que el humano tiene que decidir ahora."""
        return self.list(status=DecisionStatus.PENDIENTE)

    # ── Persistencia ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self.store_path.exists():
            self._decisions = {}
            return
        text = self.store_path.read_text(encoding="utf-8")
        if not text.strip():
            self._decisions = {}
            return
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            self._decisions = {}
            self.load_error = f"decision store JSON inválido: {exc}"
            return
        out: dict[str, Decision] = {}
        errors: list[str] = []
        for i, d in enumerate(raw.get("decisions", [])):
            try:
                dec = Decision.from_dict(d)
                out[dec.id] = dec
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"decision[{i}]: {exc}")
        self._decisions = out
        self.load_error = "; ".join(errors) if errors else None

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 1, "decisions": [d.to_dict() for d in self.list()]}
        tmp = self.store_path.with_suffix(f"{self.store_path.suffix}.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.store_path)
