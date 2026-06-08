# Taxonomía canónica de skills — fuente completa

> Fuente de verdad de la taxonomía de skills de Loombit. Obligatoria en títulos de hilo,
> documentación, manifests y planificación. La **descomposición** del dominio está en
> `ARQUITECTURA_SKILLS.md`; la **auto-autoría** en `FABRICA_DE_SKILLS.md`. *Vivo, 2026-06-08.*

## Códigos de autoridad

| Código | Nombre | Rol |
|---|---|---|
| `Skill C` | Canonical | Gobierna: nombrado, seguridad, estética, arquitectura de plataforma |
| `Skill W` | White Kernel | Núcleo limpio sin sesgo de dominio, sector ni cliente |
| `Skill G` | Golden Path | Flujo recomendado construido sobre C y W |
| `Skill D` | Domain | Especialización sectorial/comercial; depende de W, no lo contamina |
| `Skill A` | Adapter | Conector, bridge de hardware, proveedor, entorno |
| `Skill X` | Experimental | Lab/prototipo; no puede gobernar comportamiento estable |

**Precedencia:** `Skill C > Skill W > Skill G > Skill D > Skill A > Skill X`

## Reglas

- Un `Skill D` **no mueve vocabulario ni lógica** al núcleo blanco (W).
- Un `Skill W` **no asume** sector, cliente ni rol concreto.
- Un `Skill A` **debe ser reemplazable** sin cambiar el comportamiento por encima.
- Un `Skill X` **debe promoverse** (evals + revisión humana) antes de afectar comportamiento estable.
- Las 3 capas no se mezclan: **conocimiento (D) ≠ primitiva neutra (W) ≠ conector (A)**.

## Skills activas

| Nombre canónico | Alias | Tipo | Estado |
|---|---|---|---|
| `Skill C Loombit Skins` | — | C | reglas de diseño/UI/estética |
| `Skill W Loombit Coding` | Skill Coding Blanca | W | núcleo limpio de trabajo de código |
| `Skill W Loombit Pilot` | Skill Pilot Blanca | W | control local de escritorio (DPI, UIA, gates) |
| `Skill W Administration Core` | — | W | primitivas admin neutras: Entidad, **Expediente/CaseFile**, Documento, Plazo, Gate de aprobación, Recibo, **Trazabilidad**, Cursor |
| `Skill W Routines` | — | W | agentes proactivos programados (scheduler/cron) — 🟢 slice verificado (ver `ROUTINES_LOOMBIT.md`) |
| `Skill D Skill Blanca Administration` | Skill Blanca Administracion | D | trabajo administrativo de oficina (paraguas; se descompone en la familia D) |
| `Skill A Google Workspace Connector` | — | A | conector OAuth Google (Gmail, Calendar, Drive, People) |

## Familia `Skill D` administrativa (en construcción, por cuña)

Ver `ARQUITECTURA_SKILLS.md` para el detalle (supuestos/tests/código por skill):

| Skill D | Estado | Nota |
|---|---|---|
| `Skill D Cobros` | 🟡 motor (dunning Ley 3/2004) | cuña activa |
| `Skill D Documental` | 🟡 extractor (`docs_intel`) | facturas/albaranes |
| `Skill D Banca/Tesorería` | ⬜ | conciliación (innovación #1) |
| `Skill D Fiscal` | ⬜ análisis hecho | 303 + AEAT; ver `PLATAFORMA_FISCAL_ANALISIS.md` |
| `Skill D Laboral` | ⬜ | nóminas, Sistema RED, IT |
| `Skill D` sectoriales | ⬜ | salud/mutuas, transporte/eCMR, hostelería… |

## Cuándo una skill está 🟢

Una skill (o `Skill D` auto-creada) pasa a 🟢 solo cuando **pasa sus supuestos como evals**
contra datos reales, deja **recibo**, **cita fuentes** para sus afirmaciones legales/fiscales,
la **ruta de fallo bloquea limpio**, y un **humano la ha revisado/promovido** (regla `Skill X`).
Ver `FABRICA_DE_SKILLS.md` y `DEFINITION_OF_DONE.md`.
