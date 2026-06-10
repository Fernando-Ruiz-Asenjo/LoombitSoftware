# AUDITORÍA DURA EN LOOP — registro vivo (2026-06-09)

> Encargo de Fernando: auditar DURO TODO (operativa, mecánica, flujos, visibilidad,
> estética, operatividad) aplicando la 🧭 BRÚJULA (cabecera `CLAUDE.md`) y
> `docs/PROTOCOLO_AUDITORIA_DURA.md` (5 dimensiones), y **arreglar/mejorar TODO**, en un
> LOOP autónomo que encadena turnos. Este fichero es el cerebro del loop: backlog,
> hallazgos por severidad (P0 rompe / P1 frena / P2 pulido) y estado, con RECIBO.

## Reglas duras del loop (innegociable)
- **Por RECIBO, no por render.** «Se pinta» ≠ «funciona». Cada hallazgo: evidencia (qué pasó al
  clicar, captura, dato, recibo). Verificar en el **Chrome real** de Fernando («Browser 1»).
- **NUNCA «100%/todo verificado».** Reporta COBERTURA: qué probé + recibo + qué NO.
- **Arregla o quita; nunca finjas.** Rama `feat/ux-top-ola1`; ficheros <400 líneas; commit en
  VERDE (`python scripts/verify.py` → `git commit --no-verify -F tmp`; el hook no corre vía git aquí).
- **Retira falsos positivos en voz alta.**
- Correos de prueba **SOLO a fernando.ruizasenjo@gmail.com**. NO destructivos. **Gate sagrado**.
  No tocar Defender. **Bash tool, no PowerShell.** LM Studio `--parallel 1` → no apilar jobs LLM.
  Borra lo que crees en pruebas. Verifica contra el CÓDIGO.

## ⭐ PARA FERNANDO (cosas que aparté durante el loop, sin parar a preguntar)
- **Modelo de entidad:** el agente de chat registra facturas/cobros en UNA entidad por defecto
  («principal»). ¿Quieres modelo **multi-entidad (una por cliente)** o single? Afecta a cómo se
  agrupan facturas/303/cobros. Por ahora: single «principal».
- **303 fiable:** el cálculo del 303 desde una frase con el 14B NO es fiable (mis-asigna/inventa).
  Ahora que `registrar_factura` persiste, el camino bueno es **calcular el 303 desde las facturas
  registradas** (determinista). Propuesta para una próxima iteración. ¿OK?
- **Evento de prueba en tu calendario** (vie 14 jun 10:00 «Loombit · prueba de aprobación»): el
  borrado directo lo bloquea el gate de seguridad. Bórralo tú, o autorízame a hacerlo por el cauce.
- **Pilot para viajes:** primitivas vivas; operar una web de viajes e2e está SIN verificar (es frágil
  con el 14B conduciendo capturas). Cuando lo abordemos, será un proyecto con su verificación dura.

## Chequeo de regresión (arnés de presión) — 2026-06-10
`scripts/presion_cerebro.py` → **13/13 VERDE** tras ~10 iteraciones de cambios (router stems, force-tool
enfocado, telar dedup, conciliar_banco, IBAN checksum, CSRF/Origin). Nada regresó. La conciliación ya
pide el N43 (no niega capacidad) y sigue pasando la abstención; el 303 anti-línea-inventada aguanta.

