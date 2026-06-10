"""
AUDITORÍA FUERTE (caja blanca, determinista) de los 3 fixes de diseño. No comprueba «¿pasa el happy
path?» sino que MARTILLEA la lógica con casos límite diseñados para ROMPERLA: falsos positivos
(sobre-disparar), falsos negativos (no disparar), agujeros de regex, sobre-corrección de importes,
interacciones. Cada caso lleva el resultado CORRECTO esperado; un FAIL es un HALLAZGO de auditoría.

Sin LM (el clasificador LLM se prueba con un fake). Rápido. Uso: python scripts/auditoria_d1d2d3.py
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loombit_operator.agent import descomposicion as D  # noqa: E402
from loombit_operator.agent.guardas import registro_guardas  # noqa: E402
from loombit_operator.agent.intencion import intencion_consecuente, tiene_dato  # noqa: E402
from loombit_operator.agent.loop import _corregir_importe, _normalizar_alias_factura  # noqa: E402
from loombit_operator.agent.parsers import parsear_importe_es  # noqa: E402
from loombit_operator.skill_d_fiscal import (
    guardas_fiscales as G,
)  # noqa: E402,F401 (registra guardas)


class _FakeLLM:
    def __init__(self, resp):
        self._r = resp

    def chat(self, messages, temperature=None, **kw):
        return SimpleNamespace(content=self._r)


CASOS: list[tuple[str, str, bool]] = []


def chk(fam, label, got, exp):
    CASOS.append((fam, label, got == exp, f"got={got!r} exp={exp!r}"))


# ══════════════════ D-1 · ROUTING ══════════════════
# Positivos: deben rutear bien
chk(
    "D1",
    "registro coloquial 'mete'",
    intencion_consecuente("mete en el sistema lo que le facturé a x: 800 € al 21%"),
    "factura",
)
chk(
    "D1",
    "registro 'anota la factura'",
    intencion_consecuente("anota la factura emitida a López de 350 al 21%"),
    "factura",
)
chk("D1", "303 explícito", intencion_consecuente("calcula el 303 con ventas de 1000 al 21%"), "303")
chk("D1", "cobro con dato", intencion_consecuente("reclama 1500 € de la factura vencida"), "cobro")
# Falsos positivos a evitar (queries NO son registros)
chk(
    "D1",
    "FP query '¿cuánto facturé?'",
    intencion_consecuente("¿cuánto le facturé a Endesa este mes?"),
    "facturacion",
)
chk(
    "D1",
    "FP 'mete la cita en la agenda'",
    intencion_consecuente("mete la cita del lunes en la agenda") in ("recordatorio", None),
    True,
)
chk(
    "D1",
    "FP 'factura' sin verbo→no factura",
    intencion_consecuente("¿cuándo vence la factura de Acme?") != "factura",
    True,
)
chk(
    "D1",
    "compuesta→resumen",
    intencion_consecuente("¿cuánto he facturado y cuánto me deben?"),
    "resumen_financiero",
)
chk(
    "D1",
    "303 no se traga 'registra el 303'",
    intencion_consecuente("registra el 303 del 2T") != "factura",
    True,
)
# tiene_dato (data-gate del clasificador)
chk("D1", "tiene_dato cifra", tiene_dato("reclama 1500 a Acme"), True)
chk("D1", "tiene_dato palabra 'mil'", tiene_dato("reclama mil euros"), True)
chk("D1", "tiene_dato NO sin número", tiene_dato("reclama el cobro a Acme"), False)
# merece_clasificar (gate del clasificador): amplio pero no ajeno
chk("D1", "merece adeudan", D.merece_clasificar("¿cuánto me adeudan los clientes?"), True)
chk("D1", "merece factura", D.merece_clasificar("mete una factura nueva"), True)
chk("D1", "merece NO ajeno", D.merece_clasificar("¿qué tiempo hace hoy?"), False)
chk("D1", "merece NO saludo", D.merece_clasificar("buenas, ¿cómo estás?"), False)
# clasificar_intencion (fake LLM): umbral, ninguna, exclusión, JSON roto
chk(
    "D1",
    "clasif conf alta",
    D.clasificar_intencion("x", _FakeLLM('{"intencion":"cobros_pend","confianza":0.9}')),
    "cobros_pend",
)
chk(
    "D1",
    "clasif conf baja→None",
    D.clasificar_intencion("x", _FakeLLM('{"intencion":"cobro","confianza":0.4}')),
    None,
)
chk(
    "D1",
    "clasif fuera de menú→None",
    D.clasificar_intencion("x", _FakeLLM('{"intencion":"viajes","confianza":0.9}')),
    None,
)
chk("D1", "clasif JSON roto→None", D.clasificar_intencion("x", _FakeLLM("no json")), None)
chk(
    "D1",
    "clasif conciliación excluida",
    D.clasificar_intencion(
        "concíliame el banco", _FakeLLM('{"intencion":"cobros_pend","confianza":0.9}')
    ),
    None,
)
chk(
    "D1",
    "clasif extracto excluido",
    D.clasificar_intencion(
        "cuadra el extracto bancario", _FakeLLM('{"intencion":"cobros_pend","confianza":0.9}')
    ),
    None,
)

# ══════════════════ D-2 · GUARDAS DE DOMINIO ══════════════════
R, IB, M = G.es_registro_con_retencion, G.iban_invalido_a_guardar, G.modelo_no_modelado
# Retención — positivos (debe abstener)
chk("D2", "reten 'retención del 15%'", R("emite una factura con retención del 15%"), True)
chk(
    "D2",
    "reten 'me retienen'",
    R("hazme la minuta: 1000 menos el 15% de IRPF que me retienen"),
    True,
)
chk("D2", "reten 'retenido'", R("factura de 3000 con 15% retenido de irpf"), True)
chk("D2", "reten 'retiene'", R("emite la minuta, el cliente me retiene el 15%"), True)
# Retención — negativos (NO debe abstener)
chk("D2", "reten NEG 'sin retención'", R("registra la factura de 1000 al 21% sin retención"), False)
chk(
    "D2", "reten NEG 'no me retienen'", R("registra la factura de 1000, no me retienen nada"), False
)
chk("D2", "reten NEG pregunta", R("¿qué retención de IRPF me corresponde?"), False)
chk("D2", "reten NEG factura normal", R("registra una factura de 1000 al 21% de IVA"), False)
# IBAN — positivos (inválido a guardar → abstiene)
chk("D2", "iban 'guarda' inválido", IB("guarda el IBAN ES00 0000 0000 0000 0000 0000"), True)
chk(
    "D2",
    "iban 'apúntame' (acento)",
    IB("apúntame el IBAN de pago: ES00 0000 0000 0000 0000 0000"),
    True,
)
chk("D2", "iban 'anota' inválido", IB("anota el IBAN ES99 1234 de mi cliente"), True)
# IBAN — negativos
chk("D2", "iban NEG válido no abstiene", IB("guarda el IBAN ES9121000418450200051332"), False)
chk("D2", "iban NEG sin verbo guardar", IB("¿es válido el IBAN ES00 0000?"), False)
chk("D2", "iban NEG sin iban", IB("guárdame el dato de Acme"), False)
# Modelo — positivos
chk("D2", "modelo 'modelo 111'", M("hazme el modelo 111 de retenciones"), "111")
chk("D2", "modelo 'el 130'", M("prepárame el 130 del pago fraccionado"), "130")
chk("D2", "modelo nombre intracom", M("hazme el de operaciones intracomunitarias"), "349")
# Modelo — negativos (FALSOS POSITIVOS a evitar)
chk("D2", "modelo NEG 303", M("calcula el modelo 303 del 2T"), None)
chk("D2", "modelo NEG 'el 303'", M("prepárame el 303"), None)
chk("D2", "modelo NEG 'factura número 130'", M("registra la factura número 130 de Acme"), None)
chk("D2", "modelo NEG 'el 130 €'", M("te debo el 130 € de la cena"), None)
chk("D2", "modelo NEG amount 190", M("reclama el 190 € que me debe"), None)
# Conciliación + registro global
chk(
    "D2",
    "concili dispara",
    bool(registro_guardas.aplicar("concíliame el banco con mis cobros")),
    True,
)
chk("D2", "concili NEG '¿cuánto me deben?'", registro_guardas.aplicar("¿cuánto me deben?"), None)
chk(
    "D2",
    "guarda global NEG factura normal",
    registro_guardas.aplicar("registra una factura de 1000 al 21%"),
    None,
)

# ══════════════════ D-3 · EXTRACCIÓN DE IMPORTES ══════════════════
P = parsear_importe_es
chk("D3", "es-ES decimales", P("reclama 1.234,56 € vencidos"), 1234.56)
chk("D3", "negativo", P("base imponible de -200 € e IVA al 21%"), -200.0)
chk("D3", "% excluido", P("factura de 2500 al 21%"), 2500.0)
chk("D3", "año-like 2026 NO excluido", P("factura de 2026 € al 21%"), 2026.0)
chk("D3", "millón con separadores", P("1.000.000,50 € de cobro"), 1000000.5)
chk("D3", "días y % fuera", P("1500 € vencido hace 40 días al 10% de interés"), 1500.0)
chk("D3", "fecha '5 de junio de 2026' fuera", P("base -200 €, fecha 5 de junio de 2026"), -200.0)
chk("D3", "multi-importe→None", P("una de 1000 y otra de 2000"), None)
chk("D3", "sin importe→None", P("¿cuánto me deben?"), None)
chk("D3", "cero", P("factura de 0 € al 21%"), 0.0)
chk("D3", "negativo con miles", P("rectificativa de -1.234,56 €"), -1234.56)
# Corrector
a = {"total": 1.0}
chk(
    "D3",
    "corr plan_cobro total",
    (_corregir_importe("plan_cobro", a, "reclama 2000 € vencidos"), a.get("total")),
    (True, 2000.0),
)
b = {"base": 1.0, "tipo": 21}
chk(
    "D3",
    "corr factura base",
    (_corregir_importe("registrar_factura", b, "factura de 2000 al 21%"), b.get("base")),
    (True, 2000.0),
)
c = {"base": 9, "tipo": 21}
chk(
    "D3",
    "corr IVA incluido",
    (
        _corregir_importe("registrar_factura", c, "factura de 1210 € IVA incluido al 21%"),
        c.get("base"),
    ),
    (True, 1000.0),
)
d = {"base": 2000.0}
chk(
    "D3",
    "corr NO si ya cuadra",
    _corregir_importe("plan_cobro", {"total": 2000.0}, "reclama 2000 €"),
    False,
)
e = {"base": 5.0}
chk(
    "D3",
    "corr NO si multi-importe",
    _corregir_importe("registrar_factura", e, "una de 300 y otra de 500"),
    False,
)
# Alias
f = {"contraparte": "X", "base_imponible": "-200", "tipo_iva": "21"}
_normalizar_alias_factura(f)
chk("D3", "alias base_imponible→base", (f.get("base"), "base_imponible" in f), ("-200", False))
chk("D3", "alias tipo_iva→tipo", (f.get("tipo"), "tipo_iva" in f), ("21", False))
g = {"base": 500, "base_imponible": "999"}
_normalizar_alias_factura(g)
chk("D3", "alias no pisa base real", g.get("base"), 500)


def main() -> int:
    fam_tot: dict[str, list[int]] = {}
    fallos = 0
    for fam, label, ok, det in CASOS:
        fam_tot.setdefault(fam, [0, 0])
        fam_tot[fam][1] += 1
        if ok:
            fam_tot[fam][0] += 1
        else:
            fallos += 1
            print(f"  HALLAZGO [{fam}] {label}  ·  {det}")
    print()
    for fam in sorted(fam_tot):
        ok, tot = fam_tot[fam]
        print(f"  {fam}: {ok}/{tot}")
    print(f"\n== auditoría: {len(CASOS) - fallos}/{len(CASOS)} OK · hallazgos: {fallos} ==")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
