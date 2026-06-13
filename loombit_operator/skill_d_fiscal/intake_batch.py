"""
intake_batch.py — Skill D Fiscal: subir una CARPETA de facturas → cuentas a cobrar + líneas de 303.

Promesa firmada (`docs/PROMESAS.jsonl` · intake-facturas): el usuario suelta una carpeta y, sin tocar
nada, salen sus cuentas a cobrar y las líneas del 303; las que no se pueden leer se LISTAN — no se inventan.

Construye sobre lo que ya existe, sin reinventar: `docs_intel` (extracción DETERMINISTA de campos por
regex — NO el LLM), `intake.linea_desde_factura` (303) y `cuentas_cobrar.cuenta_desde_factura` (cobros).
Idempotente por número de factura. Frontera declarada: los escaneados SIN texto (visión local) quedan
FUERA de esta promesa — se listan como abstención honesta, no se adivinan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..cuentas_cobrar import CuentasCobrarStore, cuenta_desde_factura
from ..docs_intel import extract_invoice_fields, extract_text_from_pdf
from ..expedientes import ExpedienteStore
from .intake import linea_desde_factura, liquidar_303_periodo, registrar_factura

_EXT_TEXTO = {".txt", ".text"}
_EXT_FACTURA = _EXT_TEXTO | {".pdf"}


@dataclass
class ResumenIntake:
    """Lo que salió de procesar la carpeta. Honesto: lo leído, lo abstenido (con motivo) y los avisos."""

    leidas: int = 0
    duplicadas: int = 0
    cuentas_creadas: int = 0
    lineas_303: int = 0
    abstenidas: list[dict[str, str]] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "leidas": self.leidas,
            "duplicadas": self.duplicadas,
            "cuentas_creadas": self.cuentas_creadas,
            "lineas_303": self.lineas_303,
            "abstenidas": self.abstenidas,
            "avisos": self.avisos,
        }


def _texto_de(path: Path) -> tuple[str, bool]:
    """Devuelve (texto, necesita_vision). PDF → capa de texto (pypdf); .txt → contenido; escaneado sin
    texto → ('', True) para que el llamante se abstenga (visión local, fuera de esta promesa)."""
    suf = path.suffix.lower()
    if suf == ".pdf":
        r = extract_text_from_pdf(path)
        return str(r.get("text") or ""), bool(r.get("needs_ocr"))
    if suf in _EXT_TEXTO:
        try:
            return path.read_text(encoding="utf-8"), False
        except OSError:
            return "", False
    return "", False


def _numeros_registrados(store_exp: ExpedienteStore) -> set[str]:
    """Números de factura ya intake-ados (para idempotencia: no duplicar)."""
    out: set[str] = set()
    for e in store_exp.list(kind="factura_intake"):
        n = str((e.data.get("fields") or {}).get("numero") or "")
        if n:
            out.add(n)
    return out


def intake_carpeta(
    carpeta: str | Path,
    store_exp: ExpedienteStore,
    store_cc: CuentasCobrarStore,
    sentido: str = "devengado",
    plazo_dias: int = 30,
) -> ResumenIntake:
    """Procesa TODA la carpeta de facturas (ventas por defecto: `sentido='devengado'`). Por cada factura
    legible: la registra (trazabilidad), saca su línea de 303 y su cuenta a cobrar. Las ilegibles o
    escaneadas se listan en `abstenidas` con su motivo — NUNCA se inventan. Idempotente por nº de factura.
    Las cifras vienen de `docs_intel` (regex determinista), no del LLM (Ley Fundacional / §14B-1).
    """
    r = ResumenIntake()
    ya = _numeros_registrados(store_exp)
    for path in sorted(Path(carpeta).glob("*")):
        if path.is_dir() or path.suffix.lower() not in _EXT_FACTURA:
            continue
        texto, necesita_vision = _texto_de(path)
        if necesita_vision:
            r.abstenidas.append(
                {
                    "fichero": path.name,
                    "motivo": "escaneado sin texto: necesita visión local (fuera de esta promesa)",
                }
            )
            continue
        inv = extract_invoice_fields(texto)
        if inv.missing:
            r.abstenidas.append(
                {"fichero": path.name, "motivo": f"campos faltantes {inv.missing}: revísala a mano"}
            )
            continue
        numero = inv.numero or ""
        if numero and numero in ya:
            r.duplicadas += 1
            continue
        ya.add(numero)
        r.leidas += 1
        registrar_factura(
            store_exp, inv, sentido, pdf_path=path if path.suffix.lower() == ".pdf" else None
        )
        linea, avisos = linea_desde_factura(inv, sentido)
        r.avisos.extend(avisos)
        if linea is not None:
            r.lineas_303 += 1
        cuenta = cuenta_desde_factura(
            proveedor=inv.proveedor,
            total=inv.total,
            sentido=sentido,
            numero=numero,
            vencimiento=inv.vencimiento,
            plazo_dias=plazo_dias,
        )
        if cuenta is not None:
            store_cc.add(cuenta)
            r.cuentas_creadas += 1
    return r


def intake_y_liquidar(
    carpeta: str | Path,
    store_exp: ExpedienteStore,
    store_cc: CuentasCobrarStore,
    periodo: str,
    sentido: str = "devengado",
    plazo_dias: int = 30,
) -> dict[str, Any]:
    """Un tirón (F-5): CARPETA de facturas → facturas registradas + cuentas a cobrar + 303 del periodo.

    Encadena `intake_carpeta` (puebla la plataforma) y `liquidar_303_periodo` (303 `PENDING_APPROVAL`).
    Las cifras vienen del CÓDIGO (regex determinista), las ilegibles van en `intake.abstenidas` —no se
    inventan—, y el 303 lo PRESENTA el humano (la IA solo prepara). Devuelve `{"intake": ..., "303": ...}`.
    """
    resumen = intake_carpeta(carpeta, store_exp, store_cc, sentido=sentido, plazo_dias=plazo_dias)
    exp, res = liquidar_303_periodo(store_exp, periodo)
    return {
        "intake": resumen.to_dict(),
        "303": {
            "expediente_id": exp.id,
            "status": exp.status.value,  # pending_approval: la IA NO presenta a la AEAT
            "resultado": str(res.resultado),
            "casillas": res.casillas,
            "avisos": res.avisos,
        },
    }
