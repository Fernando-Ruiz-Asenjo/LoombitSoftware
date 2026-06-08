"""
routines.py — motor de Routines (agentes proactivos programados). Núcleo blanco.

Una Routine = { disparador (cron), objetivo, entrega (semáforo), estado }. Es neutra:
no sabe de "cobros" ni "IVA"; solo programa y dispara trabajo del agente. Persiste en
`runtime/local/routines.json`. Ver `docs/ROUTINES_LOOMBIT.md`.

Estado: 🟡 modelo + cron + store, unit-tested. La ejecución real va por un executor
inyectado (`scheduler.py`), para mantener este módulo desacoplado y testeable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from .config import AppSettings, get_settings
from .skills import SkillSafetyClass


class RoutineNotFoundError(KeyError):
    pass


# ── Cron: subconjunto estándar de 5 campos (min hora dom mes dow) ───────────────


def _parse_field(token: str, lo: int, hi: int) -> set[int]:
    """Expande un campo cron a un conjunto de enteros. Soporta `*`, `,`, `-`, `/`."""
    values: set[int] = set()
    for part in token.split(","):
        part = part.strip()
        step = 1
        base = part
        if "/" in part:
            base, step_s = part.split("/", 1)
            step = int(step_s)
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a, b = base.split("-", 1)
            start, end = int(a), int(b)
        else:
            start = end = int(base)
        if start > end or step < 1:
            raise ValueError(f"campo cron inválido: {token!r}")
        for v in range(start, end + 1, step):
            if lo <= v <= hi:
                values.add(v)
    if not values:
        raise ValueError(f"campo cron sin valores: {token!r}")
    return values


@dataclass(frozen=True)
class CronSchedule:
    """Expresión cron de 5 campos + zona horaria. Granularidad de minuto."""

    expr: str
    tz: str = "Europe/Madrid"

    def _fields(self) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
        parts = self.expr.split()
        if len(parts) != 5:
            raise ValueError(f"cron debe tener 5 campos: {self.expr!r}")
        minute = _parse_field(parts[0], 0, 59)
        hour = _parse_field(parts[1], 0, 23)
        dom = _parse_field(parts[2], 1, 31)
        month = _parse_field(parts[3], 1, 12)
        dow_raw = _parse_field(parts[4], 0, 7)
        dow = {0 if d == 7 else d for d in dow_raw}  # 7 = domingo = 0
        return minute, hour, dom, month, dow

    def _local(self, now: datetime) -> datetime:
        return now.astimezone(ZoneInfo(self.tz))

    def is_due(self, now: datetime) -> bool:
        """¿Coincide `now` (convertido a la tz de la rutina) con el cron, al minuto?

        Nota: si `dom` y `dow` están ambos restringidos, el cron real usa OR; aquí se
        usa AND. Nuestras plantillas usan `dom='*'`, donde no hay diferencia.
        """
        local = self._local(now)
        minute, hour, dom, month, dow = self._fields()
        cron_dow = (local.weekday() + 1) % 7  # py Mon=0 -> cron Mon=1 ; domingo=0
        return (
            local.minute in minute
            and local.hour in hour
            and local.day in dom
            and local.month in month
            and cron_dow in dow
        )

    def minute_key(self, now: datetime) -> str:
        """Clave única del minuto local — base de la idempotencia."""
        return self._local(now).strftime("%Y-%m-%dT%H:%M")

    def to_dict(self) -> dict[str, str]:
        return {"expr": self.expr, "tz": self.tz}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CronSchedule":
        return cls(expr=str(d["expr"]), tz=str(d.get("tz", "Europe/Madrid")))


# ── Routine ─────────────────────────────────────────────────────────────────────


@dataclass
class Routine:
    name: str
    schedule: CronSchedule
    objective: str
    safety: SkillSafetyClass = SkillSafetyClass.ASSISTED
    output_kind: str = "brief"  # brief | draft | notice
    enabled: bool = True
    scope: dict[str, Any] = field(default_factory=dict)  # conectores/tools (mínimo privilegio)
    id: str = field(default_factory=lambda: str(uuid4()))
    last_fired: str = ""  # minute_key de la última ejecución (idempotencia)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "schedule": self.schedule.to_dict(),
            "objective": self.objective,
            "safety": self.safety.value,
            "output_kind": self.output_kind,
            "enabled": self.enabled,
            "scope": self.scope,
            "last_fired": self.last_fired,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Routine":
        return cls(
            id=str(d["id"]),
            name=str(d["name"]),
            schedule=CronSchedule.from_dict(d["schedule"]),
            objective=str(d.get("objective", "")),
            safety=SkillSafetyClass(d.get("safety", SkillSafetyClass.ASSISTED)),
            output_kind=str(d.get("output_kind", "brief")),
            enabled=bool(d.get("enabled", True)),
            scope=dict(d.get("scope", {})),
            last_fired=str(d.get("last_fired", "")),
            created_at=str(d.get("created_at", "")),
        )


# ── Store (persistencia JSON con escritura atómica) ─────────────────────────────


class RoutineStore:
    def __init__(self, store_path: Path | None = None, settings: AppSettings | None = None) -> None:
        active = settings or get_settings()
        self.store_path = store_path or active.routine_store_path
        self._routines: dict[str, Routine] = {}
        self.load_error: str | None = None
        self._load()

    def add(self, routine: Routine) -> Routine:
        self._routines[routine.id] = routine
        self._save()
        return routine

    def get(self, routine_id: str) -> Routine:
        try:
            return self._routines[routine_id]
        except KeyError as exc:
            raise RoutineNotFoundError(routine_id) from exc

    def save_routine(self, routine: Routine) -> None:
        self._routines[routine.id] = routine
        self._save()

    def list(self, enabled_only: bool = False) -> list[Routine]:
        routines = list(self._routines.values())
        if enabled_only:
            routines = [r for r in routines if r.enabled]
        return sorted(routines, key=lambda r: r.created_at)

    def due(self, now: datetime) -> list[Routine]:
        """Rutinas habilitadas cuyo cron coincide con `now` y que NO se han disparado
        ya en este minuto (idempotencia). Un cron inválido nunca dispara."""
        out: list[Routine] = []
        for routine in self._routines.values():
            if not routine.enabled:
                continue
            try:
                if routine.schedule.is_due(
                    now
                ) and routine.last_fired != routine.schedule.minute_key(now):
                    out.append(routine)
            except ValueError:
                continue
        return out

    def snapshot(self) -> dict[str, Any]:
        routines = self.list()
        return {
            "store_path": str(self.store_path),
            "load_error": self.load_error,
            "count": len(routines),
            "enabled": sum(1 for r in routines if r.enabled),
            "routines": [r.to_dict() for r in routines],
        }

    def _load(self) -> None:
        if not self.store_path.exists():
            self._routines = {}
            return
        text = self.store_path.read_text(encoding="utf-8")
        if not text.strip():
            self._routines = {}
            return
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            self._routines = {}
            self.load_error = f"routine store JSON inválido: {exc}"
            return
        routines: dict[str, Routine] = {}
        errors: list[str] = []
        for i, d in enumerate(raw.get("routines", [])):
            try:
                r = Routine.from_dict(d)
                routines[r.id] = r
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f"routine[{i}]: {exc}")
        self._routines = routines
        self.load_error = "; ".join(errors) if errors else None

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 1, "routines": [r.to_dict() for r in self.list()]}
        tmp = self.store_path.with_suffix(f"{self.store_path.suffix}.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.store_path)


def brief_diario_routine() -> Routine:
    """Plantilla por defecto: Brief diario a las 08:00 (L-V), Europe/Madrid. PASSIVE."""
    return Routine(
        name="Brief diario",
        schedule=CronSchedule("0 8 * * 1-5", tz="Europe/Madrid"),
        objective=(
            "Resume el día en máximo 5 líneas: cola de trabajo, vencimientos de cobro, "
            "plazos próximos y el foco recomendado. Lenguaje natural, sin JSON."
        ),
        safety=SkillSafetyClass.PASSIVE,
        output_kind="brief",
    )
