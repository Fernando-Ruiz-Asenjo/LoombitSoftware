"""Cableado del Playbook (ACE) en la Fábrica: la autoría y la reparación CONSULTAN sus reglas, y el
gate humano (aprobar/descartar) las REFUERZA. Deterministas: el coder es un stub que captura el
prompt; nada de LM Studio ni disco real (store en tmp_path)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from loombit_operator.fabrica.autoria import redactar
from loombit_operator.fabrica.modelos import BorradorTool, Necesidad, PropuestaSkill, Veredicto
from loombit_operator.fabrica.playbook import Playbook
from loombit_operator.fabrica.propuesta import PropuestaStore
from loombit_operator.fabrica.reparar import proponer_parche


class _Captura:
    """Stub de LLM que recuerda los mensajes que se le pasaron (para auditar el prompt)."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.msgs = None

    def chat(self, **kw):
        self.msgs = kw.get("messages")
        return SimpleNamespace(content=self.content)


def _pb(tmp_path: Path) -> Playbook:
    return Playbook(store_path=tmp_path / "pb.json")


def test_autoria_inyecta_reglas_del_playbook(tmp_path):
    pb = _pb(tmp_path)
    pb.aprender("MARCA_PB_AUTORIA: para días hábiles usa weekday", tags=["dias", "habiles"])
    payload = '{"nombre":"x","descripcion":"d","parametros":{},"source":"def x(): return 1","eval_source":""}'
    nec = Necesidad(titulo="crear tool de días hábiles entre dos fechas")

    cap = _Captura(payload)
    redactar(nec, llm=cap, playbook=pb)
    assert "MARCA_PB_AUTORIA" in json.dumps(cap.msgs, ensure_ascii=False)

    # sin playbook NO se inyecta nada (cero efecto colateral; backward-compatible)
    cap2 = _Captura(payload)
    redactar(nec, llm=cap2)
    assert "MARCA_PB_AUTORIA" not in json.dumps(cap2.msgs, ensure_ascii=False)


def test_reparar_inyecta_reglas_del_playbook(tmp_path):
    objetivo = tmp_path / "m.py"
    objetivo.write_text("x=1\n", encoding="utf-8")
    pb = _pb(tmp_path)
    pb.aprender("MARCA_PB_REPARA: devuelve el fichero completo", tags=["reparar", "fichero"])
    cap = _Captura("x = 1\n")
    proponer_parche(objetivo, "formatea el módulo", llm=cap, playbook=pb)
    assert "MARCA_PB_REPARA" in json.dumps(cap.msgs, ensure_ascii=False)


def test_gate_aprobar_refuerza_playbook(tmp_path):
    pb = _pb(tmp_path)
    pb.aprender("para IVA del 303 calcula en código con Decimal", tags=["iva", "303"])
    store = PropuestaStore(store_path=tmp_path / "p.json")
    prop = store.add(
        PropuestaSkill(
            necesidad=Necesidad(titulo="calcular el IVA del 303"),
            borrador=BorradorTool(nombre="x", descripcion="", parametros={}, source=""),
            veredicto=Veredicto(),
        )
    )
    store.aprobar(prop.id, "ok", playbook=pb)
    regla_iva = [r for r in pb.reglas if "303" in " ".join(r.tags)][0]
    assert regla_iva.helpful >= 2  # 1 al crear + ≥1 al reforzar por la aprobación
