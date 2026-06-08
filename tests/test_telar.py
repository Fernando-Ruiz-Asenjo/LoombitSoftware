"""La tela de la mañana: el día tejido en hilos accionables (+ detección de plazos)."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

from loombit_operator import telar


def test_telar_es_blanco_expone_usuario_del_owner() -> None:
    # BLANCO: el nombre NO está hardcodeado; viene del owner (clave `usuario`). El saludo es neutro.
    tela = telar.tejer_dia(
        now=datetime(2026, 2, 15, 9),
        eventos=[],
        correos=[],
        inbox=[],
        vencidas=[],
        proximas=[],
        aprobaciones=0,
    )
    assert "usuario" in tela
    assert "Fernando" not in tela["saludo"]


def test_saludo_por_hora() -> None:
    assert telar._saludo(datetime(2026, 6, 8, 9)) == "Buenos días"
    assert telar._saludo(datetime(2026, 6, 8, 16)) == "Buenas tardes"
    assert telar._saludo(datetime(2026, 6, 8, 23)) == "Buenas noches"


def test_fecha_en_reconoce_formatos() -> None:
    hoy = date(2026, 6, 1)
    assert telar._fecha_en("antes del 15/06", hoy) == "2026-06-15"
    assert telar._fecha_en("vence el 20 de junio", hoy) == "2026-06-20"
    assert telar._fecha_en("sin fecha aquí", hoy) is None


def test_plazos_requiere_palabra_y_fecha() -> None:
    hoy = date(2026, 6, 1)
    correos = [
        {
            "subject": "Modelo 303",
            "snippet": "hay que presentar antes del 20/07",
            "from": "Gestoría <g@x.com>",
        },
        {
            "subject": "Hola",
            "snippet": "nos vemos el 20/07 para comer",
            "from": "Ana <a@x.com>",
        },  # fecha sin palabra de plazo
        {
            "subject": "Recordatorio",
            "snippet": "el plazo es importante",
            "from": "X <x@x.com>",
        },  # palabra sin fecha
    ]
    plazos = telar._plazos_en_correos(correos, hoy)
    assert len(plazos) == 1
    assert plazos[0]["fecha"] == "2026-07-20"
    assert plazos[0]["de"] == "Gestoría"


def test_tejer_dia_produce_hilos_con_accion() -> None:
    tela = telar.tejer_dia(
        now=datetime(2026, 6, 8, 9),
        eventos=[{"summary": "Reunión", "start": "2026-06-08T12:00:00+02:00"}],
        correos=[{"from": "David <d@x.com>", "subject": "presupuesto", "snippet": "¿me lo pasas?"}],
        vencidas=[SimpleNamespace(cliente="Acme", importe=1200.0)],
        proximas=[],
        aprobaciones=1,
    )
    tipos = {h["tipo"] for h in tela["hilos"]}
    assert {"agenda", "correo", "cobro", "aprobacion"} <= tipos
    # el cobro y el correo traen su acción preparada (agent_task con tarea)
    cobro = next(h for h in tela["hilos"] if h["tipo"] == "cobro")
    assert cobro["accion"]["modo"] == "agent_task"
    assert "Acme" in cobro["accion"]["task"]
    assert "1200" in cobro["accion"]["task"]
    assert tela["saludo"] == "Buenos días"


def test_tejer_dia_ordena_por_urgencia() -> None:
    tela = telar.tejer_dia(
        now=datetime(2026, 6, 8, 9),
        eventos=[{"summary": "Café", "start": "2026-06-08T10:00:00"}],  # urgencia 1
        correos=[],
        vencidas=[SimpleNamespace(cliente="Z", importe=500.0)],  # urgencia 2
        proximas=[],
        aprobaciones=0,
    )
    assert tela["hilos"][0]["urgencia"] >= tela["hilos"][-1]["urgencia"]
    assert tela["hilos"][0]["tipo"] == "cobro"  # lo urgente, primero


def test_tejer_dia_vacio_es_amable() -> None:
    # 15-feb: sin señales y sin obligación fiscal en ventana (el 1T se presenta el 20-abr).
    tela = telar.tejer_dia(
        now=datetime(2026, 2, 15, 9),
        eventos=[],
        correos=[],
        inbox=[],
        vencidas=[],
        proximas=[],
        aprobaciones=0,
    )
    assert tela["hilos"] == []
    assert "despejado" in tela["resumen"]


def test_plazo_desde_la_bandeja_no_solo_contactos() -> None:
    # El caso de oro: la gestoría/AEAT manda un plazo aunque no sea un contacto frecuente.
    tela = telar.tejer_dia(
        now=datetime(2026, 6, 8, 9),
        eventos=[],
        correos=[],
        inbox=[
            {
                "from": "AEAT <no-reply@aeat.es>",
                "subject": "Modelo 303",
                "snippet": "plazo hasta el 20/07",
            }
        ],
        vencidas=[],
        proximas=[],
        aprobaciones=0,
    )
    plazo = next(h for h in tela["hilos"] if h["tipo"] == "plazo")
    assert "2026-07-20" in plazo["accion"]["task"]


def test_obligacion_fiscal_proxima_dentro_de_ventana() -> None:
    # En junio, el 2º trimestre (303) se presenta ~20/07 → dentro de la ventana de 45 días.
    obs = telar._obligaciones_fiscales(date(2026, 6, 8))
    assert len(obs) == 1
    assert obs[0]["fecha"] == "2026-07-20"
    assert "303" in obs[0]["modelos"]


def test_obligacion_fiscal_lejana_no_aparece() -> None:
    # A principios de febrero, el siguiente (1T, 20/04) está a >45 días → no se surface aún.
    assert telar._obligaciones_fiscales(date(2026, 2, 1)) == []


def test_telar_surface_hilo_fiscal() -> None:
    tela = telar.tejer_dia(
        now=datetime(2026, 6, 8, 9),
        eventos=[],
        correos=[],
        inbox=[],
        vencidas=[],
        proximas=[],
        aprobaciones=0,
    )
    fiscal = next(h for h in tela["hilos"] if h["tipo"] == "fiscal")
    assert "303" in fiscal["titulo"]
    assert fiscal["accion"]["label"] == "Preparar borrador"


def test_plazo_genera_hilo_de_agendar() -> None:
    tela = telar.tejer_dia(
        now=datetime(2026, 6, 8, 9),
        eventos=[],
        correos=[
            {"from": "Gestoría <g@x.com>", "subject": "303", "snippet": "presentar antes del 20/07"}
        ],
        vencidas=[],
        proximas=[],
        aprobaciones=0,
    )
    plazo = next(h for h in tela["hilos"] if h["tipo"] == "plazo")
    assert plazo["accion"]["label"] == "Agendar"
    assert "2026-07-20" in plazo["accion"]["task"]
