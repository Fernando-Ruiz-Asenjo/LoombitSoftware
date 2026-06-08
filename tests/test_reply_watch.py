"""
Routine 'Vigilar respuestas': detecta respuestas de contactos y prepara borradores.
Se prueban las partes puras (config, dispatch, sin red).
"""

from datetime import datetime

from loombit_operator import routine_executors as rx
from loombit_operator.skills import SkillSafetyClass


def test_routine_config():
    r = rx.vigilar_respuestas_routine()
    assert r.name == "Vigilar respuestas"
    assert r.output_kind == "reply_watch"
    assert r.enabled is True  # activa (daemon proactivo)
    assert r.schedule.expr == "* * * * *"  # cada minuto
    assert r.safety == SkillSafetyClass.ASSISTED


def test_buscar_respuestas_sin_contactos_no_toca_red():
    # sin contactos no hay query → [] sin llamar a Gmail
    assert rx._buscar_respuestas("token-falso", []) == []


def test_default_executor_despacha_reply_watch(monkeypatch):
    llamado = {}

    def _fake(routine, now):
        llamado["ok"] = True
        return "ok"

    monkeypatch.setattr(rx, "reply_watch_executor", _fake)
    rx.default_executor(rx.vigilar_respuestas_routine(), datetime.now())
    assert llamado.get("ok") is True
