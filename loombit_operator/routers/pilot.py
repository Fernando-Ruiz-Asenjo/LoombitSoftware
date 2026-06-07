"""
Router Skill W Loombit Pilot — control local genérico del equipo.

Expone:
  GET  /loombit/pilot/capabilities   — lista de pasos, contrato de seguridad
  POST /loombit/pilot/execute        — ejecuta una secuencia de pasos

Estado: 🟠 Parcial
  - screenshot, click, type_text, hotkey, wait → reales vía pynput + Pillow
  - focus_window, inspect_controls, click_control → reales si pywinauto instalado
  - open_url → real vía webbrowser

  Pendiente (🟢 requiere ejecución real + recibo):
  - Verificar focus_window en Chrome con pywinauto
  - Verificar inspect_controls enumera controles de Chrome
  - Escribir recibo de secuencia completa en runtime/local/skill_pilot/
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from loombit_operator.pilot.executor import (
    SAFETY_CONTRACT,
    SUPPORTED_STEPS,
    execute_sequence,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/loombit/pilot", tags=["pilot"])


# ── Modelos ───────────────────────────────────────────────────────────────────


class PilotStep(BaseModel):
    type: str
    # Parámetros opcionales según el tipo de paso
    url: str | None = None
    process_name: str | None = None
    title: str | None = None
    limit: int | None = None
    x: int | None = None
    y: int | None = None
    button: str = "left"
    name: str | None = None
    automation_id: str | None = None
    text: str | None = None
    keys: str | None = None
    key: str | None = None
    seconds: float | None = None
    direction: str | None = None
    amount: int | None = None


class PilotExecuteRequest(BaseModel):
    objective: str = Field(..., description="Descripción del objetivo de la secuencia.")
    steps: list[PilotStep] = Field(..., description="Lista de pasos a ejecutar.")
    dry_run: bool = Field(False, description="Si true, simula sin tocar el escritorio.")
    operator_command: str = Field("", description="Comando original del operador.")


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/capabilities")
async def get_capabilities() -> dict[str, Any]:
    """Lista de pasos soportados y contrato de seguridad."""
    return {
        "skill": "Skill W Loombit Pilot",
        "version": "0.2.0",
        "status": "🟠 parcial",
        "supported_steps": SUPPORTED_STEPS,
        "safety_contract": SAFETY_CONTRACT,
        "operating_hierarchy": [
            "1. API directa (Gmail, Calendar, Graph…) cuando disponible.",
            "2. Browser semantic adapter (Playwright / CDP) — próximo.",
            "3. Windows UI Automation (pywinauto) — disponible si instalado.",
            "4. Coordenadas ratón/teclado (pynput) — siempre disponible.",
        ],
        "requires": {
            "always": ["pillow", "pynput"],
            "ui_automation": ["pywinauto", "psutil"],
            "win32_fallback": ["pywin32"],
        },
    }


@router.post("/execute")
async def pilot_execute(body: PilotExecuteRequest) -> dict[str, Any]:
    """
    Ejecuta una secuencia de pasos de control local.

    El operador debe proporcionar `objective` y `steps`. Con `dry_run: true`
    la secuencia se valida pero no toca el escritorio.

    Cada paso devuelve un resultado. Si un paso falla, la secuencia se detiene
    y el campo `error_halted` es true en el recibo.
    """
    if not body.steps:
        raise HTTPException(status_code=400, detail="La secuencia de pasos está vacía.")

    # Convertir modelos Pydantic a dicts para el executor
    steps_raw = [s.model_dump(exclude_none=True) for s in body.steps]

    # Directorio de recibos
    try:
        from loombit_operator.config import get_settings

        settings = get_settings()
        receipt_dir = Path(settings.agent_run_store_path).parent / "skill_pilot"
    except Exception:
        receipt_dir = Path("runtime/local/skill_pilot")

    receipt = await execute_sequence(
        objective=body.objective,
        steps=steps_raw,
        dry_run=body.dry_run,
        receipt_dir=receipt_dir,
        operator_command=body.operator_command,
    )

    return receipt
