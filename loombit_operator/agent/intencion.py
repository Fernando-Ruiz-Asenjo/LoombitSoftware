"""
Detección DETERMINISTA de intención que EXIGE herramienta — para forzar la tool CORRECTA.

El 14B a veces (a) calcula a ojo y fabrica cifras (cobro/303), (b) dice que buscó sin buscar. Para
esas intenciones forzamos `tool_choice` Y enfocamos las tools a la(s) correcta(s), de modo que:
  - en cobro/303/factura NO pueda calcular a mano NI elegir la tool equivocada;
  - PERO solo si la petición trae el DATO (un número): si faltan datos, NO forzamos → que pregunte,
    no que invente (regresión observada: forzar sin datos hacía que Qwen inventara importes).

Puro y testeable. Ver docs/ALGORITMO_CEREBRO.md.
"""

from __future__ import annotations

import re

from .parsers import parsear_importe_es

# «venc\w+» cubre vence/venció/vencía/vencida/vencido/vencimiento (antes solo «vencid\w+» → «venció»
# en pasado NO casaba y la consulta de cobro se iba a un free-form que alucinaba tools).
_COBRO = re.compile(r"\b(cobro|cobrar|reclam\w+|moros\w+|impag\w+|deuda|deudas|venc\w+|demora)\b")
# Verbo CLARO de reclamar/cobrar (NO el mero «vence», que en una pregunta de fecha no es reclamación):
# para enrutar «reclama el cobro a <Cliente>» SIN importe → reclamar la factura registrada del cliente.
# Tolerante a acentos en imperativos enclíticos («cóbrale», «reclámale») — igual que _FACTURA.
_RECLAMO_VERBO = re.compile(r"\b(c[oó]br\w+|recl[aá]m\w+|moros\w+|impag\w+|adeud\w*|deuda\w*)\b")
# Contraparte NOMBRADA: un nombre propio (mayúscula inicial en el texto ORIGINAL) tras una preposición
# mid-frase que indica que ESE cliente me debe a MÍ («a Acme», «de García»). Se EXCLUYEN «con/para/
# contra», que marcan la dirección contraria (una deuda MÍA o una reclamación de consumo: «deuda con
# Endesa», «reclamación para Iberdrola»). La preposición en minúscula evita casar la mayúscula inicial
# de la frase; el nombre propio es señal de baja-falso-positivo de que hay un cliente concreto.
_PREP_NOMBRE = re.compile(r"\b(?:a|de|al)\s+([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ&.\-]*)")
# Variante para nombres con artículo inicial («a El Corte Inglés», «de La Caixa»): preposición +
# artículo capitalizado + el nombre propio (lo que se valida es el nombre, no el artículo).
_PREP_ART_NOMBRE = re.compile(
    r"\b(?:a|de|al)\s+(?:[Ee]l|[Ll]a|[Ll]os|[Ll]as)\s+([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ&.\-]*)"
)
# Palabras que, aun capitalizadas tras preposición, NO son una contraparte (instituciones, meses,
# días, genéricos fiscales). Sin esto, «el IVA de Marzo» o «la deuda de Hacienda» pasarían por cliente.
_NO_CONTRAPARTE = {
    "hacienda",
    "aeat",
    "iva",
    "irpf",
    "el",
    "la",
    "los",
    "las",
    "ley",
    "seguridad",
    "social",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "setiembre",
    "octubre",
    "noviembre",
    "diciembre",
    "lunes",
    "martes",
    "miercoles",
    "miércoles",
    "jueves",
    "viernes",
    "sabado",
    "sábado",
    "domingo",
    "cliente",
    "factura",
    "cobro",
    "deuda",
    "empresa",
    "todos",
    "nadie",
    "alguien",
}
# Indicios de que la deuda es MÍA (la pago yo), no un cobro a un cliente: «tengo/mi/una deuda…», «le
# debo…», «debo a…». Inhibe forzar reclamar_cobro_cliente (mejor que el LLM lo gestione).
_DEUDA_PROPIA = re.compile(
    r"\b(tengo|mi|mis|una|esa)\b[^.\n]{0,18}\bdeuda\b|\b(le\s+)?debo\b|\bdeb[eo]\w*\s+a\b|\bpagar\s+a\b"
)
# La reclamación ya NO procede: la factura YA está cobrada/pagada, o el usuario NIEGA reclamar, o es un
# FUTURO condicional («cuando cobre»). Sin esto, «ya he cobrado la factura de Acme» o «no le reclames,
# ya pagó» forzaban una reclamación Ley 3/2004 contra quien acaba de pagar.
_RECLAMO_INHIBIDO = re.compile(
    r"\bya\b[^.\n]{0,20}\b(cobr\w+|pag\w+|abon\w+|liquidad\w+|saldad\w+)\b"
    r"|\b(cobrad|pagad|abonad|saldad)\w*\b[^.\n]{0,12}\b(ya|por\s+completo)\b"
    r"|\bmarca\w*\s+(la\s+factura\s+|esa\s+|esta\s+)?(como\s+)?(cobrad|pagad)\w*"
    r"|\bcuando\s+(la\s+|me\s+)?(cobr\w*|pag\w*)"
    r"|\bno\s+(le\s+|la\s+|les\s+|me\s+)?(reclam\w*|cobr\w*|insist\w*)"
)
_F303 = re.compile(r"\b(303|iva|trimestral|repercutid\w+|soportad\w+|devengad\w+|liquidaci[oó]n)\b")
# 303 «con lo que tengo registrado/apuntado»: lee las facturas registradas → NO necesita un número.
_F303_REGISTRADAS = re.compile(
    r"registrad\w+|apuntad\w+|mis\s+factura|con\s+lo\s+que\s+tengo|lo\s+(que\s+tengo\s+)?(registr|apunt)"
)
# OJO: debe casar el COMANDO de crear factura ("regístrame/emite una factura"), NO el adjetivo
# "facturas registradas/emitidas" (eso es una consulta sobre lo YA registrado → intención 303).
_FACTURA = re.compile(
    # verbos de registro «pegados» (regístrame/apúntame/factúrame/emíteme)…
    r"\b(reg[ií]strame|ap[uú]ntame|fact[uú]ra(?:me|le|les|nos|lo|la)|em[ií]teme)\b"
    # …o un verbo de registro (incluido coloquial: mete/anota/añade/introduce/carga) cerca del
    # sustantivo factura/venta/minuta o de «facturé/vendí». Acota a REGISTRAR, no a consultar.
    r"|\b(reg[ií]stra\w*|ap[uú]nta\w*|em[ií]t\w+|an[oó]ta\w*|m[eé]te\w*|pon\w*|gu[aá]rda\w*|a[ñn][aá]de\w*|introd[uú]ce\w*|c[aá]rga\w*"
    r"|fact[uú]r\w*)\b[^.\n]{0,30}\b(factur\w+|venta\w*|vend[ií]\w*|minuta\w*)\b"
)
_BUSCAR_CORREO = re.compile(
    r"\b(busca\w*|b[uú]scame|encuentra|revisa|mira)\b[^\n]{0,25}\b"
    r"(correo|correos|email|e-mail|mail|bandeja|mensaje\w*|inbox)\b"
)
# «¿cuál es el correo/email/teléfono de <persona>?», «dame el contacto de X», «¿cómo contacto con X?»
# = AVERIGUAR los datos de contacto de una persona por su nombre → contacts_find. Distinto de
# _BUSCAR_CORREO (lleva verbo de búsqueda: «busca correos de…») y del ENVÍO («un correo A Ana»): aquí
# es «… DE <nombre>». Antes no existía esta intención, así que «¿cuál es el correo de David?» no forzaba
# contacts_find y el 14B acababa PIDIENDO el dato al usuario (viola «acierta, no preguntes»). RC·Cerebro.
_CONTACTO = re.compile(
    r"\b(correo|email|e-mail|mail|tel[eé]fono|m[oó]vil|contacto|direcci[oó]n)\b"
    r"[^.\n]{0,18}\bde\b\s+[a-záéíóúñ]"
    r"|\bc[oó]mo\s+(?:puedo\s+)?contact\w+"
)
# «recuérdame [hacer X] [cuándo]» = crear un EVENTO de recordatorio, NO registrar/ejecutar la acción.
# El 14B lo confundía con registrar un pago/factura y pedía NIF; aquí forzamos calendar_create.
# NO incluimos «apúntame que …»: es AMBIGUO («apúntame que el cliente prefiere transferencia» es un
# HECHO/nota sin fecha, no un evento) → forzar calendar_create creaba un evento absurdo. Solo señales
# inequívocas de recordatorio temporal.
_RECORDATORIO = re.compile(
    r"\b(recu[eé]rdame\w*|recordatorio|acu[eé]rdame|av[ií]same\w*|no se me olvide)\b"
)
# «¿cuánto he facturado/ingresado este mes?» = sumar las emitidas (resumen_facturacion), NO el 303 ni
# registrar. El 14B no la elegía de forma fiable → la forzamos. Pregunta nº1 de un autónomo.
_FACTURACION = re.compile(
    r"\bcu[aá]nto\b[^\n]{0,25}\b(factur\w+|ingres\w+|gast\w+)\b"
    r"|\bqué\b[^\n]{0,15}\b(gast[eé]|factur[eé]|ingres[eé]|vend[ií])\b"  # «qué gasté/facturé» (interrogativo)
    r"|\b(mi facturaci[oó]n|facturaci[oó]n de|total facturad\w+|benefici\w+|mis gastos"
    r"|mis ingres\w+|ingres\w+ de|mis ventas)\b"
)
# «¿cuánto me deben?»/«¿quién me debe?» = sumar los cobros pendientes (cobros_pendientes), NO plan_cobro
# (una factura) ni el 303. El agente caía a memory_search y daba un número contaminado.
_COBROS_PEND = re.compile(
    r"\b(me deben|me debe|me adeud\w*|qui[eé]n me debe|por cobrar|cobros pendientes|pendiente[s]? de cobro"
    r"|sin cobrar|facturas? impagad\w+)\b"
)
# «resumen financiero», «¿cómo voy?» o una pregunta COMPUESTA que cruza ≥2 familias de métrica
# (facturado/gastos · me-deben · 303/IVA) → resumen_financiero: UNA tool determinista que las junta
# TODAS. Sin esto, el force-tool enfoca a UNA intención y excluye las otras dominio-tools del run, así
# que «¿cuánto facturé Y cuánto me deben?» solo respondía la 1ª métrica (P2 del loop anterior).
_RESUMEN_GLOBAL = re.compile(
    r"resumen\s+(financ\w*|econ[oó]m\w*|de\s+(mis\s+|las\s+)?(cuentas|finanzas|n[uú]meros))"
    r"|c[oó]mo\s+va\w*\s+(mi|el)\s+negocio"
    r"|c[oó]mo\s+va\w*\s+mis\s+(cuentas|finanzas|n[uú]meros)"
    r"|c[oó]mo\s+voy\s+de\s+(dinero|cuentas|finanzas|n[uú]meros|pasta)"
    r"|situaci[oó]n\s+(financ\w*|econ[oó]m\w*)"
    r"|estado\s+de\s+(mis\s+)?(finanzas|cuentas)"
    r"|balance\s+(econ[oó]m\w*|general|de\s+mis\s+(cuentas|finanzas))"
    r"|mis\s+finanzas\b|mis\s+n[uú]meros\b"
)
_FAM_FACT = re.compile(r"\b(factur\w+|ingres\w+|gast\w+|benefici\w+)\b")
_FAM_303 = re.compile(r"\b(303|iva|liquidaci[oó]n\w*)\b")
# Coordinación de DOS métricas en la misma frase (evita que «¿cuánto IVA he facturado?» —una métrica
# con 'iva' como objeto— dispare el resumen): conjunción «y/e», «también/además», o dos «cuánt…».
_MULTI_ASK = re.compile(r"\b(y|e|tambi[eé]n|adem[aá]s)\b|junto\s+con|as[ií]\s+como")


