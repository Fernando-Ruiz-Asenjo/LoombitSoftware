"""
Tools de DOMINIO administrativo — exponen los "cerebros" deterministas que ya
existían como módulos (cobros, fiscal 303) como herramientas que el AGENTE puede
invocar. Antes el chat anunciaba "Reclamar cobro" / "303" pero el agente no tenía
ninguna tool para hacerlo → 0 steps y narración vacía. Esto le da las manos.

Local-first y determinista: el cálculo lo hace código (no el LLM); el LLM solo
decide cuándo llamar y narra el resultado. Ningún efecto externo aquí (no envían
nada): preparar un cobro o un borrador de 303 es seguro; el envío real sigue
pasando por gmail_send con su gate.
"""

from __future__ import annotations

import re
import unicodedata
from calendar import monthrange
from datetime import date
from typing import Any

from ..cobros import LATE_FEE_FIXED_EUR, dunning_plan
from ..docs_intel import InvoiceFields
from ..expedientes import ExpedienteStore
from ..skill_d_fiscal.intake import rango_periodo as _rango_periodo
from ..skill_d_fiscal.intake import rango_trimestre as _rango_trimestre
from ..skill_d_fiscal.intake import recopilar_lineas as _recopilar_lineas
from ..skill_d_fiscal.intake import registrar_factura as _intake_registrar
from ..skill_d_fiscal.modelo_303 import LineaIVA, borrador_303_texto, calcular_303
from .registry import ToolDefinition, tool_registry

# Entidad por defecto para el agente de chat (un solo titular). El modelo multi-entidad
# (una por cliente) es una decisión de producto pendiente → ver «PARA FERNANDO» en
# docs/AUDITORIA_LOOP_2026-06-09.md. Por ahora todo va a la entidad «principal».
_ENTIDAD_DEFECTO = "principal"

_STAGE_ES = {
    "por_vencer": "aún no vence",
    "vence_hoy": "vence hoy",
    "recordatorio_amistoso": "recordatorio amistoso (1–7 días vencida)",
    "recordatorio_firme": "recordatorio firme (8–21 días)",
    "reclamacion_formal": "reclamación formal (22–60 días)",
    "via_judicial": "vía judicial (>60 días) — la decide un profesional",
    "cobrado": "cobrado",
}


def _plan_cobro(
    total: float,
    fecha_vencimiento: str,
    cobrado: float = 0.0,
    tipo_interes_anual: float | None = None,
) -> str:
    """Calcula el plan de cobro de UNA factura (Ley 3/2004): saldo, etapa, interés y compensación."""
    try:
        plan: dict[str, Any] = dunning_plan(
            total=float(total),
            due_date=str(fecha_vencimiento),
            paid=float(cobrado or 0),
            annual_rate_pct=tipo_interes_anual,
        )
    except (ValueError, TypeError) as exc:
        return f"ERROR: no pude calcular el cobro ({exc}). Dame el total y la fecha de vencimiento."

    accion = plan.get("action")
    if accion == "no_reclamar":
        return "Esta factura ya está cobrada por completo: no hay nada que reclamar."

    saldo = plan.get("outstanding")
    overdue = plan.get("overdue_days", 0)
    etapa = _STAGE_ES.get(str(plan.get("stage")), str(plan.get("stage")))

    partes = [f"Saldo pendiente: {saldo} €."]
    if overdue < 0:
        partes.append(
            f"Aún no vence (faltan {abs(overdue)} días). Acción: esperar / preparar aviso."
        )
    elif accion == "preparar_recordatorio":
        partes.append("Vence hoy. Acción: preparar recordatorio amistoso.")
    else:
        partes.append(f"Vencida hace {overdue} días → {etapa}.")
        partes.append(
            f"Compensación legal por costes de cobro (art. 8): {LATE_FEE_FIXED_EUR:.0f} €."
        )
        interes = plan.get("interest") or {}
        if interes.get("rate_required"):
            partes.append(
                "Interés de demora: tipo variable (BCE + 8, por semestre) — a verificar el vigente."
            )
        elif interes.get("amount") is not None:
            rate = interes.get("rate_pct")
            cita = interes.get("fuente") or interes.get("note") or ""
            txt = f"Interés de demora: {interes['amount']} €"
            if rate:
                txt += f" (al {rate}% anual)"
            partes.append(txt + (f". {cita}" if cita else "."))
        if plan.get("escalate_to_human"):
            partes.append(
                "Supera el plazo: la vía judicial la decide un profesional; desde la "
                "L.O. 1/2025 hay que intentar/documentar un MASC antes de demandar."
            )
        partes.append("Acción recomendada: redactar la reclamación (te la dejo lista para enviar).")
    return " ".join(partes)


def _norm_tipo(t: object) -> float:
    """Acepta 21, 21.0 o 0.21 y devuelve fracción (0.21)."""
    v = float(t)
    return v / 100.0 if v > 1 else v


# Tipos de IVA válidos en España (fracción): exento 0, superreducido 4%, temporal 5%,
# reducido 10%, general 21%. Cualquier otro es un dato inventado/erróneo → se rechaza,
# nunca se calcula un 303 con cifras imposibles (un IVA del 40% no existe).
_TIPOS_IVA_VALIDOS = {0.0, 0.04, 0.05, 0.10, 0.21}


