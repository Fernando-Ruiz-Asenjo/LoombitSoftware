"""
chat.py — el canal para HABLAR con la Fábrica (COGNICIÓN, no extracción).

Dos capas, en orden de precedencia:
1. **Cognición (el 14B lee el hilo):** entiende la intención del mensaje aunque no use la palabra
   clave exacta y extrae los parámetros (qué tema buscar, qué fichero arreglar…). Devuelve un plan
   {accion, slots}. Es lo que pide la brújula: "la regex no destila, el LLM leyendo el hilo sí".
2. **Red de seguridad determinista:** si no hay modelo (LM Studio caído) o el modelo se va por las
   ramas, un router por palabras clave clasifica igual. El chat NUNCA se queda mudo.

Las acciones de listado responden con texto exacto (cifras por código, no inventadas). La conversación
abierta y las explicaciones SÍ las narra el modelo, fundamentadas en el estado real de la Fábrica.
Devuelve {respuesta, accion, datos} para pintarlo en la Sala de la Fábrica. Best-effort: nunca lanza.
"""

from __future__ import annotations

import json
from typing import Any, Callable

# Catálogo de acciones que el chat sabe ejecutar (el LLM elige una de estas, exactamente).
_ACCIONES: dict[str, str] = {
    "estado": "resumen: cuántas propuestas esperan tu gate y cuántos hallazgos nuevos del radar",
    "propuestas": "listar las propuestas de tool pendientes de tu aprobación",
    "oportunidades": "listar los hallazgos que ya trajo el radar",
    "radar": "buscar en la Red sobre un tema (competencia, mercado, tech, normativa). slot: query",
    "proponer_tool": "redactar y validar una tool nueva para una necesidad. slot: descripcion",
    "salud": "analizar la salud del código en uso (bugs, TODO, ficheros grandes, prompts)",
    "monetizacion": "destilar vías de producto/monetización a partir de las señales del radar",
    "ciclo": "correr un ciclo completo de auto-mejora (mira dentro, la Red y meta)",
    "reparar": "proponer un parche validado para un fichero concreto. slots: ref, instruccion",
    "gepa": "optimizar el prompt del agente: reflexiona sobre trazas y VALIDA con evals (gate)",
    "explicar": "explicar qué es la Fábrica, una propuesta, un hallazgo o un concepto. slot: tema",
    "charla": "conversación general, saludo o pregunta abierta sobre la Fábrica",
}


def _tras(m: str, *gatillos: str) -> str:
    """Texto tras el primer gatillo (extrae la query/descripción del mensaje)."""
    for g in gatillos:
        i = m.find(g)
        if i >= 0:
            return m[i + len(g) :].strip(" :.-¿?¡!")
    return ""


def _llm_por_defecto() -> Any:
    """Cliente del instructor (14B), o None si no hay modelo. Lazy, best-effort."""
    try:
        from ..llm import LLMClient

        return LLMClient()
    except Exception:  # noqa: BLE001
        return None


# ── Capa 1: cognición — el modelo entiende la intención ────────────────────────
_SISTEMA_INTENT = (
    "Eres el enrutador COGNITIVO de la Sala de la Fábrica de Loombit (el motor de auto-mejora "
    "gobernada del operador administrativo local). Lee el mensaje del usuario y el historial y decide "
    "qué ACCIÓN pide, de esta lista EXACTA:\n"
    + "\n".join(f"- {k}: {v}" for k, v in _ACCIONES.items())
    + "\nDevuelve SOLO un objeto JSON (sin texto alrededor, sin markdown) con esta forma:\n"
    '{"accion": "<una de la lista>", "query": "", "descripcion": "", "ref": "", '
    '"instruccion": "", "tema": ""}\n'
    "Rellena únicamente los slots que apliquen a la acción (query para radar; descripcion para "
    "proponer_tool; ref+instruccion para reparar; tema para explicar). Si el usuario solo saluda, "
    "charla o hace una pregunta abierta, usa accion=charla. Entiende el SENTIDO aunque no use la "
    "palabra exacta (p. ej. «¿qué hace la competencia X?» → radar con query=X)."
)