# Un REGISTRO de factura ('registra/apúntame/emite una factura …') es una ACCIÓN, no un resumen —
# aunque mencione 'factura' e 'IVA' (que casarían como 2 familias). Verbo de registro pegado al
# sustantivo. Sin esto, «registra una factura con base e IVA» mis-rutaba a resumen_financiero y la
# tool registrar_factura no se ofrecía (destapado por el e2e de D-3).
_REGISTRO_FACTURA = re.compile(
    r"\b(reg[ií]str\w+|ap[uú]nt\w+|anot\w+|em[ií]t\w+)\b[^.\n]{0,20}"
    r"\b(una |la |mi |esta |esa )?(factura|minuta|rectificativa)\w*",
    re.IGNORECASE,
)


# D-4: COMPARATIVA periodo-vs-anterior («¿facturé más que el mes pasado?», «¿cuánto he crecido?»,
# evolución/tendencia). El autónomo piensa en evolución. NO incluye la PREDICCIÓN del futuro (sin datos).
_COMPARATIVA = re.compile(
    r"\b(comp[aá]r\w+|crec\w+|crecimiento|evoluci\w+|tendenci\w+|versus)\b|\bvs\b"
    r"|\b(m[aá]s|menos|mejor|peor|igual)\b[^.\n]{0,45}\bque\b[^.\n]{0,25}\b(mes|trimestre|a[ñn]o|ejercicio|anterior|pasad\w+)"
    r"|\brespecto\s+al?\b[^.\n]{0,25}\b(mes|trimestre|a[ñn]o|ejercicio)"
    r"|\bcontra\s+(el\s+|la\s+)?(mes|trimestre|a[ñn]o|ejercicio|anterior|pasad\w+)"
    r"|\b(mes|trimestre|a[ñn]o|ejercicio)\s+(pasad\w+|anterior)\b",
    re.IGNORECASE,
)
# Predicción del FUTURO: NO se computa (no hay datos) → excluye la comparativa (que es pasado/actual).
_PREDICCION = re.compile(
    r"\b(facturar[eé]|ganar[eé]|ingresar[eé]|tendr[eé]|ir[eé]\b|voy\s+a\s+\w+"
    r"|pr[oó]xim\w+\s+(mes|trimestre|a[ñn]o|semana)|(mes|trimestre|a[ñn]o|semana)\s+que\s+viene"
    r"|a\s+este\s+ritmo|predic\w+|estimaci\w+|proyec\w+|previsi\w+|forecast)\b",
    re.IGNORECASE,
)


