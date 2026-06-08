"""
pilot_demo.py — demostración visible del Pilot: cartel "LOOMBIT PILOTANDO" + mueve el cursor real
+ abre la página de Google Console (publicar la app OAuth).

Uso: python scripts/pilot_demo.py
"""

from __future__ import annotations

import ctypes
import math
import sys
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loombit_operator.pilot.input_control import mouse_move  # noqa: E402
from loombit_operator.pilot.overlay import PilotOverlay  # noqa: E402

GOOGLE_CONSENT = "https://console.cloud.google.com/apis/credentials/consent"


def main() -> None:
    print("Pilot: mostrando cartel 'LOOMBIT PILOTANDO'...")
    overlay = PilotOverlay("LOOMBIT PILOTANDO").start()
    time.sleep(0.8)

    user32 = ctypes.windll.user32
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    cx, cy = sw // 2, sh // 2

    print("Pilot: moviendo el cursor (lo verás dar dos vueltas)...")
    for i in range(0, 720, 7):
        a = math.radians(i)
        mouse_move(int(cx + 320 * math.cos(a)), int(cy + 200 * math.sin(a)))
        time.sleep(0.012)
    mouse_move(cx, cy)

    print("Pilot: abriendo Google Console (pantalla de consentimiento OAuth)...")
    webbrowser.open(GOOGLE_CONSENT)

    time.sleep(3.5)
    overlay.stop()
    print(
        "Pilot: demo terminada. En Google Console: 'Publicar app' para que no vuelva a pedirte acceso."
    )


if __name__ == "__main__":
    main()
