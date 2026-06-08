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


@router.get("/health/selfcheck")
def selfcheck() -> dict:
    """Auto-verificación: corre el eval-set determinista y dice si el comportamiento esperado
    (taxonomía F1-F8) sigue verde. La UI/monitor lo consulta; se aplica solo, no a mano."""
    from ..selfcheck import run_selfcheck

    return run_selfcheck()


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


@router.get("/health/llm-debug")
def llm_debug() -> dict:
    """Prueba la llamada al LLM con y sin tools; devuelve el error exacto."""
    import httpx
    from ..tools import tool_registry

    base_url = "http://localhost:1234/v1"
    model = "qwen2.5-7b-instruct-1m"
    msgs = [{"role": "user", "content": "di hola en una palabra"}]

    results = {}
    with httpx.Client(timeout=15) as client:
        # Test 1: sin tools
        try:
            r = client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": msgs,
                    "max_tokens": 20,
                    "temperature": 0.1,
                },
            )
            results["no_tools"] = {"status": r.status_code, "body": r.text[:500]}
        except Exception as e:
            results["no_tools"] = {"error": str(e)}

        # Test 2: con tools (primeras 3)
        tools3 = tool_registry.to_openai()[:3]
        try:
            r = client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": msgs,
                    "max_tokens": 50,
                    "temperature": 0.1,
                    "tools": tools3,
                    "tool_choice": "auto",
                },
            )
            results["with_3_tools"] = {"status": r.status_code, "body": r.text[:500]}
        except Exception as e:
            results["with_3_tools"] = {"error": str(e)}

        # Test 3: con TODAS las tools
        all_tools = tool_registry.to_openai()
        try:
            r = client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": msgs,
                    "max_tokens": 512,
                    "temperature": 0.1,
                    "tools": all_tools,
                    "tool_choice": "auto",
                },
            )
            results["with_all_tools"] = {"status": r.status_code, "body": r.text[:500]}
        except Exception as e:
            results["with_all_tools"] = {"error": str(e)}

        # Test 4: con system prompt real del agente + tools
        from ..agent.prompts import build_system_prompt

        sys_prompt = build_system_prompt("administrativo")
        real_msgs = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": "hola"},
        ]
        try:
            r = client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": real_msgs,
                    "max_tokens": 512,
                    "temperature": 0.2,
                    "tools": all_tools,
                    "tool_choice": "auto",
                },
            )
            results["real_agent_call"] = {
                "status": r.status_code,
                "sys_prompt_len": len(sys_prompt),
                "body": r.text[:800],
            }
        except Exception as e:
            results["real_agent_call"] = {"error": str(e)}

    return results


@router.post("/health/lmstudio-load")
def lmstudio_load_model(
    model_id: str = "qwen2.5-7b-instruct-1m", context_length: int = 16384
) -> dict:
    """Carga un modelo en LM Studio con el contexto especificado vía REST API."""
    import httpx

    try:
        r = httpx.post(
            "http://localhost:1234/api/v0/models/load",
            json={"identifier": model_id, "config": {"contextLength": context_length}},
            timeout=60,
        )
        return {"status": r.status_code, "body": r.text[:1000]}
    except Exception as e:
        return {"error": str(e)}


@router.post("/health/git-commit-push")
def git_commit_push(message: str = "chore: auto-commit from server") -> dict:
    """Hace git add -A, commit y push desde el proceso del servidor."""

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
        steps.append(
            {
                "cmd": " ".join(cmd[:2]),
                "rc": r.returncode,
                "out": r.stdout.strip()[:200],
                "err": r.stderr.strip()[:200],
            }
        )
        if r.returncode not in (0, 1):  # 1 = nothing to commit, ok
            break

    return {"steps": steps, "ok": steps[-1]["rc"] in (0, 1)}
