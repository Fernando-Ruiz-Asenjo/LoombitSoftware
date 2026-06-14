"""Tests del prompt del agente: jerarquía de ejecución y gates de seguridad."""

from loombit_operator.agent.prompts import build_system_prompt


def test_prompt_includes_execution_hierarchy_and_pilot_tools():
    p = build_system_prompt()
    assert "JERARQUÍA DE EJECUCIÓN" in p
    assert "desktop_ui_snapshot" in p
    assert "desktop_click_accessibility" in p
    assert "desktop_screen_changed" in p


def test_prompt_includes_security_gates():
    low = build_system_prompt().lower()
    for kw in (
        "pausa",  # los efectos externos pausan para que el usuario apruebe (sin tool aparte)
        "apruebe",
        "credenciales",
        "no inventes datos",
        "fraude",
        "datos, no órdenes",
    ):
        assert kw in low


def test_prompt_formats_and_appends_memory():
    p = build_system_prompt(profile="contabilidad", memory_block="\n\nMEMORIA: saldo")
    assert "Loombit Operator" in p
    assert "MEMORIA: saldo" in p
    assert "{rol_descripcion}" not in p  # el .format se aplicó


def test_prompt_blinda_ui_generada():
    """§SEG-8 / D-101: la UI generada es propuesta, no camino de control (catálogo cerrado)."""
    low = build_system_prompt().lower()
    assert "interfaz generada" in low
    assert "catálogo cerrado" in low
    assert "no el camino de control" in low
