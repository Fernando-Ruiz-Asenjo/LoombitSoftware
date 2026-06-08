"""Configuración compartida de la suite.

Apaga la señal visible del Pilot (halo tkinter) durante los tests: los tests que
ejercitan los endpoints `/computer-use/*` de acción no deben abrir ventanas reales.
El test del propio gestor reactiva la lógica con monkeypatch.
"""

import os

os.environ.setdefault("LOOMBIT_PILOT_OVERLAY_OFF", "1")
