"""
lm_jobs.py — cola local de trabajos de LLM (Skill W, núcleo blanco).

Migrado desde `jetson-ai-operator`. Modela trabajos de LLM (rol instructor/coder),
los persiste en JSON local y los ejecuta contra un `executor` inyectado (el
cliente LLM no se importa aquí, para mantener el módulo desacoplado y testeable).

Estado: 🟡 migrado y unit-tested (store + validación JSON). El cableado a routers
y al cliente LLM real (`llm.py`) queda pendiente.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import AppSettings, get_settings


class LMJobNotFoundError(KeyError):
    pass


class LMJobRole(StrEnum):
    DEFAULT = "default"
    INSTRUCTOR = "instructor"
    CODER = "coder"


class LMJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class LMJobExpectation(StrEnum):
    TEXT = "text"
    JSON = "json"


ChatExecutor = Callable[..., dict[str, Any]]


@dataclass
class LMJob:
    role: LMJobRole
    task_type: str
    messages: list[dict[str, str]]
    expectation: LMJobExpectation = LMJobExpectation.TEXT
    temperature: float | None = None
    max_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    status: LMJobStatus = LMJobStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    result: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def mark_running(self) -> None:
        if self.status not in {LMJobStatus.PENDING, LMJobStatus.FAILED}:
            raise ValueError(f"Cannot run LM job from status '{self.status}'")
        self.status = LMJobStatus.RUNNING
        self.updated_at = datetime.now(UTC)
        self.error = None

    def mark_completed(self, result: dict[str, Any], validation: dict[str, Any]) -> None:
        if self.status != LMJobStatus.RUNNING:
            raise ValueError(f"Cannot complete LM job from status '{self.status}'")
        self.status = LMJobStatus.COMPLETED
        self.updated_at = datetime.now(UTC)
        self.result = result
        self.validation = validation
        self.error = None

    def mark_failed(self, error: str, validation: dict[str, Any] | None = None) -> None:
        if self.status != LMJobStatus.RUNNING:
            raise ValueError(f"Cannot fail LM job from status '{self.status}'")
        self.status = LMJobStatus.FAILED
        self.updated_at = datetime.now(UTC)
        self.error = error
        self.validation = validation or {
            "expected": self.expectation.value,
            "valid": False,
            "errors": [error],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role.value,
            "task_type": self.task_type,
            "messages": self.messages,
            "expectation": self.expectation.value,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "metadata": self.metadata,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "result": self.result,
            "validation": self.validation,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LMJob":
        return cls(
            id=str(data["id"]),
            role=LMJobRole(data.get("role", LMJobRole.DEFAULT)),
            task_type=str(data["task_type"]),
            messages=[
                {"role": str(message["role"]), "content": str(message["content"])}
                for message in data.get("messages", [])
            ],
            expectation=LMJobExpectation(data.get("expectation", LMJobExpectation.TEXT)),
            temperature=data.get("temperature"),
            max_tokens=data.get("max_tokens"),
            metadata=dict(data.get("metadata", {})),
            status=LMJobStatus(data.get("status", LMJobStatus.PENDING)),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            result=dict(data.get("result", {})),
            validation=dict(data.get("validation", {})),
            error=data.get("error"),
        )


class LMJobStore:
    def __init__(self, store_path: Path | None = None, settings: AppSettings | None = None) -> None:
        active_settings = settings or get_settings()
        self.store_path = store_path or active_settings.lm_job_store_path
        self._jobs: dict[str, LMJob] = {}
        self.load_error: str | None = None
        self._load()

    def submit(
        self,
        *,
        role: str,
        task_type: str,
        messages: list[dict[str, str]],
        expectation: str = LMJobExpectation.TEXT,
        temperature: float | None = None,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LMJob:
        if not task_type.strip():
            raise ValueError("task_type is required")
        if not messages:
            raise ValueError("messages are required")

        job = LMJob(
            role=LMJobRole(role),
            task_type=task_type,
            messages=[_normalise_message(message) for message in messages],
            expectation=LMJobExpectation(expectation),
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata or {},
        )
        self._jobs[job.id] = job
        self._save()
        return job

    def get(self, job_id: str) -> LMJob:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise LMJobNotFoundError(job_id) from exc

    def delete(self, job_id: str) -> dict[str, Any]:
        job = self.get(job_id)
        del self._jobs[job_id]
        self._save()
        return {
            "deleted": True,
            "job_id": job.id,
            "task_type": job.task_type,
            "status": job.status.value,
        }

    def list(self, status: str | LMJobStatus | None = None) -> list[LMJob]:
        jobs = list(self._jobs.values())
        if status is not None:
            active_status = LMJobStatus(status)
            jobs = [job for job in jobs if job.status == active_status]
        return sorted(jobs, key=lambda job: job.created_at)

    def snapshot(self) -> dict[str, Any]:
        jobs = self.list()
        by_status = {status.value: 0 for status in LMJobStatus}
        for job in jobs:
            by_status[job.status.value] += 1
        return {
            "store_path": str(self.store_path),
            "load_error": self.load_error,
            "count": len(jobs),
            "by_status": by_status,
            "roles": [role.value for role in LMJobRole],
            "safety_contract": {
                "local_only": True,
                "models_cannot_execute_shell": True,
                "models_cannot_modify_files_directly": True,
                "human_or_runtime_validation_required": True,
            },
        }

    def to_dict(self, status: str | LMJobStatus | None = None) -> dict[str, Any]:
        jobs = self.list(status=status)
        return {
            "count": len(jobs),
            "jobs": [job.to_dict() for job in jobs],
            "safety_contract": self.snapshot()["safety_contract"],
        }

    def run(self, job_id: str, executor: ChatExecutor) -> LMJob:
        job = self.get(job_id)
        job.mark_running()
        self._save()

        try:
            response = executor(
                role=job.role.value,
                messages=job.messages,
                temperature=job.temperature,
                max_tokens=job.max_tokens,
            )
            result, validation = _build_result(response, job.expectation)
            if not validation["valid"]:
                raise ValueError("; ".join(validation["errors"]))
            job.mark_completed(result=result, validation=validation)
        except Exception as exc:
            job.mark_failed(str(exc))
        self._save()
        return job

    def _load(self) -> None:
        if not self.store_path.exists():
            self._jobs = {}
            return

        text = self.store_path.read_text(encoding="utf-8")
        if not text.strip():
            self._jobs = {}
            self.load_error = "LM job store file is empty"
            return

        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            self._jobs = {}
            self.load_error = f"LM job store JSON is invalid: {exc}"
            return

        jobs: dict[str, LMJob] = {}
        errors: list[str] = []
        for index, job_data in enumerate(raw.get("jobs", [])):
            try:
                job = LMJob.from_dict(job_data)
                jobs[job.id] = job
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"job[{index}]: {exc}")
        self._jobs = jobs
        self.load_error = "; ".join(errors) if errors else None

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "jobs": [job.to_dict() for job in self.list()],
        }
        temp_path = self.store_path.with_suffix(f"{self.store_path.suffix}.tmp")
        temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(self.store_path)


def _normalise_message(message: dict[str, str]) -> dict[str, str]:
    role = str(message.get("role", "")).strip()
    content = str(message.get("content", "")).strip()
    if role not in {"system", "user", "assistant"}:
        raise ValueError(f"Unsupported LM message role: {role}")
    if not content:
        raise ValueError("LM message content is required")
    return {"role": role, "content": content}


def _build_result(
    response: dict[str, Any],
    expectation: LMJobExpectation,
) -> tuple[dict[str, Any], dict[str, Any]]:
    content = _assistant_content(response)
    result: dict[str, Any] = {
        "content": content,
        "response": response,
    }
    validation: dict[str, Any] = {
        "expected": expectation.value,
        "valid": True,
        "errors": [],
    }
    if expectation == LMJobExpectation.JSON:
        try:
            result["parsed_json"] = _parse_json_content(content)
        except ValueError as exc:
            validation["valid"] = False
            validation["errors"].append(str(exc))
    return result, validation


def _assistant_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("LLM response has no choices")
    message = choices[0].get("message", {})
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM response has no text content")
    return content.strip()


def _parse_json_content(content: str) -> Any:
    clean = _strip_code_fence(content)
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    starts = [index for index in (clean.find("{"), clean.find("[")) if index >= 0]
    ends = [index for index in (clean.rfind("}"), clean.rfind("]")) if index >= 0]
    if not starts or not ends:
        raise ValueError("No JSON object or array found in LLM response")

    candidate = clean[min(starts) : max(ends) + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON returned by LLM: {exc}") from exc


def _strip_code_fence(content: str) -> str:
    lines = content.strip().splitlines()
    if len(lines) >= 2 and lines[0].lstrip().startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return content.strip()
