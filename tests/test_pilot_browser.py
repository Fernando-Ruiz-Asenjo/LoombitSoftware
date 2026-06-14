"""
Núcleo gobernado del adaptador de navegador del Pilot (pilot/browser.py).

Golden DETERMINISTA (sin red, sin navegador): la allowlist de dominios (cerrada por defecto), el
marcado de pasos CONSECUENTES (pago/compra/envío → gate humano antes de ejecutar) y el parseo del
árbol de accesibilidad. El driving Playwright/CDP queda fuera (frontera 🟠 declarada en D-93).
"""

from __future__ import annotations

from loombit_operator.pilot.browser import (
    SAFETY_CONTRACT,
    ElementoA11y,
    dominio_permitido,
    es_paso_consecuente,
    parse_a11y,
    validar_secuencia,
)

# ── Allowlist de dominios: cerrada por defecto ────────────────────────────────


def test_dominio_permitido_acepta_dominio_y_subdominios():
    allow = ["iberia.com"]
    assert dominio_permitido("https://www.iberia.com/es/vuelos", allow) is True
    assert dominio_permitido("https://iberia.com", allow) is True


def test_dominio_no_permitido_se_bloquea():
    assert dominio_permitido("https://evil.com/pago", ["iberia.com"]) is False


def test_sin_allowlist_se_bloquea_todo():
    # CERRADO por defecto: el navegador no navega a cualquier sitio.
    assert dominio_permitido("https://iberia.com", []) is False


# ── Pasos consecuentes → gate humano antes de ejecutar ────────────────────────


def test_pagar_es_consecuente():
    assert es_paso_consecuente({"type": "click_element", "nombre": "Pagar 250 €"}) is True
    assert es_paso_consecuente({"type": "click_element", "name": "Comprar billetes"}) is True
    assert es_paso_consecuente({"type": "navigate", "url": "https://iberia.com/checkout"}) is True


def test_buscar_no_es_consecuente():
    assert es_paso_consecuente({"type": "click_element", "nombre": "Buscar vuelos"}) is False
    assert es_paso_consecuente({"type": "a11y_snapshot"}) is False


# ── Validación de la secuencia entera ─────────────────────────────────────────


def test_validar_secuencia_bloquea_dominio_y_marca_pago():
    steps = [
        {"type": "navigate", "url": "https://www.iberia.com/es/vuelos"},  # 0 ok
        {"type": "navigate", "url": "https://evil.com/track"},  # 1 fuera de allowlist
        {"type": "a11y_snapshot"},  # 2 ok
        {"type": "click_element", "nombre": "Pagar y reservar"},  # 3 consecuente → gate
    ]
    plan = validar_secuencia(steps, allowlist=["iberia.com"])
    assert plan.ok is False  # hay un dominio bloqueado
    assert any(b["i"] == 1 for b in plan.bloqueados)
    assert 3 in plan.requieren_gate  # el pago exige aprobación humana


def test_validar_secuencia_paso_no_soportado_se_bloquea():
    plan = validar_secuencia([{"type": "borrar_disco"}], allowlist=["iberia.com"])
    assert plan.ok is False and plan.bloqueados


def test_secuencia_limpia_pasa_sin_gate():
    steps = [
        {"type": "navigate", "url": "https://iberia.com/es"},
        {"type": "a11y_snapshot"},
        {"type": "click_element", "nombre": "Buscar vuelos"},
    ]
    plan = validar_secuencia(steps, allowlist=["iberia.com"])
    assert plan.ok is True and plan.requieren_gate == []


# ── Árbol de accesibilidad (a11y-first) ───────────────────────────────────────


def test_parse_a11y_indexa_elementos():
    snap = [
        {"role": "textbox", "name": "Origen"},
        {"role": "button", "name": "Buscar vuelos"},
    ]
    els = parse_a11y(snap)
    assert len(els) == 2
    assert isinstance(els[0], ElementoA11y)
    assert els[1].idx == 1 and els[1].rol == "button" and els[1].nombre == "Buscar vuelos"


# ── Contrato de seguridad presente ────────────────────────────────────────────


def test_contrato_seguridad_no_ejecuta_sin_aprobacion():
    assert SAFETY_CONTRACT["does_not_execute_without_approval"] is True
    assert SAFETY_CONTRACT["domain_allowlist"] is True
    assert SAFETY_CONTRACT["local_only"] is True