def _parse_lineas(items: list[dict] | None, sentido: str, defecto: str) -> list[LineaIVA]:
    out: list[LineaIVA] = []
    for it in items or []:
        concepto = str(it.get("concepto", defecto))
        # El sentido lo MANDA el concepto del propio ítem cuando es inequívoco: el 14B a veces mete una
        # «compra» en el bucket de ventas (iva_repercutido) → el 303 saldría inflado (devengado de más,
        # deducible de menos). Si el concepto dice claramente compra/venta, se respeta ESO; si es
        # ambiguo, vale el bucket. Frontera de determinismo: la cifra fiscal no puede depender de que el
        # 14B acierte el bucket. (_SENT_*/_es_factura_emitida definidos más abajo, resueltos en runtime.)
        cl = concepto.lower()
        if any(k in cl for k in _SENT_RECIBIDA):
            s = "soportado"
        elif any(k in cl for k in _SENT_EMITIDA):
            s = "devengado"
        else:
            s = sentido
        out.append(
            LineaIVA(
                base=it["base"],
                tipo=_norm_tipo(it.get("tipo", 0.21)),
                sentido=s,
                concepto=concepto,
            )
        )
    return out


def _calcular_303(
    iva_repercutido: list[dict] | None = None,
    iva_soportado: list[dict] | None = None,
    periodo: str = "",
) -> str:
    """Calcula un BORRADOR del modelo 303 (IVA, régimen general) a partir de bases y tipos."""
    try:
        lineas = _parse_lineas(iva_repercutido, "devengado", "venta") + _parse_lineas(
            iva_soportado, "soportado", "compra"
        )
    except (KeyError, TypeError, ValueError) as exc:
        return (
            "ERROR: necesito las líneas de IVA como listas de {base, tipo} "
            f"para ventas (repercutido) y compras (soportado). Detalle: {exc}"
        )
    if not lineas:
        return (
            "Para el 303 necesito al menos las bases de tus ventas (IVA repercutido) y, si las "
            "hay, de tus compras (IVA soportado). Dímelas y te dejo el borrador."
        )
    # Guard antifabricación: ningún tipo de IVA imposible. Si el modelo se inventó un 40 %,
    # no calculamos un 303 falso — paramos y lo decimos (brújula: cifras por código, no mentir).
    for ln in lineas:
        if round(float(ln.tipo), 4) not in _TIPOS_IVA_VALIDOS:
            return (
                f"ERROR: tipo de IVA no válido en España: {float(ln.tipo) * 100:.0f}% "
                f"(en '{ln.concepto}'). Tipos válidos: 0, 4, 5, 10, 21%. Usa SOLO las cifras "
                "que te dé el usuario; no inventes líneas ni tipos."
            )

    # Echo de visibilidad: deja ver EXACTAMENTE con qué se calculó (si el modelo añadió líneas
    # que el usuario no dijo, aquí se ve). Honestidad por transparencia.
    def _fmt(lns: list[LineaIVA]) -> str:
        return (
            "; ".join(f"{ln.concepto} {ln.base}€ al {float(ln.tipo) * 100:.0f}%" for ln in lns)
            or "—"
        )

    ventas = [ln for ln in lineas if ln.sentido == "devengado"]
    compras = [ln for ln in lineas if ln.sentido == "soportado"]
    echo = f"Calculado con — Ventas: {_fmt(ventas)} · Compras: {_fmt(compras)}\n\n"
    res = calcular_303(lineas)
    return echo + borrador_303_texto(res, periodo or "periodo indicado")


# Sinónimos del sentido fiscal. 'repercutido'/'devengado' = IVA de SALIDA (emitida); 'soportado' =
# IVA de ENTRADA (recibida). Antes solo se reconocía 'emit'/'vent' → 'repercutido' caía a recibida y
# el 303 salía INVERTIDO (devengado↔deducible). La frontera de determinismo no puede fallar aquí.
_SENT_EMITIDA = ("emit", "vent", "repercut", "deveng", "ingres", "cobr")
_SENT_RECIBIDA = ("recib", "compr", "soport", "gast", "pago", "provee")


def _es_factura_emitida(sentido: object, contraparte: object = "") -> bool:
    """True si la factura es EMITIDA (ventas, IVA repercutido/devengado); False si RECIBIDA (compras,
    soportado). Reconoce los términos fiscales estándar, no solo 'emitida'/'venta'. Si el sentido no
    es claro, lo infiere de la contraparte (cliente→emitida, proveedor→recibida); por defecto emitida.
    """
    s = str(sentido or "").lower()
    if any(k in s for k in _SENT_EMITIDA):
        return True
    if any(k in s for k in _SENT_RECIBIDA):
        return False
    c = str(contraparte or "").lower()
    if "client" in c:
        return True
    if "provee" in c:
        return False
    return True  # por defecto, emitida (igual que el parámetro por defecto)