def _es_comparativa(t: str) -> bool:
    """True si pide comparar un periodo con el ANTERIOR (evolución/crecimiento), y NO es una predicción
    del futuro (que no se computa)."""
    return bool(_COMPARATIVA.search(t)) and not _PREDICCION.search(t)


def _es_resumen_financiero(t: str) -> bool:
    """True si pide una visión GLOBAL ('resumen financiero', '¿cómo va mi negocio?') o COMPUESTA
    (≥2 familias de métrica financiera coordinadas) → se compone con la tool resumen_financiero."""
    if _REGISTRO_FACTURA.search(t):  # un registro de factura no es un resumen (es una acción)
        return False
    if _RESUMEN_GLOBAL.search(t):
        return True
    familias = sum(bool(rx.search(t)) for rx in (_FAM_FACT, _COBROS_PEND, _FAM_303))
    if familias < 2:
        return False
    return bool(_MULTI_ASK.search(t)) or len(re.findall(r"cu[aá]nt", t)) >= 2


# Hay un DATO numérico (cifra o número en palabras) → tiene sentido calcular; si no, hay que preguntar.
_TIENE_DATO = re.compile(
    r"\d|\b(mil|cien|ciento|doscient\w+|trescient\w+|cuatrocient\w+|quinient\w+|"
    r"seiscient\w+|setecient\w+|ochocient\w+|novecient\w+)\b"
)

