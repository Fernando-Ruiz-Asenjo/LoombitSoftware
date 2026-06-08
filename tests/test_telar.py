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
        asuntos=[],
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


def test_telar_reunion_comprendida_confirmada_con_lugar() -> None:
    # Caso David: la COMPRENSIÓN da la reunión confirmada por ambos, con la fecha del correo (jueves 11)
    # y el lugar. El telar la muestra con su estado, lugar y la urgencia que marca la comprensión.
    tela = telar.tejer_dia(
        now=datetime(2026, 6, 8, 9),
        eventos=[],
        proximos=[],
        correos=[],
        inbox=[],
        vencidas=[],
        proximas=[],
        aprobaciones=0,
        asuntos=[
            {
                "tipo": "reunion",
                "titulo": "Reunión con David Valentín",
                "con": "David Valentín",
                "resumen": "ambos confirmasteis la reunión",
                "estado": "confirmada",
                "fecha": "2026-06-11",
                "hora": "09:00",
                "lugar": "Calle Manzana, 8 Local, Getafe",
                "importancia": 3,
                "accion": "",
                "origen": "RE: BAREMOS",
                "dia_semana": "jueves",
            }
        ],
    )
    r = next(h for h in tela["hilos"] if h["tipo"] == "reunion")
    assert "David Valentín" in r["titulo"]
    assert "jueves 11/6" in r["titulo"] and "09:00" in r["titulo"]  # la fecha del CORREO
    assert "Getafe" in r["detalle"] and "confirmada por ambos" in r["detalle"]
    assert r["urgencia"] == 3


def test_telar_notificacion_oficial_es_importante() -> None:
    # Generalidad: una notificación oficial (Policía/AEAT) es un asunto importante con su acción.
    tela = telar.tejer_dia(
        now=datetime(2026, 6, 8, 9),
        eventos=[],
        proximos=[],
        correos=[],
        inbox=[],
        vencidas=[],
        proximas=[],
        aprobaciones=0,
        asuntos=[
            {
                "tipo": "notificacion",
                "titulo": "Notificación de la Dirección General de la Policía",
                "con": "DGP",
                "resumen": "te informan de un trámite del DNI",
                "estado": "requiere_accion",
                "fecha": "",
                "hora": "",
                "lugar": "",
                "importancia": 3,
                "accion": "revisar la notificación de la Policía sobre tu DNI",
                "origen": "Notificación Dirección General de la Policía",
                "dia_semana": "",
            }
        ],
    )
    n = next(h for h in tela["hilos"] if h["tipo"] == "notificacion")
    assert "Policía" in n["titulo"]
    assert "requiere acción" in n["detalle"]
    assert n["accion"]["label"] == "Gestionar"
    assert "DNI" in n["accion"]["task"]
    assert n["urgencia"] == 3
