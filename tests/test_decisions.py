"""
LD-0 «Loombit Decide» — la Decision de primera clase + la cola.

Golden del modelo + el store: encolar, listar, resolver (con la opción elegida), descartar,
persistencia round-trip y resiliencia a una fila corrupta (la cola es la pantalla de inicio: una
decisión malformada NO puede tumbarla).
"""

import json

import pytest

from loombit_operator.decisions import (
    Decision,
    DecisionKind,
    DecisionOption,
    DecisionStatus,
    DecisionStore,
    OptionKind,
    Risk,
)


def _store(tmp_path):
    return DecisionStore(store_path=tmp_path / "decisions.json")


def _cobro():
    return Decision(
        title="Reclamar cobro a Acme · 1.210 € VENCIDA",
        why="Vencida hace 12 días — el recordatorio ya está redactado.",
        kind=DecisionKind.COBRO,
        risk=Risk.MEDIO,
        reversible=True,
        options=[
            DecisionOption(id="aprobar", label="Aprobar y enviar", kind=OptionKind.APROBAR),
            DecisionOption(id="editar", label="Editar", kind=OptionKind.EDITAR),
            DecisionOption(id="posponer", label="Posponer", kind=OptionKind.POSPONER),
        ],
        payload={"importe": 1210.0, "cliente": "Acme"},
        source={"cuenta_id": "cc-1"},
    )


def test_encolar_y_listar(tmp_path):
    s = _store(tmp_path)
    s.add(_cobro())
    assert len(s.cola()) == 1
    # persiste y recarga
    assert len(_store(tmp_path).cola()) == 1


def test_cola_solo_pendientes(tmp_path):
    s = _store(tmp_path)
    a = s.add(_cobro())
    s.add(_cobro())
    s.resolve(a.id, "aprobar")
    cola = s.cola()
    assert len(cola) == 1
    assert all(d.status == DecisionStatus.PENDIENTE for d in cola)


def test_resolver_registra_opcion(tmp_path):
    s = _store(tmp_path)
    d = s.add(_cobro())
    s.resolve(d.id, "editar")
    got = _store(tmp_path).get(d.id)
    assert got.status == DecisionStatus.RESUELTA
    assert got.chosen_option == "editar"
    assert got.resolved_at


def test_resolver_opcion_desconocida_falla(tmp_path):
    s = _store(tmp_path)
    d = s.add(_cobro())
    with pytest.raises(ValueError):
        s.resolve(d.id, "no-existe")


def test_no_se_puede_resolver_dos_veces(tmp_path):
    s = _store(tmp_path)
    d = s.add(_cobro())
    s.resolve(d.id, "aprobar")
    with pytest.raises(ValueError):
        s.get(d.id).resolve("editar")


def test_descartar_saca_de_la_cola(tmp_path):
    s = _store(tmp_path)
    d = s.add(_cobro())
    s.dismiss(d.id)
    assert s.cola() == []
    assert _store(tmp_path).get(d.id).status == DecisionStatus.DESCARTADA


def test_roundtrip_serializacion(tmp_path):
    d = _cobro()
    got = Decision.from_dict(d.to_dict())
    assert got.title == d.title
    assert got.kind == DecisionKind.COBRO
    assert got.risk == Risk.MEDIO
    assert [o.id for o in got.options] == ["aprobar", "editar", "posponer"]
    assert got.options[0].kind == OptionKind.APROBAR
    assert got.payload["importe"] == 1210.0


def test_fila_corrupta_no_tumba_la_cola(tmp_path):
    s = _store(tmp_path)
    s.add(_cobro())
    # inyecta una fila corrupta directamente en el JSON
    raw = json.loads((tmp_path / "decisions.json").read_text(encoding="utf-8"))
    raw["decisions"].append({"id": "malo"})  # sin 'title' → from_dict lanza
    (tmp_path / "decisions.json").write_text(json.dumps(raw), encoding="utf-8")
    s2 = DecisionStore(store_path=tmp_path / "decisions.json")
    assert len(s2.cola()) == 1  # la buena sigue; la mala se omitió
    assert s2.load_error is not None  # el error de la fila mala quedó registrado, no silenciado
