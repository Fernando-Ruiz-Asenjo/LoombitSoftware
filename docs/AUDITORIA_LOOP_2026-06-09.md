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

> **ÍNDICE de decisiones pendientes (priorizado, detalle abajo y en el log):**
> 1. **[P1 riesgo real, MITIGADO por código]** Asesoramiento fiscal regulado: el 14B inventa
>    tipos/exenciones de IVA. **Ya hay aviso DETERMINISTA garantizado** ("no es asesoramiento,
>    confírmalo con tu gestor/AEAT") antepuesto en estas preguntas (2026-06-10), que de-autoritativiza
>    el dato. FALTA TU DECISIÓN para cerrarlo del todo: ¿KB fiscal curada que CITE, o política dura
>    "no doy específicos"? (el aviso reduce el riesgo, no elimina el específico equivocado)
> 2. **[Producto]** Modelo de entidad: ¿multi-entidad (una por cliente) o single «principal»?
> 3. **[Producto/UX]** Responsive del shell (0 media queries hoy): ¿lo queremos y en qué fase del rediseño?
> 4. **[Fiscal/AEAT]** Etiquetar rectificativas (tipo=rectificativa + ref. a la factura original).
> 5. **[Seguridad]** HMAC/sello temporal en entregables si se usan como PRUEBA legal ante terceros.
> 6. **[Operativa]** ~50 commits del loop en `feat/ux-top-ola1` (local, sin PR): subir a PR cuando quieras.
> 7. **[Menor]** Borrar el evento de prueba del calendario (el gate bloquea borrarlo desde aquí).

- **Modelo de entidad:** el agente de chat registra facturas/cobros en UNA entidad por defecto
  («principal»). ¿Quieres modelo **multi-entidad (una por cliente)** o single? Afecta a cómo se
  agrupan facturas/303/cobros. Por ahora: single «principal».
- **⚠️ Asesoramiento fiscal/legal regulado (P1, NO resuelto por código):** el 14B da consejo fiscal
  CONCRETO equivocado aunque le digas que no (dogfooding clínica: dijo que la fisioterapia lleva IVA,
  cuando está EXENTA art.20 LIVA; antes confundía RETA con IVA). El guardrail de prompt lo MEJORÓ (quita
  la conflación, recomienda gestor) pero el modelo SIGUE inventando tipos/exenciones. **Decisión:** ¿(a)
  base de conocimiento fiscal curada que el agente CITE, o (b) política dura "Loombit no da tipos ni
  exenciones de IVA; te lo confirma tu gestor" (rehúsa el específico)? Hoy: riesgo mitigado, no cerrado.
- **303 fiable:** el cálculo del 303 desde una frase con el 14B NO es fiable (mis-asigna/inventa).
  Ahora que `registrar_factura` persiste, el camino bueno es **calcular el 303 desde las facturas
  registradas** (determinista). Propuesta para una próxima iteración. ¿OK?
- **~~Fecha relativa del calendario~~ → ARREGLADO (2026-06-10):** el 14B erraba fechas relativas
  ('próximo lunes'→sábado, 'mañana'→hoy). Ahora `_corregir_fecha_calendario` recalcula con `parsear_fecha`
  (determinista) y corrige el `start_iso` antes del gate. Verificado en vivo. Cierra el item T5.
  **Extendido a COBRO (2026-06-10):** 'venció hace N semanas' → el 14B daba 24 días (correcto 21),
  cambiando la ETAPA legal e interés. `parsear_fecha` ahora entiende 'hace N días/semanas' y corrige
  `fecha_vencimiento` en plan_cobro. Verificado: 21 días, etapa correcta.
- **Evento de prueba en tu calendario** (vie 14 jun 10:00 «Loombit · prueba de aprobación»): el
  borrado directo lo bloquea el gate de seguridad. Bórralo tú, o autorízame a hacerlo por el cauce.
- **Pilot para viajes:** primitivas vivas; operar una web de viajes e2e está SIN verificar (es frágil
  con el 14B conduciendo capturas). Cuando lo abordemos, será un proyecto con su verificación dura.

## Chequeo de regresión (arnés de presión) — 2026-06-10
`scripts/presion_cerebro.py` → **13/13 VERDE** tras ~10 iteraciones de cambios (router stems, force-tool
enfocado, telar dedup, conciliar_banco, IBAN checksum, CSRF/Origin). Nada regresó. La conciliación ya
pide el N43 (no niega capacidad) y sigue pasando la abstención; el 303 anti-línea-inventada aguanta.
**2º pase 13/13 verde** tras los arreglos de fecha (calendar/cobro), relay_fiel multi y prompt fiscal:
sin regresión; la interceptación de fechas relativas NO toca las fechas explícitas (cobro 'el 1 de mayo'
sigue dando 40 días correctos).
**3er pase 13/13 verde** tras el trimestre-fiel del 303 y el AVISO fiscal determinista en `_relay_fiel`:
sin regresión, y el aviso NO se cuela en cálculos (cobro/303 limpios).
**4º pase 13/13 verde** tras calendar_semana + fmt_evento (días) + hace-N-meses + ruteo cierre-de-mes:
sin regresión, y MEJORA visible — `leer_agenda` ahora responde la semana con días correctos (antes
daba el fallback "me he liado").

**Dogfooding construcción (multi-ítem) — 2026-06-10:** "apúntame 3 facturas recibidas (200/350/500€ al
21%)" → registró LAS 3 correctas, `sentido=soportado` (verificado en disco). Datos OK. **P2 recurrente
(presentación):** el resultado final solo ECHOA la última de N (relay-fiel muestra el último autoritativo);
las demás se guardan en silencio → confuso ("¿registró todas?"). **ARREGLADO (2026-06-10):** `relay_fiel`
ahora recoge TODAS las tools autoritativas en orden (single-tool idéntico, fijado por golden); verificado
en vivo: 3 facturas → las 3 visibles en el resultado. +2 golden, gate verde.

