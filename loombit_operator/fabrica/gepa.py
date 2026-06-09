"""
gepa.py — GEPA real: optimiza el PROMPT del agente reflexionando sobre trazas y VALIDÁNDOLO con evals.

No es "marcar": es el bucle reflexivo (Reflective Prompt Evolution, estilo GEPA) adaptado y SEGURO
para Loombit:
  1. Puntúa el prompt ACTUAL contra un eval de COMPORTAMIENTO derivado de la taxonomía de fallos
     reales F1-F8 (una vuelta del modelo con tools; ¿llama a la tool correcta?, ¿no pregunta el
     asunto?, ¿no inventa el destinatario?, ¿es proactivo?…).
  2. REFLEXIONA sobre los escenarios fallados + lecciones de trazas y propone una EDICIÓN del prompt
     (instructor 14B), conservando intención y gates.
  3. Re-puntúa el candidato con el MISMO eval.
  4. Si mejora SIN regresión y conserva los anclajes de seguridad, lo emite como PROPUESTA con su
     diff y sus scores. **NUNCA escribe**: el humano lo aplica en una rama (gate sagrado · andamiaje,
     no pesos). Sin modelo, sin señales o sin mejora, lo dice con honestidad.

Determinista para tests: `evaluar`, los checkers y el guard se prueban sin LM Studio (stub/objetos).
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from ..config import get_settings

# El correo lo firma el usuario; el agente NO se delata como IA/bot (F4). Reusa el guard del loop.
try:
    from ..agent.loop import _DELATA_BOT
except Exception:  # noqa: BLE001 — si el loop no carga, un patrón mínimo de respaldo
    import re as _re

    _DELATA_BOT = _re.compile(r"soy (un|una) (agente|asistente|bot|ia)|agente aut[oó]nomo", _re.I)

# Anclajes que el prompt candidato DEBE conservar (si los pierde, lo rechazamos: gate de seguridad
# sobre la propia salida de GEPA — no dejamos que la optimización borre las barreras).
_ANCLAS_SEGURIDAD = ("task_done", "gmail_send", "ask_user", "aprob", "{capacidades}", "{fecha_hoy}")


# ── Escenarios de comportamiento (prompt-sensibles, derivados de F1-F8) ────────
@dataclass
class Escenario:
    """Un caso de UNA vuelta: dado el prompt como sistema + `user`, ¿el modelo actúa bien?"""

    id: str
    taxon: str
    user: str
    espera: Callable[[Any], tuple[bool, str]]  # (ChatResponse) -> (ok, nota)
    desc: str = ""


def _primera_tool(resp: Any) -> Any:
    tcs = getattr(resp, "tool_calls", None) or []
    return tcs[0] if tcs else None


def _check_redacta_correo(resp: Any) -> tuple[bool, str]:
    """F1/F7/F4: con email explícito, redacta asunto+cuerpo y envía; no pregunta, no se delata."""
    tc = _primera_tool(resp)
    if tc is None:
        return False, "no llamó a ninguna tool (¿se quedó preguntando?)"
    if tc.tool_name == "ask_user":
        return False, "preguntó en vez de redactar el correo (F1)"
    if tc.tool_name != "gmail_send":
        return False, f"llamó a {tc.tool_name} en vez de gmail_send"
    subj = str(tc.arguments.get("subject", "")).strip()
    body = str(tc.arguments.get("body", "")).strip()
    if len(subj) < 4 or subj.lower() in ("asunto", "mensaje", "presentación automática"):
        return False, "asunto vacío/genérico (F7)"
    if len(body) < 20 or "\\n" in body:
        return False, "cuerpo trivial o con '\\n' literal (F7)"
    if _DELATA_BOT.search(body):
        return False, "el correo se delata como bot (F4)"
    return True, "redactó asunto+cuerpo y envía"


def _check_no_inventa_destinatario(resp: Any) -> tuple[bool, str]:
    """F2: solo un NOMBRE (sin email) → resuelve con contacts_find o pregunta; NUNCA inventa el to."""
    tc = _primera_tool(resp)
    if tc is None:
        return False, "no actuó"
    if tc.tool_name in ("contacts_find", "ask_user", "gmail_search"):
        return True, f"resolvió/pidió el destinatario ({tc.tool_name})"
    if tc.tool_name == "gmail_send":
        return False, f"envió a un destinatario sin resolver: {tc.arguments.get('to', '?')} (F2)"
    return False, f"hizo algo inesperado: {tc.tool_name}"


def _check_proactivo_brief(resp: Any) -> tuple[bool, str]:
    """Proactividad: 'en qué me centro hoy' → daily_brief/calendar_today, no devolver la pelota."""
    tc = _primera_tool(resp)
    if tc is None:
        return False, "no actuó (¿preguntó?)"
    if tc.tool_name in ("daily_brief", "calendar_today", "gmail_search"):
        return True, f"fue proactivo ({tc.tool_name})"
    return False, f"no usó el brief: {tc.tool_name}"


def _check_busca_en_bandeja(resp: Any) -> tuple[bool, str]:
    """No preguntar lo que se puede leer: '¿cuándo quedé con David?' → gmail_search, no ask_user."""
    tc = _primera_tool(resp)
    if tc is None:
        return False, "no actuó"
    if tc.tool_name in ("gmail_search", "daily_brief", "calendar_today"):
        return True, f"buscó en la bandeja ({tc.tool_name})"
    if tc.tool_name == "ask_user":
        return False, "preguntó algo que podía leer en la bandeja"
    return False, f"hizo algo inesperado: {tc.tool_name}"


def _check_agenda_evento(resp: Any) -> tuple[bool, str]:
    """Calendario: 'agéndame café con Luis mañana a las 10' → calendar_create, sin pedir trivialidades."""
    tc = _primera_tool(resp)
    if tc is None:
        return False, "no actuó"
    if tc.tool_name in ("calendar_create", "contacts_find"):
        return True, f"avanzó hacia el evento ({tc.tool_name})"
    if tc.tool_name == "ask_user":
        return False, "preguntó en vez de preparar el evento"
    return False, f"hizo algo inesperado: {tc.tool_name}"


def escenarios_por_defecto() -> list[Escenario]:
    """El eval de comportamiento del prompt: casos prompt-sensibles que curan fallos reales."""
    return [
        Escenario(
            "redacta_correo",
            "F1",
            "Manda un correo a ana@ejemplo.com confirmándole que asistiré a la reunión del martes.",
            _check_redacta_correo,
            "Con email explícito, redacta y envía (no pregunta el asunto, no se delata como bot).",
        ),
        Escenario(
            "no_inventa_destinatario",
            "F2",
            "Envía un correo a Marta diciéndole que el informe ya está listo.",
            _check_no_inventa_destinatario,
            "Solo un nombre: resuelve el email, no lo inventa.",
        ),
        Escenario(
            "proactivo_brief",
            "PROACT",
            "¿En qué me centro hoy?",
            _check_proactivo_brief,
            "Petición de alto nivel: prepara el brief, no devuelve la pelota.",
        ),
        Escenario(
            "busca_en_bandeja",
            "F-LEER",
            "¿Cuándo quedé con David para la visita?",
            _check_busca_en_bandeja,
            "No preguntes lo que puedes leer en la bandeja.",
        ),
        Escenario(
            "agenda_evento",
            "F-CAL",
            "Agéndame un café con Luis mañana a las 10:00.",
            _check_agenda_evento,
            "Prepara el evento sin pedir trivialidades.",
        ),
    ]


# ── Evaluación: puntúa un prompt contra los escenarios (una vuelta del modelo) ──
def _tools_para(user: str) -> list[dict[str, Any]] | None:
    try:
        from ..tools import tool_registry

        return tool_registry.to_openai(task=user)
    except Exception:  # noqa: BLE001
        return None


def evaluar(
    prompt: str, escenarios: list[Escenario], llm: Any
) -> tuple[float, list[dict[str, Any]]]:
    """Puntúa el prompt: para cada escenario, una vuelta del modelo con tools y su checker.
    Devuelve (score 0..1, detalle por escenario). Best-effort: un escenario que peta cuenta fallo.
    """
    detalle: list[dict[str, Any]] = []
    oks = 0
    for esc in escenarios:
        try:
            resp = llm.chat(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": esc.user},
                ],
                tools=_tools_para(esc.user),
                tool_choice="auto",
                temperature=0.0,
                max_tokens=320,
            )
            ok, nota = esc.espera(resp)
        except Exception as exc:  # noqa: BLE001
            ok, nota = False, f"error evaluando: {exc!r}"
        oks += 1 if ok else 0
        detalle.append({"id": esc.id, "taxon": esc.taxon, "ok": ok, "nota": nota})
    score = oks / len(escenarios) if escenarios else 0.0
    return score, detalle


# ── Reflexión → reescritura del prompt (el instructor propone la edición) ──────
_SISTEMA_REFLEXION = (
    "Eres el optimizador de prompts del agente de Loombit (operador administrativo local). Te paso el "
    "PROMPT-PLANTILLA actual del agente, los ESCENARIOS que aún falla (con qué se esperaba y qué hizo "
    "mal) y LECCIONES de trazas reales. Reescribe la plantilla COMPLETA para corregir esos fallos, con "
    "estas reglas DURAS:\n"
    "- Conserva LITERALMENTE los marcadores entre llaves: {fecha_hoy}, {rol_descripcion}, "
    "{dominio_ejemplos}, {capacidades}. No introduzcas otras llaves.\n"
    "- Conserva TODOS los gates de seguridad y la intención; solo AFINA las instrucciones que causan "
    "los fallos (sé más claro/imperativo donde el modelo falla).\n"
    "- No la alargues en exceso; edición quirúrgica, no reescritura cosmética.\n"
    "Devuelve SOLO el texto de la nueva plantilla, sin comillas ni markdown ni explicación."
)


def _lecciones_de_trazas(limite: int = 8) -> list[str]:
    try:
        from ..agent.memory import get_memory

        mem = get_memory()
        lessons = [str(getattr(le, "lesson", le)) for le in getattr(mem, "lessons", [])[:limite]]
        return [le for le in lessons if le]
    except Exception:  # noqa: BLE001
        return []


def _limpiar_plantilla(texto: str) -> str:
    t = (texto or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip("`").strip()


def reflexionar_y_reescribir(plantilla: str, fallos: list[dict[str, Any]], llm: Any) -> str | None:
    """Pide al instructor una plantilla mejorada que cure los `fallos`. None si no produce algo usable."""
    if not fallos:
        return None
    lineas_fallo = "\n".join(f"- [{f['taxon']}] {f['id']}: {f['nota']}" for f in fallos)
    lecciones = _lecciones_de_trazas()
    bloque_lecc = (
        ("\nLECCIONES DE TRAZAS:\n" + "\n".join(f"- {le}" for le in lecciones)) if lecciones else ""
    )
    user = (
        f"PROMPT-PLANTILLA ACTUAL:\n{plantilla}\n\n"
        f"ESCENARIOS FALLADOS:\n{lineas_fallo}{bloque_lecc}"
    )
    try:
        resp = llm.chat(
            messages=[
                {"role": "system", "content": _SISTEMA_REFLEXION},
                {"role": "user", "content": user},
            ],
            temperature=0.4,
            max_tokens=1600,
        )
        cand = _limpiar_plantilla(getattr(resp, "content", "") or "")
    except Exception:  # noqa: BLE001
        return None
    return cand or None


# ── Guards sobre el candidato (la optimización no puede romper la seguridad) ───
def _render(plantilla: str) -> str | None:
    """Renderiza la plantilla como lo hace build_system_prompt (perfil administrativo). None si rompe."""
    try:
        from ..agent.prompts import _PROFILES
        from ..tool_labels import capability_block

        fecha = datetime.now(UTC).strftime("%A, %d de %B de %Y")
        return plantilla.format(
            fecha_hoy=fecha, capacidades=capability_block(), **_PROFILES["administrativo"]
        )
    except (KeyError, IndexError, ValueError):
        return None
    except Exception:  # noqa: BLE001
        return None


def candidato_es_seguro(plantilla: str) -> tuple[bool, str]:
    """Rechaza un candidato que pierda anclajes de seguridad, no renderice o crezca desmesuradamente."""
    for ancla in _ANCLAS_SEGURIDAD:
        if ancla not in plantilla:
            return False, f"perdió el anclaje obligatorio: {ancla!r}"
    if _render(plantilla) is None:
        return False, "la plantilla no renderiza (llaves rotas)"
    return True, "conserva los anclajes y renderiza"


# ── Persistencia del último resultado (para que la Sala lo muestre) ────────────
def _ruta_ultimo() -> Path:
    return get_settings().agent_run_store_path.parent / "gepa_ultimo.json"


def _guardar_ultimo(res: dict[str, Any]) -> None:
    try:
        ruta = _ruta_ultimo()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def ultimo_resultado() -> dict[str, Any] | None:
    try:
        return json.loads(_ruta_ultimo().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


# ── Orquestación GEPA ──────────────────────────────────────────────────────────
def optimizar_prompt(
    llm: Any = None,
    *,
    plantilla: str | None = None,
    escenarios: list[Escenario] | None = None,
    max_intentos: int = 2,
) -> dict[str, Any]:
    """Corre el bucle GEPA y devuelve {ok, resumen, base_score, mejor_score, fijados, diff, candidato,
    detalle_base, detalle_mejor}. NUNCA escribe el prompt: es una propuesta para aplicar en rama."""
    if llm is None:
        try:
            from ..llm import LLMClient

            llm = LLMClient()
        except Exception:  # noqa: BLE001
            return {"ok": False, "resumen": "Modelo no disponible para GEPA."}

    if plantilla is None:
        from ..agent.prompts import _BASE_PROMPT

        plantilla = _BASE_PROMPT
    escenarios = escenarios or escenarios_por_defecto()

    base_score, base_det = evaluar(_render(plantilla) or plantilla, escenarios, llm)
    base_fallos = [d for d in base_det if not d["ok"]]
    if not base_fallos:
        res = {
            "ok": True,
            "resumen": f"El prompt ya pasa los {len(escenarios)} escenarios de comportamiento "
            f"({int(base_score * 100)}%). No propongo cambios.",
            "base_score": base_score,
            "mejor_score": base_score,
            "fijados": [],
            "diff": "",
            "candidato": "",
            "detalle_base": base_det,
        }
        _guardar_ultimo(res)
        return res

    mejor = plantilla
    mejor_score = base_score
    mejor_det = base_det
    base_fallos_ids = {d["id"] for d in base_fallos}

    for _ in range(max_intentos):
        cand = reflexionar_y_reescribir(mejor, [d for d in mejor_det if not d["ok"]], llm)
        if not cand:
            break
        seguro, _motivo = candidato_es_seguro(cand)
        if not seguro:
            continue  # un candidato que pierde gates o no renderiza se descarta sin piedad
        cand_score, cand_det = evaluar(_render(cand) or cand, escenarios, llm)
        cand_fallos_ids = {d["id"] for d in cand_det if not d["ok"]}
        # Acepta solo si MEJORA y NO regresiona (no rompe ninguno que antes pasaba).
        if cand_score > mejor_score and cand_fallos_ids <= base_fallos_ids:
            mejor, mejor_score, mejor_det = cand, cand_score, cand_det
            if cand_score >= 1.0:
                break

    if mejor is plantilla or mejor_score <= base_score:
        res = {
            "ok": False,
            "resumen": f"No encontré una mejora SIN regresión (base {int(base_score * 100)}%). "
            "No propongo cambios: mejor no tocar que empeorar.",
            "base_score": base_score,
            "mejor_score": base_score,
            "fijados": [],
            "diff": "",
            "candidato": "",
            "detalle_base": base_det,
        }
        _guardar_ultimo(res)
        return res

    fijados = sorted(base_fallos_ids - {d["id"] for d in mejor_det if not d["ok"]})
    diff = "".join(
        difflib.unified_diff(
            plantilla.splitlines(keepends=True),
            mejor.splitlines(keepends=True),
            fromfile="agent/prompts.py::_BASE_PROMPT (actual)",
            tofile="agent/prompts.py::_BASE_PROMPT (propuesto)",
        )
    )
    res = {
        "ok": True,
        "resumen": f"Mejora validada: {int(base_score * 100)}% → {int(mejor_score * 100)}% "
        f"de los escenarios. Fija {', '.join(fijados) or '—'}. Revisa el diff y aplícalo en una rama "
        "(no he escrito nada).",
        "base_score": base_score,
        "mejor_score": mejor_score,
        "fijados": fijados,
        "diff": diff,
        "candidato": mejor,
        "detalle_base": base_det,
        "detalle_mejor": mejor_det,
    }
    _guardar_ultimo(res)
    return res
