"""Tests del motor scheduler: semáforo, recibo, idempotencia, fallo contenido."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from loombit_operator.routines import CronSchedule, Routine, RoutineStore
from loombit_operator.scheduler import RoutineScheduler
from loombit_operator.skills import SkillSafetyClass

MADRID = ZoneInfo("Europe/Madrid")
NOW = datetime(2026, 6, 8, 6, 0, tzinfo=UTC)


def _due_cron() -> CronSchedule:
    local = NOW.astimezone(MADRID)
    return CronSchedule(f"{local.minute} {local.hour} * * *")


def _store_with(tmp_path, safety=SkillSafetyClass.PASSIVE):
    store = RoutineStore(store_path=tmp_path / "r.json")
    r = Routine(name="r", schedule=_due_cron(), objective="o", safety=safety)
    store.add(r)
    return store, r


def _sched(store, tmp_path, executor):
    return RoutineScheduler(store, executor, receipt_dir=tmp_path / "rec")


def test_tick_passive_completes_and_writes_receipt(tmp_path):
    store, r = _store_with(tmp_path, SkillSafetyClass.PASSIVE)
    sched = _sched(store, tmp_path, lambda routine, now: "brief de prueba")
    receipts = sched.tick(NOW)
    assert len(receipts) == 1
    rc = receipts[0]
    assert rc.status == "completed"
    assert rc.output == "brief de prueba"
    assert list((tmp_path / "rec").glob("*.json"))  # recibo en disco
    assert store.get(r.id).last_fired == r.schedule.minute_key(NOW)


def test_tick_assisted_pending_approval(tmp_path):
    store, _ = _store_with(tmp_path, SkillSafetyClass.ASSISTED)
    sched = _sched(store, tmp_path, lambda routine, now: "draft")
    assert sched.tick(NOW)[0].status == "pending_approval"


def test_tick_blocked(tmp_path):
    store, _ = _store_with(tmp_path, SkillSafetyClass.BLOCKED_BY_DEFAULT)
    sched = _sched(store, tmp_path, lambda routine, now: "x")
    assert sched.tick(NOW)[0].status == "blocked"


def test_tick_failure_is_contained(tmp_path):
    store, r = _store_with(tmp_path, SkillSafetyClass.PASSIVE)

    def boom(routine, now):
        raise RuntimeError("LM caido")

    sched = _sched(store, tmp_path, boom)
    rc = sched.tick(NOW)[0]  # no debe propagar
    assert rc.status == "failed"
    assert "LM caido" in rc.error
    # marca el minuto igualmente para no reintentar en bucle
    assert store.get(r.id).last_fired == r.schedule.minute_key(NOW)


def test_idempotency_second_tick_same_minute(tmp_path):
    store, _ = _store_with(tmp_path, SkillSafetyClass.PASSIVE)
    sched = _sched(store, tmp_path, lambda routine, now: "ok")
    assert len(sched.tick(NOW)) == 1
    assert len(sched.tick(NOW)) == 0  # mismo minuto -> no refire


def test_run_routine_forces_ignoring_cron(tmp_path):
    store = RoutineStore(store_path=tmp_path / "r.json")
    local = NOW.astimezone(MADRID)
    r = Routine(
        name="x",
        schedule=CronSchedule(f"{(local.minute + 1) % 60} {local.hour} * * *"),
        objective="o",
        safety=SkillSafetyClass.PASSIVE,
    )
    store.add(r)
    assert store.due(NOW) == []  # no toca por cron
    sched = _sched(store, tmp_path, lambda routine, now: "forzado")
    rc = sched.run_routine(r, NOW)
    assert rc.status == "completed"
    assert rc.output == "forzado"
