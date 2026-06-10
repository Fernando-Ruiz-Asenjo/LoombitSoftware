"""
ALG-1.3 / ALG-1.4 · parsers y validación DETERMINISTAS (frontera de determinismo).

Las cifras, fechas e identificadores NO los saca el LLM: los extrae y valida CÓDIGO. Así un
importe o un IBAN no dependen de que el 14B acierte. Puro y 100% testeable. Blanco/reutilizable.
Ver docs/ALGORITMO_CEREBRO.md (ALG-1.3/1.4) y docs/REPARACION_CANONICA.md.
"""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, timedelta

# Tipos de IVA válidos en España (fracción): exento, superreducido, temporal, reducido, general.
TIPOS_IVA_VALIDOS = frozenset({0.0, 0.04, 0.05, 0.10, 0.21})

_MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
_DIAS = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}

# Números en palabras (para 'hace tres semanas' = 21 días). El 14B yerra estos cálculos; el código no.
_PALABRA_NUM = {
    "un": 1,
    "una": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
}


def parsear_importe(texto: object) -> float | None:
    """Extrae un importe respetando separadores es ('1.500,75') e en ('1,500.75'). None si no hay."""
    if texto is None:
        return None
    m = re.search(r"\d[\d.,]*", str(texto))
    if not m:
        return None
    num = m.group(0).rstrip(".,")
    if "." in num and "," in num:
        # el separador MÁS a la derecha es el decimal; el otro son miles
        if num.rfind(",") > num.rfind("."):
            num = num.replace(".", "").replace(",", ".")
        else:
            num = num.replace(",", "")
    elif "," in num:
        ent, _, dec = num.rpartition(",")
        num = f"{ent.replace('.', '')}.{dec}" if len(dec) in (1, 2) else num.replace(",", "")
    elif "." in num:
        ent, _, dec = num.rpartition(".")
        if len(dec) not in (1, 2):  # '.' como separador de miles
            num = num.replace(".", "")
    try:
        return float(num)
    except ValueError:
        return None


def parsear_tipo_iva(texto: object) -> float | None:
    """'21%'/'21'/'0.21'/'0,21' → 0.21 (fracción). No valida el tipo (eso lo hace tipo_iva_valido)."""
    v = parsear_importe(texto)
    if v is None:
        return None
    return round(v / 100.0 if v > 1 else v, 4)


def tipo_iva_valido(tipo: float | None) -> bool:
    return tipo is not None and round(float(tipo), 4) in TIPOS_IVA_VALIDOS


def parsear_fecha(texto: object, hoy: date | None = None) -> date | None:
    """Fecha desde ISO, dd/mm/aaaa, '1 de mayo de 2026' o relativa ('mañana', 'el jueves'). None si no."""
    hoy = hoy or date.today()
    s = str(texto or "").strip().lower()
    if not s:
        return None
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", s)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})\b", s)
    if m:
        d, mo, y = int(m[1]), int(m[2]), int(m[3])
        if y < 100:
            y += 2000
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})\s+de\s+([a-záéíóú]+)(?:\s+de\s+(\d{4}))?\b", s)
    if m and m[2] in _MESES:
        y = int(m[3]) if m[3] else hoy.year
        try:
            return date(y, _MESES[m[2]], int(m[1]))
        except ValueError:
            return None
    # 'hace N días/semanas' (vencimientos relativos al pasado): exacto, el 14B se equivoca.
    m = re.search(
        r"\bhace\s+(\d+|un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+"
        r"(d[ií]as?|semanas?)\b",
        s,
    )
    if m:
        n = _PALABRA_NUM.get(m[1])
        if n is None:
            try:
                n = int(m[1])
            except ValueError:
                n = None
        if n is not None:
            return hoy - timedelta(days=7 * n if m[2].startswith("sem") else n)
    # 'hace N meses' → aritmética de calendario (no 30 días, que deriva), con clamp del día.
    m = re.search(
        r"\bhace\s+(\d+|un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+mes(?:es)?\b", s
    )
    if m:
        n = _PALABRA_NUM.get(m[1])
        if n is None:
            try:
                n = int(m[1])
            except ValueError:
                n = None
        if n is not None:
            mes, anio = hoy.month - n, hoy.year
            while mes <= 0:
                mes += 12
                anio -= 1
            return date(anio, mes, min(hoy.day, monthrange(anio, mes)[1]))
    if "pasado manana" in s or "pasado mañana" in s:
        return hoy + timedelta(days=2)
    if "manana" in s or "mañana" in s:
        return hoy + timedelta(days=1)
    if "hoy" in s:
        return hoy
    for nombre, wd in _DIAS.items():
        if nombre in s:
            return hoy + timedelta(days=(wd - hoy.weekday()) % 7)
    return None


def validar_iban(iban: object) -> bool:
    """Valida un IBAN por longitud + checksum mod-97 (ISO 13616). Determinista."""
    s = re.sub(r"\s", "", str(iban or "")).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]+", s) or not (15 <= len(s) <= 34):
        return False
    reordenado = s[4:] + s[:4]
    numerico = "".join(str(int(c, 36)) for c in reordenado)  # letras→números (A=10…Z=35)
    return int(numerico) % 97 == 1


_LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"


def validar_nif(nif: object) -> bool:
    """Valida NIF/DNI y NIE (letra de control). CIF no incluido. Determinista."""
    s = re.sub(r"[\s\-]", "", str(nif or "")).upper()
    m = re.fullmatch(r"([XYZ]?)(\d{7,8})([A-Z])", s)
    if not m:
        return False
    pre, num, letra = m.groups()
    if pre:  # NIE: X→0, Y→1, Z→2 delante
        num = str("XYZ".index(pre)) + num
    if len(num) > 8:
        return False
    return _LETRAS_DNI[int(num) % 23] == letra


# ── D-3: extractor DETERMINISTA de importes (la cifra NO la pone el LLM; brújula) ─────────────────
_IMPORTE_ES = re.compile(r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+(?:,\d+)?")


def parsear_importe_es(texto: object) -> float | None:
    """Extrae el ÚNICO importe principal en € de un texto es-ES (1.234,56 / -200 / 2500), EXCLUYENDO
    porcentajes, días, fechas (dd/mm/aaaa, «5 de junio») y años. Devuelve None si hay 0 o >1 importes
    DISTINTOS (ambiguo → no se corrige: que lo decida el modelo). Determinista, conservador."""
    t = str(texto or "")
    # tachar lo que NO es un importe (su número no debe contarse)
    t = re.sub(
        r"-?\d[\d.,]*\s*(%|por\s*ciento)", " ", t, flags=re.IGNORECASE
    )  # 21% / 21 por ciento
    t = re.sub(r"\b\d+\s*d[ií]as?\b", " ", t, flags=re.IGNORECASE)  # 40 días
    t = re.sub(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", " ", t)  # 01/04/2026
    # «5 de junio de 2026» (incluido el año) → así un año NO se confunde con un importe (2000 €). NO
    # se excluye el año suelto: «2000» es un importe, no un año, salvo en una fecha explícita.
    t = re.sub(r"\b\d{1,2}\s+de\s+[a-záéíóúñ]+(?:\s+de\s+\d{4})?", " ", t, flags=re.IGNORECASE)
    vals: list[float] = []
    for n in _IMPORTE_ES.findall(t):
        try:
            vals.append(float(n.replace(".", "").replace(",", ".")))
        except ValueError:
            pass
    distintos = {round(v, 2) for v in vals}
    return distintos.pop() if len(distintos) == 1 else None
