"""
guardas_fiscales.py — Skill D Fiscal: guardas de DOMINIO (España) pre-intent.

Movido aquí desde el núcleo blanco `agent/loop.py` (D-2): el IRPF, el IBAN español y los modelos AEAT
son DOMINIO, no van en el núcleo. Cada guarda detecta una petición que Loombit hoy NO modela y devuelve
una abstención HONESTA (mejor «no lo hago» que fabricarlo mal). Se registran en `registro_guardas`; el
bucle las consulta antes del ReAct sin saber de fiscalidad.
"""

from __future__ import annotations

import re

from ..agent.guardas import registro_guardas
from ..agent.parsers import validar_iban

# ── Retención de IRPF: registrar_factura NO la modela. Registrar una factura con retención SIN la
# retención falsearía el 303 y el 111/130 → se rehúsa honesto, hasta construir el 130 (decisión #8/#9).
# «reten\w+» cubre retención/retenido/retenida/retener; «reti[eé]n\w+» la conjugación «retiene/retienen»;
# «irpf» cubre «factura con IRPF del 15%» (la tasa de IRPF en una factura ES la retención, aunque no se
# diga «retención»). El negativo («sin IRPF», «exento de IRPF») lo capta _SIN_RETENCION. ──────────────
_RETENCION_IRPF = re.compile(r"\breten\w+\b|\breti[eé]n\w+\b|\birpf\b", re.IGNORECASE)
_SIN_RETENCION = re.compile(
    r"\bsin\b[^.\n]{0,18}(?:reten|irpf)"  # «sin (…) retención / sin IRPF»
    r"|\bno\s+(?:lleva|tiene|hay|aplica)\b[^.\n]{0,18}(?:reten|irpf)"  # «no lleva (…) retención»
    r"|\bno\s+(?:me\s+|le\s+|nos\s+|te\s+)?reti?en\w+"  # «no me retienen / no retengas / no retener»
    r"|\bexent\w+[^.\n]{0,14}(?:reten|irpf)"  # «exenta de retención / exento de IRPF»
    r"|\bning\w+[^.\n]{0,14}(?:reten|irpf)"  # «ninguna retención»
    r"|\b0\s*%[^.\n]{0,14}(?:reten|irpf)",  # «0% de retención»
    re.IGNORECASE,
)
_MSG_RETENCION_NO_MODELADA = (
    "⚠️ No he registrado la factura: lleva RETENCIÓN de IRPF y todavía no modelo la retención. "
    "Registrarla sin la retención falsearía tu 303 y tu 111/130, así que prefiero NO hacerlo a "
    "hacerlo mal. Apúntala con tu gestoría por ahora; cuando construyamos el modelo 130 la registro "
    "con su retención. (No se ha guardado nada.)"
)


def lleva_retencion(task: str, args: dict | None = None) -> bool:
    """True si la factura a registrar lleva retención de IRPF (por el arg explícito o por el texto).
    «sin retención» NO cuenta. Conservador: ante retención, mejor rehusar que falsear."""
    r = (args or {}).get("retencion", (args or {}).get("retención"))
    if r not in (None, "", 0, "0", 0.0):
        try:
            return float(r) != 0
        except (ValueError, TypeError):
            return True
    t = task or ""
    if _SIN_RETENCION.search(t):
        return False
    return bool(_RETENCION_IRPF.search(t))


_HACER_FACTURA = re.compile(r"\b(minuta\w*|factura\w*)\b", re.IGNORECASE)
_VERBO_HACER = re.compile(
    r"\b(haz\w*|hacer|hag\w+|prepar\w+|reg[ií]str\w+|em[ií]t\w+|fact[uú]r\w+|ap[uú]nt\w+"
    r"|gener\w+|cre\w+)\b",
    re.IGNORECASE,
)


# Marcadores de PREGUNTA (no es un encargo de crear) → no abstener. «¿qué IRPF lleva la minuta?».
_PREGUNTA = re.compile(
    r"^\s*¿|\bqu[eé]\b|\bcu[aá]l\w*\b|\bcu[aá]nto\w*\b|\bc[oó]mo\b", re.IGNORECASE
)
_TIENE_IMPORTE_RET = re.compile(r"[€$]|\d")


def es_registro_con_retencion(task: str) -> bool:
    """True si la petición pide REGISTRAR/PREPARAR una factura o minuta CON retención de IRPF (no
    modelada). Excluye «sin retención» y las PREGUNTAS (no piden crear nada). Corta ANTES del ReAct,
    cubriendo TODOS los caminos por los que el 14B fabricaría (registrar_factura, mis-ruteo a 303…).
    """
    t = task or ""
    if _SIN_RETENCION.search(t) or not _RETENCION_IRPF.search(t) or not _HACER_FACTURA.search(t):
        return False
    if _VERBO_HACER.search(t):
        return True
    # Sin verbo explícito, pero «minuta/factura de 1000 con IRPF» es un encargo elíptico → abstiene si
    # hay importe y NO es una pregunta («¿qué IRPF lleva una minuta?» no crea nada).
    return bool(_TIENE_IMPORTE_RET.search(t)) and not _PREGUNTA.search(t)