def _registrar_factura(
    contraparte: str,
    base: float,
    numero: str = "",
    iva: float | None = None,
    tipo: float | None = None,
    sentido: str = "emitida",
    fecha: str = "",
    nif: str = "",
) -> str:
    """Registra una factura (emitida a cliente o recibida de proveedor) y la persiste."""
    try:
        base_f = float(base)
    except (TypeError, ValueError):
        return "ERROR: dame la base imponible (un número) de la factura."
    if iva is not None:
        iva_f = float(iva)
    else:
        t = _norm_tipo(tipo if tipo is not None else 0.21)
        iva_f = round(base_f * t, 2)
    total = round(base_f + iva_f, 2)
    es_emitida = _es_factura_emitida(sentido, contraparte)
    sentido_303 = "devengado" if es_emitida else "soportado"
    inv = InvoiceFields(
        numero=numero or "s/n",
        fecha=fecha or "",
        proveedor=contraparte or "",
        nif=nif or "",
        base_imponible=base_f,
        iva=iva_f,
        total=total,
    )
    try:
        store = ExpedienteStore(entity_id=_ENTIDAD_DEFECTO)
        exp = _intake_registrar(store, inv, sentido_303)
    except Exception as exc:  # noqa: BLE001 — devolver el error en humano, no romper el run
        return f"ERROR al registrar la factura: {exc}"
    etiqueta = "emitida (a cliente)" if es_emitida else "recibida (de proveedor)"
    return (
        f"✅ Factura {inv.numero} registrada — {etiqueta}. {contraparte or 's/ contraparte'}: "
        f"base {base_f:.2f}€ + IVA {iva_f:.2f}€ = total {total:.2f}€. Guardada (id {exp.id[:8]}). "
        "Quedará disponible para tu 303."
    )


def _calcular_303_registradas(periodo: str = "") -> str:
    """Calcula el 303 desde las facturas YA REGISTRADAS (datos reales), no de una frase del LLM.

    Es el camino FIABLE: las cifras salen de facturas persistidas (registrar_factura), no de lo que
    el modelo extraiga de una oración. Cierra el riesgo de que el 14B invente/mis-asigne importes.
    """
    desde, hasta, etiqueta = _rango_trimestre(periodo)
    try:
        store = ExpedienteStore(entity_id=_ENTIDAD_DEFECTO)
        lineas, avisos = _recopilar_lineas(store, desde, hasta)
    except Exception as exc:  # noqa: BLE001
        return f"ERROR al leer tus facturas registradas: {exc}"
    if not lineas:
        ámbito = f"del {etiqueta}" if desde else "registradas"
        msg = (
            f"No tienes facturas {ámbito} todavía. Regístralas (las emitidas y las recibidas) y te "
            "calculo el 303 con datos REALES, no estimados."
        )
        if avisos:  # p.ej. facturas excluidas por no tener fecha o ser de otro trimestre
            msg += "\n\nOJO:\n" + "\n".join(f"  - {a}" for a in avisos)
        return msg
    n_emit = sum(1 for ln in lineas if ln.sentido == "devengado")
    n_rec = sum(1 for ln in lineas if ln.sentido == "soportado")
    res = calcular_303(lineas)
    cab = (
        f"303 calculado desde {len(lineas)} factura(s) registrada(s) "
        f"({n_emit} emitidas, {n_rec} recibidas) — datos reales, no estimados.\n\n"
    )
    out = cab + borrador_303_texto(res, etiqueta)
    if desde is None:
        out += (
            "\n\n⚠ No me diste un trimestre claro, así que incluí TODAS tus facturas. Dime el periodo "
            "(p.ej. «2T 2026») para que lo acote al trimestre."
        )
    if avisos:
        out += "\n\nAVISOS de las facturas:\n" + "\n".join(f"  - {a}" for a in avisos)
    return out


def _resumen_facturacion(periodo: str = "") -> str:
    """Resumen ECONÓMICO de un periodo desde las facturas registradas: cuánto has FACTURADO (ingresos),
    cuánto has GASTADO (recibidas) y tu BENEFICIO. Responde las preguntas nº1 de un autónomo
    ('¿cuánto he facturado/gastado este mes?'). Determinista (no estima)."""
    desde, hasta, etiqueta = _rango_periodo(periodo)
    ámbito = etiqueta if desde else "total"
    try:
        store = ExpedienteStore(entity_id=_ENTIDAD_DEFECTO)
        lineas, _ = _recopilar_lineas(store, desde, hasta)
    except Exception as exc:  # noqa: BLE001
        return f"ERROR al leer tus facturas registradas: {exc}"
    emit = [ln for ln in lineas if ln.sentido == "devengado"]
    recib = [ln for ln in lineas if ln.sentido == "soportado"]
    if not emit and not recib:
        donde = f"en {etiqueta}" if desde else "registradas"
        return f"No tienes facturas {donde} todavía. Regístralas y te digo cuánto has facturado y gastado."
    base_e = round(sum(float(ln.base) for ln in emit), 2)
    iva_e = round(sum(float(ln.cuota) for ln in emit), 2)
    base_g = round(sum(float(ln.base) for ln in recib), 2)
    iva_g = round(sum(float(ln.cuota) for ln in recib), 2)
    beneficio = round(base_e - base_g, 2)
    cuerpo = (
        f"Resumen económico de {ámbito} (datos reales de tus facturas registradas):\n"
        f"  Facturado (ingresos): {len(emit)} factura(s) → base {base_e:.2f} € + IVA {iva_e:.2f} € "
        f"= {base_e + iva_e:.2f} €\n"
        f"  Gastos (recibidas): {len(recib)} factura(s) → base {base_g:.2f} € + IVA {iva_g:.2f} € "
        f"= {base_g + iva_g:.2f} €\n"
        f"  Beneficio (ingresos − gastos, sin IVA): {beneficio:.2f} €"
    )
    if desde is None:
        cuerpo += "\n\n⚠ No me diste un mes/trimestre claro, así que sumé TODO. Dime el periodo (p.ej. «junio 2026») para acotar."
    return cuerpo


