# 🧭 Visión — Loombit Decide (el operador autónomo + interfaz generativa)

> **Estado: PROPUESTA DE DIRECCIÓN (D-57), no construida.** Marca el norte de producto por encima del
> gobierno (que es el cimiento, ya en marcha). Adoptarla como canon de roadmap exige su PR + OK de
> Fernando + entrada en `DECISIONES.md` (ya está: D-57). Nada de aquí está 🟢 hasta tener su recibo.
>
> Origen: idea de Fernando (2026-06-11). Investigación web + GitHub abajo, con veredicto adopt/learn/avoid.

---

## 1. El escenario

Hoy Loombit es un **copiloto**: le hablas y te ayuda. La dirección le da la vuelta:

> **Loombit hace el trabajo administrativo; tú solo decides.**

El usuario **no lee correos, no registra facturas, no persigue cobros, no rellena modelos** — nada de la
operativa. Loombit **percibe → comprende → prepara → ejecuta hasta el borde del efecto externo**, y lo único
que sube al humano es **una decisión bien planteada, en el momento justo**. La pantalla deja de ser fija:
Loombit **genera lo que necesitas ver ahora** (esta decisión, este resumen, esta confirmación) y nada más.

Tres frentes:
1. **Agente autónomo de bandeja/admin** — lee, tría, redacta y actúa solo; el humano no toca el correo.
2. **UI generativa/adaptativa** — la interfaz se compone al vuelo según lo que haga falta, no pantallas fijas.
3. **UX de cola de decisiones** — el trabajo del humano = aprobar/decidir lo que el agente le pone delante.

---

## 2. La idea arquitectónica clave: **UI generativa GOBERNADA**

La UI generativa del mercado tiene dos sabores y ninguno encaja tal cual:
- **El LLM emite componentes React** (Vercel AI SDK / RSC): potente, pero React/Next + nube. Loombit es
  **local-first + JS plano**. No encaja.
- **El LLM escupe HTML crudo** (p.ej. el repo `overhuman`): **viola la Ley Fundacional** — mete al LLM en
  el camino de control (XSS, inyección, inconsistencia). Es exactamente el agujero que §SEG/§GOB-1 cierran.

La forma correcta para Loombit es la **misma honestidad de §GOB-1, aplicada a la pantalla**:

> **El LLM PROPONE una *especificación* de interfaz desde un vocabulario CERRADO y seguro
> (`decision_card`, `resumen`, `eleccion`, `borrador_preview`, `cola`…). El CÓDIGO determinista la VALIDA y
> la RENDERIZA.** El LLM elige el *qué mostrar*; el plano decide y el código dispone el *cómo*. El LLM nunca
> emite HTML/JS ejecutable.

Esto es **server-driven UI**: el backend (Loombit) emite JSON, un renderer JS plano lo pinta. Sin reescribir
a React, sin nube, con el LLM fuera del camino de confianza. El esquema declarativo más maduro de referencia
es **Microsoft Adaptive Cards** (JSON→UI, MIT, renderer JS); se puede adoptar como base o inspirar un
vocabulario propio más pequeño y específico de "decisiones".

---

## 3. Investigación (web + GitHub) — con veredicto

### UI generativa / adaptativa
- **Vercel AI SDK "Generative UI"** (streamUI/RSC): production-ready pero React/Next. → **EVITAR** (stack).
- **Microsoft Adaptive Cards**: JSON declarativo, renderers multiplataforma (incl. JS), MIT. → **ADOPTAR/BASE**.
- **`json-render` (Vercel)** y la lista **`narrowin/awesome-generative-ui`**: patrón JSON→UI. → **APRENDER**.
- **`aladin2907/overhuman`**: el LLM genera HTML único por respuesta. → **EVITAR** (viola la Ley Fundacional);
  útil solo como prueba de hasta dónde llega la idea.
- **`CopilotKit` + AG-UI Protocol**: "frontend stack for agents & generative UI" (React). → **APRENDER** la
  idea de un *protocolo agente→UI*; implementarlo nosotros en JSON plano.

### Agentes de correo autónomos
- **Shortwave / Fyxer**: asisten (triaje, borradores) pero **el humano veta el envío**. **Alfred_** cierra el
  lazo (triaje + borrador + extracción de tareas + Daily Brief). → **APRENDER** el patrón
  *triaje → borrador → digest*. **Nuestro foso**: local/privado + decisión-como-UI + admin profundo
  (fiscal/cobros), no solo correo.

