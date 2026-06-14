"""
Golden de K2 — valla de AUTOPROTECCIÓN del sistema de ficheros.

Verifica que el agente NO puede escribir su propio código, el gate, la constitución, `.env` ni el
token store (ni vía `write_file` —que AUTO-ejecuta sin gate humano— ni vía un comando shell de
escritura), y que SÍ puede escribir documentos del usuario en rutas normales. Determinista, sin red.
Cierra la 2ª vía 🔴 del red team (el agente reescribiendo sus propios guardarraíles).
"""

from __future__ import annotations

from loombit_operator.sandbox import policy
from loombit_operator.tools.base import _run_shell, _write_file

_REPO = policy._REPO


# ── ruta_protegida ────────────────────────────────────────────────────────────
def test_protege_codigo_gate_constitucion_y_credenciales():
    protegidas = [
        _REPO / "loombit_operator" / "agent" / "loop.py",
        _REPO / "loombit_operator" / "policy" / "authority_plane.py",
        _REPO / "scripts" / "verify.py",
        _REPO / ".githooks" / "pre-commit",
        _REPO / "CLAUDE.md",
        _REPO / "docs" / "BRUJULA.md",
        _REPO / "pyproject.toml",
        _REPO / ".env",
        _REPO / "runtime" / "local" / "skill_blanca_oauth_tokens.json",
    ]
    for p in protegidas:
        prot, motivo = policy.ruta_protegida(str(p))
        assert prot, f"debería estar protegida: {p}"
        assert motivo


def test_permite_documentos_del_usuario(tmp_path):
    for p in [tmp_path / "informe.txt", _REPO / "runtime" / "local" / "borrador.md"]:
        prot, _ = policy.ruta_protegida(str(p))
        assert not prot, f"NO debería estar protegida: {p}"


def test_no_se_sortea_con_path_traversal():
    # runtime/../loombit_operator/agent/loop.py resuelve DENTRO del sistema → protegida.
    travieso = _REPO / "runtime" / ".." / "loombit_operator" / "agent" / "loop.py"
    prot, _ = policy.ruta_protegida(str(travieso))
    assert prot


# ── write_file (AUTO-ejecuta → es el agujero ANCHO) ───────────────────────────
def test_write_file_bloquea_el_propio_codigo():
    res = _write_file(str(_REPO / "loombit_operator" / "agent" / "loop.py"), "ROTO")
    assert "BLOQUEADO" in res and "autoprotección" in res
    assert not res.startswith("OK")  # no escribió


def test_write_file_bloquea_credenciales():
    assert "BLOQUEADO" in _write_file(str(_REPO / ".env"), "SECRET=x")
    assert "BLOQUEADO" in _write_file(
        str(_REPO / "runtime" / "local" / "skill_blanca_oauth_tokens.json"), "{}"
    )


def test_write_file_permite_documento_del_usuario(tmp_path):
    destino = tmp_path / "salida" / "informe.txt"
    res = _write_file(str(destino), "hola mundo")
    assert res.startswith("OK")
    assert destino.read_text(encoding="utf-8") == "hola mundo"


# ── run_shell (gated, pero defensa en profundidad) ────────────────────────────
def test_run_shell_bloquea_escritura_al_sistema_sin_ejecutar():
    res = _run_shell("echo ROTO > loombit_operator/agent/loop.py")
    assert "BLOQUEADO" in res
    assert "EXIT:" not in res  # NO llegó a ejecutarse


def test_run_shell_permite_lectura_o_ejecucion():
    assert not policy.comando_peligroso("python -m loombit_operator.launcher")[0]
    assert not policy.comando_peligroso("cat loombit_operator/agent/loop.py")[0]
    # pero un borrado del propio código sí se caza:
    assert policy.comando_peligroso("rm loombit_operator/agent/loop.py")[0]
