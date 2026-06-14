"""
routers/verifactu.py — API del LIBRO VeriFactu (registros inalterables y encadenados).

GET /verifactu/registros  → los registros del libro (cada uno con su huella) + si la cadena es íntegra.
GET /verifactu/verificar  → comprueba la inalterabilidad del libro entero: {ok, errores}.

Solo LECTURA: el alta de registros la hace el intake (factura emitida → libro). Aquí no se calcula nada
con el LLM ni se presenta a la AEAT — es la vista auditable del libro y su verificación de integridad.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..skill_d_fiscal.verifactu_store import RegistroVerifactuStore

router = APIRouter(prefix="/verifactu", tags=["verifactu"])


@router.get("/registros")
def registros() -> dict:
    """Los registros del libro VeriFactu + si la cadena de huellas está íntegra (tamper-evident)."""
    store = RegistroVerifactuStore()
    errores = store.verificar()
    return {
        "registros": [r.to_dict() for r in store.list()],
        "count": len(store.list()),
        "integro": not errores,
    }


@router.get("/verificar")
def verificar() -> dict:
    """Comprueba la inalterabilidad del libro entero. `ok=False` + motivos si algo se manipuló."""
    errores = RegistroVerifactuStore().verificar()
    return {"ok": not errores, "errores": errores}
