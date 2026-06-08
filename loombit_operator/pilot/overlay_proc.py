"""
overlay_proc.py — proceso dedicado del halo de marca del Pilot.

El servidor (uvicorn) no puede pintar tkinter de forma fiable desde un hilo de
trabajo, así que la señal visible corre en SU PROPIO proceso, donde el overlay
vive en el hilo principal. El servidor enciende este proceso y va "refrescando"
un fichero keepalive en cada acción del Pilot; cuando el keepalive caduca
(el agente dejó de actuar) este proceso se cierra solo y el halo desaparece.

Uso:  python -m loombit_operator.pilot.overlay_proc <keepalive_path> <idle_seconds> [texto]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from loombit_operator.pilot.overlay import PilotOverlay
from loombit_operator.pilot.system import enable_dpi_awareness


def main() -> None:
    keepalive = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    idle = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    texto = sys.argv[3] if len(sys.argv) > 3 else "LOOMBIT PILOTANDO"

    enable_dpi_awareness()

    def _stale() -> bool:
        # Cierra si el keepalive desapareció o lleva > idle segundos sin refrescarse.
        if keepalive is None:
            return False
        try:
            return (time.time() - keepalive.stat().st_mtime) > idle
        except OSError:
            return True

    PilotOverlay(texto).run_blocking(should_stop=_stale)


if __name__ == "__main__":
    main()
