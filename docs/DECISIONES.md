# Bitácora de decisiones (bloque autónomo 2026-06-08)

> Registro de cada decisión tomada mientras Fernando descansa, con **alternativas
> descartadas y el porqué**, para que pueda revertir o cambiar sin arqueología.
> Autorización del bloque: foco "todo muy pulido", fusionar a main + push, decidir y avanzar.

Formato: **D-NN — decisión** · *contexto* · **elegido** vs alternativas · por qué · reversibilidad.

---

## Scheduler / Routines

**D-01 — Formato de horario: cron de 5 campos (subconjunto), no APScheduler.**
- Alternativas: APScheduler (robusto pero dependencia pesada) · `Schedule` tipado daily/weekly.
- Elegido: matcher cron propio (`*`, `,`, `-`, `/`) en `routines.py`, sin dependencia nueva.
- Por qué: cero dependencias, formato estándar conocido, totalmente unit-testable; las plantillas usan `dom='*'` (sin el gotcha cron del OR dom/dow).
- Reversible: sí; se puede sustituir por APScheduler manteniendo el modelo `Routine`.

**D-02 — `tzdata` como dependencia.**
- Contexto: `zoneinfo` no trae base de zonas en este Windows; `Europe/Madrid` fallaba.
- Elegido: añadir `tzdata>=2024.1` a requirements (forma estándar en Windows).
- Alternativa descartada: offset fijo CET/CEST (incorrecto con cambios de hora).
- Reversible: sí.

**D-03 — Idempotencia por clave de minuto local, persistida.**
- Elegido: `last_fired = "YYYY-MM-DDTHH:MM"` (tz local); `due()` excluye el minuto ya disparado; se persiste en el store → sobrevive a reinicios.
- Por qué: cumple el DoD del slice ("reiniciar no duplica"). Sin catch-up de minutos perdidos (comportamiento cron estándar; mejora futura).
- Reversible: sí.

**D-04 — Semáforo = `SkillSafetyClass` (reutilizado).**
- Elegido: PASSIVE → completado; ASSISTED/SAFETY_SENSITIVE → pendiente de aprobación; BLOCKED_BY_DEFAULT → bloqueado.
- Por qué: reutiliza el enum que ya existía (no inventa); materializa la autonomía supervisada.

**D-05 — Daemon de reloj OPT-IN (flag, por defecto OFF).**
- Elegido: `routines_daemon_enabled=False` por defecto; el tick automático cada 60s solo se activa por config/.env.
- Por qué: evita llamadas LLM sorpresa al importar la app (tests/dev) y respeta "sin efectos inesperados". El motor se prueba por tests + endpoints `/routines/tick` y `/routines/{id}/run`.
- Reversible: sí (poner el flag a True).

**D-06 — Ejecutor del brief: LLM instructor (14B) con contexto mínimo honesto.**
- Contexto: aún NO existen conectores de lectura Gmail/Calendar/banco.
- Elegido: el brief se genera con el 14B y un contexto explícito de "sin fuentes conectadas todavía" (honesto), inyectable para crecer cuando existan las fuentes.
- Por qué: no fingir datos que no tenemos (regla nº1). El motor queda listo; la riqueza del brief llega con los conectores.

---

## Fiscal (Skill D)

**D-07 — El módulo fiscal es una `Skill D` independiente que depende de la Skill Blanca.**
- Decisión de Fernando (explícita). Ver `docs/ARQUITECTURA_SKILLS.md` y el análisis fiscal.
- Implicación: el motor de expedientes/trazabilidad/extracción es núcleo blanco (W); la lógica del 303 y la casuística AEAT viven en `Skill D Fiscal`.

**D-08 — Slice del scheduler IMPLEMENTADO y verificado.**
- `routines.py` + `scheduler.py` + `routers/routines.py` + daemon opt-in + `lifespan` en `main.py`.
- 15 tests nuevos (suite 138 passed); brief real generado por el 14B con recibo en `runtime/local/`.
- Daemon por defecto OFF (ver D-05); se activa con `LOOMBIT_OPERATOR_ROUTINES_DAEMON_ENABLED=true`.

