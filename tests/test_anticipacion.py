"""
Objetivo #4: niveles de ANTICIPACIÓN A0–A3 ("la autonomía que se gana"). Deterministas, derivados
del hábito. INVARIANTE: ningún nivel autoriza el envío externo — eso lo aprueba SIEMPRE el humano;
lo único que sube es cuánto se PREPARA y cuán arriba se pone. Ver docs/INVESTIGACION_*_2026.md (§3).
"""

from loombit_operator.anticipacion import (
    NIVELES,
    nivel_de,
    nivel_desde_habito,
    requiere_aprobacion_humana,
    transicion,
)
from loombit_operator.habitos import HabitLedger


def _hab(racha=0, veredicto="sin_patron"):
    return {"veredicto": veredicto, "racha_aceptadas": racha}


def test_niveles_por_racha():
    assert nivel_desde_habito(_hab(racha=0))["nivel"] == "A0"
    assert nivel_desde_habito(_hab(racha=1, veredicto="sueles_aceptar"))["nivel"] == "A1"
    assert nivel_desde_habito(_hab(racha=3, veredicto="sueles_aceptar"))["nivel"] == "A2"
    assert nivel_desde_habito(_hab(racha=5, veredicto="sueles_aceptar"))["nivel"] == "A3"


def test_sueles_ignorar_silencia_a_a0():
    assert nivel_desde_habito(_hab(racha=0, veredicto="sueles_ignorar"))["nivel"] == "A0"


def test_un_rechazo_baja_pero_no_a_cero_si_el_patron_es_positivo():
    # racha=0 (acaba de rechazar) pero el patrón de fondo sigue siendo 'sueles_aceptar' → A1
    # (sigue sugiriendo, deja de pre-redactar): se gana lento, se pierde rápido, sin quedarse mudo.
    assert nivel_desde_habito(_hab(racha=0, veredicto="sueles_aceptar"))["nivel"] == "A1"


def test_transicion_detecta_subida_y_bajada():
    assert transicion("A1", "A3")["sube"] is True
    assert transicion("A3", "A1")["sube"] is False
    assert transicion("A2", "A2") is None


def test_invariante_envio_externo_nunca_es_autonomo():
    # El techo duro está EN EL CÓDIGO: ningún nivel, ni A3, autoriza el envío sin humano.
    for n in NIVELES:
        assert requiere_aprobacion_humana(n) is True


def test_nivel_de_integra_con_el_ledger(tmp_path):
    h = HabitLedger(path=tmp_path / "h.json", racha_autonomia=5)
    for _ in range(5):
        h.registrar("respuesta", "javier@x.com", "aceptada")
    assert nivel_de(h, "respuesta", "javier@x.com")["nivel"] == "A3"
    h.registrar("respuesta", "javier@x.com", "rechazada")  # se pierde rápido
    assert nivel_de(h, "respuesta", "javier@x.com")["nivel"] == "A1"
