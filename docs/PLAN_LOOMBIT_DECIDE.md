# 🗺️ Plan de implementación — «Loombit Decide» (operador autónomo + UI generativa gobernada)

> **Traduce la dirección `docs/VISION_LOOMBIT_DECIDE.md` (D-57) a hitos construibles, verticales y con
> recibo.** Estado global: **PROPUESTA, 0% construido.** Cada hito es 🟡/🟠/🟢 por su propio DoD; nada se
> marca hecho sin recibo (regla nº1). Decisión de secuenciado: **D-59**.
>
> Origen idea: Fernando (2026-06-11). Investigación con recibo de lectura en la visión §3.

---

## Principio rector (de dónde NO nos salimos)

La visión **no rompe la Ley Fundacional, la extiende a la pantalla**: el LLM **propone** una *spec* de UI
desde un **vocabulario cerrado**; el **código valida y rinde**. El LLM nunca emite HTML/JS, nunca calcula
cifras, nunca dispara el efecto externo. Todo hito que viole esto se rechaza, por bonito que sea.

**No es un giro de producto:** es **subir un piso** sobre el cerebro + el gobierno que ya existen. No se
reescribe el núcleo; se compone con lo que hay.

---

## Dependencia honesta con el camino crítico actual

`Loombit Decide` **no sustituye** el camino crítico de la cuña 1 (`ESTADO_Y_ROADMAP.md`): **INTAKE de
facturas (F-5, 🔴) → cobros e2e (Fase 3)**. Lo **reenmarca**: la "tarjeta de decisión de un cobro" (LD-2)
**necesita datos reales** que hoy faltan. Por eso:

> **LD-0 y LD-1 (el motor de decisiones + el contrato de UI gobernada) se pueden construir YA** sobre el gate
> y el cerebro existentes. **LD-2 (la primera rebanada vertical) depende del INTAKE** para tener un impago de
> verdad que decidir. El intake sigue siendo prioridad 🔴; LD-2 se engancha detrás.

---

## Los hitos (LD-0 … LD-5)

> Leyenda esfuerzo: **S** (≤1 sesión) · **M** (1-2 sesiones) · **L** (varias). Todos arrancan en ⬜.

### LD-0 — Espina: `Decision` de primera clase + cola  ·  esfuerzo **M**  ·  refuerza Fase 3/4
- **Objetivo:** una `Decision` como objeto de dominio (qué · por qué · opciones · reversibilidad · riesgo ·
  estado) que **se acumula en una cola**, no un chat.
- **Construye sobre:** `policy/authority_plane.py` (ya distingue `EJECUTAR`/`APROBAR`/`CORREGIR`/`REHUSAR`) +
  el gate `PENDING_APPROVAL` + `telar.py` (la tela proactiva **se convierte en la cola de decisiones**).
- **Entregable:** modelo `Decision` + store/cola persistente + API de listar/resolver. Sin UI nueva todavía.
- **DoD (🟢):** golden de la cola (encolar → resolver mueve estado; reversibilidad declarada por decisión) +
  recibo en vivo: una decisión real del cerebro (un cobro) entra en la cola y se resuelve por el gate
  existente, **sin tocar el camino de efecto** (cero regresión en los ~717 tests).
- **Riesgo:** acoplar la cola al chat actual. Mitigación: la cola es backend puro; la UI llega en LD-1.

