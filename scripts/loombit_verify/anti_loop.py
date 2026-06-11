#!/usr/bin/env python3
"""Ley ANTIBUCLE: ledger de intentos que fuerza un HALT cuando no hay progreso.

Implementa la LEY 2 (§ANTIBUCLE) del ALGORITMO UNIFICADO.

Idea
----
Cada objetivo (un bug a reparar, una auditoria) lleva un registro append-only
de sus intentos: una metrica medida por el oraculo (p.ej. nº de tests rojos) y
un hash del enfoque probado. Antes de autorizar OTRO intento, este modulo
decide CONTINUE o HALT segun reglas deterministas:

  L1 progreso: si la metrica no baja en 2 intentos seguidos -> HALT
  L2 no-repeticion: si el enfoque (hash) ya se probo -> HALT
  L4 limites duros: si intentos > MAX -> HALT

Asi el agente no puede quedarse en bucle infinito "dando vueltas a corregir":
la jaula se lo impide y obliga a un INFORME DE PARADA honesto (🟠/🔴).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

MAX_INTENTOS = 3
MAX_SIN_PROGRESO = 2


@dataclass
class Intento:
    n: int
    metrica: float  # menor = mejor (ej: nº de rojos, distancia al DoD)
    fix_hash: str


@dataclass
class Objetivo:
    objetivo_id: str
    intentos: list[Intento] = field(default_factory=list)


def _load(ledger: Path) -> dict:
    if ledger.exists():
        return json.loads(ledger.read_text(encoding="utf-8"))
    return {}


def _save(ledger: Path, data: dict) -> None:
    ledger.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def decidir(ledger: Path, objetivo_id: str, metrica: float, fix_hash: str) -> tuple[str, str]:
    """Registra un intento y devuelve (ACCION, motivo). ACCION in {CONTINUE, HALT}."""
    data = _load(ledger)
    obj = data.get(objetivo_id, {"objetivo_id": objetivo_id, "intentos": []})
    intentos = obj["intentos"]

    # L2 no-repeticion: enfoque ya probado
    if any(it["fix_hash"] == fix_hash for it in intentos):
        motivo = f"BUCLE: el enfoque {fix_hash[:8]} ya se probo (L2 no-repeticion)."
        _registrar(ledger, data, obj, metrica, fix_hash)
        return "HALT", motivo

    n = len(intentos) + 1
    _registrar(ledger, data, obj, metrica, fix_hash)
    intentos = obj["intentos"]

    # L4 limite duro de intentos
    if n > MAX_INTENTOS:
        return "HALT", f"LIMITE: {n} intentos > MAX_INTENTOS={MAX_INTENTOS} (L4)."

    # L1 progreso obligatorio: contar intentos seguidos sin mejora
    sin_progreso = 0
    mejor = float("inf")
    for it in intentos:
        if it["metrica"] < mejor:
            mejor = it["metrica"]
            sin_progreso = 0
        else:
            sin_progreso += 1
    if sin_progreso >= MAX_SIN_PROGRESO:
        return "HALT", (
            f"SIN PROGRESO: {sin_progreso} intentos seguidos sin bajar la metrica "
            f"(L1). Para y emite INFORME DE PARADA honesto."
        )

    return "CONTINUE", f"intento {n}/{MAX_INTENTOS}, metrica={metrica} (mejor={mejor})."


def _registrar(ledger: Path, data: dict, obj: dict, metrica: float, fix_hash: str) -> None:
    obj["intentos"].append(
        {"n": len(obj["intentos"]) + 1, "metrica": metrica, "fix_hash": fix_hash}
    )
    data[obj["objetivo_id"]] = obj
    _save(ledger, data)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Ledger antibucle: decide CONTINUE/HALT.")
    p.add_argument("--ledger", type=Path, default=Path(".loombit_anti_loop.json"))
    p.add_argument("--objetivo", required=True)
    p.add_argument("--metrica", type=float, required=True, help="menor = mejor")
    p.add_argument("--fix-hash", required=True, help="hash/id del enfoque probado")
    args = p.parse_args(argv)
    accion, motivo = decidir(args.ledger, args.objetivo, args.metrica, args.fix_hash)
    print(f"{accion}: {motivo}")
    return 0 if accion == "CONTINUE" else 3  # exit 3 = HALT (bloquea mas reintentos)


if __name__ == "__main__":
    raise SystemExit(main())
