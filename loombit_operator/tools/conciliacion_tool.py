"""
Tool de CONCILIACIÓN bancaria para el agente — el motor ya existía (`conciliacion.py`), pero NO
estaba expuesto como herramienta, así que el chat abstenía ("no tengo herramienta para conciliar").
Esto le da las manos: el agente PROPONE matches de un extracto Norma 43 contra los cobros pendientes.

Regla nº1 (la IA propone, no decide el dinero): es SOLO PROPUESTA, de solo lectura. NO marca nada
como cobrado; el humano aprueba qué aplicar (flujo /entidades/{id}/conciliacion/.../aprobar). Las
cifras y el casado los hace CÓDIGO determinista, no el LLM.
"""

from __future__ import annotations

from .registry import ToolDefinition, tool_registry

_ENTIDAD_DEFECTO = "principal"


def _conciliar_banco(extracto_n43: str = "") -> str:
    """Casa un extracto Norma 43 contra los cobros pendientes y PROPONE los matches (no aplica nada)."""
    if not (extracto_n43 or "").strip():
        return (
            "Para conciliar necesito tu extracto en formato Norma 43 (un fichero de texto que puedes "
            "descargar de tu banca online). Pégalo o pásame su ruta y caso los abonos con tus cobros "
            "pendientes; tú decides cuáles aplicar."
        )
    # Imports perezosos: el motor tira de expedientes/skill_d_fiscal → evita ciclos al cargar tools.
    from ..alias_resolver import AliasStore
    from ..conciliacion import ConfianzaTier, conciliar, parse_norma43
    from ..expedientes import ExpedienteStore
    from ..skill_d_fiscal import pendientes_de_cobro

    cuentas = parse_norma43(extracto_n43)
    if not cuentas:
        return (
            "Eso no parece un extracto Norma 43 válido (no encontré cuentas). Descárgalo de tu banca "
            "online en formato 'Norma 43' / 'C43' y vuelve a pasármelo."
        )
    movimientos = [m for c in cuentas for m in c.movimientos]
    try:
        store = ExpedienteStore(entity_id=_ENTIDAD_DEFECTO)
        pendientes = pendientes_de_cobro(store)
        resolver = AliasStore(entity_id=_ENTIDAD_DEFECTO)
    except Exception as exc:  # noqa: BLE001
        return f"ERROR al leer tus cobros pendientes: {exc}"

    conciliaciones = conciliar(movimientos, pendientes, alias_resolver=resolver)
    resumen = {t: sum(1 for c in conciliaciones if c.tier is t) for t in ConfianzaTier}
    lineas = [
        f"Conciliación de {len(movimientos)} movimiento(s) contra {len(pendientes)} cobro(s) "
        "pendiente(s) — PROPUESTA, no he marcado nada como cobrado:"
    ]
    for t in ConfianzaTier:
        if resumen[t]:
            lineas.append(f"  · {resumen[t]} con confianza {t.value}")
    for c in conciliaciones[:8]:
        contraparte = c.pendiente.contraparte if c.pendiente else "(sin pareja)"
        lineas.append(
            f"  - {c.movimiento.fecha_operacion.isoformat()} · {c.movimiento.importe} € "
            f"«{c.movimiento.texto[:32]}» → {contraparte} [{c.tier.value}]"
        )
    lineas.append("Dime cuáles confirmo y los marco como cobrados (tú apruebas).")
    return "\n".join(lineas)


tool_registry.register(
    ToolDefinition(
        name="conciliar_banco",
        description=(
            "Concilia un extracto bancario Norma 43 (texto en `extracto_n43`) contra tus cobros "
            "pendientes y PROPONE qué abono casa con qué factura (con semáforo de confianza). NO marca "
            "nada como cobrado: es una propuesta para que el usuario apruebe. Úsala cuando pidan "
            "'concilia mi banco/extracto'. Si no hay extracto, pídelo (Norma 43 de la banca online)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "extracto_n43": {
                    "type": "string",
                    "description": "Contenido del extracto en formato Norma 43.",
                },
            },
        },
        fn=_conciliar_banco,
        category="base",
        authoritative=True,
    )
)
