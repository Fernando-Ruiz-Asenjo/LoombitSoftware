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

**D-22 — Panel "Novedades del operador" en la UI (feed del daemon).** Estado 🟢 (endpoint en vivo; UI pendiente de ver con datos reales).
- *Elegido:* `GET /routines/feed` (helper `build_feed`) lee los recibos del daemon, **descarta los ticks vacíos de vigilancia** (ruido) y marca lo importante; el panel lateral los pinta cada 10 s con **distintivo visual por tipo** (📨 respuesta/cian · ⚠ importante/rojo · 💡 mejora/violeta · 📋 brief/azul · pendiente). +2 tests del feed.
- *Reversible:* sí; el panel y el endpoint son aditivos.

## Fase 2 — Morning Brief con datos reales

**D-23 — Store de cuentas a cobrar + el Brief usa vencimientos reales.** Estado 🟢 (verificado en vivo).
- *Elegido:* `cuentas_cobrar.py` (Skill D Cobros): store JSON `runtime/local/cuentas_cobrar.json` con `CuentaCobrar` (cliente, importe, vencimiento, estado) y `pendientes/vencidas/proximas` (reusa `cobros.days_overdue`). Router `routers/cuentas.py` (GET/POST + marcar cobrada). El Brief (`_señales_reales`) suma la señal real: "N cuenta(s) a cobrar VENCIDA(s) por X €" y "N vencen en 7 días".
- *Verificación 🟢:* POST /cuentas (vencida 1250 €) → el brief generó la señal real "1 cuenta(s) a cobrar VENCIDA(s) por 1250 €". +3 tests del store.
- *Pendiente:* alimentar el store desde intake de facturas / conciliación (hoy se añade por API); UI del brief.
- *Reversible:* sí; store y router son aditivos.

## Fase 1 cerrada

**D-24 — Fase 1 (Verdad de conectores) CERRADA.** Estado 🟢 (2026-06-08).
- *Hecho:* con OK explícito de Fernando, creado **1 evento real** en Google Calendar (`create_event`): `event_id` `vmovd103mbb40u7ek3ehb5jsa0`, recibo en `runtime/local/skill_blanca_connector_outbox/`. Junto al envío real de correo ya 🟢 (`message_id` 19ea478e791867b0), la Fase 1 queda cerrada: OAuth real + 1 correo + 1 evento, ambos con recibo.
- *Nota:* efecto externo aprobado por el humano (no autónomo). El evento es de prueba, borrable.

## Fase 4 — La Galaxia (UI humana)

**D-26 — MVP de la Galaxia: el negocio como sistema estelar.** Estado **🟢** (verificado EN VIVO en el servidor real, 2026-06-08). Diseño en `docs/GALAXIA_LOOMBIT.md`.
- *Qué es:* el mapa relacional y vivo del negocio que Google no da (sol=entidad + KPIs; planetas=contactos y cuentas a cobrar; aristas contacto↔cuenta). El chat ejecuta; la Galaxia muestra el estado del mundo.
- *Backend (`galaxia.py` + `routers/galaxia.py`, `GET /galaxia`):* agrega SIN inventar nada lo que ya existe — contactos de Enviados (`home._contactos_de_gmail`, `peso`=frecuencia, `temperatura`=intensidad de trato) + cuentas a cobrar (`cuentas_cobrar`, `estado` semáforo, `dias`=urgencia) + **aristas contacto↔cuenta** por solapamiento de tokens de nombre/dominio (determinista; `_STOP` excluye formas societarias y dominios genéricos para no casar por "SL" ni "gmail"). Sol con KPIs vivos (total a cobrar, vencidas, próximas, aprobaciones pendientes, correos sin leer best-effort). `store` y `contactos` **inyectables** → el test (`test_galaxia.py`, 6) nunca toca Gmail ni el store de producción. Caché TTL 20 s en el router (la UI hace polling; los contactos tocan Gmail).
- *UI (`static/index.html`, canvas propio, sin dependencia):* layout orbital **DETERMINISTA y EDGELESS** (la relación se codifica por POSICIÓN: órbita=categoría, radio=urgencia; **las líneas solo aparecen al hacer foco** en un planeta = su constelación). Gravedad semántica (vencidas → centro), color por semáforo, tamaño por importe/frecuencia, brillo por temperatura, **cinturón de asteroides** para la cola larga de contactos, **command palette ⌘K** (buscar/saltar), hover=tooltip, clic=foco, doble clic=abrir en el chat (reclamar cobro / ver relación — reusa el chat). Marca violeta→cian como el halo del Pilot. Botón 🌌 en la topbar; Esc cierra.
- *Anti-"hairball" (investigado, §10 del diseño):* sin aristas por defecto + focus+context + cinturón. Verificado: con 8 contactos y 4 cuentas, al enfocar un cliente aparece **solo SU** arista; el resto se atenúa. Sin maraña.
- *Verificación 🟢 (en vivo, servidor real, no proceso aparte):* server reiniciado con el `.venv`; `GET /galaxia` devolvió 8 contactos reales (fuente Gmail), y con 4 cuentas de prueba que casaban por nombre/dominio (Amovens, Sandra Gandara, David Valentín + una huérfana "Estudio Marsal SL") se generaron **3 aristas correctas y 0 espurias** (la huérfana sin arista). En la UI: las vencidas (Amovens 2480 €, Estudio Marsal 1150 €) pintaron en rojo hacia el centro; al enfocar "Beatriz C from Amovens" salió una única línea a su factura vencida; palette filtró contacto+cuenta; tooltip con CTA "reclamar cobro". `scripts/verify.py` en verde (black+ruff+pytest, +6 tests del MVP). **Datos de prueba borrados tras la captura** (el store volvió a vacío; nunca se ensució el `/cuentas` real ni se envió nada).
- *Alternativas descartadas:* (a) motor de grafos (Cytoscape/Sigma/D3) — innecesario para una PYME (decenas de entidades) y arriesga la maraña por física; canvas determinista da control de marca y cero dependencia (se deja documentado cuándo subir); (b) pintar todas las aristas a la vez — es justo lo que produce el "hairball"; edgeless por construcción; (c) `temperatura`=recencia real (último contacto) — para el MVP es intensidad de trato (frecuencia normalizada); la recencia con marca de tiempo de los mensajes es el siguiente slice.
- *Siguientes slices:* drag-to-act (reclamar/enviar/agendar arrastrando un planeta sobre otro), latido por novedad (cableado al daemon/feed), zoom semántico galaxia→sistema→planeta, y las órbitas de correo/calendario/documentos (= los 3 gaps de Google).
- *Reversible:* sí; módulo + router + vista aditivos (un router nuevo en `main.py`, un botón y una vista en la UI); nada toca el flujo existente.