def _cobros_pendientes(**_: object) -> str:
    """Cuánto te DEBEN: suma las facturas emitidas aún NO cobradas (cobros pendientes). Responde
    '¿cuánto me deben?'/'¿quién me debe?'. Determinista, desde las facturas registradas."""
    from ..skill_d_fiscal.conciliacion_cobros import pendientes_de_cobro

    try:
        store = ExpedienteStore(entity_id=_ENTIDAD_DEFECTO)
        pend = pendientes_de_cobro(store)
    except Exception as exc:  # noqa: BLE001
        return f"ERROR al leer tus cobros pendientes: {exc}"
    if not pend:
        return (
            "No tienes cobros pendientes: todas tus facturas emitidas están cobradas (o no has "
            "registrado ninguna emitida todavía)."
        )
    total = round(sum(float(p.importe) for p in pend), 2)
    lineas = [f"Te deben {len(pend)} factura(s) — {total:.2f} € en total:"]
    for p in pend[:12]:
        cliente = p.contraparte or "(cliente sin nombre)"
        ref = f" — factura {p.referencia}" if p.referencia else ""
        lineas.append(f"  · {cliente}: {float(p.importe):.2f} €{ref}")
    lineas.append("(Facturas emitidas registradas y aún no marcadas como cobradas.)")
    return "\n".join(lineas)


def _norm_nombre(s: object) -> str:
    """Normaliza un nombre para comparar contrapartes: minúsculas, sin acentos, sin espacios extra."""
    t = unicodedata.normalize("NFKD", str(s or "").lower())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


# Tokens de forma jurídica/genéricos: no identifican a un cliente por sí solos («SL» no es «la SL»).
_TOKENS_GENERICOS = {"sl", "sa", "slu", "sau", "scp", "sc", "cb", "slne", "sociedad", "limitada"}


def _sanea_nombre(s: object, limite: int = 80) -> str:
    """Limpia el nombre de cliente antes de meterlo en una respuesta AUTORITATIVA (se relaya verbatim
    y se reinyecta en el contexto del LLM): quita saltos de línea/controles y marcadores markdown/HTML,
    colapsa espacios y recorta. Neutraliza el phishing embebido en el campo `proveedor` de una factura
    (texto de un tercero, no de confianza). No altera el cálculo: solo cómo se MUESTRA el nombre."""
    t = re.sub(r"[\x00-\x1f\x7f]", " ", str(s or ""))  # controles + saltos de línea
    t = re.sub(r"[*_`#>\[\]<>|~]", "", t)  # marcadores markdown/HTML
    t = " ".join(t.split())
    return t[:limite].strip()


def _casa_contraparte(objetivo: str, contraparte: str) -> bool:
    """¿El nombre pedido `objetivo` identifica a esta `contraparte`? Coincidencia por PALABRA, no por
    substring crudo: «Acme» casa «Acme Dos SL» (prefijo de la razón social) y «García» casa «Marco
    García» (palabra), pero «Marco» NO casa «Comarco SL» y «SL»/«a» no casan a nadie. Evita reclamar a
    un tercero o agregar varios clientes bajo el nombre del primero."""
    o = _norm_nombre(objetivo)
    c = _norm_nombre(contraparte)
    if len(o) < 2 or not c or o in _TOKENS_GENERICOS:
        return False
    if o == c or c.startswith(o + " "):
        return True
    return o in [w for w in c.split() if w not in _TOKENS_GENERICOS]


