# Estado y roadmap de Loombit — ¿cómo vamos?

> Documento vivo. Honestidad obligatoria (`DEFINITION_OF_DONE.md`): 🟢 = funciona
> contra el servicio/realidad con recibo; 🟡 = código completo + tests (sin piloto
> real); 🟠 = parcial; ⬜ = pendiente; 🔴 = bloqueado.
> Actualizado: 2026-06-14.

## ⏱️ 2026-06-14 (tarde) — Aterrizaje del NORTE (caja+agente local+adaptativo) + EL MURO (equipo de defensa)

> Investigación de innovación (5 vueltas del harness `deep-research`, verificación adversarial a 3 votos)
> aterrizada en la constitución. PR de integración: **#61** (rebasado sobre `main`, que ya trae #58 + #60).

- **🟢 NORTE ampliado — "LA CAJA" (D-100):** Loombit = caja donde escribes cualquier tarea → *dentro* =
  skill rápida determinista, *fuera* = **agente autónomo de computer-use LOCAL** (fallthrough); interfaz
  **ADAPTATIVA**. Autonomía en local/lectura/cómputo; gate humano SOLO en el efecto externo. En `CLAUDE.md`
  + `BRUJULA.md` §NORTE. Investigación destilada en `DESTILADO_STUFF_CAJA_AGENTE_LOOMBIT_2026-06-14.md`.
- **🟢 Ley §SEG-8 — la UI generada NO es camino de confianza (D-101):** Vuelta 5 (UI generativa/adaptativa
  2026) verificada 3-0 (patrón tldraw). El LLM propone la pantalla como intents sobre un **vocabulario
  CERRADO de componentes**; código determinista valida/renderiza; el efecto pasa por el gate. Blindada en
  `BRUJULA.md` §SEG-8 + tabla Parte IV + el prompt del operador local (`agent/prompts.py`).
