"""
Destilación de reuniones acordadas en correo (el caso de Fernando: tenía un mail con David y una
reunión el jueves a las 09:00, y Loombit no lo sabía). Conservador y honesto: palabra de cita + día
reconocible; la hora es opcional; nada se inventa.
"""

from __future__ import annotations

from datetime import date

from loombit_operator.percepcion_correo import detectar_reuniones, dia_en, hora_en

# Un lunes, para que los días de la semana sean deterministas.
LUNES = date(2026, 6, 8)  # 2026-06-08 es lunes


def test_hora_en_formatos():
    assert hora_en("nos vemos a las 9") == "09:00"
    assert hora_en("la reunión es a las 09.00") == "09:00"
    assert hora_en("quedamos a las 9:30") == "09:30"
    assert hora_en("a las 5 de la tarde") == "17:00"
    assert hora_en("a las 9 de la mañana") == "09:00"
    assert hora_en("sin hora aquí") == ""


def test_dia_en_dia_de_la_semana():
    fecha, etiqueta = dia_en("hemos quedado el jueves", LUNES)
    assert fecha == "2026-06-11"  # el jueves de esa semana
    assert etiqueta == "el jueves"


def test_dia_en_fecha_explicita():
    assert dia_en("te llamo el 12/06", LUNES)[0] == "2026-06-12"
    assert dia_en("la cita es el 20 de junio", LUNES)[0] == "2026-06-20"


def test_caso_david_reunion_jueves_9():
    correos = [
        {
            "from": "David Valentín <david@empresa.com>",
            "subject": "Colaboración",
            "snippet": "Perfecto, entonces hemos quedado para la reunión el jueves a las 09.00. Un saludo.",
        }
    ]
    reuniones = detectar_reuniones(correos, LUNES)
    assert len(reuniones) == 1
    r = reuniones[0]
    assert r["de"] == "David Valentín"
    assert r["email"] == "david@empresa.com"
    assert r["fecha"] == "2026-06-11"  # jueves
    assert r["hora"] == "09:00"
    assert r["cuando"] == "el jueves a las 09:00"


def test_conservador_sin_palabra_de_cita_no_detecta():
    # menciona "jueves" pero no hay palabra de reunión → no inventa una cita
    correos = [
        {"from": "x <x@y.com>", "subject": "factura", "snippet": "te paso la factura del jueves"}
    ]
    assert detectar_reuniones(correos, LUNES) == []


def test_conservador_sin_dia_no_detecta():
    correos = [
        {
            "from": "x <x@y.com>",
            "subject": "reunión",
            "snippet": "tenemos que hacer una reunión pronto",
        }
    ]
    assert detectar_reuniones(correos, LUNES) == []


def test_no_propone_reuniones_pasadas():
    # "el lunes" cuando hoy ya es lunes resuelve a hoy (válido); una fecha explícita pasada se descarta
    correos = [
        {"from": "x <x@y.com>", "subject": "reunión", "snippet": "quedamos el 1/06 para la reunión"}
    ]
    assert detectar_reuniones(correos, LUNES) == []  # 1 de junio ya pasó


def test_dedup_misma_reunion():
    correos = [
        {
            "from": "David <d@x.com>",
            "subject": "reunión jueves",
            "snippet": "quedamos el jueves a las 9",
        },
        {
            "from": "David <d@x.com>",
            "subject": "RE: reunión jueves",
            "snippet": "ok, el jueves a las 9 perfecto",
        },
    ]
    assert len(detectar_reuniones(correos, LUNES)) == 1