# Tools a las que se LIMITA la llamada forzada (+ ask_user/task_done para poder preguntar o terminar).
_TOOLS_POR_INTENCION: dict[str, set[str]] = {
    "cobro": {"plan_cobro"},
    "cobro_cliente": {"reclamar_cobro_cliente"},
    "303": {"calcular_303", "calcular_303_registradas"},
    "factura": {"registrar_factura"},
    "buscar": {"gmail_search"},
    "recordatorio": {"calendar_create"},
    "facturacion": {"resumen_facturacion"},
    "cobros_pend": {"cobros_pendientes"},
    "resumen_financiero": {"resumen_financiero"},
    "comparativo": {"resumen_comparativo"},
    "contacto": {"contacts_find"},
}
_SIEMPRE = {"ask_user", "task_done"}


def tiene_dato(task: str) -> bool:
    """True si la petición trae un DATO numérico (cifra o número en palabras). Lo usa el clasificador
    LLM de respaldo: cobro/303/factura SIN dato no se fuerzan (que pregunte, no que invente)."""
    return bool(_TIENE_DATO.search((task or "").lower()))


def _contraparte_nombrada(task: str) -> bool:
    """True si la petición nombra a una CONTRAPARTE (cliente) con nombre propio: «… de Acme», «a
    García», «a El Corte Inglés». Usa el texto ORIGINAL (la mayúscula del nombre propio es la señal);
    descarta genéricos («el cliente de siempre» → ningún nombre propio tras la preposición)."""
    for m in _PREP_NOMBRE.finditer(task or ""):
        if m.group(1).lower() not in _NO_CONTRAPARTE:
            return True
    # Razones sociales que EMPIEZAN por artículo («El Corte Inglés», «La Caixa»): el artículo solo no
    # es contraparte, pero seguido de un nombre propio capitalizado sí lo es (lo capta el grupo).
    for m in _PREP_ART_NOMBRE.finditer(task or ""):
        if m.group(1).lower() not in _NO_CONTRAPARTE:
            return True
    return False