### LD-1 — UI generativa GOBERNADA: el contrato  ·  esfuerzo **L**  ·  refuerza Fase 4
- **Objetivo:** el mecanismo de "generar lo que el usuario necesita ver", **gobernado**.
- **Vocabulario CERRADO (v1):** `decision_card`, `resumen`, `eleccion`, `borrador_preview`, `cola`. Es un
  **schema declarativo**, no HTML. Referencia de diseño: **Adaptive Cards** (MIT, "no code allowed / safe
  payloads") y el **vocabulario de eventos de AG-UI** (MIT, framework-agnóstico) — ver visión §3.
- **Construye sobre:** `static/` (Tela/galaxia/chat ya existen) como base del renderer.
- **Entregable:** (a) **validador backend** (whitelist de componentes; rechaza todo lo que no esté en el
  vocabulario, **nunca** HTML/JS) + (b) **renderer JS plano** que pinta la spec validada (server-driven UI).
- **DoD (🟢):** golden del contrato — el LLM **no puede** colar HTML/`<script>`/campo fuera de schema (spec
  inválida → rechazada, no renderizada); recibo en vivo: el 14B propone una `decision_card` para un caso real,
  el validador la acepta y el renderer la pinta. **Test adversarial:** inyección en la spec → bloqueada.
- **Riesgo:** que el vocabulario se quede corto y tiente a "dejar pasar HTML". Mitigación: se **amplía el
  vocabulario** (más componentes cerrados), **nunca** se abre a markup libre (§SEG/§GOB-1).

### LD-2 — Primera rebanada vertical: `decision_card` de UN cobro  ·  esfuerzo **M**  ·  cierra demo Fase 3↔4
- **Objetivo:** probar el **lazo entero** en vertical, sobre código que ya existe.
- **Flujo:** el cerebro detecta el impago (ya lo hace, `cobros.py` + `reclamar_cobro_cliente`) → prepara plan
  (Ley 3/2004, cifras por código) + borrador → emite **una sola `decision_card`** (aprobar / editar /
  posponer) → el renderer la pinta → la resolución dispara el efecto **con el gate**.
- **Construye sobre:** LD-0 + LD-1 + `cobros.py` + `comprension.py` (la percepción quién/qué/estado).
- **Depende de:** **INTAKE de facturas (F-5)** para tener un impago real; con datos mock se valida el lazo
  técnico, con datos reales se valida el producto.
- **DoD (🟢):** recibo en vivo (percepción → decisión → spec validada → efecto con gate, end-to-end con el
  14B) + golden de la spec del cobro (vocabulario cerrado, nunca HTML del LLM) + cero regresión.
- **Riesgo:** que el 14B proponga cifras en la card. Mitigación: las cifras las pone **código** (`cobros.py`);
  el LLM solo elige *qué mostrar*, no los números (§14B).

### LD-3 — Agente reactivo → autónomo (niveles graduados)  ·  esfuerzo **L**  ·  refuerza Fase 5
- **Objetivo:** de "responde cuando le hablas" a **trabajar en background y encolar decisiones**.
- **Niveles de autonomía (graduados y MEDIDOS, no prometidos):** `observa` → `propone` → `actúa-con-gate` →
  `actúa-solo en lo reversible`. Patrón aprendido de HumanLayer (conceptual) + LangChain HITL (valida lo
  nuestro) — ver visión §3.
- **Construye sobre:** `routers/routines.py` + `scheduler.py` (el trabajo en 2º plano que **genera** las
  decisiones de LD-0).
- **DoD (🟢):** una routine genera decisiones en background y las encola sin intervención; el nivel de
  autonomía es **configurable y auditable**; recibo: N decisiones encoladas autónomamente, 0 efectos externos
  sin gate. **Honestidad §14B:** el 14B local limita la autonomía real → se empieza en `propone+gate` y solo
  sube a `actúa-solo` en lo **reversible y medido**.
- **Riesgo:** autonomía excesiva con un modelo local limitado. Mitigación: la subida de nivel exige recibo.

### LD-4 — Correo: contexto → triaje autónomo  ·  esfuerzo **L**  ·  refuerza Fase 2/6
- **Objetivo:** la promesa "el usuario **no toca el correo**". El lazo *leer todo → clasificar → redactar →
  subir solo la decisión*.
- **Construye sobre:** `gmail_search` (ya 🟢 para contexto) + el cerebro + LD-0/LD-1 (cada correo accionable →
  una decisión en la cola, no una bandeja que revisar).
- **DoD (🟢):** un lote de correos reales → triaje + borradores + **solo las decisiones suben** a la cola; el
  envío **siempre con gate**; recibo en vivo. **§SEG:** todo correo leído pasa por `datos≠órdenes` (ya está).
- **Riesgo:** inyección desde el correo (el caso clásico). Mitigación: §SEG-2 ya neutraliza marcadores; el
  gate de efecto + `_recipiente_resuelto` frenan el envío a destinatarios no pedidos.

### LD-5 — Generalizar el vocabulario (la UI que se adapta a cada momento)  ·  esfuerzo **L**  ·  Fase 4+
- **Objetivo:** que la interfaz **genere lo que haga falta en cada momento** más allá del cobro: 303 a
  presentar, conciliación a confirmar, evento a agendar, lead a contestar — cada uno su `decision_card`.
- **Construye sobre:** LD-1 (el contrato) + las skills D existentes (fiscal, conciliación, agenda).
- **DoD (🟢):** ≥3 tipos de decisión distintos renderizados por el **mismo** contrato gobernado, cada uno con
  su golden + recibo en vivo.
- **Riesgo:** explosión del vocabulario. Mitigación: componentes reutilizables, no uno por dominio.

---

## Orden recomendado (y por qué)

```
LD-0 (motor+cola) ──► LD-1 (contrato UI gobernada) ──► LD-2 (rebanada: cobro)  ──► LD-5 (generalizar)
        │                                                    ▲
        └──────────────► LD-3 (autonomía) ─────────────┐     │
                          LD-4 (correo) ───────────────┴─────┘   [LD-2 espera al INTAKE F-5 para datos reales]
```

1. **LD-0 + LD-1 primero** — son el cimiento (motor de decisiones + contrato de UI gobernada), se construyen
   YA sobre el gate existente, y **no dependen de datos**. Mayor valor estructural por sesión.
2. **INTAKE de facturas (F-5, 🔴)** en paralelo — sigue siendo el desbloqueo de datos del camino crítico.
3. **LD-2** detrás del intake — la primera rebanada **demostrable** (el lazo entero sobre un cobro real).
4. **LD-3 y LD-4** suben la autonomía (background + correo) una vez el lazo está probado.
5. **LD-5** generaliza cuando el contrato está maduro.

---

## Cómo se refleja en `ESTADO_Y_ROADMAP.md`

- **Fase 4 (UI humana)** absorbe LD-0/LD-1/LD-5 (la Tela pasa de pantallas fijas a **UI generativa gobernada**).
- **Fase 3 (cobros e2e)** gana LD-2 como su **vista de decisión** (la demo que la cierra de cara al usuario).
- **Fase 5 (memoria/aprendizaje)** gana LD-3 (la autonomía graduada que encola en background).
- **Fase 2/6** ganan LD-4 (correo autónomo + endurecimiento de la frontera de datos).

---

*Esto es un plan, no una promesa. Cada hito se construye por rebanada vertical con recibo, sobre el gobierno
como cimiento. Si un hito cuesta más de lo que vale, se retira en voz alta (§META-2). Mejora lo que se pide
(Ley 0): si ves un atajo mejor manteniendo la Ley Fundacional, tómalo.*
