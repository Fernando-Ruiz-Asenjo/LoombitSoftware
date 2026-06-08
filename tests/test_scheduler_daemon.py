"""
Eval del daemon de Routines: el hilo de fondo hace tick() de verdad y para limpio.
(El primer tick ocurre nada más arrancar, antes de la espera.)
"""

import time

from loombit_operator.routines import RoutineStore
from loombit_operator.scheduler import RoutineScheduler, SchedulerDaemon


def _isolated_scheduler(tmp_path, executor):
    # AISLADO: store vacío en tmp + recibos en tmp → NO toca las routines reales
    # ni la carpeta de recibos de producción (el bug del 'ok').
    return RoutineScheduler(
        RoutineStore(store_path=tmp_path / "routines.json"),
        executor,
        receipt_dir=tmp_path / "receipts",
    )


def test_daemon_ticks_and_stops(tmp_path):
    ticks = {"n": 0}
    sched = _isolated_scheduler(tmp_path, lambda r, now: "ok")
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


def test_daemon_double_start_is_safe(tmp_path):
    daemon = SchedulerDaemon(_isolated_scheduler(tmp_path, lambda r, now: "ok"), interval_seconds=5)
    daemon.start()
    daemon.start()  # no debe lanzar ni crear un segundo hilo
    daemon.stop()
