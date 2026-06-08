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
        proximos=[],
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
        proximos=[],
        correos=[{"from": "David <d@x.com>", "subject": "presupuesto", "snippet": "¿me lo pasas?"}],
        inbox=[],
        reuniones=[],
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
        proximos=[],
        correos=[],
        inbox=[],
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
        proximos=[],
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
        proximos=[],
        correos=[],
        inbox=[
            {
                "from": "AEAT <no-reply@aeat.es>",
                "subject": "Modelo 303",
                "snippet": "plazo hasta el 20/07",
            }
        ],
        reuniones=[],
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
        proximos=[],
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
        proximos=[],
        correos=[
            {"from": "Gestoría <g@x.com>", "subject": "303", "snippet": "presentar antes del 20/07"}
        ],
        inbox=[],
        reuniones=[],
        vencidas=[],
        proximas=[],
        aprobaciones=0,
    )
    plazo = next(h for h in tela["hilos"] if h["tipo"] == "plazo")
    assert plazo["accion"]["label"] == "Agendar"
    assert "2026-07-20" in plazo["accion"]["task"]


def test_cobro_vencido_muestra_desglose_legal_con_cita_boe() -> None:
    # Una vencida CON vencimiento → el hilo lleva su desglose legal (saldo + 40 € + interés con BOE).
    tela = telar.tejer_dia(
        now=datetime(2026, 6, 7, 9),
        eventos=[],
        proximos=[],
        correos=[],
        inbox=[],
        vencidas=[SimpleNamespace(cliente="Acme", importe=1250.0, vencimiento="2026-05-01")],
        proximas=[],
        aprobaciones=0,
    )
    cobro = next(h for h in tela["hilos"] if h["tipo"] == "cobro")
    assert "VENCIDA (37d)" in cobro["titulo"]
    # el detalle nombra la compensación, el interés con su tipo y la fuente BOE, y lo reclamable
    det = cobro["detalle"]
    assert "40,00 €" in det
    assert "interés demora" in det and "10,15%" in det and "BOE-A-2025-27201" in det
    assert "reclamable" in det
    # la acción es una reclamación formal (37 días) que cita la base legal, en nombre del usuario
    assert cobro["accion"]["label"] == "Reclamación formal"
    assert "Acme" in cobro["accion"]["task"] and "Ley 3/2004" in cobro["accion"]["task"]


def test_cobro_sin_vencimiento_degrada_a_recordatorio_basico() -> None:
    # Sin vencimiento no se puede calcular el desglose → recordatorio básico, sin inventar nada.
    tela = telar.tejer_dia(
        now=datetime(2026, 6, 7, 9),
        eventos=[],
        proximos=[],
        correos=[],
        vencidas=[SimpleNamespace(cliente="Beta", importe=900.0)],
        proximas=[],
        aprobaciones=0,
    )
    cobro = next(h for h in tela["hilos"] if h["tipo"] == "cobro")
    assert "detalle" not in cobro  # sin desglose legal
    assert cobro["accion"]["label"] == "Preparar recordatorio"
    assert "Beta" in cobro["accion"]["task"]


def test_telar_reunion_con_conflicto_usa_la_fecha_del_correo() -> None:
    # Caso David: el destilador da la reunión con CONFLICTO (correo jueves 11 vs calendario lunes 15).
    # El telar usa la fecha del CORREO, muestra el lugar y ofrece corregir el calendario. Lo más urgente.
    tela = telar.tejer_dia(
        now=datetime(2026, 6, 8, 9),
        eventos=[],
        proximos=[],
        correos=[],
        inbox=[],
        vencidas=[],
        proximas=[],
        aprobaciones=0,
        reuniones=[
            {
                "con": "David Valentín",
                "fecha": "2026-06-11",
                "hora": "09:00",
                "lugar": "Calle Manzana, 8 Local, Getafe",
                "fuente": "correo",
                "conflicto": True,
                "nota": "tu calendario la tiene el lunes 15",
                "origen": "RE: BAREMOS BRICOS Y MANTENIMIENTOS",
                "dia_semana": "jueves",
            }
        ],
    )
    r = next(h for h in tela["hilos"] if h["tipo"] == "reunion")
    assert "David Valentín" in r["titulo"]
    assert (
        "jueves 11/6" in r["titulo"] and "09:00" in r["titulo"]
    )  # la fecha del CORREO, no del calendario
    assert "Getafe" in r["detalle"] and "correo" in r["detalle"].lower()
    assert r["accion"]["label"] == "Corregir calendario"
    assert "2026-06-11" in r["accion"]["task"]
    assert r["urgencia"] == 3  # el descuadre es lo más urgente del telar


def test_telar_reunion_normal_del_calendario() -> None:
    # Sin conflicto: una reunión del calendario se muestra con "Ver".
    tela = telar.tejer_dia(
        now=datetime(2026, 6, 8, 9),
        eventos=[],
        proximos=[],
        correos=[],
        inbox=[],
        vencidas=[],
        proximas=[],
        aprobaciones=0,
        reuniones=[
            {
                "con": "David Valentin",
                "fecha": "2026-06-15",
                "hora": "11:00",
                "lugar": "",
                "fuente": "calendario",
                "conflicto": False,
                "nota": "",
                "origen": "Reunión con David Valentin",
                "dia_semana": "lunes",
            }
        ],
    )
    r = next(h for h in tela["hilos"] if h["tipo"] == "reunion")
    assert "David Valentin" in r["titulo"] and "lunes 15/6" in r["titulo"]
    assert r["accion"]["label"] == "Ver"
    assert r["urgencia"] == 2