### Human-in-the-loop / cola de decisiones
- **LangChain `HumanInTheLoopMiddleware`** (aprobar/editar/rechazar tool calls antes de ejecutar): es
  **exactamente** nuestro `PENDING_APPROVAL` + `AuthorityPlane`. → **VALIDA** lo que ya tenemos.
- **`humanlayer/humanlayer`** (Python, `@require_approval`, cola async vía Slack/email/dashboard,
  permisiva): → **APRENDER** la cola async + niveles de autonomía + undo. Reutilizable como referencia
  (Python, encaja con nuestro backend).

**Licencias:** preferir permisivas (MIT/Apache); Adaptive Cards (MIT) y HumanLayer (Apache-2.0) son seguras
para producto propietario. Evitar copyleft fuerte (AGPL/GPL) en lo que se incruste.

---

## 4. Las necesidades (de código a lo visual)

| Capa | Qué falta construir |
|---|---|
| **Motor de decisiones** (backend) | Una `Decision` de primera clase (qué, por qué, opciones, reversibilidad, riesgo) que **se acumula en una cola**, no un chat. Se construye sobre el gate `PENDING_APPROVAL` + `AuthorityPlane`. |
| **Compositor de UI generativa** (backend) | Dado el estado, emite una **spec JSON** desde un vocabulario cerrado. El LLM elige *qué* mostrar; el código **valida** (whitelist de componentes) y rinde. |
| **Renderer adaptativo** (visual) | Módulo JS plano que pinta la spec → reutiliza la "Tela"/galaxia; la pantalla se reconfigura según la cola. |
| **Agente reactivo → autónomo** | De "responde cuando le hablas" a **trabajar en background** (routines) y **encolar decisiones**. **Niveles de autonomía graduados**: observa → propone → actúa-con-gate → actúa-solo en lo reversible. |
| **Correo: contexto → triaje autónomo** | Hoy hay `gmail_search` para contexto; falta el lazo *leer todo → clasificar → redactar → subir solo la decisión*. |

---

## 5. Cómo encaja con lo que YA tenemos (no se reinventa)

| Pieza existente | Rol en la visión |
|---|---|
| `telar.py` (tela proactiva) | **se convierte en la cola de decisiones** |
| gate `PENDING_APPROVAL` + `policy/authority_plane.py` | **el motor de decisiones** (ya distingue ejecutar/aprobar/rehusar) |
| `comprension.py` | **la percepción** (quién/qué/estado) que alimenta las decisiones |
| `routines.py` / `scheduler.py` | **el trabajo en segundo plano** que las genera |
| `static/` (Tela, galaxia, chat) | **el renderer** del vocabulario generativo |

La visión no es un giro: es **subir un piso** sobre el cerebro + el gobierno que ya existen.

---

## 6. La primera rebanada (fina, vertical, demostrable)

**Una `decision_card` generativa para UN cobro.** Loombit detecta el impago (el cerebro ya lo hace), prepara
el plan + el borrador, y te pone **una sola tarjeta de decisión generada** (aprobar / editar / posponer), sin
que toques nada. Prueba el lazo entero —percepción → decisión → UI generada (spec JSON validada) → efecto con
gate— en vertical, sobre código que ya existe. DoD: recibo en vivo + golden de la spec (vocabulario cerrado,
nunca HTML del LLM).

---

## 7. Riesgos (honestos)

- **El 14B local limita la autonomía real** hoy (por eso §14B). La autonomía se **gradúa y se mide**, no se
  promete. Empezar en "propone + gate", subir a "actúa-solo" únicamente en lo reversible y medido.
- **El vocabulario de UI debe ser CERRADO.** Si el LLM puede emitir HTML/JS, se reabre el agujero que §SEG/
  §GOB-1 cierran. La spec se valida contra una whitelist; el render es código.
- **Confianza = todo.** Un solo efecto erróneo no vetado rompe la promesa "tú solo decides". El gate de
  efecto y la reversibilidad/undo son innegociables.

---

*Esta es una dirección, no una promesa. Se construye por rebanadas verticales con recibo, sobre el gobierno
como cimiento. Si se queda corta, se mejora (Ley 0) — por su procedimiento (§META-3).*