## Backlog de superficies (orden por valor) — estado
| # | Superficie | Estado | Notas |
|---|---|---|---|
| 1 | Chat / agente / cognición (memoria, tools, abstención) | 🟠 en curso | memoria ✅, router ✅, cobro/303 tools ✅, cobro e2e 🟢; **P0 contexto 4096→8192 ✅**; abstención honesta MEJORADA (prompt) 🟠 aún sobre-promete; durabilidad del contexto PENDIENTE |
| 2 | Telar (cognición→tarjetas, dedup, dudup caché) | 🟢 auditado (2026-06-10) | P1 DUP agenda↔reunión comprendida ARREGLADO (suprime evento de calendario ya cubierto) + robustez `_hilo_asunto` (no tumba el home por un asunto malformado). 4 golden. Falta: dedup también plazos/correos repetidos |
| 3 | Aprobaciones «Preparado para ti» | 🟢 verificado clicando (Aprobar→evento real) | falta probar Descartar en vivo |
| 4 | Home / shell `loombit-app.html` | 🟢 auditado en Chrome real (2026-06-10) | Carga OK; hilos del día RENDERIZAN (pide acción/impuestos/reunión); fetches same-origin `/telar`→200 `/galaxia`→200 (el **middleware CSRF NO rompe la UI**); sin errores JS de Loombit (consola = MetaMask, ajeno). Cobertura: load+telar+fetch+consola; NO re-cliqué cada chip ni reenvié chat este turno (chat ya verificado antes) |
| 5 | Tools dominio: cobro ✅, 303 ✅, factura ✅, conciliación ✅ | 🟢 | factura e2e 🟢; 303 desde registradas 🟢 (validado e2e); **conciliación CABLEADA** (`conciliar_banco`, motor N43 existente expuesto como tool, solo-propuesta; verificado: pide N43 / usa la tool) 2026-06-10. Falta: soporte CSV de extracto (hoy solo N43) |
| 6 | Galaxia (drag-to-act) | 🟢 auditada (2026-06-10) | `resolve_drop`: combo sin regla → `_no_aplica` (seguro, sin crash); combo válido → `agent_task` enrutado al agente CON gate (no efecto sin aprobar). Cubierto por `test_galaxia_actions.py`. Sin bug. ~~P2 e-commerce rectificativa narró "error"~~ → **RETIRADO** (no reproducible: re-ejecutado, run limpio, era narración estocástica del 14B). El flujo de rectificativa (factura negativa) cuadra el 303. ⭐PARA FERNANDO: la rectificativa se guarda como factura negativa normal; para AEAT conviene ETIQUETARLA (tipo=rectificativa + referencia a la factura original) — mejora futura |
| 7 | Fábrica (auto-reparación de código) | 🟢 auditada (2026-06-10) | `proponer_parche` con guardas SÓLIDAS (verificado por recibo): rechaza parche que elimina símbolo público EN USO (ok=False), rechaza sintaxis rota (no compila), y **NUNCA escribe** el fichero (solo propone diff; el humano aplica en rama). Tests opcionales en repo aislado. Cubierto por `test_fabrica.py`. Sin bug |
| 8 | Ajustes (credenciales/secretos) | 🟢 parte sensible auditada (2026-06-10) | `CredentialVault` verificado por recibo: `list()` NO filtra el secreto; fichero en disco sin plaintext (solo `secret_enc` cifrado); `get_secret()` round-trip OK; sin cifrado → `set()` se NIEGA (RuntimeError, nunca guarda en claro). Cubierto por `test_credentials.py`. Sin bug. Falta: UI de ajustes (Chrome) sin auditar |
| 9 | Entregables (dossier offline + sello) | 🟢 auditado (2026-06-10) | Sello de integridad = `verify_chain` (cadena de hashes de eventos). Verificado por recibo: intacto→True, evento manipulado en BD→False. Ya cubierto por `test_tamper_is_detected`. **Nota honesta:** tamper-EVIDENTE, no infalsificable (sin HMAC/firma/timestamp externo); OK para local-first. ⭐PARA FERNANDO: si los dossiers se usan como PRUEBA legal ante terceros, añadir HMAC con secreto o sellado temporal |
| 10 | Pilot (operar web real e2e) | 🟠 primitivas OK, e2e SIN verificar | |
| 11 | Responsive / móvil | ⬜ | |
| 12 | Seguridad / operativa / privacidad (datos≠órdenes, IBAN, Origin/CSRF) | 🟠 en curso | datos≠órdenes ✅ (allowlist+prompt); anti-fuga prompt ✅; IBAN checksum + low_confidence aflorado ✅; **Host/Origin local-first ✅ (anti DNS-rebinding + CSRF, `seguridad_web.py`, verificado en vivo: evil→403, local→200)** (2026-06-10). Pendiente: red-team aimafia, exfiltración avanzada, rate-limit |
| 13 | Estética / voz / motion / accesibilidad AA | ⬜ | |

## Dogfooding MULTISECTOR (encargo de Fernando) — hacerme pasar por usuarios reales
En cada iteración, además de auditar superficies, **actúa como un usuario de un sector** y encárgale a
Loombit tareas reales por el chat/agente (por RECIBO: qué tool llama, qué devuelve, ¿es correcto y útil?).
Rota sectores; anota fallos con severidad. Correos SOLO a fernando.ruizasenjo@gmail.com.

