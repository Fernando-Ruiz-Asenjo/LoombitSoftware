"""
EL RADAR VIVE (§INNOVACIÓN, D-85) — golden con dientes. «Si no hay radar, no pasa.»

Prueba que el check confronta de verdad: sin radar falla, un radar anémico falla, y una señal sin FUENTE
o sin PROPUESTA se caza (humo). Y que el radar REAL commiteado (`docs/RADAR.jsonl`) vive. Determinista.
"""

from __future__ import annotations

from scripts.auditoria_radar import auditar, cargar, validar_senal

SENAL_OK = {
    "fecha": "2026-06-12",
    "tema": "Demo",
    "fuente": "https://ejemplo.com/articulo",
    "evidencia": "dura",
    "hallazgo": "Un hallazgo real y concreto del mercado.",
    "propuesta": "Una propuesta accionable para Loombit, clara.",
}


# ── Lo válido pasa ────────────────────────────────────────────────────────────


def test_senal_valida_pasa():
    assert validar_senal(SENAL_OK) == []


# ── Dientes: confronta de verdad ──────────────────────────────────────────────


def test_sin_fuente_falla():
    s = dict(SENAL_OK, fuente="no-es-url")
    assert any("FUENTE" in e for e in validar_senal(s))


def test_sin_propuesta_falla():
    s = dict(SENAL_OK, propuesta="")
    assert any("propuesta" in e.lower() for e in validar_senal(s))


def test_evidencia_invalida_falla():
    s = dict(SENAL_OK, evidencia="regular")
    assert any("evidencia" in e.lower() for e in validar_senal(s))


def test_hallazgo_trivial_falla():
    s = dict(SENAL_OK, hallazgo="x")
    assert any("hallazgo" in e.lower() for e in validar_senal(s))


# ── «Si no hay radar, no pasa» ────────────────────────────────────────────────


def test_sin_radar_no_pasa(tmp_path):
    vacio = tmp_path / "radar.jsonl"
    fallos = auditar(vacio)  # no existe
    assert fallos and "NO HAY RADAR" in fallos[0]


def test_radar_anemico_no_pasa(tmp_path):
    import json

    p = tmp_path / "radar.jsonl"
    p.write_text(json.dumps(SENAL_OK) + "\n", encoding="utf-8")  # solo 1 señal
    assert any("ANÉMICO" in e for e in auditar(p))


# ── El radar REAL del repo vive ───────────────────────────────────────────────


def test_radar_real_vive():
    assert cargar(), "no hay radar commiteado"
    assert auditar() == []
