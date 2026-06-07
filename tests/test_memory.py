"""
Tests de confirmación — agent/memory.py

Verifican que la memoria:
  1. Se crea desde cero con valores por defecto
  2. Añade contactos sin duplicados
  3. Registra historial sin límite
  4. Guarda y aprende procedimientos
  5. Registra propuestas del propio agente
  6. Persiste en disco y se recarga entre instancias
  7. Genera un bloque de contexto correcto para el LLM
  8. El endpoint GET /agent/memory devuelve el snapshot real

Estado: 🟡 — tests unitarios con store temporal. No requieren servicio externo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_store(tmp_path: Path):
    """Devuelve una ruta temporal para el store de memoria."""
    return tmp_path / "agent_memory.json"


@pytest.fixture
def mem(tmp_store: Path):
    """Instancia de AgentMemory con store temporal (no contamina runtime/local/)."""
    from loombit_operator.agent.memory import AgentMemory

    return AgentMemory(store_path=tmp_store)


# ── 1. Creación desde cero ────────────────────────────────────────────────────


def test_memory_creates_default_owner(mem):
    assert mem.owner["name"] == "Fernando"
    assert mem.owner["email"] == "fernando.ruizasenjo@gmail.com"
    assert mem.owner["company"] == "LoomBit Software Inc."


def test_memory_starts_empty(mem):
    assert mem.contacts == []
    assert mem.history == []
    assert mem.procedures == {}
    assert mem.proposals == []


# ── 2. Contactos sin duplicados ───────────────────────────────────────────────


def test_add_contact(mem):
    mem.add_contact("Jana Wall", "jana@acme.com", company="Acme", role="CEO")
    assert len(mem.contacts) == 1
    c = mem.contacts[0]
    assert c.name == "Jana Wall"
    assert c.email == "jana@acme.com"


def test_contact_deduplication_by_email(mem):
    mem.add_contact("Jana Wall", "jana@acme.com", company="Acme")
    mem.add_contact("Jana Wall Updated", "JANA@ACME.COM")  # case-insensitive
    assert len(mem.contacts) == 1
    assert mem.contacts[0].name == "Jana Wall Updated"


def test_add_multiple_contacts(mem):
    mem.add_contact("Jana Wall", "jana@acme.com")
    mem.add_contact("Paco López", "paco@empresa.es")
    assert len(mem.contacts) == 2


def test_find_contact_by_name(mem):
    mem.add_contact("Jana Wall", "jana@acme.com", company="Acme Corp")
    results = mem.find_contact("jana")
    assert len(results) == 1
    assert results[0].email == "jana@acme.com"


def test_find_contact_by_company(mem):
    mem.add_contact("Jana Wall", "jana@acme.com", company="Acme Corp")
    results = mem.find_contact("acme")
    assert len(results) == 1


# ── 3. Historial sin límite ───────────────────────────────────────────────────


def test_history_no_limit(mem):
    """El historial no tiene tope — crece indefinidamente."""
    for i in range(200):
        mem.add_history(f"Tarea {i}", f"Resultado {i}")
    assert len(mem.history) == 200


def test_history_most_recent_first(mem):
    mem.add_history("Primera tarea", "✅ OK")
    mem.add_history("Segunda tarea", "✅ OK")
    assert mem.history[0].task == "Segunda tarea"


def test_history_stores_tools_used(mem):
    mem.add_history("Enviar correo", "✅ OK", tools_used=["contacts_find", "gmail_send"])
    h = mem.history[0]
    assert "gmail_send" in h.tools_used


def test_history_stores_run_id(mem):
    mem.add_history("Tarea", "✅ OK", run_id="abc-123")
    assert mem.history[0].run_id == "abc-123"


# ── 4. Procedimientos aprendidos ──────────────────────────────────────────────


def test_add_procedure(mem):
    mem.add_procedure(
        task_type="enviar_correo",
        steps=["1. contacts_find para buscar email", "2. gmail_send para enviar"],
        tools=["contacts_find", "gmail_send"],
    )
    assert "enviar_correo" in mem.procedures


def test_procedure_increments_success_count(mem):
    mem.add_procedure("enviar_correo", steps=["paso 1"], tools=["gmail_send"])
    mem.add_procedure("enviar_correo", steps=["paso 1 mejorado"], tools=["gmail_send"])
    assert mem.procedures["enviar_correo"].success_count == 2


def test_procedure_updates_steps_on_repeat(mem):
    mem.add_procedure("enviar_correo", steps=["paso viejo"], tools=["gmail_send"])
    mem.add_procedure("enviar_correo", steps=["paso nuevo"], tools=["gmail_send"])
    assert mem.procedures["enviar_correo"].steps[0] == "paso nuevo"


def test_find_procedure_by_keyword(mem):
    mem.add_procedure("enviar_correo", steps=["paso 1"], tools=["gmail_send"])
    result = mem.find_procedure("enviar un correo a un cliente")
    assert result is not None
    assert result.task_type == "enviar_correo"


# ── 5. Propuestas del agente ──────────────────────────────────────────────────


def test_add_proposal(mem):
    mem.add_proposal(
        issue="No puedo leer adjuntos de email",
        suggestion="Añadir tool gmail_get_attachment",
        category="tool_missing",
    )
    assert len(mem.proposals) == 1
    p = mem.proposals[0]
    assert p.category == "tool_missing"
    assert "adjuntos" in p.issue


def test_multiple_proposals(mem):
    mem.add_proposal("Issue 1", "Suggestion 1", "tool_missing")
    mem.add_proposal("Issue 2", "Suggestion 2", "behavior")
    assert len(mem.proposals) == 2
    # Más reciente primero
    assert mem.proposals[0].issue == "Issue 2"


# ── 6. Persistencia real en disco ─────────────────────────────────────────────


def test_persistence_across_instances(tmp_store: Path):
    """
    CONFIRMACIÓN 100%: los datos sobreviven entre instancias distintas.
    Simula el cierre y reapertura del servidor.
    """
    from loombit_operator.agent.memory import AgentMemory

    # Sesión 1: guardar datos
    m1 = AgentMemory(store_path=tmp_store)
    m1.add_contact("Jana Wall", "jana@acme.com", company="Acme", role="CEO")
    m1.add_history("Enviar informe a Jana", "✅ Correo enviado", tools_used=["gmail_send"])
    m1.add_procedure("enviar_correo", steps=["contacts_find", "gmail_send"], tools=["gmail_send"])
    m1.add_proposal("Falta tool para leer correos", "Implementar gmail_read", "tool_missing")

    # Verificar que el fichero se creó en disco
    assert tmp_store.exists(), "El fichero agent_memory.json no se creó en disco"
    raw = json.loads(tmp_store.read_text(encoding="utf-8"))
    assert len(raw["contacts"]) == 1
    assert len(raw["history"]) == 1
    assert "enviar_correo" in raw["procedures"]
    assert len(raw["proposals"]) == 1

    # Sesión 2: cargar desde disco — simula reinicio del servidor
    m2 = AgentMemory(store_path=tmp_store)
    assert len(m2.contacts) == 1
    assert m2.contacts[0].name == "Jana Wall"
    assert m2.contacts[0].email == "jana@acme.com"
    assert len(m2.history) == 1
    assert m2.history[0].task == "Enviar informe a Jana"
    assert "enviar_correo" in m2.procedures
    assert len(m2.proposals) == 1
    assert m2.proposals[0].category == "tool_missing"


# ── 7. Bloque de contexto para el LLM ────────────────────────────────────────


def test_context_block_includes_owner(mem):
    block = mem.to_context_block()
    assert "Fernando" in block
    assert "LoomBit Software Inc." in block


def test_context_block_includes_contacts(mem):
    mem.add_contact("Jana Wall", "jana@acme.com")
    block = mem.to_context_block()
    assert "Jana Wall" in block
    assert "jana@acme.com" in block


def test_context_block_includes_history(mem):
    mem.add_history("Enviar informe", "✅ OK")
    block = mem.to_context_block()
    assert "Enviar informe" in block


def test_context_block_includes_procedure_hint(mem):
    mem.add_procedure("enviar_correo", steps=["paso 1"], tools=["gmail_send"])
    block = mem.to_context_block(task_hint="enviar un correo a Jana")
    assert "enviar_correo" in block or "Procedimiento" in block


def test_context_block_empty_when_no_data(tmp_store: Path):
    """Si no hay datos relevantes, el bloque sólo tiene la cabecera del owner."""
    from loombit_operator.agent.memory import AgentMemory

    m = AgentMemory(store_path=tmp_store)
    # Limpiar el owner para que no haya nada
    m._data["owner"] = {}
    block = m.to_context_block()
    # Sin owner, sin contactos, sin historial: el bloque puede estar vacío o muy corto
    assert len(block) < 100


# ── 8. Snapshot para el endpoint /agent/memory ───────────────────────────────


def test_snapshot_structure(mem):
    mem.add_contact("Jana Wall", "jana@acme.com")
    mem.add_history("Tarea test", "✅ OK")
    snap = mem.snapshot()

    assert snap["contacts_count"] == 1
    assert snap["history_count"] == 1
    assert "store_path" in snap
    assert "owner" in snap
    assert "preferences" in snap
    assert "procedures_count" in snap
    assert "proposals_count" in snap


def test_snapshot_history_recent_limited_to_20(mem):
    """El snapshot limita history_recent a 20, pero history_count es el total."""
    for i in range(50):
        mem.add_history(f"Tarea {i}", "✅ OK")
    snap = mem.snapshot()
    assert snap["history_count"] == 50
    assert len(snap["history_recent"]) == 20


# ── 9. Extracción de contactos desde steps ────────────────────────────────────


def test_extract_contacts_from_steps(mem):
    """Simula los steps de un run real que usó gmail_send."""

    class FakeStep:
        def __init__(self, tool_name, arguments, result="{}"):
            self.tool_name = tool_name
            self.arguments = arguments
            self.result = result

    steps = [
        FakeStep(
            "contacts_find",
            {},
            result='{"contacts": [{"name": "Jana Wall", "email": "jana@acme.com"}]}',
        ),
        FakeStep("gmail_send", {"to": "jana@acme.com", "subject": "Informe"}, result="{}"),
    ]

    added = mem.extract_contacts_from_steps(steps)
    assert added >= 1
    contacts = mem.find_contact("jana")
    assert len(contacts) == 1


# ── 10. Tool propose_improvement registrada ───────────────────────────────────


def test_propose_improvement_tool_registered():
    """La tool propose_improvement debe estar en el registry global."""
    from loombit_operator.tools import tool_registry

    tool = tool_registry.get("propose_improvement")
    assert tool is not None
    assert tool.name == "propose_improvement"


def test_propose_improvement_tool_writes_to_memory(tmp_store: Path, monkeypatch):
    """Cuando el agente llama propose_improvement, la propuesta va a memoria."""
    from loombit_operator.agent.memory import AgentMemory
    import loombit_operator.agent.memory as mem_module

    # Monkey-patch singleton para usar store temporal
    test_mem = AgentMemory(store_path=tmp_store)
    monkeypatch.setattr(mem_module, "_memory", test_mem)

    from loombit_operator.tools import tool_registry

    tool = tool_registry.get("propose_improvement")
    result_str = tool.execute(
        issue="No puedo leer adjuntos de correo",
        suggestion="Implementar tool gmail_get_attachment",
        category="tool_missing",
    )
    result = json.loads(result_str)
    assert result["ok"] is True

    # Verificar que quedó guardado en disco
    raw = json.loads(tmp_store.read_text(encoding="utf-8"))
    assert len(raw["proposals"]) == 1
    assert raw["proposals"][0]["category"] == "tool_missing"
