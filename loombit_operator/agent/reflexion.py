"""
reflexion.py — aprendizaje GENERAL sin fine-tuning (Reflexion, Shinn et al.).

Tras una tarea (sobre todo si falla o se cancela), el modelo reflexiona en lenguaje y extrae
UNA lección general y reutilizable. Es agnóstico al dominio: no sabe si era un correo o una
factura — reflexiona sobre lo que sea que se hizo. La lección se guarda en la memoria y se
recupera por relevancia en tareas futuras. Ver `docs/METODO_INGENIERIA_IA_LOOMBIT.md` (§3).
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_SYS = (
    "Eres el meta-aprendiz de un operador de IA. Te paso el resumen de una tarea recién "
    "ejecutada (con su resultado o error). Devuelve UNA sola lección GENERAL, breve e imperativa, "
    "que ayude a hacerlo mejor la próxima vez (qué hacer o qué evitar). Una frase, sin explicar. "
    "Si no hay nada útil que aprender, responde exactamente: NADA."
)


def reflexionar(run, llm) -> str | None:
    """Devuelve una lección de una frase, o None. Best-effort: cualquier fallo → None."""
    try:
        resp = llm.chat(
            messages=[
                {"role": "system", "content": _SYS},
                {"role": "user", "content": _resumen_run(run)},
            ],
            tools=[],
            tool_choice="none",
        )
        texto = (getattr(resp, "content", "") or "").strip().strip('"').strip()
        if not texto or texto.upper().startswith("NADA") or len(texto) < 8:
            return None
        return texto[:300]
    except Exception:
        logger.debug("reflexion best-effort fallida", exc_info=True)
        return None


def etiquetas_de_tarea(task: str) -> list[str]:
    """Palabras clave de la tarea, para indexar/recuperar la lección por relevancia."""
    return sorted({w for w in re.findall(r"[a-záéíóúñ0-9]+", task.lower()) if len(w) >= 4})[:8]


def _resumen_run(run) -> str:
    estado = getattr(run.status, "value", str(run.status))
    pasos = "; ".join(getattr(s, "tool_name", "?") for s in getattr(run, "steps", [])[:12])
    detalle = (getattr(run, "error", "") or getattr(run, "result", "") or "")[:400]
    return f"Tarea: {run.task}\nEstado: {estado}\nTools usadas: {pasos}\nResultado/error: {detalle}"
