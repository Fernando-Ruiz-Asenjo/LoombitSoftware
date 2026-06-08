# Investigación 6 — Mejorar lo que YA tenemos (profundidad, no anchura) (2026-06-08)

> Misma dureza que la Investigación 5, pero hacia dentro: **cómo subir de calidad,
> robustez y honestidad lo que ya existe — sin añadir ni una Skill ni una feature nueva.**
> Es la consecuencia directa del veredicto de la auditoría: *profundidad > anchura*.
> Hallazgos anclados en el código real (con `fichero:línea`). Solo análisis, sin implementar.

## Principio
No tocar el alcance. Coger cada capacidad que ya existe y llevarla de 🟡→🟢 o de "funciona"
a "excelente y honesta". El 80% del valor está en **cerrar el bucle de cobros e2e** y en
**endurecer el determinismo y los evals**; el resto son quick wins.

---

## 1. EL HUECO Nº1: cerrar cobros e2e (mejorando los cerebros que ya hay)

El cerebro existe y es bueno; lo que falta es **quitarle las abstenciones que lo dejan a medias**
y orquestarlo. Sin features nuevas:

- **`cobros.py` — el interés SIEMPRE se abstiene.** `late_interest()` ([cobros.py:77](loombit_operator/cobros.py)) devuelve `rate_required=True` si no le pasan el tipo, y NADIE se lo pasa → el importe de demora nunca se calcula. **Mejora honesta y determinista:** una **tabla de tipos BCE+8 por semestre** (dato público, fijo, versionado en el repo) que alimente el cálculo. El número sigue siendo de código, no del LLM; se acaba la abstención perpetua. Añadir también **días hábiles** vs naturales para los plazos legales.
- **Validar los umbrales contra los supuestos.** `escalation_stage()` y `dunning_plan()` tienen umbrales heurísticos (7/21/60 días). Convertir **S-01…S-03** del banco de supuestos en **tests deterministas** que fijen el comportamiento (no es feature nueva: es blindar lo que hay).
- **El lazo de entrada está roto.** Las cuentas a cobrar se crean por API, no nacen de facturas/banco. Mejora sin Skill nueva: cablear el `galaxia_intel`/`docs_intel` que YA detectan importes reales para **proponer** (no crear) una cuenta a cobrar candidata que el humano aprueba (es justo el "Siguiente" que pone D-27).

## 2. ENDURECER DETERMINISMO Y HONESTIDAD (el foso del producto)

- **Gate anti-seed (lección D-27).** El incidente —datos de prueba que aparecieron en el panel real— es sistémico. Mejora: un **guard** que impida escribir datos marcados como demo/seed en stores de producción (`cuentas_cobrar.json`, entidades). Cero features; pura disciplina codificada.
- **Auditar TODO camino de número.** Recorrer cada sitio donde una cifra podría venir del LLM y confirmar que viene de regex/código (cobros, conciliación, 303, galaxia_intel, VL-OCR). El VL recién cableado ya lo hace bien (transcribe, el regex extrae) — **falta el cruce de validación**: aplicar `cross_check_amount` (base+IVA=total) al texto OCR y **abstenerse** si no cuadra, en vez de devolver un importe mal leído.
- **Cobertura de abstención.** Listar qué capacidades abstienen ante duda y cuáles no; las que no, son deuda de confianza.

## 3. EVALS: cerrar los huecos que el propio sistema reporta

`selfcheck.run_selfcheck()` ([selfcheck.py:42](loombit_operator/selfcheck.py)) ya devuelve
`pendientes_sin_eval` — el sistema **te está diciendo qué no está cubierto** y nadie lo cierra.

- **Convertir S-01…S-15 + A-G/I-X en evals deterministas** (lo que el DESTILADO §5 llama "evals como ciudadanos de primera", R1 del radar). No es feature: es subir el rigor de lo existente.
- **Métrica de cobertura + tendencia**: `selfcheck` reporta verdes/total pero no la **cobertura** (evals / comportamientos anunciados) ni si sube o baja. Añadir el número hace visible la deuda.
- **Evals con juez-LLM** (`needs_llm`) hoy se saltan en el auto-chequeo rápido; correrlos en CI (no en arranque) cerraría el hueco de los comportamientos que solo se pueden juzgar con modelo.

## 4. EL AGENTE: menos pelea, más fiabilidad

El run real que destapó los bugs (D-30) tenía **13 pasos de pelea** (tools inexistentes,
fechas mal, re-pausa en bucle). Mejoras sobre lo que hay:

