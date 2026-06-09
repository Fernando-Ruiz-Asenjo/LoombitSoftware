"""El texto final no debe mostrar nombres de tools (p.ej. 'task_done') como artefacto."""

from __future__ import annotations

from loombit_operator.agent.loop import _strip_tool_artifacts


def test_quita_task_done_colgante() -> None:
    # Reproduce la captura: brief correcto + 'task_done' literal al final.
    texto = (
        "✅ Resumen del día. Resultado: Hoy no tienes eventos ni correos nuevos.\n\n"
        "Para mantenerte enfocado, revisa tus tareas pendientes.\n\n"
        "task_done"
    )
    out = _strip_tool_artifacts(texto)
    assert "task_done" not in out
    assert "Resumen del día" in out
    assert "tareas pendientes" in out


def test_quita_nombre_de_tool_con_markdown() -> None:
    assert _strip_tool_artifacts("Listo.\n`daily_brief`") == "Listo."
    assert _strip_tool_artifacts("Hecho.\n**task_done**") == "Hecho."
    assert _strip_tool_artifacts("Vale.\n- task_done") == "Vale."


def test_no_toca_prosa_legitima() -> None:
    texto = "Te he preparado el resumen del día y lo he guardado."
    assert _strip_tool_artifacts(texto) == texto


def test_no_rompe_el_sentinel_de_done() -> None:
    # Una línea que empieza por TASK_DONE: NO es solo un nombre de tool → se conserva.
    texto = "TASK_DONE:✅ Correo enviado. Resultado: ok"
    assert _strip_tool_artifacts(texto) == texto
