# Arquitectura de plataforma — LoomBit como SO que gobierna a Qwen

> **Tesis.** Qwen no es el producto: es el **motor cognitivo**. LoomBit es el **sistema operativo**
> que lo gobierna. Qwen *piensa y propone*; LoomBit *valida*; el operador *aprueba*; las herramientas
> *ejecutan*; todo *queda registrado*. Esto NO es un chatbot, y NO se "toca el cerebro" del modelo a mano.
>
> Este doc consolida la arquitectura ya existente en el repo (no inventa) y marca honestamente qué está
> 🟢 hecho / 🟡 contrato / ⬜ hueco. Es coherente con la **LEY FUNDACIONAL** de `docs/BRUJULA.md`:
> *el LLM nunca está en el camino de control de confianza para nada consecuente*.

---

## 0. Las cinco leyes de la plataforma — y su ESTADO REAL (auditado contra el código)

> Auditado leyendo `loop.py:706`, `policy/authority_plane.py::autorizar`, `tools/base.py`. **No vendas
> humo:** la columna "Estado real" dice lo que el código hace HOY, no lo que aspiramos.

| # | Ley | Quién la garantiza | Estado real |
|---|---|---|---|
| 1 | **Qwen propone, no dispone.** El modelo emite `tool(intención, datos)`; nunca ejecuta por sí mismo. | `agent/loop.py:706` → `AUTHORITY_PLANE.autorizar()` → `ToolRegistry.execute()` | 🟢 |
| 2 | **Datos ≠ órdenes (CaMeL).** IBAN/importe/destinatario NUNCA se confían al texto del modelo ni se liftean de contenido no confiable. | `authority_plane.valor_de_cuarentena` | **🟠 DORMIDA** — `loop.py:706` NO pasa `contenido_no_confiable` → el filtro nunca se dispara (el propio código lo marca como follow-up). Ver §18. |
| 3 | **Gate humano para todo efecto externo.** → PENDING_APPROVAL. | `requires_approval=True` + `AgentStatus.PENDING_APPROVAL` | 🟢 con fuga: `gmail_send` auto-envía si el destinatario es "claro" (sin tarjeta). |
| 4 | **Local-first.** Los datos no salen; el servidor solo escucha en 127.0.0.1. | `seguridad_web.py` (anti DNS-rebinding + CSRF) | 🟢 — pero contiene la **red de entrada**, NO la ejecución (ver §10). |
| 5 | **Todo deja recibo.** Nada es "hecho" sin registro auditable. | `AgentStore` + recibos en `runtime/local/` | 🟢 |

> **Lectura honesta:** 3 leyes 🟢, 1 dormida (🟠 CaMeL), y el sandbox (§10) ⬜. Las acciones para
> cerrarlo, priorizadas por valor×esfuerzo, están en §18 (backlog).

---

## 1. Qwen: qué tocar, qué no, qué es peligroso

Qwen2.5-14B-Instruct (rol `instructor`) + Qwen2.5-Coder-7B (rol `coder`), servidos por LM Studio en
`http://localhost:1234/v1` (API OpenAI-like). El cliente es `loombit_operator/llm.py`.

### 1.1 Qué SÍ se puede (y se debe) tocar — desde fuera, sin reentrenar
Todo esto es **gobierno externo**, reversible y versionable:

- **Decodificación.** `temperature` (hoy 0.2), `top_p`, `max_tokens` (512), `stop`, `seed`. → `config.py`.
- **Prompt de sistema.** El rol, las reglas y el "no eres un bot". → `agent/prompts.py::build_system_prompt`.
- **Catálogo de tools** que ve el modelo (function calling). → `tools/registry.py` (activación por intención).
- **Contexto inyectado**: memoria recuperada, hits de RAG, fecha de hoy, datos del usuario. → `agent/contexto.py`.
- **Gramática / salida forzada** (JSON-schema, grammars de llama.cpp) cuando se necesite salida estricta.
- **Modelo cargado**: cambiar de 14B a 7B-1M para contexto largo (fallback). → `config.py` (roles).

### 1.2 Qué NO conviene tocar
- **Los pesos del modelo.** Decisión de proyecto: *fine-tuning de pesos está fuera de alcance*
  (`CLAUDE.md` → "Lo que nunca hace"). El aprendizaje es **memoria operativa**, no pesos.
- **El tokenizer / la plantilla de chat del modelo** (chat template de Qwen): si la cambias a mano
  rompes el function calling y la coherencia. Deja que LM Studio aplique la del modelo.
- **El runtime del servidor LLM** (LM Studio / llama.cpp): trátalo como una caja negra reemplazable
  detrás de la API OpenAI-like. Hoy LM Studio, mañana `llama-server` en Jetson — sin tocar LoomBit.

### 1.3 Qué es PELIGROSO tocar
- **Fine-tuning de pesos en producción.** Riesgos: olvido catastrófico, alucinación de formato de
  tool-call, coste de re-evaluar todo el comportamiento, e *imposibilidad de auditar qué cambió*.
  Va en contra de la Ley 2 (el comportamiento consecuente debe ser código verificable, no pesos opacos).
