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

**D-17 — AliasResolver que aprende IMPLEMENTADO** (`alias_resolver.py` + cableado en `routers/conciliacion.py`). Estado **🟡**. Materializa la costura *fenced* de D-15 (turno aparte, ya construido).
- *Qué es:* el **flywheel determinista** de la conciliación. Un pagador aparece en el extracto con un nombre que no coincide con el de su factura (“TRANSFERENCIA DE J. LOPEZ” ↔ factura de “INMOBILIARIA COSTA SL”); el humano resuelve el puente una vez y el sistema no vuelve a preguntarlo. `AliasStore` aprende `tokens-de-nombre-del-concepto → contraparte` **solo de cobros que el humano confirma**, con procedencia (quién/cuándo) y revocación. Tabla determinista: **sin LLM, sin fine-tuning**.
- *Integración:* al **aprobar** una conciliación, `aprender(concepto, contraparte)` por cada match confirmado; al **proponer**, el resolver se inyecta en el matcher y desambigua. Endpoints nuevos `GET /entidades/{id}/aliases` (auditoría) y `POST …/aliases/{id}/revocar`.
- *Reconciliación con D-09/D-15 (decisión de arquitectura):* la idea original decía “vive en la `EntityProfile`”. Al construir se vio que `EntityProfile`/`AgentMemory` es **global al owner**, no aislada por tenant. Para respetar el aislamiento físico multi-entidad (D-09), el `AliasStore` vive **por entidad** (`runtime/local/entities/<id>/aliases.json`), como los Expedientes → los alias de un cliente de la gestoría no contaminan a otro. La idea (procedencia, confirmación humana) se respeta; cambia el *dónde*.
- *Salvaguardas frente al claim “un alias malo contamina” (estresado en su día):* (1) solo aprende de confirmaciones humanas; (2) el resolver **solo sube a MEDIA**, nunca a ALTA (ALTA exige importe+referencia reales); (3) **ningún match marca cobro sin aprobación humana** → un alias erróneo, en el peor caso, propone una MEDIA que el humano rechaza; (4) **revocable y auditado** (procedencia append-only). Además la **llave excluye tokens con dígitos** (nº de factura/recibo) para no atar el alias a una referencia de un solo uso.
- *Tests:* 9 nuevos (8 unidad del store + flywheel vía `conciliar`, 1 e2e de router: aprende→audita→revoca). Suite **204**. Estado 🟡 (igual que la conciliación: el 🟢 llega con extractos reales repetidos de un mismo pagador).
- *Reversible:* sí; el resolver es inyectable y opcional — quitarlo deja la conciliación funcionando sin memoria.

## Pilot / señal visible

**D-18 — Señal visible PROPIA de Loombit cuando el Pilot controla (halo de marca), no solo el cartel.** Estado **🟢** (verificado EN VIVO en escritorio real, 2026-06-08).
- *Contexto:* al verificar el Pilot, el halo del perímetro que aparecía era el de **Claude/Computer-Use** (naranja), no de Loombit; el Pilot solo pintaba un cartel arriba y, encima, en un teal `#00d2af` **que ni estaba en la paleta de marca**. Confusión de identidad: el usuario no distingue "está pilotando Loombit" de "está observando otra herramienta".
- *Elegido:* `overlay.py` reescrito con **tres capas en colores de marca** (`static/index.html`: violeta `#8b5cf6`/`#a78bfa` → cian `#06b6d4`): (1) **halo de perímetro** degradado pegado al borde del monitor; (2) **halo de cursor** (anillo concéntrico que sigue al ratón vía `GetCursorPos`, deja el cursor real visible en el centro); (3) **cartel** "LOOMBIT PILOTANDO" con píldora de borde violeta. El violeta/cian se distingue inequívocamente del naranja de Claude.
- *Técnica:* tkinter en hilo daemon (como antes), un `Tk()` oculto + un `Toplevel` por capa. Transparencia y *click-through* por Windows: `-transparentcolor` (color-clave `#010101`) + `WS_EX_LAYERED|WS_EX_TRANSPARENT|WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE` vía `SetWindowLongW` sobre `GetAncestor(hwnd, GA_ROOT)`. **Click-through es obligatorio**: el halo no puede capturar ni los clics del propio Pilot ni los del usuario. Reusa `enable_dpi_awareness()` para alinear el espacio de coordenadas con el del Pilot.
- *Alternativas descartadas:* (a) un solo borde sólido sin degradado (menos identidad de marca); (b) glow por `-alpha` global — descartado porque combinar `-alpha` con `-transparentcolor` no es fiable en todas las versiones de Windows (riesgo de oscurecer toda la pantalla si el color-clave deja de funcionar); el degradado finge el glow sin tocar alpha; (c) cubrir todo el escritorio virtual — de momento el marco va en el **monitor primario** (el que el Pilot opera); el anillo de cursor sí cruza monitores.
- *Verificación 🟢 (en vivo, no a ojo):* el cartel + el marco violeta→cian + el anillo siguiendo al cursor se capturaron en una sola pantalla real; el movimiento del cursor por las piezas de producción (`input_control.mouse_move`) se probó determinista (log con coordenadas exactas del círculo); el `pilot_demo.py` literal abrió Google Console. `scripts/verify.py` en verde (black+ruff+pytest, 240 tests, +6 del overlay).
- *Limitación honesta:* probado a escala 100% en monitor primario 5120×1440; en escalado DPI ≠ 100% o monitor secundario con offset negativo el posicionado podría necesitar ajuste (no bloquea; el Pilot opera el primario). El overlay **aún no está cableado al executor del agente** (solo a `pilot_demo.py`); cablearlo es el paso natural cuando el Pilot actúe de verdad.
- *Reversible:* sí; `PilotOverlay` mantiene la API (`start()`/`stop()`, `texto`) y acepta flags `perimetro`/`cursor`/`cartel` para desactivar capas.