- **Robustez de aprobación** (ya marcada como tarea): si una acción aprobada FALLA al ejecutarse, `loop.resume` re-pausa en silencio → el usuario aprueba y "sigue saliendo la ventanita". Debe **mostrar el fallo** y cortar el bucle de re-pausa.
- **Anti-flailing**: `loop.py` ya detecta repetición de tool, pero el modelo alucinó `calendar_search` (no existe) y repitió `calendar_create` con fecha inválida 3 veces. Endurecer: **presupuesto de pasos más agresivo + cambiar de estrategia tras 2 errores de la MISMA tool + mensaje claro al modelo de "esa tool no existe / ese argumento es inválido"**.
- **Reflexion también del ÉXITO.** `reflexion.py` ([reflexion.py:25](loombit_operator/agent/reflexion.py)) hoy aprende sobre todo de fallos; aprender también **qué funcionó** (y medir si una lección recuperada de verdad ayudó) cierra el flywheel de aprendizaje que el DESTILADO promete.
- **Selección de tools por keywords es frágil**: `select_tool_names` ([tools/registry.py](loombit_operator/tools/registry.py)) acierta por palabras; un fallo deja al modelo sin la tool y le hace preguntar/alucinar. Medir la tasa de "tool correcta seleccionada" como eval.

## 5. ARQUITECTURA: pagar la deuda (regla ~400 líneas)

8 ficheros rotos. Refactor sin cambiar comportamiento (cubierto por tests):
- **`agent/memory.py` 950** — el peor; partir por responsabilidad (contactos / lecciones / entidades / historial).
- `agent/loop.py` 647, `tools/pilot.py` 694, `routers/computer.py` 673, `skill_blanca_oauth.py` 550, `pilot/windows_control.py` 537, `conciliacion.py` 445, `tools/connectors.py` 436.
- **`CLAUDE.md`** sigue diciendo "Fase actual: Fase 1" (cerrada en D-24) → corregir a la realidad.

## 6. CAPACIDADES QUE ESTÁN A MEDIO GAS (terminar, no ampliar)

- **MCP: capacidades 🟡→🟢.** El protocolo es 🟢 pero las tools envueltas no tienen recibo real *vía MCP*. Mejora: un recibo de `gmail_search`/`daily_brief` ejecutadas por un cliente MCP real, y exponer **resources** (los recibos de `runtime/local/`) que ya existen.
- **Galaxia drag-to-act: terminar el MVP.** El resolutor ya da las acciones locales (`asignar_pagador`, `adjuntar_doc_cuenta`) pero **no se persisten** (el endpoint solo enruta los `agent_task`). Cablearlas a `alias_resolver` y a `expedientes` cierra lo empezado. Y el chip de **documento** necesita subida de fichero (hoy solo conversaciones).
- **VL escaneadas: validar antes de confiar.** Cruce base+IVA=total sobre el OCR + flag de confianza; evaluar **Qwen3-VL** (radar L3) como upgrade del 7B.
- **Brief: de invocable a programado.** El cerebro y el scheduler existen; falta **encender el cron diario** del brief (cierra el criterio de la Fase 5 sin código nuevo de dominio).

## 7. UX / PULIDO (quick wins de lo que ya se ve)

- **Botón ⚙ de ajustes muerto** (`index.html`, `title="Ajustes (próximamente)"`, sin `onclick`): darle una función real con lo que ya existe (conectar Google, estado del sistema) o quitarlo.
- **Mensajes de error y estados de carga**: revisar que todo fallo se explique en humano (ya se hizo con "no puedes ver el calendario" y "task_done"; barrer el resto).
- **Doble-vía de descubribilidad** (NN/G): cada acción de arrastre, también por clic — sube la usabilidad de lo recién hecho sin features nuevas.

---

## Prioridad (qué mejorar primero)
1. **Tabla de tipos BCE + lazo factura→cuenta candidata** → desbloquea cobros e2e.
2. **Robustez de aprobación + anti-flailing** → el agente deja de frustrar.
3. **Supuestos → evals deterministas + cobertura** → sube el rigor, blinda regresiones.
4. **Gate anti-seed + cruce de validación del VL** → honestidad estructural.
5. **Refactor de `memory.py` (950) + corregir `CLAUDE.md`** → paga la deuda más visible.
6. Quick wins UX (botón ⚙, mensajes, doble-vía).

## Una frase
Antes de añadir nada, **terminar y endurecer lo que ya existe** hasta que el cobros e2e sea
🟢 ×5 y los evals cubran los supuestos. Eso es lo que separa "demo" de "producto fiable".
