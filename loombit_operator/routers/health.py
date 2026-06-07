"""Router de salud."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter

from .. import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "loombit-operator", "version": __version__}


@router.get("/health/python-env")
def python_env() -> dict:
    """Debug: info del entorno Python del proceso servidor."""
    import importlib.util
    import os

    win32api_found = importlib.util.find_spec("win32api")
    pywin32_sys32 = None
    for sp in sys.path:
        d = Path(sp) / "pywin32_system32"
        if d.is_dir():
            pywin32_sys32 = str(d)
            break

    # Lista los DLL directories activos (Python 3.8+)
    try:
        dll_dirs = [str(p) for p in os.DLL_PATH]  # type: ignore[attr-defined]
    except AttributeError:
        dll_dirs = ["os.DLL_PATH not available"]

    # Intentar import directo
    try:
        import win32api  # type: ignore
        win32_import = "OK"
    except Exception as e:
        win32_import = f"ERROR: {e}"

    try:
        import pywinauto  # type: ignore
        pywinauto_import = f"OK v{pywinauto.__version__}"
    except Exception as e:
        pywinauto_import = f"ERROR: {e}"

    return {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "win32api_spec": str(win32api_found),
        "pywin32_system32_dir": pywin32_sys32,
        "dll_dirs_active": dll_dirs,
        "win32api_import": win32_import,
        "pywinauto_import": pywinauto_import,
        "sys_path_sample": sys.path[:6],
    }


@router.post("/health/git-commit-push")
def git_commit_push(message: str = "chore: auto-commit from server") -> dict:
    """Hace git add -A, commit y push desde el proceso del servidor."""
    import os
    cwd = r"C:\Users\fernando\loombit-new"

    # Limpiar locks huerfanos antes de operar
    for lock in ["index.lock", "HEAD.lock", "objects/maintenance.lock"]:
        lock_path = Path(cwd) / ".git" / lock
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    steps = []

    for cmd in [
        ["git", "add", "-A"],
        ["git", "commit", "-m", message],
        ["git", "push"],
    ]:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
        steps.append({
            "cmd": " ".join(cmd[:2]),
            "rc": r.returncode,
            "out": r.stdout.strip()[:200],
            "err": r.stderr.strip()[:200],
        })
        if r.returncode not in (0, 1):  # 1 = nothing to commit, ok
            break

    return {"steps": steps, "ok": steps[-1]["rc"] in (0, 1)}
