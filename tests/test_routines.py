"""Tests del modelo de Routines: cron, store, idempotencia."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from loombit_operator.routines import (
    CronSchedule,
    Routine,
    RoutineStore,
    _parse_field,
    brief_diario_routine,
)
from loombit_operator.skills import SkillSafetyClass

MADRID = ZoneInfo("Europe/Madrid")
NOW = datetime(2026, 6, 8, 6, 0, tzinfo=UTC)


def test_parse_field_basic():
    assert _parse_field("*", 0, 5) == {0, 1, 2, 3, 4, 5}
    assert _parse_field("1-3", 0, 59) == {1, 2, 3}
    assert _parse_field("1,4,7", 0, 59) == {1, 4, 7}
    assert _parse_field("0-10/5", 0, 59) == {0, 5, 10}
    assert _parse_field("*/15", 0, 59) == {0, 15, 30, 45}


def test_parse_field_invalid_range():
    with pytest.raises(ValueError):
        _parse_field("5-1", 0, 59)


def test_cron_minute_match():
    local = NOW.astimezone(MADRID)
    due = CronSchedule(f"{local.minute} {local.hour} * * *")
    not_due = CronSchedule(f"{(local.minute + 1) % 60} {local.hour} * * *")
    assert due.is_due(NOW) is True
    assert not_due.is_due(NOW) is False


def test_cron_weekday_filter():
    local = NOW.astimezone(MADRID)
    cron_dow = (local.weekday() + 1) % 7
    matching = CronSchedule(f"{local.minute} {local.hour} * * {cron_dow}")
    other = CronSchedule(f"{local.minute} {local.hour} * * {(cron_dow + 1) % 7}")
    assert matching.is_due(NOW) is True
    assert other.is_due(NOW) is False


def test_cron_wrong_field_count_raises():
    with pytest.raises(ValueError):
        CronSchedule("0 8 * *").is_due(NOW)


def test_minute_key_is_local():
    local = NOW.astimezone(MADRID)
    assert CronSchedule("0 8 * * *").minute_key(NOW) == local.strftime("%Y-%m-%dT%H:%M")


def test_store_roundtrip(tmp_path):
    store = RoutineStore(store_path=tmp_path / "r.json")
    r = store.add(brief_diario_routine())
    reloaded = RoutineStore(store_path=tmp_path / "r.json").get(r.id)
    assert reloaded.name == "Brief diario"
    assert reloaded.safety == SkillSafetyClass.PASSIVE
    assert reloaded.schedule.expr == "0 8 * * 1-5"


def test_due_filters_disabled_and_idempotency(tmp_path):
    store = RoutineStore(store_path=tmp_path / "r.json")
    local = NOW.astimezone(MADRID)
    r = Routine(
        name="x",
        schedule=CronSchedule(f"{local.minute} {local.hour} * * *"),
        objective="o",
        safety=SkillSafetyClass.PASSIVE,
    )
    store.add(r)
    assert [x.id for x in store.due(NOW)] == [r.id]

    r.enabled = False
    store.save_routine(r)
    assert store.due(NOW) == []

    r.enabled = True
    r.last_fired = r.schedule.minute_key(NOW)
    store.save_routine(r)
    assert store.due(NOW) == []  # ya disparado este minuto


def test_due_skips_invalid_cron(tmp_path):
    store = RoutineStore(store_path=tmp_path / "r.json")
    store.add(Routine(name="bad", schedule=CronSchedule("no-valido"), objective="o"))
    assert store.due(NOW) == []  # no revienta y no dispara