def _reclamar_cobro_cliente(contraparte: str = "", **_: object) -> str:
    """Reclama el cobro de la(s) factura(s) pendiente(s) de un CLIENTE por su NOMBRE, sin que el
    usuario dicte el importe: localiza en las facturas REGISTRADAS las emitidas y aún no cobradas de
    esa contraparte y calcula su plan de cobro (Ley 3/2004). Cierra el flujo «reclama el cobro a Acme»
    sin importe — resuelve la factura en vez de pedir el dato o irse a buscar al correo. Determinista:
    el importe y el vencimiento salen de la factura registrada, no del LLM."""
    from ..skill_d_fiscal.conciliacion_cobros import (
        pendientes_con_vencimiento,
        rectificativas_pendientes,
    )

    nombre = str(contraparte or "").strip()
    try:
        store = ExpedienteStore(entity_id=_ENTIDAD_DEFECTO)
        todos = pendientes_con_vencimiento(store)
        rects = rectificativas_pendientes(store)
    except Exception as exc:  # noqa: BLE001
        return f"ERROR al leer tus facturas registradas: {exc}"
    if not todos:
        return (
            "No tienes ninguna factura emitida pendiente de cobro registrada. Regístrala (o dime el "
            "importe y el vencimiento) y te preparo la reclamación según la Ley 3/2004."
        )
    casos = [t for t in todos if _casa_contraparte(nombre, t[0].contraparte)]
    if not casos:
        # Sin nombre o sin coincidencia: enseña a QUIÉN se le debe (para que elija), en vez de pedir
        # un dato a ciegas o irse al correo. No inventa la factura de un cliente que no existe.
        clientes = sorted(
            {_sanea_nombre(p.contraparte) or "(cliente sin nombre)" for p, *_ in todos}
        )
        quien = f"«{_sanea_nombre(nombre)}»" if nombre else "ese cliente"
        return (
            f"No encuentro ninguna factura pendiente de cobro de {quien} en tus registros. "
            f"Tienes cobros pendientes de: {', '.join(clientes)}. Dime de cuál preparo la "
            "reclamación (o regístrala si te falta)."
        )
    # DESAMBIGUACIÓN: si el nombre casa con VARIOS clientes distintos, no agregues sus facturas bajo
    # el primero — pregunta de cuál (mejor que una reclamación con la contraparte equivocada).
    distintas = sorted({_sanea_nombre(p.contraparte) for p, *_ in casos})
    if len(distintas) > 1:
        return (
            f"«{_sanea_nombre(nombre)}» coincide con varios clientes: {', '.join(distintas)}. "
            "¿De cuál preparo la reclamación?"
        )
    cliente0 = _sanea_nombre(casos[0][0].contraparte) or "ese cliente"
    # NETEO de rectificativas (notas de abono) del MISMO cliente: una rectificativa que cancela la
    # factura deja la deuda neta en 0 → no hay nada que reclamar (no reclamar dinero ya anulado).
    bruto = round(sum(float(p.importe) for p, *_ in casos), 2)
    neg = round(sum(float(imp) for cp, imp in rects if _casa_contraparte(nombre, cp)), 2)
    neto = round(bruto + neg, 2)
    if neg and neto <= 0:
        return (
            f"La(s) rectificativa(s) de {cliente0} cancelan la deuda (facturado {bruto:.2f} € − "
            f"{abs(neg):.2f} € en rectificativas = {neto:.2f} €): no hay nada que reclamar."
        )
    bloques: list[str] = []
    for p, venc, estimado, pagado in casos:
        if venc:
            plan = _plan_cobro(total=float(p.importe), fecha_vencimiento=venc, cobrado=pagado)
            if estimado:
                plan += (
                    " (Sin vencimiento pactado en la factura: aplico el plazo legal de 30 días desde "
                    "la emisión, Ley 3/2004 art. 4.)"
                )
        else:
            saldo = float(p.importe) - pagado
            plan = (
                f"Saldo pendiente: {saldo:.2f} €. Esta factura no tiene ni vencimiento ni fecha de "
                "emisión registrada, así que no puedo fijar la etapa ni el interés de demora; dime el "
                "vencimiento y te calculo la reclamación completa."
            )
        ref = f" (factura {_sanea_nombre(p.referencia, 40)})" if p.referencia else ""
        bloques.append(
            f"• {_sanea_nombre(p.contraparte) or 'cliente'}{ref} — {float(p.importe):.2f} €:\n{plan}"
        )
    if len(casos) == 1:
        cab = (
            f"Reclamación de cobro de {cliente0} (Ley 3/2004), desde tus facturas registradas:\n\n"
        )
    else:
        cab = (
            f"{len(casos)} facturas pendientes de {cliente0} (Ley 3/2004), desde tus facturas "
            "registradas:\n\n"
        )
    if neg:  # hay rectificativas pero la deuda neta sigue siendo positiva → avisar
        cab += (
            f"⚠ OJO: hay {abs(neg):.2f} € en rectificativas de {cliente0}; la deuda NETA es "
            f"{neto:.2f} € (verifica antes de reclamar el bruto factura a factura).\n\n"
        )
    return cab + "\n\n".join(bloques)


def _resumen_financiero(periodo: str = "") -> str:
    """Resumen FINANCIERO COMPLETO de un periodo, TODO en una respuesta determinista: lo FACTURADO
    (ingresos), los GASTOS, el BENEFICIO, el IVA del 303 del periodo y cuánto te DEBEN (cobros
    pendientes). Para preguntas globales ('¿cómo va mi negocio?') o COMPUESTAS ('¿cuánto facturé Y
    cuánto me deben?'), que una sola tool no respondía entera (el force-tool enfocaba una métrica).
    """
    from ..skill_d_fiscal.conciliacion_cobros import pendientes_de_cobro

    desde, hasta, etiqueta = _rango_periodo(periodo)
    ámbito = etiqueta if desde else "total"
    try:
        store = ExpedienteStore(entity_id=_ENTIDAD_DEFECTO)
        lineas, _ = _recopilar_lineas(store, desde, hasta)
        pend = pendientes_de_cobro(store)
    except Exception as exc:  # noqa: BLE001
        return f"ERROR al leer tus facturas registradas: {exc}"

    emit = [ln for ln in lineas if ln.sentido == "devengado"]
    recib = [ln for ln in lineas if ln.sentido == "soportado"]
    if not emit and not recib and not pend:
        donde = f"en {etiqueta}" if desde else "registradas"
        return (
            f"No tienes facturas {donde} todavía. Regístralas (emitidas y recibidas) y te doy el "
            "resumen financiero completo: facturado, gastos, beneficio, 303 y lo que te deben."
        )
    base_e = round(sum(float(ln.base) for ln in emit), 2)
    iva_e = round(sum(float(ln.cuota) for ln in emit), 2)
    base_g = round(sum(float(ln.base) for ln in recib), 2)
    iva_g = round(sum(float(ln.cuota) for ln in recib), 2)
    beneficio = round(base_e - base_g, 2)
    deben_total = round(sum(float(p.importe) for p in pend), 2)

    partes = [
        f"Resumen financiero de {ámbito} (datos reales de tus facturas registradas):",
        f"  Facturado (ingresos): {len(emit)} factura(s) → base {base_e:.2f} € + IVA {iva_e:.2f} € "
        f"= {base_e + iva_e:.2f} €",
        f"  Gastos (recibidas): {len(recib)} factura(s) → base {base_g:.2f} € + IVA {iva_g:.2f} € "
        f"= {base_g + iva_g:.2f} €",
        f"  Beneficio (ingresos − gastos, sin IVA): {beneficio:.2f} €",
    ]
    if emit or recib:
        res = calcular_303(lineas)
        if res.resultado > 0:
            signo = "a ingresar"
        elif res.resultado < 0:
            signo = "a compensar/devolver"
        else:
            signo = "sin resultado"
        partes.append(
            f"  IVA del periodo (303): devengado {res.iva_devengado} € − deducible "
            f"{res.iva_deducible} € = {abs(res.resultado)} € ({signo})"
        )
    if pend:
        partes.append(
            f"  Te deben (cobros pendientes, saldo actual): {deben_total:.2f} € en "
            f"{len(pend)} factura(s)"
        )
    else:
        partes.append("  Te deben (cobros pendientes): nada pendiente.")
    if desde is None:
        partes.append(
            "\n⚠ No me diste un mes/trimestre claro, así que sumé TODO. Dime el periodo "
            "(p.ej. «2T 2026» o «junio 2026») para acotarlo."
        )
    return "\n".join(partes)