- **Quitar el `stop` o subir `temperature` alto** en flujos consecuentes: aumenta la deriva y la
  invención de destinatarios/cifras. Mantén `temperature` baja para razonamiento operativo.
- **Dar al modelo una tool sin `requires_approval` que tenga efecto externo.** Es saltarse la Ley 3.
- **Inyectar contenido no confiable (correo/web leído) directo al prompt sin marcarlo como DATO.**
  Es la puerta de la inyección de prompt → lo maneja `authority_plane` (cuarentena CaMeL).

> Regla práctica: **si dudas entre tocar el modelo o tocar el orquestador, toca el orquestador.**
> El modelo se gobierna desde el código, no se reeduca a mano.

---

## 2. Arquitectura de 10 capas (pedida ↔ código real)

```
┌──────────────────────────────────────────────────────────────────────┐
│ (1) INTERFAZ LOCAL    static/index.html  +  routers/ui.py · home.py    │
│                       (single-page, 127.0.0.1:8787)                    │
└───────────────┬──────────────────────────────────────────────────────┘
                │ HTTP (solo local: seguridad_web.py)
┌───────────────▼──────────────────────────────────────────────────────┐
│ (2) ORQUESTADOR SEGURO                                                 │
│     routers/agent.py → agent/loop.py (ReAct)                           │
│     ├─ (7) PERMISOS / VALIDACIÓN  policy/authority_plane.py            │
│     │       + agent/guardas.py (guardas de dominio)                    │
│     ├─ (4) MEMORIA                agent/memory.py                      │
│     ├─ (5) RAG                    rag.py (embeddings locales)          │
│     ├─ (10) APROBACIÓN HUMANA     AgentRun.PENDING_APPROVAL            │
│     └─ (8) LOGS / RECIBOS         AgentStore + runtime/local/*.json    │
└───────┬───────────────────────────────┬──────────────────────────────┘
        │ propone tool(args)            │ ejecuta (tras validar+aprobar)
┌───────▼─────────────┐     ┌───────────▼──────────────────────────────┐
│ (3) QWEN LOCAL      │     │ (6) HERRAMIENTAS  tools/registry.py       │
│     llm.py          │     │     base · connectors · dominio · pilot   │
│     LM Studio /v1   │     │ (9) SANDBOX  ⬜ pendiente (ver §9)         │
└─────────────────────┘     └────────────────────────────────────────────┘
```

| # | Componente pedido | Módulo real | Estado |
|---|---|---|---|
| 1 | Interfaz local | `static/index.html`, `routers/ui.py`, `routers/home.py` | 🟢 |
| 2 | Orquestador seguro | `agent/loop.py`, `routers/agent.py` | 🟢 |
| 3 | Qwen local | `llm.py` + LM Studio | 🟢 |
| 4 | Memoria | `agent/memory.py`, `agent/memory_dedup.py` | 🟢 |
| 5 | RAG | `rag.py`, `routers/rag.py` | 🟡 (requiere embeddings cargados) |
| 6 | Herramientas | `tools/registry.py` + `base/connectors/dominio/pilot` | 🟢 contrato / 🟠 efectos reales |
| 7 | Permisos | `policy/authority_plane.py` + `safety_class` + `guardas.py` | 🟢 |
| 8 | Logs | `agent/run.py::AgentStore`, recibos en `runtime/local/` | 🟢 |
| 9 | **Sandbox** | `fabrica/seguridad.py` (solo código generado) | ⬜ **hueco real** |
| 10 | Aprobación humana | `requires_approval` + `PENDING_APPROVAL` + MCP gate | 🟢 |

---

## 3. Cómo se controla a Qwen desde código

El bucle ReAct (`agent/loop.py`) es el único que habla con el modelo. Ciclo:

1. `build_system_prompt()` + tarea + tools del registry → `LLMClient.chat()`.
2. El modelo devuelve **texto** (`stop`) **o** `tool_calls`.
3. Si `tool_calls`: **el loop NO ejecuta directamente.** Pasa la propuesta a `authority_plane`.
4. `authority_plane.decidir()` devuelve una de cuatro acciones:
   - `EJECUTAR` → corre la tool vía `ToolRegistry.get(name).execute()`.
   - `APROBAR` → `PENDING_APPROVAL` (gate humano).
   - `CORREGIR` → no ejecuta; devuelve mensaje al modelo para que reintente (p.ej. destinatario no resuelto).
   - `REHUSAR` → no ejecuta; rehúsa duro (p.ej. intento de manipulación).
5. Resultado de la tool → de vuelta al modelo → repite hasta `TASK_DONE` o `exceeded_max_steps`.

Robustez del transporte: `llm.py::_post_con_reintento` reintenta solo errores **transitorios**
(429/5xx, timeouts); un 400 (esquema/contexto) es determinista y lo arregla el recorte de contexto
(`agent/contexto.py`), no un reintento.

