"""Tests del AliasStore: el flywheel determinista (aprende de cobros confirmados por el humano).

Cubre: aprendizaje + procedencia, exclusión de conceptos sin nombre, alias más específico,
revocación auditada, persistencia por entidad, y el salto de vanguardia — que un alias
aprendido convierte una abstención (ambigüedad) en un match MEDIA en una conciliación posterior.
"""

from datetime import date
from decimal import Decimal

from loombit_operator.alias_resolver import AliasStore
from loombit_operator.conciliacion import ConfianzaTier, Movimiento, Pendiente, conciliar


def _store(tmp_path, entity="acme") -> AliasStore:
    return AliasStore(entity_id=entity, base_dir=tmp_path)


def _abono(importe: str, concepto: str) -> Movimiento:
    return Movimiento(
        fecha_operacion=date(2024, 1, 20),
        fecha_valor=date(2024, 1, 20),
        importe=Decimal(importe),
        concepto_comun="06",
        concepto_propio="002",
        num_documento="0000000002",
        referencia1="",
        referencia2="",
        conceptos=[concepto],
    )


def _pend(id_: str, importe: str, referencia: str = "", contraparte: str = "") -> Pendiente:
    return Pendiente(
        id=id_, importe=Decimal(importe), referencia=referencia, contraparte=contraparte
    )


def test_aprende_y_resuelve_con_procedencia(tmp_path):
    store = _store(tmp_path)
    alias = store.aprender("PAGO ACME GLOBAL", "ACME GLOBAL SL", actor="fernando")
    assert alias is not None
    assert alias.clave_tokens == ["ACME", "GLOBAL"]
    assert alias.confirmaciones == 1
    assert alias.procedencia[0]["actor"] == "fernando"
    assert store.canonico("TRANSFERENCIA DE ACME GLOBAL") == "ACME GLOBAL SL"


def test_concepto_sin_nombre_no_aprende(tmp_path):
    store = _store(tmp_path)
    # solo referencia numérica → nada nombrable que aprender (no inventa un alias frágil)
    assert store.aprender("TRANSFERENCIA REF 880055", "BETA SL") is None
    assert store.aprender("PAGO FACTURA FRA2024-007", "BETA SL") is None
    assert store.aliases() == []


def test_aprender_idempotente_incrementa_confirmaciones(tmp_path):
    store = _store(tmp_path)
    a1 = store.aprender("PAGO BETA SISTEMAS", "BETA SISTEMAS SL")
    a2 = store.aprender("ABONO BETA SISTEMAS", "BETA SISTEMAS SL")  # misma llave + canónico
    assert a1.id == a2.id
    assert a2.confirmaciones == 2
    assert len(store.aliases()) == 1


def test_alias_mas_especifico_gana(tmp_path):
    store = _store(tmp_path)
    store.aprender("GARCIA", "GARCIA UNO SL")
    store.aprender("GARCIA HERMANOS", "GARCIA HERMANOS SL")
    assert store.canonico("PAGO GARCIA HERMANOS") == "GARCIA HERMANOS SL"
    assert store.canonico("PAGO GARCIA SOLITO") == "GARCIA UNO SL"


def test_revocar_alias_desactiva_y_audita(tmp_path):
    store = _store(tmp_path)
    a = store.aprender("PAGO OMEGA", "OMEGA SL")
    assert store.canonico("TRANSFERENCIA OMEGA") == "OMEGA SL"
    assert store.revocar(a.id, actor="fernando") is True
    assert store.canonico("TRANSFERENCIA OMEGA") is None
    assert store.revocar(a.id) is False  # ya revocado
    # queda auditado, no borrado
    revocados = store.aliases(incluir_revocados=True)
    assert len(revocados) == 1
    assert revocados[0].revocado is True
    assert revocados[0].procedencia[-1]["accion"] == "revocado"


def test_persistencia_por_entidad(tmp_path):
    _store(tmp_path, "acme").aprender("PAGO DELTA", "DELTA SL")
    # otra entidad no ve el alias (aislamiento físico)
    assert _store(tmp_path, "globex").canonico("ABONO DELTA") is None
    # recarga de disco en la misma entidad: persiste
    assert _store(tmp_path, "acme").canonico("ABONO DELTA") == "DELTA SL"


def test_flywheel_alias_aprendido_desambigua_una_conciliacion_posterior(tmp_path):
    """El núcleo del flywheel: el humano confirma una vez que 'J. LOPEZ' es INMOBILIARIA COSTA;
    una conciliación posterior con dos importes iguales deja de abstenerse y propone MEDIA."""
    store = _store(tmp_path)
    store.aprender("TRANSFERENCIA DE J LOPEZ MARTINEZ REF 12", "INMOBILIARIA COSTA SL")

    mov = _abono("300.00", "TRANSFERENCIA DE J LOPEZ MARTINEZ REF 77")
    facturas = [
        _pend("f1", "300.00", referencia="A1", contraparte="INMOBILIARIA COSTA SL"),
        _pend("f2", "300.00", referencia="B2", contraparte="OTRO CLIENTE SA"),
    ]
    # sin el alias: dos importes iguales sin nada que los distinga → abstención
    assert conciliar([mov], facturas)[0].tier is ConfianzaTier.ABSTENCION
    # con el alias aprendido: el resolver afirma la contraparte → MEDIA sobre f1
    c = conciliar([mov], facturas, alias_resolver=store)[0]
    assert c.tier is ConfianzaTier.MEDIA
    assert c.pendiente.id == "f1"


def test_resolver_nunca_sube_a_alta(tmp_path):
    """Salvaguarda: el alias solo puede llegar a MEDIA; ALTA exige importe + referencia reales."""
    store = _store(tmp_path)
    store.aprender("TRANSFERENCIA DE J LOPEZ", "ACME SL")
    mov = _abono("100.00", "TRANSFERENCIA DE J LOPEZ")
    facturas = [_pend("f1", "100.00", referencia="A1", contraparte="ACME SL")]
    c = conciliar([mov], facturas, alias_resolver=store)[0]
    assert c.tier is ConfianzaTier.MEDIA  # no ALTA: el concepto no trae la referencia A1