- **🟢 EL MURO — los auditores/gates ahora son UN EQUIPO (D-102):** carta en `docs/EL_MURO.md`. Capas
  separadas: El Muro defiende el NORTE y la Brújula sin *ser* ninguno (Separación de Autoridades). Lema:
  *el LLM propone, El Muro dispone*. Miembros: gate `verify.py` + 8 auditorías + mutación + test en vivo +
  candados + CI + CODEOWNERS + cadena + recibos + **K2** (valla FS, #60) + el **centinela**.
- **🟢 Centinela always-on (`el_muro_centinela.py`):** Routine PASSIVE 24/7 que vigila la salud de El Muro
  (radar fresco ≤45 d + cadena íntegra) y deja recibo; `salud_muro()` pura, arnés `test_el_muro_centinela.py`.
  Candados endurecidos. Gate local verde (cobertura 79.4%).
- **🟢 Miembros dormidos despertados:** `core.hooksPath`→`.githooks` (el gate local vuelve a correr en cada
  commit) + `mypy` instalado (faltaba y degradaba el type-check en silencio).
- **🟢 Método guardado:** `docs/METODO_DEEP_RESEARCH_VUELTAS.md` (harness 3-votos + filtro duro + plantilla
  reutilizable) + recibos de conducta D-70.
- **Ya en `main` esta sesión:** **#58** descompuso `loop.py` (1433→178) + D-96 cuarentena CaMeL EN VIVO
  (D-99) → **D-96 ya NO está bloqueado**; **#60 = K2** valla de autoprotección del sistema de ficheros.
- **Pendiente:** V1 (GTM fiscal-España, sin cifras verificadas — *pendiente*) · V6 (malleable software +
  render server-driven sin JS: AG-UI / MCP-UI / shadcn-registry) · grafo temporal de memoria 🔴 aún detrás
  de **decomponer `memory.py`** (964 líneas, congelado por el ratchet).

## ⏱️ 2026-06-14 — Cable de sesiones · GEPA Pareto cableado · el ratchet CONGELÓ el núcleo

- **🟢 EL CABLE (PR #54)** — puente git nube↔PC (`scripts/bridge_*.py` + `docs/CABLE_SESIONES.md`),
  **verificado e2e EN VIVO en Windows** (round-trip `Get-Date` → `approved=True exit=0`). Corre en 2º plano
  con gate `allowlist`. Pendiente: tu review de codeowner para fundir.
- **🟢 D-98 — GEPA frontera de Pareto CABLEADA (PR #55)** — completa el D-97 🟠: `optimizar_prompt` busca
  sobre la **frontera de no-dominados** (no «mejor por media»); padre a expandir y propuesta final salen de
  la frontera. Extraído `fabrica/gepa_escenarios.py`; `gepa.py` **416→278** (fuera de deuda). Gate canónico
  (normal) verde + 24 goldens. Pendiente: tu review de codeowner.
- **🧱 HALLAZGO IMPORTANTE — el ratchet de tamaño ha CONGELADO los ficheros núcleo.** `auditoria_brujula.py`
  pone el muro ROJO si TOCAS cualquier `loombit_operator/*.py` **> 400 líneas** (sin excepción de deuda). Como
  `loop.py`=**1433** y `memory.py`=**964**, **no se pueden editar hasta decomponerlos a <400**. Por tanto:
  - **D-96 (cuarentena CaMeL EN VIVO)** ✅ **RESUELTO por #58** (2026-06-14): `loop.py` descompuesto
    (1433→178) y la cuarentena cableada en vivo. *(Esta nota queda como histórico; ya no está bloqueado.)*
  - **Grafo temporal de memoria (#1, «la joya»)** 🔴 bloqueado igual detrás de **decomponer `memory.py`**.
  - **Navegador (D-93/D-94)** 🟠 — núcleo gobernado + driving 🟡; **registrar la tool + verificar EN VIVO**
    sigue bloqueado en TUS recursos (`pip install playwright` + web real) y en no-mentir (no se expone al 14B
    sin recibo en vivo).
- **deep-research** — la barrida amplia (Google/OpenAI-Operator/Cursor internals) sigue pendiente; se atascó
  a ~2h20 el 13-jun (reanudable).

## Foto global
- **Repo**: limpio y profesional, historial sano, LICENSE propietaria. `origin/main` con el **gobierno
  (Brújula v2) en marcha** (PRs #12/#13/#14) + gate alineado con CI (#15).
- **CI / gate**: verde (black + ruff `.` + **805 pytest** + evals F1-F8).
- **«Loombit Decide»**: dirección + plan (#16, D-57/D-59) y **LD-0…LD-3 fundidos en `main`** 🟡 (#17,
  D-60…D-63) — motor de decisiones + UI generativa gobernada + rebanada del cobro + autonomía graduada.
- **NORTE reencuadrado (D-64):** visión amplia (compañero universal) + cuña admin/España como foco.

---

## 🏛️ Gobierno (Brújula v2) — estado real

> **Criterio "sin fallos" (medible, no aspiracional; reconcilia con la regla nº1 "nunca 100%"):**
> un mecanismo está **🟢 sin fallos** solo si: (1) **recibo real** (DoD) · (2) **golden en el gate**
> (rojo→verde, no tautológico) · (3) **verificado EN VIVO** con el 14B · (4) **cero regresión** (gate
> entero verde). La **seguridad operativa "sin fallos"** = un **corpus de ataque definido pasa a 0** +
> **defensa medida** + **residuo declarado** (qué NO cubre y qué lo frena aguas abajo). Nunca "es seguro".

| § | Mecanismo | Estado | Recibo | Fallos abiertos |
|---|---|---|---|---|
| §META-4 | Estado fuera de la constitución | ✅ | `CLAUDE.md` saneado → `ESTADO_Y_ROADMAP.md` (PR #12) | 0 |
| El Muro | equipo único de defensa (centinela always-on + K2 valla FS + candados) | 🟢 propuesto (#61) | `docs/EL_MURO.md` + `el_muro_centinela.py` + `test_el_muro_centinela.py`; gate local verde | residuo: centinela espera CI; render server-driven (V6) pendiente |
| §SEG-8 | la UI generada NO es camino de confianza | 🟢 norma | `BRUJULA.md` §SEG-8 + tabla Parte IV + `agent/prompts.py` + golden `test_agent_prompts.py` | golden de UI generada (runtime) por construir |
| K2 | valla de autoprotección del sistema de ficheros | 🟢 (#60) | `sandbox/policy.py` + golden `test_valla_autoproteccion.py` | hardening en contenedor (futuro) |
| §SEG-2 | datos≠órdenes (neutraliza inyección en lo leído) | 🟢 | golden `test_seg_inyeccion.py` 7 (rojo→verde) + live [2] del plano (PR #13) | 0 en corpus; **residuo:** lenguaje natural sin marcadores (lo frenan gate de efecto + `_recipiente_resuelto`); `resume` no blindado |
| §GOB-1 | Capability Policy Plane (autoridad única) | 🟢 | golden `test_gob1_authority_plane.py` 10 + ~717 tests A TRAVÉS del plano + **live 3/3** `live_gob1_receipt.py` (PR #14) | 0 en corpus; **residuo:** predicados aún en `loop.py` (migración pendiente) |
| §GOB-2 | gate canónico + compila la tabla + prohibir `--no-verify` | 🟠→🟢 parcial | **gate canónico único `verify.py --strict` = hook ⊆ CI, sin drift** (D-65) | falta `validate_brujula.py` (compilar tabla Parte IV) + prohibición efectiva de `--no-verify` |
| §GOB-3/4 | dientes del arnés (mutación) + auditorías en el gate de merge | 🟠 | **mutación 8/8 + auditoría 449 + cobro/fuzz 10k casos, todo en CI** (D-65) | falta independencia real (auditor≠constructor) + held-out |
| §META-1/2/3/5 · §14B · §DATOS · §CONC · §EST | resto del gobierno | ⬜ | — | sin construir (orden P0→P4, ver `BRUJULA.md` Parte V) |

**Honesto:** el **P0 cimiento** (§META-4 + §SEG-2 + §GOB-1) está 🟢 en `main`, cada uno a 0 fallos en su
corpus con residuo declarado. El **gobierno completo NO está al 100%** (eso sería teatro): P1-P4 pendientes.

---

## 🧭 Dirección «Loombit Decide» — plan en el roadmap (D-57 visión · D-59 plan)

> Visión: `VISION_LOOMBIT_DECIDE.md` · Plan detallado (hitos, DoD, orden): **`PLAN_LOOMBIT_DECIDE.md`**.
> **Estado: LD-0…LD-3 construidos y fundidos (🟡, #17); LD-4/LD-5 pendientes.** Reenmarca la UX/autonomía
> SOBRE el cerebro + gobierno que ya existen; **no sustituye** el camino crítico (INTAKE F-5 → cobros e2e),
> lo sube un piso. Backend con **recibo EN VIVO**; falta 14B + navegador + cablear el renderer a la Tela.

| Hito | Qué | Construye sobre (código real) | Depende de | Fase | Estado |
|---|---|---|---|---|---|
| **LD-0** | `Decision` de 1ª clase + **cola** | `policy/authority_plane.py` + `PENDING_APPROVAL` + `telar.py` | — (ya construible) | 3/4 | 🟡 (D-60, PR #17) |
| **LD-1** | **UI generativa GOBERNADA**: vocabulario cerrado + validador + renderer JS | `static/` (Tela/galaxia) | LD-0 | 4 | 🟡 (D-60, PR #17) — falta cablear el renderer a la Tela |
| **LD-2** | Rebanada vertical: `decision_card` de **un cobro** | `cobros.py` + `comprension.py` + LD-0/LD-1 | **INTAKE F-5** (datos reales) | 3↔4 | 🟡 (D-61, PR #17) — backend con recibo EN VIVO; falta 14B+navegador |
| **LD-3** | Agente reactivo→autónomo, **niveles graduados** | `routers/routines.py` + `scheduler.py` | LD-0 | 5 | 🟡 (D-63, PR #17) — `actua_solo` no construido (§14B) |
| **LD-4** | Correo: contexto→**triaje autónomo** (el usuario no toca el correo) | `gmail_search` + §SEG-2 + LD-0/1 | LD-0/1 | 2/6 | ⬜ |
| **LD-5** | Generalizar el vocabulario (303, conciliación, agenda…) | skills D + LD-1 | LD-1 maduro | 4+ | ⬜ |

**Orden:** **LD-0 + LD-1 primero** (cimiento, no dependen de datos) ∥ **INTAKE F-5** (🔴 desbloqueo de datos)
→ **LD-2** (demo del lazo entero) → **LD-3/LD-4** (autonomía) → **LD-5** (generalizar). Detalle y DoD por hito
en `PLAN_LOOMBIT_DECIDE.md`. **Regla nº1:** ningún hito 🟢 sin recibo en vivo + golden + cero regresión.

---

## ★ DÓNDE ESTAMOS Y HACIA DÓNDE VAMOS (2026-06-09 — sesión «UX TOP»)

**El NORTE:** la **visión** es Loombit = **compañero de trabajo necesario para cualquier actividad —laboral o
no— ante un ordenador, tablet o teléfono** (núcleo blanco + skills; ver `BRUJULA.md` §NORTE, D-64). La **cuña
activa** (estrategia para llegar, no el techo) es el **operador administrativo del autónomo/PYME español**.
Foso: **local · comprensión profunda · adaptativo** (+ español en la cuña). La meta no es «otro dashboard
bonito»: que la persona lo sienta **indispensable** — que al abrir vea su día ya resuelto y cerrarlo dé vértigo.

**Qué se hizo esta sesión (UX a TOP, todo 🟢 verificado EN VIVO en el Chrome real):** auditoría profunda
(`AUDITORIA_UX_2026-06-09.md`) + Ola 1 (cognición en la tarjeta, telar instantáneo con caché, doble saludo
muerto, aprobación en columna con borrador visible) + Ola 2 (galaxia real, **chat copiloto** ejecutable,
conectar Google, acciones que ejecutan de verdad) + arreglos de pruebas DURAS (jerga de tools fuera,
volcados de código→fallback honesto) + visual (usa el ancho, jerarquía, porqué visible) + **todo botón con
función** (⚙️ Ajustes real, «Editar»). Detalle y prioridad fusionada en `AUDITORIA_UX_2026-06-09.md`.

**El diagnóstico honesto (por qué AÚN no es indispensable):** la **piel** ya está bien; lo que falla es la
**sustancia con datos**. Probando a fondo: `/cuentas` vacío, galaxia 0 €, sin facturas → **cobros y 303 no
tienen con qué trabajar** (F-5), y sin datos el agente **improvisa** en vez de guiar (F-6). Ese es el
verdadero techo, no el maquillaje.

**HACIA DÓNDE VAMOS (orden por valor real, no por cosmética):**
1. **🔴 Llenar la plataforma de datos = INTAKE de facturas** (subir carpeta / leer del correo con el
   VL local → líneas de 303 + cuentas a cobrar). Desbloquea cobros, 303 y la galaxia de golpe. **Es el
   mayor salto de experiencia pendiente.**
2. **🔴 Abstención honesta con salida** (F-6): sin datos, Loombit dice «no encuentro tus facturas; conéctalas»
   y guía — nunca promete-y-no-hace ni escupe basura.
3. **★ Fase 3 · bucle e2e de COBROS con recibo 🟢 ×5** (camino crítico, cierra la cuña 1): comprensión
   (impago)→cobro vencido (desglose BOE)→borrador→envío con gate→conciliación. El cerebro ya está; con el
   intake llenándolo, este lazo por fin tiene materia.
4. **UX a paridad → promover la Tela nueva a `/`** (S4 chat ✅; faltan sidebar/historial/settings en la Tela)
   + Ola 3 (pasos del agente en vivo, polling→eventos) + Ola 4 (⌘K, motion, responsive) + **Fábrica a
   backstage** (no exponer el código interno al usuario, V-7).
5. **Foso/seguridad (red-team):** frontera data≠órdenes, IBAN-swap, Origin/CSRF en `:8787`//mcp, gate de
   lecciones. **Fábrica polish:** F5 Super Loop+Ralph, F7 auto-GEPA.
6. **Aceptación final:** simulacro e2e haciéndome pasar por Fernando, ejercitando TODO y arreglando fallos
   (correos solo a su dirección; borrar lo publicado).

**Bloqueado en recursos de Fernando (no en código):** fiscal a 🟢 = certificado AEAT (VeriFactu) + N43 real;
VL a 🟢 = un escaneado real; «día gestionado»/Rutas = clave de API de mapas; Jetson = hardware.

---

## Lo construido (2026-06-09 — Fábrica al 100 % + P1 RAG)
Ver `DECISIONES.md` D-42…D-45 (todo 🟢 verificado EN VIVO en :8787).
- **Chat de la Fábrica con COGNICIÓN** (D-42): el 14B entiende la intención (no regex) y conversa
  con el estado real; **fast-path** determinista para comandos obvios (0,6 s, sin LLM) + multi-turno.
- **GEPA REAL** (D-43): optimiza el prompt del agente reflexionando sobre trazas y **validándolo con
  un eval de comportamiento F1-F8**; propone diff+scores con gate, nunca escribe. Recibo: el prompt
  actual puntúa 80 % (4/5) contra el 14B real; GEPA se abstiene honestamente si no mejora sin regresión.
- **UX de la Sala** (D-44): visor del código + arnés de la propuesta antes de aprobar, panel GEPA con
  diff coloreado, chat con chips/escritura/markdown. 0 errores de consola.
- **P1 · RAG / índice semántico LOCAL** (D-45): embeddings nomic locales; reindexó 54 docs reales a
  768 dims; búsqueda por significado; tool `memory_search` para el agente. **Fundamento del roadmap P1.**
- **Fase 5 cerrada** (D-46): daemon de **aprendizaje proactivo** (`aprendizaje.py` + routine
  `Aprendizaje`) que consolida la memoria en 2º plano: reindexa el RAG + destila lecciones de los runs
  recientes (Reflexion proactiva, idempotente). Acotado a 3 runs para no monopolizar el modelo local.
- **Fricción cero en el chat** (D-47): un "hola"/"gracias" ya NO pasa por el loop ReAct del 14B —
  responde al instante (**85 s → ~0,4 s** medido) con `agent/smalltalk.py`. Conservador: solo cortesías
  puras; cualquier tarea real va al agente igual.
- **Arquitectura**: núcleo blanco + skills + ReAct; FastAPI en `:8787`; LLM local (instructor **Qwen2.5-14B**, coder 7B, vía LM Studio). Ver `MODELOS_LOOMBIT.md`.

## Avance por fases

| Fase | Objetivo | Estado | Qué falta para cerrarla |
|---|---|---|---|
| 0 · Fundación limpia | Repo, CI, estructura | ✅ Cerrada | — |
| 1 · Verdad de conectores | OAuth real Google + 1 correo + 1 evento reales | ✅ **Cerrada (2026-06-08)** | Correo real (`message_id` 19ea478e791867b0) + evento real (`event_id` vmovd103mbb40u7ek3ehb5jsa0), ambos con recibo |
| 2 · Percepción real (Morning Brief) | Brief diario con datos reales | 🟢 **Brief con datos reales** (store de cuentas a cobrar D-23 + `daily_brief` en el chat con agenda/correos/cobros D-28) | Daemon programado del brief (hoy es invocable, no aún cron diario) |
| 3 · Bucle e2e cuña 1 (cobros) | Flujo cobros completo ×5 sin intervención | 🟠 Cerebro listo | Orquestación e2e + recibos 🟢. **Dependía de tener datos → primero INTAKE de facturas (F-5).** **Loombit Decide:** su vista de decisión = **LD-2** (`decision_card` de un cobro), ver `PLAN_LOOMBIT_DECIDE.md`. |
| 4 · UI humana | Dashboard no técnico | 🟢 **Galaxia + drag-to-act**; 🟠 **rediseño «Tela» en curso** | Galaxia MVP (D-26/27) + drag-to-act (D-31). **Sesión UX TOP (`feat/ux-top-ola1`)**: auditoría + Ola 1-2 (telar instantáneo, cognición en tarjeta, chat copiloto, galaxia real, Google, aprobación con borrador, todo botón con función) en la **Tela nueva** `/static/loombit.html`. **Falta para cerrar:** paridad (sidebar/historial/settings) → **promover a `/`**; Ola 3 (pasos del agente en vivo, polling→eventos); Ola 4 (⌘K, motion, responsive); Fábrica a backstage. **Loombit Decide:** evolución a **UI generativa GOBERNADA** = **LD-0/LD-1/LD-5** (`PLAN_LOOMBIT_DECIDE.md`) — la Tela pasa de pantallas fijas a spec JSON validada. Ver `AUDITORIA_UX_2026-06-09.md` + `EXPERIENCIA_LOOMBIT.md` |
| 5 · Memoria y aprendizaje | Daemon de memoria proactiva | 🟢 **Cerrada (2026-06-09)** — memoria + RAG semántico + Reflexion + GEPA + **daemon de aprendizaje proactivo** (`aprendizaje.py`, routine `Aprendizaje`: reindexa RAG + destila lecciones, idempotente) | daemon opt-in global (`routines_daemon_enabled`); refinar grafo temporal (#6) es mejora futura |
| 6 · Endurecimiento + navegador | Consentimiento, export, Skill Pilot navegador | ⬜ | Adaptador Playwright/CDP, contrato de coordenadas |
| 7 · Edge / Jetson | Benchmark en Jetson Orin NX | ⬜ | Comprar hardware |

## Conectores (estado honesto)

| Conector | Estado |
|---|---|
| OAuth Google (escritorio: PKCE, auto-refresh, token cifrado, botón home) | 🟢 **CONECTADO con cuenta real (2026-06-08)**; token cifrado en disco; refresh presente |
| Gmail send | 🟢 **ENVÍO REAL VERIFICADO (2026-06-07)** — recibo en `runtime/local/skill_blanca_connector_outbox/` (`message_id` `19ea478e791867b0`, respuesta API Gmail) |
| Calendar create | 🟢 **EVENTO REAL VERIFICADO (2026-06-08)** — `event_id` `vmovd103mbb40u7ek3ehb5jsa0`, recibo en `runtime/local/skill_blanca_connector_outbox/` |
| Calendar read (agenda de hoy) | 🟡 `eventos_de_hoy` (read-only, auto-refresh) cableado al brief (D-28); falta recibo de lectura real con token vivo |
| Gmail search (lectura para contexto) | 🟢 corregido el bug de cliente cerrado (D-30); lee contexto real |
| Outbox local (.eml) / Calendario local (.ics) | 🟢 |

## Adopción de tendencias IA 2025-2026 (ver `ROADMAP_TENDENCIAS_IA.md`)

| # | Tendencia | Estado |
|---|---|---|
| 1 | Proactividad (morning brief) | 🟢 brief invocable desde el chat (`daily_brief`: agenda + correos + cobros) + patrón "propón un plan, no preguntes" en el prompt (D-28). El daemon programado sigue pendiente |
| — | **Conciliación bancaria (innovación #1)** | 🟡 parser N43 + matcher con semáforo + Expediente + router (27 tests); falta extracto de banco real → 🟢 |
| 7 | **Plantillas que aprenden — AliasResolver de pagador (flywheel)** | 🟡 tabla determinista por entidad, aprende de cobros confirmados, con procedencia/revocación (9 tests); el LLM no interviene |
| 3 | Memoria de empresa (`EntityProfile`) | 🟡 hecho (IBANs, pago, incidencias, **gate antifraude**) |
| 4 | Inteligencia documental (facturas) | 🟡 hecho (extractor + endpoint + tool, cruce albarán) |
| 6 | Computer Use / Pilot | 🟡 reforzado (DPI, UIA accesibilidad-primero, gates) |
| 8 | Qwen2.5-VL (escaneados) | 🟡 **CABLEADO + verificado EN VIVO** (2026-06-09) — `docs_intel_vision.py` (OCR literal con el VL local) escalado desde `/docs-intel/invoice` cuando el PDF/imagen no tiene capa de texto; el extractor determinista saca las cifras y se marca `via_ocr` para verificación humana (regla nº1). Recibo: una factura imagen pasó por el VL real (`via_ocr=True`, 15 s) → `base 100 + IVA 21 = total 121` ✓, NIF/IBAN OK, `proveedor` marcado baja confianza con honestidad. Tests en `test_docs_intel_vision.py`. **Para 🟢:** un escaneado REAL de Fernando |
| 5 | Servidor MCP | 🟢 **protocolo** / 🟡 capacidades — adaptador sobre el `tool_registry`, `POST /mcp` (Streamable HTTP) con gate server-side, verificado con el MCP Inspector real (D-29). Ver `MCP_SERVER_LOOMBIT.md` |
| 7 | Voz (Whisper local) | ⬜ pendiente |
| 10 | VeriFactu, grafo temporal, A2A | ⬜ futuro |

## Lo construido en esta sesión
- **Saneado del repo**: historial reescrito, LICENSE, CI verde, deps Windows con markers.
- **OAuth escritorio**: PKCE, auto-refresh, **token cifrado** (keyring/DPAPI), botón "Conectar Google", guía.
- **Skill Pilot**: DPI-awareness, tecleo Unicode, `ui_snapshot` (UIA), 3 tools nuevas en executor, jerarquía + gates en el prompt.
- **Migración**: `lm_jobs`, `skills`, `skill_loader` del repo anterior.
- **Memoria de empresa** (`EntityProfile`) con gate antifraude de IBAN.
- **Inteligencia documental** (`docs_intel`) + endpoint `/docs-intel/invoice` + tool `read_invoice`.
- **Motor de cobros** (`cobros`, Ley 3/2004).
- **Docs de dominio** al repo: oficio administrativo, banco de supuestos, dominio, tendencias.

## Próximos pasos (orden sugerido)
0. ✅ **Conciliación bancaria (#1)** — HECHO 2026-06-08 (🟡): parser Norma 43 con cuadre del registro 33 + matcher determinista con semáforo (ALTA/MEDIA/BAJA/abstención) + Expediente `conciliacion_bancaria` (`PENDING_APPROVAL`) + `routers/conciliacion.py`; al aprobar marca facturas cobradas y alimenta el gate S-01 de cobros. 27 tests. **Para 🟢:** un extracto N43 real de un banco de Fernando (anonimizado) conciliado e2e. Ver D-14/D-15 en `DECISIONES.md`.
0b. ✅ **AliasResolver que aprende (flywheel)** — HECHO 2026-06-08 (🟡): `alias_resolver.py`, tabla determinista por entidad que aprende `concepto→contraparte` de cobros confirmados por el humano (procedencia + revocación, sin LLM); desambigua conciliaciones futuras (abstención→MEDIA). 9 tests. Ver D-17. **Para 🟢:** extractos reales repetidos de un mismo pagador.
1. **Crear 1 evento real en Calendar** → cierra la Fase 1 🟢 (mismo patrón que el correo; OAuth y recibos ya están). *(siguiente)*
2. ✅ **Swap del instructor a Qwen2.5-14B-Instruct (Q4_K_M)** — HECHO 2026-06-08, verificado contra la API real (genera asunto/cuerpo y llama a la tool sin preguntar). Ver `MODELOS_LOOMBIT.md`.
3. **WhatsApp como objetivo del Pilot** — canal de negocio real (92% lo usa a diario, 68% prefiere WhatsApp a email/teléfono). Ver `INSIGHTS_PRODUCTO_Y_SUPUESTOS.md`.
4. 🟢 **Routines: scheduler + Brief diario** — verificado end-to-end (2026-06-08): motor + cron + recibo + semáforo + 15 tests + brief real contra el 14B. **Falta**: cablear fuentes reales (banco/Gmail) al brief + store de cuentas a cobrar (cierra MVP Fase 2). Ver `ROUTINES_LOOMBIT.md`.
5. **Piloto real de cobros** end-to-end → primer recibo 🟢 (necesita LM Studio + datos).
   - ✅ **Galaxia MVP (Fase 4)** — HECHO 2026-06-08 (🟢): `GET /galaxia` agrega contactos (Enviados) +
     cuentas a cobrar + aristas contacto↔cuenta; vista orbital determinista y **edgeless** (anti-maraña),
     gravedad semántica (vencidas al centro), command palette ⌘K, cinturón para la cola. Verificado en
     vivo en el servidor real. Ver D-26. **Siguiente**: drag-to-act, latido por novedad, órbitas
     correo/calendario/Drive (= los 3 gaps de Google).
6. Qwen2.5-VL local (facturas escaneadas), servidor MCP, adaptador navegador.
7. Convertir los supuestos (S-01…S-15 + los nuevos A-G/I-X de investigación de campo) en **tests de comportamiento**.

## Innovaciones acopladas por fase

Ideas de la investigación de campo integradas en el plan (detalle, código base, DoD y esfuerzo en `INNOVACIONES.md`):

| Fase | Innovaciones que la refuerzan |
|---|---|
| 2 · Morning Brief | #4 brief de 5 líneas (UX) ⭐ · #1 conciliación bancaria ⭐ · #8 velocidad de leads · #9 radar de contratos recurrentes |
| 3 · Cobros e2e | #1 conciliación bancaria ⭐ · #2 semáforo de confianza ⭐ · #3 captura única · #6 memoria temporal · #10 cruce factura/albarán + mutuas |
| 4 · UI humana | #4 brief de 5 líneas ⭐ · #2 semáforo de confianza (visible) |
| 5 · Memoria y aprendizaje | #6 memoria grafo temporal · #7 plantillas que aprenden (cierra el criterio de fase) |
| 6 · Endurecimiento + navegador/WhatsApp | #5 monitor Sede/DEH/Lexnet · #2 gates de consentimiento · WhatsApp Pilot |

**Secuencia recomendada:** primero los multiplicadores que reutilizan código ya escrito —
#4 + #1 + #2 (refuerzan Fases 2-3)— luego quick wins (#8, #9), y el resto por fase. ⭐ = meter primero.

## Plataforma fiscal (análisis — pendiente de decidir)

Análisis de arquitecto en `PLATAFORMA_FISCAL_ANALISIS.md`: el 303 como **caso de entrada** de un
**motor de expedientes oficiales** (Skill W) + **`Skill D Fiscal`** + memoria fiscal proactiva.
**Propuestas clave a validar por Fernando** (cambian el brief): liderar con *percibir y preparar*
(intake + conciliación + calendario + monitor DEH), no con *presentar*; diseñar para la
**gestoría** (multi-entidad → SQLite por entidad); el **email** como entrada real. Primer slice:
intake de factura + borrador de 303 (el humano presenta), cero riesgo legal.

**Construido ya** (con OK de Fernando para decidir y avanzar): el **motor de Expedientes**
(Skill W Core) — `expedientes.py`, SQLite por entidad + **trazabilidad inmutable** (cadena de
hashes) + documentos con sha256, 8 tests. 🟡 (sin router/UI todavía). Y encima, el
**`Skill D Fiscal`**: cálculo **determinista** del 303 (Decimal + casillas principales + avisos de
casuística) y `procesar_303` (abre Expediente → calcula → `PENDING_APPROVAL`), 11 tests. La IA
prepara; el humano valida y presenta. El **intake** (factura → línea del 303, con abstención
honesta) ya está (`intake.py`); `liquidar_303_periodo` hace el flujo completo factura→303.
El **router fiscal** (API multi-entidad: registrar factura, liquidar 303 → `PENDING_APPROVAL`,
aprobar con justificante) ya está (`routers/fiscal.py`). Pendiente: **extracción con 14B/visión**
para facturas difíciles/escaneadas, y la **UI**.

## Bloqueadores / dependen de Fernando
- ~~**#28**: crear el cliente OAuth "App de escritorio"~~ → ✅ **RESUELTO** el 2026-06-08
  (creado vía Pilot/navegador; cuenta real conectada, token cifrado).
- **LM Studio** corriendo para probar el agente de punta a punta (en marcha).

> Aprendizaje clave: el alta del cliente OAuth + la conexión se hicieron conduciendo el
> navegador con los gates intactos (humano da el consentimiento, el operador no toca
> credenciales). Es el patrón que el **adaptador de navegador (Playwright/CDP)** debe
> replicar dentro del propio Pilot para webs (vuelos, banca, AEAT…).
