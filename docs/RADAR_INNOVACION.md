# Radar de innovación — ideas proactivas (documento vivo)

> **Mantenido por Claude de forma proactiva** (y, en el futuro, por una routine "tech-radar"
> que barre normativa + estado del arte). El objetivo: que las ideas de "lo último para
> administrativos" lleguen **sin que Fernando tenga que buscarlas**. Cada idea con su madurez,
> encaje de fase y acción. Las que se aprueban pasan a `INNOVACIONES.md` / al roadmap.
> *Última actualización: 2026-06-08.*

**Madurez:** 🟢 probado en producción en el sector · 🟡 emergente sólido · 🔵 experimental.

| # | Idea | Por qué para Loombit | Madurez | Fase | Acción |
|---|---|---|---|---|---|
| R1 | **Evals como ciudadanos de primera** (los supuestos = tests automáticos de cada skill) | una skill no está 🟢 hasta pasar sus evals; lo que enseña el `skill-creator` | 🟢 | transversal | adoptar como método (ver `FABRICA_DE_SKILLS.md`) |
| R2 | **Verificación determinista del dinero** (IVA/totales/intereses en código, el LLM solo narra) | los LLM suman mal; en finanzas es inaceptable | 🟢 | 3 | regla de implementación en `Skill D Cobros/Fiscal` |
| R3 | **Razonamiento con procedencia + abstención** (cita BOE/AEAT; si duda, escala) | foso de confianza + antídoto a "no inventar" | 🟡 | 3-6 | base de `Skill D Fiscal/Laboral` |
| R4 | **Autonomía que se gana** (el semáforo sube de tier lo aprobado N veces) | confianza que compone por acción×cliente | 🟡 | 4 | extensión del semáforo (#2) |
| R5 | **Auto-crítica antes de presentar** (Reflexion/self-refine en salidas de alto riesgo) | menos errores en lo legal/fiscal sin intervención | 🟡 | 5 | paso opcional en `agent/loop` |

## Hallazgos del barrido en vivo (2026-06-08)

Primer barrido tech-radar (Claude + web), con fuentes.

| # | Hallazgo | Implicación para Loombit | Madurez | Fase | Fuente |
|---|---|---|---|---|---|
| L1 | **Meta Business Agent en WhatsApp** (global, jun 2026): reserva citas, cualifica leads, conecta a Shopify/Zendesk; 10M conversaciones/semana | valida el WhatsApp-Pilot **y** es competencia. Foso de Loombit: **local/privado + opera TU WhatsApp sin que los datos salgan + profundidad administrativa** (cobros, fiscal). Integrar, no competir de frente. | 🟢 | 6/Pilot | [TechCrunch](https://techcrunch.com/2026/06/03/metas-ai-agent-for-whatsapp-business-is-now-available-globally/) |
| L2 | **VeriFactu — plazos precisos + factura-e B2B**: IS antes 1-ene-2027, resto antes 1-jul-2027; factura-e B2B obligatoria 1-oct-2027 (>8M€) y 1-oct-2028 (resto); **multa 50.000€/ejercicio** por software no conforme; 2026 = transición | `Skill D Fiscal` debe **emitir conforme VeriFactu** (QR + "VERI*FACTU"); el 50k€ es argumento de venta directo | 🟢 (ley) | 4+ | [AEAT](https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/cuestiones-generales.html) · [Holded](https://www.holded.com/es/blog/autonomos-2026-adaptarse-factura-electronica) |
| L3 | **Qwen3-VL (2b/4b/8b)** disponible — sucesor del VL para leer facturas escaneadas, corre local | candidato a **upgrade del VL-7B** al cablear la visión (`docs_intel`); evaluar 4b/8b en la RTX 5080 | 🟡 | 3/6 | [SiliconFlow](https://www.siliconflow.com/articles/en/best-open-source-LLM-for-Document-screening) |
| L4 | **Agentes contables autónomos** (Pilot "AI Accountant" feb-2026; Intuit+Anthropic; adopción agentic 6%→44% en 12 meses) | el mercado va a agentic ya; el foso de Loombit es **local + marco legal español + opera-sin-API**; los rivales son cloud/US | 🟢 | estratégico | [Beancount.io](https://beancount.io/blog/2026/05/10/agentic-ai-bookkeeping-2026-autonomous-finance-agents-month-end-close-ap-reconciliation-workflows-guide) · [Accounting Today](https://www.accountingtoday.com/news/a-big-year-for-ai-in-accounting) |

## Barrido 2 — asistentes de IA de correo (2026-06-08)

Destilado de ~20 productos (Gmelius, Superhuman, Shortwave, Lindy, Missive, Hiver, Front, MailMaestro,
SaneBox, Fyxer, Perplexity-email, Canary, Ellie, alfred_…). **Qué hacen TODOS** (la mesa de juego):
triaje por prioridad (Importante/Notif/Marketing), **redacción en tu voz** (aprende del «Enviados»),
**resumen de hilos**, **brief de la mañana**, **extracción de tareas**, agendado y **send-time**,
**seguimiento de respuestas pendientes**, **RAG sobre tu histórico**, detección de urgencia/sentimiento,
y los punteros (Shortwave, Lindy) ya hacen **acciones autónomas multi-paso**.

**La conclusión estratégica:** todos son **cloud, en inglés, genéricos**. NINGUNO es **local + español +
administrativo profundo + cognición del oficio**. Ahí está el foso de Loombit — no competir en "redactar
bonito", sino en **comprender y GESTIONAR** el día de un autónomo español sin que sus datos salgan de su
máquina. Lo que ellos hacen, lo hacemos local; lo que ellos no pueden (fiscal/cobros/trámites España), es
nuestro.

| # | Idea robada/mejorada | Cómo en Loombit (cruzando skills) | Madurez | Acción |
|---|---|---|---|---|
| E1 | **Triaje tipado + silenciar ruido** (SaneBox) | `comprension` YA clasifica; añadir auto-etiqueta/archivado LOCAL del ruido (newsletters/promos) y subir solo lo importante al telar | 🟢 | extensión de `comprension` |
| E2 | **Redacción con TU voz** (Ghostwriter/Meli/Ellie) | RAG **local** sobre tu carpeta «Enviados» → los borradores suenan a ti (no a IA). Cruza `comprension`×`gmail_send` | 🟡 | nueva primitiva `estilo_propio` |
| E3 | **Seguimiento de respuestas pendientes** (Superhuman) | "este correo lleva 5 días sin respuesta" — **es el mismo motor que el seguimiento de cobros**: unificar `cobros`×`comprension` en un "perseguidor" genérico | 🟢 | cruce de skills existentes |
| E4 | **Privacidad como bandera #1** (Canary local Copilot) | Loombit YA es local: convertirlo en el argumento de venta y un sello visible en la UI ("nada sale de tu máquina") | 🟢 | producto/marketing + badge UI |
| E5 | **Acción autónoma multi-paso** (Shortwave/Lindy) | de un asunto comprendido → cadena: agendar + calcular ruta + recordatorio de salida + preparar doc. Cruza `comprension`×`calendar`×Rutas×`pilot` | 🟡 | el "día gestionado" (objetivo) |
| E6 | **Composición con procedencia** (Perplexity-email) | para lo fiscal/admin, citar la fuente (BOE/AEAT) en la respuesta — ya es R3; aplicarlo a respuestas de correo | 🟡 | `Skill D Fiscal` × correo |

**Experimento concreto propuesto (ya):** el "**día gestionado**" (E5) sobre el caso David — Loombit
comprende la reunión (hecho), y de ahí encadena: ruta desde casa (Skill A Maps) → "sal a las 8:15" →
recordatorio → y prepara el hilo para que llegues listo. Es cruzar 4 skills en un flujo que ningún
competidor cloud puede hacer con tus datos locales.

**Sobre el propio radar (autocrítica):** hoy lo mantengo a mano. Para que VIVA de verdad, convertirlo en
una **routine `tech-radar`** (existe el motor de routines): barrido web periódico → destila → propone
filas aquí, con aprobación. Es el siguiente enganche natural del flywheel.

*Fuentes barrido 2: [Gmelius](https://gmelius.com/es/blog/asistentes-ia-correo-electronico) ·
[read.ai](https://www.read.ai/articles/the-7-best-ai-email-tools-in-2026) ·
[alfred_](https://get-alfred.ai/blog/best-ai-email-assistants) ·
[Fyxer](https://www.fyxer.com/blog/best-ai-email-assistant).*

## Barrido 3 — IA que se automejora (2026-06-08)

Destilado de papers/proyectos 2025-2026 sobre **automejora, autoprogramación, autorreparación y
autoaprendizaje**. La fusión:

- **Reflexion** — autocrítica verbal tras un fallo, guardada y antepuesta al siguiente intento, **sin
  reentrenar pesos**. → Loombit YA lo tiene (`agent/reflexion.py` + `_aprender_de_fallo`). ✅
- **Voyager / Skill Library + SAGE (2025/26)** — el agente **escribe código/skills reutilizables**, los
  prueba contra casos de validación, **guarda los que funcionan** en una librería y los **recupera y
  compone**. Es el patrón central de la autoprogramación. → Loombit: `Skill D` + `propose_improvement`
  + Fábrica de Skills son la semilla; falta la librería viva con auto-guardado validado. 🟡
- **GEPA (DSPy, ICLR'26)** — **evolución reflexiva de prompts/skills/tool-descriptions** por reflexión en
  lenguaje natural sobre las TRAZAS de ejecución; gradient-free, **supera a RL ~20% con 35× menos
  rollouts**, sin GPU. *Hermes Agent Self-Evolution* (DSPy+GEPA) muta los ficheros de skill y **propone
  mejoras vía PR, validadas por gates de restricción**. → **Encaje altísimo con Loombit:** evolucionar
  nuestros prompts/skills reflexionando sobre los `agent_runs`, **validado por los evals + el pre-commit
  gate, propuesto como RAMA** (nunca auto-aplicado).
- **Experiential learning (ERL, EvolveR)** — guardar trayectorias → reflexionar → **abstraer en
  heurísticas/skills reutilizables**; mejora paramétrica-libre por experiencia acumulada. → memoria +
  reflexión de Loombit es la base; falta la abstracción a skills.
- **Self-healing / code-repair loops** — leer código roto → tests fallan → LLM depura → parchea → repite
  hasta verde; disparado por CI. *Intent-based healing* 75-90%+ en cambios de UI. → Loombit: anti-flailing
  + puerta `verify.py` + reflexión son la semilla; un **bucle de autorreparación** (evals/tests en rojo →
  propone rama de arreglo) es implementable.
- **Gödel Agent** — modifica recursivamente su propia lógica guiado por objetivos de alto nivel
  (potente pero **arriesgado**; la literatura insiste en evals/gobernanza antes de soltarlo).
- **Metacognición** — el agente evalúa su propio desempeño, planea qué aprender y comprueba si funcionó.
  → `selfcheck.py` + routine de mejora continua es la semilla.

**La gran lectura para Loombit:** el campo avisa de que la automejora SIN gobernanza es lo que "quita el
sueño a los investigadores". **Loombit ya tiene justo el andamiaje seguro que piden:** supuestos→evals,
puerta de verificación (`verify.py`/pre-commit), **rama + aprobación de Fernando**, reflexión y memoria.
La oportunidad concreta: **un bucle de auto-evolución estilo GEPA/Voyager** — reflexiona sobre las trazas
de los runs → propone mejoras de skill/prompt **como rama** → las valida con los evals + el gate → Fernando
aprueba. Eso es la **Fábrica de Skills hecha real, en su versión segura** (autoría con freno de mano). Foso:
local + gobernado, frente a la automejora cloud sin auditoría.

| # | Idea | Madurez | Acción |
|---|---|---|---|
| S1 | **Auto-evolución GEPA-style** (reflexión sobre `agent_runs` → propone prompt/skill como rama, valida con evals+gate) | 🟡 | prototipo en `agent/reflexion` + routine; el gate ya es el freno |
| S2 | **Skill Library viva** (Voyager): el agente guarda skills que pasan sus evals y las recupera | 🟡 | extender `propose_improvement` + Fábrica de Skills |
| S3 | **Bucle de autorreparación** (evals/tests rojos → rama de arreglo propuesta) | 🟡 | engancha `selfcheck` + el agente coder |

*Fuentes barrido 3: [Gödel Agent](https://arxiv.org/abs/2410.04444) · [Voyager](https://blog.pebblous.ai/report/voyager-lifelong-agent-2023/en/) · [GEPA](https://arxiv.org/pdf/2507.19457) · [Hermes Self-Evolution](https://github.com/NousResearch/hermes-agent-self-evolution) · [Survey Self-Evolving Agents](https://arxiv.org/pdf/2508.07407) · [ERL](https://arxiv.org/abs/2603.24639) · [Self-Healing CI](https://dagger.io/blog/automate-your-ci-fixes-self-healing-pipelines-with-ai-agents/).*

## Barrido 4 — IA que se automejora, a FONDO + ingeniería de cómo se construye (2026-06-08)

Profundización del barrido 3 con los sistemas EMPÍRICOS punteros 2025 y, sobre todo, **cómo se
construyen** (la diferencia entre "potente" y chorrada). Esto se **destiló ANTES de programar** y
fundó la **Fábrica de Skills** (D-39, `loombit_operator/fabrica/`).

**Lo nuevo del estado del arte:**
- **Darwin Gödel Machine** (Sakana/UBC, may-25): versión empírica de Gödel — reescribe su propio
  código y se valida en benchmarks; **archivo evolutivo (linaje abierto)**; SWE-bench 20%→50%.
- **SICA** (Bristol, ICLR'25): edita su propia base de código; bucle **evaluar→seleccionar→revisar**
  con archivo; el mejor del archivo siembra la siguiente revisión; 17%→53% SWE-bench Verified.
- **ADAS / Meta Agent Search** (ICLR'25): un meta-agente **programa agentes en código** y archiva
  los que baten a los hechos a mano; transfieren entre dominios.
- **AlphaEvolve** (DeepMind, may-25) + **OpenEvolve/CodeEvolve** (open): agente evolutivo que mejoró
  algoritmos reales (4×4 en 48 productos, batió a Strassen). **Evaluación en cascada** + **canal de
  artefactos** (realimenta el error al siguiente prompt).
- **SEAL** (MIT, jun-25), **Absolute Zero** (NeurIPS'25), **R-Zero** (ago-25): self-play / self-edits
  que tocan **pesos** → ⚠️ la línea que Loombit **no cruza** (sin fine-tuning, por brújula).
- **TextGrad**: "diferenciación vía texto" — backprop de feedback NL por un sistema compuesto.
- **APR 2025** (survey + SWE-bench ~63%): self-debugging; ⚠️ **test-overfitting** (los LLM gaman los
  tests) → exige evals held-out. **A-MEM/Mem0**: memoria que se auto-organiza por reflexión.
- **Gobernanza** (AGENTSAFE/AURA/Oversight Game): piden trazabilidad + least-privilege + humano en el
  lazo; **<10% de orgs lo tiene**. **SkillsBench**: la auto-generación SIN verificación **empeora**
  el sistema (-1,3pp) → la prueba de que solo el gate riguroso la vuelve positiva.

**La ingeniería que importa (barrido específico):** sandbox por **AST + allowlist + builtins
recortados** (smolagents/LLM-Sandbox) · **cascada** de evaluación barato→caro fail-fast · **canal de
artefactos** para auto-reparar · **archivo/linaje** con fitness · contenedor (gVisor) como hardening.

**Mini-hoja de ruta (→ implementada como la Fábrica, D-39):**

| # | Idea del barrido | Dónde quedó en el código |
|---|---|---|
| **S4** | El **verificador es el foso** (evaluador con verdad de tierra) | `fabrica/validacion.py` (7 puertas en cascada) ✅ |
| **S5** | **Archivo/linaje** (DGM/ADAS), no hill-climbing | `PropuestaSkill.fitness` + `PropuestaStore` ✅ |
| **S6** | Auto-currículo / Challenger (R-Zero/AZR) | *pendiente* (siguiente: casos adversarios fiscales) 🔵 |
| **S7** | Optimización reflexiva (GEPA/TextGrad) + auto-reparación | `fabrica/autoria.py` (feedback del arnés) ✅ |
| **S8** | Anti-overfit (held-out) | puerta `sin_regresion` del arnés ✅ |
| **S9** | Memoria auto-organizada (A-MEM/Mem0) | *pendiente* (engancha el RAG local P1) 🔵 |
| **S10** | **Gobernanza = producto** (gate, local, andamiaje≠pesos) | `fabrica/seguridad.py` + gate sagrado ✅ |

*Fuentes barrido 4: [DGM](https://arxiv.org/abs/2505.22954) · [SICA](https://arxiv.org/abs/2504.15228) ·
[ADAS](https://arxiv.org/abs/2408.08435) · [AlphaEvolve](https://arxiv.org/abs/2506.13131) ·
[OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve) · [SEAL](https://arxiv.org/abs/2506.10943) ·
[Absolute Zero](https://arxiv.org/abs/2505.03335) · [R-Zero](https://arxiv.org/abs/2508.05004) ·
[TextGrad](https://arxiv.org/abs/2406.07496) · [survey APR](https://arxiv.org/abs/2506.23749) ·
[A-MEM](https://arxiv.org/abs/2502.12110) · [Survey self-evolving](https://arxiv.org/abs/2508.07407) ·
[smolagents secure exec](https://huggingface.co/docs/smolagents/en/tutorials/secure_code_execution) ·
[Agent Skills SoK](https://arxiv.org/html/2602.12430v4).*

## Cómo se alimenta este radar
1. **Claude (yo), de forma continua** — al trabajar, propongo aquí lo que veo de vanguardia aplicable.
2. **Routine "tech/normativa radar"** (futura) — barrido periódico de normativa (BOE/AEAT) y estado del arte → nuevas filas con fuente.
3. **Del propio sistema** — la Fábrica de Skills detecta carencias reales y las sube aquí.

> Nota: cuando una idea madura y se decide, se mueve a `INNOVACIONES.md` (con DoD) y al roadmap.
