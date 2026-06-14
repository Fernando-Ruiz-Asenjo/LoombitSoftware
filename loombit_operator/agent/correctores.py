"""
correctores.py — correctores DETERMINISTAS de los argumentos del agente («cifras/fechas por código»).

Extraído de loop.py (en deuda de tamaño, >400; ratchet de la Brújula) para poder cablear D-96 sin
engordarlo. Aquí viven los algoritmos que ARREGLAN lo que el 14B garbea al rellenar args: líneas del
303 fabricadas, fechas relativas, periodo/trimestre, unidad de la comparativa, alias de factura e
importe fiel. Ley Fundacional: las cifras y fechas las decide CÓDIGO, no el LLM. Sin cambiar
comportamiento respecto a lo que vivía en loop.py.
"""

from __future__ import annotations

import re
from datetime import date

from .parsers import parsear_fecha, parsear_importe_es


def _numeros_del_texto(texto: str) -> set[str]:
    """Números del mensaje, normalizados (sin separadores de miles) para comparar bases."""
    out: set[str] = set()
    for m in re.findall(r"\d[\d.,]*", texto or ""):
        out.add(m.rstrip(".,").replace(".", "").replace(",", ""))
    return out


# Si el usuario escribió importes EN PALABRAS (mil, quinientos…), no podemos comparar bases por
# dígitos sin convertirlos → el filtro se desactiva para no tirar líneas legítimas (falso positivo).
_NUM_EN_PALABRAS = re.compile(
    r"\b(mil|cien|ciento|doscient\w+|trescient\w+|cuatrocient\w+|quinient\w+|"
    r"seiscient\w+|setecient\w+|ochocient\w+|novecient\w+)\b"
)


def _filtrar_lineas_303(args: dict, task: str) -> tuple[dict, int]:
    """ALG anti-fabricación del 303: quita las líneas cuya BASE no aparece en el mensaje del usuario
    (el 14B inventa líneas plausibles, p.ej. 'servicios 5000€'). Determinista. Devuelve (args, n_quitadas).
    No filtra si el usuario dio las cifras en palabras (evita falsos positivos).
    """
    t = (task or "").lower()
    nums = _numeros_del_texto(t)
    if not nums or _NUM_EN_PALABRAS.search(t):
        return args, 0
    quitadas = 0
    for campo in ("iva_repercutido", "iva_soportado"):
        lineas = args.get(campo)
        if not isinstance(lineas, list):
            continue
        nuevas = []
        for ln in lineas:
            try:
                base = str(int(float(ln.get("base"))))
            except (TypeError, ValueError):
                nuevas.append(ln)
                continue
            if base in nums:
                nuevas.append(ln)
            else:
                quitadas += 1
        args[campo] = nuevas
    return args, quitadas


_REL_FECHA = re.compile(
    r"\b(mañana|manana|pasado\s+mañana|pasado\s+manana|hoy|lunes|martes|mi[eé]rcoles|jueves|"
    r"viernes|s[aá]bado|domingo|que\s+viene|pr[oó]xim\w+)\b"
    r"|hace\s+\w+\s+(?:d[ií]as?|semanas?|mes(?:es)?)"
)


def _corregir_fecha_calendario(args: dict, task: str, hoy: date | None = None) -> bool:
    """ALG fecha-fiel: el 14B se equivoca con fechas relativas ('próximo lunes'→sábado). Si el task
    trae una fecha relativa, la recalcula con parsear_fecha (determinista) y corrige el `start_iso`
    (mantiene la HORA del modelo). Devuelve True si corrigió. Solo actúa si hay marcador relativo.
    """
    t = (task or "").lower()
    if not _REL_FECHA.search(t):
        return False
    fecha = parsear_fecha(t, hoy)
    if fecha is None:
        return False
    iso = str(args.get("start_iso") or "")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})([T ].*)?$", iso)
    if not m:
        return False
    fecha_14b = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    nueva = fecha.isoformat()
    if fecha_14b == nueva:
        return False
    args["start_iso"] = nueva + (m.group(4) or "T09:00:00Z")
    return True


def _corregir_fecha_cobro(args: dict, task: str, hoy: date | None = None) -> bool:
    """ALG fecha-fiel (cobro): corrige `fecha_vencimiento` si el task trae una fecha relativa
    ('venció hace tres semanas'). El 14B la calcula mal (21→24 días) y eso cambia etapa e interés.
    """
    t = (task or "").lower()
    if not _REL_FECHA.search(t):
        return False
    fecha = parsear_fecha(t, hoy)
    if fecha is None:
        return False
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(args.get("fecha_vencimiento") or ""))
    actual = m.group(1) if m else ""
    nueva = fecha.isoformat()
    if actual == nueva:
        return False
    args["fecha_vencimiento"] = nueva
    return True


_TRIMESTRE_USUARIO = re.compile(
    r"\b[1-4]\s*[ºo]?\s*t\b|\bt[1-4]\b|(primer|segundo|tercer|cuarto)\s+trimestre", re.I
)


def _trimestre_actual(hoy: date | None = None) -> str:
    h = hoy or date.today()
    return f"{(h.month - 1) // 3 + 1}T {h.year}"


