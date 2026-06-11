"""
Objetivo #5: cablear las decisiones REALES (aprobar/rechazar) al motor de hábitos.
Solo se aprende de las sugerencias PROACTIVAS de Loombit (no de lo que el usuario pidió).
"""

from types import SimpleNamespace

from loombit_operator.habitos import HabitLedger
from loombit_operator.habitos_runs import registrar_decision_run, tipo_sujeto_de_run


def _run(**kw):
    base = {"proactive": True, "pending_approval": {}, "task": "", "id": "r1"}
    base.update(kw)
    return SimpleNamespace(**base)


def test_extrae_respuesta_y_destinatario_del_proposed_action():
    run = _run(
        pending_approval={"proposed_action": "Enviar correo a javier@acme.com con asunto RE: …"}
    )
    assert tipo_sujeto_de_run(run) == ("respuesta", "javier@acme.com")


def test_extrae_del_task_si_falta_en_pending():
    run = _run(task="Responde al correo de Ana <ana@x.com> y envíalo con gmail_send a ana@x.com")
    assert tipo_sujeto_de_run(run) == ("respuesta", "ana@x.com")


def test_detecta_tipo_evento():
    run = _run(
        pending_approval={"proposed_action": "calendar_create: reunión con luis@x.com el martes"}
    )
    assert tipo_sujeto_de_run(run) == ("evento", "luis@x.com")


def test_sin_email_devuelve_none():
    assert tipo_sujeto_de_run(_run(task="haz algo sin destinatario")) is None


def test_solo_aprende_de_proactivos(tmp_path, monkeypatch):
    import loombit_operator.habitos_runs as hr

    led = HabitLedger(path=tmp_path / "h.json")
    monkeypatch.setattr(hr, "get_habits", lambda: led)

    # Run NO proactivo (lo pidió el usuario) → no se aprende.
    pedido = _run(proactive=False, pending_approval={"proposed_action": "correo a x@x.com"})
    assert registrar_decision_run(pedido, "aceptada") is False
    assert led.habito("respuesta", "x@x.com")["n"] == 0

    # Run proactivo → sí se aprende la decisión.
    sugerido = _run(proactive=True, pending_approval={"proposed_action": "correo a javier@x.com"})
    assert registrar_decision_run(sugerido, "aceptada") is True
    assert led.habito("respuesta", "javier@x.com")["aceptadas"] == 1
    registrar_decision_run(sugerido, "rechazada")
    assert led.habito("respuesta", "javier@x.com")["rechazadas"] == 1