**D-27 — Destilar contexto REAL de las conversaciones (sin inventar cifras).** Estado **🟢** (verificado EN VIVO contra el Gmail real de Fernando, 2026-06-08). Petición explícita de Fernando: *"no me pongas cifras inventadas; destila las conversaciones y saca todos los datos que puedas para poner contexto."*
- *Contexto / incidente que lo motiva:* para la demostración 🟢 de la Galaxia (D-26) usé 4 cuentas de PRUEBA con importes inventados (Amovens 2480 €, etc.) y, aunque las borré, **aparecieron en su panel real de cuentas** — justo lo que el repo prohíbe (regla nº1, "no inventar datos"). Corregido y reorientado: en vez de inyectar cifras, Loombit **percibe** las reales de los correos.
- *Elegido:* `galaxia_intel.py` (`distill_contacto`) lee los correos recientes de un contacto (enviados + recibidos, read-only) y extrae **con procedencia**: (a) **importes en €** hallados **literalmente** en el texto, por **regex DETERMINISTA** (`_importes_de` + `normalizar_importe` en formato español punto=miles/coma=decimal) — **el número NUNCA lo pone el LLM** (D-09/D-14); (b) **referencias** de factura/presupuesto (exigen un dígito → no cuela "factura de" ni la palabra "no" como "nº"); (c) **últimos asuntos + fechas + dirección** (enviado/recibido). El **14B solo redacta** una frase de relación a partir de los asuntos reales; jamás aporta cifras. Endpoint **lazy** `GET /galaxia/contacto?email=` (al enfocar un planeta-contacto se abre su "sistema"/lunas = su contexto real). Panel de detalle en la UI con el resumen, los importes (cada uno con su correo de origen + aviso "extraídas literalmente, no inventadas"), los asuntos y un CTA "Abrir relación en el chat".
- *Verificación 🟢 (en vivo, Gmail real):* sobre contactos reales — **Amovens**: resumen "gestiona casos de deuda y reclamos de alquileres" + importe **150,04 € con procedencia** ("AMOVENS Debt case 1088836", 2026-05-14); **Sandra Gandara**: "Factura de Sklum" 90,87 €, "devolución mesa" 70 €; **David Valentín** (sin cifras en sus correos): **0 importes**, solo asuntos reales — confirma que NO inventa cuando no hay dato. Tests deterministas `test_galaxia_intel.py` (6): normalización española, importes solo pegados a €/EUR (no cuela un DNI/teléfono), referencias con dígito. `scripts/verify.py` verde.
- *Datos de prueba de D-26 borrados:* el store `cuentas_cobrar.json` se restauró a vacío (nunca se ensució el `/cuentas` real ni se envió nada). Lección registrada: una demo no inyecta datos falsos en stores de producción — se demuestra con datos reales o en tmp.
- *Siguiente:* convertir un importe real detectado (p.ej. una factura emitida tuya hallada en Enviados) en **cuenta a cobrar candidata** que el humano aprueba (no auto-creada) → cierra el lazo "percibir → proponer → cobrar" con datos reales. Y `temperatura`=recencia real (ya tenemos la fecha del último correo por contacto).
- *Reversible:* sí; módulo + endpoint + panel aditivos.

## Sesión paralela 2026-06-08 (constructor) — desplegado a main y verificado en vivo

> Construido en sesión paralela aislada (worktrees + ramas), fundido a `main` con OK
> explícito de Fernando y reiniciando `:8787`. Cada entrada se verificó EN VIVO.

**D-28 — Operador proactivo y humano: resumen del día en el chat + capacidades en lenguaje humano.** Estado **🟢** (verificado en vivo).
- *Elegido:* (a) `tool_labels.py` traduce el nombre técnico de cada tool a una etiqueta humana; el prompt instruye a presentarse en lenguaje humano, NUNCA con el nombre de la tool. (b) `skill_blanca_calendar_read.eventos_de_hoy` — LECTURA de la agenda (faltaba; el conector solo escribía). (c) `tools/brief.py` (`daily_brief`, `calendar_today`) expone al chat el MISMO cerebro de señales del daemon (`_señales_reales`, ahora con agenda); cifras por código, el LLM solo narra (fallback determinista sin LM Studio). (d) patrón **PROACTIVIDAD** en el prompt: ante peticiones de alto nivel, preparar y proponer un plan ("voy a (1)…(2)… ¿lo hago?") en vez de preguntar; las lecturas se ejecutan directas.
- *Verificación 🟢:* el agente real responde "¿qué herramientas tienes?" con nombres humanos (cero técnicos) y "resumen de hoy" junta agenda + correos + cobros. 19 tests.
- *Reversible:* sí; módulos nuevos + ediciones aditivas en prompt/registry.