def intencion_consecuente(task: str) -> str | None:
    """Intención que EXIGE herramienta: 'cobro'|'303'|'factura'|'buscar', o None.
    Para cobro/303/factura exige además un DATO numérico (si no, None → que pregunte)."""
    t = (task or "").lower()
    if _RECORDATORIO.search(t):  # antes que todo: «recuérdame pagar…» es recordatorio, no un pago
        return "recordatorio"
    if _es_comparativa(t):  # D-4: «¿facturé más que el mes pasado?» → comparativa, no foto suelta
        return "comparativo"
    # Query GLOBAL o COMPUESTA (≥2 métricas) → resumen_financiero ANTES que las single-métrica, porque
    # una compuesta también casa con facturacion/cobros_pend/303 (y antes solo respondía la 1ª).
    if _es_resumen_financiero(t):
        return "resumen_financiero"
    # «¿cuánto he facturado?» = resumen; pero «¿cuánto IVA con las 303 facturas?» es 303, no facturación.
    # «¿cuánto voy a facturar el mes que viene?» = PREDICCIÓN (futuro) → no se fuerza (abstención honesta).
    if _FACTURACION.search(t) and not _F303.search(t) and not _PREDICCION.search(t):
        return "facturacion"
    # Un IMPORTE de verdad (€, «800», «1.500») ≠ un dígito cualquiera (una FECHA, un nº de factura):
    # parsear_importe_es excluye fechas/%/días y exige un único importe. Sin esto, «… que venció el 15
    # de mayo» mandaba el cobro-por-cliente a plan_cobro (que pide el total) por el «15» de la fecha.
    tiene_importe = parsear_importe_es(task) is not None
    # «¿cuánto me deben?» = agregado de cobros pendientes. PERO una reclamación IMPERATIVA con importe
    # concreto («reclama los 2000 € que me debe Acme») NO es la consulta agregada: ahí el «me debe»
    # DESCRIBE el importe, no pregunta cuánto → debe ir a plan_cobro (cobro), no a cobros_pendientes.
    if _COBROS_PEND.search(t) and not (_RECLAMO_VERBO.search(t) and tiene_importe):
        return "cobros_pend"
    if _BUSCAR_CORREO.search(t):
        return "buscar"
    # «el correo/email/teléfono/contacto de <persona>» → averiguar su contacto (contacts_find), NO
    # pedírselo al usuario. Va DESPUÉS de buscar (que lleva verbo) y de cobros_pend (financiero).
    if _CONTACTO.search(t):
        return "contacto"
    tiene_dato = bool(_TIENE_DATO.search(t))
    # La reclamación ya no procede (ya cobrada / negada / futura) → no se fuerza ninguna ruta de cobro;
    # que lo gestione el LLM (p.ej. marcar la factura cobrada), no una reclamación contra quien pagó.
    reclamo_inhibido = bool(_RECLAMO_INHIBIDO.search(t))
    # factura ANTES que 303: "regístrame una factura … más IVA" menciona IVA pero es factura.
    if _FACTURA.search(t) and tiene_dato:
        return "factura"
    if _COBRO.search(t) and tiene_importe and not reclamo_inhibido:
        return "cobro"
    # 303 con DATO, o «calcula el IVA del trimestre con mis facturas registradas» (sin número: las lee).
    # VA ANTES de cobro_cliente: «calcula el IVA… la de Acme sigue impagada» es una consulta fiscal, no
    # una reclamación — el «impagada de Acme» no debe secuestrar el 303.
    if _F303.search(t) and (tiene_dato or _F303_REGISTRADAS.search(t)):
        return "303"
    # COBRO por CLIENTE sin importe: «reclama el cobro de la factura vencida de Acme» → resuelve la
    # factura REGISTRADA de esa contraparte y calcula el plan (Ley 3/2004), en vez de pedir el importe
    # o irse a buscar al correo. Va DESPUÉS del cobro-con-importe y del 303; respeta la inhibición.
    if _RECLAMO_VERBO.search(t) and _contraparte_nombrada(task) and not reclamo_inhibido:
        if not _DEUDA_PROPIA.search(
            t
        ):  # «tengo una deuda con/a X» es deuda MÍA, no un cobro a cliente
            return "cobro_cliente"
    return None