def _json_de(txt: str) -> dict[str, Any] | None:
    """Extrae el primer objeto JSON de un texto (el modelo a veces lo envuelve)."""
    i, j = txt.find("{"), txt.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        data = json.loads(txt[i : j + 1])
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def _entender(
    mensaje: str, historial: list[dict[str, Any]] | None, llm: Any
) -> dict[str, Any] | None:
    """El 14B clasifica la intención + extrae slots. None si no hay modelo o no se entiende."""
    if llm is None:
        return None
    msgs: list[dict[str, Any]] = [{"role": "system", "content": _SISTEMA_INTENT}]
    for h in (historial or [])[-6:]:
        rol = "assistant" if h.get("role") in ("a", "assistant") else "user"
        texto = str(h.get("text") or h.get("content") or "")
        if texto:
            msgs.append({"role": rol, "content": texto[:600]})
    msgs.append({"role": "user", "content": mensaje})
    try:
        resp = llm.chat(messages=msgs, max_tokens=160, temperature=0.0)
        data = _json_de(getattr(resp, "content", "") or "")
    except Exception:  # noqa: BLE001
        return None
    if data and data.get("accion") in _ACCIONES:
        return data
    return None


# ── Capa 2: red de seguridad determinista (sin modelo, igual clasifica) ────────
def _router_keywords(m: str, mensaje: str) -> dict[str, Any]:
    if any(
        k in m for k in ("estado", "resumen", "cómo vas", "como vas", "qué tienes", "que tienes")
    ):
        return {"accion": "estado"}
    if any(
        k in m for k in ("busca", "competencia", "competidor", "mercado", "qué hacen", "que hacen")
    ):
        query = (
            _tras(m, "busca", "competidores de", "competencia de", "mercado de", "sobre") or mensaje
        )
        return {"accion": "radar", "query": query}
    if any(k in m for k in ("oportunidad", "hallazgo", "radar", "encontrado", "qué has visto")):
        return {"accion": "oportunidades"}
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
        return {
            "accion": "proponer_tool",
            "descripcion": _tras(m, "tool para", "tool que", "una tool") or mensaje,
        }
    if any(k in m for k in ("propuesta", "qué propones", "que propones", "pendiente")):
        return {"accion": "propuestas"}
    if any(
        k in m
        for k in ("gepa", "mejora el prompt del agente", "optimiza el prompt", "afina el prompt")
    ):
        return {"accion": "gepa"}
    if any(
        k in m
        for k in ("repara", "arregla", "mejora el fichero", "mejora el código", "mejora el codigo")
    ):
        ref = next((t for t in mensaje.split() if "/" in t or t.endswith(".py")), "")
        return {"accion": "reparar", "ref": ref, "instruccion": mensaje}
    if any(k in m for k in ("salud", "marca", "bug", "deuda", "código en uso", "codigo en uso")):
        return {"accion": "salud"}
    if any(
        k in m for k in ("monetiz", "estrategia", "ganar dinero", "negocio", "ingresos", "vías")
    ):
        return {"accion": "monetizacion"}
    if any(k in m for k in ("ciclo", "auto-mejora", "automejora", "barre", "mejórate", "mejorate")):
        return {"accion": "ciclo"}
    if any(
        k in m
        for k in (
            "explica",
            "explícame",
            "explicame",
            "qué es",
            "que es",
            "cómo funciona",
            "como funciona",
        )
    ):
        return {"accion": "explicar", "tema": mensaje}
    return {"accion": "charla"}


# ── Contexto real de la Fábrica (para que la charla/explicación NO invente) ────
def _contexto_fabrica() -> str:
    lineas: list[str] = []
    try:
        from .propuesta import EstadoPropuesta, PropuestaStore

        ps = PropuestaStore()
        pend = ps.list(EstadoPropuesta.PENDIENTE)
        lineas.append(f"Propuestas de tool pendientes de gate: {len(pend)}.")
        for p in pend[:5]:
            lineas.append(f"  · «{p.borrador.nombre}» para: {p.necesidad.titulo}")
    except Exception:  # noqa: BLE001
        pass
    try:
        from .oportunidades import OportunidadStore

        ops = OportunidadStore().list()
        lineas.append(f"Hallazgos del radar guardados: {len(ops)}.")
        for o in ops[:5]:
            lineas.append(
                f"  · {o['necesidad'].get('titulo', '')[:90]} [{o['necesidad'].get('fuente', '')}]"
            )
    except Exception:  # noqa: BLE001
        pass
    return "\n".join(lineas) or "Aún no hay propuestas ni hallazgos guardados."