**Verificación calendario semana (2026-06-10):** '¿tengo algo el viernes?' → usa calendar_semana, responde bien (viernes vacío, lista lo próximo) sin crear nada; los días del fix _fmt_evento ('Domingo 14','Lunes 15') fluyen correctos a la narración. OK.

**Auditoría calidad de correo (2026-06-10):** SÓLIDA por recibo — asunto concreto, cuerpo natural y
profesional, firmado como el usuario (nombre+empresa de la memoria), saludo/despedida, NO se delata
como IA/bot. Feature de uso diario OK; sin bug.

**Auditoría ROUTINES (proactivas) — seguridad (2026-06-10):** SEGURO por recibo. Una routine proactiva
(p.ej. reply_watch) redacta y llama a gmail_send, pero el run lleva `proactive=True` (campo persistido,
sobrevive recarga) y la política de aprobación lo FUERZA al gate (PENDING_APPROVAL) aunque el
destinatario sea claro — "lo proactivo SIEMPRE se confirma" (loop.py:580). NO auto-envía. ⚠️ Falso
positivo retirado: una 1ª prueba mal montada (email solo en messages, no en task) chocó con el guard
anti-destinatario-inventado y lo malinterpreté; re-test correcto → GATE.

**Composición verificada (2026-06-10):** flujo compuesto 'cobro hace 3 semanas + correo de reclamación a López' → plan_cobro (force-tool) + 21 días (fecha-fiel) + interés BOE 11,68€ (relay-fiel) + contacts_find, sin auto-envío a tercero. Los arreglos recientes componen bien.

