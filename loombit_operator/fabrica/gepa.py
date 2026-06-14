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

La búsqueda mantiene una FRONTERA DE PARETO de candidatos (D-97 · cableado): el siguiente padre a
expandir y la propuesta final se eligen de la frontera (cobertura por instancia), no del "mejor por
media" — así no se atasca en un óptimo local y conserva estrategias complementarias. Los
escenarios/checkers viven en `gepa_escenarios.py`; la matemática de Pareto, en `gepa_pareto.py`
(ambos golden-testeados aparte).

Determinista para tests: `evaluar`, los checkers y el guard se prueban sin LM Studio (stub/objetos).
"""

from __future__ import annotations

import difflib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..config import get_settings
from .gepa_escenarios import Escenario, escenarios_por_defecto
from .gepa_pareto import (
    CandidatoPareto,
    agregado,
    elegir_de_frontera,
    frontera_pareto,
    vector_de,
)

# Anclajes que el prompt candidato DEBE conservar (si los pierde, lo rechazamos: gate de seguridad
# sobre la propia salida de GEPA — no dejamos que la optimización borre las barreras).
_ANCLAS_SEGURIDAD = ("task_done", "gmail_send", "ask_user", "aprob", "{capacidades}", "{fecha_hoy}")


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


# ── Orquestación GEPA (búsqueda sobre la FRONTERA DE PARETO, D-97) ─────────────
def _resultado_sin_mejora(base_score: float, base_det: list[dict[str, Any]]) -> dict[str, Any]:
    """Respuesta honesta cuando no hay una mejora SIN regresión que proponer."""
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


def optimizar_prompt(
    llm: Any = None,
    *,
    plantilla: str | None = None,
    escenarios: list[Escenario] | None = None,
    max_intentos: int = 2,
) -> dict[str, Any]:
    """Corre el bucle GEPA y devuelve {ok, resumen, base_score, mejor_score, fijados, diff, candidato,
    detalle_base, detalle_mejor}. NUNCA escribe el prompt: es una propuesta para aplicar en rama.

    Búsqueda con FRONTERA DE PARETO: cada candidato seguro entra en un POOL con su vector de score por
    instancia; el siguiente padre a expandir y la propuesta final salen de la FRONTERA (cobertura por
    escenario), no del mejor por media. Contrato de seguridad intacto: solo se PROPONE algo que MEJORA
    la media SIN regresión (no rompe ningún escenario que la base ya pasaba).
    """
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

    base_fallos_ids = {d["id"] for d in base_fallos}
    # POOL de la frontera de Pareto. La base es el primer candidato (el que hay que batir).
    pool = [CandidatoPareto("base", vector_de(base_det), plantilla)]
    dets: dict[str, list[dict[str, Any]]] = {"base": base_det}

    for i in range(max_intentos):
        # El PADRE a expandir sale de la frontera, no siempre del mejor por media: así la búsqueda
        # conserva estrategias complementarias en vez de colapsar a un óptimo local (esto es GEPA).
        padre = elegir_de_frontera(pool) or pool[0]
        cand = reflexionar_y_reescribir(
            padre.prompt, [d for d in dets[padre.clave] if not d["ok"]], llm
        )
        if not cand:
            break
        if not candidato_es_seguro(cand)[0]:
            continue  # un candidato que pierde gates o no renderiza se descarta sin piedad
        _cand_score, cand_det = evaluar(_render(cand) or cand, escenarios, llm)
        clave = f"cand{i}"
        pool.append(CandidatoPareto(clave, vector_de(cand_det), cand))
        dets[clave] = cand_det
        if all(d["ok"] for d in cand_det):
            break  # alguien ya es perfecto: no gastes más vueltas del modelo

    # La PROPUESTA final sale de la frontera: mayor cobertura, que MEJORA la media SIN regresión.
    candidatos = [
        c
        for c in frontera_pareto(pool)
        if c.clave != "base"
        and agregado(c.vector) > base_score
        and {d["id"] for d in dets[c.clave] if not d["ok"]} <= base_fallos_ids
    ]
    elegido = elegir_de_frontera(candidatos) if candidatos else None
    if elegido is None:
        return _resultado_sin_mejora(base_score, base_det)

    mejor = elegido.prompt
    mejor_score = agregado(elegido.vector)
    mejor_det = dets[elegido.clave]
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
