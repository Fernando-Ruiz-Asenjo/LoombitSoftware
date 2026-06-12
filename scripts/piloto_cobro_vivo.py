"""
piloto_cobro_vivo.py — dispara el envío REAL de un recordatorio de cobro contra TU Loombit en vivo.

Un solo comando. Habla con el Loombit que tengas lanzado (por defecto http://127.0.0.1:8787) por su API:
comprueba OAuth, crea una factura vencida de prueba, coge su decisión de cobro y la APRUEBA con `via=gmail`
→ el correo sale de verdad por Gmail al DESTINO SEGURO del piloto (§SEG-4), nunca a un cliente. Imprime el
recibo (o el error con su causa). No calcula cifras ni usa el LLM: solo orquesta los endpoints.

Uso (con Loombit ya encendido y el OAuth de Google conectado):
    python scripts/piloto_cobro_vivo.py
    python scripts/piloto_cobro_vivo.py --base http://127.0.0.1:8787 --importe 1210 --dias 42
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from typing import NoReturn


def _fatal_url_error(url: str, reason: object) -> NoReturn:
    """Loombit no responde: imprime la causa y termina (esta rama nunca retorna)."""
    print(f"\n❌ No pude hablar con Loombit en {url}\n   ¿Está lanzado? ({reason})")
    sys.exit(2)


def _req(method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Host", "127.0.0.1")  # el middleware solo-local exige Host local
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(detail)
        except json.JSONDecodeError:
            return e.code, {"raw": detail}
    except urllib.error.URLError as e:
        _fatal_url_error(url, e.reason)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Envío real de un recordatorio de cobro (piloto en vivo)."
    )
    ap.add_argument("--base", default="http://127.0.0.1:8787", help="URL de tu Loombit")
    ap.add_argument("--importe", type=float, default=1210.0)
    ap.add_argument(
        "--dias", type=int, default=42, help="días que lleva vencida la factura de prueba"
    )
    ap.add_argument("--cliente", default="Cliente Demo SL")
    args = ap.parse_args(argv)
    base = args.base.rstrip("/")

    print(f"== Piloto de cobro en vivo contra {base} ==")

    # 1) OAuth de Google conectado
    st, status = _req("GET", f"{base}/skill-blanca/oauth/google/status")
    if not status.get("connected"):
        print(f"❌ Google OAuth no conectado (status={status}).")
        print("   Conéctalo primero: ver docs/OAUTH_GOOGLE_SETUP.md")
        return 2
    print("✅ Google OAuth conectado.")

    # 2) Factura vencida de prueba
    venc = (date.today() - timedelta(days=args.dias)).isoformat()
    st, cuenta = _req(
        "POST",
        f"{base}/cuentas",
        {"cliente": args.cliente, "importe": args.importe, "vencimiento": venc},
    )
    print(
        f"   factura de prueba: {args.cliente} · {args.importe} € · vence {venc} (id {cuenta.get('id')})"
    )

    # 3) La decisión de cobro pendiente de esa cuenta
    st, pend = _req("GET", f"{base}/cobros/pendientes")
    cid = next(
        (d["cuenta_id"] for d in pend.get("pendientes", []) if d["cuenta_id"] == cuenta.get("id")),
        "",
    )
    if not cid:
        print(
            f"❌ La cuenta no aparece como cobro vencido pendiente (pendientes={pend.get('count')})."
        )
        return 2

    # 4) APROBAR → envío real por Gmail al destino seguro
    st, out = _req("POST", f"{base}/cobros/aprobar", {"cuenta_id": cid, "via": "gmail"})
    print(f"\n-- POST /cobros/aprobar (via=gmail) → HTTP {st} --")
    print(json.dumps(out, indent=2, ensure_ascii=False))

    recibo = (out or {}).get("recibo", {})
    inner = recibo.get("recibo", {}) if isinstance(recibo, dict) else {}
    if st == 200 and recibo.get("via") == "gmail" and inner.get("message_id"):
        print(
            f"\n🟢 ENVIADO de verdad por Gmail a {recibo.get('destino')} · message_id={inner['message_id']}"
        )
        print(f"   recibo guardado: {inner.get('receipt_path', '(ver runtime/local/)')}")
        print("   → pega esta salida en el chat para registrar el 🟢.")
        return 0
    print(
        "\n🟠 No se confirmó el envío real. Revisa el detalle de arriba (token/scope/destino/writes)."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
