"""
ui_spec.py — LD-1 de «Loombit Decide»: UI generativa GOBERNADA (el contrato).

§GOB-1 aplicado a la PANTALLA. La UI generativa del mercado deja al LLM emitir componentes React o
HTML crudo — eso metería al LLM en el camino de control (XSS/inyección): la Ley Fundacional lo
prohíbe. Aquí la honestidad es la misma que en el plano de autoridad:

    El LLM PROPONE una *spec* de interfaz desde un vocabulario CERRADO.
    El CÓDIGO la VALIDA (este módulo) y la RINDE (static/loombit-render.js, con textContent).

Este módulo es la **superficie de validación**: la whitelist de componentes + sus claves permitidas +
el rechazo de cualquier marca de HTML/script. Todo lo que no esté en el vocabulario, toda clave
desconocida, todo tipo de valor incorrecto y toda inyección → RECHAZADO (no se renderiza). El LLM
nunca emite HTML/JS ejecutable; como mucho propone un `decision_card` con texto, y el texto se pinta
como texto.

El renderer (JS) garantiza la seguridad pintando con `textContent`/`createElement`, NUNCA `innerHTML`
ni `eval`. Este validador es la defensa en profundidad gemela: aunque el renderer fuera perfecto, una
spec con `<script>` se rechaza aquí antes de salir del backend.
"""

from __future__ import annotations

import re
from typing import Any

# ── El vocabulario CERRADO (v1) ──────────────────────────────────────────────────
# Para cada tipo de componente: claves REQUERIDAS y claves OPCIONALES. Cualquier otra clave → rechazo.

_DECISION_CARD = {
    "required": {"type", "title", "options"},
    "optional": {"why", "detail", "risk", "reversible", "kind", "id", "badges"},
}
_RESUMEN = {"required": {"type"}, "optional": {"title", "lines"}}
_ELECCION = {"required": {"type", "prompt", "options"}, "optional": {"id"}}
_BORRADOR_PREVIEW = {"required": {"type", "body"}, "optional": {"subject", "to"}}
_COLA = {"required": {"type", "items"}, "optional": {"title"}}

_SCHEMA: dict[str, dict[str, set[str]]] = {
    "decision_card": _DECISION_CARD,
    "resumen": _RESUMEN,
    "eleccion": _ELECCION,
    "borrador_preview": _BORRADOR_PREVIEW,
    "cola": _COLA,
}

ALLOWED_TYPES = frozenset(_SCHEMA)

# Valores cerrados de algunos campos.
_ALLOWED_RISK = frozenset({"bajo", "medio", "alto"})
_ALLOWED_OPTION_KIND = frozenset({"aprobar", "editar", "posponer", "rechazar"})

# Tipos de componente que pueden anidarse dentro de `cola`.
_COLA_ITEM_TYPES = frozenset({"decision_card", "resumen", "borrador_preview"})

