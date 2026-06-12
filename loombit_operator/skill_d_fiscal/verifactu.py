"""
verifactu.py — arranque VeriFactu (D-88): de la factura al REGISTRO conforme, con huella ENCADENADA.

VeriFactu (RRSIF, AEAT) exige registros de facturación INALTERABLES y ENCADENADOS: cada registro lleva una
huella SHA-256 de sus campos + la huella del registro ANTERIOR (mismo patrón que la cadena de gobierno).
Esto genera el registro conforme y lo encadena; las cifras (importe) vienen de la factura por CÓDIGO, no del
LLM. Si faltan campos requeridos, se ABSTIENE (no inventa).

Es el ancla regulatoria de la cuña (D-86 / §EST-2, deadline 1-jul-2027 autónomos). Frontera DECLARADA: la
PRESENTACIÓN a la Sede AEAT (certificado/firma electrónica) queda FUERA de esta promesa — esto PREPARA el
registro inalterable, no lo presenta (eso necesita el certificado de Fernando).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from ..docs_intel import InvoiceFields

GENESIS = "0" * 64
# Campos que entran en la huella (orden fijo, estilo cadena canónica AEAT).
_CAMPOS_HUELLA = ("nif_emisor", "numero", "fecha", "importe_total", "huella_anterior")


@dataclass
class RegistroVerifactu:
    """Un registro de facturación VeriFactu (alta), con su huella encadenada al anterior."""

    nif_emisor: str
    numero: str
    fecha: str
    importe_total: float
    huella_anterior: str = GENESIS
    huella: str = ""

    def __post_init__(self) -> None:
        if not self.huella:
            self.huella = huella_registro(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nif_emisor": self.nif_emisor,
            "numero": self.numero,
            "fecha": self.fecha,
            "importe_total": self.importe_total,
            "huella_anterior": self.huella_anterior,
            "huella": self.huella,
        }


def _canonical(reg: RegistroVerifactu) -> str:
    """Cadena canónica de los campos (orden fijo) para hashear igual siempre."""
    return "&".join(f"{k}={getattr(reg, k)}" for k in _CAMPOS_HUELLA)


def huella_registro(reg: RegistroVerifactu) -> str:
    """SHA-256 de los campos del registro + la huella del anterior (encadenamiento, inalterabilidad)."""
    return hashlib.sha256(_canonical(reg).encode("utf-8")).hexdigest()


def registro_desde_factura(
    inv: InvoiceFields, nif_emisor: str, huella_anterior: str = GENESIS
) -> tuple[RegistroVerifactu | None, list[str]]:
    """Construye el registro VeriFactu de una factura. Abstención honesta si faltan campos requeridos."""
    faltan = [
        c
        for c, v in (("numero", inv.numero), ("fecha", inv.fecha), ("importe_total", inv.total))
        if not v
    ]
    if not nif_emisor:
        faltan.append("nif_emisor")
    if faltan:
        return None, [
            f"Factura {inv.numero or 's/n'}: faltan campos VeriFactu {faltan} → no se registra "
            "(no se inventa)."
        ]
    reg = RegistroVerifactu(
        nif_emisor=nif_emisor,
        numero=str(inv.numero),
        fecha=str(inv.fecha),
        importe_total=float(inv.total),
        huella_anterior=huella_anterior,
    )
    return reg, []


def encadenar(
    facturas: list[InvoiceFields], nif_emisor: str, huella_inicial: str = GENESIS
) -> tuple[list[RegistroVerifactu], list[str]]:
    """Encadena una lista de facturas en registros VeriFactu (cada huella referencia la anterior)."""
    out: list[RegistroVerifactu] = []
    avisos: list[str] = []
    prev = huella_inicial
    for inv in facturas:
        reg, avs = registro_desde_factura(inv, nif_emisor, prev)
        avisos.extend(avs)
        if reg is not None:
            out.append(reg)
            prev = reg.huella
    return out, avisos


def verificar_cadena(registros: list[RegistroVerifactu]) -> list[str]:
    """Comprueba la inalterabilidad: alterar/reordenar un registro del pasado rompe la cadena."""
    errores: list[str] = []
    prev = GENESIS
    for i, r in enumerate(registros):
        if r.huella_anterior != prev:
            errores.append(f"registro {i} ({r.numero}): no encadena con el anterior")
        if r.huella != huella_registro(r):
            errores.append(f"registro {i} ({r.numero}): huella no cuadra (¿registro alterado?)")
        prev = r.huella
    return errores