**D-29 — Servidor MCP: Loombit como servidor del Model Context Protocol (`Skill A`).** Estado **🟢 protocolo · 🟡 capacidades envueltas**. (Cierra la tendencia #5, antes ⬜.)
- *Elegido:* adaptador PURO sobre el `tool_registry` (`mcp_server.py` = JSON-RPC 2.0; `routers/mcp.py` = transporte Streamable HTTP en `POST /mcp` + `GET /mcp/info`). **Cero dependencias nuevas** (no se añade el SDK `mcp`). Gate server-side (regla nº1): `tools/call` bloquea sin ejecutar toda tool con `requires_approval` o categoría `pilot`/`computer` o `safety_class` sensible — el human-in-the-loop vive en el servidor, no en el cliente. Hallazgo: las `desktop_*` son categoría `pilot` (no `computer`) → incluida explícitamente para no dejar abierto ratón/teclado por MCP.
- *Verificación 🟢:* contra el server real, con el **MCP Inspector oficial** (cliente independiente) + un cliente httpx: handshake + `tools/list` + `tools/call` (lectura ejecuta, `gmail_send` bloqueado). 22 tests. Ver `docs/MCP_SERVER_LOOMBIT.md`.
- *Alternativas descartadas:* SDK `mcp` como server stdio (dep pesada, proceso aparte, peor para reusar el registry); SSE completo (innecesario para un server de solo-tools).
- *Reversible:* sí; 1 módulo + 1 router + 1 línea de montaje.

**D-30 — Fixes del flujo del agente + UI.** Estado **🟢** (verificados en vivo).
- *Aprobar un evento ya no re-pausa en bucle:* causa raíz — `calendar._parse_dt` no aceptaba ISO con `Z`/offset (el modelo emite `2026-06-15T09:00:00+02:00`) → `calendar_create` fallaba y, al aprobar, re-pausaba. Ahora usa `datetime.fromisoformat`.
- *`gmail_search`* usaba el cliente httpx fuera del `with` → "client has been closed"; ahora el bucle va dentro.
- *`daily_brief`/`calendar_today`* toleran args extra del modelo (`**kwargs`).
- *El nombre de la tool ("task_done") no se muestra como texto:* `_strip_tool_artifacts` quita líneas sueltas que sean solo el nombre de una tool.
- *UI:* botón "← Volver al chat" claro en la Galaxia; la barra "Aprobar todo" lista **qué** hay que aprobar (la acción en humano).
- *Reversible:* sí; correcciones acotadas + tests de cada bug.

**D-31 — Galaxia viva + drag-to-act.** Estado **🟢** (verificado en vivo). Continúa D-26/D-27.
- *Galaxia viva:* `galaxia_cache.py` (stale-while-revalidate) → `GET /galaxia` instantáneo + revalidación en background (sin daemon que machaque Gmail); `gxPrewarm()` calienta al cargar la página; badge en 🌌 si hay vencidas/aprobaciones hoy.
- *Drag-to-act:* `galaxia_actions.resolve_drop` mapea de forma DETERMINISTA (qué arrastras: conversación/documento/contacto) × (dónde sueltas: contacto/cuenta/sol) → `DropAction`. `POST /galaxia/act` resuelve y, si hay efecto externo, lo enruta como TAREA al agente (aprobación + firma + proactividad ya existentes; gate intacto). Frontend: dock de chips arrastrables, halo del destino (reusa `GXHover`), fantasma con la acción, toast; doble-clic→chat como vía descubrible (recomendación NN/G). Referencias: React Flow/JsPlumb DropManager, DragApp.
- *Verificación 🟢:* en vivo, 8 contactos reales, pre-carga sirviendo instantánea, `/galaxia/act` correcto. 35 tests galaxia.
- *Pendiente (no en el MVP):* arrastrar documentos (subir fichero, no solo el nombre); persistir las acciones locales (vincular doc↔cuenta, asignar pagador — el resolutor las da, falta el guardado); doble-vía por clic en cada planeta.
- *Reversible:* sí; módulos nuevos + endpoint + vista aditivos.

**D-32 — Frente 2: fiabilidad del agente (anti-flailing + no re-pausa muda).** Estado **🟢** (fundida a main `bd7e306` y en vivo en :8787 tras OK de Fernando; 11 tests). Sale de Investigación 6.
- *No re-pausa en silencio al fallar una aprobación:* cuando `resume()` ejecuta la acción YA APROBADA y falla (p. ej. token caducado), antes el modelo recibía solo el `ERROR` y volvía a sacar la **misma tarjeta** sin explicar por qué ("la ventanita que reaparece"). Ahora se le inyecta un mensaje honesto ("la acción que aprobaste falló: X — corrígelo UNA vez o explícalo con `task_done`, no repitas idéntico"). Generaliza el fix puntual de D-30 (que solo curó el caso `_parse_dt`) a nivel de bucle.
- *Anti-flailing:* si la **misma tool falla 2 veces seguidas** (`_consecutive_tool_errors` ≥ `_TOOL_ERROR_CUT`), el bucle **corta en seco** (`mark_failed` honesto que nombra la tool y la causa) en vez de quemar los 20 pasos martilleando algo roto (tool inexistente, args inválidos, excepción). El 1er fallo solo **avisa** ("esa tool no existe / no encaja; un 2º fallo idéntico me detendrá") para dar una oportunidad de cambiar. Errores intercalados de otras tools no rompen la cuenta; un éxito la resetea. Complementa —no sustituye— el `_inject_loop_hint` existente (que detecta 3 repeticiones SIN error).
- *Por qué cortar:* fricción cero y honestidad (regla DoD) — mejor parar y decir la verdad que simular trabajo gastando pasos. La reflexión (`_aprender_de_fallo`) aprende del corte para tareas futuras.
- *Reversible:* sí; cambio acotado a `loop.py` (+helpers `_is_error_result`/`_error_brief`/`_consecutive_tool_errors`/`_maybe_cut_for_flailing`) + `tests/test_loop_reliability.py`. Sin tocar routers, UI ni estado persistido.

**D-33 — Cobros: el interés de demora deja de abstenerse (tabla oficial BOE).** Estado **🟢** (fundida a main `6fcb25f`, 19 tests). Primer trozo del frente "cobros e2e". Sale de Investigación 6.
- *Problema:* `cobros.late_interest` se abstenía SIEMPRE que no le pasaran un tipo (`rate_required=True`), porque el interés de demora (Ley 3/2004, art. 7) es variable por semestre y el código no inventa cifras legales. Resultado: el operador nunca podía afirmar el interés por su cuenta.
- *Solución:* `tipos_demora.py` — tabla de los tipos **publicados en el BOE** (BCE + 8 puntos), una entrada por semestre **con su referencia de resolución** (1S2023…1S2026), verificada contra el BOE el 2026-06-08. `dunning_plan`, cuando no recibe tipo explícito, resuelve el tipo legal de la tabla y **reparte el interés por tramos** (cada semestre a su tipo vigente). Un tipo explícito sigue teniendo prioridad.
- *Honestidad mantenida (S-02):* no se inventa nada — cada cifra es la oficial y lleva su `boe`. Si algún tramo del periodo cae **fuera de la tabla verificada**, se sigue absteniendo (`rate_required=True`) y nombra el semestre que falta. Invariante testada: `tipo_pct == bce_pct + 8`.
- *Cifras verificadas (tipo · BCE · BOE):* 1S23 10,50·2,50·A-2022-24416 · 2S23 12,00·4,00·A-2023-15221 · 1S24 12,50·4,50·A-2023-26709 · 2S24 12,25·4,25·A-2024-13089 · 1S25 11,15·3,15·A-2024-27618 · 2S25 10,15·2,15·A-2025-13217 · 1S26 10,15·2,15·A-2025-27201.
- *Pendiente del frente (no en este trozo):* `Skill A Banca N43` (lectura de extractos) + lazo factura→cuenta candidata + surfacing en router/UI/telar; mantenimiento de la tabla cuando el Tesoro publique nuevos semestres (futura routine).
- *Reversible:* sí; módulo nuevo `tipos_demora.py` + 7 líneas en `cobros.py` + tests. Sin tocar routers, UI ni estado.

**D-34 — Cobros visibles: el telar muestra el cobro vencido con su desglose legal.** Estado **🟡** (rama `feat/cobros-visible`, +4 tests; espera OK para fundir). Continúa D-33 (segundo trozo del frente). Sale de "hazlo visible".
- *Problema:* el cerebro de cobros (`dunning_plan` + interés legal de D-33) ya calculaba todo, pero **no se veía**: el hilo de cobro del telar solo decía "Cliente · X € VENCIDA" y la UI ni siquiera pintaba el campo `detalle`.
- *Solución (telar):* `_hilo_cobro_vencida` construye el hilo de la factura vencida con su **desglose legal honesto** en `detalle` — días vencidos · saldo · 40 € compensación (art. 8) · interés de demora con su tipo y **cita BOE** · total reclamable —, y modula el **tono** de la acción según la etapa (`escalation_stage`): cordial / firme / formal y, en `via_judicial`, escala a un profesional (no litiga; recuerda el MASC L.O. 1/2025). Degrada con gracia: sin vencimiento → recordatorio básico, sin inventar.
- *Solución (API):* `GET /cuentas` adjunta el `plan` de cobro a cada vencida + nuevo `GET /cuentas/{id}/plan`.
- *Solución (UI):* el panel del telar ahora **renderiza `detalle`** (una línea atenuada bajo el título) — beneficia también a los hilos fiscal y de plazo, que ya lo traían y no se mostraba.
- *Verificación:* 393 tests verdes; `/telar` real (server aislado :8799) devolvió el hilo enriquecido con `BOE-A-2025-27201` y reclamable correcto; `index.html` servido incluye el render. (Screenshot del panel no capturado: el preview-MCP colisiona con el :8787 vivo.)
- *Reversible:* sí; `telar.py` (+helpers `_eur`/`_TONO_ETAPA`/`_hilo_cobro_vencida`) + 2 endpoints en `routers/cuentas.py` + 1 línea de render en `index.html` + tests. Aditivo.

**D-35 — Fix crítico del flujo de chat (responder/aprobar) + rename a «Oficina Loombit».** Estado **🟡** (rama `fix/chat-answer-approve-flow`, +7 tests; espera OK para fundir). Sale de una incidencia reportada por Fernando (captura 2026-06-08): respondió a una pregunta del agente, le re-preguntó lo mismo, y al 2º intento dio `Error al responder: ... status=pending_approval`.
- *Causa raíz (sistémica):* `/answer` y `/approve` lanzaban TODO el trabajo (inyección/ejecución + LLM) en background y devolvían el run en su estado **anterior** (`pending_question`/`pending_approval`). La UI, al no ver `running`, **re-pintaba la misma pregunta/tarjeta** y dejaba de hacer polling; mientras, en background el run avanzaba a `pending_approval` → la 2ª respuesta caía en un estado que ya no era `pending_question` → error 409.
- *Arreglo (backend):* se separa **ACEPTACIÓN** (síncrona, instantánea) de **EJECUCIÓN** (background): `accept_answer`/`accept_approval` inyectan la respuesta o aprueban y dejan el run en `running` ANTES de responder; el LLM continúa en `execute_run`/`_resume_execute`. `answer`/`resume` se mantienen (= accept + execute) para tests/compat.
- *Arreglo (UI):* `answerRun`/`approveRun` ahora **siempre hacen polling** al estado real tras aceptar, en vez de re-pintar el estado devuelto. Sin carrera, sin doble pregunta, sin tarjeta repetida.
- *Rename:* la **Skill D Skill Blanca Administration** se muestra al usuario como **«Oficina Loombit»** (cabecera, avatar `OL`, bienvenida, nombre del remitente en el chat). El nombre **interno/canónico sigue siendo Skill Blanca Administrativo** (código, prompts, manifests, taxonomía Skill C/W/G/D/A/X intactos).
- *Verificación:* 400 tests verdes; 2 tests de regresión **a nivel HTTP** prueban que `/answer` y `/approve` ya devuelven `running` (no el estado viejo); `index.html` servido muestra «Oficina Loombit» y el polling tras responder; el `Skill Blanca` visible desaparece de la UI.
- *Pendiente (lo siguiente):* el **fallo de destilación** del mismo episodio — el `daily_brief` dijo "no hay correos ni vencimientos" cuando Fernando tenía un hilo con David y una reunión el jueves. Eso NO es este fix; es la mejora de percepción/contexto ("destilar mejor que Google"), que se aborda aparte.
- *Reversible:* sí; `loop.py` (split accept/execute) + 6 líneas en `routers/agent.py` + 2 funciones JS en `index.html` + rename de strings de UI + tests.

**D-36 — Destilación: Loombit SÍ sabe de tus reuniones (caso David).** Estado **🟡** (rama `feat/destilacion-reuniones`, +20 tests; espera OK). Cierra el fallo del mismo episodio de Fernando: tenía un hilo con David y una reunión cerrada para el jueves, y el `daily_brief` dijo "no tienes nada". "Destilar y poner contexto mejor que Google".
- *Causa raíz:* la percepción era estrecha — el brief/telar solo miraban (a) la agenda de **HOY** (la reunión era el jueves) y (b) correos **sin leer** de **contactos conocidos** (David no era contacto y el hilo estaba leído). Todo lo demás era invisible.
- *Arreglo (3 frentes):*
  1. **Agenda próxima** (autoritativo): `calendar_read.eventos_proximos(dias=7)` — el telar y el brief muestran las citas de los **próximos días**, no solo hoy. Aquí vive la reunión con David. (Verificado en vivo: el telar real sacó «Reunión con David · lun 15/6 · 09:00» y «con David Valentin · 11:00».)
  2. **Reuniones acordadas en correo** (`percepcion_correo.detectar_reuniones`): destila citas pactadas por email aunque NO estén en el calendario (palabra de cita + día reconocible —día de la semana/fecha/mañana— + hora opcional). Conservador y honesto ("según un correo de X"); dedup contra el calendario y filtra correos que enviaste tú. `_fuente_inbox` ahora puede incluir **leídos** (`incluir_leidos`): una reunión que ya leíste sigue siendo contexto.
  3. **El agente se fundamenta en la bandeja**: nuevo nudge en el prompt — si mencionas "tengo un mail con David", BUSCA con `gmail_search` antes de preguntar, no preguntes lo que puede leer.
- *Honestidad (regla nº1):* cero invención. El calendario es fuente autoritativa; lo de email se marca "según un correo" y se propone agendar (gate de aprobación intacto).
- *Reversible:* sí; módulo nuevo `percepcion_correo.py` + `eventos_proximos` en `calendar_read.py` + hilos en `telar.py` + señales en `routine_executors.py` + 1 nudge en `prompts.py` + tests. Aditivo.

**D-37 — Reuniones inteligentes: destilación LLM + reconciliación calendario×correo (caso David, confianza).** Estado **🟡** (rama `feat/reuniones-inteligentes`, +10 tests; verificado en vivo contra Gmail real; espera OK). Sale de una bronca justificada de Fernando: el telar mostraba la reunión con David el **lunes 15** (del calendario) cuando el correo de David decía **jueves 11, 9:00, Calle Manzana 8, Getafe**. Loombit pedía revisar al usuario — inaceptable: debe ACERTAR.
- *Principio:* Loombit NUNCA pide al usuario que revise su trabajo; tiene que acertar al 100 % (la confianza es la base del negocio). La regex no destila (confundía un timestamp con la hora: "13:57") — **el que destila es el MODELO leyendo el hilo**.
- *Solución — `reuniones_intel.destilar_reuniones`:* el LLM local (Qwen 14B) lee los correos relevantes + el calendario y devuelve la reunión REAL (con, fecha, hora, lugar) reconciliando conflictos con regla clara: **la verdad es lo que las personas acuerdan EXPLÍCITAMENTE en el correo**; si el calendario contradice, manda el correo y se marca el descuadre. JSON validado (descarta fechas pasadas/no ancladas); cae al calendario si el LLM falla (sin la regex); caché TTL 10 min para no llamar al modelo en cada carga.
- *Clave de fiabilidad — buscar al interlocutor:* la ventana de 18 correos NO contenía el hilo (era más viejo). Para cada reunión del calendario se **busca a la contraparte en TODO el Gmail** (`_buscar_correos` → `gmail_search`) y se le dan ESOS correos al modelo. Mejor que "200 correos": trae justo el hilo. Verificado en vivo: el telar pasó de "lunes 15" a **«Reunión con David Valentín · jueves 11/6 · 09:00 · Calle Manzana 8, Getafe»**.
- *Retirada la heurística ruidosa:* eliminados `percepcion_correo.py` + su test (ya no se usan). El telar y el brief usan el destilador LLM.
- *Pendiente (propuesto, siguiente):* (a) flag de conflicto más consistente → acción "Corregir calendario"; (b) **Skill A · Rutas (Maps)**: con la dirección, calcular trayecto + recordatorio de salida ("sal a las 8:15"); (c) pantalla de calendario.
- *Reversible:* sí; módulo nuevo `reuniones_intel.py` + reescritura del bloque de reuniones en `telar.py`/`routine_executors.py` (inyectable `reuniones`) + `_buscar_correos`. Sin tocar el gate de aprobación.

**D-38 — COMPRENSIÓN de la bandeja: cognición fiable (supera a D-37).** Estado **🟡** (rama `feat/reuniones-fiables`, +12 tests; verificado en vivo; espera OK). Fernando, dos exigencias duras: (1) **NO PUEDE HABER FALLOS** — su telar volvió a mostrar "lunes 15" (el LLM en caliente hacía timeout → fallback al calendario crudo, el dato MALO); (2) **no es extraer un dato, es COMPRENDER** el hilo (quién es quién, de qué va, en qué estado) — *"hay que tener cognición"* — y vale para TODOS los casos, no solo David.
- *Motor `comprension.py`:* una pasada del LLM local que ENTIENDE la bandeja (correos + sus hilos buscados en todo el Gmail + calendario) y devuelve asuntos tipados (`reunion|notificacion|plazo|gestion`) con `estado` (confirmada/requiere_accion/…), resumen, lugar, importancia y acción. Reconcilia: la palabra explícita del correo manda sobre el calendario. Lo oficial (Policía/AEAT/banco) siempre importa.
- *FIABILIDAD (cero fallos):* el LLM NO se llama en caliente desde el telar. Se calcula en **segundo plano** (`refrescar_async` + calentado al arrancar en el `lifespan`) y se **persiste** (`runtime/local/comprension_bandeja.json`). El telar **lee la caché** (instantáneo) y, si el LLM falla, **conserva el último resultado bueno** — NUNCA cae al calendario crudo. Si aún no hay nada, muestra "verificando…", jamás un dato sin verificar.
- *Verificado EN VIVO (Gmail real):* la caché comprendió «Reunión con David Valentín · **jueves 11/6 · 09:00** · Calle Manzana 8, Getafe · **confirmada por ambos**» (la fecha del correo, no el lunes 15 del calendario), + «Activar 2FA en GitHub (requiere acción)» + notificaciones. **3 cargas del telar idénticas** (consistencia = caché). Generaliza a tipos distintos, sin trampas.
- *Retirado:* `reuniones_intel.py` (D-37) y el bloque regex de plazos del telar — superados por la comprensión.
- *Pendiente:* afinar la ventana para que entren correos importantes más viejos (la notificación de la Policía del 7-jun no entró esta vez); acción "corregir calendario" cuando hay descuadre; Skill A Rutas (trayecto desde la dirección).
- *Reversible:* sí; módulo nuevo `comprension.py` + bloque del telar/brief que lee la caché (inyectable `asuntos`) + calentado en `main.lifespan`. Sin tocar el gate de aprobación.

**D-39 — Fábrica de Skills (Skill X): auto-autoría GOBERNADA que automejora la plataforma.** Estado **🟡** (rama `feat/skill-fabrica-automejora`, +16 tests; e2e verificado en vivo: el bucle completo registra y ejecuta una tool auto-escrita; espera OK de Fernando para fundir). Fernando pidió algo POTENTE (no "chorradas de 6º nivel"): que Loombit cree **skills y herramientas verdaderamente útiles** y mejore solo. Diseño destilado del estado del arte 2025-26 (DGM, SICA, ADAS, AlphaEvolve, AZR, TextGrad, OpenEvolve, SkillsBench) — ver `RADAR_INNOVACION.md` barrido 4.
- *La tesis:* el **verificador es el foso**. Todo bucle de automejora puntero depende de un evaluador con verdad de tierra; nosotros ya casi lo teníamos (evals + dinero determinista + recibos). La pieza nueva: el **arnés grado-foso** `fabrica/validacion.py` con 7 puertas en cascada (fail-fast): **seguridad AST → contrato → black → ruff → import aislado → su propio eval → sin regresión** (anti-overfit). Una tool sin su eval es una chorrada → puerta en rojo.
- *Seguridad (linchpin):* `fabrica/seguridad.py` = gate estático (allowlist de imports, sin os/subprocess/eval/dunders) + **sandbox dinámico** (builtins recortados + `__import__` seguro) para el `exec`. Patrón 2025 (smolagents/LLM-Sandbox). El código auto-escrito NO se ejecuta hasta vetarse.
- *La línea dura:* evolucionamos el **andamiaje** (código/tools/manifests), **NUNCA los pesos** (SEAL/AZR cruzan esa línea; nosotros no, por brújula).
- *Gate sagrado:* el ciclo `detectar→redactar→validar→proponer` solo **PROPONE** (`PropuestaStore`, estado PENDIENTE). NUNCA auto-aplica. Solo `aprobar` (acción humana) materializa la tool en cuarentena `fabrica/generadas/` (re-verificada) y la registra. Autocarga al arrancar opt-in (`fabrica_autocargar_generadas`, off). Archivo/**linaje** con fitness (DGM/ADAS): los intentos fallidos se guardan como peldaños.
- *Detección útil (no micro-tweaks):* `fabrica/necesidad.py` mina huecos REALES — lo que el agente pidió (`propose_improvement(tool_missing)`) y tools que fallan en bucle. *Autoría:* `fabrica/autoria.py` con el **coder local** (Qwen-Coder) + lazo de auto-reparación (realimenta el fallo del arnés, estilo OpenEvolve).
- *Empírico que respalda el diseño:* SkillsBench — las skills auto-generadas SIN verificación iterativa **empeoran** el sistema (-1,3pp). Justo la razón de hacerlo gobernado: validador = foso + gate humano + local.
- *Cableado:* manifest `skills/fabrica_de_skills.json` (activa el `skill_loader` end-to-end, antes 🟡), router `/fabrica/*`, routine opt-in, eval `FAB.seguridad` en el selfcheck (19/19 verde). Ficheros < 200 líneas, núcleo blanco intacto.
- *Pendiente a 🟢:* correr el ciclo contra el coder real (Qwen-Coder en vivo) y que proponga una tool útil de verdad de las carencias reales; promover de Skill X a estable tras N aprobaciones; sandbox en contenedor como hardening.
- *Reversible:* sí; paquete nuevo `loombit_operator/fabrica/` + router + manifest + 1 flag de config + 1 routine opt-in + 1 eval. No toca el núcleo del agente ni el gate de aprobación.

**D-40 — La Fábrica sube de ambición: motor MULTI-FUENTE (dentro + la Red + meta).** Estado **🟡** (rama `feat/skill-fabrica-automejora`, +6 tests; demo EN VIVO). Fernando: la Fábrica no es para básicos ni fixes de código — debe **apuntar mucho más alto**, abarcar **lo de dentro y lo de fuera en la Red** (competencia, mercado, noticias, nuevas tecnologías, agentes/skills en GitHub) **para traer cosas útiles**, y **mejorar su propio abanico de escenarios**.
- *Generalización:* de "autora de tools" a **motor multi-fuente de oportunidades**. `fabrica/fuentes.py` = registro EXPANDIBLE (`FuenteRegistry`); registrar una fuente nueva es una línea. Modelos: enum `Fuente` (proceso/cognición/**red**/usuario/meta) + `TipoNecesidad.MEJORA`.
- *Lo de FUERA (`fabrica/red.py`):* un **radar de inteligencia** con APIs públicas gratis vía httpx — **GitHub** (qué agentes/skills construyen los demás), **HackerNews** (mercado/competencia/noticias), **arXiv** (técnicas), **BOE** (normativa, uno más). Cada hallazgo CON cita (URL). Verificado en vivo: trajo `agenticSeek` (26k★, "Fully Local Manus"), `mcp-use`, "AI forensic accounting" (competidor), YC/n8n.
- *Meta (`fabrica/meta.py`):* la Fábrica revisa su cobertura/linaje y **propone ampliar su propio abanico** (fuente seca → revisarla; muchos fallos de tool → abrir auto-evolución de cognición; nuevo canal de radar). Auto-mejora del motor de auto-mejora, con gate.
- *Hallazgos (`fabrica/oportunidades.py`):* lo de la Red/meta no es código que se redacta — es inteligencia citada que se persiste (`runtime/local/oportunidades.json`, con dedup) para tu revisión/roadmap. Solo lo tipo TOOL pasa por el arnés. Router `/fabrica/oportunidades`.
- *Honestidad:* el coder local (7B) aporta lógica; el arnés normaliza estilo (black+ruff-fix) y decide. Los tres ejes que pediste (evolucionar cognición · capacidades del foso · skills completas) son objetivos del abanico; la auto-autoría de MEJORAS de skill (no solo tools) es el siguiente peldaño.
- *Reversible:* sí; aditivo (`fuentes/red/meta/oportunidades.py` + ciclo multi-fuente + 1 endpoint). El backbone seguro (arnés+gate+linaje) intacto.

