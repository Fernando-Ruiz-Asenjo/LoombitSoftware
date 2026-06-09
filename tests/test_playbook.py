"""Tests del Playbook de la Fábrica (ACE) — memoria de autoría con contadores helpful/harmful.

Deterministas, locales (store en tmp_path): no tocan runtime/local ni necesitan LM Studio.
"""

from __future__ import annotations

from pathlib import Path

from loombit_operator.fabrica.playbook import Playbook, ReglaPlaybook


def _pb(tmp_path: Path) -> Playbook:
    return Playbook(store_path=tmp_path / "pb.json")


def test_nace_con_reglas_fundacionales(tmp_path):
    pb = _pb(tmp_path)
    assert len(pb.reglas) >= 6
    # la memoria no nace tonta: el saber del arnés ya está
    assert any("eval" in r.contenido.lower() for r in pb.reglas)
    assert any("seguridad" in " ".join(r.tags) for r in pb.reglas)


def test_aprender_dedup_y_refuerza(tmp_path):
    pb = _pb(tmp_path)
    n0 = len(pb.reglas)
    r1 = pb.aprender("evita devolver medio fichero al reparar", tags=["reparar"], util=False)
    assert len(pb.reglas) == n0 + 1 and r1.harmful == 1 and r1.helpful == 0
    # mismo contenido → NO crea otra, refuerza la existente (delta, no reescribe)
    r2 = pb.aprender("Evita devolver medio fichero al reparar", util=False)
    assert len(pb.reglas) == n0 + 1 and r2.harmful == 2


def test_score_y_relevancia(tmp_path):
    pb = _pb(tmp_path)
    pb.aprender("para días hábiles usa date.weekday y cuenta lun-vie", tags=["dias", "habiles"])
    rel = pb.relevantes("crear una tool de días hábiles entre dos fechas", k=3)
    assert rel and any("hábiles" in r.contenido or "habiles" in " ".join(r.tags) for r in rel)
    bloque = pb.como_contexto("tool de días hábiles", k=3)
    assert bloque.startswith("REGLAS DE AUTORÍA APRENDIDAS")
    assert "weekday" in bloque


def test_regla_dañina_se_depreca_y_no_se_inyecta(tmp_path):
    pb = _pb(tmp_path)
    for _ in range(3):
        pb.aprender("usa recursión profunda sin límite para todo", tags=["zzdaño"], util=False)
    daninas = [r for r in pb.reglas if "recursión profunda" in r.contenido]
    assert daninas and daninas[0].deprecada is True
    # una regla depreciada NO aparece en la recuperación ni en el bloque de contexto
    rel = pb.relevantes("recursión profunda sin límite", k=5)
    assert all("recursión profunda" not in r.contenido for r in rel)


def test_reforzar_relevantes_marca_por_resultado(tmp_path):
    pb = _pb(tmp_path)
    pb.aprender("para IVA calcula en código con Decimal", tags=["iva", "dinero"])
    tocadas = pb.reforzar_relevantes("propuesta de cálculo de IVA aprobada", util=True, k=2)
    assert tocadas >= 1
    iva = [r for r in pb.reglas if "iva" in " ".join(r.tags)][0]
    assert iva.helpful >= 2  # 1 al crear + ≥1 al reforzar


def test_persiste_y_recarga(tmp_path):
    pb = _pb(tmp_path)
    pb.aprender("regla persistente de prueba", tags=["persist"], util=True)
    pb.aprender("regla persistente de prueba", util=True)  # helpful=2
    pb2 = Playbook(store_path=tmp_path / "pb.json")
    encontrada = [r for r in pb2.reglas if r.contenido == "regla persistente de prueba"]
    assert encontrada and encontrada[0].helpful == 2


def test_regla_serializa_ida_y_vuelta():
    r = ReglaPlaybook(contenido="x", tags=["a"], helpful=3, harmful=1, fuente="test")
    r2 = ReglaPlaybook.from_dict(r.to_dict())
    assert r2.contenido == "x" and r2.helpful == 3 and r2.harmful == 1 and r2.score == 2