# ── D-4: COMPARATIVA periodo-vs-anterior (el autónomo piensa en EVOLUCIÓN, no en fotos sueltas) ────
_MES_NOM = [
    "",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]
_UNIDAD_NOMBRE = {"mes": "mes", "trimestre": "trimestre", "anio": "año"}


def _norm_unidad(unidad: str) -> str:
    """Normaliza la unidad de comparación a 'mes' | 'trimestre' | 'anio' (por defecto 'mes')."""
    u = (unidad or "").lower()
    if "trimestr" in u or u in ("t", "q", "3m"):
        return "trimestre"
    if "añ" in u or "an" in u or "anual" in u or "year" in u or "ejercicio" in u:
        return "anio"
    return "mes"


def _rango_mes_d4(anio: int, mes: int) -> tuple[date, date, str]:
    return date(anio, mes, 1), date(anio, mes, monthrange(anio, mes)[1]), f"{_MES_NOM[mes]} {anio}"


def _periodos_comparados(unidad: str, hoy: date):
    """(unidad_norm, (desde,hasta,etiq) ACTUAL, (desde,hasta,etiq) ANTERIOR) para mes/trimestre/año."""
    u = _norm_unidad(unidad)
    if u == "anio":
        a = hoy.year
        return (
            u,
            (date(a, 1, 1), date(a, 12, 31), str(a)),
            (
                date(a - 1, 1, 1),
                date(a - 1, 12, 31),
                str(a - 1),
            ),
        )
    if u == "trimestre":
        a, q = hoy.year, (hoy.month - 1) // 3 + 1
        sm = (q - 1) * 3 + 1
        act = (date(a, sm, 1), date(a, sm + 2, monthrange(a, sm + 2)[1]), f"{q}T {a}")
        pq, pa = (q - 1, a) if q > 1 else (4, a - 1)
        psm = (pq - 1) * 3 + 1
        ant = (date(pa, psm, 1), date(pa, psm + 2, monthrange(pa, psm + 2)[1]), f"{pq}T {pa}")
        return u, act, ant
    a, m = hoy.year, hoy.month
    pa, pm = (a, m - 1) if m > 1 else (a - 1, 12)
    return u, _rango_mes_d4(a, m), _rango_mes_d4(pa, pm)


def _metricas_periodo(store: "ExpedienteStore", desde: date, hasta: date) -> dict:
    """Facturado/gastado/beneficio (base, sin IVA) de un rango, desde las facturas registradas."""
    lineas, _ = _recopilar_lineas(store, desde, hasta)
    emit = [ln for ln in lineas if ln.sentido == "devengado"]
    recib = [ln for ln in lineas if ln.sentido == "soportado"]
    base_e = round(sum(float(ln.base) for ln in emit), 2)
    base_g = round(sum(float(ln.base) for ln in recib), 2)
    return {
        "n_emit": len(emit),
        "base_e": base_e,
        "n_recib": len(recib),
        "base_g": base_g,
        "beneficio": round(base_e - base_g, 2),
        "vacio": not emit and not recib,
    }


def _variacion(actual: float, anterior: float) -> tuple[str, str]:
    """(Δ en €, Δ en %). Maneja anterior=0 (sin base de comparación → no se inventa un %)."""
    delta = round(actual - anterior, 2)
    signo = "+" if delta > 0 else ""
    if anterior == 0:
        pct = "—" if actual == 0 else "(no había nada el periodo anterior)"
    else:
        pct = f"{signo}{round(delta / abs(anterior) * 100, 1):.1f}%"
    return f"{signo}{delta:.2f} €", pct