**D-09 — Decisiones de arquitectura de la plataforma fiscal** (análisis, `PLATAFORMA_FISCAL_ANALISIS.md`).
- **`Skill D Fiscal` independiente** sobre `Skill W Administration Core` (motor de Expediente en W; lógica 303/AEAT en D). Decisión de Fernando.
- **SQLite por entidad** (no JSON plano) para expedientes multi-entidad con aislamiento físico (RGPD, escala a gestoría).
- **Liderar con percibir/preparar, NO con presentar** (cero riesgo legal primero); la presentación (borrador → humano presenta) llega con confianza.
- **Diseñar para la gestoría** (multi-entidad día 1); **email como entrada real**; **el número nunca lo pone el LLM** (cálculo determinista + procedencia + abstención).
- Estas son **propuestas a validar por Fernando** (cambian el planteamiento del brief); documentadas para que decida.

**D-10 — Motor de Expedientes (Skill W Core) IMPLEMENTADO** (`expedientes.py`).
- Tras el "sigue con todo mi ok, tú decides": doy por validadas las 4 propuestas fiscales (D-09) y construyo la base.
- **SQLite por entidad** (aislamiento físico multi-tenant); **trazabilidad inmutable** por cadena de hashes (`verify_chain` detecta manipulación); documentos con `sha256`.
- **Neutro** (núcleo blanco; sin vocabulario fiscal) → reutilizable por laboral/mercantil/DGT.
- 8 tests (suite 146). Pendiente: router/UI y el `Skill D Fiscal` (cálculo 303) encima.

**D-11 — `Skill D Fiscal` (cálculo del 303) IMPLEMENTADO** (`skill_d_fiscal/modelo_303.py`).
- Cálculo **determinista** con `Decimal` (ROUND_HALF_UP), cuadre contra la cuota declarada, casillas principales del régimen general.
- Casuística especial (inversión sujeto pasivo, recargo equivalencia, criterio de caja, prorrata) **se señala, no se adivina** (avisos + régimen no general → escala).
- `procesar_303` une W+D: abre Expediente `fiscal_303`, calcula, deja trazabilidad y lo pone **PENDING_APPROVAL** (la IA nunca da por presentado).
- 11 tests (suite 157). Pendiente: extracción de facturas (14B/visión) que alimente las líneas, y router/UI.

**D-12 — Intake fiscal (factura → línea del 303) IMPLEMENTADO** (`skill_d_fiscal/intake.py`).
- Infiere el tipo por **cuadre de cuota al céntimo** (no por ratio): evita colar 5% como 4% y es robusto al tamaño de la base.
- **Abstención** si el tipo no es estándar o faltan base/IVA (no inventa; lo deja como aviso a revisar).
- `registrar_factura` (Expediente `factura_intake` + PDF con huella) y `liquidar_303_periodo` (reúne facturas → 303 → `PENDING_APPROVAL`, arrastrando avisos de facturas ilegibles).
- 8 tests (suite 165). Extracción con 14B/visión para difíciles/escaneadas: pendiente.

**D-13 — Router fiscal (API multi-entidad) IMPLEMENTADO** (`routers/fiscal.py`).
- Endpoints: listar/ver expedientes (con `verify_chain` + eventos + documentos), registrar factura, liquidar 303 (→ `PENDING_APPROVAL`), y **aprobar** (el humano aporta justificante → cierra).
- **Ningún endpoint presenta a la AEAT ni cierra sin acción humana** (regla legal inamovible).
- 3 tests TestClient del flujo completo (suite 168).

---

## Conciliación bancaria (#1) y limpieza de proceso (bloque 2026-06-08, tarde)

