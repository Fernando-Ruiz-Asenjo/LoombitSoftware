"""
live_smoke.py — TEST EN VIVO de Loombit, automatizado y reproducible.

No mocks: ARRANCA el servidor FastAPI de verdad (uvicorn, en un cwd temporal aislado para no tocar tus
datos), espera a `/health`, y ejerce flujos REALES por HTTP de punta a punta. Cada paso es un aserto;
si algo no se comporta como se pide, sale != 0 y dice qué falló.

Es la pieza "EN VIVO" del gate canónico (`verify.py --live`): el comportamiento se prueba contra el
sistema corriendo, no contra la narración de nadie. Determinista (no usa el 14B). Lo confirma GitHub CI.

Uso: python scripts/live_smoke.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.environ.get("LOOMBIT_SMOKE_PORT", "8911"))
BASE = f"http://127.0.0.1:{PORT}"


def _arrancar(tmp: str) -> subprocess.Popen:
    """Lanza uvicorn con cwd aislado (runtime/local/ va a `tmp`, no a tus datos reales)."""
    env = {**os.environ, "PYTHONPATH": ROOT}
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "loombit_operator.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
            "--log-level",
            "warning",
        ],
        cwd=tmp,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _esperar_salud(timeout: float = 25.0) -> bool:
    """Sondea /health hasta que responde ok (arranque robusto, sin flakiness por timing)."""
    fin = time.time() + timeout
    while time.time() < fin:
        try:
            r = httpx.get(f"{BASE}/health", timeout=2.0)
            if r.status_code == 200 and r.json().get("status") == "ok":
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


class _Fallo(Exception):
    pass


def _check(cond: bool, msg: str, recibos: list[str]) -> None:
    if not cond:
        raise _Fallo(msg)
    recibos.append(f"OK · {msg}")


def _flujos() -> list[str]:
    """Flujos REALES end-to-end sobre el servidor vivo. Cada aserto es un recibo comprobable."""
    recibos: list[str] = []
    with httpx.Client(base_url=BASE, timeout=10.0) as c:
        # 1) salud
        _check(c.get("/health").json()["status"] == "ok", "GET /health = ok", recibos)

        # 2) sembrar un cobro vencido REAL en el store
        venc = (date.today() - timedelta(days=30)).isoformat()
        r = c.post(
            "/cuentas", json={"cliente": "SmokeTest SL", "importe": 1210.0, "vencimiento": venc}
        )
        _check(r.status_code == 200, "POST /cuentas crea la cuenta (200)", recibos)

        # 3) LD-3: generar decisiones desde los cobros vencidos
        r = c.post("/decisions/sembrar-cobros")
        _check(
            r.status_code == 200 and r.json()["creadas"] >= 1,
            "sembrar-cobros crea >=1 decisión",
            recibos,
        )

        # 4) LD-0/LD-1: la cola sale con su spec de UI GOBERNADA y VÁLIDA
        data = c.get("/decisions").json()
        _check(data["count"] >= 1, "GET /decisions: cola no vacía", recibos)
        _check(data["spec"]["type"] == "cola", "la cola trae una spec 'cola'", recibos)
        card = data["spec"]["items"][0]
        _check(card["type"] == "decision_card", "el item es un decision_card", recibos)
        # la spec que sale del backend pasa la validación del contrato cerrado (importada en vivo)
        sys.path.insert(0, ROOT)
        from loombit_operator.ui_spec import validate_spec  # noqa: E402

        ok, errores = validate_spec(data["spec"])
        _check(ok, f"la spec emitida es VÁLIDA contra el contrato ({errores})", recibos)
        did = data["decisions"][0]["id"]

        # 5) resolver 'posponer' NO dispara efecto (run_id vacío) y saca la decisión de la cola
        r = c.post(f"/decisions/{did}/resolve", json={"option_id": "posponer"}).json()
        _check(r["decision"]["status"] == "resuelta", "resolver marca 'resuelta'", recibos)
        _check(r["run_id"] == "", "posponer NO dispara efecto (run_id vacío)", recibos)
        _check(c.get("/decisions").json()["count"] == 0, "la decisión sale de la cola", recibos)

        # 6) idempotencia: re-sembrar no duplica
        _check(
            c.post("/decisions/sembrar-cobros").json()["creadas"] == 0,
            "sembrar es idempotente",
            recibos,
        )

        # 7) el contrato rechaza un verbo fuera del vocabulario (400)
        # (re-sembramos para tener una decisión viva que intentar resolver mal)
        c.post("/cuentas", json={"cliente": "Otra SL", "importe": 500.0, "vencimiento": venc})
        c.post("/decisions/sembrar-cobros")
        d2 = c.get("/decisions").json()["decisions"][0]["id"]
        r = c.post(f"/decisions/{d2}/resolve", json={"option_id": "borrar_todo"})
        _check(r.status_code == 400, "opción fuera del vocabulario → HTTP 400", recibos)
    return recibos


def main() -> int:
    print("== Loombit · TEST EN VIVO (servidor real, HTTP real) ==")
    with tempfile.TemporaryDirectory(prefix="loombit_smoke_") as tmp:
        proc = _arrancar(tmp)
        try:
            if not _esperar_salud():
                print("   FALLO: el servidor no respondió a /health a tiempo")
                return 1
            recibos = _flujos()
        except _Fallo as exc:
            print(f"   FALLO EN VIVO: {exc}")
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"   ERROR EN VIVO: {exc!r}")
            return 1
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    for r in recibos:
        print("  " + r)
    print(f"\n== TEST EN VIVO VERDE: {len(recibos)} recibos comprobados contra el servidor real ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
