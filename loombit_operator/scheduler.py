"""
scheduler.py — dispara las Routines `due`, ejecuta vía un executor inyectado, escribe
recibo y aplica el semáforo. Núcleo blanco. Ver `docs/ROUTINES_LOOMBIT.md`.

Reglas de solidez:
- **Idempotencia:** tras disparar, se marca `last_fired` (clave de minuto); re-ejecutar
  `tick` en el mismo minuto no vuelve a disparar (y sobrevive a reinicios, porque se
  persiste en el store).
- **Semáforo:** PASSIVE → completado; ASSISTED/SAFETY_SENSITIVE → pendiente de aprobación;
  BLOCKED_BY_DEFAULT → bloqueado.
- **Fallo ruidoso pero contenido:** si el executor revienta, la rutina queda en `failed`
  con su error y el `tick` sigue con las demás (no se cae el bucle).
- **Recibo:** cada ejecución deja un JSON auditable en `runtime/local/routine_receipts/`.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .config import AppSettings, get_settings
from .routines import Routine, RoutineStore
from .skills import SkillSafetyClass

# Un executor recibe la rutina y el instante, y devuelve el texto de salida.
RoutineExecutor = Callable[[Routine, datetime], str]


@dataclass
class RoutineReceipt:
    routine_id: str
    name: str
    fired_at: str  # ISO UTC
    minute_key: str  # clave local de minuto (idempotencia)
    status: str  # completed | pending_approval | blocked | failed
    output_kind: str
    safety: str
    output: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_STATUS_BY_SAFETY = {
    SkillSafetyClass.PASSIVE: "completed",
    SkillSafetyClass.ASSISTED: "pending_approval",
    SkillSafetyClass.SAFETY_SENSITIVE: "pending_approval",
    SkillSafetyClass.BLOCKED_BY_DEFAULT: "blocked",
}


class RoutineScheduler:
    def __init__(
        self,
        store: RoutineStore,
        executor: RoutineExecutor,
        settings: AppSettings | None = None,
        receipt_dir: Path | None = None,
    ) -> None:
        active = settings or get_settings()
        self.store = store
        self.executor = executor
        self.receipt_dir = receipt_dir or active.routine_receipt_dir

    def tick(self, now: datetime | None = None) -> list[RoutineReceipt]:
        """Procesa todas las rutinas `due` en `now` (UTC por defecto)."""
        now = now or datetime.now(UTC)
        receipts: list[RoutineReceipt] = []
        for routine in self.store.due(now):
            receipts.append(self._run_one(routine, now))
        return receipts

    def run_routine(self, routine: Routine, now: datetime | None = None) -> RoutineReceipt:
        """Fuerza la ejecución de una rutina ahora, ignorando el cron (demo/manual)."""
        return self._run_one(routine, now or datetime.now(UTC))

    def _run_one(self, routine: Routine, now: datetime) -> RoutineReceipt:
        minute_key = routine.schedule.minute_key(now)
        output, error = "", ""
        try:
            output = self.executor(routine, now)
            status = _STATUS_BY_SAFETY.get(routine.safety, "pending_approval")
        except Exception as exc:  # fallo contenido: no tumbar el tick
            status = "failed"
            error = str(exc)

        # Idempotencia: marcar SIEMPRE el minuto (incluso si falló) para no reintentar
        # el mismo minuto en bucle. Se persiste -> sobrevive a reinicios.
        routine.last_fired = minute_key
        self.store.save_routine(routine)

        receipt = RoutineReceipt(
            routine_id=routine.id,
            name=routine.name,
            fired_at=now.astimezone(UTC).isoformat(),
            minute_key=minute_key,
            status=status,
            output_kind=routine.output_kind,
            safety=routine.safety.value,
            output=output,
            error=error,
        )
        self._write_receipt(receipt)
        return receipt

    def _write_receipt(self, receipt: RoutineReceipt) -> None:
        self.receipt_dir.mkdir(parents=True, exist_ok=True)
        stamp = receipt.fired_at.replace(":", "").replace("-", "")
        path = self.receipt_dir / f"{stamp}_{receipt.routine_id}.json"
        path.write_text(
            json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )


class SchedulerDaemon:
    """Hilo de fondo que llama a `scheduler.tick()` cada `interval` segundos.

    Cada tick va envuelto en try/except: el hilo nunca muere en silencio. Opt-in
    (ver `routines_daemon_enabled` en config); por defecto NO se arranca.
    """

    def __init__(self, scheduler: RoutineScheduler, interval_seconds: int = 60) -> None:
        self.scheduler = scheduler
        self.interval = max(5, int(interval_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None
        self.tick_count = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="routines-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.scheduler.tick()
                self.tick_count += 1
            except Exception as exc:  # noqa: BLE001 — nunca tumbar el hilo del daemon
                self.last_error = str(exc)
            self._stop.wait(self.interval)
