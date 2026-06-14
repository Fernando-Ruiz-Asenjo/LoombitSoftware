"""
pilot/browser_driver.py — Capa de DRIVING del adaptador de navegador (Playwright/CDP).

Conduce Chrome de verdad SOBRE el núcleo gobernado de `browser.py` (D-93): a11y-first, allowlist
cerrada por defecto y **GATE humano ANTES de los pasos consecuentes** (pago/compra/envío) — aquí el
gate se ENFORZA en ejecución (no solo se marca): ante un paso consecuente no aprobado, PARA y devuelve
`pendiente_aprobacion`, no ejecuta el pago. Recibo local. El LLM PROPONE la secuencia; este código DISPONE.

Playwright es dependencia OPCIONAL (import perezoso, como pypdf en docs_intel): el módulo importa y se
testea SIN Playwright (se inyecta un `page` falso). El driving REAL contra Chrome queda **🟡 hasta
verificarse EN VIVO** (`pip install playwright && playwright install chromium`) — frontera declarada (D-94).

Click ACCESSIBILITY-first: clic por rol+nombre (Playwright `get_by_role`), no por XPaths frágiles ni
coordenadas — robusto a cambios de layout (estilo Skyvern/AgentOccam, misma filosofía que el UIA de escritorio).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .browser import ElementoA11y, dominio_permitido, parse_a11y, validar_secuencia


def _aplanar(nodo: Any, out: list[dict] | None = None) -> list[dict]:
    """Aplana el árbol de accesibilidad (`page.accessibility.snapshot()`) a una lista de nodos
    accionables (con rol y nombre). Determinista, sin red."""
    out = out if out is not None else []
    if isinstance(nodo, dict):
        if nodo.get("role") and nodo.get("name"):
            out.append(
                {"role": nodo.get("role"), "name": nodo.get("name"), "value": nodo.get("value", "")}
            )
        for hijo in nodo.get("children", []) or []:
            _aplanar(hijo, out)
    return out


class BrowserDriver:
    """Conduce el navegador respetando el núcleo gobernado. `page` inyectable (tests sin Playwright)."""

    def __init__(
        self,
        allowlist: list[str],
        page: Any = None,
        headless: bool = True,
        receipt_dir: str | Path | None = None,
    ) -> None:
        self._allowlist = list(allowlist or [])
        self._page: Any = page
        self._headless = headless
        self._receipt_dir = Path(receipt_dir) if receipt_dir else None
        self._pw: Any = None
        self._browser: Any = None

    def _page_or_launch(self) -> Any:
        if self._page is None:
            from playwright.sync_api import sync_playwright  # dep OPCIONAL, perezosa

            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=self._headless)
            self._page = self._browser.new_page()
        return self._page

    def snapshot_a11y(self) -> list[ElementoA11y]:
        snap = self._page_or_launch().accessibility.snapshot() or {}
        return parse_a11y(_aplanar(snap))

    def _navegar(self, url: str) -> dict:
        if not dominio_permitido(url, self._allowlist):
            return {"ok": False, "error": f"dominio fuera de la allowlist: {url}"}
        self._page_or_launch().goto(url)
        return {"ok": True, "url": url}

    def _click_por_rol(self, rol: str, nombre: str) -> dict:
        self._page_or_launch().get_by_role(rol, name=nombre).click()
        return {"ok": True, "click": nombre}

    def _type(self, texto: str) -> dict:
        self._page_or_launch().keyboard.type(texto)
        return {"ok": True, "typed_len": len(texto)}

    def ejecutar(self, steps: list[dict], aprobaciones: set[int] | None = None) -> dict:
        """Ejecuta la secuencia respetando el gobierno: valida (allowlist/pasos) y, en cada paso
        CONSECUENTE no aprobado, PARA y devuelve `pendiente_aprobacion` (NO ejecuta el pago)."""
        aprobaciones = aprobaciones or set()
        plan = validar_secuencia(steps, self._allowlist)
        resultados: list[dict] = []
        if not plan.ok:
            return {"ok": False, "motivo": "secuencia bloqueada", "plan": plan.to_dict()}
        for i, step in enumerate(steps):
            if i in plan.requieren_gate and i not in aprobaciones:
                return {
                    "ok": False,
                    "pendiente_aprobacion": i,
                    "paso": step,
                    "plan": plan.to_dict(),
                    "resultados": resultados,
                }
            resultados.append({"i": i, **self._dispatch(step)})
        return {"ok": True, "resultados": resultados, "recibo": self._recibo(steps, resultados)}

    def _dispatch(self, step: dict) -> dict:
        t = step.get("type")
        if t == "navigate":
            return self._navegar(step.get("url", ""))
        if t == "a11y_snapshot":
            return {"ok": True, "elementos": [e.__dict__ for e in self.snapshot_a11y()]}
        if t == "click_element":
            return self._click_por_rol(
                step.get("rol", step.get("role", "button")),
                step.get("nombre", step.get("name", "")),
            )
        if t == "type_text":
            return self._type(step.get("text", step.get("texto", "")))
        if t == "wait":
            return {"ok": True, "wait": True}
        return {"ok": True, "noop": t}

    def _recibo(self, steps: list[dict], resultados: list[dict]) -> str | None:
        if not self._receipt_dir:
            return None
        self._receipt_dir.mkdir(parents=True, exist_ok=True)
        rid = uuid4().hex[:8]
        path = self._receipt_dir / f"browser_{rid}.json"
        path.write_text(
            json.dumps(
                {
                    "run_id": rid,
                    "at": datetime.now(UTC).isoformat(),
                    "pasos": len(steps),
                    "resultados": resultados,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return str(path)

    def close(self) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
