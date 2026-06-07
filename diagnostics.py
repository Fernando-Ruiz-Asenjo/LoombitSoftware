"""
diagnostics.py -- verificacion completa de Skill W Loombit Pilot
Ejecutar: python diagnostics.py
"""

import sys
import json
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

print("=" * 60)
print("  Loombit Pilot -- Diagnostico de capacidades")
print(f"  Python {sys.version}")
print("=" * 60)

results = {}

# ── 1. Pillow ─────────────────────────────────────────────────────
print("\n[1/6] Pillow (screenshot) ...")
try:
    from PIL import ImageGrab

    img = ImageGrab.grab()
    w, h = img.size
    import io
    import base64

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_len = len(base64.b64encode(buf.getvalue()))
    print(f"  OK  {w}x{h} px, base64={b64_len} bytes")
    results["pillow"] = {"ok": True, "width": w, "height": h}
except Exception as e:
    print(f"  ERR {e}")
    traceback.print_exc()
    results["pillow"] = {"ok": False, "error": str(e)}

# ── 2. pynput mouse ───────────────────────────────────────────────
print("\n[2/6] pynput mouse (mover a 100,100) ...")
try:
    from pynput.mouse import Controller as MC

    m = MC()
    old_pos = m.position
    m.position = (100, 100)
    time.sleep(0.1)
    new_pos = m.position
    m.position = old_pos  # restaurar
    print(f"  OK  movido a {new_pos}")
    results["pynput_mouse"] = {"ok": True, "position": list(new_pos)}
except Exception as e:
    print(f"  ERR {e}")
    results["pynput_mouse"] = {"ok": False, "error": str(e)}

# ── 3. pynput keyboard ────────────────────────────────────────────
print("\n[3/6] pynput keyboard (tecla sin efectos visibles) ...")
try:
    from pynput.keyboard import Controller as KC, Key

    kb = KC()
    # Pulsamos Shift sin soltar -- inocuo
    kb.press(Key.shift)
    time.sleep(0.05)
    kb.release(Key.shift)
    print("  OK  Key.shift pulsado y soltado")
    results["pynput_keyboard"] = {"ok": True}
except Exception as e:
    print(f"  ERR {e}")
    results["pynput_keyboard"] = {"ok": False, "error": str(e)}

# ── 4. pywinauto ──────────────────────────────────────────────────
print("\n[4/6] pywinauto (Desktop UIA) ...")
try:
    import pywinauto

    print(f"  import ok -- version {pywinauto.__version__}")
    from pywinauto import Desktop

    d = Desktop(backend="uia")
    wins = d.windows()
    titles = [w.window_text() for w in wins[:5] if w.window_text()]
    print(f"  Desktop ok -- {len(wins)} ventanas. Primeras: {titles}")
    results["pywinauto"] = {"ok": True, "windows": len(wins), "sample": titles}
except Exception as e:
    print(f"  ERR {type(e).__name__}: {e}")
    traceback.print_exc()
    results["pywinauto"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

# ── 5. webbrowser ─────────────────────────────────────────────────
print("\n[5/6] webbrowser.open (URL test -- no abre nada) ...")
try:
    import webbrowser

    # Solo comprueba que la funcion existe y acepta el argumento
    print(f"  OK  webbrowser disponible: {webbrowser.get().name}")
    results["webbrowser"] = {"ok": True}
except Exception as e:
    print(f"  ERR {e}")
    results["webbrowser"] = {"ok": False, "error": str(e)}

# ── 6. Servidor Loombit ───────────────────────────────────────────
print("\n[6/6] Servidor Loombit en :8787 ...")
try:
    import httpx

    r = httpx.get("http://127.0.0.1:8787/health", timeout=3)
    print(f"  OK  /health -> {r.status_code} {r.json()}")
    results["server"] = {"ok": True, "status": r.status_code}

    # Estado computer-use
    r2 = httpx.get("http://127.0.0.1:8787/computer-use/status", timeout=3)
    cu = r2.json()
    print(f"  computer-use/status: {cu}")
    results["computer_use_status"] = cu

    # Screenshot via API
    r3 = httpx.post(
        "http://127.0.0.1:8787/loombit/pilot/execute",
        json={
            "objective": "diagnostics screenshot",
            "steps": [{"type": "screenshot"}],
            "dry_run": False,
            "operator_command": "diagnostics.py",
        },
        timeout=10,
    )
    receipt = r3.json()
    print(
        f"  pilot/execute screenshot: run_id={receipt.get('run_id')} error_halted={receipt.get('error_halted')}"
    )
    results["pilot_screenshot"] = receipt

except Exception as e:
    print(f"  ERR {e}")
    results["server"] = {"ok": False, "error": str(e)}

# ── Resumen ───────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  RESUMEN")
print("=" * 60)
summary = {
    "pillow": results.get("pillow", {}).get("ok"),
    "pynput_mouse": results.get("pynput_mouse", {}).get("ok"),
    "pynput_keyboard": results.get("pynput_keyboard", {}).get("ok"),
    "pywinauto": results.get("pywinauto", {}).get("ok"),
    "webbrowser": results.get("webbrowser", {}).get("ok"),
    "server": results.get("server", {}).get("ok"),
}
for k, v in summary.items():
    icon = "OK " if v else "ERR"
    print(f"  {icon}  {k}")

# Guardar resultado
out = Path("runtime/local/skill_pilot")
out.mkdir(parents=True, exist_ok=True)
ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
report_path = out / f"diagnostics_{ts}.json"
report_path.write_text(
    json.dumps(
        {"timestamp": ts, "summary": summary, "details": results}, indent=2, ensure_ascii=False
    ),
    encoding="utf-8",
)
print(f"\n  Informe guardado: {report_path}")
print("=" * 60)
