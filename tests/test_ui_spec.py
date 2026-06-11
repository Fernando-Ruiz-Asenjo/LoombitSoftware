"""
LD-1 «Loombit Decide» — el contrato de UI generativa GOBERNADA.

Golden del validador: el vocabulario CERRADO acepta specs válidas y RECHAZA todo lo demás —
tipos desconocidos, claves no permitidas, formas incorrectas y, sobre todo, **inyección de
HTML/script** (la garantía de la Ley Fundacional: el LLM no puede colar interfaz ejecutable).
"""

import pytest

from loombit_operator.decisions import Decision, DecisionKind, DecisionOption, OptionKind, Risk
from loombit_operator.ui_spec import (
    SpecInvalida,
    cola_to_spec,
    decision_to_spec,
    validate_spec,
    validated_spec,
)


def _card():
    return {
        "type": "decision_card",
        "title": "Reclamar cobro a Acme",
        "why": "Vencida hace 12 días.",
        "risk": "medio",
        "reversible": True,
        "options": [
            {"id": "aprobar", "label": "Aprobar", "kind": "aprobar"},
            {"id": "posponer", "label": "Posponer", "kind": "posponer"},
        ],
    }


# ── Lo válido pasa ────────────────────────────────────────────────────────────


def test_decision_card_valida():
    ok, errores = validate_spec(_card())
    assert ok, errores


def test_resumen_y_eleccion_validos():
    assert validate_spec({"type": "resumen", "title": "Hoy", "lines": ["a", "b"]})[0]
    assert validate_spec(
        {"type": "eleccion", "prompt": "¿Qué hago?", "options": [{"id": "x", "label": "X"}]}
    )[0]


def test_cola_anida_cards():
    spec = {"type": "cola", "title": "Tus decisiones", "items": [_card(), _card()]}
    ok, errores = validate_spec(spec)
    assert ok, errores


# ── Lo inválido se rechaza ────────────────────────────────────────────────────


def test_tipo_desconocido_rechazado():
    ok, errores = validate_spec({"type": "iframe", "src": "x"})
    assert not ok and any("no permitido" in e for e in errores)


def test_clave_desconocida_rechazada():
    card = _card()
    card["onclick"] = "alert(1)"  # clave fuera del schema
    ok, errores = validate_spec(card)
    assert not ok


def test_falta_clave_requerida():
    ok, _ = validate_spec({"type": "decision_card", "title": "X"})  # sin options
    assert not ok


def test_risk_y_option_kind_cerrados():
    card = _card()
    card["risk"] = "catastrofico"  # fuera del conjunto cerrado
    assert not validate_spec(card)[0]
    card2 = _card()
    card2["options"][0]["kind"] = "borrar_todo"
    assert not validate_spec(card2)[0]


def test_cola_no_se_anida_en_cola():
    spec = {"type": "cola", "items": [{"type": "cola", "items": []}]}
    assert not validate_spec(spec)[0]


# ── EL test adversarial: inyección de HTML/script (la garantía Ley Fundacional) ──


@pytest.mark.parametrize(
    "veneno",
    [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "click <a href=javascript:alert(1)>aquí</a>",
        "hola<iframe src=evil>",
        "texto &#106;avascript",
    ],
)
def test_inyeccion_en_titulo_rechazada(veneno):
    card = _card()
    card["title"] = veneno
    ok, errores = validate_spec(card)
    assert not ok, f"DEBÍA rechazar: {veneno!r}"


def test_inyeccion_en_opcion_rechazada():
    card = _card()
    card["options"][0]["label"] = "<script>x</script>"
    assert not validate_spec(card)[0]


def test_inyeccion_anidada_en_cola_rechazada():
    veneno = dict(_card())
    veneno["why"] = "<svg onload=alert(1)>"
    spec = {"type": "cola", "items": [_card(), veneno]}
    assert not validate_spec(spec)[0]


def test_validated_spec_lanza_en_invalida():
    with pytest.raises(SpecInvalida):
        validated_spec({"type": "iframe"})


# ── El compositor Decision → spec produce specs válidas ───────────────────────


def _decision():
    return Decision(
        title="Reclamar cobro a Acme · 1.210 € VENCIDA",
        why="Vencida hace 12 días.",
        detail="Saldo 1.210 € + 40 € compensación (art. 8).",
        kind=DecisionKind.COBRO,
        risk=Risk.MEDIO,
        options=[
            DecisionOption(id="aprobar", label="Aprobar y enviar", kind=OptionKind.APROBAR),
            DecisionOption(id="editar", label="Editar", kind=OptionKind.EDITAR),
        ],
    )


def test_decision_to_spec_valida():
    spec = decision_to_spec(_decision())
    assert spec["type"] == "decision_card"
    assert validate_spec(spec)[0]
    assert spec["risk"] == "medio"
    assert [o["id"] for o in spec["options"]] == ["aprobar", "editar"]


def test_cola_to_spec_valida():
    spec = cola_to_spec([_decision(), _decision()])
    assert spec["type"] == "cola"
    assert validate_spec(spec)[0]
    assert len(spec["items"]) == 2
