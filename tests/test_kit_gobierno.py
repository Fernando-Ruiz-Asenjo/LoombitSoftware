"""
Kit de gobierno reutilizable y BLINDADO — golden. Demuestra lo que el usuario pidió:
1. **Blindado / dientes:** el motor `brujula_check.py` BLOQUEA de verdad (caza cada violación mecánica).
2. **Reutilizable / blanco:** los esqueletos no llevan dominio (cero palabras de un sector concreto).
3. El kit está completo (todos los ficheros para adoptarlo).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "kit-gobierno"


def _cargar_motor():
    """Carga `kit-gobierno/brujula_check.py` (la carpeta lleva guion → import por ruta)."""
    spec = importlib.util.spec_from_file_location("brujula_check_kit", KIT / "brujula_check.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bc = _cargar_motor()


# ── 1) Dientes: el motor BLOQUEA cada violación mecánica ───────────────────────


def test_tamano_bloquea_sobre_limite():
    assert bc.viola_tamano([("src/x.py", bc.LIMITE_LINEAS + 1)]) != []
    assert bc.viola_tamano([("src/x.py", bc.LIMITE_LINEAS)]) == []


def test_modulo_nuevo_sin_test_bloquea():
    assert bc.viola_arnes(["src/nuevo.py"], hay_test_en_diff=False) != []
    assert bc.viola_arnes(["src/nuevo.py"], hay_test_en_diff=True) == []


def test_tocar_normas_sin_registro_bloquea():
    assert bc.viola_sync_constitucion({"CLAUDE.md"}) != []
    assert bc.viola_sync_constitucion({"CLAUDE.md", "DECISIONES.md"}) == []


def test_saltar_el_gate_bloquea():
    assert bc.viola_no_verify(["git commit --no-verify -m x"]) != []
    assert bc.viola_no_verify(["git commit -m x"]) == []


def test_cambio_normal_no_exige_registro():
    assert bc.viola_sync_constitucion({"src/x.py"}) == []


# ── 2) Blanco: los esqueletos no llevan dominio ───────────────────────────────

_DOMINIO_PROHIBIDO = (
    "cobro",
    "autónomo",
    "autonomo",
    "factura",
    "aeat",
    "irpf",
    "verifactu",
    "gmail",
    "calendar",
    "jetson",
    "qwen",
    "loombit",
    "españ",
)


def test_esqueletos_son_blancos():
    for nombre in ("CLAUDE.md", "BRUJULA.md", "brujula_check.py"):
        texto = (KIT / nombre).read_text(encoding="utf-8").lower()
        sucias = [w for w in _DOMINIO_PROHIBIDO if w in texto]
        assert not sucias, f"{nombre} no es blanco: contiene dominio {sucias}"


# ── 3) El kit está completo ───────────────────────────────────────────────────


def test_kit_completo():
    for f in (
        "brujula_check.py",
        "gobierno.workflow.yml",
        "INSTALAR.md",
        "CLAUDE.md",
        "BRUJULA.md",
        "pull_request_template.md",
        "CODEOWNERS",
    ):
        assert (KIT / f).exists(), f"falta {f} en el kit"
