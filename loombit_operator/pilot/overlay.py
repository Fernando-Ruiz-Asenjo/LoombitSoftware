"""
overlay.py — Skill W Pilot: cartel visible "LOOMBIT PILOTANDO" mientras el Pilot controla la pantalla.

Transparencia: cuando Loombit toma el control del escritorio, el usuario lo VE (banner siempre
encima). Corre en su propio hilo (tkinter) para no bloquear las acciones del Pilot.
"""

from __future__ import annotations

import threading


class PilotOverlay:
    """Banner frameless, siempre encima, que indica que el Pilot está actuando."""

    def __init__(self, texto: str = "LOOMBIT PILOTANDO") -> None:
        self.texto = texto
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> "PilotOverlay":
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            import tkinter as tk
        except Exception:
            return
        try:
            root = tk.Tk()
            root.overrideredirect(True)  # sin barra de título
            root.attributes("-topmost", True)
            try:
                root.attributes("-alpha", 0.92)
            except Exception:
                pass
            root.configure(bg="#0d1b2a")
            sw = root.winfo_screenwidth()
            root.geometry(f"400x66+{sw // 2 - 200}+18")
            tk.Label(
                root,
                text="🟢  " + self.texto,
                fg="#00d2af",
                bg="#0d1b2a",
                font=("Segoe UI", 18, "bold"),
            ).pack(expand=True, fill="both")

            def _tick() -> None:
                if self._stop.is_set():
                    root.destroy()
                    return
                root.after(100, _tick)

            root.after(100, _tick)
            root.mainloop()
        except Exception:
            return
