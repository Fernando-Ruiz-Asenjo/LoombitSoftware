"""
auditoria_cadena.py — CADENA DE GOBIERNO: el núcleo útil de «blockchain», sin red ni token (D-79).

Norma: el registro de gobierno (recibos de conducta, decisiones, gate verde, merges) **no se puede
reescribir en silencio**. Esto lo vuelve binario con lo ÚNICO de blockchain que aporta aquí: una **cadena
de hashes** (cada bloque lleva el SHA-256 del anterior). Si alguien EDITA, BORRA, REORDENA o INSERTA un
bloque del pasado, la cadena se rompe y este algoritmo pone el gate ROJO.

Lo que NO es (y por qué): nada de red P2P, consenso distribuido ni token. Eso resuelve «confiar entre
desconocidos sin autoridad central»; aquí la autoridad es GitHub + Fernando, a propósito. Una cadena
PÚBLICA además rompería el foso LOCAL (difundir datos). Y git ya es un Merkle DAG: esto lo complementa
para los RECIBOS de gobierno, anclando cada bloque a una prueba externa (`ref` = commit SHA / run de CI).

Frontera honesta: una cadena a prueba de manipulación de MENTIRAS sigue siendo mentiras. Esto hace el
registro INFORJABLE, no VERDADERO: cada bloque debe anclar a su prueba externa (`ref`). La verdad la sigue
dando el gate verde; la cadena solo impide borrar/alterar la historia sin que se note. Determinista, puro.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CADENA = ROOT / "docs" / "CADENA_GOBIERNO.jsonl"

GENESIS_PREV = "0" * 64
# Campos que entran en el hash (todo el bloque MENOS el propio `hash`).
_CAMPOS_HASH = ("seq", "ts", "tipo", "ref", "datos", "prev")


def _canonical(obj: Any) -> str:
    """Serialización determinista (claves ordenadas, sin espacios) para hashear igual siempre."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_bloque(bloque: dict[str, Any]) -> str:
    """SHA-256 del contenido del bloque (sin el campo `hash`). El hash sella seq+ts+tipo+ref+datos+prev."""
    cuerpo = {k: bloque.get(k) for k in _CAMPOS_HASH}
    return hashlib.sha256(_canonical(cuerpo).encode("utf-8")).hexdigest()


def crear_genesis(nota: str, ts: str) -> dict[str, Any]:
    """Bloque 0 de la cadena: su `prev` son ceros (no hay anterior)."""
    b: dict[str, Any] = {
        "seq": 0,
        "ts": ts,
        "tipo": "genesis",
        "ref": "",
        "datos": {"nota": nota},
        "prev": GENESIS_PREV,
    }
    b["hash"] = hash_bloque(b)
    return b


def siguiente_bloque(
    ultimo: dict[str, Any], tipo: str, ref: str, datos: Any, ts: str
) -> dict[str, Any]:
    """Encadena un bloque nuevo al `ultimo`: su `prev` = hash del último. `ref` = prueba externa
    (commit SHA / run de CI); `datos` = el recibo/decisión. El hash sella todo."""
    b: dict[str, Any] = {
        "seq": int(ultimo["seq"]) + 1,
        "ts": ts,
        "tipo": tipo,
        "ref": ref,
        "datos": datos,
        "prev": ultimo["hash"],
    }
    b["hash"] = hash_bloque(b)
    return b


def cargar(path: Path = CADENA) -> list[dict[str, Any]]:
    """Lee la cadena de un .jsonl (una línea = un bloque). Lista vacía si no existe."""
    if not path.exists():
        return []
    bloques: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            bloques.append(json.loads(ln))
    return bloques


def verificar_cadena(bloques: list[dict[str, Any]]) -> list[str]:
    """Comprueba la integridad: devuelve la lista de roturas (vacía = cadena íntegra).
    Caza edición, borrado, reordenado e inserción de cualquier bloque del pasado."""
    errores: list[str] = []
    prev_hash = GENESIS_PREV
    for i, b in enumerate(bloques):
        if b.get("seq") != i:
            errores.append(
                f"bloque {i}: seq {b.get('seq')} != {i} (¿borrado/reordenado/insertado?)"
            )
        esperado = hash_bloque(b)
        if b.get("hash") != esperado:
            errores.append(
                f"bloque {i} (seq {b.get('seq')}): hash no cuadra (¿editado el contenido?)"
            )
        if b.get("prev") != prev_hash:
            errores.append(f"bloque {i}: prev roto (no encadena con el anterior)")
        prev_hash = b.get("hash", "")
    return errores


def agregar(tipo: str, ref: str, datos: Any, ts: str, path: Path = CADENA) -> dict[str, Any]:
    """Encadena y PERSISTE un bloque nuevo al final del .jsonl. Si no hay cadena, crea el génesis primero."""
    bloques = cargar(path)
    if not bloques:
        gen = crear_genesis(
            "Cadena de gobierno de Loombit (D-79). Tamper-evident, local-first.", ts
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(_canonical(gen) + "\n")
        bloques = [gen]
    bloque = siguiente_bloque(bloques[-1], tipo, ref, datos, ts)
    with path.open("a", encoding="utf-8") as f:
        f.write(_canonical(bloque) + "\n")
    return bloque


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verifica la cadena de gobierno (tamper-evident).")
    p.add_argument("--add", nargs=3, metavar=("TIPO", "REF", "JSON"), help="encadena un bloque")
    p.add_argument("--ts", default="", help="timestamp ISO del bloque a añadir")
    args = p.parse_args(argv)
    if args.add:
        tipo, ref, datos_json = args.add
        bloque = agregar(tipo, ref, json.loads(datos_json), args.ts or "1970-01-01T00:00:00Z")
        print(f"encadenado seq={bloque['seq']} hash={bloque['hash'][:12]}…")
        return 0
    bloques = cargar()
    if not bloques:
        print("== cadena de gobierno: vacía (nada que verificar) ==")
        return 0
    errores = verificar_cadena(bloques)
    if errores:
        print(f"== CADENA DE GOBIERNO ROTA: {len(errores)} fallo(s) — historia MANIPULADA ==")
        for e in errores:
            print(f"  ❌ {e}")
        return 1
    print(f"== cadena de gobierno ÍNTEGRA: {len(bloques)} bloques encadenados, sin manipular ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
