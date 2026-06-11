# Investigación — Asistente proactivo, local-first y que aprende de hábitos (2026)

> Investigación multi-fuente (web, verificada) sobre cómo se construye, a nivel profesional y de
> vanguardia, un asistente como **Gemini Spark** y sus competidores, traducida a propuestas
> concretas para Loombit DENTRO de su gobernanza (local · cifras deterministas en código · el LLM
> narra/propone, el código dispone · ningún efecto externo se auto-escala). *Generado 2026-06-11.*

## 0. Regla canónica que sale de aquí

> **Creatividad gobernada.** En cada tarea, trae ≥1 idea del estado del arte (memoria, aprendizaje,
> UX de agentes) y **aplícala DENTRO de la gobernanza**: local, cifras deterministas en código, el
> LLM narra/propone y el código dispone, y **ningún efecto externo se auto-escala**. La creatividad
> vive en percibir→aprender→anticipar→preparar; nunca en saltarse el gate de aprobación.

## 1. Qué hacen Spark y los competidores (verificado)

- **Gemini Spark** corre en **VMs de Google Cloud, NO on-device** (Gemini 3.5 Flash + harness
  "Antigravity"). Tres primitivas, definidas en lenguaje natural: **Tasks** (objetivo), **Schedules**
  (cron/condición), **Skills** (patrones reutilizables auto-detectados). Brief matinal cruza
  bandeja+calendario+tareas y **prioriza + sugiere próximos pasos**. Permisos **opt-in por app, off
  por defecto**; enviar/pagar requiere aprobación.
  [blog.google IO 2026](https://blog.google/innovation-and-ai/sundar-pichai-io-2026/) ·
  [gemini.google/spark](https://gemini.google/overview/agent/spark/)
- **Fatiga de aprobación (hallazgo clave, Anthropic):** los usuarios aprobaron ~93% de las peticiones
  y la diligencia cae con el volumen. Mitigación: **Plan Mode** — revisar/editar/aprobar el plan
  entero por adelantado, no acción por acción.
  [anthropic.com/how-we-contain-claude](https://www.anthropic.com/engineering/how-we-contain-claude)
- **Microsoft Recall** analiza on-device — prueba de que lo local es viable.
  [learn.microsoft.com/Recall](https://learn.microsoft.com/en-us/purview/dlp-recall-get-started)
- **Patrones estándar de facto** (OpenAI Pulse/Tasks, Copilot Memory, Claude, Martin): brief matinal
  en tarjetas finitas con freno anti-engagement; workflows que corren sin el usuario; permisos por
  acción + HITL (leer libre, actuar fuera se aprueba/edita/rechaza); memoria editable que aprende del
  usuario; automatizaciones enseñables por demostración.
  [ChatGPT Pulse](https://techcrunch.com/2025/09/25/openai-launches-chatgpt-pulse-to-proactively-write-you-morning-briefs/) ·
  [Copilot Memory](https://techcommunity.microsoft.com/blog/microsoft365copilotblog/introducing-copilot-memory-a-more-productive-and-personalized-ai-for-the-way-you/4432059)

## 2. Estado del arte de ingeniería

### Memoria de agente
- **MemGPT/Letta**: memoria por capas (core editable en contexto / recall / archival vía tool-call),
  inyección **selectiva** (el código compila qué entra; el LLM nunca ve todo).
  [MemGPT 2310.08560](https://arxiv.org/abs/2310.08560) · [Letta memory blocks](https://www.letta.com/blog/memory-blocks)
- **Generative Agents**: recuperación `score = recency·importance·relevance`; recency y relevance las
  calcula **código**, importance la sugiere el LLM pero se **normaliza** en código.
  [2304.03442](https://arxiv.org/abs/2304.03442)
- **Store local**: `sqlite-vec` (KNN dentro de SQLite, sin dependencias) o FAISS.

### Aprender de hábitos SIN fine-tuning
- **PRELUDE/CIPHER**: infiere la preferencia latente del usuario de **aceptar/editar/rechazar** y del
  **diff al editar**. [2404.15269 (NeurIPS'24)](https://arxiv.org/abs/2404.15269)
- **Reflexion + ExpeL**: destilar "insights" en lenguaje natural reutilizables de cada flujo.
  [Reflexion 2303.11366](https://arxiv.org/abs/2303.11366) · [ExpeL 2308.10144](https://arxiv.org/abs/2308.10144)
- **Thompson sampling / contextual bandits**: priorizar/anticipar qué preparar primero, con la señal
  HITL como recompensa. [2306.14834](https://arxiv.org/pdf/2306.14834)

### Autonomía gradual (trust calibration)
- **Dato empírico (Anthropic):** la auto-aprobación sube con la experiencia (≈20%→40% con 750+
  sesiones), pero los expertos **interrumpen más** (≈9% vs 5%) — supervisión activa, no desconexión.
  [anthropic.com/measuring-agent-autonomy](https://www.anthropic.com/research/measuring-agent-autonomy)
- **Niveles de autonomía** (analogía SAE J3016): la frontera la marcan el dominio acotado, la
  responsabilidad de la acción y el fallback humano.
  [Levels of autonomy](https://arxiv.org/abs/2506.12469) ·
  [CSA](https://cloudsecurityalliance.org/blog/2026/01/28/levels-of-autonomy)
- **HITL**: approve/edit/reject con checkpoints persistentes (LangGraph `interrupt()`); "human-in"
  (bloquea cada acción de riesgo) vs "human-on" (monitoriza y puede interrumpir); aprobación
  escalonada por consecuencia (rutinario libre · riesgo confirma · irreversible sign-off).
- **Guardrails**: allow-list de tools + clasificación de riesgo (bajo ejecuta / medio notifica / alto
  autoriza); el guardrail corre **antes** de cualquier side-effect; dry-run/preview antes de ejecutar.

### Código profesional para agentes (maduro, a adoptar)
- **Constrained decoding** (xgrammar/outlines) > "JSON mode": JSON inválido imposible.
  [Beyond JSON mode](https://tianpan.co/blog/2025-10-29-structured-outputs-llm-production)
- **El LLM narra, el código calcula** (= regla nº1, validada por la industria).
  [Anthropic building effective agents](https://www.anthropic.com/research/building-effective-agents)
- **Context engineering** ("context rot": +tokens = −precisión): tool-sets mínimos, note-taking en
  ficheros, sub-agentes que devuelven resúmenes.
- **Evals en el gate de CI + mutation testing** (Meta a escala) = nuestro gobierno.
- **Modelos pequeños capaces**: Qwen 4B ganó un eval de tool-calling con 97.5% (no hay correlación
  tamaño↔tool-calling).
- **Vanguardia**: grafo de conocimiento **temporal** local (estilo Zep/Graphiti, bitemporal) para
  quién-es-quién/estado/plazos = "cognición, no extracción". [Zep 2501.13956](https://arxiv.org/abs/2501.13956)
  Y **event sourcing** (JSONL append-only) como columna de auditoría y base de "deshacer".

## 3. Diseño Loombit: "la autonomía que se gana"

**Invariante:** las aprobaciones repetidas suben la **anticipación/preparación/prioridad**, pero el
**efecto externo (enviar, pagar, borrar, crear evento) lo aprueba SIEMPRE el humano** con un toque.
Loombit nunca cruza a "human-on-the-loop" para side-effects externos; solo afina cuánto prepara y
cuán arriba lo pone.

**Niveles de ANTICIPACIÓN (por tipo de acción × contraparte, no global):**
- **A0 Reactivo** — solo actúa si se lo piden.
- **A1 Sugiere** — detecta el patrón y lo propone en el feed; aún no prepara.
- **A2 Pre-redacta (dry-run)** — deja el borrador completo en *preview* a 1-clic. El envío sigue
  requiriendo confirmación.
- **A3 Anticipa + agenda** — dispara por cron/evento y deja el borrador preparado *antes* de pedirlo,
  arriba, con su contexto. Aun así: tarjeta de confirmación para el efecto externo, sin excepción.

**Transiciones (deterministas; el código decide, el LLM propone):**
- **Subir:** ≥ N aprobaciones consecutivas *sin edición sustancial* del mismo tipo de acción y clase
  de destinatario.
- **Bajar (instantáneo, asimétrico):** 1 rechazo / 1 edición fuerte / cambio de contexto → baja un
  nivel. La confianza se gana lento y se pierde rápido.
- **Techo duro:** ningún tipo de acción externa supera A3. No existe "A4 = envía solo".
- **Recibo:** cada transición y aprobación deja recibo auditable en `runtime/local/` (quién/qué/cuándo
  + si hubo edición), reusando el patrón de recibos 🟢. Eso alimenta la subida/bajada de nivel.

## 4. Backlog de implementación (informado por la investigación)

1. **`habitos.py` v1 (HECHO):** ledger de decisiones aceptar/editar/rechazar/ignorar + veredicto
   determinista + `autonomia_sugerida`. Base PRELUDE/HITL.
2. **Aprender del *diff* al editar** (PRELUDE): cuando el usuario edita un borrador, guardar el delta
   y derivar la preferencia (tono, firma, hora de envío).
3. **Priorizador determinista del telar** (`recency·importance·relevance`): el orden lo decide código;
   el LLM solo aporta "importance" normalizada.
4. **Niveles de anticipación A0–A3** sobre `habitos.py` + el semáforo de routines, con las reglas de
   transición de §3 y recibo por transición.
5. **Cableado HITL→aprendizaje:** que cada approve/reject real alimente el ledger.
6. **(Vanguardia, Skill X) grafo temporal local** para el TELAR; **memoria por capas** (Letta) como
   evolución de `agent/memory.py`.

**Honestidad:** algunos preprints arXiv de 2026 no se usan como fuente primaria por no poder
validarlos a fondo; los detalles on-device/cloud de Spark son los oficiales (todo en VM cloud).
