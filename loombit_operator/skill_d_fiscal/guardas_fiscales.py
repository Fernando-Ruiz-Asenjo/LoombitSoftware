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
# «reten\w+» cubre retención/retenido/retenida/retener; «reti[eé]n\w+» la conjugación «retiene/retienen»
# («el IRPF que me retienen» — antes se escapaba porque «retienen» no empieza por «reten»). ──────────
_RETENCION_IRPF = re.compile(r"\breten\w+\b|\breti[eé]n\w+\b", re.IGNORECASE)
_SIN_RETENCION = re.compile(
    r"\bsin\b[^.\n]{0,18}reten"  # «sin (…) retención»
    r"|\bno\s+(?:lleva|tiene|hay|aplica)\b[^.\n]{0,18}reten"  # «no lleva (…) retención»
    r"|\bno\s+(?:me\s+|le\s+|nos\s+|te\s+)?reti?en\w+",  # «no me retienen / no retengas / no retener»
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


def es_registro_con_retencion(task: str) -> bool:
    """True si la petición pide REGISTRAR/PREPARAR una factura o minuta CON retención de IRPF (no
    modelada). Excluye «sin retención» y las preguntas que no piden crear nada. Corta ANTES del ReAct,
    cubriendo TODOS los caminos por los que el 14B fabricaría (registrar_factura, mis-ruteo a 303…).
    """
    t = task or ""
    if _SIN_RETENCION.search(t) or not _RETENCION_IRPF.search(t):
        return False
    return bool(_HACER_FACTURA.search(t) and _VERBO_HACER.search(t))


# ── IBAN inválido: no fabricamos un «✅ guardado» de un IBAN que no cuadra (longitud/checksum mod-97).
_IBAN_TOKEN = re.compile(r"\bES\s?\d[\d\s]{6,30}", re.IGNORECASE)
_GUARDA_IBAN = re.compile(
    r"\b(guarda\w*|gu[aá]rda\w*|ap[uú]nta\w*|registra\w*|anota\w*|almacena\w*)\b",
    re.IGNORECASE,
)
_MSG_IBAN_INVALIDO = (
    "⚠️ No he guardado ese IBAN: no es válido (no cuadra por longitud o dígito de control). Revísalo "
    "y pásamelo completo (un IBAN español tiene 24 caracteres) y lo guardo."
)


def iban_invalido_a_guardar(task: str) -> bool:
    """True si la petición pide GUARDAR un IBAN y el IBAN del texto es INVÁLIDO (longitud/checksum)."""
    t = task or ""
    if "iban" not in t.lower() or not _GUARDA_IBAN.search(t):
        return False
    m = _IBAN_TOKEN.search(t)
    return bool(m) and not validar_iban(m.group(0))


# ── Modelos AEAT no modelados (hoy solo el 303 de IVA): abstención HONESTA. El 303 NO entra aquí. ──
# Se pide «el modelo NNN» o por su NOMBRE («pago fraccionado»=130, «operaciones intracomunitarias»=349…)
# sin citar el número. El 303 nunca. NO casamos «el 130» a secas: «el 130 €» / «el 190 que me debe» son
# IMPORTES, no modelos (falsos positivos que destapó la auditoría) → exige «modelo» o el nombre.
_MODELO_NO_MODELADO = re.compile(
    r"\bmodelo\s+(111|115|123|130|180|184|190|193|347|349|390)\b", re.IGNORECASE
)
_MODELO_POR_NOMBRE = (
    (re.compile(r"pago\s+fraccionad\w+", re.IGNORECASE), "130"),
    (re.compile(r"operaci\w+\s+intracomunitar\w+", re.IGNORECASE), "349"),
    (
        re.compile(r"retenci\w+\s+(a\s+)?(profesional\w+|trabajador\w+|cuenta)", re.IGNORECASE),
        "111",
    ),
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
_CONCILIACION = re.compile(r"\bconc[ií]li\w+", re.IGNORECASE)
_MSG_CONCILIACION = (
    "Para conciliar tus cobros con el banco necesito el EXTRACTO bancario en formato Norma 43 (N43) "
    "— lo exportas desde tu banca online. Pásamelo y cruzo cada apunte con tus facturas; lo que cuadre "
    "lo marco como cobrado."
)


@registro_guardas.register
def _guarda_conciliacion(task: str) -> str | None:
    return _MSG_CONCILIACION if _CONCILIACION.search(task or "") else None