**D-41 — Automejora INTERNA: la Fábrica mira su propio código en uso, lo marca y propone reparación.** Estado **🟡** (rama `feat/skill-fabrica-automejora`, +4 tests; demo EN VIVO contra el coder). Fernando: además del exterior, una herramienta de automejora interna para **mejorar nuestro código ya programado y en uso, marcar y reparar errores, y mejorar los prompts**. Es la fuente COGNICION del abanico.
- *Marcar (`fabrica/interno.py`, determinista):* escanea el código en uso y señala lo real y de alto valor (sin ruido de estilo): **posibles bugs** (ruff bugbear `--select=B`), **TODO/FIXME**, **ficheros >400 líneas** (regla de la brújula), **prompts del sistema** auto-evolucionables (GEPA), y **huecos sin eval**. Verificado en vivo: marcó 2 bugs B008 (incl. mi propio router), 8 prompts, y 8 ficheros sobre 400 líneas (`agent/memory.py` 952, `agent/loop.py` 766, `telar.py` 639…). Registrado como fuente COGNICION → el ciclo lo surfacea en `/fabrica/oportunidades`.
- *Reparar (`fabrica/reparar.py`, gate sagrado):* el coder propone una versión mejorada del fichero; se valida y se devuelve un **DIFF** como propuesta. **NUNCA escribe el fichero** (la validación de comportamiento ocurre al aplicar en rama). Endpoint `POST /fabrica/reparar`. Vale para código y prompts.
- *Hallazgo de seguridad (importante):* la demo en vivo destapó que la **validación estática (parse+black+ruff) NO basta** para reparar código en uso — el 7B, al "mejorar el docstring", **borró medio módulo** y pasó parse/black/ruff. Se añadió un **guard de API en uso** (AST, sin ejecutar): un parche no puede **eliminar símbolos públicos** existentes. Re-verificado en vivo: el mismo parche destructivo ahora se **rechaza**. La validación de comportamiento por tests (worktree aislado) es el siguiente peldaño.
- *Reversible:* sí; aditivo (`interno.py` + `reparar.py` + fuente COGNICION + 1 endpoint). No escribe en el código en uso; el núcleo del agente intacto.

