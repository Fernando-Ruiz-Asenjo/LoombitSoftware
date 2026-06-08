"""
publish.py — un push que se VERIFICA contra el remoto (no se fía del eco).

Causa del 'pushed OK' falso: estaba en otra rama y `git push origin main` no subía nada; el eco
decía OK. Esto lo cierra: empuja la rama ACTUAL y comprueba que `origin/<rama>` apunta de verdad a
tu HEAD. Si no coincide (o estás en una rama que no es main sin querer), FALLA y lo dice.

Uso: `python scripts/publish.py`  (en vez de `git push` a pelo).
"""

from __future__ import annotations

import subprocess
import sys


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def main() -> int:
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    head = _git("rev-parse", "HEAD")
    if branch != "main":
        print(f"AVISO: estás en '{branch}', no en 'main'. Empujaré '{branch}'.")

    print(f"-> git push origin {branch} ...")
    subprocess.run(["git", "push", "origin", branch])

    _git("fetch", "-q", "origin")
    remoto = _git("rev-parse", f"origin/{branch}")

    if remoto == head and head:
        print(f"OK VERIFICADO: origin/{branch} = {head[:8]} (el remoto lo recibió).")
        return 0
    print(
        f"FALLO: el push NO llegó. origin/{branch}={remoto[:8] or '∅'} != HEAD={head[:8]}. "
        "NO está publicado — no lo des por hecho."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
