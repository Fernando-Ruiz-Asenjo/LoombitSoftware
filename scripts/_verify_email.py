"""Verificacion puntual: 3 encargos de correo contra el 14B real. Muestra el correo FINAL
(sobre incluido) tal como se enviaria. NO envia: se queda en la aprobacion."""

import json
import re
import time

import httpx

from loombit_operator.skill_blanca_gmail import normalize_email_text

BASE = "http://127.0.0.1:8787"
TASKS = [
    "Escribe a Jana (jana.espinal@gmail.com) presentandome como nuevo contacto y proponiendo una breve llamada esta semana.",
    "Escribe a Carlos (carlos@example.com) para proponerle una reunion el jueves a las 10 sobre el presupuesto.",
    "Escribe a Talleres Gomez (info@talleresgomez.com) recordandoles con amabilidad que la factura F-2024-018 sigue pendiente de pago.",
]


def run_task(client, task):
    rid = client.post(f"{BASE}/agent/run", json={"task": task}).json()["id"]
    for _ in range(90):
        time.sleep(2)
        d = client.get(f"{BASE}/agent/runs/{rid}").json()
        if d["status"] in ("pending_approval", "pending_question", "completed", "failed"):
            return d
    return {"status": "timeout"}


def main():
    with httpx.Client(timeout=30) as client:
        for n, task in enumerate(TASKS, 1):
            d = run_task(client, task)
            print(f"\n{'='*70}\nENCARGO {n}: {task[:60]}...\n   status={d['status']}")
            pa = d.get("pending_approval") or {}
            action = pa.get("proposed_action", "")
            m = re.search(r"\{.*\}", action, re.S)
            if not m:
                print("   (sin propuesta)  ", d.get("error", ""))
                continue
            args = json.loads(m.group(0))
            print(f"   Para: {args.get('to')}")
            print(f"   Asunto: {args.get('subject')}")
            print("   --- CORREO (lo escribe el modelo) ---")
            for line in normalize_email_text(args.get("body", "")).splitlines():
                print(f"   | {line}")


if __name__ == "__main__":
    main()