**D-42 — El chat de la Fábrica gana COGNICIÓN (no enrutado por regex).** Estado **🟢** (rama `feat/fabrica-cognicion-gepa`, +14 tests; verificado EN VIVO en :8787). Brújula: «la regex no destila, el LLM leyendo el hilo sí». El chat enrutaba por palabras clave y **ni siquiera pasaba el LLM** (`responder(mensaje)` con `llm=None`).
- *Cognición:* el 14B ENTIENDE la intención aunque no se use la palabra exacta (p. ej. «echa un ojo a lo que hace Holded» → radar) y extrae los slots (query/descripción/fichero). `fabrica/chat.py` reescrito con handlers por acción + narración conversacional (`charla`/`explicar`) **fundamentada en el estado real** de la Fábrica (no inventa cifras: las de listado las pone el código).
- *Fast-path (UX + robustez):* un comando OBVIO se enruta SIN llamar al LLM (instantáneo, no depende de LM Studio: «salud del código» responde en **0,6 s**). El 14B solo entra a ENTENDER cuando el mensaje no es un comando claro. Red de seguridad determinista si el modelo cae → el chat nunca se queda mudo.
- *Multi-turno:* el endpoint acepta `historial`; la UI manda los últimos 8 mensajes como contexto.
- *Reversible:* sí; reescritura de `fabrica/chat.py` (misma API pública `responder`) + endpoint que pasa `historial`. No toca el núcleo del agente.

