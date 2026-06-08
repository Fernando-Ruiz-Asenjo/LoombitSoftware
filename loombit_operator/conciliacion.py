"""
conciliacion.py — Skill W Administration Core: conciliación bancaria determinista.

Dos piezas, ambas **deterministas y locales** (el LLM no toca un número):

1. **Parser Norma 43** (Cuaderno 43 AEB/CSB) — el formato estándar de extracto bancario
   interbancario en España. Valida el cuadre de saldos del registro 33: si el extracto no
   cuadra, lo señala en `avisos` (no lo oculta) → no se concilia a ciegas.
2. **Matcher con semáforo de confianza** — casa cada abono del extracto contra las partidas
   pendientes de cobro, con un tier explicable (ALTA/MEDIA/BAJA/ABSTENCIÓN) y una razón
   legible. **Si duda, se abstiene** (no inventa el cobro): la decisión la confirma el humano.

Núcleo **blanco y neutro**: no conoce "IVA" ni "303". El dominio (fiscal/cobros) construye
las `Pendiente` desde sus expedientes y materializa los matches que el humano confirma. El
matcher acepta un `AliasResolver` inyectable (costura del flywheel: aprender alias de pagador
de los cobros confirmados); en este slice se inyecta el resolver no-op.

Layout Norma 43 (registros de 80 posiciones; índices 0-based en el código):
  11 cabecera de cuenta · 22 movimiento · 23 concepto complementario
  33 final de cuenta (totales) · 88 fin de fichero
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from itertools import combinations
from typing import Protocol

CENT = Decimal("0.01")


def _imp(raw: str) -> Decimal:
    """14 dígitos N43 → Decimal con 2 decimales implícitos. '00000000123456' → 1234.56."""
    digits = raw.strip() or "0"
    return (Decimal(digits) / Decimal(100)).quantize(CENT)


def _fecha(raw: str) -> date:
    """AAMMDD → date. Pivote de siglo: 00-79 → 20xx, 80-99 → 19xx (extractos recientes)."""
    yy, mm, dd = int(raw[0:2]), int(raw[2:4]), int(raw[4:6])
    year = 2000 + yy if yy < 80 else 1900 + yy
    return date(year, mm, dd)


def _signo(debe_haber: str) -> int:
    """Clave N43: 1=debe (cargo, sale dinero → negativo) · 2=haber (abono → positivo)."""
    return -1 if debe_haber.strip() == "1" else 1


@dataclass
class Movimiento:
    fecha_operacion: date
    fecha_valor: date
    importe: Decimal  # con signo: + abono (haber), - cargo (debe)
    concepto_comun: str
    concepto_propio: str
    num_documento: str
    referencia1: str
    referencia2: str
    conceptos: list[str] = field(default_factory=list)  # texto libre de los registros 23

    @property
    def es_abono(self) -> bool:
        return self.importe > 0

    @property
    def texto(self) -> str:
        """Concepto consolidado (lo que el matcher leerá para casar contrapartida/ref)."""
        partes = [self.referencia1.strip(), self.referencia2.strip(), *self.conceptos]
        return " ".join(p for p in partes if p).strip()


@dataclass
class CuentaExtracto:
    entidad: str
    oficina: str
    cuenta: str
    fecha_inicial: date
    fecha_final: date
    divisa: str
    saldo_inicial: Decimal
    saldo_final: Decimal
    movimientos: list[Movimiento] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def total_abonos(self) -> Decimal:
        return sum((m.importe for m in self.movimientos if m.importe > 0), Decimal("0.00"))

    @property
    def total_cargos(self) -> Decimal:
        return sum((-m.importe for m in self.movimientos if m.importe < 0), Decimal("0.00"))

    @property
    def cuadra(self) -> bool:
        """saldo_inicial + abonos - cargos == saldo_final (al céntimo). El gate de honestidad:
        si no cuadra, NO se concilia a ciegas; se escala (queda en `avisos`)."""
        calculado = (self.saldo_inicial + self.total_abonos - self.total_cargos).quantize(CENT)
        return abs(calculado - self.saldo_final) <= CENT


def parse_norma43(text: str) -> list[CuentaExtracto]:
    """Parsea un fichero Norma 43 en una o varias cuentas (cada bloque 11…33).

    Determinista y tolerante a líneas cortas (las rellena a 80). No inventa importes;
    valida el cuadre debe/haber/saldo y los totales del registro 33, dejando avisos.
    """
    cuentas: list[CuentaExtracto] = []
    actual: CuentaExtracto | None = None
    mov_actual: Movimiento | None = None

    for ln in text.splitlines():
        if not ln.strip():
            continue
        r = ln.ljust(80)
        tipo = r[0:2]

        if tipo == "11":
            actual = CuentaExtracto(
                entidad=r[2:6].strip(),
                oficina=r[6:10].strip(),
                cuenta=r[10:20].strip(),
                fecha_inicial=_fecha(r[20:26]),
                fecha_final=_fecha(r[26:32]),
                divisa=r[47:50].strip(),
                saldo_inicial=_imp(r[33:47]) * _signo(r[32:33]),
                saldo_final=Decimal("0.00"),
            )
            cuentas.append(actual)
            mov_actual = None

        elif tipo == "22" and actual is not None:
            mov_actual = Movimiento(
                fecha_operacion=_fecha(r[6:12]),
                fecha_valor=_fecha(r[12:18]),
                concepto_comun=r[18:20].strip(),
                concepto_propio=r[20:23].strip(),
                importe=_imp(r[24:38]) * _signo(r[23:24]),
                num_documento=r[38:48].strip(),
                referencia1=r[48:60].strip(),
                referencia2=r[60:76].strip(),
            )
            actual.movimientos.append(mov_actual)

        elif tipo == "23" and mov_actual is not None:
            for trozo in (r[4:42], r[42:80]):
                t = trozo.strip()
                if t:
                    mov_actual.conceptos.append(t)

        elif tipo == "33" and actual is not None:
            n_debe, suma_debe = int(r[6:11] or 0), _imp(r[11:25])
            n_haber, suma_haber = int(r[25:30] or 0), _imp(r[30:44])
            actual.saldo_final = _imp(r[45:59]) * _signo(r[44:45])
            _validar_totales(actual, n_debe, suma_debe, n_haber, suma_haber)
            actual = None
            mov_actual = None

    return cuentas


def _validar_totales(
    cuenta: CuentaExtracto,
    n_debe: int,
    suma_debe: Decimal,
    n_haber: int,
    suma_haber: Decimal,
) -> None:
    """Compara los totales declarados en el registro 33 con lo parseado. No corrige: avisa."""
    apuntes_debe = sum(1 for m in cuenta.movimientos if m.importe < 0)
    apuntes_haber = sum(1 for m in cuenta.movimientos if m.importe > 0)
    if n_debe != apuntes_debe or n_haber != apuntes_haber:
        cuenta.avisos.append(
            f"Nº de apuntes no cuadra con el registro 33 (debe {apuntes_debe}/{n_debe}, "
            f"haber {apuntes_haber}/{n_haber}): revisar el extracto."
        )
    if abs(suma_debe - cuenta.total_cargos) > CENT or abs(suma_haber - cuenta.total_abonos) > CENT:
        cuenta.avisos.append(
            f"Sumas no cuadran con el registro 33 (debe {cuenta.total_cargos}/{suma_debe}, "
            f"haber {cuenta.total_abonos}/{suma_haber}): revisar el extracto."
        )
    if not cuenta.cuadra:
        cuenta.avisos.append(
            "El saldo final no cuadra con saldo inicial + abonos - cargos: NO conciliar "
            "a ciegas, escalar a revisión humana."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Matcher con semáforo de confianza (determinista; el LLM no decide ni numera).
# ─────────────────────────────────────────────────────────────────────────────

# Tokens de forma jurídica y ruido que NO identifican a la contraparte.
_TOKENS_RUIDO = frozenset(
    {
        "SL",
        "SA",
        "SLU",
        "SAU",
        "SCP",
        "SC",
        "SLL",
        "SLNE",
        "CB",
        "SRL",
        "SCCL",
        "SAL",
        "DE",
        "DEL",
        "LA",
        "EL",
        "LOS",
        "LAS",
        "Y",
        "SU",
        "TRANSF",
        "TRANSFERENCIA",
        "PAGO",
        "ABONO",
        "RECIBO",
        "FACTURA",
        "FRA",
        "REF",
        "CONCEPTO",
        "NOMINA",
    }
)


def _sin_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _norm(s: str) -> str:
    """Mayúsculas, sin acentos, espacios colapsados — para comparar por tokens."""
    return " ".join(_sin_acentos(s).upper().split())


def _compacto(s: str) -> str:
    """Solo alfanumérico en mayúsculas — para contención robusta de referencias
    ('FRA2024-007' y 'FRA 2024 007' colapsan a 'FRA2024007')."""
    return re.sub(r"[^0-9A-Z]", "", _sin_acentos(s).upper())


def _tokens_significativos(nombre: str) -> list[str]:
    return [t for t in _norm(nombre).split() if len(t) >= 3 and t not in _TOKENS_RUIDO]


class ConfianzaTier(StrEnum):
    ALTA = "alta"  # importe exacto + referencia/nº de factura en el concepto
    MEDIA = "media"  # importe exacto + contraparte, o candidato único
    BAJA = "baja"  # pago parcial o agrupado N:1 → requiere revisión humana
    ABSTENCION = "abstencion"  # sin candidato fiable: no se concilia (escala)


@dataclass
class Pendiente:
    """Partida pendiente de cobro, **neutra** (sin vocabulario fiscal). El dominio la
    construye desde sus expedientes; el matcher solo ve importe + referencia + contraparte."""

    id: str
    importe: Decimal  # importe pendiente de cobrar (> 0)
    referencia: str = ""  # nº de factura / referencia esperada en el concepto
    contraparte: str = ""  # nombre del cliente/pagador esperado


@dataclass
class Conciliacion:
    """Propuesta de casación de UN movimiento. `pendiente`/`grupo` solo si hay match."""

    movimiento: Movimiento
    pendiente: Pendiente | None
    tier: ConfianzaTier
    razon: str
    score: float = 0.0
    grupo: list[Pendiente] = field(default_factory=list)  # solo en agrupado N:1


class AliasResolver(Protocol):
    """Costura del flywheel (turno aparte): mapea un concepto libre del banco al nombre
    canónico de una contraparte conocida, aprendido de los cobros que el humano confirma
    (tabla de alias determinista, con procedencia; el LLM no interviene). En este slice se
    inyecta un resolver no-op (`canonico` devuelve None)."""

    def canonico(self, texto: str) -> str | None: ...


def _ref_en_texto(ref: str, texto_compacto: str) -> bool:
    c = _compacto(ref)
    return len(c) >= 4 and c in texto_compacto


def _contraparte_en_texto(contraparte: str, texto_norm: str, canon: str | None) -> bool:
    cp_toks = set(_tokens_significativos(contraparte))
    # El alias-resolver afirma "este concepto del banco ES la contraparte <canon>": casa si la
    # factura es de esa misma contraparte (comparación canon ↔ contraparte, no canon ↔ texto).
    if canon and cp_toks & set(_tokens_significativos(canon)):
        return True
    texto_toks = set(texto_norm.split())
    return any(t in texto_toks for t in cp_toks)


def conciliar(
    movimientos: list[Movimiento],
    pendientes: list[Pendiente],
    alias_resolver: AliasResolver | None = None,
) -> list[Conciliacion]:
    """Casa cada movimiento del extracto contra las partidas pendientes de cobro.

    Solo los **abonos** se casan contra cobros; los cargos se devuelven marcados como fuera
    de alcance (nada se descarta en silencio). Determinista: el tier sale de reglas, no de un
    modelo. Devuelve una `Conciliacion` por movimiento, en orden.
    """
    return [
        (
            _conciliar_abono(mov, pendientes, alias_resolver)
            if mov.es_abono
            else Conciliacion(
                mov,
                None,
                ConfianzaTier.ABSTENCION,
                "Movimiento de cargo (pago emitido): fuera del alcance de conciliación de cobros.",
            )
        )
        for mov in movimientos
    ]


def _conciliar_abono(
    mov: Movimiento, pendientes: list[Pendiente], alias_resolver: AliasResolver | None
) -> Conciliacion:
    texto_norm = _norm(mov.texto)
    texto_comp = _compacto(mov.texto)
    canon = alias_resolver.canonico(mov.texto) if alias_resolver else None

    exactos = [p for p in pendientes if abs(p.importe - mov.importe) <= CENT]

    # 1. Referencia (señal casi única) sobre importe exacto → ALTA.
    con_ref = [p for p in exactos if p.referencia and _ref_en_texto(p.referencia, texto_comp)]
    if len(con_ref) == 1:
        return Conciliacion(
            mov,
            con_ref[0],
            ConfianzaTier.ALTA,
            f"Importe exacto + referencia {con_ref[0].referencia} presente en el concepto.",
            1.0,
        )
    if len(con_ref) > 1:
        return Conciliacion(
            mov,
            None,
            ConfianzaTier.ABSTENCION,
            "Varias facturas con el mismo importe y referencia en el concepto: ambiguo, revisar.",
        )

    # 2. Importe exacto + contraparte, o candidato único → MEDIA.
    if exactos:
        con_cp = [p for p in exactos if _contraparte_en_texto(p.contraparte, texto_norm, canon)]
        if len(con_cp) == 1:
            return Conciliacion(
                mov,
                con_cp[0],
                ConfianzaTier.MEDIA,
                f"Importe exacto + contraparte «{con_cp[0].contraparte}» en el concepto.",
                0.75,
            )
        if len(exactos) == 1:
            return Conciliacion(
                mov,
                exactos[0],
                ConfianzaTier.MEDIA,
                "Importe exacto y candidato único (sin referencia ni nombre en el concepto).",
                0.6,
            )
        return Conciliacion(
            mov,
            None,
            ConfianzaTier.ABSTENCION,
            f"{len(exactos)} facturas con el mismo importe y nada que las distinga: revisar.",
        )

    # 3. Sin importe exacto → pago parcial (con referencia) o agrupado N:1; si no, abstención.
    parcial = [
        p
        for p in pendientes
        if p.referencia and _ref_en_texto(p.referencia, texto_comp) and mov.importe < p.importe
    ]
    if len(parcial) == 1:
        return Conciliacion(
            mov,
            parcial[0],
            ConfianzaTier.BAJA,
            f"Posible pago parcial de la factura {parcial[0].referencia} "
            f"(cobrado {mov.importe} de {parcial[0].importe}): revisar.",
            0.4,
        )

    grupo = _subset_suma(mov, pendientes, texto_norm, canon)
    if grupo is not None:
        refs = ", ".join(p.referencia or p.id for p in grupo)
        return Conciliacion(
            mov,
            None,
            ConfianzaTier.BAJA,
            f"Posible pago agrupado de varias facturas que suman el importe ({refs}): revisar.",
            0.4,
            grupo=grupo,
        )

    return Conciliacion(
        mov,
        None,
        ConfianzaTier.ABSTENCION,
        "Sin factura pendiente que cuadre con el importe: no se concilia (escalar).",
    )


def _subset_suma(
    mov: Movimiento,
    pendientes: list[Pendiente],
    texto_norm: str,
    canon: str | None,
    max_n: int = 3,
) -> list[Pendiente] | None:
    """Busca un subconjunto pequeño de pendientes de la MISMA contraparte (presente en el
    concepto) cuyos importes sumen el movimiento. Acotado a `max_n` para no explotar."""
    candidatos = [p for p in pendientes if _contraparte_en_texto(p.contraparte, texto_norm, canon)]
    if len(candidatos) < 2:
        return None
    for n in range(2, min(max_n, len(candidatos)) + 1):
        for combo in combinations(candidatos, n):
            if abs(sum((p.importe for p in combo), Decimal("0.00")) - mov.importe) <= CENT:
                return list(combo)
    return None
