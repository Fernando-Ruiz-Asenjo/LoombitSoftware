"""El observador Pilot registra actividad SEMÁNTICA (app/ventana), nunca teclas ni pantalla.

Garantías: la muestra solo lleva ts/app/title (no hay campos de teclado/pantalla), el log es local
y el resumen agrega por app. Privacidad por diseño (no keylogger).
"""

import json

from loombit_operator.pilot.observer import (
    foreground_activity,
    registrar_actividad,
    resumen_procesos,
)


def test_muestra_solo_lleva_campos_semanticos():
    m = foreground_activity()
    assert set(m.keys()) == {"ts", "app", "title"}  # nada de 'keys'/'screen'/'password'
    assert isinstance(m["ts"], str)


def test_registrar_y_resumir(tmp_path):
    # registramos varias muestras (en CI sin ventana, app sale vacía: lo forzamos vía fichero)
    log = tmp_path / "activity.jsonl"
    log.write_text(
        "\n".join(
            json.dumps({"ts": "t", "app": a, "title": ""})
            for a in ["chrome.exe", "chrome.exe", "excel.exe"]
        ),
        encoding="utf-8",
    )
    resumen = resumen_procesos(base_dir=tmp_path)
    assert resumen[0] == {"app": "chrome.exe", "muestras": 2}
    assert {"app": "excel.exe", "muestras": 1} in resumen


def test_registrar_actividad_escribe_local(tmp_path):
    m = registrar_actividad(base_dir=tmp_path)
    assert (tmp_path / "activity.jsonl").exists()
    assert "ts" in m and "app" in m and "title" in m
