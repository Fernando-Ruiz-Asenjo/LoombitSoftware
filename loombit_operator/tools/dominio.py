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
        out.append(
            LineaIVA(
                base=it["base"],
                tipo=_norm_tipo(it.get("tipo", 0.21)),
                sentido=sentido,
                concepto=str(it.get("concepto", defecto)),
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
