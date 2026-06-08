"""
Eval del daemon de Routines: el hilo de fondo hace tick() de verdad y para limpio.
(El primer tick ocurre nada más arrancar, antes de la espera.)
"""

import time

from loombit_operator.routines import RoutineStore
from loombit_operator.scheduler import RoutineScheduler, SchedulerDaemon


def test_daemon_ticks_and_stops():
    ticks = {"n": 0}

    def _executor(routine, now):
        return "ok"

    sched = RoutineScheduler(RoutineStore(), _executor)
    # envolver tick para contar invocaciones reales del hilo
    orig_tick = sched.tick

    def _counting_tick(now=None):
        ticks["n"] += 1
        return orig_tick(now)

    sched.tick = _counting_tick  # type: ignore[method-assign]

    daemon = SchedulerDaemon(sched, interval_seconds=5)
    daemon.start()
    time.sleep(0.4)  # el primer tick es inmediato
    daemon.stop()

    assert ticks["n"] >= 1
    assert daemon.tick_count >= 1


def test_daemon_double_start_is_safe():
    sched = RoutineScheduler(RoutineStore(), lambda r, now: "ok")
    daemon = SchedulerDaemon(sched, interval_seconds=5)
    daemon.start()
    daemon.start()  # no debe lanzar ni crear un segundo hilo
    daemon.stop()