**D-43 — GEPA REAL: optimización del prompt del agente VALIDADA con evals (no "marcar").** Estado **🟢** (rama `feat/fabrica-cognicion-gepa`, +13 tests; **recibo en vivo**). El peldaño que faltaba de la Fábrica: auto-evolución de cognición de verdad (Reflective Prompt Evolution, estilo GEPA), no solo señalar el prompt.
- *Bucle (`fabrica/gepa.py`):* (1) puntúa el prompt ACTUAL contra un **eval de COMPORTAMIENTO** derivado de la taxonomía F1-F8 — 5 escenarios prompt-sensibles, una vuelta del modelo con tools (¿redacta el correo?, ¿no inventa el destinatario?, ¿es proactivo?, ¿busca en la bandeja?, ¿agenda?); (2) **reflexiona** sobre los fallos + lecciones de trazas y reescribe la plantilla (14B); (3) **re-puntúa** el candidato; (4) si mejora **SIN regresión** y conserva los anclajes de seguridad, emite PROPUESTA con su **diff + scores**.
- *Gate de seguridad sobre la propia salida de GEPA:* el candidato se rechaza si pierde anclajes (`task_done`/`gmail_send`/`ask_user`/aprobación/los marcadores `{...}`) o no renderiza. **NUNCA escribe el prompt**: devuelve un diff para aplicar en rama (igual que `reparar`; andamiaje, no pesos).
- *Recibo en vivo (2026-06-09):* `POST /fabrica/gepa` corrió contra el 14B real en 37,5 s → el prompt actual puntúa **80 % (4/5)**; falla `agenda_evento` (el modelo no emitió la tool); GEPA reflexionó y **honestamente NO propuso cambio** (no halló mejora sin regresión: «mejor no tocar que empeorar»). El mecanismo end-to-end queda verificado; encontrar mejora depende del modelo/intentos.
- *Reversible:* sí; módulo nuevo `fabrica/gepa.py` + 2 endpoints (`POST/GET /fabrica/gepa`). No toca `agent/prompts.py` (solo propone).

