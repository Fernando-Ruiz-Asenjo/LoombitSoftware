#!/usr/bin/env python3
"""
bridge_send.py — EL CABLE (lado remoto/nube): encola un comando para ESE PC y espera el resultado.

Deja un mensaje en `inbox/` de la rama-buzón `loombit-bridge`, lo empuja, y sondea `outbox/`
hasta que el ejecutor del PC (`bridge_local.py`) devuelva el resultado. Imprime el resultado.

Uso:
  python scripts/bridge_send.py --shell powershell "Get-Date"
  python scripts/bridge_send.py --shell bash "uname -a" --timeout 120
  python scripts/bridge_send.py --init     # crea/siembra la rama-buzón si no existe
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

BRIDGE_BRANCH = "loombit-bridge"
REPO = Path(__file__).resolve().parent.parent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=check)


def _worktree_dir() -> Path:
    return REPO.parent / ".loombit-bridge-wt-send"


def _seed_branch(wt: Path) -> None:
    _git(["worktree", "add", "--detach", str(wt), "HEAD"], REPO)
    _git(["checkout", "--orphan", BRIDGE_BRANCH], wt)
    _git(["rm", "-rf", "."], wt, check=False)
    for sub in ("inbox", "outbox"):
        (wt / sub).mkdir(parents=True, exist_ok=True)
        (wt / sub / ".keep").write_text("", encoding="utf-8")
    (wt / "README.md").write_text(
        "# loombit-bridge — buzón del CABLE\n\n"
        "Rama de datos efímera. `inbox/` = comandos de la nube; `outbox/` = resultados del PC.\n"
        "No mezclar con código. La gobierna scripts/bridge_send.py + scripts/bridge_local.py.\n",
        encoding="utf-8",
    )
    _git(["add", "-A"], wt)
    _git(["commit", "-m", "bridge: init buzón del cable"], wt)
    _git(["push", "-u", "origin", BRIDGE_BRANCH], wt)


def ensure_worktree(crear: bool = False) -> Path:
    wt = _worktree_dir()
    _git(["fetch", "origin", BRIDGE_BRANCH], REPO, check=False)
    remoto = _git(["ls-remote", "--heads", "origin", BRIDGE_BRANCH], REPO, check=False)
    existe = bool(remoto.stdout.strip())
    if (wt / ".git").exists():
        if existe:
            _git(["reset", "--hard", f"origin/{BRIDGE_BRANCH}"], wt, check=False)
        return wt
    if existe:
        _git(["worktree", "add", "-B", BRIDGE_BRANCH, str(wt), f"origin/{BRIDGE_BRANCH}"], REPO)
    elif crear:
        _seed_branch(wt)
    else:
        print(
            f"[cable] la rama '{BRIDGE_BRANCH}' no existe. Lanza primero: bridge_send.py --init",
            file=sys.stderr,
        )
        sys.exit(2)
    return wt


def _push_inbox(wt: Path, intentos: int = 4) -> None:
    _git(["add", "-A"], wt)
    _git(["commit", "-m", f"bridge: comando {_now()}"], wt, check=False)
    espera = 2
    for _ in range(intentos):
        if _git(["push", "origin", BRIDGE_BRANCH], wt, check=False).returncode == 0:
            return
        _git(["fetch", "origin", BRIDGE_BRANCH], wt, check=False)
        _git(["rebase", f"origin/{BRIDGE_BRANCH}"], wt, check=False)
        time.sleep(espera)
        espera *= 2
    print("[cable] no pude empujar el comando.", file=sys.stderr)
    sys.exit(1)


def enviar(cmd: str, shell: str, cwd: str, timeout: float, poll: float) -> int:
    wt = ensure_worktree()
    cid = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    msg = {"id": cid, "ts": _now(), "shell": shell, "cmd": cmd, "cwd": cwd}
    (wt / "inbox" / f"{cid}.json").write_text(
        json.dumps(msg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _push_inbox(wt)
    print(f"[cable] comando {cid} enviado. Esperando al PC (timeout {timeout:.0f}s)…")
    t0 = time.time()
    out = wt / "outbox" / f"{cid}.json"
    while time.time() - t0 < timeout:
        _git(["fetch", "origin", BRIDGE_BRANCH], wt, check=False)
        _git(["reset", "--hard", f"origin/{BRIDGE_BRANCH}"], wt, check=False)
        if out.exists():
            res = json.loads(out.read_text(encoding="utf-8"))
            print("─" * 60)
            print(f"approved={res.get('approved')}  exit={res.get('exit')}")
            if res.get("stdout"):
                print("── stdout ──\n" + res["stdout"])
            if res.get("stderr"):
                print("── stderr ──\n" + res["stderr"])
            return int(res.get("exit", 0) or 0)
        time.sleep(poll)
    print(
        f"[cable] sin respuesta en {timeout:.0f}s. ¿Está corriendo bridge_local.py en el PC?",
        file=sys.stderr,
    )
    return 1


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Cable remoto: envía un comando al PC y espera el resultado."
    )
    ap.add_argument("cmd", nargs="?", default="", help="comando a ejecutar en el PC")
    ap.add_argument("--shell", choices=["powershell", "cmd", "bash"], default="powershell")
    ap.add_argument("--cwd", default="", help="subdirectorio del repo donde ejecutar (relativo)")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--poll", type=float, default=4.0)
    ap.add_argument("--init", action="store_true", help="crea/siembra la rama-buzón y sale")
    args = ap.parse_args()

    if args.init:
        ensure_worktree(crear=True)
        print(f"[cable] rama-buzón '{BRIDGE_BRANCH}' lista en origin.")
        return
    if not args.cmd:
        ap.error("falta el comando (o usa --init)")
    sys.exit(enviar(args.cmd, args.shell, args.cwd, args.timeout, args.poll))


if __name__ == "__main__":
    main()
