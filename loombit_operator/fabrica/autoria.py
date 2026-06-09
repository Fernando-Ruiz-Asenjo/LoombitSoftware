"""
autoria.py — redacta una tool nueva con el modelo CODER local (Qwen-Coder), sin tocar pesos.

De una `Necesidad` saca un `BorradorTool` (contrato + código + su propio eval). El prompt lleva
las restricciones de seguridad DENTRO (allowlist, sin red/disco/procesos, autocontenida, trae su
`check(fn)`), porque el arnés rechaza lo que se salte la norma — y el coste de un rechazo es un
reintento con el fallo realimentado (canal de artefactos estilo OpenEvolve), no un fallo silencioso.

Best-effort: si el modelo no está o no devuelve JSON usable, devuelve None (el ciclo lo registra
honestamente, no inventa una tool). La validación de lo que SÍ devuelve la hace `validacion.py`.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .modelos import BorradorTool, Necesidad
from .seguridad import MODULOS_PERMITIDOS

_SISTEMA = (
    "Eres el redactor de herramientas de Loombit (Skill W, núcleo blanco). Te doy una NECESIDAD "
    "real y devuelves UNA tool de Python ÚTIL que la cubra. Responde SOLO con un objeto JSON, sin "
    "texto alrededor, con estas claves exactas: nombre, descripcion, parametros, source, eval_source.\n"
    "REGLAS DURAS (si las incumples, se rechaza):\n"
    "- Cómputo PURO y determinista. Prohibido: red, disco, procesos, entrada de usuario, hora real "
    "no determinista. Solo imports de esta lista: {permitidos}.\n"
    "- `source` define una función de nivel superior llamada igual que `nombre` (snake_case). "
    "Devuelve SIEMPRE un string JSON (json.dumps(..., ensure_ascii=False)).\n"
    "- Las cifras (dinero, fechas, impuestos) se calculan en código exacto; nada de aproximar.\n"
    "- `eval_source` define `def check(fn):` que llama a la función con casos concretos y devuelve "
    "una tupla (bool, str). Debe probar el comportamiento de verdad, no `assert True`.\n"
    "- Código formateado estilo black y limpio para ruff (líneas ≤ 99, sin imports sin usar).\n"
    '- `parametros` es un JSON-schema: {{"type":"object","properties":{{...}},"required":[...]}}.'
)

_EJEMPLO_USER = "NECESIDAD: una tool que cuente los días hábiles (lun-vie) entre dos fechas ISO."
_EJEMPLO_ASSISTANT = json.dumps(
    {
        "nombre": "dias_habiles_entre",
        "descripcion": "Cuenta los días hábiles (lun-vie) entre dos fechas ISO, ambas inclusive.",
        "parametros": {
            "type": "object",
            "properties": {
                "inicio": {"type": "string", "description": "fecha ISO de inicio (YYYY-MM-DD)"},
                "fin": {"type": "string", "description": "fecha ISO de fin (YYYY-MM-DD)"},
            },
            "required": ["inicio", "fin"],
        },
        "source": (
            "import json\n"
            "from datetime import date\n\n\n"
            "def dias_habiles_entre(inicio: str, fin: str) -> str:\n"
            '    """Cuenta los días hábiles (lun-vie) entre dos fechas ISO, ambas inclusive."""\n'
            "    d0 = date.fromisoformat(inicio)\n"
            "    d1 = date.fromisoformat(fin)\n"
            "    if d1 < d0:\n"
            "        d0, d1 = d1, d0\n"
            "    dias = 0\n"
            "    actual = d0\n"
            "    while actual <= d1:\n"
            "        if actual.weekday() < 5:\n"
            "            dias += 1\n"
            "        actual = date.fromordinal(actual.toordinal() + 1)\n"
            '    return json.dumps({"ok": True, "dias_habiles": dias}, ensure_ascii=False)\n'
        ),
        "eval_source": (
            "import json\n\n\n"
            "def check(fn):\n"
            "    # 7 días consecutivos contienen siempre 5 días hábiles.\n"
            '    r = json.loads(fn(inicio="2026-06-01", fin="2026-06-07"))\n'
            '    ok = r.get("ok") is True and r.get("dias_habiles") == 5\n'
            "    return ok, f\"dias_habiles={r.get('dias_habiles')}\"\n"
        ),
    },
    ensure_ascii=False,
)


def _mensajes(necesidad: Necesidad, feedback: str, reglas: str = "") -> list[dict[str, str]]:
    permitidos = ", ".join(sorted(MODULOS_PERMITIDOS))
    sistema = _SISTEMA.format(permitidos=permitidos)
    user = f"NECESIDAD: {necesidad.titulo}\n"
    if necesidad.descripcion:
        user += f"Contexto: {necesidad.descripcion}\n"
    if reglas:  # reglas de autoría aprendidas (playbook ACE), si las hay
        user += f"\n{reglas}\n"
    if feedback:
        user += (
            "\nEl intento anterior FUE RECHAZADO por el validador. Corrige EXACTAMENTE esto y "
            f"vuelve a devolver el JSON completo:\n{feedback}\n"
        )
    return [
        {"role": "system", "content": sistema},
        {"role": "user", "content": _EJEMPLO_USER},
        {"role": "assistant", "content": _EJEMPLO_ASSISTANT},
        {"role": "user", "content": user},
    ]


def _extraer_json(texto: str) -> dict[str, Any] | None:
    """Saca el primer objeto JSON del texto del modelo (tolera fences y prosa alrededor)."""
    if not texto:
        return None
    limpio = re.sub(r"^```(?:json)?|```$", "", texto.strip(), flags=re.MULTILINE).strip()
    inicio = limpio.find("{")
    if inicio < 0:
        return None
    profundidad = 0
    for i in range(inicio, len(limpio)):
        if limpio[i] == "{":
            profundidad += 1
        elif limpio[i] == "}":
            profundidad -= 1
            if profundidad == 0:
                try:
                    return json.loads(limpio[inicio : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _a_borrador(d: dict[str, Any], necesidad: Necesidad) -> BorradorTool | None:
    try:
        return BorradorTool(
            nombre=str(d["nombre"]).strip(),
            descripcion=str(d.get("descripcion", necesidad.titulo)).strip(),
            parametros=dict(d.get("parametros", {})),
            source=str(d.get("source", "")),
            eval_source=str(d.get("eval_source", "")),
            notas=f"redactada para: {necesidad.id}",
        )
    except (KeyError, TypeError, ValueError):
        return None


def redactar(
    necesidad: Necesidad, feedback: str = "", llm: Any = None, playbook: Any = None
) -> BorradorTool | None:
    """Pide al coder una tool para la necesidad. `feedback` realimenta el fallo del arnés del
    intento anterior (auto-reparación). Si se pasa `playbook` (memoria de autoría ACE), inyecta sus
    reglas más relevantes en el prompt. Best-effort: None si el modelo no produce JSON usable."""
    if llm is None:
        try:
            from ..llm import LLMClient

            llm = LLMClient(role="coder")
        except Exception:  # noqa: BLE001 — sin modelo no se inventa nada
            return None
    reglas = ""
    if playbook is not None:
        try:
            reglas = playbook.como_contexto(f"{necesidad.titulo} {necesidad.descripcion}")
        except Exception:  # noqa: BLE001 — el playbook es best-effort; sin él se redacta igual
            reglas = ""
    try:
        resp = llm.chat(
            messages=_mensajes(necesidad, feedback, reglas), temperature=0.2, max_tokens=1800
        )
        texto = (getattr(resp, "content", "") or "").strip()
    except Exception:  # noqa: BLE001
        return None
    d = _extraer_json(texto)
    if not d:
        return None
    return _a_borrador(d, necesidad)
