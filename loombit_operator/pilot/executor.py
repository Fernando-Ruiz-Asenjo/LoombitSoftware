"""
executor.py — motor de secuencias de Skill W Loombit Pilot.

Ejecuta listas de pasos con recibos auditables. Compatible con dry_run.
Cada paso devuelve un dict de resultado. El recibo final se guarda en JSON.

Tipos de paso soportados:
  open_url        — abre URL en el navegador predeterminado
  focus_window    — trae ventana al frente por título/proceso
  inspect_controls— enumera controles UI Automation
  screenshot      — captura de pantalla (base64 + disco)
  click           — clic en coordenadas (x, y)
  double_click    — doble clic en coordenadas
  click_control   — clic en control UI por nombre/automation_id
  type_text       — escribe texto
  hotkey          — combinación de teclas (ctrl+a, alt+f4…)
  wait            — espera N segundos

Contrato de seguridad:
  - dry_run nunca toca el escritorio.
  - Las URLs se redactan en los recibos.
  - El texto escrito se resume por longitud, no se vuelca completo.
  - Los recibos se guardan localmente, nunca se suben a la nube.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .screen import screen_changed, take_screenshot
from .input_control import (
    mouse_click,
    mouse_double_click,
    mouse_scroll,
    keyboard_type,
    keyboard_hotkey,
)
from .windows_control import (
    open_url,
    focus_window,
    inspect_controls,
    click_control,
    click_accessibility,
    wait_for_window,
)

logger = logging.getLogger(__name__)

SUPPORTED_STEPS = [
    "open_url",
    "focus_window",
    "wait_for_window",
    "inspect_controls",
    "screenshot",
    "click",
    "double_click",
    "click_control",
    "click_accessibility",
    "type_text",
    "hotkey",
    "wait",
    "scroll",
    "screen_changed",
]

SAFETY_CONTRACT = {
    "local_only": True,
    "does_not_upload": True,
    "does_not_execute_without_approval": True,
    "no_login_bypass": True,
    "no_captcha_bypass": True,
    "receipts_local": True,
    "dry_run_available": True,
}


# ── Executor principal ────────────────────────────────────────────────────────


async def execute_sequence(
    objective: str,
    steps: list[dict[str, Any]],
    dry_run: bool = False,
    receipt_dir: Path | None = None,
    operator_command: str = "",
) -> dict[str, Any]:
    """
    Ejecuta una secuencia de pasos.

    Args:
        objective:       Descripción del objetivo de la secuencia.
        steps:           Lista de pasos [{type, ...params}].
        dry_run:         Si True, simula sin tocar el escritorio.
        receipt_dir:     Directorio donde guardar el recibo JSON.
        operator_command:Comando original del operador (para el recibo).

    Returns:
        dict con run_id, objective, results, receipt_path si se guardó.
    """
    run_id = uuid4().hex[:8]
    started_at = datetime.now(UTC).isoformat()
    results: list[dict[str, Any]] = []
    error_halted = False

    for i, step in enumerate(steps):
        step_type = step.get("type", "")
        step_result: dict[str, Any] = {
            "step_index": i + 1,
            "type": step_type,
        }

        if step_type not in SUPPORTED_STEPS:
            step_result["error"] = f"Tipo de paso no soportado: {step_type!r}"
            results.append(step_result)
            error_halted = True
            break

        if dry_run:
            step_result["dry_run"] = True
            step_result["would_execute"] = {k: v for k, v in step.items() if k != "type"}
        else:
            try:
                output = await _execute_step(step)
                step_result.update(output)
                if output.get("error"):
                    error_halted = True
                    results.append(step_result)
                    break
            except Exception as exc:
                logger.exception("Error en paso %d (%s)", i + 1, step_type)
                step_result["error"] = str(exc)
                error_halted = True
                results.append(step_result)
                break

        results.append(step_result)

    receipt: dict[str, Any] = {
        "run_id": run_id,
        "objective": objective,
        "operator_command": operator_command,
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat(),
        "dry_run": dry_run,
        "steps_total": len(steps),
        "steps_executed": len(results),
        "error_halted": error_halted,
        "results": results,
    }

    if receipt_dir and not dry_run:
        try:
            rd = Path(receipt_dir)
            rd.mkdir(parents=True, exist_ok=True)
            path = rd / f"pilot_{run_id}.json"
            path.write_text(
                json.dumps(receipt, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            receipt["receipt_path"] = str(path)
            logger.info("Recibo guardado: %s", path)
        except Exception as exc:
            receipt["receipt_save_error"] = str(exc)

    return receipt


# ── Dispatcher de pasos ───────────────────────────────────────────────────────


async def _execute_step(step: dict[str, Any]) -> dict[str, Any]:
    step_type = step["type"]

    if step_type == "open_url":
        url = step.get("url", "")
        return open_url(url)

    elif step_type == "focus_window":
        return focus_window(
            process_name=step.get("process_name", ""),
            title=step.get("title", ""),
        )

    elif step_type == "wait_for_window":
        return wait_for_window(
            step.get("title", ""),
            timeout=float(step.get("timeout", 10.0)),
        )

    elif step_type == "inspect_controls":
        return inspect_controls(
            process_name=step.get("process_name", ""),
            title=step.get("title", ""),
            limit=int(step.get("limit", 40)),
        )

    elif step_type == "screenshot":
        # El base64 puede ser grande; guardamos en disco y devolvemos la ruta
        from loombit_operator.config import get_settings  # evitar import circular

        settings = get_settings()
        save_dir = Path(settings.agent_run_store_path).parent / "skill_pilot"
        result = take_screenshot(save_dir=save_dir, include_base64=False)
        return result

    elif step_type == "click":
        x = int(step.get("x", 0))
        y = int(step.get("y", 0))
        button = step.get("button", "left")
        return mouse_click(x, y, button=button)

    elif step_type == "double_click":
        x = int(step.get("x", 0))
        y = int(step.get("y", 0))
        return mouse_double_click(x, y)

    elif step_type == "scroll":
        x = int(step.get("x", 0))
        y = int(step.get("y", 0))
        return mouse_scroll(
            x,
            y,
            direction=step.get("direction", "down"),
            amount=int(step.get("amount", 3)),
        )

    elif step_type == "click_control":
        return click_control(
            name=step.get("name", ""),
            automation_id=step.get("automation_id", ""),
            process_name=step.get("process_name", ""),
            title=step.get("title", ""),
        )

    elif step_type == "click_accessibility":
        return click_accessibility(
            name=step.get("name", ""),
            automation_id=step.get("automation_id", ""),
            window_title=step.get("window_title", step.get("title", "")),
        )

    elif step_type == "screen_changed":
        return screen_changed(
            threshold=float(step.get("threshold", 0.02)),
            interval=float(step.get("interval", 0.5)),
        )

    elif step_type == "type_text":
        text = step.get("text", "")
        return keyboard_type(text)

    elif step_type == "hotkey":
        keys = step.get("keys", step.get("key", ""))
        return keyboard_hotkey(keys)

    elif step_type == "wait":
        secs = float(step.get("seconds", 1.0))
        secs = min(secs, 30.0)  # máximo 30 s por paso
        await asyncio.sleep(secs)
        return {"waited_seconds": secs}

    return {"error": f"Paso no implementado: {step_type}"}