**D-44 — UX de la Sala de la Fábrica: ver el código antes de aprobar + panel GEPA + chat vivo.** Estado **🟢** (verificado EN VIVO; sin tests propios = UI). El gate humano debe **ver lo que aprueba**.
- *Visor de propuesta:* «👁 Ver y aprobar» abre un modal con el **código en cuarentena**, su eval y el **arnés de 7 puertas** (verde/rojo por puerta); Aprobar/Descartar desde ahí. Antes se aprobaba a ciegas.
- *Panel GEPA:* botón 🧬 en la barra → corre GEPA y muestra **scores antes→después** + el **diff coloreado** (verde/rojo) en el modal, con el recordatorio de que no escribe nada.
- *Chat más cálido:* chips de arranque (Estado · Salud · 🧬 Optimiza el prompt · Monetización · ¿Qué eres?), indicador de escritura, markdown ligero, e historial multi-turno. Verificado en vivo: modal+diff+chips+columnas con datos reales, **0 errores de consola**.
- *Reversible:* sí; aditivo en `static/index.html` (CSS + modal + JS). 

**D-45 — P1 · RAG / índice semántico LOCAL (el fundamento que pedía el roadmap).** Estado **🟢** (rama `feat/fabrica-cognicion-gepa`, +8 tests; **recibo en vivo**). Un administrativo recuerda por SENTIDO, no por palabra exacta.
- *Índice (`rag.py`, Skill W):* vectoriza el histórico con el modelo de embeddings LOCAL (`text-embedding-nomic-embed-text-v1.5` vía LM Studio) y busca por similitud coseno (pura, sin numpy). Persistido en `runtime/local/rag_index.json`. `embed_fn` inyectable (tests deterministas sin modelo). Corpus DE DENTRO: ejecuciones, lecciones, empresas, contactos, procedimientos (dedup por id estable, idempotente).
- *Al servicio del agente:* tool `memory_search` (pasiva) — el agente recuerda algo parecido que ya pasó, por significado. Etiqueta humana «🧠 Recordar lo ya hecho» + grupo por intención (histórico/recuerda/parecido…). Endpoints `/rag/reindexar`, `/rag/buscar`, `/rag/estado`.
- *Recibo en vivo (2026-06-09):* `/rag/reindexar` indexó **54 documentos a 768 dims** (history 34 · lesson 7 · entity 1 · contact 4 · procedure 8) en 10 s; `/rag/buscar?q=correo a un cliente` devolvió por SIGNIFICADO la lección «NUNCA inventes el email del destinatario» (score 0,77) en 2,4 s. Embeddings locales reales funcionando.
- *Reversible:* sí; módulo nuevo `rag.py` + router `/rag/*` + 1 tool + `LLMClient.embed` + 2 settings. Local-first: los vectores no salen de la máquina.

