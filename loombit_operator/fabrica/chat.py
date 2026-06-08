"""
chat.py — el canal para HABLAR con la Fábrica en lenguaje natural.

Enruta el mensaje a una acción (determinista por palabras clave — robusto, sin depender del LLM para
decidir): estado, oportunidades, buscar en la Red, propuestas, proponer una tool, salud del código,
monetización, correr un ciclo, ayuda. Las acciones que crean (tool, monetización) sí usan el modelo.
Devuelve {respuesta, accion, datos} para pintarlo en la Sala de la Fábrica.
"""

from __future__ import annotations

from typing import Any


def _tras(m: str, *gatillos: str) -> str:
    """Texto tras el primer gatillo (para extraer la query/descripción del mensaje)."""
    for g in gatillos:
        i = m.find(g)
        if i >= 0:
            return m[i + len(g) :].strip(" :.-")
    return ""


def _ayuda() -> dict[str, Any]:
    return {
        "accion": "ayuda",
        "respuesta": (
            "Puedo: «estado», «oportunidades», «busca <tema>» (mira la competencia/mercado), "
            "«propuestas», «propón una tool para <X>», «salud del código», «monetización», "
            "«corre un ciclo». ¿Qué quieres?"
        ),
        "datos": None,
    }


def responder(mensaje: str, llm: Any = None) -> dict[str, Any]:
    """Punto de entrada del chat. Best-effort: nunca lanza, siempre devuelve una respuesta."""
    m = (mensaje or "").lower().strip()
    if not m:
        return _ayuda()

    try:
        # ── Estado / resumen ──────────────────────────────────────────────────
        if any(
            k in m
            for k in ("estado", "resumen", "cómo vas", "como vas", "qué tienes", "que tienes")
        ):
            from .oportunidades import OportunidadStore
            from .propuesta import EstadoPropuesta, PropuestaStore

            ps = PropuestaStore()
            pend = len(ps.list(EstadoPropuesta.PENDIENTE))
            ops = OportunidadStore().snapshot()
            return {
                "accion": "estado",
                "respuesta": f"{pend} propuesta(s) de tool pendientes de tu gate · "
                f"{ops.get('nuevas', 0)} hallazgo(s) nuevos del radar.",
                "datos": {"propuestas_pendientes": pend, "oportunidades": ops},
            }

        # ── Buscar en la Red (competencia/mercado) ───────────────────────────
        if any(
            k in m
            for k in ("busca", "competencia", "competidor", "mercado", "qué hacen", "que hacen")
        ):
            from .oportunidades import OportunidadStore
            from .red import buscar_en_red

            query = (
                _tras(m, "busca", "competidores de", "competencia de", "mercado de", "sobre")
                or mensaje
            )
            hallazgos = buscar_en_red(query)
            OportunidadStore().registrar(hallazgos)
            return {
                "accion": "radar",
                "respuesta": f"Miré la Red sobre «{query[:60]}»: {len(hallazgos)} hallazgo(s), con cita.",
                "datos": [
                    {"titulo": h.titulo, "url": h.procedencia[0] if h.procedencia else ""}
                    for h in hallazgos
                ],
            }

        # ── Oportunidades (lo que ya trajo el radar) ─────────────────────────
        if any(k in m for k in ("oportunidad", "hallazgo", "radar", "encontrado", "qué has visto")):
            from .oportunidades import OportunidadStore

            items = OportunidadStore().list()
            return {
                "accion": "oportunidades",
                "respuesta": f"{len(items)} oportunidad(es) en el radar.",
                "datos": [i["necesidad"] for i in items[:20]],
            }

        # ── Propuestas de tool pendientes ────────────────────────────────────
        if any(k in m for k in ("propuesta", "qué propones", "que propones", "pendiente")):
            from .propuesta import EstadoPropuesta, PropuestaStore

            props = PropuestaStore().list(EstadoPropuesta.PENDIENTE)
            return {
                "accion": "propuestas",
                "respuesta": f"{len(props)} propuesta(s) de tool esperan tu aprobación.",
                "datos": [
                    {"id": p.id, "tool": p.borrador.nombre, "necesidad": p.necesidad.titulo}
                    for p in props
                ],
            }

        # ── Proponer una tool para algo concreto ─────────────────────────────
        if any(
            k in m
            for k in (
                "propón una tool",
                "propon una tool",
                "crea una tool",
                "necesito una tool",
                "haz una tool",
            )
        ):
            from .ciclo import _atacar_necesidad
            from .modelos import Necesidad, TipoNecesidad
            from .propuesta import EstadoPropuesta, PropuestaStore

            desc = _tras(m, "tool para", "tool que", "una tool") or mensaje
            nec = Necesidad(titulo=desc, tipo=TipoNecesidad.TOOL, descripcion=mensaje)
            prop, detalle = _atacar_necesidad(nec, max_intentos=3, llm=llm)
            if prop and prop.estado == EstadoPropuesta.PENDIENTE:
                PropuestaStore().add(prop)
                return {
                    "accion": "proponer_tool",
                    "respuesta": f"Redacté y validé la tool «{prop.borrador.nombre}» (7/7 puertas). "
                    "Está en propuestas, espera tu gate.",
                    "datos": {"id": prop.id, "tool": prop.borrador.nombre},
                }
            return {
                "accion": "proponer_tool",
                "respuesta": "El coder no produjo una tool que pase el arnés (no cuelo chorradas). "
                f"Detalle: {detalle.get('estado')}.",
                "datos": detalle,
            }

        # ── Salud del código (marcar) ────────────────────────────────────────
        if any(k in m for k in ("salud", "marca", "código", "codigo", "bug", "error", "deuda")):
            from .interno import marcar

            necs = marcar()
            return {
                "accion": "salud",
                "respuesta": f"Marqué {len(necs)} señal(es) en el código en uso (bugs/TODO/ficheros grandes/prompts).",
                "datos": [
                    {
                        "titulo": n.titulo,
                        "tipo": n.tipo.value,
                        "ref": n.procedencia[0] if n.procedencia else "",
                    }
                    for n in necs[:20]
                ],
            }

        # ── Monetización / estrategia ────────────────────────────────────────
        if any(
            k in m for k in ("monetiz", "estrategia", "ganar dinero", "negocio", "ingresos", "vías")
        ):
            from .estrategia import sintetizar_estrategia
            from .oportunidades import OportunidadStore

            res = sintetizar_estrategia(OportunidadStore().list(), llm=llm)
            return {"accion": "monetizacion", "respuesta": res.get("resumen", ""), "datos": res}

        # ── Correr un ciclo completo (heavy) ─────────────────────────────────
        if any(
            k in m for k in ("ciclo", "auto-mejora", "automejora", "barre", "mejórate", "mejorate")
        ):
            from .ciclo import ejecutar_ciclo

            inf = ejecutar_ciclo(max_necesidades=2, max_intentos=2)
            t = inf.get("tools", {})
            return {
                "accion": "ciclo",
                "respuesta": f"Ciclo hecho: {len(t.get('propuestas_pendientes_nuevas', []))} tool(s) "
                f"propuesta(s) · {inf.get('hallazgos_red_meta', {}).get('nuevos', 0)} hallazgo(s) nuevos.",
                "datos": inf,
            }

        # ── Reparar / mejorar un fichero o prompt (GEPA-lite, validado) ──────
        if any(
            k in m
            for k in (
                "repara",
                "arregla",
                "mejora el prompt",
                "mejora el fichero",
                "mejora el código",
            )
        ):
            from .reparar import proponer_parche

            ref = next((t for t in mensaje.split() if "/" in t or t.endswith(".py")), "")
            if not ref:
                return {
                    "accion": "reparar",
                    "respuesta": "Dime QUÉ fichero (ruta, p.ej. loombit_operator/agent/prompts.py) y qué mejorar.",
                    "datos": None,
                }
            instruccion = (
                "Mejora el prompt/código manteniendo la intención y la API pública."
                if "prompt" in m
                else mensaje
            )
            res = proponer_parche(ref, instruccion, llm=llm, validar_tests=True)
            if res is None:
                return {
                    "accion": "reparar",
                    "respuesta": "El coder no produjo un parche usable.",
                    "datos": None,
                }
            estado = (
                "validado (estático + API + tests)"
                if res.get("ok")
                else f"RECHAZADO: {res.get('validacion')}"
            )
            return {
                "accion": "reparar",
                "respuesta": f"Parche para {ref}: {estado}. No he escrito nada — revisa el diff y aplícalo en rama.",
                "datos": res,
            }

        return _ayuda()
    except Exception as exc:  # noqa: BLE001 — el chat nunca rompe; informa con honestidad
        return {"accion": "error", "respuesta": f"No pude completar eso: {exc!r}", "datos": None}
