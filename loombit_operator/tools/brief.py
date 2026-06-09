"""
Tools de PERCEPCIÓN del día — el "resumen de hoy" desde el chat.

Hasta ahora el brief solo vivía en el daemon (proactivo programado). Estas tools lo
hacen invocable desde la conversación, reutilizando EXACTAMENTE el mismo cerebro de
señales reales (`routine_executors._señales_reales`), para que el chat y el daemon
digan lo mismo. Son lectura pura: no envían nada, no requieren aprobación.

Regla de oro: las cifras (cuántos correos, cuánto se debe, qué eventos) las calcula
el CÓDIGO de forma determinista; el LLM solo las narra. Si el LLM no está disponible,
se devuelve un resumen determinista en viñetas (sigue siendo útil y honesto).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .registry import ToolDefinition, tool_registry


def _fmt_evento(ev: dict[str, Any]) -> str:
    if ev.get("all_day"):
        return f"{ev['summary']} (todo el día)"
    hora = str(ev.get("start", ""))[11:16]  # HH:MM de un dateTime ISO
    return f"{hora} {ev['summary']}".strip()


def _señales_del_dia(now: datetime | None = None) -> list[str]:
    """Señales REALES de hoy (deterministas): el mismo cerebro del brief del daemon,
    que ya incluye agenda + correos sin leer + aprobaciones + cuentas a cobrar."""
    try:
        from ..routine_executors import _señales_reales

        return _señales_reales(now=now)
    except TypeError:
        # Compatibilidad si _señales_reales aún no acepta `now`.
        from ..routine_executors import _señales_reales

        return _señales_reales()
    except Exception:
        return []


def _narrar(señales: list[str]) -> str:
    """Redacta el brief en 3-4 líneas. Si el LLM no está, cae a viñetas deterministas."""
    contexto = "; ".join(señales) if señales else "sin señales conectadas hoy"
    try:
        from ..llm import LLMClient
        from ..routine_executors import _BRIEF_SYSTEM

        messages = [
            {"role": "system", "content": _BRIEF_SYSTEM},
            {
                "role": "user",
                "content": (
                    "Hazme el resumen de hoy con foco recomendado.\n\n"
                    f"DATOS REALES DE HOY (no añadas nada más): {contexto}."
                ),
            },
        ]
        texto = LLMClient().chat(messages, max_tokens=250).content.strip()
        if texto:
            return texto
    except Exception:
        pass
    # Fallback determinista (sin modelo): viñetas honestas con lo que hay.
    if not señales:
        return "Hoy no tengo señales conectadas (calendario/correo/cobros) que reportar."
    return "Resumen de hoy:\n" + "\n".join(f"• {s}" for s in señales)


def _daily_brief(**_: object) -> str:
    """Resumen del día: agenda + correos por responder + aprobaciones + cobros que vencen.
    Acepta y descarta cualquier argumento (el modelo a veces pasa alguno de más)."""
    return _narrar(_señales_del_dia())


def _calendar_today(**_: object) -> str:
    """Lista, en texto, los eventos de hoy del calendario. Tolera args extra del modelo."""
    try:
        from ..skill_blanca_calendar_read import eventos_de_hoy

        eventos = eventos_de_hoy()
    except ValueError as exc:
        if "no_token" in str(exc):
            return "Tu Google Calendar no está conectado. Conéctalo para que pueda ver tu agenda."
        if "unauthorized" in str(exc):
            return "El acceso a tu calendario ha caducado. Vuelve a conectar Google."
        return f"No pude leer el calendario ({exc})."
    except Exception as exc:  # noqa: BLE001
        return f"No pude leer el calendario ({exc})."

    if not eventos:
        return "No tienes eventos en el calendario para hoy."
    return "Hoy en tu agenda:\n" + "\n".join(f"• {_fmt_evento(e)}" for e in eventos)


# ── Registro ──────────────────────────────────────────────────────────────────

tool_registry.register(
    ToolDefinition(
        name="daily_brief",
        description=(
            "Resumen del día con foco recomendado: junta tu agenda de hoy, los correos "
            "sin responder de tus contactos, las aprobaciones pendientes y las cuentas a "
            "cobrar que vencen. Úsala cuando el usuario pida un resumen, qué tiene hoy, en "
            "qué centrarse o cómo va el día. Solo lectura."
        ),
        parameters={"type": "object", "properties": {}},
        fn=_daily_brief,
        category="connector",
    )
)

tool_registry.register(
    ToolDefinition(
        name="calendar_today",
        description=(
            "Lee los eventos de HOY del calendario de Google (solo lectura). Úsala cuando "
            "el usuario pregunte qué tiene hoy, su agenda o sus citas del día."
        ),
        parameters={"type": "object", "properties": {}},
        fn=_calendar_today,
        category="connector",
    )
)
