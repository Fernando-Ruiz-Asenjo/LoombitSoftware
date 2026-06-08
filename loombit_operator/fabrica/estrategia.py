"""
estrategia.py — síntesis de PRODUCTO/MONETIZACIÓN a partir de la inteligencia del radar.

El radar trae señales sueltas (competidores, mercado, tech). Aquí el instructor LLM las DESTILA en
vías concretas para Loombit: qué construir, qué monetizar, dónde está el hueco — siempre desde el
foso (local · español · administrativo). Cada idea referida a la señal que la motiva (procedencia).
Best-effort: si no hay modelo o señales, lo dice; no inventa.
"""

from __future__ import annotations

from typing import Any

_SISTEMA = (
    "Eres el estratega de producto de Loombit (el operador administrativo LOCAL del autónomo/PYME "
    "español; foso: privacidad local + español + admin profundo). Te paso SEÑALES reales del radar "
    "(competencia, mercado, nuevas tecnologías). Destila 3-5 VÍAS concretas para Loombit — de "
    "producto o de monetización — cada una en 1-2 frases, accionable y honesta, citando la señal que "
    "la motiva. Prioriza lo que refuerza el foso. Nada de humo ni de prometer lo imposible. Español, "
    "conciso, sin markdown ni JSON."
)


def sintetizar_estrategia(hallazgos: list[Any], llm: Any = None) -> dict[str, Any]:
    """De las señales del radar saca vías de producto/monetización. `hallazgos` = list de dicts del
    OportunidadStore o de Necesidad. Devuelve {ok, resumen, basado_en}."""
    señales: list[str] = []
    for h in hallazgos:
        if isinstance(h, dict):
            nec = h.get("necesidad", h)
            titulo = nec.get("titulo", "")
            fuente = nec.get("fuente", "")
        else:  # Necesidad
            titulo = getattr(h, "titulo", "")
            fuente = getattr(getattr(h, "fuente", None), "value", "")
        if titulo:
            señales.append(f"[{fuente}] {titulo}")

    if not señales:
        return {
            "ok": False,
            "resumen": "Sin señales del radar todavía. Corre un ciclo primero.",
            "basado_en": 0,
        }

    if llm is None:
        try:
            from ..llm import LLMClient

            llm = LLMClient()
        except Exception:  # noqa: BLE001
            return {"ok": False, "resumen": "Modelo no disponible.", "basado_en": len(señales)}

    contexto = "\n".join(f"- {s}" for s in señales[:24])
    try:
        resp = llm.chat(
            messages=[
                {"role": "system", "content": _SISTEMA},
                {"role": "user", "content": f"SEÑALES DEL RADAR:\n{contexto}"},
            ],
            max_tokens=500,
        )
        texto = (getattr(resp, "content", "") or "").strip()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "resumen": f"No pude sintetizar: {exc!r}", "basado_en": len(señales)}
    return {"ok": bool(texto), "resumen": texto, "basado_en": len(señales)}


_SISTEMA_INVESTIGAR = (
    "Eres analista de producto de Loombit (operador administrativo LOCAL del autónomo/PYME español; "
    "foso: privacidad local + español + admin). Te paso UNA señal del radar (un proyecto/competidor/"
    "noticia) y, si pude leerla, un extracto. En 3-5 frases: (1) qué ES, (2) si es relevante para "
    "Loombit y por qué, (3) cómo TRAERLO/aplicarlo aquí (capacidad, skill o vía de monetización), "
    "desde el foso. Honesto: si no aplica o es ruido, dilo. Español, sin markdown."
)


def _leer_url(url: str) -> str:
    """Extracto de texto plano de la URL (best-effort, truncado). Para 'ver qué hacen' de verdad."""
    if not url.startswith("http"):
        return ""
    try:
        import re

        import httpx

        resp = httpx.get(
            url, timeout=12, follow_redirects=True, headers={"User-Agent": "Loombit-Radar"}
        )
        if resp.status_code != 200:
            return ""
        txt = re.sub(
            r"<(script|style)[^>]*>.*?</\1>", " ", resp.text, flags=re.DOTALL | re.IGNORECASE
        )
        txt = re.sub(r"<[^>]+>", " ", txt)
        return re.sub(r"\s+", " ", txt).strip()[:2000]
    except Exception:  # noqa: BLE001
        return ""


def analizar_oportunidad(titulo: str, url: str = "", llm: Any = None) -> dict[str, Any]:
    """Investiga UNA señal del radar: la lee (si puede) y dice qué es y cómo traerla a Loombit."""
    if llm is None:
        try:
            from ..llm import LLMClient

            llm = LLMClient()
        except Exception:  # noqa: BLE001
            return {"ok": False, "analisis": "Modelo no disponible."}
    extracto = _leer_url(url)
    user = f"SEÑAL: {titulo}\nFuente: {url or '(sin URL)'}"
    if extracto:
        user += f"\nEXTRACTO LEÍDO:\n{extracto}"
    try:
        resp = llm.chat(
            messages=[
                {"role": "system", "content": _SISTEMA_INVESTIGAR},
                {"role": "user", "content": user},
            ],
            max_tokens=420,
        )
        texto = (getattr(resp, "content", "") or "").strip()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "analisis": f"No pude investigar: {exc!r}"}
    return {"ok": bool(texto), "analisis": texto, "leido": bool(extracto)}
