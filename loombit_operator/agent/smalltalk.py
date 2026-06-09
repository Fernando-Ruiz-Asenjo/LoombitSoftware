"""
smalltalk.py — cortesía instantánea (fricción cero).

Un "hola" o un "gracias" NO deben gastar el bucle ReAct del 14B (en local eso son ~decenas de
segundos de "Procesando…" para nada). Aquí se detecta SOLO la charla trivial —saludos, gracias,
despedidas— y se responde al instante, de forma determinista, sin tocar el modelo.

CONSERVADOR a propósito: solo casa la FRASE COMPLETA normalizada con un repertorio curado de
cortesías cortas. Cualquier cosa con una intención real ("hola, envíame el informe a Ana") NO casa
y va al agente como siempre. Mejor dejar pasar una cortesía rara al agente que interceptar una tarea.
"""

from __future__ import annotations

import re

_SALUDOS = {
    "hola",
    "holaa",
    "hola buenas",
    "buenas",
    "hey",
    "ey",
    "ola",
    "buenos dias",
    "buenas tardes",
    "buenas noches",
    "que tal",
    "que tal todo",
    "como estas",
    "como va",
    "como va todo",
    "saludos",
    "hola que tal",
    "buenas que tal",
    "muy buenas",
    "hola muy buenas",
    "hola loombit",
    "buenas loombit",
}
_GRACIAS = {
    "gracias",
    "muchas gracias",
    "mil gracias",
    "ok gracias",
    "vale gracias",
    "genial gracias",
    "perfecto gracias",
}
_OK = {"ok", "okey", "vale", "genial", "perfecto", "estupendo", "de acuerdo", "entendido", "guay"}
_DESPEDIDAS = {
    "adios",
    "hasta luego",
    "chao",
    "nos vemos",
    "hasta pronto",
    "hasta manana",
}

_R_SALUDO = (
    "¡Hola! Soy tu operador. Puedo ocuparme de tus correos, tu agenda, tus cobros y tus facturas, "
    "y prepararte el resumen del día. ¿Con qué empezamos?"
)
_R_GRACIAS = "¡A mandar! ¿Quieres que siga con algo más?"
_R_OK = "Perfecto. ¿Seguimos con otra cosa?"
_R_DESPEDIDA = "¡Hasta luego! Aquí sigo cuando me necesites."


def _norm(texto: str) -> str:
    """Minúsculas, sin tildes, SIN puntuación, espacios colapsados."""
    t = (texto or "").strip().lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ü", "u")):
        t = t.replace(a, b)
    t = re.sub(r"[^a-z0-9ñ ]+", " ", t)  # fuera comas, signos ¿¡!?, etc.
    return re.sub(r"\s+", " ", t).strip()


def respuesta_social(task: str) -> str | None:
    """Si `task` es una cortesía pura y corta, devuelve la respuesta instantánea; si no, None.

    None significa "no es charla trivial → que lo lleve el agente". Es la red de seguridad: ante la
    duda, None (no interceptamos tareas reales)."""
    raw = (task or "").strip()
    # Una cifra, un '@' o una barra → seguramente hay una intención real; no es cortesía.
    if not raw or len(raw) > 40 or "@" in raw or "/" in raw or any(c.isdigit() for c in raw):
        return None
    t = _norm(raw)
    if not t or len(t.split()) > 4:
        return None
    if t in _SALUDOS:
        return _R_SALUDO
    if t in _GRACIAS:
        return _R_GRACIAS
    if t in _DESPEDIDAS:
        return _R_DESPEDIDA
    if t in _OK:
        return _R_OK
    return None
