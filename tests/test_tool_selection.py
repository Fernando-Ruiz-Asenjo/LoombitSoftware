"""
Activación de tools por intención: el agente solo recibe las tools que la
petición necesita (núcleo + grupos), no las 44 de golpe.
"""

from loombit_operator.tools import tool_registry
from loombit_operator.tools.registry import CORE_TOOLS, select_tool_names


def test_email_task_selects_email_tools():
    names = select_tool_names("manda un correo a Jana dando las buenas noches")
    assert "gmail_send" in names
    assert "contacts_find" in names
    assert CORE_TOOLS <= names  # el núcleo siempre
    assert "desktop_click" not in names  # nada de escritorio para un correo


def test_desktop_task_selects_desktop_tools():
    names = select_tool_names("abre Excel y haz una captura de pantalla")
    assert "desktop_screenshot" in names  # el grupo especialista se activa
    # El reach admin (web/correo) sigue disponible: permite flujos cruzados
    # (p.ej. "abre Excel, rellénalo y mándamelo por correo") y nunca deja ciego al agente.
    assert "web_fetch" in names


def test_calendar_task_selects_calendar():
    names = select_tool_names("agéndame una reunión con el proveedor el jueves")
    assert "calendar_create" in names


def test_unmatched_task_keeps_admin_reach():
    # Una petición que no casa con ninguna keyword NO debe dejar al agente con
    # solo correo+calendario: mantiene su reach (web, memoria, documentos).
    names = select_tool_names("échame una mano con una gestión")
    assert {"gmail_send", "web_fetch", "memory_search", "read_invoice"} <= names
    assert CORE_TOOLS <= names


def test_travel_task_not_blind_to_web():
    # Regresión: el vocabulario de una agencia de viajes no casaba con ninguna
    # keyword → el agente quedaba ciego a web_fetch y decía "no puedo abrir webs".
    names = select_tool_names("búscame vuelos a Londres y un hotel de 4 estrellas para Marta")
    assert "web_fetch" in names
    assert "memory_search" in names


def test_brief_task_selects_daily_brief():
    names = select_tool_names("hazme un resumen de hoy con el foco recomendado")
    assert "daily_brief" in names  # el resumen enruta al brief, no al correo
    assert "calendar_today" in names


def test_to_openai_task_sends_fewer_tools_than_all():
    all_tools = tool_registry.to_openai()
    email_tools = tool_registry.to_openai(task="manda un correo a Jana")
    assert len(email_tools) < len(all_tools)
    names = {t["function"]["name"] for t in email_tools}
    assert "gmail_send" in names
    assert all(n not in names for n in ("desktop_click", "desktop_mouse_move"))
