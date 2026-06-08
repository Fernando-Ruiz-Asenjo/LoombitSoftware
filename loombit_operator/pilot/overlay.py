"""
overlay.py — Skill W Pilot: señal visible y propia de Loombit mientras el Pilot controla la pantalla.

Transparencia (innegociable): cuando Loombit toma el control del escritorio el usuario lo VE,
y lo ve con la **identidad de Loombit**, no con la de otra herramienta. Tres capas, todas en los
colores de marca (violeta #8b5cf6 → cian #06b6d4, los del `static/index.html`):

  1. **Halo de perímetro**: marco degradado violeta→cian pegado al borde del monitor.
  2. **Halo de cursor**: anillo que sigue al ratón (deja el cursor real visible en el centro).
  3. **Cartel** "LOOMBIT PILOTANDO" arriba.

Todo es *click-through* (WS_EX_TRANSPARENT): el halo nunca bloquea ni los clics del propio Pilot
ni los del usuario. Corre en su hilo (tkinter) para no bloquear las acciones del Pilot.
"""

from __future__ import annotations

import ctypes
import sys
import threading

# ── Colores de marca Loombit (de static/index.html) ──
CYAN = "#06b6d4"
BLUE = "#3b82f6"
PURPLE = "#8b5cf6"
PURPLE_BRIGHT = "#a78bfa"
NAVY = "#0b0f1a"
# Color-clave: los píxeles exactamente de este color se vuelven transparentes y click-through.
TRANSP = "#010101"


def _lerp(c1: str, c2: str, t: float) -> str:
    """Interpola dos colores hex `#rrggbb` (t en [0,1]) → `#rrggbb`."""
    a = (int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16))
    b = (int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16))
    r = tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))
    return "#%02x%02x%02x" % r


def _gradient(n: int, c1: str, c2: str) -> list[str]:
    """`n` colores que van de `c1` a `c2`."""
    if n <= 1:
        return [c1]
    return [_lerp(c1, c2, i / (n - 1)) for i in range(n)]


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _cursor_xy() -> tuple[int, int]:
    pt = _POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _make_click_through(win: "object") -> None:
    """Hace la ventana topmost click-through y sin activarse (Windows). No-op fuera de Windows."""
    if not sys.platform.startswith("win"):
        return
    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_NOACTIVATE = 0x08000000
    try:
        win.update_idletasks()  # type: ignore[attr-defined]
        user32 = ctypes.windll.user32
        # GA_ROOT = 2: el HWND real de la ventana de nivel superior (overrideredirect no tiene wrapper).
        hwnd = user32.GetAncestor(win.winfo_id(), 2) or win.winfo_id()  # type: ignore[attr-defined]
        styles = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        styles |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, styles)
    except Exception:
        pass


class PilotOverlay:
    """Señal visible de marca Loombit: halo de perímetro + halo de cursor + cartel."""

    CURSOR_D = 72  # diámetro de la ventana del halo de cursor
    BAND = 10  # nº de líneas del marco de perímetro (≈ BAND*3 px de grosor)

    def __init__(
        self,
        texto: str = "LOOMBIT PILOTANDO",
        *,
        perimetro: bool = True,
        cursor: bool = True,
        cartel: bool = True,
    ) -> None:
        self.texto = texto
        self.perimetro = perimetro
        self.cursor = cursor
        self.cartel = cartel
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._should_stop = None  # callback opcional; True → cerrar (para run_blocking)

    def start(self) -> "PilotOverlay":
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def run_blocking(self, should_stop=None) -> None:
        """Corre el overlay en el HILO ACTUAL (robusto: tkinter pinta de forma fiable
        en su hilo principal). `should_stop()` → True cierra. Para el proceso del overlay."""
        self._should_stop = should_stop
        self._run()

    def stop(self) -> None:
        self._stop.set()

    # ── interno ──

    def _run(self) -> None:
        try:
            import tkinter as tk
        except Exception:
            return
        # Alinear el espacio de coordenadas del overlay con el del Pilot (píxeles reales).
        try:
            from loombit_operator.pilot.system import enable_dpi_awareness

            enable_dpi_awareness()
        except Exception:
            pass
        try:
            root = tk.Tk()
            root.withdraw()  # la raíz es invisible; cada capa es un Toplevel.

            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()

            cursor_win = None
            if self.perimetro:
                self._build_perimeter(tk, root, sw, sh)
            if self.cartel:
                self._build_banner(tk, root, sw)
            if self.cursor:
                cursor_win = self._build_cursor(tk, root)

            def _follow() -> None:
                if self._stop.is_set() or (self._should_stop is not None and self._should_stop()):
                    root.destroy()
                    return
                if cursor_win is not None:
                    try:
                        x, y = _cursor_xy()
                        d = self.CURSOR_D
                        cursor_win.geometry(f"{d}x{d}+{x - d // 2}+{y - d // 2}")
                    except Exception:
                        pass
                root.after(16, _follow)

            root.after(16, _follow)
            root.mainloop()
        except Exception:
            return

    def _build_perimeter(self, tk: "object", root: "object", sw: int, sh: int) -> None:
        win = tk.Toplevel(root)  # type: ignore[attr-defined]
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"{sw}x{sh}+0+0")
        win.configure(bg=TRANSP)
        try:
            win.attributes("-transparentcolor", TRANSP)
        except Exception:
            pass
        cv = tk.Canvas(win, width=sw, height=sh, bg=TRANSP, highlightthickness=0, bd=0)  # type: ignore[attr-defined]
        cv.pack(fill="both", expand=True)
        # Marco degradado: cian en el borde → violeta hacia dentro.
        for i, color in enumerate(_gradient(self.BAND, CYAN, PURPLE_BRIGHT)):
            inset = i * 3 + 1
            cv.create_rectangle(inset, inset, sw - inset, sh - inset, outline=color, width=3)
        _make_click_through(win)

    def _build_banner(self, tk: "object", root: "object", sw: int) -> None:
        win = tk.Toplevel(root)  # type: ignore[attr-defined]
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"360x52+{sw // 2 - 180}+16")
        win.configure(bg=PURPLE)  # el fondo violeta hace de borde de 2px
        inner = tk.Frame(win, bg=NAVY)  # type: ignore[attr-defined]
        inner.pack(fill="both", expand=True, padx=2, pady=2)
        tk.Label(  # type: ignore[attr-defined]
            inner,
            text="●  " + self.texto,
            fg=PURPLE_BRIGHT,
            bg=NAVY,
            font=("Segoe UI", 16, "bold"),
        ).pack(expand=True, fill="both")
        _make_click_through(win)

    def _build_cursor(self, tk: "object", root: "object") -> "object":
        d = self.CURSOR_D
        win = tk.Toplevel(root)  # type: ignore[attr-defined]
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"{d}x{d}+0+0")
        win.configure(bg=TRANSP)
        try:
            win.attributes("-transparentcolor", TRANSP)
        except Exception:
            pass
        cv = tk.Canvas(win, width=d, height=d, bg=TRANSP, highlightthickness=0, bd=0)  # type: ignore[attr-defined]
        cv.pack(fill="both", expand=True)
        # Anillos concéntricos; el centro queda transparente → se ve el cursor real.
        cv.create_oval(3, 3, d - 3, d - 3, outline=CYAN, width=3)
        cv.create_oval(13, 13, d - 13, d - 13, outline=BLUE, width=3)
        cv.create_oval(23, 23, d - 23, d - 23, outline=PURPLE_BRIGHT, width=3)
        _make_click_through(win)
        return win