# ── IBAN inválido: no fabricamos un «✅ guardado» de un IBAN que no cuadra (longitud/checksum mod-97).
_IBAN_TOKEN = re.compile(r"\bES\s?\d[\d\s]{6,30}", re.IGNORECASE)
_GUARDA_IBAN = re.compile(
    r"\b(guarda\w*|gu[aá]rda\w*|ap[uú]nta\w*|reg[ií]stra\w*|anota\w*|almacena\w*)\b",
    re.IGNORECASE,
)
_IBAN_O_CUENTA = re.compile(
    r"\biban\b|\bcuenta\b", re.IGNORECASE
)  # «iban» o «cuenta» (nº de cuenta)
_MSG_IBAN_INVALIDO = (
    "⚠️ No he guardado ese IBAN: no es válido (no cuadra por longitud o dígito de control). Revísalo "
    "y pásamelo completo (un IBAN español tiene 24 caracteres) y lo guardo."
)


def iban_invalido_a_guardar(task: str) -> bool:
    """True si la petición pide GUARDAR un IBAN/cuenta y el IBAN español del texto es INVÁLIDO
    (longitud/checksum). Acepta «cuenta» además de «iban» (el usuario no siempre dice «IBAN»)."""
    t = task or ""
    if not _IBAN_O_CUENTA.search(t) or not _GUARDA_IBAN.search(t):
        return False
    m = _IBAN_TOKEN.search(t)
    return bool(m) and not validar_iban(m.group(0))


# ── Modelos AEAT no modelados (hoy solo el 303 de IVA): abstención HONESTA. El 303 NO entra aquí. ──
# Se pide «el modelo NNN» o por su NOMBRE («pago fraccionado»=130, «operaciones intracomunitarias»=349…)
# sin citar el número. El 303 nunca. NO casamos «el 130» a secas: «el 130 €» / «el 190 que me debe» son
# IMPORTES, no modelos (falsos positivos que destapó la auditoría) → exige «modelo» o el nombre.
_MODELO_NO_MODELADO = re.compile(
    r"\bmodelo\s+(100|111|115|123|130|180|184|190|193|200|347|349|390|714|720)\b",
    re.IGNORECASE,
)
_MODELO_POR_NOMBRE = (
    (re.compile(r"pago\s+fraccionad\w+", re.IGNORECASE), "130"),
    (re.compile(r"operaci\w+\s+intracomunitar\w+", re.IGNORECASE), "349"),
    (
        re.compile(r"retenci\w+\s+(a\s+)?(profesional\w+|trabajador\w+|cuenta)", re.IGNORECASE),
        "111",
    ),
    # Modelos por su NOMBRE coloquial (sin citar el número). Acotado a «impuesto … X»/«declaración de
    # la renta» para no confundir «la renta del local» (alquiler) ni «la sociedad» (una empresa).
    (
        re.compile(
            r"declaraci\w+\s+de\s+la\s+renta|\brenta\s+anual\b|impuesto\w*\s+de\s+la\s+renta",
            re.IGNORECASE,
        ),
        "100",
    ),
    (re.compile(r"impuesto\w*\s+(de|sobre)\s+(las?\s+)?sociedades", re.IGNORECASE), "200"),
    (re.compile(r"impuesto\w*\s+(de|sobre)\s+(el\s+)?patrimonio", re.IGNORECASE), "714"),
    (
        re.compile(
            r"resumen\s+anual\s+d\w+\s+iva|declaraci\w+\s+anual\s+d\w+\s+iva", re.IGNORECASE
        ),
        "390",
    ),
    (re.compile(r"operaci\w+\s+con\s+tercero", re.IGNORECASE), "347"),
    # «el 130 del IRPF» (130 = pago fraccionado IRPF) sin decir «modelo» ni «pago fraccionado».
    (re.compile(r"\b130\b[^.\n]{0,18}\birpf\b|\birpf\b[^.\n]{0,12}\b130\b", re.IGNORECASE), "130"),
)
_MSG_MODELO_NO_MODELADO = (
    "Todavía no calculo el modelo {m} — hoy Loombit prepara el 303 (IVA) desde tus facturas. Ese "
    "modelo lo lleva tu gestor; cuando lo construyamos, te lo preparo yo. Mientras, te ayudo con el "
    "303, registrar facturas o tus cobros."
)