def _resumen_comparativo(unidad: str = "mes") -> str:
    """Compara un periodo con el ANTERIOR (este mes vs el mes pasado, trimestre vs trimestre anterior,
    año vs año pasado): FACTURADO, GASTOS y BENEFICIO, con la variación en € y en %. Responde «¿facturé
    más que el mes pasado?», «¿cómo va mi crecimiento?». Determinista; NO predice el futuro."""
    u, (d_a, h_a, et_a), (d_b, h_b, et_b) = _periodos_comparados(unidad, date.today())
    try:
        store = ExpedienteStore(entity_id=_ENTIDAD_DEFECTO)
        ma = _metricas_periodo(store, d_a, h_a)
        mb = _metricas_periodo(store, d_b, h_b)
    except Exception as exc:  # noqa: BLE001
        return f"ERROR al leer tus facturas registradas: {exc}"
    if ma["vacio"] and mb["vacio"]:
        return (
            f"No tienes facturas registradas en {et_a} ni en {et_b}, así que no hay nada que comparar. "
            "Regístralas y te comparo la evolución."
        )
    fact_d, fact_p = _variacion(ma["base_e"], mb["base_e"])
    gast_d, gast_p = _variacion(ma["base_g"], mb["base_g"])
    ben_d, ben_p = _variacion(ma["beneficio"], mb["beneficio"])
    if ma["base_e"] > mb["base_e"]:
        titular = "facturaste MÁS"
    elif ma["base_e"] < mb["base_e"]:
        titular = "facturaste MENOS"
    else:
        titular = "facturaste IGUAL"
    return (
        f"Comparativa {et_a} vs {et_b} (datos reales de tus facturas registradas):\n"
        f"  Facturado: {ma['base_e']:.2f} € vs {mb['base_e']:.2f} € → {fact_d} ({fact_p})\n"
        f"  Gastos:    {ma['base_g']:.2f} € vs {mb['base_g']:.2f} € → {gast_d} ({gast_p})\n"
        f"  Beneficio: {ma['beneficio']:.2f} € vs {mb['beneficio']:.2f} € → {ben_d} ({ben_p})\n"
        f"En resumen: este {_UNIDAD_NOMBRE[u]} {titular} que el anterior."
    )


tool_registry.register(
    ToolDefinition(
        name="resumen_comparativo",
        description=(
            "COMPARA un periodo con el ANTERIOR (este mes vs el mes pasado, este trimestre vs el "
            "anterior, este año vs el pasado): facturado, gastos y beneficio, con la variación en € y "
            "en %. Úsala para «¿he facturado más que el mes pasado?», «¿cuánto he crecido?», «¿voy "
            "mejor que el año pasado?», evolución/tendencia. NO predice el futuro. Solo lectura."
        ),
        parameters={
            "type": "object",
            "properties": {
                "unidad": {
                    "type": "string",
                    "enum": ["mes", "trimestre", "anio"],
                    "description": "Unidad a comparar con su anterior: 'mes', 'trimestre' o 'anio'.",
                },
            },
        },
        fn=_resumen_comparativo,
        category="base",
        authoritative=True,
    )
)


tool_registry.register(
    ToolDefinition(
        name="cobros_pendientes",
        description=(
            "Dice CUÁNTO te DEBEN y QUIÉN: suma tus facturas emitidas aún no cobradas (cobros "
            "pendientes), con el cliente y el importe de cada una. Úsala cuando pregunten cuánto les "
            "deben, quién les debe, qué tienen por cobrar o sus facturas pendientes de cobro. Solo lectura."
        ),
        parameters={"type": "object", "properties": {}},
        fn=_cobros_pendientes,
        category="base",
        authoritative=True,
    )
)


tool_registry.register(
    ToolDefinition(
        name="reclamar_cobro_cliente",
        description=(
            "RECLAMA el cobro de la(s) factura(s) pendiente(s) de un CLIENTE por su NOMBRE, cuando el "
            "usuario NO dice el importe (p.ej. «reclama el cobro de la factura vencida de Acme», "
            "«cóbrale a García lo que me debe»). Busca en tus facturas REGISTRADAS las emitidas a esa "
            "contraparte aún no cobradas y calcula el plan de cobro (Ley 3/2004): saldo, días "
            "vencidos, etapa, compensación de 40 € e interés de demora. NO envía nada. Úsala en vez de "
            "pedir el importe o buscar en el correo cuando el usuario nombra al cliente."
        ),
        parameters={
            "type": "object",
            "properties": {
                "contraparte": {
                    "type": "string",
                    "description": "Nombre del cliente al que reclamar el cobro (p.ej. 'Acme').",
                },
            },
            "required": ["contraparte"],
        },
        fn=_reclamar_cobro_cliente,
        category="base",
        authoritative=True,
    )
)


tool_registry.register(
    ToolDefinition(
        name="resumen_facturacion",
        description=(
            "Resumen ECONÓMICO de un periodo —mes ('junio', 'este mes') o trimestre ('2T 2026')— desde "
            "las facturas registradas: cuánto has FACTURADO (ingresos), cuánto has GASTADO (recibidas) "
            "y tu BENEFICIO. Úsala cuando pregunten cuánto han facturado/ingresado/gastado o su "
            "beneficio en un mes/trimestre. NO es el 303 (eso es el IVA a liquidar). Solo lectura."
        ),
        parameters={
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "description": "Mes o trimestre, p.ej. 'junio 2026' o '2T 2026'.",
                },
            },
        },
        fn=_resumen_facturacion,
        category="base",
        authoritative=True,
    )
)


tool_registry.register(
    ToolDefinition(
        name="resumen_financiero",
        description=(
            "Resumen FINANCIERO COMPLETO de un periodo en UNA respuesta: lo FACTURADO (ingresos), los "
            "GASTOS, el BENEFICIO, el IVA del 303 del periodo y cuánto te DEBEN (cobros pendientes). "
            "ÚSALA para preguntas GLOBALES ('¿cómo voy?', 'resumen financiero') o COMPUESTAS que pidan "
            "VARIAS métricas a la vez ('¿cuánto he facturado y cuánto me deben?'). Una sola tool las "
            "junta todas; no encadenes varias. Solo lectura."
        ),
        parameters={
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "description": "Mes o trimestre, p.ej. 'junio 2026' o '2T 2026'. Opcional.",
                },
            },
        },
        fn=_resumen_financiero,
        category="base",
        authoritative=True,
    )
)


