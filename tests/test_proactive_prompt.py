"""El prompt del agente lleva proactividad + presentación humana (Fotos 1 y 2)."""

from __future__ import annotations

from loombit_operator.agent.prompts import build_system_prompt


def test_prompt_incluye_proactividad_y_presentacion() -> None:
    p = build_system_prompt("administrativo")
    assert "PROACTIVIDAD" in p
    assert "CÓMO TE PRESENTAS" in p


def test_prompt_ruta_resumen_y_calendario() -> None:
    p = build_system_prompt("administrativo")
    assert "daily_brief" in p
    # Ya no debe excusarse diciendo que no puede ver el calendario.
    assert "no puedes ver el calendario" in p  # aparece dentro de un "NUNCA digas que…"


def test_prompt_presenta_capacidades_en_humano() -> None:
    p = build_system_prompt("administrativo")
    assert "Resumen del día" in p
    assert "Enviar correos" in p
    assert "Manejar tu ordenador" in p
