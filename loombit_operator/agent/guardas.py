"""
guardas.py — HOOK BLANCO de guardas de dominio pre-intent (D-2).

El núcleo del agente (`loop.py`) NO debe contener lógica de DOMINIO (la brújula: «el dominio vive en
skills/routers, no en el núcleo blanco»). Aquí el núcleo solo ofrece el MECANISMO: un registro de
«guardas» que el DOMINIO aporta (p.ej. `skill_d_fiscal` registra las fiscales: retención, IBAN,
modelos AEAT). El bucle, ANTES del ReAct, consulta el registro; si una guarda aplica, devuelve su
mensaje de abstención honesta y termina — sin que el núcleo sepa nada de IRPF ni de IBAN.

Una guarda = callable `(task: str) -> str | None`: si aplica, devuelve el MENSAJE; si no, None.
"""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)

GuardaDominio = Callable[[str], "str | None"]


class _RegistroGuardas:
    def __init__(self) -> None:
        self._guardas: list[tuple[str, GuardaDominio]] = []

    def register(self, fn: GuardaDominio) -> GuardaDominio:
        """Registra una guarda de dominio (idempotente por nombre de función)."""
        nombre = getattr(fn, "__name__", repr(fn))
        if all(n != nombre for n, _ in self._guardas):
            self._guardas.append((nombre, fn))
        return fn

    def aplicar(self, task: str) -> str | None:
        """Devuelve el mensaje de la PRIMERA guarda que aplica (abstención honesta), o None."""
        for nombre, g in self._guardas:
            try:
                msg = g(task)
            except Exception as exc:  # noqa: BLE001 — una guarda rota no tumba el run
                logger.info("guarda de dominio '%s' falló: %s", nombre, exc)
                msg = None
            if msg:
                return msg
        return None

    def clear(self) -> None:
        self._guardas.clear()

    def __len__(self) -> int:
        return len(self._guardas)


registro_guardas = _RegistroGuardas()
