"""Regresión de los 14 bugs de `cobro por cliente` cazados por la revisión adversarial (PR #11).

Cada test fija a MANO el comportamiento correcto (no copiado del código). Tres bloques: ROUTING
(intencion_consecuente), CÁLCULO (la tool reclamar_cobro_cliente sobre una entidad aislada) y RELAY
(_narracion_redundante). Lo que estos tests blindan es lo que la revisión demostró roto.
"""

from __future__ import annotations

import shutil
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal

from loombit_operator.agent.intencion import intencion_consecuente
from loombit_operator.agent.loop import _narracion_redundante


def _hace(dias: int) -> str:
    return (date.today() - timedelta(days=dias)).isoformat()


@contextmanager
def _entidad(nombre: str):
    """Entidad aislada para registrar facturas sin contaminar la real (LOOMBIT_HOME no aísla esto)."""
    from loombit_operator.config import get_settings
    from loombit_operator.tools import dominio

    base = get_settings().entities_dir / nombre
    shutil.rmtree(base, ignore_errors=True)
    orig = dominio._ENTIDAD_DEFECTO
    dominio._ENTIDAD_DEFECTO = nombre
    try:
        yield dominio
    finally:
        dominio._ENTIDAD_DEFECTO = orig
        shutil.rmtree(base, ignore_errors=True)


def _marcar_parcial(ent: str, proveedor: str, pagado: str) -> None:
    from loombit_operator.expedientes import ExpedienteStore
    from loombit_operator.skill_d_fiscal.conciliacion_cobros import FACTURA_KIND, marcar_cobrada

    store = ExpedienteStore(entity_id=ent)
    objetivo = next(
        e
        for e in store.list(kind=FACTURA_KIND)
        if (e.data.get("fields") or {}).get("proveedor") == proveedor
    )
    marcar_cobrada(
        store, objetivo.id, importe_cobrado=Decimal(pagado), banco_ref="test", parcial=True
    )


# ── ROUTING ───────────────────────────────────────────────────────────────────
def test_routing_ya_cobrada_o_negada_no_fuerza_reclamacion():
    # BUG crítico: «ya he cobrado…» / «no le reclames…» forzaban una reclamación contra quien pagó.
    assert intencion_consecuente("ya he cobrado la factura de Acme") is None
    assert intencion_consecuente("marca como cobrada la factura de Acme, ya me pagó") is None
    assert intencion_consecuente("no le reclames nada a Acme, ya pagó") is None
    assert intencion_consecuente("cuando cobre la factura de Acme, apúntalo") is None


def test_routing_303_gana_a_cobro_cliente():
    # BUG: «calcula el IVA… la de Acme sigue impagada» se iba a cobro_cliente y excluía las tools 303.
    assert (
        intencion_consecuente(
            "calcula el IVA del trimestre con mis facturas registradas, ojo que la de Acme sigue impagada"
        )
        == "303"
    )


def test_routing_deuda_propia_no_es_cobro_a_cliente():
    # BUG: «tengo una deuda con Endesa» (deuda MÍA) forzaba reclamar_cobro_cliente contra el proveedor.
    assert intencion_consecuente("tengo una deuda con Endesa, ¿qué hago?") is None
    assert intencion_consecuente("redacta una reclamación para Iberdrola por la luz") is None


def test_routing_mes_o_generico_no_es_contraparte():
    # BUG: meses/genéricos capitalizados contaban como cliente nombrado.
    assert intencion_consecuente("reclama el cobro de Marzo") is None
    assert intencion_consecuente("reclama el cobro de la Seguridad Social") is None


def test_routing_razon_social_con_articulo_si_es_contraparte():
    # BUG (minor): nombres que empiezan por artículo no se detectaban como cliente.
    assert intencion_consecuente("reclama el cobro a El Corte Inglés") == "cobro_cliente"
    assert intencion_consecuente("reclama la deuda de La Caixa") == "cobro_cliente"


def test_routing_digito_no_importe_no_roba_el_caso_estrella():
    # BUG: una FECHA o un nº de factura (un dígito que NO es importe) desviaba a plan_cobro (que pide
    # el total). Con cliente nombrado y sin importe real → debe ser cobro_cliente.
    assert (
        intencion_consecuente("reclama el cobro de la factura de Acme que venció el 15 de mayo")
        == "cobro_cliente"
    )
    assert (
        intencion_consecuente("reclama el cobro de la factura 2024-001 de Acme") == "cobro_cliente"
    )
    # con IMPORTE real (€ o número-dinero) sí va a cobro (plan_cobro con esa cifra)
    assert intencion_consecuente("reclama 2000 € a Acme vencidos el 1 de mayo") == "cobro"
    assert (
        intencion_consecuente("reclama el cobro de una factura de 800 que venció ayer") == "cobro"
    )