def _corregir_periodo_303(args: dict, task: str, hoy: date | None = None) -> bool:
    """Si el usuario NO especificó trimestre, usa el ACTUAL (desde la fecha), no la adivinanza del
    14B ('Primer trimestre' en junio). Determinista. Devuelve True si cambió el periodo."""
    if _TRIMESTRE_USUARIO.search(task or ""):
        return False  # el usuario indicó el trimestre → respétalo
    actual = _trimestre_actual(hoy)
    if str(args.get("periodo") or "").strip() == actual:
        return False
    args["periodo"] = actual
    return True


_TRIMESTRE_RELATIVO = re.compile(
    r"\b(este|el|nuestro)\s+trimestre\b|\btrimestre\s+actual\b|\beste\s+trim\b", re.IGNORECASE
)


def _corregir_trimestre_relativo(args: dict, task: str, hoy: date | None = None) -> bool:
    """Corrige «este/el trimestre» al trimestre ACTUAL (el 14B a veces pasa un trimestre específico
    equivocado, p.ej. 1T en junio). Solo toca referencias RELATIVAS de trimestre (no meses ni
    trimestres explícitos), así no rompe «junio» ni «2T 2026». Devuelve True si cambió el periodo.
    """
    if not _TRIMESTRE_RELATIVO.search(task or ""):
        return False
    actual = _trimestre_actual(hoy)
    if str(args.get("periodo") or "").strip() == actual:
        return False
    args["periodo"] = actual
    return True


# D-4: la UNIDAD de la comparativa (mes/trimestre/año) la fija el CÓDIGO desde el texto, no el 14B.
_UNIDAD_TRIMESTRE = re.compile(r"\btrimestr", re.IGNORECASE)
_UNIDAD_ANIO = re.compile(r"\ba[ñn]o\b|\banual\b|\bejercicio\b", re.IGNORECASE)


def _corregir_unidad_comparativa(args: dict, task: str) -> bool:
    """Pone args['unidad'] (mes/trimestre/anio) según el texto. Determinista. Devuelve True si cambió."""
    if _UNIDAD_TRIMESTRE.search(task or ""):
        u = "trimestre"
    elif _UNIDAD_ANIO.search(task or ""):
        u = "anio"
    else:
        u = "mes"
    if str(args.get("unidad") or "") == u:
        return False
    args["unidad"] = u
    return True


# D-3: importe-fiel. El 14B garbea la cifra al rellenar el arg (negativos -200→-827; total-vs-base).
# Si el texto trae UN importe claro, lo recalcula el código. «IVA incluido» → el importe es el TOTAL,
# luego base = importe/(1+tipo). Conservador: si hay 0 o >1 importes (parsear_importe_es=None), no toca.
_IVA_INCLUIDO = re.compile(r"iva\s+inclu|impuestos?\s+inclu|con\s+(el\s+)?iva\b", re.IGNORECASE)

# El 14B a veces nombra los args como base_imponible/tipo_iva; registrar_factura espera base/tipo.
# Mapeo de alias INEQUÍVOCOS (no «importe», que sería ambiguo total-vs-base).
_ALIAS_FACTURA = {
    "base_imponible": "base",
    "baseimponible": "base",
    "tipo_iva": "tipo",
    "tipoiva": "tipo",
}


def _normalizar_alias_factura(args: dict) -> None:
    """Renombra los alias inequívocos del 14B (base_imponible→base, tipo_iva→tipo) y descarta el alias,
    para que la llamada no rompa y el corrector de importe vea `base`."""
    for alias, real in _ALIAS_FACTURA.items():
        if alias in args:
            if real not in args or args.get(real) in (None, "", 0, "0"):
                args[real] = args[alias]
            del args[alias]


def _corregir_importe(tool_name: str, args: dict, task: str) -> bool:
    """Corrige plan_cobro.total / registrar_factura.base con el extractor determinista de importes.
    Para registrar_factura recalcula además el IVA desde la base corregida (el 14B garbea el split).
    Devuelve True si cambió el arg."""
    imp = parsear_importe_es(task)
    if imp is None:
        return False
    if tool_name == "plan_cobro":
        try:
            actual = float(args.get("total", 0) or 0)
        except (ValueError, TypeError):
            actual = 0.0
        if abs(actual - imp) <= 0.01:
            return False
        args["total"] = imp
        return True
    # registrar_factura → la BASE. «IVA incluido» → el importe es el TOTAL → base = imp/(1+tipo);
    # siempre se fuerza (el 14B no sabe partir base/IVA) y se recalcula el IVA desde la base.
    iva_incluido = bool(_IVA_INCLUIDO.search(task or ""))
    try:
        tf = float(args.get("tipo")) if args.get("tipo") is not None else 0.21
    except (ValueError, TypeError):
        tf = 0.21
    if tf > 1:
        tf /= 100.0
    objetivo = round(imp / (1.0 + tf), 2) if (iva_incluido and tf >= 0) else imp
    try:
        actual = float(args.get("base", 0) or 0)
    except (ValueError, TypeError):
        actual = 0.0
    if not iva_incluido and abs(actual - objetivo) <= 0.01:
        return False
    args["base"] = objetivo
    args.pop("iva", None)  # recomputar el IVA desde base×tipo (no usar el del 14B, que lo garbea)
    return True
