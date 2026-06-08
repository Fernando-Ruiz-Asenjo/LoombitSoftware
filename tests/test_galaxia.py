"""
Galaxia (`build_galaxia`): agrega sol+KPIs, planetas contacto/cuenta y aristas contacto↔cuenta.

AISLAMIENTO: `store` y `contactos` se inyectan (tmp + stub) y se neutraliza `_correos_sin_leer`
para que el test NUNCA toque el store de producción ni Gmail.
"""

import loombit_operator.galaxia as gx
from loombit_operator.cuentas_cobrar import CuentaCobrar, CuentasCobrarStore
from loombit_operator.galaxia import build_galaxia

TODAY = "2026-06-10"

CONTACTOS = [
    {"name": "Jana Wall", "email": "jana@acme.com", "veces": 12},
    {"name": "David Valentín", "email": "david@beta.es", "veces": 3},
    {"name": "Sin trato", "email": "nadie@otro.com", "veces": 1},
]


def _store(tmp_path):
    s = CuentasCobrarStore(path=tmp_path / "cc.json")
    s.add(CuentaCobrar(cliente="Acme S.L.", importe=1250, vencimiento="2026-06-01"))  # vencida 9d
    s.add(CuentaCobrar(cliente="Beta", importe=400, vencimiento="2026-06-13"))  # vence en 3d
    s.add(CuentaCobrar(cliente="Lejana Corp", importe=70, vencimiento="2026-09-30"))  # lejos
    return s


def _galaxia(tmp_path, monkeypatch):
    # Nunca llamar a Gmail desde el test:
    monkeypatch.setattr(gx, "_correos_sin_leer", lambda *a, **k: None)
    return build_galaxia(today=TODAY, store=_store(tmp_path), contactos=CONTACTOS)


def test_sol_kpis(tmp_path, monkeypatch):
    g = _galaxia(tmp_path, monkeypatch)
    k = g["sol"]["kpis"]
    assert k["total_cobrar"] == 1720  # 1250 + 400 + 70
    assert k["vencidas"] == 1  # solo Acme
    assert k["proximas"] == 1  # solo Beta (<=7 días)
    assert k["correos_sin_leer"] is None
    assert isinstance(g["sol"]["nombre"], str) and g["sol"]["nombre"]


def test_nodos_contacto_peso_y_temperatura(tmp_path, monkeypatch):
    g = _galaxia(tmp_path, monkeypatch)
    contactos = {n["etiqueta"]: n for n in g["nodos"] if n["tipo"] == "contacto"}
    assert set(contactos) == {"Jana Wall", "David Valentín", "Sin trato"}
    # El más frecuente brilla al máximo; el de menos trato, el mínimo del rango.
    assert contactos["Jana Wall"]["temperatura"] == 1.0
    assert contactos["Sin trato"]["temperatura"] == round(0.35 + 0.65 * (1 / 12), 3)
    assert contactos["Jana Wall"]["peso"] == 12


def test_nodos_cuenta_estado_y_dias(tmp_path, monkeypatch):
    g = _galaxia(tmp_path, monkeypatch)
    cuentas = {n["etiqueta"]: n for n in g["nodos"] if n["tipo"] == "cuenta"}
    assert cuentas["Acme S.L."]["estado"] == "vencida"
    assert cuentas["Acme S.L."]["dias"] == -9  # vencida hace 9 días → la vista la acerca al centro
    assert cuentas["Beta"]["estado"] == "proxima"
    assert cuentas["Beta"]["dias"] == 3
    assert cuentas["Lejana Corp"]["estado"] == "pendiente"


def test_aristas_contacto_cuenta_por_nombre_y_dominio(tmp_path, monkeypatch):
    g = _galaxia(tmp_path, monkeypatch)
    pares = {(a["origen"], a["destino"]) for a in g["aristas"]}
    # Jana ↔ Acme: casa por el DOMINIO del email (jana@ACME.com ↔ cliente "Acme S.L.").
    acme = next(n["id"] for n in g["nodos"] if n["etiqueta"] == "Acme S.L.")
    beta = next(n["id"] for n in g["nodos"] if n["etiqueta"] == "Beta")
    assert ("c:jana@acme.com", acme) in pares
    # David ↔ Beta: casa por el DOMINIO (david@BETA.es ↔ cliente "Beta").
    assert ("c:david@beta.es", beta) in pares
    # "Sin trato" no casa con ninguna cuenta → sin aristas espurias (anti-maraña).
    assert not any(o == "c:nadie@otro.com" for o, _ in pares)
    # Lejana Corp no tiene contacto → no aparece en ninguna arista.
    lejana = next(n["id"] for n in g["nodos"] if n["etiqueta"] == "Lejana Corp")
    assert not any(d == lejana for _, d in pares)


def test_meta_cuenta_nodos_y_aristas(tmp_path, monkeypatch):
    g = _galaxia(tmp_path, monkeypatch)
    assert g["meta"]["n_contactos"] == 3
    assert g["meta"]["n_cuentas"] == 3
    assert g["meta"]["n_aristas"] == len(g["aristas"]) >= 2
    assert g["meta"]["fuente_contactos"] == "inyectado"


def test_endpoint_galaxia_cachea(monkeypatch):
    """El router devuelve la forma esperada y cachea (no reconstruye en cada poll)."""
    from fastapi.testclient import TestClient

    from loombit_operator import galaxia_cache
    from loombit_operator.main import app

    llamadas = {"n": 0}

    def _fake_build():
        llamadas["n"] += 1
        return {"sol": {"nombre": "X", "kpis": {}}, "nodos": [], "aristas": [], "meta": {}}

    # La caché ahora vive en galaxia_cache (pre-carga stale-while-revalidate).
    monkeypatch.setattr(galaxia_cache, "build_galaxia", _fake_build)
    galaxia_cache._snap = None
    galaxia_cache._ts = 0.0
    galaxia_cache._refreshing = False

    with TestClient(app) as client:
        r1 = client.get("/galaxia")
        assert r1.status_code == 200
        assert set(r1.json()) == {"sol", "nodos", "aristas", "meta"}
        client.get("/galaxia")  # dentro del TTL → cacheado
        assert llamadas["n"] == 1
        client.get("/galaxia?force=1")  # fuerza reconstrucción
        assert llamadas["n"] == 2