tool_registry.register(
    ToolDefinition(
        name="calcular_303_registradas",
        description=(
            "Calcula el BORRADOR del 303 (IVA del trimestre) desde las facturas que YA tienes "
            "registradas (datos reales, deterministas). PREFIÉRELA sobre calcular_303 cuando el "
            "usuario tenga facturas registradas: no hay que dictar cifras a mano ni arriesgar errores. "
            "Si no hay facturas registradas, lo dice y pide registrarlas."
        ),
        parameters={
            "type": "object",
            "properties": {
                "periodo": {"type": "string", "description": "Periodo, p.ej. '2T 2026'."},
            },
        },
        fn=_calcular_303_registradas,
        category="base",
        authoritative=True,
    )
)


tool_registry.register(
    ToolDefinition(
        name="registrar_factura",
        description=(
            "Registra y GUARDA una factura: emitida (a un cliente) o recibida (de un proveedor). "
            "Persiste la factura para que luego compute tu 303 con datos reales. Úsala cuando el "
            "usuario quiera registrar/apuntar/emitir una factura. Pasa SOLO las cifras que te dé; "
            "si falta la base imponible, pregunta. NO inventes importes ni NIF."
        ),
        parameters={
            "type": "object",
            "properties": {
                "contraparte": {
                    "type": "string",
                    "description": "Nombre del cliente (si emitida) o proveedor (si recibida).",
                },
                "base": {"type": "number", "description": "Base imponible en € (sin IVA)."},
                "numero": {"type": "string", "description": "Número de factura, si lo hay."},
                "iva": {
                    "type": "number",
                    "description": "Cuota de IVA en €, si la sabes. Si no, se calcula con 'tipo'.",
                },
                "tipo": {
                    "type": "number",
                    "description": "Tipo de IVA (% o fracción) si no das la cuota. Por defecto 21%.",
                },
                "sentido": {
                    "type": "string",
                    "enum": ["emitida", "recibida"],
                    "description": "'emitida' (la haces tú a un cliente) o 'recibida' (de un proveedor).",
                },
                "fecha": {"type": "string", "description": "Fecha de la factura (YYYY-MM-DD)."},
                "nif": {"type": "string", "description": "NIF de la contraparte, si lo hay."},
            },
            "required": ["contraparte", "base"],
        },
        fn=_registrar_factura,
        category="base",
        authoritative=True,
    )
)


tool_registry.register(
    ToolDefinition(
        name="plan_cobro",
        description=(
            "Calcula el plan de cobro de UNA factura impagada o vencida según la Ley 3/2004 "
            "de morosidad: saldo pendiente, días vencidos, etapa de reclamación, compensación "
            "legal de 40 € e interés de demora (tipo legal del BOE). Úsala cuando el usuario "
            "quiera reclamar un cobro o saber cómo está una factura pendiente. NO envía nada."
        ),
        parameters={
            "type": "object",
            "properties": {
                "total": {"type": "number", "description": "Importe total de la factura (€)."},
                "fecha_vencimiento": {
                    "type": "string",
                    "description": "Fecha de vencimiento (YYYY-MM-DD o DD/MM/YYYY).",
                },
                "cobrado": {
                    "type": "number",
                    "description": "Importe ya cobrado (€). 0 si nada.",
                    "default": 0,
                },
                "tipo_interes_anual": {
                    "type": "number",
                    "description": "Tipo de interés de demora anual en %, si se conoce. "
                    "Si se omite, se usa el tipo legal del BOE.",
                },
            },
            "required": ["total", "fecha_vencimiento"],
        },
        fn=_plan_cobro,
        category="base",
        authoritative=True,
    )
)

tool_registry.register(
    ToolDefinition(
        name="calcular_303",
        description=(
            "Calcula un BORRADOR del 303 a partir de cifras que el USUARIO TE DICTA EN EL MENSAJE "
            "(p.ej. «mi 303 con ventas 10.000 al 21% y compras 2.000 al 21%»). Úsala SOLO en ese caso. "
            "Si el usuario tiene facturas REGISTRADAS (lo normal), NO uses esta: usa "
            "calcular_303_registradas (fiable, sin dictar cifras). Devuelve devengado, deducible y "
            "resultado. Borrador, NO presentación. Pasa EXACTAMENTE las cifras del usuario; NO inventes "
            "ni añadas líneas, importes ni tipos. Si faltan datos, NO los rellenes: pregunta con ask_user."
        ),
        parameters={
            "type": "object",
            "properties": {
                "iva_repercutido": {
                    "type": "array",
                    "description": "Ventas emitidas: lista de {base, tipo}. tipo en % (21) o fracción (0.21).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "base": {"type": "number"},
                            "tipo": {"type": "number"},
                            "concepto": {"type": "string"},
                        },
                        "required": ["base"],
                    },
                },
                "iva_soportado": {
                    "type": "array",
                    "description": "Compras recibidas deducibles: lista de {base, tipo}.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "base": {"type": "number"},
                            "tipo": {"type": "number"},
                            "concepto": {"type": "string"},
                        },
                        "required": ["base"],
                    },
                },
                "periodo": {
                    "type": "string",
                    "description": "Periodo, p.ej. '2T 2026'.",
                },
            },
        },
        fn=_calcular_303,
        category="base",
        authoritative=True,
    )
)
