"""El texto de cara al usuario nunca debe filtrar nombres de tools (auditoría: 14B los filtra)."""

from __future__ import annotations

from loombit_operator.tool_labels import humanize_user_text


def test_quita_tool_con_conector_previo() -> None:
    # Caso REAL observado en vivo (el 14B alucinó "calendar_search").
    s = "No pude encontrar la reunión específica usando `calendar_search`, pero ya tengo los detalles."
    out = humanize_user_text(s)
    assert "calendar_search" not in out
    assert "usando" not in out
    assert out == "No pude encontrar la reunión específica, pero ya tengo los detalles."


def test_quita_varias_tools_sueltas() -> None:
    out = humanize_user_text("Lo busqué con gmail_search y te lo envié con gmail_send.")
    assert "gmail_search" not in out and "gmail_send" not in out


def test_no_pisa_nombres_de_fichero() -> None:
    # Un nombre de fichero NO es una tool: no debe tocarse.
    s = "Guardé el resumen en mi_factura_2024.pdf como pediste."
    assert humanize_user_text(s) == s


def test_quita_task_done_y_desktop() -> None:
    out = humanize_user_text("Listo task_done. Lo hice con desktop_click_accessibility.")
    assert "task_done" not in out and "desktop_click" not in out


def test_texto_limpio_intacto() -> None:
    s = "Te he enviado el recordatorio a tu correo ✅. Te aviso si responde."
    assert humanize_user_text(s) == s


def test_vacio() -> None:
    assert humanize_user_text("") == ""
