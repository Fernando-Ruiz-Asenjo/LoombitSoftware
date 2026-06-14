#!/usr/bin/env python3
"""
prueba_en_vivo.py — ARNÉS de PRUEBAS EN VIVO de Loombit (se ejecuta en el PC, contra el servidor real).

Lo conduce la sesión de la nube por EL CABLE (`bridge_send.py`). Ejercita las capacidades y flujos del
operador contra el Loombit REAL (FastAPI :8787 + 14B en LM Studio + OAuth Google conectado) y deja un
LEDGER de verdes/rojos/pendientes con recibo auditable.

Principios (Brújula):
  - NO aprueba ningún efecto externo. Lleva cada flujo hasta su gate (PENDING_APPROVAL) y lo APILA;
    Fernando aprueba después en la UI. Si manda correos, al destinatario de prueba acordado.
  - Las comprobaciones son DETERMINISTAS y conservadoras: fijan el ESTADO terminal esperado y los
    datos consecuentes (p. ej. el destinatario), no la prosa del 14B (que varía).
  - Recibo incremental: escribe cada resultado a `runtime/local/prueba_en_vivo/<ts>.json` según avanza,
    para poder recuperarlo aunque el cable corte por timeout.

Uso (en el PC):
  python scripts/prueba_en_vivo.py                       # batería completa
  python scripts/prueba_en_vivo.py --only hola,correo     # subconjunto (cabe en el timeout del cable)
  python scripts/prueba_en_vivo.py --list                 # lista los escenarios y sale
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
BASE_DEFAULT = "http://127.0.0.1:8787"
LM_DEFAULT = "http://127.0.0.1:1234"
CORREO_PRUEBA = "admin@construiaapp.com"  # acordado con Fernando: los correos de prueba van aquí

_TERMINALES = {"completed", "failed", "cancelled", "pending_approval", "pending_question"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Comprobadores deterministas (run dict → (ok: bool, motivo: str)) ──────────────────────────────
def _completado(run: dict) -> tuple[bool, str]:
    if run.get("status") != "completed":
        return False, f"esperaba completed, fue {run.get('status')}"
    if not (run.get("result") or "").strip():
        return False, "completed pero sin texto de resultado"
    return True, "completado con respuesta"


def _instantaneo(run: dict) -> tuple[bool, str]:
    ok, motivo = _completado(run)
    if not ok:
        return ok, motivo
    if run.get("step_count", 0) != 0:
        return False, f"esperaba 0 pasos (fast-path), hubo {run.get('step_count')}"
    return True, "respuesta social instantánea sin gastar el bucle del 14B"


def _gate_correo(run: dict) -> tuple[bool, str]:
    """El flujo de correo debe PARAR en el gate con el destinatario correcto (no auto-enviar)."""
    if run.get("status") != "pending_approval":
        return False, f"esperaba pending_approval (gate de envío), fue {run.get('status')}"
    blob = json.dumps(run.get("pending_approval", {}), ensure_ascii=False).lower()
    if CORREO_PRUEBA.lower() not in blob:
        return False, f"el gate no muestra el destinatario {CORREO_PRUEBA}: {blob[:200]}"
    return True, f"gate de envío disparado con destinatario {CORREO_PRUEBA} (apilado para aprobar)"


def _termina_sin_inventar(run: dict) -> tuple[bool, str]:
    """Abstención honesta: termina (completed) sin haber disparado un efecto externo a ciegas."""
    if run.get("status") not in ("completed", "pending_question"):
        return False, f"esperaba completed/pregunta honesta, fue {run.get('status')}"
    return True, "cerró con abstención/pregunta honesta, sin inventar un efecto"


# ── Batería de escenarios ─────────────────────────────────────────────────────────────────────────
ESCENARIOS: list[dict] = [
    {
        "nombre": "hola",
        "que_prueba": "Fricción cero: una cortesía se responde al instante sin bucle del 14B",
        "task": "hola",
        "check": _instantaneo,
    },
    {
        "nombre": "brief",
        "que_prueba": "Proactividad / lectura real (agenda+correos+cobros): daily_brief",
        "task": "¿en qué me centro hoy? dame mi resumen del día",
        "check": _completado,
    },
    {
        "nombre": "agenda",
        "que_prueba": "Lectura de calendario en vivo (OAuth Google): una PREGUNTA no crea evento",
        "task": "¿qué tengo en la agenda esta semana?",
        "check": _completado,
    },
    {
        "nombre": "correo",
        "que_prueba": "Redacción + gate de envío: para en PENDING_APPROVAL con el destinatario correcto",
        "task": (
            f"escribe un correo a {CORREO_PRUEBA} presentándote brevemente y diciendo que esto es "
            "una prueba en vivo de Loombit; fírmalo como Fernando"
        ),
        "check": _gate_correo,
    },
    {
        "nombre": "factura",
        "que_prueba": "Fiscal determinista: registrar una factura emitida (sin pedir el email del cliente)",
        "task": "registra una factura emitida a Acme SL de 1000 euros de base con IVA del 21%",
        "check": _completado,
    },
    {
        "nombre": "303",
        "que_prueba": "Fiscal: calcular el 303 del trimestre con las facturas registradas",
        "task": "calcula mi modelo 303 de este trimestre con las facturas que tengo registradas",
        "check": _completado,
    },
    {
        "nombre": "cobro",
        "que_prueba": "Motor de cobros (Ley 3/2004): preparar un cobro de una factura vencida",
        "task": "prepárame un cobro de 500 euros a Acme SL de una factura que venció hace 30 días",
        "check": _completado,
    },
    {
        "nombre": "abstencion",
        "que_prueba": "Abstención honesta: sin el fichero, NO inventa una conciliación",
        "task": "concíliame el extracto bancario de este mes",
        "check": _termina_sin_inventar,
    },
]


def _probe(base: str, lm: str) -> dict:
    out: dict = {"ts": _now()}
    with httpx.Client(timeout=10) as c:
        try:
            out["loombit_health"] = c.get(f"{base}/health").json()
        except Exception as e:
            out["loombit_health"] = f"DOWN: {e}"
        try:
            ids = [m.get("id") for m in c.get(f"{lm}/v1/models").json().get("data", [])]
            out["lm_models"] = ids
        except Exception as e:
            out["lm_models"] = f"DOWN: {e}"
        for ruta in ("/skill-blanca/oauth/google/status", "/skill-blanca/oauth/status"):
            try:
                out[f"oauth{ruta}"] = c.get(f"{base}{ruta}").json()
            except Exception as e:
                out[f"oauth{ruta}"] = f"ERR: {e}"
    return out


def _run_task(base: str, esc: dict, max_steps: int, timeout: float, poll: float) -> dict:
    """Lanza una tarea al agente y sondea hasta el estado terminal. Devuelve el resultado + check."""
    res: dict = {"nombre": esc["nombre"], "que_prueba": esc["que_prueba"], "task": esc["task"]}
    t0 = time.time()
    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(
                f"{base}/agent/run",
                json={"task": esc["task"], "max_steps": max_steps, "profile": "administrativo"},
            )
            r.raise_for_status()
            run = r.json()
            rid = run["id"]
            res["run_id"] = rid
            while run.get("status") not in _TERMINALES and time.time() - t0 < timeout:
                time.sleep(poll)
                run = c.get(f"{base}/agent/runs/{rid}").json()
    except Exception as e:
        res.update(ok=False, status="error", motivo=f"excepción conduciendo el run: {e}")
        res["segundos"] = round(time.time() - t0, 1)
        return res

    res["status"] = run.get("status")
    res["step_count"] = run.get("step_count")
    res["segundos"] = round(time.time() - t0, 1)
    res["result_excerpt"] = (run.get("result") or "")[:400]
    if run.get("status") == "pending_approval":
        res["pending_approval"] = run.get("pending_approval", {})
    if run.get("status") not in _TERMINALES:
        res.update(ok=False, motivo=f"sin terminar en {timeout:.0f}s (status={run.get('status')})")
        return res
    ok, motivo = esc["check"](run)
    res.update(ok=ok, motivo=motivo)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="Pruebas en vivo de Loombit (lado PC)")
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--lm", default=LM_DEFAULT)
    ap.add_argument("--only", default="", help="lista separada por comas de nombres de escenario")
    ap.add_argument("--max-steps", type=int, default=12)
    ap.add_argument("--timeout", type=float, default=180.0, help="por escenario")
    ap.add_argument("--poll", type=float, default=3.0)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        for e in ESCENARIOS:
            print(f"{e['nombre']:12} — {e['que_prueba']}")
        return 0

    seleccion = [e for e in ESCENARIOS if not args.only or e["nombre"] in args.only.split(",")]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    recibo_dir = ROOT / "runtime" / "local" / "prueba_en_vivo"
    recibo_dir.mkdir(parents=True, exist_ok=True)
    recibo = recibo_dir / f"{ts}.json"

    ledger: dict = {
        "ts": _now(),
        "base": args.base,
        "probe": _probe(args.base, args.lm),
        "escenarios": [],
    }
    recibo.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"== PRUEBAS EN VIVO Loombit · {ts} ==")
    print("probe:", json.dumps(ledger["probe"], ensure_ascii=False)[:600])
    sys.stdout.flush()

    for e in seleccion:
        print(f"\n-> {e['nombre']}: {e['task'][:80]} …")
        sys.stdout.flush()
        r = _run_task(args.base, e, args.max_steps, args.timeout, args.poll)
        ledger["escenarios"].append(r)
        recibo.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
        marca = "🟢" if r.get("ok") else ("🟠" if r.get("status") == "pending_approval" else "🔴")
        print(f"   {marca} [{r.get('status')}] {r.get('motivo')}  ({r.get('segundos')}s)")
        sys.stdout.flush()

    verdes = sum(1 for r in ledger["escenarios"] if r.get("ok"))
    print(f"\n== RESUMEN: {verdes}/{len(ledger['escenarios'])} verdes · recibo: {recibo} ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