**D-14 — Conciliación bancaria IMPLEMENTADA e integrada en `main`** (`conciliacion.py` + `routers/conciliacion.py` + `skill_d_fiscal/conciliacion_cobros.py`). Estado **🟡**.
- *Contexto:* es el pendiente ⭐ "meter primero" del roadmap; 100% determinista y local → se lleva a verificable **sin** LM Studio ni Google levantados. Reutiliza Expedientes (W), intake y cobros (multiplicador, no obra nueva).
- **Dos piezas, ambas deterministas (el LLM no toca un número):**
  1. **Parser Norma 43** (Cuaderno 43 AEB/CSB), registros 11/22/23/33/88 a posiciones reales, importes a `Decimal` (2 decimales implícitos, sin float), y **cuadre del registro 33** (saldo inicial + abonos − cargos == saldo final, + nº y sumas de apuntes). Si no cuadra **avisa y continúa** (no aborta): deja el aviso para que el humano escale, en vez de dejarlo tirado si su banco exporta un `33` fuera de norma.
  2. **Matcher con semáforo de confianza** (innovación #2 acoplada): casa cada **abono** contra las facturas pendientes con tier explicable — **ALTA** (importe exacto + referencia en el concepto), **MEDIA** (importe exacto + contraparte, o candidato único), **BAJA** (pago parcial con referencia, o agrupado N:1 acotado), **ABSTENCIÓN** (sin candidato o ambigüedad → *no inventa*, escala). Referencias casadas en forma compacta (robusto a separadores).
- **El flywheel (gate S-01):** al aprobar un match, `marcar_cobrada` pone la factura `cobrado` con traza inmutable (`cobro_conciliado`) → el cerebro de `cobros.py` deja de reclamar lo ya pagado. **Humano en el bucle:** el endpoint propone y queda `PENDING_APPROVAL`; solo el humano confirma qué matches aplicar.
- **Alcance honesto (🟡):** código + 27 tests (13 parser + 14 matcher/router), fixture N43 a posiciones reales del estándar. **Para 🟢 falta** un extracto real de un banco de Fernando (anonimizado) parseado y conciliado de punta a punta.
- *Alternativas descartadas:* APScheduler-style libs de conciliación (dependencia + caja negra) · matcher por ratio de importe (cola 5% como 4%) → se casa por **cuadre al céntimo** · que el LLM puntúe el match (viola "el número no lo pone el modelo") → reglas deterministas.
- *Reversible:* sí; módulo nuevo + router nuevo, apenas toca ficheros compartidos (solo monta el router en `main.py`).

**D-15 — Matcher en núcleo blanco (W) con costura `AliasResolver` no-op (flywheel *fenced*).**
- `conciliacion.py` es **Skill W neutro**: no conoce "IVA" ni "303"; consume `Pendiente` (importe/referencia/contraparte). El adaptador dominio→neutro vive en `skill_d_fiscal/conciliacion_cobros.py` (D depende de W, no lo contamina).
- El matcher acepta un `AliasResolver` inyectable — la idea de vanguardia de "aprender alias de pagador de los cobros que el humano confirma" (tabla determinista con procedencia, **sin fine-tuning, sin LLM**). En este slice se inyecta el **resolver no-op**: la costura existe y está testeada (un stub desambigua lo que de otro modo se abstiene), pero **construir el resolver que aprende es un turno aparte** → no infla el slice 🟡.
- *Por qué fenced:* traer la idea sin prometer 🟢 lo que es 🟡. Reversible: el resolver real se enchufa después sin tocar el matcher.

**D-16 — Retirado del repositorio el aparato de proceso "Hilo A/B/C".**
- *Contexto:* un bloque previo montó un proceso dialéctico de dos agentes (A creativo, B crítico) debatiendo en `docs/DIALOGO_HILOS_AB.md` antes de construir, con resultados a `docs/BANDEJA_C.md` y ramas/worktrees `hilo-*`. Fernando pidió **eliminarlo del repositorio**.
- *Hecho:* borrados `docs/DIALOGO_HILOS_AB.md` y `docs/BANDEJA_C.md`; eliminado el worktree `loombit-wt-a-conciliacion` y la rama `hilo-a/conciliacion-n43`. **El trabajo útil que vivía en ese worktree (el parser N43, sin commitear) se rescató a `main` despojado del envoltorio "Hilo A"** (ver D-14), no se perdió.
- *Por qué:* el proceso es decisión del operador humano; el repo guarda producto y decisiones (este doc), no el andamiaje de cómo se debatió. Reversible: el patrón dialéctico puede re-adoptarse fuera del repo sin dejar rastro en él.

*(se irán añadiendo entradas según avance el bloque)*
