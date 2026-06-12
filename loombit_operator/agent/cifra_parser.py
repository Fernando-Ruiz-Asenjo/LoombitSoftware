"""
cifra_parser.py — §14B-1: el GUARDIA POST-LLM de las cifras consecuentes (€).

Ley Fundacional: *las cifras las calcula CÓDIGO determinista; el LLM narra*. Pero un 14B local, narrando,
suelta importes que NO salieron de ninguna tool ("te debe ~2.400 €" cuando la tool dijo 2.350,00 €, o sin
tool ninguna). Este módulo es el peaje POST-LLM: coge la NARRATIVA del modelo y el LEDGER de cifras que
produjeron tools ejecutadas EN EL MISMO RUN, y **bloquea todo € narrado que no esté respaldado al céntimo**.
Bloqueado → la política es re-prompt (que el modelo solo cite cifras de tool) o ABSTENCIÓN honesta.

Por qué solo € (y no %, días, años): el daño consecuente vive en el dinero (lo que el usuario paga/cobra).
Un "21% de IVA" o "a 30 días" son constantes de oficio, no cifras de tool. Restringir a € da un guardia de
ALTA precisión (no marca el IVA) sin perder lo que importa. Determinista, puro, sin red, sin LLM. Blanco.

NO juzga si el importe es "correcto" contra el mundo: juzga si **procede de una tool de este run**. La
verdad del importe la da la tool (código); aquí solo se impide que el LLM invente o redondee a ojo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Tolerancia de respaldo: una cifra de tool es exacta al céntimo. Un € narrado se considera respaldado solo
# si coincide con una cifra del ledger dentro de esto. NO se afloja (sería la puerta de atrás del guardia).
TOL_CENTIMO = 0.005

# Marcas de APROXIMACIÓN: una tool da el dato exacto; si el modelo HEDGEA ("~2.400 €", "unos 2.400 €") está
# narrando a ojo aunque el número ronde un valor del ledger → se trata como NO respaldado (es justo el caso
# que la brújula nombra: «bloquea cifras narradas ("~2.400 €")»).
_MARCAS_APROX = (
    "~",
    "≈",
    "aprox",
    "aproximadamente",
    "unos",
    "unas",
    "alrededor de",
    "cerca de",
    "en torno a",
    "sobre los",
    "sobre las",
    "más o menos",
    "mas o menos",
    "casi",
    "rondando",
    "ronda los",
    "ronda las",
)

# Un € es un número (es-ES o en-US) pegado a un marcador de moneda, por delante (€2.400) o por detrás
# (2.400 €, 2.400 EUR, 2.400 euros). El número admite miles con . y decimales con , (o al revés en-US).
_NUM = r"-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|-?\d+(?:[.,]\d+)?"
_RE_EURO = re.compile(
    rf"(?:(?P<pre>€|EUR)\s*(?P<n1>{_NUM}))" rf"|(?:(?P<n2>{_NUM})\s*(?P<post>€|EUR|euros?|eur))",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CifraNarrada:
    """Un importe en € hallado en la narrativa del LLM: su valor normalizado, el texto crudo y si venía
    hedgeado con una marca de aproximación (lo que ya de por sí lo descalifica como cifra de tool).
    """

    valor: float
    crudo: str
    aproximada: bool


@dataclass
class ReporteCifras:
    """Veredicto del guardia POST-LLM sobre una narrativa. `veredicto` ∈ {LIMPIO, BLOQUEAR}."""

    veredicto: str
    respaldadas: list[CifraNarrada] = field(default_factory=list)
    sin_respaldo: list[CifraNarrada] = field(default_factory=list)
    motivos: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.veredicto == LIMPIO


LIMPIO, BLOQUEAR = "LIMPIO", "BLOQUEAR"
# Acciones de política cuando hay € sin respaldo (la brújula: «re-prompt o abstención honesta»).
EMITIR, REPROMPT, ABSTENER = "emitir", "re-prompt", "abstener"


def _normalizar_numero(crudo: str) -> float | None:
    """'2.400,50' (es) / '2,400.50' (en) / '2400' → float. None si no parsea. El separador MÁS a la
    derecha manda como decimal SOLO si deja 1-2 dígitos; si no, es separador de miles."""
    s = crudo.replace("−", "-").replace(" ", "")
    neg = s.startswith("-")
    s = s.lstrip("-")
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):  # es-ES: coma decimal
            s = s.replace(".", "").replace(",", ".")
        else:  # en-US: punto decimal
            s = s.replace(",", "")
    elif "," in s:
        ent, _, dec = s.rpartition(",")
        s = f"{ent.replace('.', '')}.{dec}" if len(dec) in (1, 2) else s.replace(",", "")
    elif "." in s:
        ent, _, dec = s.rpartition(".")
        if len(dec) not in (1, 2):  # punto como separador de miles
            s = s.replace(".", "")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _es_aproximada(texto: str, ini: int) -> bool:
    """¿Hay una marca de aproximación justo antes de la cifra (mismos ~16 chars previos)?"""
    ventana = texto[max(0, ini - 16) : ini].lower()
    return any(m in ventana for m in _MARCAS_APROX)


def extraer_cifras_euro(narrativa: object) -> list[CifraNarrada]:
    """Extrae TODOS los importes en € de una narrativa (no solo el principal). Alta recall: el guardia
    debe ver cada € que el modelo afirma. Ignora números sin marcador de moneda (no son consecuentes).
    """
    texto = str(narrativa or "")
    out: list[CifraNarrada] = []
    for m in _RE_EURO.finditer(texto):
        crudo = m.group("n1") if m.group("n1") is not None else m.group("n2")
        if crudo is None:
            continue
        valor = _normalizar_numero(crudo)
        if valor is None:
            continue
        out.append(
            CifraNarrada(valor=valor, crudo=crudo, aproximada=_es_aproximada(texto, m.start()))
        )
    return out


def _respaldo_ledger(ledger: object) -> list[float]:
    """El ledger = cifras que salieron de tools de este run. Acepta lista de números o de dicts con
    'valor'/'importe'/'monto'/'cantidad'. Lo no numérico se ignora (no respalda)."""
    vals: list[float] = []
    if ledger is None:
        return vals
    items = ledger if isinstance(ledger, (list, tuple, set)) else [ledger]
    for it in items:
        v: object = it
        if isinstance(it, dict):
            for clave in ("valor", "importe", "monto", "cantidad", "total"):
                if clave in it:
                    v = it[clave]
                    break
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            vals.append(float(v))
    return vals


def _respaldada(valor: float, respaldos: list[float]) -> bool:
    return any(abs(valor - r) <= TOL_CENTIMO for r in respaldos)


def auditar_cifras(narrativa: object, ledger: object = None) -> ReporteCifras:
    """GUARDIA §14B-1: toda cifra en € de la narrativa debe estar respaldada (al céntimo) por una cifra de
    tool del ledger; si está hedgeada ('~2.400 €') no cuenta como respaldada aunque ronde un valor. Si
    queda algún € sin respaldo → veredicto BLOQUEAR (no se emite a ojo)."""
    respaldos = _respaldo_ledger(ledger)
    cifras = extraer_cifras_euro(narrativa)
    rep = ReporteCifras(veredicto=LIMPIO)
    for c in cifras:
        if c.aproximada:
            rep.sin_respaldo.append(c)
            rep.motivos.append(
                f"cifra narrada APROXIMADA «{c.crudo} €» (una tool da el dato exacto)"
            )
        elif _respaldada(c.valor, respaldos):
            rep.respaldadas.append(c)
        else:
            rep.sin_respaldo.append(c)
            rep.motivos.append(
                f"«{c.crudo} €» no procede de ninguna tool de este run (cifra inventada)"
            )
    if rep.sin_respaldo:
        rep.veredicto = BLOQUEAR
    return rep


def decidir_accion(reporte: ReporteCifras) -> str:
    """Política tras el guardia (brújula §14B-1): limpio → EMITIR; con cifras sin respaldo → re-prompt si
    HAY ledger (el modelo puede corregir citando la tool), o ABSTENER si no había ninguna cifra de tool
    (no hay de dónde sacar el dato → abstención honesta)."""
    if reporte.ok:
        return EMITIR
    # Si ninguna cifra se respaldó y tampoco hay respaldadas, no hay base → abstención honesta.
    return REPROMPT if reporte.respaldadas else ABSTENER


def exigir_cifras_respaldadas(narrativa: object, ledger: object = None) -> ReporteCifras:
    """Igual que `auditar_cifras` pero LANZA si hay € sin respaldo (para el camino que no tolera emitir a
    ojo). Devuelve el reporte limpio si pasa."""
    rep = auditar_cifras(narrativa, ledger)
    if not rep.ok:
        raise CifraSinRespaldo(rep)
    return rep


class CifraSinRespaldo(ValueError):
    """Se intentó emitir una narrativa con € que no salieron de ninguna tool del run (§14B-1)."""

    def __init__(self, reporte: ReporteCifras) -> None:
        super().__init__("; ".join(reporte.motivos) or "cifra sin respaldo")
        self.reporte = reporte
