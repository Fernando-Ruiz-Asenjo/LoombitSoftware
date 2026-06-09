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

## Backlog de superficies (orden por valor) — estado
| # | Superficie | Estado | Notas |
|---|---|---|---|
| 1 | Chat / agente / cognición (memoria, tools, abstención) | 🟠 en curso | memoria ✅, router ✅, cobro/303 tools ✅, cobro e2e 🟢; **P0 contexto 4096 arreglado (reload 8192)**; abstención honesta PENDIENTE; durabilidad del contexto PENDIENTE |
| 2 | Telar (cognición→tarjetas, dedup, dudup caché) | ⬜ | |
| 3 | Aprobaciones «Preparado para ti» | 🟢 verificado clicando (Aprobar→evento real) | falta probar Descartar en vivo |
| 4 | Home / shell `loombit-app.html` | ⬜ | |
| 5 | Tools dominio: cobro ✅, 303 ✅ / factura, conciliación | 🟠 | factura+conciliación (necesitan store) PENDIENTE |
| 6 | Galaxia | ⬜ | |
| 7 | Fábrica | ⬜ | |
| 8 | Ajustes | ⬜ | |
| 9 | Entregables | ⬜ | |
| 10 | Pilot (operar web real e2e) | 🟠 primitivas OK, e2e SIN verificar | |
| 11 | Responsive / móvil | ⬜ | |
| 12 | Seguridad / operativa / privacidad (datos≠órdenes, IBAN, Origin/CSRF) | ⬜ | red-team aimafia pendiente |
| 13 | Estética / voz / motion / accesibilidad AA | ⬜ | |

## Dogfooding MULTISECTOR (encargo de Fernando) — hacerme pasar por usuarios reales
En cada iteración, además de auditar superficies, **actúa como un usuario de un sector** y encárgale a
Loombit tareas reales por el chat/agente (por RECIBO: qué tool llama, qué devuelve, ¿es correcto y útil?).
Rota sectores; anota fallos con severidad. Correos SOLO a fernando.ruizasenjo@gmail.com.

| Sector | Persona / encargo típico | Estado |
|---|---|---|
| Agencia de viajes | buscar vuelo+hotel, presupuesto a cliente, factura, cobro | 🟠 vuelos→Pilot pendiente; factura sin tool; cobro 🟢 |
| Gestoría / asesoría | 303/130 de un cliente, recordar plazos, redactar a Hacienda | 🟠 303 no fiable (14B mis-asigna) |
| Autónomo / freelance | emitir factura, reclamar impago, agenda con cliente | ⬜ |
| E-commerce / tienda | conciliar cobros, responder incidencia de pedido | ⬜ |
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