## Backlog de superficies (orden por valor) — estado
| # | Superficie | Estado | Notas |
|---|---|---|---|
| 1 | Chat / agente / cognición (memoria, tools, abstención) | 🟢 muy reforzado | memoria ✅, router ✅, cobro/303/factura/conciliación tools ✅; force-tool enfocado ✅; allowlist ✅; relay_fiel multi ✅; fecha-fiel (calendario+cobro) ✅; trimestre 303 ✅; aviso fiscal determinista ✅; **F-7 agenda de la semana CERRADA** (`calendar_semana`, verificado en vivo) ✅; 13/13 bajo presión. Residual: narración del 14B (días de semana, específicos fiscales) |
| 2 | Telar (cognición→tarjetas, dedup, dudup caché) | 🟢 auditado (2026-06-10) | P1 DUP agenda↔reunión comprendida ARREGLADO (suprime evento de calendario ya cubierto) + robustez `_hilo_asunto` (no tumba el home por un asunto malformado). 4 golden. Falta: dedup también plazos/correos repetidos |
| 3 | Aprobaciones «Preparado para ti» | 🟢 verificado clicando (Aprobar→evento real) | falta probar Descartar en vivo |
| 4 | Home / shell `loombit-app.html` | 🟢 auditado en Chrome real (2026-06-10) | Carga OK; hilos del día RENDERIZAN (pide acción/impuestos/reunión); fetches same-origin `/telar`→200 `/galaxia`→200 (el **middleware CSRF NO rompe la UI**); sin errores JS de Loombit (consola = MetaMask, ajeno). Cobertura: load+telar+fetch+consola; NO re-cliqué cada chip ni reenvié chat este turno (chat ya verificado antes) |
| 5 | Tools dominio: cobro ✅, 303 ✅, factura ✅, conciliación ✅ | 🟢 | factura e2e 🟢; 303 desde registradas 🟢 (validado e2e); **conciliación CABLEADA** (`conciliar_banco`, motor N43 existente expuesto como tool, solo-propuesta; verificado: pide N43 / usa la tool) 2026-06-10. Falta: soporte CSV de extracto (hoy solo N43) |
| 6 | Galaxia (drag-to-act) | 🟢 auditada (2026-06-10) | `resolve_drop`: combo sin regla → `_no_aplica` (seguro, sin crash); combo válido → `agent_task` enrutado al agente CON gate (no efecto sin aprobar). Cubierto por `test_galaxia_actions.py`. Sin bug. ~~P2 e-commerce rectificativa narró "error"~~ → **RETIRADO** (no reproducible: re-ejecutado, run limpio, era narración estocástica del 14B). El flujo de rectificativa (factura negativa) cuadra el 303. ⭐PARA FERNANDO: la rectificativa se guarda como factura negativa normal; para AEAT conviene ETIQUETARLA (tipo=rectificativa + referencia a la factura original) — mejora futura |
| 7 | Fábrica (auto-reparación de código) | 🟢 auditada (2026-06-10) | `proponer_parche` con guardas SÓLIDAS (verificado por recibo): rechaza parche que elimina símbolo público EN USO (ok=False), rechaza sintaxis rota (no compila), y **NUNCA escribe** el fichero (solo propone diff; el humano aplica en rama). Tests opcionales en repo aislado. Cubierto por `test_fabrica.py`. Sin bug |
| 8 | Ajustes (credenciales/secretos) | 🟢 parte sensible auditada (2026-06-10) | `CredentialVault` verificado por recibo: `list()` NO filtra el secreto; fichero en disco sin plaintext (solo `secret_enc` cifrado); `get_secret()` round-trip OK; sin cifrado → `set()` se NIEGA (RuntimeError, nunca guarda en claro). Cubierto por `test_credentials.py`. Sin bug. Falta: UI de ajustes (Chrome) sin auditar |
| 9 | Entregables (dossier offline + sello) | 🟢 auditado (2026-06-10) | Sello de integridad = `verify_chain` (cadena de hashes de eventos). Verificado por recibo: intacto→True, evento manipulado en BD→False. Ya cubierto por `test_tamper_is_detected`. **Nota honesta:** tamper-EVIDENTE, no infalsificable (sin HMAC/firma/timestamp externo); OK para local-first. ⭐PARA FERNANDO: si los dossiers se usan como PRUEBA legal ante terceros, añadir HMAC con secreto o sellado temporal |
| 10 | Pilot (operar web real e2e) | 🟠 primitivas OK, e2e SIN verificar | |
| 11 | Responsive / móvil | 🟠 auditado: NO implementado (2026-06-10) | Recibo: el shell tiene **0 media queries** → no se adapta a móvil/tablet (layout fijo de 3 columnas de escritorio). Es FEATURE pendiente, no bug; el shell está en rediseño → NO añado CSS sin poder verificarlo por recibo (el `resize` del MCP no afectó el viewport interno). ⭐PARA FERNANDO: decidir si el shell objetivo debe ser responsive (móvil real) y en qué fase del rediseño se aborda |
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
