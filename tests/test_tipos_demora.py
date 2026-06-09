"""
Tabla oficial del tipo legal de interés de demora (Ley 3/2004). Verifica que:
  - cada tipo publicado cumple la invariante legal tipo = BCE + 8 puntos,
  - el reparto por semestres es exacto (un solo tramo y varios tramos),
  - fuera de la tabla verificada el cálculo se ABSTIENE (no inventa cifras).
Las cifras provienen del BOE (cada entrada cita su resolución); verificado el 2026-06-08.
"""

from loombit_operator import tipos_demora as td


def test_invariante_tipo_es_bce_mas_8():
    for (year, sem), fila in td.TIPOS_PUBLICADOS.items():
        esperado = round(fila["bce_pct"] + td.MARGEN_LEGAL_PUNTOS, 2)
        assert fila["tipo_pct"] == esperado, f"{sem}S{year}: {fila['tipo_pct']} != {esperado}"


def test_semestre_de_y_limites():
    assert td.semestre_de("2024-01-01") == (2024, 1)
    assert td.semestre_de("2024-06-30") == (2024, 1)
    assert td.semestre_de("2024-07-01") == (2024, 2)
    assert td.semestre_de("2024-12-31") == (2024, 2)


def test_tipo_vigente_con_fuente():
    v = td.tipo_vigente("2025-08-10")
    assert v["semestre"] == "2S2025"
    assert v["tipo_pct"] == 10.15
    assert v["boe"] == "BOE-A-2025-13217"


def test_tipo_vigente_fuera_de_tabla_es_none():
    assert td.tipo_vigente("2019-01-01") is None
    assert td.tipo_vigente("2030-01-01") is None


def test_interes_un_solo_semestre():
    # 1250 € · 10,15 % (1S2026) · 37 días / 365 = 12,86 €
    r = td.interes_demora_legal(1250.0, "2026-05-01", "2026-06-07")
    assert r["rate_required"] is False
    assert r["rate_pct"] == 10.15
    assert r["amount"] == 12.86
    assert len(r["tramos"]) == 1
    assert r["tramos"][0]["dias"] == 37
    assert r["tramos"][0]["boe"] == "BOE-A-2025-27201"


def test_interes_reparte_por_dos_semestres():
    # 2024-06-16 … 2024-07-15 = 15 días en 1S2024 (12,50 %) + 15 días en 2S2024 (12,25 %).
    r = td.interes_demora_legal(10000.0, "2024-06-15", "2024-07-15")
    assert r["rate_required"] is False
    assert r["rate_pct"] is None  # periodo a caballo entre dos semestres → tipo no único
    semestres = [t["semestre"] for t in r["tramos"]]
    assert semestres == ["1S2024", "2S2024"]
    assert [t["dias"] for t in r["tramos"]] == [15, 15]
    # 10000·0,1250·15/365 = 51,37 ; 10000·0,1225·15/365 = 50,34 → 101,71
    assert r["amount"] == 101.71


def test_interes_se_abstiene_si_algun_tramo_no_esta_publicado():
    r = td.interes_demora_legal(1000.0, "2019-05-01", "2019-06-01")
    assert r["rate_required"] is True
    assert r["amount"] is None
    assert "2019" in r["note"]


def test_interes_cero_si_no_hay_dias_o_principal():
    assert td.interes_demora_legal(0.0, "2026-01-01", "2026-06-01")["amount"] == 0.0
    assert td.interes_demora_legal(1000.0, "2026-06-01", "2026-06-01")["amount"] == 0.0
    assert td.interes_demora_legal(1000.0, "2026-06-10", "2026-06-01")["amount"] == 0.0


def test_suma_de_dias_de_tramos_igual_a_dias_vencidos():
    r = td.interes_demora_legal(5000.0, "2023-03-10", "2025-09-20")
    dias_tramos = sum(t["dias"] for t in r["tramos"])
    # días devengados = (hoy - vencimiento)
    from datetime import date

    esperado = (date(2025, 9, 20) - date(2023, 3, 10)).days
    assert dias_tramos == esperado
