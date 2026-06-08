"""Tool de resumen del día + ver agenda (Foto 2: proactividad de lectura)."""

from __future__ import annotations

from types import SimpleNamespace

from loombit_operator.llm import LLMClient
from loombit_operator.tools import brief
from loombit_operator.tools.registry import select_tool_names


def test_resumen_selecciona_daily_brief() -> None:
    sel = select_tool_names("Hazme un resumen de hoy: tareas, vencimientos y el foco recomendado")
    assert "daily_brief" in sel
    assert "calendar_today" in sel


def test_narrar_usa_el_llm_cuando_esta(monkeypatch) -> None:
    monkeypatch.setattr(
        LLMClient, "chat", lambda self, m, max_tokens=None: SimpleNamespace(content="Hoy: 2 citas.")
    )
    assert brief._narrar(["2 evento(s) hoy", "1 aprobación pendiente"]) == "Hoy: 2 citas."


def test_narrar_cae_a_vinetas_si_el_llm_falla(monkeypatch) -> None:
    def _boom(self, m, max_tokens=None):
        raise RuntimeError("LM Studio apagado")

    monkeypatch.setattr(LLMClient, "chat", _boom)
    out = brief._narrar(["3 cuenta(s) a cobrar VENCIDA(s) por 500 €"])
    assert "•" in out and "500" in out  # determinista y honesto, sin modelo


def test_daily_brief_junta_senales(monkeypatch) -> None:
    monkeypatch.setattr(
        brief, "_señales_del_dia", lambda now=None: ["sin eventos hoy", "2 correos sin leer"]
    )
    monkeypatch.setattr(
        LLMClient, "chat", lambda self, m, max_tokens=None: SimpleNamespace(content="Resumen.")
    )
    assert brief._daily_brief() == "Resumen."


def test_calendar_today_sin_conexion(monkeypatch) -> None:
    import loombit_operator.skill_blanca_calendar_read as cr

    def _no_token(*a, **k):
        raise ValueError("calendar_read_no_token")

    monkeypatch.setattr(cr, "eventos_de_hoy", _no_token)
    assert "no está conectado" in brief._calendar_today()


def test_calendar_today_lista_eventos(monkeypatch) -> None:
    import loombit_operator.skill_blanca_calendar_read as cr

    monkeypatch.setattr(
        cr,
        "eventos_de_hoy",
        lambda *a, **k: [
            {"summary": "Dentista", "start": "2026-06-08T17:00:00+02:00", "all_day": False}
        ],
    )
    out = brief._calendar_today()
    assert "Dentista" in out and "17:00" in out
