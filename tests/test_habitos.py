"""
Motor de hábitos (aprende del usuario): registra qué sugerencias acepta/rechaza y deriva,
de forma DETERMINISTA, si "sueles aceptar"/"sueles ignorar" algo, para anticipar y priorizar.
Fiel al foso: nada de efectos externos se auto-escala; sube la ANTICIPACIÓN, no el envío.
"""

import pytest

from loombit_operator.habitos import HabitLedger


def _l(tmp_path, **kw):
    return HabitLedger(path=tmp_path / "habitos.json", **kw)


def test_sin_datos_es_neutral(tmp_path):
    h = _l(tmp_path)
    v = h.habito("respuesta", "javier@x.com")
    assert v["n"] == 0
    assert v["veredicto"] == "sin_patron"
    assert h.silenciar("respuesta", "javier@x.com") is False
    assert h.prioridad("respuesta", "javier@x.com") == 0.5


def test_aceptar_repetido_marca_habito_y_prioriza(tmp_path):
    h = _l(tmp_path)
    for _ in range(4):
        h.registrar("respuesta", "javier@x.com", "aceptada")
    v = h.habito("respuesta", "javier@x.com")
    assert v["n"] == 4 and v["aceptadas"] == 4
    assert v["propension"] == 1.0
    assert v["veredicto"] == "sueles_aceptar"
    assert h.prioridad("respuesta", "javier@x.com") > h.prioridad("respuesta", "otro@x.com")


def test_rechazo_repetido_silencia(tmp_path):
    h = _l(tmp_path)
    for _ in range(4):
        h.registrar("respuesta", "news@spam.com", "rechazada")
    v = h.habito("respuesta", "news@spam.com")
    assert v["veredicto"] == "sueles_ignorar"
    assert h.silenciar("respuesta", "news@spam.com") is True


def test_autonomia_se_gana_con_aprobaciones_seguidas(tmp_path):
    h = _l(tmp_path, racha_autonomia=3)
    for _ in range(3):
        h.registrar("respuesta", "javier@x.com", "aceptada")
    assert h.habito("respuesta", "javier@x.com")["autonomia_sugerida"] is True
    # un rechazo ROMPE la racha → deja de sugerirse subir la anticipación (se gana, no se regala)
    h.registrar("respuesta", "javier@x.com", "rechazada")
    assert h.habito("respuesta", "javier@x.com")["autonomia_sugerida"] is False


def test_editada_cuenta_como_aceptacion_con_matiz(tmp_path):
    h = _l(tmp_path)
    for _ in range(3):
        h.registrar("respuesta", "ana@x.com", "editada")
    assert h.habito("respuesta", "ana@x.com")["veredicto"] == "sueles_aceptar"


def test_persistencia(tmp_path):
    p = tmp_path / "habitos.json"
    HabitLedger(path=p).registrar("respuesta", "a@b.com", "aceptada")
    assert HabitLedger(path=p).habito("respuesta", "a@b.com")["n"] == 1


def test_decision_invalida_se_rechaza(tmp_path):
    with pytest.raises(ValueError):
        _l(tmp_path).registrar("respuesta", "a@b.com", "quizas")


def test_resumen_lista_solo_patrones_fuertes(tmp_path):
    h = _l(tmp_path)
    for _ in range(3):
        h.registrar("respuesta", "javier@x.com", "aceptada")
    for _ in range(3):
        h.registrar("respuesta", "news@x.com", "rechazada")
    h.registrar("respuesta", "tibio@x.com", "aceptada")  # 1 sola → sin patrón
    res = h.resumen()
    sujetos = {r["sujeto"] for r in res}
    assert "javier@x.com" in sujetos and "news@x.com" in sujetos
    assert "tibio@x.com" not in sujetos
