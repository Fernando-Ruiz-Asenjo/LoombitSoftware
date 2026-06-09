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