_SISTEMA_CHARLA = (
    "Eres la Fábrica de Skills de Loombit hablando en primera persona: el motor de auto-mejora "
    "GOBERNADA del operador administrativo local del autónomo/PYME español. Nunca aplicas nada por tu "
    "cuenta: detectas necesidades (dentro: trazas y código; fuera: la Red con cita; meta), redactas "
    "tools y las validas con un arnés de 7 puertas, y se las PROPONES a Fernando para que él apruebe "
    "(el gate es sagrado). También sabes optimizar el prompt del agente con GEPA (reflexión validada "
    "por evals). Responde cálido, claro y BREVE (2-4 frases), en español, sin markdown. Fundaméntate "
    "SOLO en el ESTADO REAL que te paso: no inventes cifras ni capacidades. Si te piden algo "
    "accionable, di la frase exacta que lo dispara (p. ej. «di: corre un ciclo»)."
)


def _narrar(mensaje: str, llm: Any, extra: str = "") -> str:
    """Conversación/explicación fundamentada en el estado real. Best-effort."""
    if llm is None:
        return (
            "Soy la Fábrica. Puedo: «estado», «busca <tema>», «propón una tool para…», «salud del "
            "código», «monetización», «optimiza el prompt» (GEPA) o «corre un ciclo». (El modelo "
            "local no responde ahora, así que voy en modo básico.)"
        )
    contexto = _contexto_fabrica()
    user = f"ESTADO REAL DE LA FÁBRICA:\n{contexto}"
    if extra:
        user += f"\n\nDATO ADICIONAL:\n{extra}"
    user += f"\n\nMENSAJE DEL USUARIO: {mensaje}"
    try:
        resp = llm.chat(
            messages=[
                {"role": "system", "content": _SISTEMA_CHARLA},
                {"role": "user", "content": user},
            ],
            max_tokens=320,
            temperature=0.3,
        )
        return (getattr(resp, "content", "") or "").strip() or _ayuda()["respuesta"]
    except Exception:  # noqa: BLE001
        return _ayuda()["respuesta"]


def _ayuda() -> dict[str, Any]:
    return {
        "accion": "ayuda",
        "respuesta": (
            "Puedo: «estado», «busca <tema>» (mira la competencia/mercado), «propuestas», «propón "
            "una tool para <X>», «salud del código», «monetización», «optimiza el prompt» (GEPA), "
            "«corre un ciclo». También puedo explicarte cualquiera. ¿Qué quieres?"
        ),
        "datos": None,
    }


# ── Handlers de cada acción (cifras por código; el modelo solo narra lo abierto) ─
def _h_estado(intent, mensaje, llm) -> dict[str, Any]:
    from .oportunidades import OportunidadStore
    from .propuesta import EstadoPropuesta, PropuestaStore

    pend = len(PropuestaStore().list(EstadoPropuesta.PENDIENTE))
    ops = OportunidadStore().snapshot()
    return {
        "accion": "estado",
        "respuesta": f"{pend} propuesta(s) de tool pendientes de tu gate · "
        f"{ops.get('nuevas', 0)} hallazgo(s) nuevos del radar (de {ops.get('count', 0)}).",
        "datos": {"propuestas_pendientes": pend, "oportunidades": ops},
    }


def _h_radar(intent, mensaje, llm) -> dict[str, Any]:
    from .oportunidades import OportunidadStore
    from .red import buscar_en_red

    query = (intent.get("query") or "").strip() or mensaje
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


def _h_oportunidades(intent, mensaje, llm) -> dict[str, Any]:
    from .oportunidades import OportunidadStore

    items = OportunidadStore().list()
    return {
        "accion": "oportunidades",
        "respuesta": f"{len(items)} oportunidad(es) en el radar.",
        "datos": [i["necesidad"] for i in items[:20]],
    }


def _h_propuestas(intent, mensaje, llm) -> dict[str, Any]:
    from .propuesta import EstadoPropuesta, PropuestaStore

    props = PropuestaStore().list(EstadoPropuesta.PENDIENTE)
    return {
        "accion": "propuestas",
        "respuesta": f"{len(props)} propuesta(s) de tool esperan tu aprobación.",
        "datos": [
            {"id": p.id, "tool": p.borrador.nombre, "necesidad": p.necesidad.titulo} for p in props
        ],
    }