# Marcas de HTML/script/inyección. Si una cadena del spec las contiene → rechazo (defensa en
# profundidad; el renderer ya pinta como texto, pero una spec sucia no debe salir del backend).
_MARKUP = re.compile(
    r"""(
        <\s*/?\s*[a-zA-Z]      # una etiqueta tipo <a, </div, < img
      | <\s*!--                # comentario HTML
      | javascript:           # esquema peligroso
      | \bon[a-z]+\s*=         # manejador de evento: onerror=, onclick=
      | &\#                    # entidad numérica (ofuscación)
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# Tope de tamaño: una spec honesta es pequeña; un texto gigante es señal de abuso.
_MAX_STR = 4000
_MAX_OPTIONS = 8
_MAX_ITEMS = 50
_MAX_LINES = 30


def _es_limpia(s: str) -> bool:
    return len(s) <= _MAX_STR and not _MARKUP.search(s)


def _validar_opciones(options: Any, errores: list[str], ctx: str, *, con_kind: bool) -> None:
    if not isinstance(options, list) or not options:
        errores.append(f"{ctx}: 'options' debe ser una lista no vacía")
        return
    if len(options) > _MAX_OPTIONS:
        errores.append(f"{ctx}: demasiadas opciones ({len(options)} > {_MAX_OPTIONS})")
    for i, o in enumerate(options):
        oc = f"{ctx}.options[{i}]"
        if not isinstance(o, dict):
            errores.append(f"{oc}: cada opción debe ser un objeto")
            continue
        permitidas = {"id", "label", "kind"} if con_kind else {"id", "label"}
        extra = set(o) - permitidas
        if extra:
            errores.append(f"{oc}: claves no permitidas {sorted(extra)}")
        for req in ("id", "label"):
            if not isinstance(o.get(req), str) or not o.get(req):
                errores.append(f"{oc}: falta '{req}' (str no vacío)")
        for k in ("id", "label"):
            v = o.get(k)
            if isinstance(v, str) and not _es_limpia(v):
                errores.append(
                    f"{oc}.{k}: contenido no permitido (markup/inyección o demasiado largo)"
                )
        if con_kind and "kind" in o and o["kind"] not in _ALLOWED_OPTION_KIND:
            errores.append(f"{oc}.kind: valor no permitido «{o['kind']}»")


def _validar_componente(spec: Any, errores: list[str], ctx: str, *, anidado: bool) -> None:
    if not isinstance(spec, dict):
        errores.append(f"{ctx}: debe ser un objeto")
        return
    tipo = spec.get("type")
    if tipo not in ALLOWED_TYPES:
        errores.append(f"{ctx}: tipo no permitido «{tipo}» (vocabulario: {sorted(ALLOWED_TYPES)})")
        return
    schema = _SCHEMA[tipo]
    claves = set(spec)
    faltan = schema["required"] - claves
    if faltan:
        errores.append(f"{ctx}({tipo}): faltan claves requeridas {sorted(faltan)}")
    extra = claves - schema["required"] - schema["optional"]
    if extra:
        errores.append(f"{ctx}({tipo}): claves no permitidas {sorted(extra)}")

    # Todas las cadenas escalares deben estar limpias.
    for k, v in spec.items():
        if isinstance(v, str) and not _es_limpia(v):
            errores.append(f"{ctx}({tipo}).{k}: contenido no permitido (markup/inyección o largo)")

    if tipo == "decision_card":
        _validar_opciones(spec.get("options"), errores, f"{ctx}(decision_card)", con_kind=True)
        if "risk" in spec and spec["risk"] not in _ALLOWED_RISK:
            errores.append(f"{ctx}(decision_card).risk: valor no permitido «{spec['risk']}»")
        if "reversible" in spec and not isinstance(spec["reversible"], bool):
            errores.append(f"{ctx}(decision_card).reversible: debe ser booleano")
        if "badges" in spec:
            badges = spec["badges"]
            if not isinstance(badges, list) or not all(isinstance(b, str) for b in badges):
                errores.append(f"{ctx}(decision_card).badges: debe ser lista de str")
            else:
                for b in badges:
                    if not _es_limpia(b):
                        errores.append(f"{ctx}(decision_card).badges: contenido no permitido")
    elif tipo == "eleccion":
        _validar_opciones(spec.get("options"), errores, f"{ctx}(eleccion)", con_kind=False)
    elif tipo == "resumen":
        lines = spec.get("lines", [])
        if "lines" in spec:
            if not isinstance(lines, list) or not all(isinstance(x, str) for x in lines):
                errores.append(f"{ctx}(resumen).lines: debe ser lista de str")
            elif len(lines) > _MAX_LINES:
                errores.append(f"{ctx}(resumen).lines: demasiadas líneas")
            else:
                for x in lines:
                    if not _es_limpia(x):
                        errores.append(f"{ctx}(resumen).lines: contenido no permitido")
    elif tipo == "cola":
        if anidado:
            errores.append(f"{ctx}: 'cola' no puede anidarse dentro de otra 'cola'")
            return
        items = spec.get("items")
        if not isinstance(items, list):
            errores.append(f"{ctx}(cola).items: debe ser una lista")
            return
        if len(items) > _MAX_ITEMS:
            errores.append(f"{ctx}(cola).items: demasiados items ({len(items)} > {_MAX_ITEMS})")
        for i, it in enumerate(items):
            if isinstance(it, dict) and it.get("type") not in _COLA_ITEM_TYPES:
                errores.append(
                    f"{ctx}.items[{i}]: tipo «{it.get('type')}» no permitido dentro de 'cola'"
                )
                continue
            _validar_componente(it, errores, f"{ctx}.items[{i}]", anidado=True)


def validate_spec(spec: Any) -> tuple[bool, list[str]]:
    """Valida una spec de UI contra el vocabulario CERRADO. Devuelve (ok, errores).

    `ok=True` solo si la spec es íntegramente del vocabulario: tipo conocido, claves conocidas, tipos
    de valor correctos y CERO marcas de HTML/script. No muta la spec.
    """
    errores: list[str] = []
    _validar_componente(spec, errores, "spec", anidado=False)
    return (not errores, errores)


class SpecInvalida(ValueError):
    """Una spec que no pasa el contrato. El backend NUNCA la rinde."""

    def __init__(self, errores: list[str]) -> None:
        super().__init__("; ".join(errores))
        self.errores = errores


def validated_spec(spec: Any) -> dict[str, Any]:
    """Devuelve la spec si es válida; si no, lanza `SpecInvalida`. Para los endpoints: lo que sale
    del backend está validado por construcción."""
    ok, errores = validate_spec(spec)
    if not ok:
        raise SpecInvalida(errores)
    return spec  # type: ignore[return-value]


# ── Compositor: una Decision → su spec (validada) ────────────────────────────────


def decision_to_spec(decision: Any) -> dict[str, Any]:
    """Compone un `decision_card` a partir de una `decisions.Decision`. El resultado pasa por
    `validated_spec`: si el dominio metiera algo sucio, salta aquí, no en la pantalla."""
    spec = {
        "type": "decision_card",
        "id": getattr(decision, "id", ""),
        "title": getattr(decision, "title", ""),
        "why": getattr(decision, "why", ""),
        "detail": getattr(decision, "detail", ""),
        "kind": getattr(getattr(decision, "kind", None), "value", "generico"),
        "risk": getattr(getattr(decision, "risk", None), "value", "bajo"),
        "reversible": bool(getattr(decision, "reversible", True)),
        "options": [
            {"id": o.id, "label": o.label, "kind": o.kind.value}
            for o in getattr(decision, "options", [])
        ],
    }
    return validated_spec(spec)


def cola_to_spec(decisiones: list[Any], *, title: str = "Tus decisiones") -> dict[str, Any]:
    """Compone la `cola` (lista de `decision_card`) a partir de las decisiones pendientes."""
    spec = {
        "type": "cola",
        "title": title,
        "items": [decision_to_spec(d) for d in decisiones],
    }
    return validated_spec(spec)
