"""
Onboarding del dueño (la primera palabra del producto: 'Hola, Fernando'). Un usuario nuevo
arranca sin nombre → needs_onboarding; al conectar Google se deriva su nombre solo (zero-friction),
sin pisar nunca un nombre que el usuario ya puso. BLANCO: nada hardcodeado.
"""

from loombit_operator.agent.memory import AgentMemory
from loombit_operator.onboarding import derivar_owner_de_google, estado_onboarding


def test_usuario_nuevo_necesita_onboarding(tmp_path):
    m = AgentMemory(store_path=tmp_path / "m.json")
    est = estado_onboarding(m)
    assert est["needs_onboarding"] is True
    assert est["name"] == ""


def test_con_nombre_no_necesita_onboarding(tmp_path):
    m = AgentMemory(store_path=tmp_path / "m.json")
    m.set_owner(name="Fernando")
    est = estado_onboarding(m)
    assert est["needs_onboarding"] is False
    assert est["name"] == "Fernando"


def test_deriva_el_nombre_de_google_si_falta(tmp_path):
    m = AgentMemory(store_path=tmp_path / "m.json")
    o = derivar_owner_de_google(m, {"name": "Fernando Ruiz", "email": "fer@x.com"})
    assert o["name"] == "Fernando Ruiz"
    assert estado_onboarding(m)["needs_onboarding"] is False


def test_no_pisa_un_nombre_que_el_usuario_ya_puso(tmp_path):
    m = AgentMemory(store_path=tmp_path / "m.json")
    m.set_owner(name="Fer")
    derivar_owner_de_google(m, {"name": "Otro Nombre", "email": "x@x.com"})
    assert m.owner["name"] == "Fer"  # la verdad del usuario manda


def test_google_sin_nombre_no_inventa(tmp_path):
    m = AgentMemory(store_path=tmp_path / "m.json")
    derivar_owner_de_google(m, {"email": "x@x.com"})  # sin 'name'
    assert estado_onboarding(m)["needs_onboarding"] is True  # sigue sin nombre, honesto
