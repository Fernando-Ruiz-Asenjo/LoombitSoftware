"""
routers/habitos.py — expone lo que Loombit ha APRENDIDO de los hábitos del usuario.

Transparencia = confianza: el usuario ve (y en el futuro podrá editar/desactivar) lo que el
sistema cree saber de él, con su nivel de ANTICIPACIÓN A0–A3. Honesto: si no hay datos, no
inventa patrones. Lectura local; nada sale de la máquina.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..anticipacion import nivel_desde_habito
from ..habitos import get_habits

router = APIRouter(prefix="/habitos", tags=["habitos"])


@router.get("")
def listar() -> dict:
    """Patrones fuertes aprendidos (sueles aceptar / sueles ignorar), cada uno con su nivel de
    anticipación. Lista vacía si Loombit aún no ha aprendido nada de ti."""
    h = get_habits()
    items = []
    for hab in h.resumen():
        niv = nivel_desde_habito(hab)
        items.append({**hab, "anticipacion": niv["nivel"], "etiqueta": niv["etiqueta"]})
    return {"count": len(items), "habitos": items}