---

## 4. Prompt de sistema

Vive en `agent/prompts.py::build_system_prompt` — **es código, no una constante mágica**. Compone:
rol del operador + reglas duras (no revelarse como bot, no inventar destinatarios, no afirmar sin
recibo) + fecha de hoy + tools disponibles + datos del usuario (Skill W: nada hardcodeado de cliente).

Reglas:
- El system prompt **gobierna estilo y límites**, no es donde se ponen las salvaguardas consecuentes
  (esas son código en `authority_plane`; un prompt es *persuasión*, no *garantía*).
- Contenido no confiable (correo/web leído) **nunca** va en el system prompt; va en mensajes de
  usuario/tool marcados como DATO, sujetos a cuarentena CaMeL.

---

## 5. Memoria externa

`agent/memory.py` — memoria operativa persistente entre sesiones en `runtime/local/`, con
deduplicación (`memory_dedup.py`). Es la alternativa al fine-tuning: **el operador aprende
recordando, no recableando pesos**. La tool `memory_search` está en el piso de tools (ADMIN_BASE),
así que el agente nunca está ciego a su propia memoria.

Capas de memoria:
- **Corto plazo:** `AgentRun.messages` (el contexto del LLM de esta ejecución).
- **Largo plazo operativo:** `memory.py` (lecciones, hechos, preferencias del usuario).
- **Semántica:** RAG (§6) sobre el histórico vectorizado.

---

## 6. RAG

`rag.py` — índice semántico **local**. Vectoriza histórico (ejecuciones, lecciones, empresas,
contactos, procedimientos) con embeddings locales (`nomic-embed` vía LM Studio) y busca por
similitud. Vectores persistidos en `runtime/local/rag_index.json` — **nunca salen de la máquina**.
`embed_fn` es inyectable → tests deterministas sin red. Desbloquea: búsqueda en histórico,
procedencia ("¿de dónde saqué esto?") y recuperación de estilo propio.

---

## 7. Herramientas (tool use)

`tools/registry.py` — catálogo. Cada `ToolDefinition`:

```
name · description · parameters(JSON Schema) · fn · requires_approval · safety_class
```

- El modelo ve `to_openai()` (function-calling estándar).
- **Activación por intención:** no se exponen las ~44 tools de golpe; un piso (`CORE_TOOLS` +
  `ADMIN_BASE`) siempre disponible + grupos que se activan por palabras clave. Reduce alucinación de
  tool y coste de contexto.
- Familias: `base.py` (control del bucle), `connectors.py` (Gmail/Calendar/Graph), `dominio.py`
  (admin/fiscal), `pilot.py` + `computer.py` (control de escritorio), `documents.py`, `conciliacion`.
- **MCP:** `mcp_server.py` expone el mismo registry como servidor MCP (Skill A, adaptador puro), con
  el gate replicado en el servidor (defensa en profundidad: un cliente MCP externo no es de fiar).

---

## 8. Permisos — niveles

Dos ejes ortogonales, ambos ya en el código:

**Eje A — clase de seguridad de la tool (`safety_class` en `registry.py`):**

| Nivel | Significado | Ejemplo | Por defecto |
|---|---|---|---|
| `passive` | Solo lee/prepara, sin efecto externo | `gmail_search`, `web_fetch`, `read_invoice` | ejecuta directo |
| `assisted` | Prepara un efecto que el humano revisa | redactar correo, preparar evento | prepara → gate |
| `safety_sensitive` | Efecto externo real o acción de sistema | `gmail_send`, `calendar_create`, shell, pilot | **PENDING_APPROVAL** |
| `blocked_by_default` | Prohibida salvo habilitación explícita | comandos destructivos | rehúsa |

**Eje B — decisión del plano de autoridad (`authority_plane.Accion`):**
`EJECUTAR` · `APROBAR` · `CORREGIR` · `REHUSAR` (ver §3). Combina la clase de la tool con el contexto
(¿el destinatario está resuelto por código? ¿el valor viene de contenido no confiable? ¿hay intento
de manipulación?).

Regla de oro: **`requires_approval=True` para todo lo `safety_sensitive`.** Una sola puerta, en la
definición de la tool, no repartida por el código.

---

## 9. Logs y recibos

- **Traza de ejecución:** `agent/run.py::AgentStore` persiste cada `AgentRun` (estados, `messages`,
  `steps` con qué tool y qué devolvió) en `runtime/local/agent_runs.json`.
- **Recibos de capacidad (DoD):** un efecto real deja recibo JSON/HTML en `runtime/local/`
  (`docs/DEFINITION_OF_DONE.md`). **Sin recibo no hay 🟢.**
- **Recibos de conducta (D-70):** proponer una mejora / dar un veredicto deja un recibo cuantificable
  (`loombit_operator/conducta.py` → `docs/RECIBOS_CONDUCTA.jsonl`).
- **Outbox local:** `.eml` / `.ics` en `runtime/local/` cuando no hay credenciales cloud.

