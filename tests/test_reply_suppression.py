"""
Wiring de la anticipación al flujo proactivo: la vigilancia de respuestas deja de preparar
borradores para los remitentes que el usuario SUELE IGNORAR (hábito) — menos ruido, fricción cero.
El efecto externo sigue requiriendo aprobación; esto solo decide qué NO molestar en preparar.
"""

from loombit_operator.habitos import HabitLedger
from loombit_operator.routine_executors import filtrar_silenciados


def test_filtra_remitentes_que_sueles_ignorar(tmp_path):
    h = HabitLedger(path=tmp_path / "h.json")
    for _ in range(4):
        h.registrar("respuesta", "news@x.com", "rechazada")  # patrón: sueles ignorar
    resp = [
        {"id": "1", "from": "Newsletter <news@x.com>"},
        {"id": "2", "from": "Ana <ana@x.com>"},
    ]
    a_preparar, silenciados = filtrar_silenciados(resp, h)
    assert [r["id"] for r in a_preparar] == ["2"]
    assert "news@x.com" in [s.lower() for s in silenciados]


def test_sin_patron_no_filtra_nada(tmp_path):
    h = HabitLedger(path=tmp_path / "h.json")
    resp = [{"id": "1", "from": "Quien Sea <x@x.com>"}]
    a_preparar, silenciados = filtrar_silenciados(resp, h)
    assert len(a_preparar) == 1 and silenciados == []
