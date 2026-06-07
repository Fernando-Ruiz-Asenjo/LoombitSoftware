"""
Skill W Loombit Pilot — control local genérico del equipo.

Expone primitivas reutilizables de ejecución:
  screen.py         — captura de pantalla
  input_control.py  — ratón y teclado (pynput)
  windows_control.py— foco de ventana + UI Automation (pywinauto / ctypes)
  executor.py       — motor de secuencias con recibos auditables

No contiene lógica de dominio vertical. Es una Skill W: cualquier Skill D
(administrative, coding, industrial…) puede importar este módulo.
"""

from .system import enable_dpi_awareness

# Al importar el Pilot se activa la conciencia de DPI: captura y clic deben
# referirse a los mismos píxeles reales. Idempotente y no-op fuera de Windows.
enable_dpi_awareness()