def modelo_no_modelado(task: str) -> str | None:
    """Devuelve el número del modelo AEAT pedido si NO está modelado (111/349/130…), o None. Reconoce
    el número («modelo 130», «el 130») y el NOMBRE del modelo («pago fraccionado»)."""
    m = _MODELO_NO_MODELADO.search(task or "")
    if m:
        return m.group(1)
    for rx, num in _MODELO_POR_NOMBRE:
        if rx.search(task or ""):
            return num
    return None


# ── Registro de las guardas (el bucle las consulta vía registro_guardas) ─────────────────────────
@registro_guardas.register
def _guarda_retencion(task: str) -> str | None:
    return _MSG_RETENCION_NO_MODELADA if es_registro_con_retencion(task) else None


@registro_guardas.register
def _guarda_iban(task: str) -> str | None:
    return _MSG_IBAN_INVALIDO if iban_invalido_a_guardar(task) else None


@registro_guardas.register
def _guarda_modelo_aeat(task: str) -> str | None:
    m = modelo_no_modelado(task)
    return _MSG_MODELO_NO_MODELADO.format(m=m) if m else None


# ── Conciliación bancaria: SIEMPRE necesita el extracto en Norma 43. En chat (sin fichero) la
# respuesta determinista es pedir el N43 — así «concíliame los cobros con el banco» NUNCA se confunde
# con «cuánto me deben» (el free-form del 14B a veces caía en cobros_pendientes). ──────────────────
_CONCILIACION = re.compile(
    # verbo de conciliación (conciliar/reconciliar/cuadrar/puntear/cruzar) + objeto FINANCIERO cerca
    # → así «reconcilia con tu pareja» (sin objeto financiero) NO dispara.
    r"\b(?:(?:re)?conc[ií]li\w+|cu[aá]dr\w+|punt[eé]\w+|cruz\w+)[^.\n]{0,30}"
    r"\b(banc\w*|extracto\w*|n43|norma\s*43)",  # señal BANCARIA (no «cuentas del 303», que es contable)
    re.IGNORECASE,
)
_MSG_CONCILIACION = (
    "Para conciliar tus cobros con el banco necesito el EXTRACTO bancario en formato Norma 43 (N43) "
    "— lo exportas desde tu banca online. Pásamelo y cruzo cada apunte con tus facturas; lo que cuadre "
    "lo marco como cobrado."
)


@registro_guardas.register
def _guarda_conciliacion(task: str) -> str | None:
    return _MSG_CONCILIACION if _CONCILIACION.search(task or "") else None


# ── Predicción del FUTURO financiero: Loombit NO adivina lo que aún no ha pasado (sería inventar). Sin
# esta guarda, el 14B en free-form llamaba a resumen_comparativo (datos del pasado) para una predicción.
# Exige señal financiera + de futuro → no se confunde con «¿facturé el mes pasado?» (pasado). ──────────
_PREDICCION_FINANCIERA = re.compile(
    r"\b(facturar[eé]|ganar[eé]|ingresar[eé]|vender[eé]|cobrar[eé])\b"
    r"|\ba\s+este\s+ritmo\b[^.\n]{0,40}\b(factur\w+|ingres\w+|ganar\w+|vend\w+|benefici\w+|cobr\w+)"
    r"|\b(cu[aá]nto|qu[eé])\b[^.\n]{0,30}\b(voy|vas|vamos)\s+a\s+(factur\w+|ingres\w+|ganar|vend\w+|cobr\w+)"
    r"|\b(predic\w+|proyec\w+|estima\w+|previsi\w+|forecast)\b[^.\n]{0,30}"
    r"\b(factur\w+|ingres\w+|ventas|benefici\w+|cobr\w+)"
    r"|\b(llegar[eé]|alcanzar[eé]|cumplir[eé]|lograr[eé])\b[^.\n]{0,40}"
    r"(\d|€|euros?|facturaci\w+|ingres\w+|objetivo|meta)"  # «¿llegaré a los 50.000 €?»
    r"|\b(voy|vas|vamos|va)\s+a\s+(ganar\w*|ingresar)\b"  # «¿voy a ganar dinero?» (resultado, no acción)
    r"|\b(espero|prev[eé]\w*|aspiro)\s+(a\s+)?(factur|ingres|gan|vend|cobr)ar",  # «espero facturar 50.000»
    re.IGNORECASE,
)
_MSG_PREDICCION = (
    "No puedo predecir el futuro: solo trabajo con lo que YA ha pasado (tus facturas registradas). "
    "Te digo lo que llevas facturado y te lo comparo con periodos anteriores si quieres, pero adivinar "
    "lo que facturarás sería inventar — y prefiero no darte un número que no es real."
)


def es_prediccion_financiera(task: str) -> bool:
    """True si pide PREDECIR/PROYECTAR finanzas futuras (no computable; se abstiene honesto)."""
    return bool(_PREDICCION_FINANCIERA.search(task or ""))


@registro_guardas.register
def _guarda_prediccion(task: str) -> str | None:
    return _MSG_PREDICCION if es_prediccion_financiera(task) else None
