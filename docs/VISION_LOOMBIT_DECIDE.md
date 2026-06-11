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

> **Recibo de lectura (§INNOVACIÓN — un veredicto exige haber LEÍDO la fuente, no su titular). 2026-06-11:**
> - **LEÍDO ÍNTEGRO** (la lectura cambió el veredicto en ≥2 casos): Adaptive Cards overview (learn.microsoft.com)
>   + repo `microsoft/AdaptiveCards` · Vercel AI SDK RSC docs · repo `humanlayer/humanlayer` · LangChain
>   middleware docs · repo `ag-ui-protocol/ag-ui`. (6 fuentes.)
> - **SOLO BÚSQUEDA, sin lectura íntegra** (veredicto provisional, marcado): `aladin2907/overhuman` ·
>   `narrowin/awesome-generative-ui` · `json-render` · Shortwave / Fyxer / Alfred_.

### UI generativa / adaptativa
- **Microsoft Adaptive Cards** *(leído)*: JSON **"purely declarative — no code is needed or allowed"**;
  payloads **safe** ("you don't have to open up your UI framework to raw markup and scripting", "reduce risk
  of custom code injection"). Renderer JS = npm **`adaptivecards`**. **MIT verificado** (código fuente + paquetes
  npm; los binarios UWP/.NET/móvil sí llevan EULA aparte de Microsoft, pero el camino JS que usaríamos es MIT).
  → **ADOPTAR/BASE.** *La lectura lo refuerza:* sus principios ("no code allowed", "safe payloads") **son la
  Ley Fundacional aplicada a la pantalla** — no solo "encaja", la encarna.
- **Vercel AI SDK "Generative UI" (RSC)** *(leído)*: la propia doc dice ***"AI SDK RSC is currently
  experimental. We recommend using AI SDK UI for production"*** y empuja a migrar fuera de RSC. React/Next.
  → **EVITAR** (stack + experimental hasta en su propio ecosistema). *Corrección:* el doc lo llamaba
  "production-ready"; **no lo es** ni para Vercel.
- **`json-render` / `narrowin/awesome-generative-ui`** *(solo búsqueda)*: patrón JSON→UI. → **APRENDER**
  *(provisional, sin lectura íntegra)*.
- **`aladin2907/overhuman`** *(solo búsqueda)*: el LLM generaría HTML único por respuesta. → **EVITAR**
  *(provisional)* — si se confirma, viola la Ley Fundacional; útil solo como prueba de hasta dónde llega la idea.
- **AG-UI Protocol (`ag-ui-protocol/ag-ui`)** *(leído)*: **protocolo abierto MIT, framework-agnóstico**, event-based
  (~16 tipos de evento, transporte SSE/WebSocket/webhook); CopilotKit es **solo un cliente de referencia (React)**,
  no el protocolo. → **APRENDER / CANDIDATO A BASE del vocabulario evento agente→UI** (en JSON plano). *Corrección:*
  el doc lo ataba a "CopilotKit (React)"; el protocolo en sí **no depende de React** y es reutilizable.

### Agentes de correo autónomos
- **Shortwave / Fyxer / Alfred_** *(solo búsqueda)*: asisten (triaje, borradores); algunos cierran más lazo
  (digest, extracción de tareas), pero el envío lo veta el humano. → **APRENDER** el patrón
  *triaje → borrador → digest* *(provisional, sin lectura íntegra de cada producto)*. **Nuestro foso**:
  local/privado + decisión-como-UI + admin profundo (fiscal/cobros), no solo correo.

### Human-in-the-loop / cola de decisiones
- **LangChain `HumanInTheLoopMiddleware`** *(leído)*: **verificado** que **interrumpe antes de ejecutar** las
  tools marcadas (`interrupt_on={"tool": True}`, "before tool execution"). Es el mismo principio que nuestro
  `PENDING_APPROVAL` + `AuthorityPlane`. → **VALIDA** el patrón. *Corrección honesta:* el trío exacto
  "aprobar/editar/rechazar" **no lo confirma la página que leí** — confirmado solo el gate-antes-de-tool por nombre.
- **`humanlayer/humanlayer`** *(leído)*: ⚠️ **corrección importante** — el repo hoy encabeza **CodeLayer**, un IDE
  open-source de agentes de código (**TypeScript ~59% + Go ~33%**), no el SDK Python que el borrador describía. El
  **SDK Python** (`pip humanlayer` 0.7.9, `@hl.require_approval()`, cola async vía Slack/email/dashboard, Apache-2.0)
  **sigue existiendo pero está siendo *superseded* por CodeLayer**. → **APRENDER** el patrón (require_approval + cola
  async + niveles de autonomía) como **referencia conceptual**, **no** como dependencia viva en crecimiento.

**Licencias (verificadas):** Adaptive Cards **MIT** (código + npm) · AG-UI **MIT** · HumanLayer **Apache-2.0**.
Todas seguras para producto propietario. Evitar copyleft fuerte (AGPL/GPL) en lo que se incruste.

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