def _h_proponer_tool(intent, mensaje, llm) -> dict[str, Any]:
    from .ciclo import _atacar_necesidad
    from .modelos import Necesidad, TipoNecesidad
    from .propuesta import EstadoPropuesta, PropuestaStore

    desc = (intent.get("descripcion") or "").strip() or mensaje
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


def _h_salud(intent, mensaje, llm) -> dict[str, Any]:
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


def _h_monetizacion(intent, mensaje, llm) -> dict[str, Any]:
    from .estrategia import sintetizar_estrategia
    from .oportunidades import OportunidadStore

    res = sintetizar_estrategia(OportunidadStore().list(), llm=llm)
    return {"accion": "monetizacion", "respuesta": res.get("resumen", ""), "datos": res}


def _h_ciclo(intent, mensaje, llm) -> dict[str, Any]:
    from .ciclo import ejecutar_ciclo

    inf = ejecutar_ciclo(max_necesidades=2, max_intentos=2, llm=llm)
    t = inf.get("tools", {})
    return {
        "accion": "ciclo",
        "respuesta": f"Ciclo hecho: {len(t.get('propuestas_pendientes_nuevas', []))} tool(s) "
        f"propuesta(s) · {inf.get('hallazgos_red_meta', {}).get('nuevos', 0)} hallazgo(s) nuevos.",
        "datos": inf,
    }


def _h_reparar(intent, mensaje, llm) -> dict[str, Any]:
    from .reparar import proponer_parche

    ref = (intent.get("ref") or "").strip()
    if not ref:
        ref = next((t for t in mensaje.split() if "/" in t or t.endswith(".py")), "")
    if not ref:
        return {
            "accion": "reparar",
            "respuesta": "Dime QUÉ fichero (ruta, p.ej. loombit_operator/agent/prompts.py) y qué mejorar.",
            "datos": None,
        }
    instruccion = (intent.get("instruccion") or "").strip() or (
        "Mejora el prompt/código manteniendo la intención y la API pública."
        if "prompt" in mensaje.lower()
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


def _h_gepa(intent, mensaje, llm) -> dict[str, Any]:
    from .gepa import optimizar_prompt

    res = optimizar_prompt(llm=llm)
    return {"accion": "gepa", "respuesta": res.get("resumen", "GEPA sin resultado."), "datos": res}


def _h_explicar(intent, mensaje, llm) -> dict[str, Any]:
    tema = (intent.get("tema") or "").strip() or mensaje
    return {"accion": "explicar", "respuesta": _narrar(tema, llm), "datos": None}


def _h_charla(intent, mensaje, llm) -> dict[str, Any]:
    return {"accion": "charla", "respuesta": _narrar(mensaje, llm), "datos": None}


_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "estado": _h_estado,
    "radar": _h_radar,
    "oportunidades": _h_oportunidades,
    "propuestas": _h_propuestas,
    "proponer_tool": _h_proponer_tool,
    "salud": _h_salud,
    "monetizacion": _h_monetizacion,
    "ciclo": _h_ciclo,
    "reparar": _h_reparar,
    "gepa": _h_gepa,
    "explicar": _h_explicar,
    "charla": _h_charla,
}


def responder(
    mensaje: str, llm: Any = None, historial: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Punto de entrada del chat. Cognición (14B) con red de seguridad determinista.
    Best-effort: nunca lanza, siempre devuelve {accion, respuesta, datos}."""
    m = (mensaje or "").lower().strip()
    if not m:
        return _ayuda()
    if llm is None:
        llm = _llm_por_defecto()
    # Fast-path: un comando OBVIO se enruta sin gastar una llamada al LLM (instantáneo y no depende
    # de LM Studio). El 14B solo entra a ENTENDER cuando el mensaje no es un comando claro (charla):
    # ahí es donde la cognición aporta (frases naturales que no usan la palabra clave).
    kw = _router_keywords(m, mensaje)
    intent = kw if kw.get("accion") != "charla" else (_entender(mensaje, historial, llm) or kw)
    handler = _HANDLERS.get(str(intent.get("accion")), _h_charla)
    try:
        return handler(intent, mensaje, llm)
    except Exception as exc:  # noqa: BLE001 — el chat nunca rompe; informa con honestidad
        return {"accion": "error", "respuesta": f"No pude completar eso: {exc!r}", "datos": None}