---

## 10. Sandbox — **el hueco real (⬜)**

Hoy NO hay aislamiento a nivel de SO para las tools de efecto. Lo que existe:
- `fabrica/seguridad.py` — sandbox **solo para código generado** por la fábrica de skills.
- `seguridad_web.py` — defensa de red (local-first), no de ejecución.
- El gate humano (`requires_approval`) — control de *autorización*, no de *contención*.

**Lo que falta diseñar/construir (P0 de seguridad):**
- Aislar `computer.py`/`pilot.py` (control de escritorio) y cualquier `shell` tras un perímetro:
  lista blanca de comandos, FS de solo-lectura salvo `runtime/local/`, sin red salvo allowlist.
- Tiempo/recursos acotados por tool (timeout, CPU/mem).
- Para Jetson: contenedor/namespace dedicado para tools `safety_sensitive`.

> Hasta que el sandbox exista, la contención efectiva es: `blocked_by_default` para lo destructivo +
> gate humano obligatorio + local-first. Es suficiente para el MVP, **no** para autonomía proactiva.

---

## 11. Cómo se evita que el modelo ejecute comandos peligrosos (defensa en profundidad)

1. **El modelo no ejecuta nada** — solo propone (Ley 1). El loop es el único actuador.
2. **`blocked_by_default`** — las tools destructivas no están ni en el catálogo por defecto.
3. **Gate humano** — todo `safety_sensitive` para en `PENDING_APPROVAL`.
4. **CaMeL / datos ≠ órdenes** — un valor consecuente (IBAN, destinatario, importe, URL) que aparezca
   literal en contenido no confiable se pone en cuarentena: el modelo no puede "liftearlo" de un correo.
5. **Resolución por código** — destinatarios vía `contacts_find`, no inventados por el texto.
6. **`REHUSAR` ante manipulación** — el plano detecta intentos de manipulación y rehúsa.
7. **Local-first** — una web visitada no puede pilotar el servidor (anti DNS-rebinding/CSRF).
8. **(Pendiente) Sandbox** — contención si algo se salta lo anterior.

---

## 12. Cuándo LoRA/QLoRA tendría sentido — y cuándo NO

**HOY: no entrenar.** El comportamiento se gobierna con prompt + tools + memoria + RAG. Es lo
reversible, auditable y barato. Coherente con `CLAUDE.md`: aprendizaje = memoria operativa.

**Cuándo SÍ consideraría LoRA/QLoRA (futuro, fuera de la cuña actual):**
- Cuando el **formato** falle de forma sistemática que el prompt no arregla (p.ej. function-calling
  inestable en un modelo concreto) y haya un eval que lo demuestre con número antes/después.
- Para **destilar un estilo o un dominio muy repetitivo** (jerga fiscal española) y bajar tokens de
  prompt — solo si RAG+prompt ya no dan más y hay golden set para medir regresión.
- Siempre **QLoRA** (4-bit) sobre adaptadores **separables y versionados**, nunca merge a los pesos
  base. El adaptador es un artefacto auditable que se puede quitar.

**Cuándo NO entrenar (la mayoría de los casos):**
- Para "que sepa mis datos" → eso es memoria/RAG, no pesos.
- Para "que obedezca una regla nueva" → eso es prompt + authority_plane.
- Para "que use bien una tool nueva" → eso es description + ejemplos en el prompt.
- Si no tienes un eval con métrica antes/después → entrenar es fe, no ingeniería (Ley del recibo D-70).

---

## 13. Estructura de carpetas (real + propuesta)

```
loombit_operator/
├── main.py                 # solo crea app + monta routers
├── launcher.py             # arranque (puerto 8787)
├── config.py               # Pydantic Settings (params LLM, modelos, rutas)
├── llm.py                  # (3) cliente Qwen — OpenAI-like + tool use + reintento
├── rag.py                  # (5) índice semántico local
├── seguridad_web.py        # local-first (anti rebinding/CSRF)
├── mcp_server.py           # expone el registry como MCP (Skill A)
├── policy/
│   └── authority_plane.py  # (7) plano de autoridad — la superficie de decisión
├── agent/                  # (2) orquestador
│   ├── loop.py             #     ReAct: el único que habla con Qwen y actúa
│   ├── run.py              # (8) AgentRun/AgentStore (estados + traza)
│   ├── prompts.py          #     system prompt
│   ├── memory.py           # (4) memoria operativa
│   ├── contexto.py         #     recorte/inyección de contexto
│   └── guardas.py          # (7) hook de guardas de dominio (pre-intent)
├── tools/                  # (6) herramientas
│   ├── registry.py         #     catálogo + safety_class + activación por intención
│   ├── base.py · connectors.py · dominio.py · pilot.py · computer.py …
├── routers/                #     un router por dominio (<400 líneas)
│   ├── agent.py · ui.py · home.py · rag.py · mcp.py · pilot.py …
├── skill_d_fiscal/         #     dominio fiscal (Skill D — no contamina el núcleo)
├── fabrica/                #     fábrica de skills (+ seguridad.py = sandbox de código)
├── static/index.html       # (1) interfaz local single-page
└── runtime/local/          # (8) recibos JSON/HTML, agent_runs.json, rag_index.json, outbox

# ⬜ propuesta nueva (hueco de §10):
└── sandbox/                # (9) contención de ejecución de tools safety_sensitive
    ├── policy.py           #     allowlist de comandos, límites FS/red/recursos
    └── runner.py           #     ejecuta una tool aislada (subproceso/contenedor)
```

