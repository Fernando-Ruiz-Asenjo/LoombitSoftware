"""Capa de presentación humana de las capacidades (Foto 1)."""

from __future__ import annotations

from loombit_operator.tool_labels import capability_block, human_label


def test_human_label_maps_known_tool() -> None:
    assert "Enviar correos" in human_label("gmail_send")


def test_human_label_falls_back_to_name() -> None:
    assert human_label("totally_unknown") == "totally_unknown"


def test_capability_block_is_human_and_hides_technical_names() -> None:
    block = capability_block()
    # Describe capacidades en humano…
    assert "Resumen del día" in block
    assert "Enviar correos" in block
    assert "Manejar tu ordenador" in block
    # …y NUNCA expone nombres técnicos de tools.
    for tech in ("gmail_send", "calendar_create", "contacts_find", "daily_brief", "calendar_today"):
        assert tech not in block