**D-46 — Fase 5 cerrada: daemon de APRENDIZAJE PROACTIVO (consolidación de memoria).** Estado **🟢**
(rama `feat/fabrica-cognicion-gepa-rag`, +5 tests). El bucle ya aprende POR-RUN (Reflexion en fallos +
contactos + historial + procedimientos); faltaba el lazo PROGRAMADO que consolida en 2º plano.
- *Diseño (`aprendizaje.py` + routine `Aprendizaje`, output_kind="aprendizaje", PASSIVE, 4:30):* su
  valor único es **mantener fresco el índice semántico (RAG)** para que `memory_search` recupere lo
  último por significado. `consolidar()` reindexa (verificado en vivo antes: 54 docs @ 768d) y, OPT-IN
  (`max_runs>0`), destila lecciones de los runs recientes (Reflexion proactiva, idempotente por texto).
- *Robustez (lección dura):* el primer diseño reflexionaba sobre 12 runs → **190 s y timeout** del
  scheduler. Una tarea de fondo NO puede monopolizar el 14B ni reportar «failed». Arreglo: el daemon va
  **reindex-only por defecto** (`max_runs=0`, no toca el 14B → rápido y fiable); la reflexión es opt-in
  para hardware más rápido/Jetson. Best-effort: cada parte informa, `consolidar` nunca lanza.
- *Reversible:* sí; módulo nuevo `aprendizaje.py` + 1 routine + dispatch. Daemon global opt-in
  (`routines_daemon_enabled=False`). Mejora futura: grafo temporal (#6).

**D-47 — Fricción CERO en el chat: la cortesía no gasta el agente.** Estado **🟢** (rama
`feat/fabrica-cognicion-gepa-rag`, +34 tests; **recibo en vivo**). Captura de Fernando: «hola» se
quedaba en «Procesando…». Diagnóstico: **todo** mensaje —hasta un saludo— pasaba por el bucle ReAct
del 14B (prompt grande + tools + memoria) → **85 s** medidos para responder «hola».
- *Arreglo (`agent/smalltalk.py`, en `routers/agent.py`):* una cortesía PURA (saludo/gracias/despedida)
  se responde AL INSTANTE, de forma determinista, sin tocar el modelo. **Recibo: 85 s → ~0,4 s**
  («hola» 408 ms, «gracias» 273 ms). CONSERVADOR: solo casa frases de cortesía cortas y exactas; con
  cifras, «@», «/» o cualquier intención real → None → va al agente (verificado: «resúmeme el día» NO
  se intercepta). Mejor dejar pasar una cortesía rara que comerse una tarea.
- *Causa raíz del incidente concreto:* además, una corrida manual de la routine `Aprendizaje` (pesada,
  pre-D-46) había saturado LM Studio (`--parallel 1`) → el «hola» quedó en cola. Lo arregla D-46
  (reindex-only) + no lanzar jobs LLM pesados durante el uso interactivo.
- *Reversible:* sí; módulo nuevo `agent/smalltalk.py` + 6 líneas en el router. No cambia el agente para
  tareas reales.

*(se irán añadiendo entradas según avance el bloque)*