---

## 14. Flujo de una petición (end-to-end)

```
Usuario (UI local)
  │  POST /agent/run            [seguridad_web: ¿Host/Origin local?]
  ▼
routers/agent.py → AgentRun(pending) → agent/loop.py
  │  1. guardas.py: ¿una guarda de dominio aplica? → abstención honesta y fin
  │  2. contexto.py: inyecta memoria + RAG + fecha + datos usuario
  │  3. build_system_prompt() + tools del registry
  ▼
llm.py → Qwen (LM Studio) ──► propone tool_calls
  ▼
policy/authority_plane.autorizar(tool, args, run, requires_approval)
  ├─ REHUSAR   → mensaje al modelo, no ejecuta
  ├─ CORREGIR  → mensaje al modelo (resuelve destinatario / cuarentena CaMeL)
  ├─ APROBAR   → AgentRun(pending_approval) ─► UI muestra tarjeta ─► operador aprueba
  └─ EJECUTAR  → ToolRegistry.execute() ─► resultado
  ▼
loop: resultado → modelo → repite … hasta TASK_DONE
  ▼
AgentStore persiste run + recibo en runtime/local/   (8 LOGS)
  ▼
UI muestra resultado + recibo
```

---

## 15. Roadmap por fases

| Fase | Objetivo | Estado |
|---|---|---|
| **F0** | Motor: llm.py + loop ReAct + registry + UI local | 🟢 |
| **F1** | Gobierno: authority_plane + gate humano + memoria + recibos | 🟢 |
| **F2** | Conectores reales (Gmail/Calendar) con recibo 🟢 + RAG con embeddings cargados | 🟡→🟠 |
| **F3** | **Sandbox** (§10): contención de tools `safety_sensitive`, allowlist, límites | ⬜ |
| **F4** | Routines proactivas seguras (cron/evento) — solo cuando F3 esté 🟢 | ⬜ |
| **F5** | Edge: despliegue Jetson (llama-server) + perfil de VRAM | ⬜ |

> Orden crítico sin dispersión, alineado con la cuña activa (VeriFactu + cobros del autónomo español):
> **cerrar F2 a 🟢 antes de abrir F3.** No hay proactividad (F4) sin sandbox (F3).

---

## 16. MVP recomendado (lo que YA es defendible hoy)

**"Operador de oficina local con aprobación humana", sin proactividad, sin sandbox aún:**

1. UI local (127.0.0.1) → escribes una tarea ("responde a Marta confirmando la reunión del jueves").
2. Qwen propone; el plano valida (resuelve el contacto por código, cuarentena de datos del correo).
3. Tools de **lectura** corren solas (`gmail_search`, `read_invoice`, `web_fetch`).
4. Tools de **efecto** (`gmail_send`, `calendar_create`) → **tarjeta de aprobación**; tú confirmas.
5. Si no hay credenciales cloud → cae a **outbox local** (`.eml`/`.ics`) — sigue siendo útil y auditable.
6. Todo deja recibo en `runtime/local/`.

**Por qué es el MVP correcto:** ejercita las 5 leyes con efecto real y recibo, sin exponer la
superficie peligrosa (ejecución autónoma / shell) que aún no tiene sandbox. Es honesto: 🟢 lo que
tiene recibo, 🟠 lo que depende de credenciales, ⬜ lo proactivo.

**Lo único que NO debe entrar en el MVP:** routines proactivas y cualquier tool de shell/escritorio
sin gate — eso espera a F3 (sandbox).

---

## 18. Análisis endurecido (5 ciclos) — red team, contratos y backlog

> Esta sección es el resultado de 5 ciclos de mejora encadenados sobre el análisis. Cada uno corrigió
> al anterior contrastando con el código. Lo que sigue es lo que NO se puede omitir.

### 18.1 Red team — las 4 vías por donde se rompe la cadena (por gravedad)

1. **🔴 El agente puede reescribir sus propios guardarraíles.** `tools/base.py::_write_file` escribe en
   cualquier ruta (`Path(path).expanduser()`, raíz `Path.cwd()`). El modelo —o una inyección— puede
   sobrescribir `loop.py`, `authority_plane.py`, `.env` o el token store → **escalada total**, anula
   todo lo demás. Es el peor riesgo y prerrequisito bloqueante de la autonomía (F4).
