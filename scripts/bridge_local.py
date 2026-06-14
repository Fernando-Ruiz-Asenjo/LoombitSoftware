#!/usr/bin/env python3
"""
bridge_local.py — EL CABLE (lado PC): conecta una sesión remota (la nube) con ESTE ordenador.

Modelo: un buzón sobre una rama git compartida (`loombit-bridge`). La sesión de la nube deja
COMANDOS en `inbox/`; este script los ejecuta EN ESTE PC y devuelve el resultado en `outbox/`,
por la misma rama. No hay puerto abierto, ni túnel, ni pantalla remota: solo git de por medio.

LEY FUNDACIONAL (CLAUDE.md): el LLM / lo remoto NUNCA está en el camino de control para nada
consecuente. Por eso, por defecto, **cada comando exige tu aprobación AQUÍ** (`--gate prompt`)
antes de ejecutarse: datos ≠ órdenes, gate humano para todo efecto. Modos de gate:

  --gate prompt     (defecto) te pregunta s/N por cada comando, mostrándolo entero.
  --gate allowlist  solo ejecuta comandos que casen con scripts/bridge_allowlist.txt (1 regex/línea).
  --gate off        sin gate (BAJO TU RESPONSABILIDAD; no recomendado).

Uso típico en el PC (desde la carpeta del repo):
  python scripts/bridge_local.py                 # bucle, pregunta por cada comando
  python scripts/bridge_local.py --once          # procesa lo pendiente y sale
  python scripts/bridge_local.py --gate allowlist
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BRIDGE_BRANCH = "loombit-bridge"
REPO = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=check)


def _worktree_dir() -> Path:
    return REPO.parent / ".loombit-bridge-wt"


def ensure_worktree() -> Path:
    """Prepara un worktree dedicado para la rama-buzón, sin tocar tu checkout de trabajo."""
    wt = _worktree_dir()
    _git(["fetch", "origin", BRIDGE_BRANCH], REPO, check=False)
    if (wt / ".git").exists():
        _git(["reset", "--hard", f"origin/{BRIDGE_BRANCH}"], wt, check=False)
    else:
        remoto = _git(["ls-remote", "--heads", "origin", BRIDGE_BRANCH], REPO, check=False)
        if not remoto.stdout.strip():
            print(
                f"[cable] la rama '{BRIDGE_BRANCH}' no existe en origin todavía.\n"
                f"        Pídele a la sesión de la nube que la cree (siembra el buzón) y reintenta.",
                file=sys.stderr,
            )
            sys.exit(2)
        _git(["worktree", "add", "-B", BRIDGE_BRANCH, str(wt), f"origin/{BRIDGE_BRANCH}"], REPO)
    (wt / "inbox").mkdir(parents=True, exist_ok=True)
    (wt / "outbox").mkdir(parents=True, exist_ok=True)
    return wt


def _load_allowlist() -> list[re.Pattern]:
    f = REPO / "scripts" / "bridge_allowlist.txt"
    if not f.exists():
        return []
    pats = []
    for linea in f.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#"):
            pats.append(re.compile(linea))
    return pats


def _aprobado(cmd: str, gate: str, allow: list[re.Pattern]) -> bool:
    if gate == "off":
        return True
    if gate == "allowlist":
        ok = any(p.search(cmd) for p in allow)
        if not ok:
            print(f"[cable] BLOQUEADO (no casa allowlist): {cmd!r}")
        return ok
    # gate == prompt
    print("\n" + "─" * 60)
    print("[cable] comando recibido de la sesión remota:")
    print(f"    {cmd}")
    try:
        resp = input("[cable] ¿ejecutar en ESTE PC? [s/N] ").strip().lower()
    except EOFError:
        print("[cable] sin TTY para preguntar; usa --gate allowlist o --gate off.", file=sys.stderr)
        return False
    return resp in ("s", "si", "sí", "y", "yes")


def _ejecutar(cmd: str, shell: str, cwd: str) -> dict:
    workdir = (REPO / cwd).resolve() if cwd else REPO
    if shell == "powershell":
        argv = ["powershell", "-NoProfile", "-Command", cmd]
    elif shell == "cmd":
        argv = ["cmd", "/c", cmd]
    else:  # bash / sh
        argv = ["bash", "-lc", cmd]
    try:
        p = subprocess.run(argv, cwd=str(workdir), text=True, capture_output=True, timeout=600)
        return {"exit": p.returncode, "stdout": p.stdout[-20000:], "stderr": p.stderr[-20000:]}
    except FileNotFoundError as exc:
        return {"exit": 127, "stdout": "", "stderr": f"shell no encontrado: {exc}"}
    except subprocess.TimeoutExpired:
        return {"exit": 124, "stdout": "", "stderr": "timeout (600s)"}


def _push_outbox(wt: Path, intentos: int = 4) -> bool:
    """Commitea y empuja el outbox, rebasando si la nube empujó nuevos comandos."""
    _git(["add", "-A"], wt)
    r = _git(["commit", "-m", f"bridge: resultados {_now()}"], wt, check=False)
    if "nothing to commit" in (r.stdout + r.stderr):
        return True
    espera = 2
    for _ in range(intentos):
        push = _git(["push", "origin", BRIDGE_BRANCH], wt, check=False)
        if push.returncode == 0:
            return True
        _git(["fetch", "origin", BRIDGE_BRANCH], wt, check=False)
        _git(["rebase", f"origin/{BRIDGE_BRANCH}"], wt, check=False)
        time.sleep(espera)
        espera *= 2
    print("[cable] no pude empujar el outbox tras varios intentos.", file=sys.stderr)
    return False


def procesar_una_vez(gate: str, allow: list[re.Pattern]) -> int:
    wt = ensure_worktree()
    inbox, outbox = wt / "inbox", wt / "outbox"
    hechos = {p.stem for p in outbox.glob("*.json")}
    pendientes = sorted(p for p in inbox.glob("*.json") if p.stem not in hechos)
    if not pendientes:
        return 0
    procesados = 0
    for f in pendientes:
        try:
            msg = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            (outbox / f.name).write_text(
                json.dumps(
                    {"id": f.stem, "ts": _now(), "exit": 1, "stderr": f"json inválido: {exc}"}
                ),
                encoding="utf-8",
            )
            procesados += 1
            continue
        cmd = msg.get("cmd", "")
        shell = msg.get("shell", "powershell")
        cwd = msg.get("cwd", "")
        if not _aprobado(cmd, gate, allow):
            res = {"exit": 126, "stdout": "", "stderr": "rechazado por el gate humano/allowlist"}
            res["approved"] = False
        else:
            print(f"[cable] ejecutando ({shell}) …")
            res = _ejecutar(cmd, shell, cwd)
            res["approved"] = True
        salida = {"id": msg.get("id", f.stem), "ts": _now(), "cmd": cmd, **res}
        (outbox / f.name).write_text(
            json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        procesados += 1
    _push_outbox(wt)
    return procesados


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Cable local: ejecuta comandos de la sesión remota en este PC."
    )
    ap.add_argument("--gate", choices=["prompt", "allowlist", "off"], default="prompt")
    ap.add_argument("--once", action="store_true", help="procesa lo pendiente y sale")
    ap.add_argument("--interval", type=float, default=5.0, help="segundos entre sondeos del buzón")
    args = ap.parse_args()

    allow = _load_allowlist() if args.gate == "allowlist" else []
    if args.gate == "allowlist" and not allow:
        print(
            "[cable] --gate allowlist pero scripts/bridge_allowlist.txt está vacío/ausente.",
            file=sys.stderr,
        )
        sys.exit(2)

    print(f"[cable] conectado al buzón '{BRIDGE_BRANCH}'. gate={args.gate}. Ctrl+C para salir.")
    if args.once:
        n = procesar_una_vez(args.gate, allow)
        print(f"[cable] procesados {n} comando(s).")
        return
    try:
        while True:
            n = procesar_una_vez(args.gate, allow)
            if n:
                print(f"[cable] procesados {n} comando(s); sigo a la escucha.")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[cable] cerrado.")


if __name__ == "__main__":
    main()
