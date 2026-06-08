# Arquitectura de skills — descomposición del dominio administrativo

> El monolito "Skill D Administración" se resuelve en una **familia disciplinada** de skills.
> Regla de oro: **conocimiento (D) ≠ primitiva neutra (W) ≠ conector (A)**. Un `Skill D`
> depende de W y **no lo contamina**. Se construyen **just-in-time por cuña**, no todas a la vez.
> *Generado: 2026-06-08. Taxonomía: ver `SKILLS.md` y `CLAUDE.md` (precedencia C>W>G>D>A>X).*

## Las 3 capas (la disciplina que evita el mega-skill)

| Capa | Qué es | Ejemplo "Modelo 303" | Tipo |
|---|---|---|---|
| Conocimiento | saber *qué es* y *cuándo/cómo* | "el 303 es el IVA trimestral, vence el 20" | **Skill D** Fiscal |
| Primitiva neutra | conceptos sin dominio | "un plazo", "un documento", "un gate de aprobación" | **Skill W** Admin Core |
| Conector | el *mecanismo* de ejecución | "presentarlo en la Sede de la AEAT" | **Skill A** AEAT |

## La familia `Skill D` propuesta (conocimiento)

| Skill D | Conocimiento | Supuestos (tests) | Código existente | Clase de seguridad típica |
|---|---|---|---|---|
| Cobros | Ley 3/2004, dunning, intereses de demora | A, II, V | `cobros` ✅ | ASSISTED |
| Fiscal | IVA/IRPF/IS, Modelos 303/111/115/130/200, VeriFactu, calendario | I, III, VI, X | — | SAFETY_SENSITIVE |
| Laboral | nóminas, Sistema RED, TC-1, altas/bajas, IT | IV, IX | — | SAFETY_SENSITIVE |
| Banca/Tesorería | conciliación, PSD2, Norma 43, extractos | (innovación #1) | — | ASSISTED |
| Documental | facturas/albaranes, extracción, cruce | D, III | `docs_intel` ✅ | PASSIVE/ASSISTED |
| Sectoriales (overlays finos) | Salud/Mutuas, Transporte/eCMR, Hostelería, PAC… | B, C, D, G | — | según caso |

## `Skill W Administration Core` (primitivas neutras — ya en la taxonomía)
Entidad (cliente/proveedor), Documento, Plazo, **Gate de aprobación (semáforo)**, Recibo, Cursor de estado.
**Cero vocabulario de dominio.** Los `Skill D` se construyen sobre estas primitivas.

## `Skill A` (conectores, reemplazables)
Google Workspace ✅ · Microsoft Graph · **AEAT/Sede** · **Sistema RED** · **Banca (PSD2/Norma 43)** · **WhatsApp**.
El conocimiento (D) nunca depende de un conector concreto; el conector se puede cambiar sin tocar el saber.

## Reglas
- Un `Skill D` **no mueve vocabulario ni lógica** al núcleo blanco (W).
- El **saber** (D) se separa del **cómo se ejecuta** (A): "qué es un 303" ≠ "presentarlo en la Sede".
- Cada skill declara su **alcance mínimo** de conectores y su **clase de seguridad** (semáforo).
- **Anti-dispersión:** se construye el `Skill D` que el flujo activo necesita; el resto se extrae cuando un flujo real lo pida.

## Orden de construcción por cuña
1. **Cobros** (cuña activa) → ya hay motor.
2. **Banca/Tesorería** (habilita conciliación #1 y el brief).
3. **Documental** (facturas) → ya hay extractor.
4. **Fiscal** → calendario + 303.
5. **Laboral** → nóminas/SS.
6. **Sectoriales** según los clientes reales.