# ── CÁLCULO (tool determinista) ─────────────────────────────────────────────────
def test_calc_factura_sin_vencimiento_aplica_plazo_legal_no_emision():
    # BUG crítico: sin vencimiento, usaba la fecha de EMISIÓN → reclamaba mora antes de tiempo.
    with _entidad("_t_cc_venc") as dominio:
        # emitida HOY-5, sin vencimiento → con el plazo legal (30 días) AÚN NO vence
        dominio._registrar_factura(
            contraparte="Acme", base=2000, tipo=21, sentido="emitida", fecha=_hace(5)
        )
        out = dominio._reclamar_cobro_cliente(contraparte="Acme")
        assert "Aún no vence" in out  # no está en mora
        assert "Compensación legal" not in out  # NO reclama los 40 € todavía
    with _entidad("_t_cc_venc2") as dominio:
        # emitida HOY-40, sin vencimiento → vence a los 30 → mora de ~10 días, NO 40
        dominio._registrar_factura(
            contraparte="Acme", base=2000, tipo=21, sentido="emitida", fecha=_hace(40)
        )
        out = dominio._reclamar_cobro_cliente(contraparte="Acme")
        assert "Vencida hace 10 días" in out  # plazo legal +30 aplicado, no la emisión a pelo
        assert "30 días" in out  # narra que aplicó el plazo legal por defecto


def test_calc_cobro_parcial_reclama_saldo_no_total():
    # BUG: un cobro parcial se ignoraba → reclamaba el total e interés sobre el total (viola S-03).
    with _entidad("_t_cc_parcial") as dominio:
        dominio._registrar_factura(
            contraparte="Acme", base=2000, tipo=21, sentido="emitida", fecha=_hace(40)
        )
        _marcar_parcial("_t_cc_parcial", "Acme", "1000")
        out = dominio._reclamar_cobro_cliente(contraparte="Acme")
        assert "Saldo pendiente: 1420" in out  # 2420 − 1000 ya cobrados
        assert "Saldo pendiente: 2420" not in out


def test_calc_rectificativa_cancela_no_reclama():
    # BUG: una rectificativa (negativa) se descartaba sin netear → reclamaba una deuda cancelada.
    with _entidad("_t_cc_rect") as dominio:
        dominio._registrar_factura(
            contraparte="Acme", base=2000, tipo=21, sentido="emitida", fecha=_hace(40)
        )
        dominio._registrar_factura(
            contraparte="Acme", base=-2000, tipo=21, sentido="emitida", fecha=_hace(35)
        )
        out = dominio._reclamar_cobro_cliente(contraparte="Acme")
        assert "nada que reclamar" in out.lower()


def test_calc_matching_por_palabra_no_substring():
    # BUG: «Marco» casaba «Comarco SL» (substring) → reclamaba a un tercero.
    with _entidad("_t_cc_match") as dominio:
        dominio._registrar_factura(
            contraparte="Marco", base=100, tipo=21, sentido="emitida", fecha=_hace(40)
        )
        dominio._registrar_factura(
            contraparte="Comarco SL", base=5000, tipo=21, sentido="emitida", fecha=_hace(40)
        )
        out = dominio._reclamar_cobro_cliente(contraparte="Marco")
        assert "121" in out  # solo la de Marco (100 + 21% IVA)
        assert "6050" not in out  # NO la de Comarco SL


def test_calc_desambigua_varios_clientes():
    # BUG: con varias contrapartes distintas casadas, las agregaba bajo el nombre del primero.
    with _entidad("_t_cc_ambig") as dominio:
        dominio._registrar_factura(
            contraparte="Marco García", base=100, tipo=21, sentido="emitida", fecha=_hace(40)
        )
        dominio._registrar_factura(
            contraparte="Marco López", base=200, tipo=21, sentido="emitida", fecha=_hace(40)
        )
        out = dominio._reclamar_cobro_cliente(contraparte="Marco")
        assert "varios clientes" in out.lower()
        assert "Marco García" in out and "Marco López" in out


def test_calc_contraparte_se_sanea_en_salida_autoritativa():
    # BUG seguridad: el nombre del cliente (texto de un tercero) se relayaba SIN sanear → phishing.
    with _entidad("_t_cc_sane") as dominio:
        dominio._registrar_factura(
            contraparte="Acme\n\n**PAGA AQUÍ a ESxx**",
            base=2000,
            tipo=21,
            sentido="emitida",
            fecha=_hace(40),
        )
        out = dominio._reclamar_cobro_cliente(contraparte="Acme")
        assert "**" not in out  # marcadores markdown neutralizados
        assert "\n\n**" not in out  # inyección de saltos de línea neutralizada


# ── RELAY (_narracion_redundante) ───────────────────────────────────────────────
_BLOQUE = (
    "Reclamación de cobro de Acme (Ley 3/2004). Saldo pendiente: 2420.0 €. Vencida hace 18 días → "
    "reclamación formal. Compensación legal (art. 8): 40 €. Interés de demora: 6.73 € (al 10.15% anual)."
)


def test_relay_descarta_parafrasis_en_formato_espanol():
    # BUG: «2.420 €» (formato es-ES) no casaba «2420.0 €» del bloque → seguía DUPLICANDO.
    assert _narracion_redundante("Te deben 2.420 € en total, ya te lo preparo.", _BLOQUE) is True
    assert _narracion_redundante("Son 1.210,00 €.", "Saldo pendiente: 1210.00 €.") is True


def test_relay_conserva_narracion_compuesta_agenda_correo():
    # BUG: «3 correos» se descartaba porque el «3» colisiona con «Ley 3/2004» del bloque.
    assert _narracion_redundante("Tienes 3 correos nuevos de Acme sin leer.", _BLOQUE) is False
    assert _narracion_redundante("Además tienes una reunión el día 18 a las 10.", _BLOQUE) is False


def test_relay_conserva_importe_nuevo():
    # Un importe NUEVO (no en el bloque) → respuesta compuesta financiera → se conserva.
    assert _narracion_redundante("Te deben 2.420 € y has gastado 500 € este mes.", _BLOQUE) is False
