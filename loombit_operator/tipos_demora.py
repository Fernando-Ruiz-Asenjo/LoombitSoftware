"""
tipos_demora.py — tabla OFICIAL del tipo legal de interés de demora en operaciones comerciales
(Ley 3/2004, art. 7, redacción de la Ley 11/2013).

El tipo = «tipo de interés aplicado por el BCE a su más reciente operación principal de financiación
antes del primer día natural del semestre» + 8 puntos porcentuales. Lo publica la Secretaría General
del Tesoro y Financiación Internacional CADA semestre en el BOE.

Aquí se cachean los valores **publicados** (no se calcula ni se inventa nada): cada entrada lleva su
referencia de BOE. Verificado contra el BOE el 2026-06-08. Si una fecha cae en un semestre que no
está en esta tabla, la función se ABSTIENE (devuelve `rate_required=True`) — el humano verifica el
BOE vigente. Esto respeta la regla nº 1 (no mentir): una cifra legal solo se afirma con su fuente.

Para actualizar: cuando el Tesoro publique el tipo del próximo semestre, añadir la entrada con su BOE.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

# Margen legal fijo sobre el tipo del BCE (art. 7 Ley 3/2004). Invariante: tipo_pct == bce_pct + 8.
MARGEN_LEGAL_PUNTOS = 8.0

# (año, semestre) → tipo publicado, base BCE citada, referencia BOE.
# semestre: 1 = enero–junio · 2 = julio–diciembre.
TIPOS_PUBLICADOS: dict[tuple[int, int], dict[str, Any]] = {
    (2023, 1): {"tipo_pct": 10.50, "bce_pct": 2.50, "boe": "BOE-A-2022-24416"},
    (2023, 2): {"tipo_pct": 12.00, "bce_pct": 4.00, "boe": "BOE-A-2023-15221"},
    (2024, 1): {"tipo_pct": 12.50, "bce_pct": 4.50, "boe": "BOE-A-2023-26709"},
    (2024, 2): {"tipo_pct": 12.25, "bce_pct": 4.25, "boe": "BOE-A-2024-13089"},
    (2025, 1): {"tipo_pct": 11.15, "bce_pct": 3.15, "boe": "BOE-A-2024-27618"},
    (2025, 2): {"tipo_pct": 10.15, "bce_pct": 2.15, "boe": "BOE-A-2025-13217"},
    (2026, 1): {"tipo_pct": 10.15, "bce_pct": 2.15, "boe": "BOE-A-2025-27201"},
}


def _to_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"fecha no reconocida: {value!r}")


def semestre_de(d: str | date) -> tuple[int, int]:
    """(año, semestre) natural de una fecha. 1 = ene–jun, 2 = jul–dic."""
    d = _to_date(d)
    return (d.year, 1 if d.month <= 6 else 2)


def etiqueta_semestre(year: int, sem: int) -> str:
    return f"{sem}S{year}"


def tipo_vigente(d: str | date) -> dict[str, Any] | None:
    """Tipo legal de demora vigente en la fecha `d`, con su fuente BOE. None si no está publicado
    en la tabla (→ abstenerse)."""
    year, sem = semestre_de(d)
    fila = TIPOS_PUBLICADOS.get((year, sem))
    if fila is None:
        return None
    return {
        "semestre": etiqueta_semestre(year, sem),
        "tipo_pct": fila["tipo_pct"],
        "bce_pct": fila["bce_pct"],
        "boe": fila["boe"],
    }


def _fin_de_semestre(year: int, sem: int) -> date:
    return date(year, 6, 30) if sem == 1 else date(year, 12, 31)


def _segmentos(due: date, hoy: date) -> list[tuple[int, int, int]]:
    """Reparte los días devengados (due+1 … hoy, ambos inclusive) por semestre natural.
    Devuelve [(año, semestre, días), …]. Lista vacía si no hay días vencidos."""
    inicio = due + timedelta(days=1)
    if inicio > hoy:
        return []
    segmentos: list[tuple[int, int, int]] = []
    cursor = inicio
    while cursor <= hoy:
        year, sem = semestre_de(cursor)
        tramo_fin = min(_fin_de_semestre(year, sem), hoy)
        dias = (tramo_fin - cursor).days + 1
        segmentos.append((year, sem, dias))
        cursor = tramo_fin + timedelta(days=1)
    return segmentos


def interes_demora_legal(
    principal: float,
    due_date: str | date,
    today: str | date | None = None,
    *,
    base_dias: int = 365,
) -> dict[str, Any]:
    """
    Interés de demora de la Ley 3/2004 con el tipo OFICIAL publicado en el BOE, repartido por
    semestres (cada tramo a su tipo vigente). NO inventa: si algún tramo cae fuera de la tabla
    publicada, se ABSTIENE de dar un importe (`rate_required=True`) y nombra el semestre que falta.

    Devuelve el mismo contrato que `cobros.late_interest` más `tramos`/`fuente` para narrar con cita:
      {amount, rate_required, rate_pct, tramos:[{semestre,tipo_pct,dias,importe,boe}], fuente}
    """
    due = _to_date(due_date)
    hoy = _to_date(today) if today else date.today()

    if principal <= 0 or hoy <= due:
        return {"amount": 0.0, "rate_required": False, "rate_pct": None, "tramos": []}

    segmentos = _segmentos(due, hoy)
    tramos: list[dict[str, Any]] = []
    total = 0.0
    for year, sem, dias in segmentos:
        fila = TIPOS_PUBLICADOS.get((year, sem))
        if fila is None:
            # Tramo sin tipo publicado en la tabla → no se afirma un importe (regla nº 1).
            return {
                "amount": None,
                "rate_required": True,
                "rate_pct": None,
                "tramos": [],
                "note": (
                    f"El tramo {etiqueta_semestre(year, sem)} no está en la tabla de tipos "
                    "publicados: verificar el tipo legal de demora vigente en el BOE."
                ),
            }
        importe = round(principal * (fila["tipo_pct"] / 100.0) * (dias / base_dias), 2)
        total += importe
        tramos.append(
            {
                "semestre": etiqueta_semestre(year, sem),
                "tipo_pct": fila["tipo_pct"],
                "dias": dias,
                "importe": importe,
                "boe": fila["boe"],
            }
        )

    # rate_pct solo es un único número si todo el periodo cae en un mismo semestre.
    rate_pct = tramos[0]["tipo_pct"] if len(tramos) == 1 else None
    return {
        "amount": round(total, 2),
        "rate_required": False,
        "rate_pct": rate_pct,
        "tramos": tramos,
        "fuente": "Ley 3/2004 art. 7 (tipo BCE + 8 puntos); tipos publicados en el BOE.",
    }
