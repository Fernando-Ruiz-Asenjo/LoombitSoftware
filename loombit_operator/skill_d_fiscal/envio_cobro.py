"""
envio_cobro.py — el ENVÍO real del recordatorio de cobro, con GATE DE EFECTO (promesa `envio-cobro`).

Criterio SAGRADO: **no sale nada sin la aprobación humana** de la decisión. El cuerpo lo construye CÓDIGO
desde el plan (cifras deterministas) y se pasa por el guardia §14B-1 (`cifra_parser`): si el cuerpo llevara
un € que NO está en el plan, se BLOQUEA (no se manda un importe inventado). Tras enviar queda un RECIBO.

Por defecto escribe al OUTBOX local (`.eml`, sin credenciales). El envío real por Gmail es una función
INYECTADA (el adaptador `skill_blanca_gmail.send_email`), solo en el piloto en vivo (🟡→🟢). En dev/seguridad
(§SEG-4) el destinatario es SEGURO (outbox / tu cuenta), nunca arbitrario. El LLM no interviene aquí.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..agent.cifra_parser import auditar_cifras


class EnvioBloqueado(RuntimeError):
    """Se intentó enviar sin aprobación, o con un € sin respaldo del plan (gate de efecto)."""


def _plan_cifras(decision: Any) -> list[float]:
    """Las cifras del plan determinista (el ledger contra el que se valida el cuerpo)."""
    pl = getattr(decision, "payload", {}) or {}
    plan = pl.get("plan", {}) or {}
    interes = (plan.get("interest", {}) or {}).get("amount", 0) or 0
    saldo = plan.get("outstanding", pl.get("importe", 0)) or 0
    fee = plan.get("fixed_compensation_eur", 0) or 0
    reclamable = round(float(saldo) + float(fee) + float(interes), 2)
    crudos = [pl.get("importe"), saldo, fee, interes, reclamable]
    return [float(v) for v in crudos if isinstance(v, (int, float)) and not isinstance(v, bool)]


def cuerpo_recordatorio(decision: Any) -> str:
    """Construye el cuerpo del recordatorio DESDE el plan — todas las cifras por código, no por el LLM."""
    pl = getattr(decision, "payload", {}) or {}
    cliente = pl.get("cliente", "")
    plan = pl.get("plan", {}) or {}
    saldo = float(plan.get("outstanding", pl.get("importe", 0)) or 0)
    dias = plan.get("overdue_days", 0)
    fee = float(plan.get("fixed_compensation_eur", 0) or 0)
    interes = float((plan.get("interest", {}) or {}).get("amount", 0) or 0)
    reclamable = round(saldo + fee + interes, 2)
    extra = ""
    if fee:
        extra += f", más {fee:.2f} € de compensación (art. 8, Ley 3/2004)"
    if interes:
        extra += f" y {interes:.2f} € de interés de demora"
    return (
        f"Estimado/a {cliente}:\n\n"
        f"Le recordamos que la factura está vencida (hace {dias} días). El saldo pendiente es "
        f"{saldo:.2f} €{extra}, lo que suma un total reclamable de {reclamable:.2f} €.\n\n"
        "Le agradeceríamos regularizar el pago. Un saludo."
    )


def _escribir_outbox(outbox_dir: Path, to: str, asunto: str, cuerpo: str) -> Path:
    outbox_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")
    p = outbox_dir / f"{ts}_recordatorio.eml"
    p.write_text(f"To: {to}\nSubject: {asunto}\n\n{cuerpo}\n", encoding="utf-8")
    return p


def enviar_recordatorio(
    decision: Any,
    aprobada: bool,
    *,
    to_seguro: str = "outbox-local",
    asunto: str = "Recordatorio de pago",
    cuerpo: str | None = None,
    enviar_fn: Callable[..., Any] | None = None,
    outbox_dir: Path | None = None,
) -> dict[str, Any]:
    """Envía el recordatorio SOLO si la decisión está aprobada. Devuelve el recibo. Lanza `EnvioBloqueado`
    si no hay aprobación o si el cuerpo lleva un € sin respaldo del plan. `enviar_fn` (Gmail real) es
    inyectable; por defecto escribe al outbox local (sin credenciales)."""
    # 1) GATE SAGRADO — sin aprobación humana, no sale NADA.
    if not aprobada:
        raise EnvioBloqueado(
            "no se envía: falta la aprobación humana de la decisión (gate de efecto)"
        )
    texto = cuerpo if cuerpo is not None else cuerpo_recordatorio(decision)
    # 3) Cifras por CÓDIGO — el cuerpo no puede llevar un € que no esté en el plan (§14B-1).
    rep = auditar_cifras(texto, ledger=_plan_cifras(decision))
    if not rep.ok:
        raise EnvioBloqueado(
            f"no se envía: el cuerpo tiene cifras sin respaldo del plan: {rep.motivos}"
        )
    # 4) Enviar y dejar RECIBO auditable.
    if enviar_fn is not None:  # piloto en vivo: adaptador Gmail inyectado
        recibo = enviar_fn(to=to_seguro, subject=asunto, body_text=texto)
        return {"enviado": True, "via": "gmail", "destino": to_seguro, "recibo": recibo}
    od = outbox_dir or Path("runtime/local/skill_blanca_connector_outbox")
    ruta = _escribir_outbox(od, to_seguro, asunto, texto)
    return {"enviado": True, "via": "outbox", "destino": to_seguro, "ruta": str(ruta)}
