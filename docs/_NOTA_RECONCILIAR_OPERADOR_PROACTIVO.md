# Nota para reconciliar al fundir `feat/operador-proactivo` (sesión paralela)

> No edito `DECISIONES.md` ni `ESTADO_Y_ROADMAP.md` para no colisionar con la sesión
> principal. Aquí dejo el parche propuesto; al fundir, trasládalo (ajusta el nº D-NN al
> siguiente libre). Worktree: `C:\Users\fernando\loombit-par-prod`.

## Qué resuelve (dos quejas de producto de Fernando)

- **Foto 1** — el operador listaba sus herramientas con el nombre técnico (`gmail_send`,
  `calendar_create`…). → capa de presentación humana (`tool_labels.py`) + regla en el prompt.
- **Foto 2** — "resumen de hoy" fallaba ("no puedo ver tu calendario") y "hazlo con Pilot"
  devolvía la pelota. → lectura de agenda (`skill_blanca_calendar_read.py`), `daily_brief` y
  `calendar_today` (reutilizan el cerebro del brief del daemon), y patrón **proactividad** en el
  prompt (propón un plan, no preguntes; las lecturas se hacen directas).

## Entrada propuesta para `docs/DECISIONES.md` (siguiente libre, p.ej. D-25)

**D-25 — Operador proactivo y humano: resumen del día en el chat + capacidades en lenguaje humano.** Estado 🟡 (wiring + degradación verificados; lectura real de Calendar contra token vivo pendiente en la app integrada).
- *Elegido:* (a) `tool_labels.py` traduce name técnico → etiqueta amigable; el prompt instruye a presentarse en humano, nunca con el nombre de la tool. (b) Nueva LECTURA de calendario (`skill_blanca_calendar_read.eventos_de_hoy`, read-only, faltaba: el conector solo escribía). (c) `daily_brief`/`calendar_today` exponen al chat el MISMO cerebro de señales del daemon (`_señales_reales`, ahora enriquecido con la agenda); las cifras las calcula el código, el LLM solo narra, con **fallback determinista** si LM Studio no está. (d) patrón **PROACTIVIDAD** en el prompt: ante peticiones de alto nivel, preparar y proponer un plan ("voy a (1)…(2)… ¿lo hago?") en vez de preguntar dato a dato; las lecturas se ejecutan directas; "NUNCA digas que no puedes ver el calendario".
- *Fuente única:* el chat y el daemon dan el mismo brief (ambos usan `_señales_reales`). Sin duplicar.
- *Gates intactos:* `daily_brief`/`calendar_today` son lectura → no pausan; todo efecto externo sigue pausando para aprobación (regla 4). El patrón proactivo propone, no auto-ejecuta efectos.
- *Tests:* 19 nuevos + 1 actualizado (`test_unmatched_task_gets_default_admin_set`: "resumen" ya no cae al set de correo, ahora enruta a `daily_brief`). Suite: 285 passed.
- *Reversible:* sí; 3 ficheros nuevos + ediciones aditivas pequeñas en prompt/registry/routine_executors/tools.__init__.
- **Para 🟢:** ejecutar `daily_brief`/`calendar_today` en la app integrada (con `.env` + token vivos) y guardar recibo de una lectura real del calendario de hoy.

## Parche propuesto para `docs/ESTADO_Y_ROADMAP.md`

- Conectores: añadir **Calendar read-only** → 🟡 (lectura de agenda de hoy implementada, pend. verificación real).
- Tendencia #1 (Proactividad / morning brief): el brief ya es **invocable desde el chat** (no solo daemon).