2. **🔴 Inyección de prompt → acción consecuente.** Como CaMeL está dormido (Ley 2 🟠), un correo de
   cliente con un IBAN/importe puede fluir a una propuesta de cobro. La única defensa hoy
   (`gmail_send` resuelve el destinatario) **no cubre IBAN ni importe**, ni otras tools.
3. **🟠 Auto-envío sin gate.** En `gmail_send`, `auto = (not proactive) and _destinatario_claro(to)` →
   si el destinatario parece "claro", se envía sin tarjeta. Las defensas no-bot/anti-manipulación son
   **regex** → evadibles por paráfrasis.
4. **🟠 Segunda puerta MCP.** `mcp_server.py` aplica el gate por `safety_class`; el loop lo aplica por
   `requires_approval`. **Dos mecanismos paralelos**: una tool mal etiquetada rompe la coherencia.

### 18.2 Contratos del sandbox (§10 hecho ingeniería)

```python
# sandbox/policy.py — política declarativa, determinista, testeable
@dataclass(frozen=True)
class SandboxPolicy:
    fs_write_roots: tuple[Path, ...]   # único sitio escribible (p.ej. runtime/local/)
    fs_deny: tuple[Path, ...]          # .env, token store, loombit_operator/** (AUTOPROTECCIÓN)
    cmd_allowlist: tuple[str, ...]     # binarios permitidos; resto → blocked_by_default
    net_allowlist: tuple[str, ...]     # hosts permitidos para web_fetch
    limits: ResourceLimits             # timeout_s, max_mem_mb, max_cpu_s

def check_fs_write(path, pol) -> Verdict   # resuelve symlinks/.. y valida raíz
def check_command(argv, pol) -> Verdict
def check_url(url, pol) -> Verdict

# sandbox/runner.py — contención de ejecución
def run_contained(fn, args, pol) -> Result:
    # 1) valida args vs policy ANTES de ejecutar  2) subproceso con setrlimit + timeout
    # 3) en Jetson: nsjail/firejail o contenedor para safety_sensitive
```

**Cableado mínimo (quirúrgico):** `_run_shell` (`shell=True`→argv+`check_command`); `_write_file`
(`check_fs_write`); `registry.execute` enruta `safety_sensitive` por `run_contained`. **Unificar gate
por `safety_class`** (una fuente de verdad loop+MCP; `requires_approval` pasa a derivado).

**DoD — suite de inyección (§SEG):** test-set que DEBE bloquear: escribir en `loop.py`, leer `.env`,
`rm -rf`, `web_fetch` a host externo, IBAN inyectado desde correo. Sin suite verde, sandbox ≠ 🟢.

### 18.3 Valor estratégico (cuña: autónomo español · VeriFactu + cobros)

- **CaMeL no es abstracto: es la amenaza exacta de la cuña.** El ancla (cobros/morosidad) **lee
  correos de clientes** (contenido no confiable) con **IBAN/importe** → wirear CaMeL es **P0 de la
  cuña**, no "P2 seguridad".
- **Recibo encadenado (hash chain) sirve dos amos:** confianza demostrable + rastro de cumplimiento
  **VeriFactu** (registro encadenado factura→registro→303). Un trabajo, dos fosos.
- **"Local + no puede hacer daño" es argumento de VENTA verificable** frente a las SaaS cloud.

### 18.4 Backlog priorizado (orden de ataque)

| # | Acción | Valor | Esfuerzo | Prio |
|---|---|---|---|---|
| P0a | Wirear CaMeL en `loop.py:706` (`contenido_no_confiable`) + cobertura IBAN/importe + test inyección | 🔴 alto (cuña) | bajo | **P0** |
| P0b | `fs_deny` autoprotección en `write_file`/`run_shell` (prohibir `loombit_operator/**`, `.env`, token) | 🔴 alto (anti-escalada) | bajo-medio | **P0** |
| P1a | `sandbox/` (policy+runner) + límites recursos + suite §SEG | medio-alto | medio-alto | **P1** |
| P1b | Recibo encadenado (hash chain) reutilizable VeriFactu | alto (foso doble) | medio | **P1** |
| P2 | Unificar gate por `safety_class` (loop+MCP una sola verdad) | medio (deuda) | bajo | **P2** |

> **La ÚNICA acción siguiente si solo haces una:** **P0 (CaMeL + valla de autoprotección).** Dos
> cambios pequeños que cierran las dos vías 🔴 y desbloquean cuña (cobros) y autonomía (F4). El
> sandbox completo (P1) viene después; estos dos no esperan.

---

## 19. Ronda 2 (5 ciclos) — cognición, ledger, determinismo, coste, apuesta

> Segunda ronda de mejora, apuntando a producto/foso/viabilidad (la ronda 1 fue seguridad). Todo
> contrastado con el código: el repo tiene MÁS máquina de la que el diseño asumía, a medio cablear.

### 19.1 Hallazgos de verdad-terreno (corrigen suposiciones)
- **Cognición existe pero desconectada:** `comprension.py` (cognición de bandeja en background +
  persistida), `expedientes.py` (CaseFile neutro), `telar.py` (la tela) comprenden los hilos — pero
  **`agent/contexto.py` NO inyecta ese estado** → el agente planifica ciego al modelo de mundo.
