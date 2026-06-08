"""
modelo_303.py — Skill D Fiscal: cálculo DETERMINISTA del Modelo 303 (IVA, régimen general).

El número NUNCA lo pone un LLM: aquí se calcula con `Decimal` (ROUND_HALF_UP) y se cuadra
contra la cuota declarada. La casuística especial (inversión de sujeto pasivo, recargo de
equivalencia, criterio de caja, prorrata) **se señala para revisión humana, no se adivina**.
Cubre las **casillas principales** del régimen general (el 303 real tiene ~80); se declara
como subconjunto honesto. Ver `docs/PLATAFORMA_FISCAL_ANALISIS.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from ..expedientes import Expediente, ExpedienteStatus, ExpedienteStore

CENT = Decimal("0.01")
TIPOS_VALIDOS = {Decimal("0.21"), Decimal("0.10"), Decimal("0.04"), Decimal("0.00")}

# tipo IVA -> (casilla base, casilla cuota) del IVA devengado, régimen general
_CASILLA_DEVENGADO = {
    Decimal("0.21"): ("01", "03"),
    Decimal("0.10"): ("04", "06"),
    Decimal("0.04"): ("07", "09"),
}


def _dec(x: object) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


@dataclass
class LineaIVA:
    base: Decimal
    tipo: Decimal  # 0.21 / 0.10 / 0.04 / 0.00
    sentido: str  # "devengado" (ventas/emitidas) | "soportado" (compras/recibidas)
    deducible: bool = True  # solo aplica a "soportado"
    cuota: Decimal | None = None  # cuota declarada en la factura (para cuadrar)
    concepto: str = ""

    def __post_init__(self) -> None:
        self.base = _dec(self.base)
        self.tipo = _dec(self.tipo)
        if self.cuota is not None:
            self.cuota = _dec(self.cuota)


@dataclass
class Resultado303:
    iva_devengado: Decimal
    iva_deducible: Decimal
    resultado: Decimal  # devengado - deducible
    casillas: dict[str, str]
    avisos: list[str] = field(default_factory=list)

    @property
    def a_ingresar(self) -> bool:
        return self.resultado > 0


def calcular_303(lineas: list[LineaIVA], regimen: str = "general") -> Resultado303:
    """Calcula el 303 (régimen general) de forma determinista a partir de las líneas de IVA."""
    avisos: list[str] = []
    if regimen != "general":
        avisos.append(
            f"Régimen '{regimen}' no soportado por el cálculo automático: requiere revisión del asesor."
        )

    devengado = Decimal("0.00")
    deducible = Decimal("0.00")
    base_deducible = Decimal("0.00")
    base_dev: dict[Decimal, Decimal] = {}
    cuota_dev: dict[Decimal, Decimal] = {}

    for ln in lineas:
        etiqueta = ln.concepto or "línea"
        cuota_calc = (ln.base * ln.tipo).quantize(CENT, rounding=ROUND_HALF_UP)

        if ln.tipo not in TIPOS_VALIDOS:
            avisos.append(
                f"Tipo de IVA no estándar ({ln.tipo}) en '{etiqueta}': revisar "
                "(¿inversión de sujeto pasivo, recargo de equivalencia?)."
            )
        if ln.cuota is not None and abs(ln.cuota - cuota_calc) > CENT:
            avisos.append(
                f"Discrepancia de cuota en '{etiqueta}': factura {ln.cuota} vs calculado "
                f"{cuota_calc} (base {ln.base} × {ln.tipo})."
            )

        if ln.sentido == "devengado":
            devengado += cuota_calc
            base_dev[ln.tipo] = base_dev.get(ln.tipo, Decimal("0.00")) + ln.base
            cuota_dev[ln.tipo] = cuota_dev.get(ln.tipo, Decimal("0.00")) + cuota_calc
        elif ln.sentido == "soportado":
            if ln.deducible:
                deducible += cuota_calc
                base_deducible += ln.base
            else:
                avisos.append(f"IVA soportado NO deducible excluido del cálculo en '{etiqueta}'.")
        else:
            avisos.append(f"Sentido desconocido '{ln.sentido}' en '{etiqueta}': línea ignorada.")

    devengado = devengado.quantize(CENT)
    deducible = deducible.quantize(CENT)
    resultado = (devengado - deducible).quantize(CENT)

    casillas: dict[str, str] = {}
    for tipo, (c_base, c_cuota) in _CASILLA_DEVENGADO.items():
        if tipo in base_dev:
            casillas[c_base] = str(base_dev[tipo].quantize(CENT))
            casillas[c_cuota] = str(cuota_dev[tipo].quantize(CENT))
    casillas["27"] = str(devengado)  # total cuota devengada (aprox.)
    casillas["28"] = str(base_deducible.quantize(CENT))  # base operaciones interiores corrientes
    casillas["29"] = str(deducible)  # cuota deducible operaciones interiores corrientes
    casillas["71"] = str(resultado)  # resultado (aprox., sin compensaciones de periodos previos)

    return Resultado303(
        iva_devengado=devengado,
        iva_deducible=deducible,
        resultado=resultado,
        casillas=casillas,
        avisos=avisos,
    )


def borrador_303_texto(res: Resultado303, periodo: str) -> str:
    """Texto humano del borrador. Deja CLARO que es un borrador, no una presentación."""
    if res.resultado > 0:
        signo = "A INGRESAR"
    elif res.resultado < 0:
        signo = "A COMPENSAR/DEVOLVER"
    else:
        signo = "SIN RESULTADO"
    lines = [
        f"BORRADOR Modelo 303 — {periodo} (régimen general, casillas principales)",
        f"  IVA devengado:  {res.iva_devengado} €",
        f"  IVA deducible:  {res.iva_deducible} €",
        f"  Resultado:      {abs(res.resultado)} €  ({signo})",
        "",
        "  Esto es un BORRADOR, no una presentación. La validez requiere que el titular lo",
        "  revise y lo presente en la Sede de la AEAT con su certificado; el justificante",
        "  oficial devuelto por la AEAT es la única prueba de presentación.",
    ]
    if res.avisos:
        lines.append("")
        lines.append("  AVISOS (revisar antes de presentar):")
        lines.extend(f"   - {a}" for a in res.avisos)
    return "\n".join(lines)


def procesar_303(
    store: ExpedienteStore,
    lineas: list[LineaIVA],
    periodo: str,
    actor: str = "loombit",
) -> tuple[Expediente, Resultado303]:
    """Abre un Expediente `fiscal_303` (W), calcula el 303 (D), guarda resultado + borrador
    con trazabilidad, y lo deja en **PENDING_APPROVAL** (fiscal = SAFETY_SENSITIVE: la IA
    nunca lo da por presentado; lo valida y lo presenta el humano)."""
    res = calcular_303(lineas)
    exp = store.create(
        "fiscal_303",
        f"Modelo 303 {periodo}",
        data={
            "periodo": periodo,
            "casillas": res.casillas,
            "iva_devengado": str(res.iva_devengado),
            "iva_deducible": str(res.iva_deducible),
            "resultado": str(res.resultado),
            "avisos": res.avisos,
            "borrador": borrador_303_texto(res, periodo),
        },
    )
    store.add_event(
        exp.id,
        "calculo_303",
        {"resultado": str(res.resultado), "n_avisos": len(res.avisos)},
        actor,
    )
    store.set_status(exp.id, ExpedienteStatus.PENDING_APPROVAL, actor)
    return store.get(exp.id), res