| Sector | Persona / encargo típico | Estado |
|---|---|---|
| Agencia de viajes | buscar vuelo+hotel, presupuesto a cliente, factura, cobro | 🟠 vuelos→Pilot pendiente; factura sin tool; cobro 🟢 |
| Gestoría / asesoría | 303/130 de un cliente, recordar plazos, redactar a Hacienda | 🟠 303 no fiable (14B mis-asigna) |
| Autónomo / freelance | emitir factura, reclamar impago, agenda con cliente | 🟢 emitir factura e2e (agente llama registrar_factura, persiste 2420€) — recibo run 7e03b27a |
| E-commerce / tienda | conciliar cobros, responder incidencia de pedido | 🟠 conciliación: abstención MEJORADA (pide el extracto PDF, +honesto, +corto) pero aún sobre-promete (no hay tool de conciliar); falta wirear conciliación |
| Clínica / consulta | agendar citas, recordatorios a pacientes | ⬜ |
| Despacho de abogados | plazos procesales, redactar escrito, control de minutas | ⬜ |
| Restaurante / hostelería | pedidos a proveedor, control de facturas, reservas | ⬜ |
| Construcción / reformas | presupuestos, certificaciones, cobro a cliente | ⬜ |

## Hallazgos (se rellena en cada iteración)

### Iteración 0 — diagnóstico raíz (hecho antes del loop)
- **P0 (arreglado, commit f069e16):** chat SIN memoria de conversación (cada mensaje, run nuevo de cero;
  «sí» no sabía a qué respondía). Verificado en vivo: el «sí» ya sabe que va de vuelos.
- **P0 (arreglado, f069e16):** router cegaba al agente (keywords frágiles) → sin web/memoria/documentos;
  decía «no puedo abrir webs» teniéndolas. Piso admin siempre disponible. Recibo determinista.
- **P0 (arreglado, 52a1baf):** «Reclamar cobro»/303 anunciados sin tool → 0 steps. Ahora plan_cobro +
  calcular_303 (cerebros deterministas). Unit-verificado; live PENDIENTE.
- **P1 (arreglado, f069e16):** `/agent/tools` daba 500 (`tool_registry.all()` inexistente → `.list()`).
- **P2 pendiente:** evento de prueba en el calendario de Fernando (vie 14 jun 10:00) — borrado bloqueado por el gate; lo borra Fernando.

### Iteración 1 — Chat/agente: P0 de CONTEXTO (la razón de "no funciona nada" con tools)
- **P0 (RAÍZ, arreglado en runtime):** toda tarea del agente con muchas tools daba `400 Bad Request`
  de LM Studio: `"n_keep: 4124 >= n_ctx: 4096"`. El 14B estaba cargado a **4096 tokens de contexto**
  (×PARALLEL 4). El system prompt (7773 chars ≈ ~2500 tok) + 14 tools no caben. **Agravado por mi
  router nuevo** (de ~6 tools a ~14 → cruza el límite). Recibo: mismo schema de tools con prompt corto
  → 200; con el system prompt real → 400.
  **FIX:** `lms unload` + `lms load -c 8192 --parallel 1` (estimado 9.63 GiB; menos KV que 4096×4).
  Ahora CONTEXT 8192 / PARALLEL 1.
- **Falsos positivos retirados (en voz alta):** (1) "saturación transitoria de LM Studio" y
  (2) "esquema de tool roto" — AMBOS falsos; era overflow de contexto, determinista.
- **🟢 cobro e2e (recibo API):** «reclama cobro 1500€ a Viajes Marsans, venció 1 may» → completed,
  llamó `plan_cobro`, devolvió 39 días · reclamación formal · 1500€ · 40€ · interés 16,27€ al 10,15%
  (tipo BOE) + redactó la carta de reclamación. Los números solo salen de la tool determinista.
- **⚠️ CAVEAT durabilidad (P1 pendiente):** el reload es estado de RUNTIME. Si LM Studio reinicia o
  recarga el modelo (JIT/TTL) puede volver a 4096 → vuelve el 400. DURABLE: o Fernando fija el contexto
  ≥8192 por defecto en LM Studio, o un safeguard de código (cap de tools / system prompt más corto para
  caber en contextos pequeños). Recomendado: ambas. Pendiente para próxima iteración.
- **NOTA cobertura:** probado cobro; 303 NO probado e2e aún (mismo patrón, debería ir); factura y
  conciliación SIN tool todavía (necesitan store). Abstención honesta sin abordar.

### Iteración 2-3 — 303 e2e: la TOOL es fiable, el 14B NO (riesgo fiscal real)
- **303 e2e (ctx 8192, completed) → RESULTADO ERRÓNEO por el 14B (no por la tool):**
  - 1ª prueba: el modelo **INVENTÓ** líneas (Servicios 5000€@10%, Contratación 7000€@**40%**) — recibo
    en los `tool_calls` del run. Un IVA del 40% no existe.
  - 2ª prueba (con guard + "no inventes nada"): ya no inventó, PERO metió la compra (3000€) dentro de
    `iva_repercutido` → deducible 0 → 3150€ a ingresar (lo correcto: **1890€**). **Mis-asignó
    repercutido/soportado.** Recibo: ARGS `iva_repercutido:[12000 Ventas, 3000 Compras]`.
  - Además el agente **parafrasea** la salida de la tool y se come el echo de visibilidad.