- **La cadena de hashes YA existe** en `expedientes.py` (`verify_chain` + `sha256`), pero
  **`AgentStore` (`run.py`) no encadena** las acciones del agente.
- **Cifras deterministas en la práctica** (`modelo_303.calcular_303`, `intake.inferir_tipo_iva` en
  `Decimal`) pero **sin candado** que impida al LLM colar un número.
- **Sin routing de modelos:** instructor 14B / coder 7B definidos en config, pero todo va al 14B.

### 19.2 Propuestas de gran valor (conectar lo que existe)

| # | Propuesta | Reusa | Valor | Esfuerzo |
|---|---|---|---|---|
| C6 | Inyectar estado de expediente/comprensión en `contexto.py` antes del ReAct | comprension.py, expedientes.py | foso "comprensión profunda" hecho acción | medio |
| C7 | Enrutar acciones del agente como eventos en la cadena del CaseFile | expedientes.py (hash chain) | recibo inmutable + rastro VeriFactu, un solo ledger | bajo-medio |
| C8 | Candado de procedencia numérica en authority_plane + property tests (Hypothesis) sobre `calcular_303` | modelo_303.py | ancla fiscal a prueba de construcción, no de disciplina | bajo |
| C9 | Router por dificultad (7B/clasificador→14B solo lo duro) + presupuesto VRAM/latencia; generalizar el patrón "LLM fuera del camino caliente" de comprension.py | llm.py roles, config | usable en Jetson 16GB (fricción cero) | medio |

### 19.3 North-star y secuencia integrada (rondas 1+2)

**North-star (BRÚJULA):** *% de tareas cerradas al 100% sin que el usuario revise tu trabajo.*

| Orden | Bloque | Origen | Por qué ahora |
|---|---|---|---|
| **P0** | CaMeL wired + valla autoprotección `write_file` | R1 §18 | cierra 2 vías 🔴; barato; desbloquea cuña + F4 |
| **P1-a** | Expediente/comprensión → `contexto.py` | R2·C6 | el agente actúa con cognición real |
| **P1-b** | `AgentStore` → cadena de hashes del CaseFile | R2·C7 | recibo inmutable + VeriFactu reusando lo que hay |
| **P1-c** | Candado de procedencia numérica + property tests 303 | R2·C8 | ancla fiscal a prueba de construcción |
| **P1-d** | Router de modelos + presupuesto VRAM/latencia | R2·C9 | usable en Jetson |
| **P2** | `sandbox/` completo + unificar gate por `safety_class` | R1 §18 | contención total para autonomía F4 |

**La apuesta:** el foso no es "otro agente con tools" — es un operador que (1) entiende el hilo,
(2) nunca calcula lo consecuente, (3) deja rastro inmutable y (4) cabe y responde en local en Jetson.
Las 4 piezas ya tienen máquina a medio cablear; el trabajo de mayor valor es **conectarlas al camino
del agente**, no construir desde cero.

---

## 20. Ronda 3 (5 ciclos) — nuevas Skills propuestas (con radar real)

> Cada propuesta pasó el radar (D-90): fuente real en `docs/RADAR.jsonl` (señales 2026-06-14). Las
> skills respetan la taxonomía (C>W>G>D>A>X) y las leyes (gate, local-first, cifras por código, ledger).

### 20.1 Skills nuevas propuestas

| Código | Skill | Rol | Reusa del repo | Fuente (radar) |
|---|---|---|---|---|
| `Skill A` | **Visión Documental** | Qwen-VL local: lee facturas/PDF/escaneo, extrae campos | `read_invoice` + candado numérico (§19 C8) | SLM/Qwen-VL on-device |
| `Skill A` | **WhatsApp Connector** | recordatorios de cobro con tono escalado + enlace de pago | `decisions_cobros.py` | WhatsApp 3x cobro |
| `Skill A` | **Open Banking (AISP)** | importa movimientos (OPT-IN) → auto-concilia, morosidad real | `conciliacion_cobros.py` | PSD2/PSD3 AISP |
| `Skill D` | **VeriFactu** | hash encadenado + QR + export AEAT + registro de eventos | `expedientes.py` (chain), `verifactu.py` | VeriFactu jul-2026, multas 50k€ |
| `Skill G` | **Del cobro al 303** | golden path end-to-end que orquesta las D/A | todo lo anterior | — |
| `Skill X` | **Voz/Teléfono (lab)** | recordatorio de cobro por voz (TTS/ASR local) | — | experimental |

