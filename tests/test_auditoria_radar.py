"""
EL RADAR VIVE (§INNOVACIÓN, D-85) — golden con dientes. «Si no hay radar, no pasa.»

Prueba que el check confronta de verdad: sin radar falla, un radar anémico falla, y una señal sin FUENTE
o sin PROPUESTA se caza (humo). Y que el radar REAL commiteado (`docs/RADAR.jsonl`) vive. Determinista.
"""

from __future__ import annotations

from datetime import date

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


# ── Frescura: un radar que no se refresca, muere (docdecay / ThoughtWorks blip) ─


def _escribir(tmp_path, *senales):
    import json

    p = tmp_path / "radar.jsonl"
    p.write_text("\n".join(json.dumps(s) for s in senales) + "\n", encoding="utf-8")
    return p


def test_radar_fresco_pasa(tmp_path):
    frescas = [dict(SENAL_OK, fecha="2026-06-12") for _ in range(3)]
    assert auditar(_escribir(tmp_path, *frescas), hoy=date(2026, 6, 13)) == []


def test_radar_caducado_no_pasa(tmp_path):
    viejas = [dict(SENAL_OK, fecha="2026-01-01") for _ in range(3)]
    fallos = auditar(_escribir(tmp_path, *viejas), hoy=date(2026, 6, 13))
    assert any("CADUCADO" in e for e in fallos)


def test_radar_sin_fecha_valida_no_pasa(tmp_path):
    malas = [dict(SENAL_OK, fecha="ayer") for _ in range(3)]
    fallos = auditar(_escribir(tmp_path, *malas), hoy=date(2026, 6, 13))
    assert any("SIN FECHA" in e for e in fallos)


# ── El radar REAL del repo vive ───────────────────────────────────────────────


def test_radar_real_vive():
    senales = cargar()
    assert senales, "no hay radar commiteado"
    # Frescura medida desde la señal más nueva (determinista, no depende del reloj de la suite);
    # la frescura REAL contra hoy la fuerza el gate vivo (verify.py corre el auditor con date.today()).
    nuevas = max(date.fromisoformat(s["fecha"]) for s in senales)
    assert auditar(hoy=nuevas) == []