- **ARREGLADO (mitigación):** guard antifabricación en `calcular_303` (rechaza tipos de IVA imposibles
  como 40%; válidos 0/4/5/10/21) + echo de líneas usadas + descripción que prohíbe inventar. +3 tests.
- **VERDICTO HONESTO (P1 · límite del modelo, NO resuelto):** el 303 vía chat con el 14B **no es fiable
  para dinero/impuestos** (mis-asigna campos, parafrasea, inventa). Mitigado, no resuelto. **Camino
  fiable = intake desde facturas reales (F-5) + cálculo determinista**, no extracción de una frase por
  el LLM. `cobro` es más robusto (menos campos, números directos). → `calcular_303` queda 🟠
  "asistente, VERIFICA siempre". Reconsiderar: usar el coder/instructor con few-shot, o exigir
  confirmación de las líneas antes de calcular.

## Iteración 2026-06-10 — PRESIÓN DURA del cerebro + reparaciones (por recibo)
Encargo: pruebas duras/aleatorias buscando el fallo + reparar + arnés hacia "100 ciclos verde".
Bugs REALES hallados presionando y REPARADOS (todos con golden + verificados en vivo):
- **P0 Allowlist de tools (seguridad+fiabilidad):** el 14B alucinaba un nombre de tool fuera del set
  ofrecido (registrar_factura cuando solo se dio plan_cobro) y el bucle la EJECUTABA. Ahora, con
  intención enfocada/exclusión, una tool no ofrecida se RECHAZA.
- **Forzar la tool ENFOCADA** (intencion_consecuente + tools_foco/excluir): cobro/303/factura/buscar
  fuerzan la tool CORRECTA y solo con datos (si faltan, pregunta, no inventa). Arregla: fabricar el
  interés (4,5%→BOE), tool equivocada, fabricar al faltar datos.
- **Router stems** (`reclam`/`cobr`/`vencid`): "reclamo" ya ofrece plan_cobro.
- **Leer≠crear agenda** (determinista): preguntas de agenda excluyen calendar_create.
- **303 anti-línea-inventada** (`_filtrar_lineas_303`): descarta líneas cuya base no está en el
  mensaje → cierra el residual del 303 manual (10000@21 + 2000@21 → 1680 sin línea fantasma).
- **Seguridad:** prompt anti-fuga (no revelar system prompt) + anti-exfiltración masiva a externos.
- **Arnés** `scripts/presion_cerebro.py` (13 escenarios, gmail_send stubeado): base ~12-13/13.
- **Code vs fine-tuning:** decidido CÓDIGO (determinista/garantía/swap-model); fine-tuning fuera de
  alcance (brújula) y solo bajaría la prob., no garantiza. Residual honesto: el 14B aún puede
  parafrasear/inventar en casos raros; mitigado por guards + camino fiable (303 desde registradas).
- **P1 dogfooding gestoría (2026-06-10, ARREGLADO):** "con las facturas REGISTRADAS calcula mi 303"
  → el agente registraba facturas fantasma en vez de usar `calcular_303_registradas`. Causa: `_FACTURA`
  casaba el adjetivo "registradas". Fix: exigir el COMANDO de crear (regístrame/emite una factura).
  Verificado e2e: registrar 5000@21 → "303 desde registradas" usa la tool fiable (1050 devengado).
  **Camino fiable del 303 (⭐PARA FERNANDO) VALIDADO e2e.**
- **Iteración 2026-06-10 (b):** dogfooding sector **autónomo**, flujo COMPUESTO ("manda recordatorio
  de pago a Juan por factura de 600€ vencida"): **PASÓ** — contacts_find→"ambiguo" (3 Juanes)→ el
  agente PREGUNTÓ cuál (no inventó destinatario ni envió al equivocado). El endurecimiento aguanta en
  compuesto. **P2 anotado:** una pregunta de desambiguación deja el run en `completed` (con la pregunta
  en texto) en vez de `pending_question`; en chat funciona por historial → no se toca (riesgo>valor).
  **Auditoría por código del 303-registradas:** SANO (campos consistentes persist↔read, "sin facturas"
  honesto, ilegibles→avisos). Sin break que arreglar este turno.