### 20.2 Reglas que cumplen (no son humo)
- **Cifras:** Visión Documental PROPONE, pero `calcular_303`/`inferir_tipo_iva` (Decimal) DISPONEN (candado §19 C8).
- **Efectos externos:** WhatsApp/Open Banking/VeriFactu→AEAT pasan por **gate humano** (Ley 3) y entran en el **ledger encadenado** (§19 C7).
- **Contenido no confiable:** OCR de Visión y movimientos de Open Banking entran como DATO → **exigen CaMeL wired** (R1·P0) ANTES de construirse, o son inyectables.
- **Adapters reemplazables:** las `Skill A` no contaminan el núcleo; el gate se replica (unificar por `safety_class`, R1·P2).

### 20.3 Secuencia por valor × deadline
1. `Skill A WhatsApp Cobros` — máximo ROI comercial (ataca morosidad ya).
2. `Skill D VeriFactu` — deadline jul-2026/2027, reusa la cadena existente.
3. `Skill A Visión Documental` — intake real de facturas.
4. `Skill A Open Banking` — cierra el lazo de conciliación.
5. `Skill G Del cobro al 303` — los une cuando los 4 estén 🟢.

**Precondición:** R1·P0 (CaMeL + valla autoprotección) va DELANTE de estas skills — las que leen contenido
no confiable (Visión, Open Banking) son inyectables sin él.

---

## 21. Ronda 4 (5 ciclos) — familia Skill D fiscal + mejoras de núcleo (radar real)

> Profundiza los 4 hilos de la ronda 3 con fuentes reales (señales 2026-06-14 en `docs/RADAR.jsonl`).
> Corrige el alcance: la cuña son **3 obligaciones + morosidad**, no solo VeriFactu.

### 21.1 La cuña regulatoria es TRIPLE (hallazgo que corrige el plan)
VeriFactu ≠ Facturae ≠ SII, y son **complementarias**:
- **VeriFactu** — integridad del software (Ley Antifraude); autónomos jul-2026/2027.
- **Facturae** — formato XML B2B obligatorio (Crea y Crece, **RD 238/2026**, reglamento 1-oct-2026;
  jul-2027 >8M€, jul-2028 resto; público vía FACe). El software VeriFactu **genera** Facturae.
- **SII** — libros de IVA → alimenta el 303.

### 21.2 Familia Skill D fiscal (sobre `expedientes` cadena + candado numérico + gate)

| Skill D | Obligación | Cálculo determinista | Deadline | Fuente radar |
|---|---|---|---|---|
| VeriFactu | integridad + registro AEAT | hash chain (existe) | autónomos jul-2026/2027 | b2brouter |
| **Facturae** | XML B2B + FACe | — | RD 238/2026 (1-oct-2026) | marimón / sage |
| **SII** | libros IVA | agregación | régimen IVA | sage |
| **Morosidad** | Ley 3/2004 | interés 10,15% + 40€ + días | continuo | BOE 3/2004 |
| 303 | liquidación IVA | `calcular_303` (existe) | trimestral | — |

`Skill D Morosidad`: el cálculo (interés 10,15% = BCE 2,15%+8, 40€ fijos, día 61) es DETERMINISTA;
`Skill A WhatsApp/email` NARRA la cifra **citando la ley** → cobro fundado y más efectivo.

### 21.3 Mejoras de NÚCLEO (Skill W) que sostienen todas las skills
- **Constrained decoding (V18):** `llm.py` usa gramática de llama.cpp/XGrammar para extracción crítica
  → 100% schema-válido (vs 95-99% del function-calling). "Cero fallos" en formato, no por suerte.
  Fuente: structured output 2026 (pockit).
- **Spotlighting + RAG con procedencia (V19):** 2ª capa sobre CaMeL — delimitadores aleatorios que
  marcan el contenido leído como DATO opaco; `rag.py` puntúa confianza por documento (anti RAG
  poisoning: 5 docs → 90%). Fuente: OWASP LLM01 / zylos / Gemini defenses.

### 21.4 Secuencia actualizada (valor × deadline)
1. **R1·P0 + Spotlighting** — base de seguridad antes de todo (las skills leen contenido no confiable).
2. `Skill A WhatsApp Cobros` + `Skill D Morosidad` — máximo ROI, con base legal.
3. `Skill D Facturae` (RD 238/2026 oct-2026) + `Skill D VeriFactu` emitiendo Facturae.
4. `Skill A Visión Documental` + constrained decoding (V18) — intake fiable.
5. `Skill A Open Banking` + `Skill D SII` → conciliación + libros; `Skill G Del cobro al 303` los une.

---

## 17. Resumen ejecutivo

- Qwen = motor. LoomBit = SO. El modelo **propone**; el código **dispone**; el humano **aprueba**.
- Casi toda la arquitectura **ya existe** y está gobernada por `policy/authority_plane.py` + el gate
  humano. El hueco real es el **sandbox de ejecución (§10)**.
- **No reentrenar** hoy: prompt + tools + memoria + RAG cubren el comportamiento, y son reversibles,
  auditables y baratos. LoRA/QLoRA solo con eval que demuestre mejora, y siempre como adaptador
  separable, nunca merge a los pesos.
- MVP = operador de oficina local con aprobación humana y recibos; proactividad y shell esperan al sandbox.