**D-19 — El halo se cablea en el `executor`, no en cada llamador.** Estado **🟢** (verificado e2e en escritorio real, 2026-06-08).
- *Elegido:* `execute_sequence` arranca `PilotOverlay` al inicio de un run real (`not dry_run and show_overlay`) y lo para en `finally` (también si un paso falla). Param nuevo `show_overlay=True`. El recibo registra `overlay_shown`. Así **toda** acción del Pilot (endpoint `/loombit/pilot/execute` y, cuando se cablee, el agente) muestra la señal de marca sin tocar cada llamador.
- *Verificación 🟢:* el executor de producción escribió 175 caracteres (multilínea, vía portapapeles) en el Bloc de notas real con el halo activo; recibo `runtime/local/skill_pilot/pilot_16061017.json` (`overlay_shown:true`, `error_halted:false`, 3/3 pasos).
- *Limitación honesta:* el paso `screenshot` del agente captura también el halo (perímetro en los bordes + anillo en el cursor); de momento aceptable (transparencia por color-clave, anillo fino). Si degrada la visión del agente, ocultar el overlay durante `screenshot` es el siguiente refinamiento. `show_overlay=False` lo desactiva por completo.
- *Reversible:* sí; `show_overlay=False` restaura el comportamiento anterior.

## Aprobaciones de correo

**D-20 — Una sola aprobación, y auto-envío del correo cuando el destinatario es inequívoco.** Decisión de Fernando (2026-06-08).
- *Contexto:* el agente pedía aprobación para ejecutar `request_approval` (la propia tool de pedir aprobación) y, además, `gmail_send` ya pausaba → doble puerta + tarjeta circular. Y Fernando: "si te pido el correo, esa es mi aprobación; no me lo preguntes otra vez".
- *Elegido:* (1) **eliminada `request_approval`** — la única puerta es `requires_approval=True` sobre la tool real (gmail_send, calendar_create, run_shell), forzada por el bucle. (2) **gmail_send se AUTO-ENVÍA sin tarjeta cuando el destinatario es inequívoco** (`_destinatario_claro`: lo dio el usuario en su petición, o `contacts_find` lo resolvió con `estado='resuelto'`). Si hay **ambigüedad** (varios candidatos) o no se resuelve, se confirma/ bloquea. La petición del usuario ES la autorización explícita para esa acción concreta.
- *Alcance:* solo correo. `calendar_create` y `run_shell` mantienen la tarjeta de aprobación siempre. El guard anti-invención (F2) sigue intacto: nunca se envía a un destinatario inventado.
- *Matiz con CLAUDE.md:* suaviza "nunca ejecutar efecto externo sin aprobación" → para un efecto que el usuario PIDIÓ con parámetros inequívocos, la petición es la aprobación; lo autónomo/proactivo y lo ambiguo siguen requiriendo confirmación.
- *Evals:* `F2.user_email`, `F2.resolved`, `F4.humano_ok` pasan a esperar **auto-envío**; nuevo `F2.ambiguo` exige confirmación. `+5` tests (`test_email_auto_send.py`).
- *INCIDENTE asociado (honestidad):* al introducir el auto-envío, los evals (que llaman directo a `_execute_tool_call`) **enviaron 2 correos REALES** a `jana@empresa.com` en una corrida de `verify` (OAuth conectado + escrituras on). Corregido: los evals ahora **stubean** `gmail_send` (`_stub_gmail_send`), nunca tocan Gmail real. Lección: una primitiva que ejecuta un efecto externo no se ejercita "de verdad" en CI sin stub.
- *Reversible:* sí; `_destinatario_claro` se puede endurecer (volver a confirmar siempre) en una línea.

## Proactivo / daemon

**D-21 — Daemon proactivo ENCENDIDO + "Vigilar respuestas" cada minuto.** Estado **🟢** (verificado en vivo, 2026-06-08).
- *Elegido:* la routine `Vigilar respuestas` (cron `* * * * *`, ASSISTED) detecta correos sin leer de tus contactos reales (de Enviados, incluye a Jana), redacta borrador como Fernando y marca `[IMPORTANTE]` lo delicado. El `SchedulerDaemon` (hilo de fondo, ya existía) se **activa por `.env`** (`LOOMBIT_OPERATOR_ROUTINES_DAEMON_ENABLED=true`, intervalo 30 s) — NO por defecto en el repo (CI/tests no deben arrancar daemon).
- *Por qué cada minuto:* Fernando quiere flujo rápido; 15 min era demasiado.
- *Verificación 🟢:* el daemon disparó la routine solo al arrancar (recibo `routine_receipts/...`, `status=pending_approval`, output honesto "Sin respuestas nuevas"); el pipeline detectar→redactar→clasificar se probó sobre un correo REAL (David Valentín → borrador humano, IMPORTANTE=No). +2 tests del daemon, +1 del reply-watch.
- *Pendiente (honesto):* el **auto-envío** de la respuesta sigue gateado (queda como borrador `pending_approval` → tu "Aprobar todo"); abrirlo es el siguiente paso cuando esté probado. Memoria del hilo más rica = siguiente.
- *Reversible:* sí; `routines_daemon_enabled=false` en `.env` apaga todo; la routine se puede desactivar o volver a 15 min.

*(se irán añadiendo entradas según avance el bloque)*