def tools_foco(intencion: str | None) -> set[str]:
    """Conjunto de nombres de tool al que limitar la llamada forzada para esa intención."""
    if not intencion:
        return set()
    if intencion == "recordatorio":
        # SOLO calendar_create: un recordatorio se CREA. Sin ask_user NI task_done, el 14B no puede
        # escaparse a «necesito el NIF» — lo crea con el texto y la fecha (calendar_create GATEA, así
        # que el usuario lo aprueba; ningún efecto autónomo).
        return {"calendar_create"}
    if intencion == "facturacion":
        # SOLO resumen_facturacion (SIN task_done): que SUME de verdad. Con task_done en el foco, el
        # 14B se escapaba a él narrando «no encontré facturas en la bandeja» sin llamar la tool de
        # datos (visto en la batería live con «gastado»/«beneficio»). Forzar la tool lo impide.
        return {"resumen_facturacion"}
    if intencion == "cobros_pend":
        return {"cobros_pendientes"}
    if intencion == "cobro_cliente":
        # SOLO reclamar_cobro_cliente: que RESUELVA la factura del cliente y calcule el plan, sin
        # escaparse a ask_user («¿qué importe?») ni a buscar en el correo. La tool ya degrada con
        # gracia si no hay coincidencia (lista a quién se le debe).
        return {"reclamar_cobro_cliente"}
    if intencion == "contacto":
        # SOLO contacts_find: que RESUELVA el contacto por nombre, sin escaparse a ask_user (pedirle
        # el dato al usuario). Si no lo encuentra, la tool degrada con gracia y el agente lo narra.
        return {"contacts_find"}
    if intencion == "resumen_financiero":
        # un solo tool que COMPONE todas las métricas (facturado+gastos+beneficio+303+me-deben).
        return {"resumen_financiero"}
    if intencion == "factura":
        # registrar_factura + ask_user (por si falta un dato), SIN task_done: que REGISTRE de verdad,
        # no se escape a task_done narrando un «✅ registrada» confuso sin llamar la tool (visto en
        # el seguimiento multivuelta «Emitida.»). ask_user queda por si de verdad falta la base.
        return {"registrar_factura", "ask_user"}
    return _TOOLS_POR_INTENCION.get(intencion, set()) | _SIEMPRE


# Todas las tools de DOMINIO (cálculo/registro): durante una intención, se excluyen las de OTRAS
# intenciones para que el agente no divague (p.ej. en un cobro NO registre una factura fantasma).
_DOMINIO_TODAS = {
    "plan_cobro",
    "reclamar_cobro_cliente",
    "calcular_303",
    "calcular_303_registradas",
    "registrar_factura",
    "resumen_facturacion",
    "cobros_pendientes",
    "resumen_financiero",
}


def tools_excluir(intencion: str | None) -> set[str]:
    """Tools de dominio de OTRAS intenciones, a quitar del run completo (evita divagar de tool)."""
    if not intencion:
        return set()
    return _DOMINIO_TODAS - _TOOLS_POR_INTENCION.get(intencion, set())


# Pregunta sobre la agenda ("¿qué reuniones tengo?", "¿tengo algo el jueves?") = LECTURA. El 14B a
# veces la confunde con CREAR un evento → excluimos calendar_create de forma determinista.
_LECTURA_AGENDA = re.compile(
    r"\b(qu[eé]|cu[aá]l\w*|tengo|hay|tienes)\b[^\n]{0,45}"
    r"\b(reuni\w+|cita\w*|agenda|evento\w*|calendario)\b"
    # «¿tengo algo el viernes?», «¿hay algún hueco?» = LECTURA aunque no nombre la agenda: el 14B la
    # tomaba por crear un evento «consulta de disponibilidad». Excluir calendar_create lo impide.
    r"|\b(tengo|hay|tienes)\b[^\n]{0,20}\b(algo|alg[uú]n\w*|planes?|hueco|libre|ocupad\w*|disponib\w*)\b"
)


def es_lectura_agenda(task: str) -> bool:
    """True si es una PREGUNTA sobre la agenda (lectura): no debe crear eventos."""
    return bool(_LECTURA_AGENDA.search((task or "").lower()))
