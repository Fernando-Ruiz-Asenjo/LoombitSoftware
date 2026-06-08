"""Resolutor drag-to-act de la Galaxia: (qué arrastras) × (dónde sueltas) → acción."""

from __future__ import annotations

from loombit_operator.galaxia_actions import resolve_drop

CONTACTO = {
    "tipo": "contacto",
    "etiqueta": "Jana",
    "email": "jana@example.com",
    "id": "c:jana@example.com",
}
CUENTA = {"tipo": "cuenta", "etiqueta": "Acme SL", "importe": 1200.0, "id": "f:42"}
SOL = {"kind": "sol", "nombre": "Mi negocio"}
DOC = {"kind": "documento", "etiqueta": "Factura 2026-03.pdf", "path": "C:/docs/factura.pdf"}
CONV = {"kind": "conversacion", "etiqueta": "Presupuesto reforma", "id": "run-7"}


def test_documento_a_contacto_envia_con_aprobacion() -> None:
    a = resolve_drop(DOC, CONTACTO)
    assert a.action_id == "enviar_documento"
    assert a.modo == "agent_task"
    assert a.efecto_externo is True  # sale al mundo → pasa por aprobación
    assert "jana@example.com" in a.task
    assert "Jana" in a.titulo


def test_conversacion_a_contacto_retoma_con_aprobacion() -> None:
    a = resolve_drop(CONV, CONTACTO)
    assert a.action_id == "continuar_conversacion_contacto"
    assert a.efecto_externo is True
    assert "Jana" in a.titulo


def test_conversacion_a_cuenta_prepara_recordatorio_de_cobro() -> None:
    a = resolve_drop(CONV, CUENTA)
    assert a.action_id == "recordatorio_cobro"
    assert a.efecto_externo is True
    assert "1200" in a.task or "1200" in a.titulo  # el importe lo pone el código, no el LLM


def test_documento_a_cuenta_es_local_sin_efecto() -> None:
    a = resolve_drop(DOC, CUENTA)
    assert a.action_id == "adjuntar_doc_cuenta"
    assert a.modo == "local"
    assert a.efecto_externo is False


def test_documento_a_sol_hace_intake_sin_efecto_externo() -> None:
    a = resolve_drop(DOC, SOL)
    assert a.action_id == "intake_documento"
    assert a.efecto_externo is False


def test_contacto_a_cuenta_asigna_pagador_local() -> None:
    a = resolve_drop(CONTACTO, CUENTA)
    assert a.action_id == "asignar_pagador"
    assert a.modo == "local"
    assert a.efecto_externo is False


def test_conversacion_a_sol_navega() -> None:
    a = resolve_drop(CONV, SOL)
    assert a.modo == "navigate"
    assert a.efecto_externo is False


def test_combinacion_sin_sentido_devuelve_no_aplica() -> None:
    a = resolve_drop({"kind": "contacto"}, {"kind": "sol"})
    assert a.action_id == "no_aplica"
    assert a.efecto_externo is False


def test_deduce_kind_de_tipo_de_nodo_galaxia() -> None:
    # Los nodos de /galaxia traen `tipo`, no `kind`: el resolutor lo deduce.
    a = resolve_drop(DOC, {"tipo": "contacto", "etiqueta": "Luis", "email": "luis@x.com"})
    assert a.action_id == "enviar_documento"


def test_to_dict_serializa_para_la_ui() -> None:
    d = resolve_drop(DOC, CONTACTO).to_dict()
    assert set(d) >= {"action_id", "titulo", "explicacion", "modo", "efecto_externo", "task"}
