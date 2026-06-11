"""
Golden de `fabrica/estrategia.py` — síntesis de PRODUCTO/MONETIZACIÓN desde las señales del radar.

Cubre la LÓGICA pura e inyectable (D-74: mockear el LLM en su costura documentada es legítimo, no es
hardware): extracción de señales (dict y objeto Necesidad), rama sin señales, rama sin modelo, manejo de
respuesta vacía y de excepción del LLM. NO toca la red (`_leer_url`): el LLM se inyecta.
"""

from __future__ import annotations

from types import SimpleNamespace

from loombit_operator.fabrica.estrategia import (
    _leer_url,
    analizar_oportunidad,
    sintetizar_estrategia,
)


class _LLM:
    """Fake del cliente LLM: devuelve un contenido fijo por la costura `.chat()` (inyección documentada)."""

    def __init__(self, content: str) -> None:
        self._c = content

    def chat(self, messages, **_):  # noqa: ANN001
        return SimpleNamespace(content=self._c)


class _Boom:
    def chat(self, *a, **k):  # noqa: ANN001, ANN002, ANN003
        raise RuntimeError("LLM caído")


# ── sintetizar_estrategia ─────────────────────────────────────────────────────


def test_sin_senales_no_inventa():
    out = sintetizar_estrategia([], llm=_LLM("lo que sea"))
    assert out["ok"] is False
    assert out["basado_en"] == 0
    assert "radar" in out["resumen"].lower()


def test_senales_dict_anidado_y_plano():
    hallazgos = [
        {"necesidad": {"titulo": "Competidor X cobra por OCR", "fuente": "competencia"}},
        {"titulo": "Factura-e obligatoria 2027", "fuente": "regulacion"},
    ]
    out = sintetizar_estrategia(hallazgos, llm=_LLM("Vía 1: OCR local. Vía 2: Verifactu."))
    assert out["ok"] is True
    assert out["basado_en"] == 2
    assert "Verifactu" in out["resumen"]


def test_senal_objeto_necesidad():
    nec = SimpleNamespace(titulo="Auge agentes locales", fuente=SimpleNamespace(value="tech"))
    out = sintetizar_estrategia([nec], llm=_LLM("Vía: privacidad local como foso."))
    assert out["ok"] is True and out["basado_en"] == 1


def test_titulo_vacio_no_cuenta_como_senal():
    out = sintetizar_estrategia([{"titulo": "", "fuente": "x"}], llm=_LLM("algo"))
    # sin títulos válidos → tratado como "sin señales".
    assert out["ok"] is False and out["basado_en"] == 0


def test_respuesta_vacia_del_llm_no_es_ok():
    out = sintetizar_estrategia([{"titulo": "T", "fuente": "f"}], llm=_LLM("   "))
    assert out["ok"] is False and out["basado_en"] == 1


def test_excepcion_del_llm_se_reporta_sin_romper():
    out = sintetizar_estrategia([{"titulo": "T", "fuente": "f"}], llm=_Boom())
    assert out["ok"] is False
    assert "no pude sintetizar" in out["resumen"].lower()
    assert out["basado_en"] == 1


# ── analizar_oportunidad (sin URL → no toca la red) ───────────────────────────


def test_analizar_sin_url_usa_solo_el_titulo():
    out = analizar_oportunidad(
        "Proyecto Y", url="", llm=_LLM("Es un agente local; encaja en el foso.")
    )
    assert out["ok"] is True
    assert out["leido"] is False
    assert "foso" in out["analisis"]


def test_analizar_excepcion_del_llm():
    out = analizar_oportunidad("Proyecto Z", llm=_Boom())
    assert out["ok"] is False
    assert "no pude investigar" in out["analisis"].lower()


def test_leer_url_no_http_devuelve_vacio():
    # guard PURO de `_leer_url`: lo que no es http no se lee (la parte httpx es red, verificada en vivo).
    assert _leer_url("") == ""
    assert _leer_url("ftp://x/y") == ""
    assert _leer_url("solo-texto") == ""
