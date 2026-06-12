"""
auditoria_promesas.py — ¿el código hace lo que se PIDIÓ? (la confrontación contra la promesa).

Cada PROMESA = lo que pidió Fernando, bajado a CRITERIOS testeables. Una promesa **no es 🟢 hasta que
TODOS sus criterios tienen su prueba** (y el gate las pasa). Mientras falte uno → 🟠, y se corrige. Esto
impide bajarse el listón: no vale declarar una promesa floja para "pasar"; el listón es lo pedido.

Blindado y FUERA del alcance del agente (por construcción):
  - La spec (`docs/PROMESAS.jsonl`) vive bajo CODEOWNERS → el agente no la cambia sin tu review.
  - Tu FIRMA = tu Approve como auditor (no se puede falsificar; el agente no se aprueba a sí mismo).
  - Este check es obligatorio en CI → el agente no lo salta ni lo ablanda.

Frontera honesta:
  - Verifica que los criterios están PROBADOS, no que capturen del todo tu intención —eso lo firmas TÚ al
    aprobar la spec— ni que esté BIEN hecho (eso lo juzgan el subagente verificador + tú).
  - "Total" se mide contra los criterios escritos; cuando aparece un hueco, se añade un criterio (la spec
    crece). No finge demostrar la totalidad del universo.
Determinista, puro (la existencia del test es inyectable para testearlo).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
PROMESAS = ROOT / "docs" / "PROMESAS.jsonl"

ESTADOS = {"🟡", "🟠", "🟢"}  # contrato / parcial / hecho
_REQUERIDOS = {"id", "pedido", "criterios", "estado"}


def cargar(path: Path = PROMESAS) -> list[dict[str, Any]]:
    """Lee el registro de promesas (.jsonl). Lista vacía si no existe."""
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            out.append(json.loads(ln))
    return out


def existe_test(ref: object) -> bool:
    """¿Existe el test nombrado «ruta/al/test.py::nombre»? Comprueba que el fichero existe y define
    `def nombre`. Determinista, sin invocar pytest (eso lo hace el gate; aquí solo que la prueba EXISTE).
    """
    if not isinstance(ref, str) or "::" not in ref:
        return False
    fichero, _, nombre = ref.partition("::")
    p = ROOT / fichero
    if not p.exists():
        return False
    return bool(re.search(rf"\bdef\s+{re.escape(nombre)}\s*\(", p.read_text(encoding="utf-8")))


def validar_promesa(p: Any, existe: Callable[[object], bool] = existe_test) -> list[str]:
    """Confronta UNA promesa con sus pruebas. Devuelve la lista de fallos (vacía = cumple)."""
    errores: list[str] = []
    if not isinstance(p, dict):
        return ["la promesa debe ser un objeto"]
    pid = p.get("id", "?")
    faltan = _REQUERIDOS - set(p)
    if faltan:
        errores.append(f"[{pid}] faltan campos {sorted(faltan)}")
    estado = p.get("estado")
    if estado not in ESTADOS:
        errores.append(f"[{pid}] estado «{estado}» inválido (usa {sorted(ESTADOS)})")
    if not (isinstance(p.get("pedido"), str) and p["pedido"].strip()):
        errores.append(f"[{pid}] «pedido» vacío (¿qué se pidió exactamente?)")
    criterios = p.get("criterios")
    if not (isinstance(criterios, list) and criterios):
        errores.append(f"[{pid}] sin criterios: una promesa sin criterios testeables es humo")
        return errores
    for i, c in enumerate(criterios):
        if not (isinstance(c, dict) and isinstance(c.get("que"), str) and c["que"].strip()):
            errores.append(f"[{pid}] criterio {i}: «que» vacío")
            continue
        ref = c.get("test")
        if ref is not None and not existe(ref):
            errores.append(f"[{pid}] criterio «{c['que']}»: el test «{ref}» NO existe")
        if estado == "🟢" and ref is None:
            errores.append(
                f"[{pid}] criterio «{c['que']}» SIN test, pero la promesa está 🟢 "
                "(no puede ser 'hecho' sin probar TODOS los criterios)"
            )
    return errores


def auditar(path: Path = PROMESAS) -> list[str]:
    """Confronta TODAS las promesas. Lista de fallos (vacía = todas cumplen lo pedido o son honestas 🟡/🟠)."""
    fallos: list[str] = []
    for p in cargar(path):
        fallos += validar_promesa(p)
    return fallos


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description="¿El código hace lo pedido? Confronta promesas vs pruebas."
    ).parse_args(argv)
    fallos = auditar()
    if fallos:
        print(
            f"== PROMESAS SIN CUMPLIR: {len(fallos)} fallo(s) — el código no hace (aún) lo pedido =="
        )
        for f in fallos:
            print(f"  ❌ {f}")
        print(
            "  → corrige hasta que cada criterio tenga su prueba en verde, o baja el estado a 🟠."
        )
        return 1
    print("== promesas: cada criterio declarado tiene su prueba; los 🟢 están probados ✅ ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
