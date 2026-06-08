"""
AgentRun — estado persistente de una ejecución del agente.
AgentStore — almacén JSON en runtime/local/agent_runs.json

Un AgentRun pasa por estos estados:
  pending → running → completed
                    → pending_approval  (espera confirmación humana)
                    → failed

El historial de mensajes (messages) es el contexto completo del LLM.
Los pasos (steps) registran qué tools se usaron y qué devolvieron.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..config import AppSettings, get_settings


class AgentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PENDING_APPROVAL = "pending_approval"
    PENDING_QUESTION = "pending_question"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class AgentStep:
    step: int
    tool_name: str
    tool_call_id: str
    arguments: dict[str, Any]
    result: str
    requires_approval: bool
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "arguments": self.arguments,
            "result": self.result,
            "requires_approval": self.requires_approval,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentStep":
        return cls(
            step=int(d["step"]),
            tool_name=str(d["tool_name"]),
            tool_call_id=str(d["tool_call_id"]),
            arguments=dict(d.get("arguments", {})),
            result=str(d.get("result", "")),
            requires_approval=bool(d.get("requires_approval", False)),
            timestamp=str(d.get("timestamp", "")),
        )


@dataclass
class AgentRun:
    task: str
    id: str = field(default_factory=lambda: str(uuid4()))
    status: AgentStatus = AgentStatus.PENDING
    messages: list[dict] = field(default_factory=list)
    steps: list[AgentStep] = field(default_factory=list)
    result: str = ""
    error: str = ""
    pending_approval: dict = field(default_factory=dict)  # qué acción espera aprobación
    pending_question: dict = field(default_factory=dict)  # pregunta pendiente al usuario
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str = ""
    max_steps: int = 20

    # ── Transiciones de estado ────────────────────────────────────────────────

    def mark_running(self) -> None:
        self.status = AgentStatus.RUNNING
        self._touch()

    def mark_completed(self, result: str) -> None:
        self.status = AgentStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now(UTC).isoformat()
        self._touch()

    def mark_failed(self, error: str) -> None:
        self.status = AgentStatus.FAILED
        self.error = error
        self._touch()

    def mark_pending_approval(self, reason: str, proposed_action: str, tool_call_id: str) -> None:
        self.status = AgentStatus.PENDING_APPROVAL
        self.pending_approval = {
            "reason": reason,
            "proposed_action": proposed_action,
            "tool_call_id": tool_call_id,
            "requested_at": datetime.now(UTC).isoformat(),
        }
        self._touch()

    def approve(self) -> None:
        """Retoma la ejecución tras aprobación humana."""
        if self.status != AgentStatus.PENDING_APPROVAL:
            raise ValueError(f"AgentRun no está en pending_approval: {self.status}")
        self.status = AgentStatus.RUNNING
        self.pending_approval = {}
        self._touch()

    def mark_pending_question(self, question: str, tool_call_id: str) -> None:
        self.status = AgentStatus.PENDING_QUESTION
        self.pending_question = {
            "question": question,
            "tool_call_id": tool_call_id,
            "asked_at": datetime.now(UTC).isoformat(),
        }
        self._touch()

    def answer(self) -> None:
        """Retoma la ejecución tras responder a una pregunta del agente."""
        if self.status != AgentStatus.PENDING_QUESTION:
            raise ValueError(f"AgentRun no está en pending_question: {self.status}")
        self.status = AgentStatus.RUNNING
        self.pending_question = {}
        self._touch()

    def cancel(self) -> None:
        """Cancela el run (el usuario pulsó Detener)."""
        self.status = AgentStatus.CANCELLED
        self._touch()

    def add_step(self, step: AgentStep) -> None:
        self.steps.append(step)
        self._touch()

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def exceeded_max_steps(self) -> bool:
        return self.step_count >= self.max_steps

    # ── Serialización ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task": self.task,
            "status": self.status.value,
            "messages": self.messages,
            "steps": [s.to_dict() for s in self.steps],
            "result": self.result,
            "error": self.error,
            "pending_approval": self.pending_approval,
            "pending_question": self.pending_question,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "max_steps": self.max_steps,
        }

    def snapshot(self) -> dict[str, Any]:
        """Vista resumida sin el historial completo de mensajes."""
        return {
            "id": self.id,
            "task": self.task[:120],
            "status": self.status.value,
            "step_count": self.step_count,
            "result": self.result[:300] if self.result else "",
            "error": self.error[:200] if self.error else "",
            "pending_approval": self.pending_approval,
            "pending_question": self.pending_question,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentRun":
        run = cls(
            task=str(d["task"]),
            id=str(d["id"]),
            status=AgentStatus(d.get("status", AgentStatus.PENDING)),
            messages=list(d.get("messages", [])),
            steps=[AgentStep.from_dict(s) for s in d.get("steps", [])],
            result=str(d.get("result", "")),
            error=str(d.get("error", "")),
            pending_approval=dict(d.get("pending_approval", {})),
            pending_question=dict(d.get("pending_question", {})),
            created_at=str(d.get("created_at", "")),
            updated_at=str(d.get("updated_at", "")),
            completed_at=str(d.get("completed_at", "")),
            max_steps=int(d.get("max_steps", 20)),
        )
        return run

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC).isoformat()


# ── AgentStore ────────────────────────────────────────────────────────────────


class AgentStore:
    def __init__(self, store_path: Path | None = None, settings: AppSettings | None = None) -> None:
        active = settings or get_settings()
        self.store_path = store_path or active.agent_run_store_path
        self._runs: dict[str, AgentRun] = {}
        self.load_error: str | None = None
        self._load()

    def create(self, task: str, max_steps: int = 20) -> AgentRun:
        run = AgentRun(task=task, max_steps=max_steps)
        self._runs[run.id] = run
        self._save()
        return run

    def get(self, run_id: str) -> AgentRun:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise KeyError(f"AgentRun no encontrado: {run_id}") from exc

    def save_run(self, run: AgentRun) -> None:
        self._runs[run.id] = run
        self._save()

    def sweep_orphans(self) -> int:
        """Marca como fallidos los runs que quedaron 'running'/'pending' tras un reinicio: sus
        hilos murieron con el proceso, son huérfanos. Evita la pila que martillea el modelo (F8).
        Se llama UNA vez al arrancar el servidor (no en cada carga, para no pisar runs vivos)."""
        huerfanos = [
            r for r in self._runs.values() if r.status in (AgentStatus.RUNNING, AgentStatus.PENDING)
        ]
        for r in huerfanos:
            r.mark_failed("Interrumpido por reinicio del servidor (run huérfano).")
        if huerfanos:
            self._save()
        return len(huerfanos)

    def list(self, status: AgentStatus | None = None) -> list[AgentRun]:
        runs = list(self._runs.values())
        if status:
            runs = [r for r in runs if r.status == status]
        return sorted(runs, key=lambda r: r.created_at, reverse=True)

    def snapshot(self) -> dict[str, Any]:
        runs = self.list()
        by_status = {s.value: 0 for s in AgentStatus}
        for r in runs:
            by_status[r.status.value] += 1
        return {
            "store_path": str(self.store_path),
            "load_error": self.load_error,
            "count": len(runs),
            "by_status": by_status,
        }

    # ── Persistencia ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self.store_path.exists():
            self._runs = {}
            return
        text = self.store_path.read_text(encoding="utf-8")
        if not text.strip():
            self._runs = {}
            return
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            self._runs = {}
            self.load_error = f"agent_run store JSON inválido: {exc}"
            return
        runs: dict[str, AgentRun] = {}
        errors: list[str] = []
        for i, d in enumerate(raw.get("runs", [])):
            try:
                r = AgentRun.from_dict(d)
                runs[r.id] = r
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"run[{i}]: {exc}")
        self._runs = runs
        self.load_error = "; ".join(errors) if errors else None

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 1, "runs": [r.to_dict() for r in self.list()]}
        tmp = self.store_path.with_suffix(f"{self.store_path.suffix}.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.store_path)
