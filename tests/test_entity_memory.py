"""
Tests de la memoria de empresa (EntityProfile): patrones de pago, IBANs
conocidos, gate antifraude, incidencias, búsqueda y persistencia.
"""

from loombit_operator.agent.memory import AgentMemory, EntityProfile


def _mem(tmp_path):
    return AgentMemory(store_path=tmp_path / "mem.json")


def test_upsert_creates_and_dedups(tmp_path):
    mem = _mem(tmp_path)
    mem.upsert_entity(
        "Construcciones Martínez", nif="B12345678", iban="ES12 3456 7890 1234 5678 9012"
    )
    mem.upsert_entity("Construcciones Martínez", nif="B12345678", iban="es1234567890123456789012")
    mem.upsert_entity("Construcciones Martínez", nif="B12345678", contact="luis@martinez.es")

    ents = mem.find_entity("martínez")
    assert len(ents) == 1
    prof = ents[0]
    assert prof.nif == "B12345678"
    assert prof.ibans == ["ES1234567890123456789012"]  # un único IBAN normalizado (sin duplicar)
    assert "luis@martinez.es" in prof.contacts


def test_payment_pattern_pays_late(tmp_path):
    mem = _mem(tmp_path)
    for d in (10, 12, 8):
        mem.record_payment("Talleres Beltrán", d)
    prof = mem.find_entity("beltrán")[0]
    assert prof.avg_days_late == 10.0
    assert prof.pays_late is True


def test_payment_pattern_on_time(tmp_path):
    mem = _mem(tmp_path)
    for d in (0, -2, 1):
        mem.record_payment("Buen Pagador SL", d)
    prof = mem.find_entity("buen pagador")[0]
    assert prof.pays_late is False


def test_iban_alert_new_iban_on_known_entity(tmp_path):
    mem = _mem(tmp_path)
    mem.upsert_entity("Suministros Norte", nif="A11111111", iban="ES11 1111 1111 1111 1111 1111")

    known = mem.iban_alert("Suministros Norte", "ES1111111111111111111111", nif="A11111111")
    assert known["is_known"] is True
    assert known["is_new_for_known_entity"] is False

    fraud = mem.iban_alert("Suministros Norte", "ES99 9999 9999 9999 9999 9999", nif="A11111111")
    assert fraud["is_known"] is False
    assert fraud["is_new_for_known_entity"] is True  # → bloquear y verificar


def test_iban_alert_unknown_entity_not_flagged(tmp_path):
    mem = _mem(tmp_path)
    alert = mem.iban_alert("Nuevo Proveedor", "ES22 2222 2222 2222 2222 2222")
    # Sin IBANs previos no hay nada que comparar: no es señal de fraude.
    assert alert["is_new_for_known_entity"] is False


def test_is_known_iban_normalises(tmp_path):
    mem = _mem(tmp_path)
    mem.upsert_entity("X SL", iban="ES12 3456 7890 1234 5678 9012")
    assert mem.is_known_iban("X SL", "es1234567890123456789012") is True
    assert mem.is_known_iban("X SL", "ES00 0000") is False


def test_incident_and_persistence(tmp_path):
    mem = _mem(tmp_path)
    mem.upsert_entity("Cliente Conflictivo", nif="C99999999")
    mem.add_entity_incident("Cliente Conflictivo", "Disputa por factura 2026/0042", nif="C99999999")

    # Releer desde disco: la entidad y la incidencia persisten.
    mem2 = AgentMemory(store_path=tmp_path / "mem.json")
    prof = mem2.find_entity("conflictivo")[0]
    assert len(prof.incidents) == 1
    assert "Disputa" in prof.incidents[0]["note"]


def test_context_block_lists_companies_to_watch(tmp_path):
    mem = _mem(tmp_path)
    for d in (15, 20, 18):
        mem.record_payment("Moroso SA", d)
    block = mem.to_context_block()
    assert "Empresas a vigilar" in block
    assert "Moroso SA" in block


def test_entity_profile_roundtrip():
    prof = EntityProfile(name="Acme", nif="B1", ibans=["ES1"], payments=[3, 9])
    again = EntityProfile.from_dict(prof.to_dict())
    assert again.name == "Acme"
    assert again.payments == [3, 9]
