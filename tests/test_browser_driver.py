"""
Driving del adaptador de navegador (pilot/browser_driver.py).

Golden DETERMINISTA con un `page` FALSO inyectado (sin Playwright ni Chrome real): verifica que el
GATE se ENFORZA en ejecución (un paso consecuente sin aprobar PARA, no ejecuta el pago), que la
allowlist bloquea dominios y que el snapshot del árbol de accesibilidad se aplana. El driving real
contra Chrome es 🟡 hasta verificarse en vivo (D-94).
"""

from __future__ import annotations

from loombit_operator.pilot.browser_driver import BrowserDriver, _aplanar


class _FakeLocator:
    def __init__(self, registro: list) -> None:
        self._registro = registro

    def click(self) -> None:
        self._registro.append("click")


class _FakeAccessibility:
    def __init__(self, snap: dict) -> None:
        self._snap = snap

    def snapshot(self) -> dict:
        return self._snap


class _FakeKeyboard:
    def __init__(self, registro: list) -> None:
        self._registro = registro

    def type(self, texto: str) -> None:
        self._registro.append(("type", texto))


class _FakePage:
    """Navegador falso: registra lo que se le pide, sin tocar red ni Chrome."""

    def __init__(self, snap: dict | None = None) -> None:
        self.acciones: list = []
        self.accessibility = _FakeAccessibility(snap or {})
        self.keyboard = _FakeKeyboard(self.acciones)

    def goto(self, url: str) -> None:
        self.acciones.append(("goto", url))

    def get_by_role(self, rol: str, name: str = "") -> _FakeLocator:
        self.acciones.append(("get_by_role", rol, name))
        return _FakeLocator(self.acciones)


def _driver(snap: dict | None = None) -> tuple[BrowserDriver, _FakePage]:
    page = _FakePage(snap)
    return BrowserDriver(allowlist=["iberia.com"], page=page), page


# ── El GATE se enforza en ejecución ───────────────────────────────────────────


def test_paso_de_pago_para_sin_aprobacion():
    d, page = _driver()
    steps = [
        {"type": "navigate", "url": "https://iberia.com/es"},
        {"type": "click_element", "rol": "button", "nombre": "Pagar y reservar"},
    ]
    r = d.ejecutar(steps)  # sin aprobaciones
    assert r["ok"] is False and r["pendiente_aprobacion"] == 1
    # CLAVE: el pago NO se ejecutó (no hubo click).
    assert "click" not in page.acciones
    assert ("goto", "https://iberia.com/es") in page.acciones  # el navigate sí (no consecuente)


def test_con_aprobacion_ejecuta_el_pago():
    d, page = _driver()
    steps = [
        {"type": "navigate", "url": "https://iberia.com/es"},
        {"type": "click_element", "rol": "button", "nombre": "Pagar y reservar"},
    ]
    r = d.ejecutar(steps, aprobaciones={1})
    assert r["ok"] is True
    assert "click" in page.acciones  # con el OK humano, el pago se ejecuta


# ── Allowlist bloquea dominios ────────────────────────────────────────────────


def test_dominio_fuera_de_allowlist_bloquea_la_secuencia():
    d, page = _driver()
    r = d.ejecutar([{"type": "navigate", "url": "https://evil.com/x"}])
    assert r["ok"] is False and r["motivo"] == "secuencia bloqueada"
    assert page.acciones == []  # ni siquiera intentó navegar


# ── a11y snapshot se aplana ───────────────────────────────────────────────────


def test_aplanar_arbol_de_accesibilidad():
    snap = {
        "role": "WebArea",
        "name": "Iberia",
        "children": [
            {"role": "textbox", "name": "Origen"},
            {"role": "group", "children": [{"role": "button", "name": "Buscar vuelos"}]},
        ],
    }
    planos = _aplanar(snap)
    nombres = {n["name"] for n in planos}
    assert "Origen" in nombres and "Buscar vuelos" in nombres


def test_snapshot_devuelve_elementos_indexados():
    snap = {"role": "WebArea", "name": "x", "children": [{"role": "button", "name": "Buscar"}]}
    d, _ = _driver(snap)
    els = d.snapshot_a11y()
    assert els and els[-1].nombre == "Buscar" and els[-1].rol == "button"
