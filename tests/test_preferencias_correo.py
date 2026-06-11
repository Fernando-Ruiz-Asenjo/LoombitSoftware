"""
#2 (PRELUDE): aprender de las EDICIONES del usuario sobre un borrador. De forma DETERMINISTA (sin
LLM) se extraen señales del diff (longitud, firma, tratamiento) y se persisten como preferencia,
para que el próximo borrador salga más a tu gusto. El envío sigue requiriendo tu aprobación.
"""

from loombit_operator.agent.memory import AgentMemory
from loombit_operator.preferencias_correo import aplicar_a_memoria, aprender_de_edicion


def test_detecta_acortado():
    original = "Hola Ana, " + ("te escribo para detallarte todos los puntos del proyecto. " * 6)
    editado = "Hola Ana, te paso los puntos. Un saludo."
    assert aprender_de_edicion(original, editado)["longitud"] == "mas_corto"


def test_detecta_cambio_de_firma():
    original = "Hola,\nadjunto el informe.\nUn saludo,\nFernando Ruiz"
    editado = "Hola,\nadjunto el informe.\nUn saludo,\nFer"
    assert aprender_de_edicion(original, editado)["firma"] == "Fer"


def test_detecta_tuteo_frente_a_usted():
    original = "Estimado señor, le escribo para informarle. Quedo a su disposición."
    editado = "Hola, te escribo para contarte. Quedo a tu disposición."
    assert aprender_de_edicion(original, editado)["tratamiento"] == "tuteo"


def test_sin_cambios_relevantes_no_inventa_senales():
    txt = "Hola Ana, te paso los puntos. Un saludo, Fer"
    assert aprender_de_edicion(txt, txt) == {}


def test_aplicar_a_memoria_persiste_la_preferencia(tmp_path):
    m = AgentMemory(store_path=tmp_path / "m.json")
    aplicar_a_memoria(m, {"firma": "Fer", "tratamiento": "tuteo"})
    prefs = AgentMemory(store_path=tmp_path / "m.json").preferences
    assert prefs.get("firma") == "Fer"
    assert prefs.get("tratamiento") == "tuteo"
