"""
Chequeo de salud del LLM local: ¿el modelo cargado en LM Studio tiene SUFICIENTE contexto?

Problema que resuelve (regresión real 2026-06-11): si el 14B se recarga con menos contexto del que
Loombit espera (`llm_context_length`, p.ej. 4096 < 8192), TODA operación viva revienta con
`400 Bad Request: n_keep >= n_ctx` — pero el gate (pytest con LLM stub) sigue VERDE, así que el fallo
es SILENCIOSO. Este módulo lo hace RUIDOSO: compara el contexto realmente cargado contra el
configurado y avisa fuerte (en /health/llm-context y al arrancar el launcher).

Determinista y sin efectos: solo consulta la API nativa de LM Studio (`/api/v0/models`, que expone
`loaded_context_length` y `state`). Si LM Studio no responde, NO es un fallo de contexto (puede estar
apagado) → status 'unreachable', no bloquea.
"""

from __future__ import annotations

from .config import AppSettings, get_settings


def _native_models_url(base_url: str) -> str:
    """Deriva la URL de la API NATIVA de LM Studio (`/api/v0/models`) desde el `llm_base_url`
    (normalmente `http://host:port/v1`). Esa API expone el contexto cargado, que la OpenAI-like `/v1`
    no da."""
    b = (base_url or "").rstrip("/")
    if b.endswith("/v1"):
        b = b[:-3]
    return b.rstrip("/") + "/api/v0/models"


def check_context(settings: AppSettings | None = None, timeout: float = 4.0) -> dict:
    """Compara el contexto CARGADO en LM Studio para el modelo configurado contra `llm_context_length`.

    Devuelve un dict con `ok`, `status`, `loaded_context_length`, `configured_context_length`,
    `model` y `message`. Estados:
      - `ok`              : cargado >= configurado (todo bien).
      - `context_too_small`: cargado < configurado → TODA op viva dará 400 (ok=False, el grave).
      - `not_loaded`      : el modelo no está cargado / no aparece (ok=False).
      - `unreachable`     : LM Studio no responde (ok=True: puede estar apagado, no es bug de contexto).
      - `disabled`        : el proveedor LLM está deshabilitado (ok=True).
    """
    settings = settings or get_settings()
    cfg = int(settings.llm_context_length)
    model = settings.llm_model_name
    res: dict = {
        "ok": True,
        "status": "ok",
        "model": model,
        "configured_context_length": cfg,
        "loaded_context_length": None,
        "message": "",
    }
    if settings.llm_provider == "disabled":
        res.update(status="disabled", message="El proveedor LLM está deshabilitado.")
        return res

    import httpx

    url = _native_models_url(settings.llm_base_url)
    try:
        resp = httpx.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001 — no poder consultar NO es un fallo de contexto
        res.update(
            status="unreachable",
            message=f"No pude consultar el contexto cargado en LM Studio ({url}): {exc}.",
        )
        return res

    modelos = data if isinstance(data, list) else data.get("data", data) or []
    m = next((x for x in modelos if str(x.get("id")) == model), None)
    if m is None:
        res.update(
            ok=False,
            status="not_loaded",
            message=(
                f"El modelo '{model}' no aparece en LM Studio. Cárgalo con contexto ≥ {cfg}: "
                f"lms load {model} -c {cfg} --parallel 1"
            ),
        )
        return res
    if m.get("state") != "loaded":
        res.update(
            ok=False,
            status="not_loaded",
            message=f"El modelo '{model}' está en estado '{m.get('state')}', no 'loaded'.",
        )
        return res

    loaded = m.get("loaded_context_length")
    res["loaded_context_length"] = loaded
    if isinstance(loaded, int) and loaded < cfg:
        res.update(
            ok=False,
            status="context_too_small",
            message=(
                f"⚠ El modelo '{model}' está cargado con SOLO {loaded} de contexto, pero Loombit "
                f"espera {cfg}. TODA operación viva fallará con 400 'n_keep >= n_ctx' (el gate NO lo "
                f"caza: usa un LLM stub). Recárgalo: lms load {model} -c {cfg} --parallel 1"
            ),
        )
        return res

    res["message"] = f"Contexto OK: cargado {loaded} ≥ configurado {cfg}."
    return res
