# Síntesis COMPLETA — todo lo hablado sobre la plataforma LoomBit

> Consolida en un solo sitio TODA la información obtenida (regulatoria, técnica, de mercado) y TODO lo
> propuesto (skills, mejoras, arquitectura) a lo largo de esta sesión. Detalle por ronda en
> `docs/ARQUITECTURA_PLATAFORMA_LOOMBIT.md` (§0–23); acción inmediata en `docs/HANDOFF_ARQUITECTURA_PLATAFORMA.md`;
> 45 señales con fuente en `docs/RADAR.jsonl`. Rama `claude/loombit-ai-architecture-nsyw5r` · PR #57.

---

## PARTE A — La tesis y las leyes

**Qwen es el motor cognitivo; LoomBit es el SO que lo gobierna.** Cadena inviolable, ya en el código:
*Qwen propone (`llm.py`) → LoomBit valida (`policy/authority_plane.py`) → el operador aprueba
(`PENDING_APPROVAL`) → las tools ejecutan (`tools/registry.py`) → todo queda registrado (`agent/run.py`).*
Ley fundacional: **el LLM nunca está en el camino de control de confianza para nada consecuente.**

| Ley | Estado real (auditado) | Evidencia en código |
|---|---|---|
| 1. Qwen propone, código dispone | 🟢 | `agent/loop.py:706` → `AUTHORITY_PLANE.autorizar()` |
| 2. Datos ≠ órdenes (CaMeL) | **🟠 DORMIDA** | `loop.py:706` NO pasa `contenido_no_confiable`; el filtro `valor_de_cuarentena` existe pero nunca dispara |
| 3. Gate humano a efectos externos | 🟢 con fuga | `gmail_send` auto-envía si destinatario "claro" (`autorizar()`) |
| 4. Local-first | 🟢 (solo red) | `seguridad_web.py` (anti DNS-rebinding/CSRF); NO contiene la ejecución |
| 5. Todo deja recibo | 🟢 | `AgentStore` + recibos en `runtime/local/` |

---

## PARTE B — Qwen: qué tocar, qué no, qué es peligroso

Qwen2.5-14B-Instruct (`instructor`) + Qwen2.5-Coder-7B (`coder`) vía LM Studio (`localhost:1234/v1`).

- **SÍ se toca (gobierno externo, reversible):** decodificación (`temperature` 0.2, `top_p`, `max_tokens`
  512, `stop`, `seed` → `config.py`), system prompt (`agent/prompts.py`), catálogo de tools
  (`tools/registry.py`), contexto inyectado (`agent/contexto.py`), salida forzada (grammar/JSON-schema),
  modelo cargado.
- **NO conviene:** pesos (fine-tuning fuera de alcance; aprendizaje = memoria/RAG), chat template/tokenizer,
  runtime del servidor LLM (caja negra reemplazable detrás de la API OpenAI-like).
- **PELIGROSO:** fine-tuning en producción (olvido catastrófico, inauditable), `temperature` alta / quitar
  `stop` en flujos consecuentes, tool de efecto sin `requires_approval`, contenido no confiable directo al prompt.
- **LoRA/QLoRA:** solo si el FORMATO falla sistemáticamente con eval antes/después, o para destilar jerga muy
  repetitiva; siempre QLoRA 4-bit como adaptador separable, nunca merge. Hoy: **no entrenar.**

---

## PARTE C — Las 10 capas mapeadas a código

| # | Capa | Módulo real | Estado |
|---|---|---|---|
| 1 | Interfaz local | `static/index.html`, `routers/ui.py`, `home.py` | 🟢 |
| 2 | Orquestador seguro | `agent/loop.py` (ReAct), `routers/agent.py` | 🟢 |
| 3 | Qwen local | `llm.py` + LM Studio | 🟢 |
| 4 | Memoria | `agent/memory.py`, `memory_dedup.py` | 🟢 |
| 5 | RAG | `rag.py`, `routers/rag.py` (embeddings locales nomic) | 🟡 |
| 6 | Herramientas | `tools/registry.py` + base/connectors/dominio/pilot/computer | 🟢/🟠 |
| 7 | Permisos | `policy/authority_plane.py` + `safety_class` + `agent/guardas.py` | 🟢 |
| 8 | Logs/recibos | `agent/run.py::AgentStore`, `runtime/local/` | 🟢 |
| 9 | **Sandbox** | — (solo `fabrica/seguridad.py` para código generado) | ⬜ **hueco** |
| 10 | Aprobación humana | `requires_approval` + `PENDING_APPROVAL` + gate MCP | 🟢 |

**Permisos — dos ejes:** `safety_class` (`passive`/`assisted`/`safety_sensitive`/`blocked_by_default`)
× `authority_plane.Accion` (`EJECUTAR`/`APROBAR`/`CORREGIR`/`REHUSAR`). Hoy el loop gatea por
`requires_approval` y el MCP por `safety_class` → **dos mecanismos paralelos** (deuda: unificar).

---

## PARTE D — Amenazas (red team) y defensas

**2 vías 🔴 (críticas):**
1. **Auto-reescritura de guardarraíles:** `tools/base.py::_write_file` y `_run_shell` (`shell=True`)
   escriben/ejecutan en cualquier ruta → el agente puede sobrescribir `loop.py`, `authority_plane.py`,
   `.env`, token store. Escalada total. Prerrequisito bloqueante de autonomía (F4).
2. **Inyección → acción consecuente:** con CaMeL dormido, un IBAN/importe de un correo de cliente puede
   fluir a una propuesta de cobro (la amenaza EXACTA de la cuña de morosidad).

**2 vías 🟠:** auto-envío `gmail_send` sin tarjeta si destinatario "claro" (defensas regex evadibles);
doble puerta MCP vs loop incoherente si una tool se etiqueta mal.

**Defensa en profundidad (8 capas):** el modelo no ejecuta · `blocked_by_default` · gate humano · CaMeL
(a wirear) · resolución por código · `REHUSAR` ante manipulación · local-first · sandbox (a construir).
**Refuerzos del radar:** Spotlighting (delimitadores aleatorios, contenido = dato opaco) + RAG con
procedencia/score (anti poisoning: 5 docs → 90%). Inyección indirecta = **OWASP LLM01** (riesgo nº1, 3 años).

---

## PARTE E — Conocimiento REGULATORIO obtenido (cuña: autónomo español)

**Son TRES obligaciones distintas y complementarias + morosidad:**

| Norma | Qué es | Plazo clave | Fuente |
|---|---|---|---|
| **VeriFactu** | Seguridad del SOFTWARE (Ley Antifraude): hash ENCADENADO, registro de facturación + de eventos, QR + texto "VERI*FACTU", export/transmisión AEAT. Multas hasta **50.000€/ejercicio** | empresas ene-2026; autónomos jul-2026 (RD amplía a **2027**) | b2brouter, sage |
| **Facturae / Crea y Crece** | FORMATO XML obligatorio en B2B (RD **238/2026**); sector público vía **FACe**. El software VeriFactu *genera* Facturae | reglamento **1-oct-2026**; obligación jul-2027 (>8M€), jul-2028 (resto) | marimón, cuatrecasas |
| **SII** | Suministro Inmediato de Información: libros de IVA a la AEAT; autoliquidación 303 | régimen IVA | sage, anfix |
| **Ley 3/2004 Morosidad** | Pago B2B máx **60 días**; desde día 61 interés de demora AUTOMÁTICO **10,15%** (BCE 2,15% + 8) + **40€** fijos + costes acreditables | continuo | BOE, cobratufactura |

> Implicación: "cubrir VeriFactu" NO basta; el autónomo necesita VeriFactu + Facturae + SII. Y el cálculo
> de morosidad (interés/40€) es **determinista (Decimal)** → lo hace código, el LLM narra citando la ley.

---

## PARTE F — Conocimiento TÉCNICO obtenido (radar)

- **Constrained decoding (fiabilidad de salida):** 3 niveles — prompt (80-95%), function-calling (95-99%,
  el schema es PISTA), **structured output nativo con gramática (100% schema-válido)** vía Outlines/XGrammar/
  llama.cpp. → usar gramática para extracción crítica = "cero fallos" de formato. (pockit, JSONSchemaBench)
- **Prompt injection / defensas:** OWASP LLM01; RAG poisoning (5 docs → 90%); **Spotlighting** (delimitadores
  aleatorios); defensa MULTICAPA, no solo el modelo. (zylos, Gemini defenses, MS Spotlighting)
- **SLM / Qwen-VL on-device:** Qwen3-VL 2b/4b/8b corren local (Ollama/LM Studio); extracción documental
  fiable, barata y dentro del perímetro de cumplimiento; "document agents" entienden y deciden, no solo OCR. (cogitx)
- **GEPA (auto-mejora de prompts):** frontera de Pareto > "mejor por media"; hasta 35x menos rollouts que RL.
  Ya cableado en `fabrica/gepa.py` + `gepa_pareto.py`. (arXiv 2507.19457)
- **OSWorld (control de equipo):** SOTA 2026 ~72-82% → aún falla → el gate humano es la red obligatoria;
  medir el Pilot al estilo OSWorld, NO prometer autonomía total. (arXiv 2505.03570)
- **Open Banking AISP (PSD2→PSD3 2026):** un AISP agrega cuentas → conciliación automática en tiempo real;
  España sin estándar oficial (agregador privado de facto). (openapi, embat)
- **WhatsApp Business API:** recordatorios de pago cobran **3x más rápido**; mensajes "utility" ~80% más
  baratos que marketing; enlace de pago + webhook de cobrado. (jestor, messagecentral)
- **Local-first es el patrón ganador transversal:** finanzas (SenticMoney: datos en el dispositivo, sin
  Plaid), hogar (Home Assistant + Whisper.cpp + Ollama, cero llamadas externas, RPi5), salud (líderes cloud
  que entrenan con tus datos), tutoría (minimización/self-host). El foso escala fuera del fiscal.

---

## PARTE G — Catálogo COMPLETO de skills propuestas

**Cuña activa (orden por valor × deadline):**

| Skill | Tipo | Reusa del repo | Fuente |
|---|---|---|---|
| WhatsApp Cobros | `Skill A` | `decisions_cobros.py` (tono escalado) | WhatsApp 3x |
| Morosidad | `Skill D` | cálculo Decimal (interés 10,15% + 40€) | Ley 3/2004 |
| VeriFactu | `Skill D` | `expedientes.py` (cadena hashes) + `verifactu.py` | b2brouter |
| Facturae | `Skill D` | XML + FACe | RD 238/2026 |
| SII | `Skill D` | libros IVA | sage |
| Visión Documental | `Skill A` | `read_invoice` + Qwen-VL local + candado nº | cogitx |
| Open Banking (AISP) | `Skill A` | `conciliacion_cobros.py` (OPT-IN) | openapi |
| Del cobro al 303 | `Skill G` | orquesta todo lo anterior | — |

**NO adyacentes (VISIÓN/radar — prueba del kernel blanco; NO construir hasta cerrar la cuña 1):**

| Skill | Usuario | Reusa del kernel | Fuente |
|---|---|---|---|
| Salud Personal / Cuidado de Mayores | familia | `expedientes` multi-tenant + gate | Amazon/MS Health; mercado 56B→387B |
| Legal/Contratos | abogado | plazos (`tipos_demora`) + `comprension` | GC.ai |
| Segundo Cerebro | estudiante/investigador | `rag.py` + `mcp_server` | Obsidian+MCP |
| Estudio/Tutor | estudiante | `rag.py` + `scheduler.py` + plazos | mystudylife |
| Finanzas Personales | hogar | conciliación + RAG + Decimal | SenticMoney |
| Búsqueda de Empleo | candidato | `expedientes` (CaseFile=Kanban) + plazos | skillscouter |
| Smart Home | tablet/móvil | Adapter (Pilot) + Voz | Home Assistant |
| Accesibilidad | discapacidad | Pilot + Voz + visión (verbosidad adaptativa) | Nature AURA |
| Visión Ambiental | accesibilidad/inventario | conector Qwen-VL | Seeing AI / Ray-Ban Meta |
| Voz local | manos libres | ASR/TTS local (Whisper.cpp) | Home Assistant |

**Tesis validada:** 6 primitivos del kernel (loop+gate · `expedientes`/CaseFile · `rag.py` ·
`scheduler`/plazos · Adapter/`pilot` · visión Qwen-VL) cubren ~10 dominios no adyacentes **sin tocar el núcleo**.

---

## PARTE H — Mejoras de NÚCLEO propuestas (Skill W)

1. **Wirear CaMeL** (pasar `contenido_no_confiable` en `loop.py:706`; cubrir IBAN/importe).
2. **Spotlighting** (2ª capa) en `contexto.py`/`sanear_dato` + **RAG con procedencia** en `rag.py`.
3. **Valla de autoprotección** en `write_file`/`run_shell` (`fs_deny`) + `sandbox/` (policy+runner+límites).
4. **Inyectar cognición** (expediente/comprensión) en `contexto.py` antes del ReAct.
5. **Ledger único:** `AgentStore` → eventos en la cadena de hashes del CaseFile (`expedientes.py`).
6. **Candado de procedencia numérica** + property tests sobre `calcular_303`.
7. **Constrained decoding** (gramática) en `llm.py` para extracción crítica.
8. **Router de modelos** (7B→14B) + presupuesto VRAM/latencia (Jetson Orin NX 16GB).
9. **Unificar gate por `safety_class`** (loop + MCP, una sola fuente de verdad).

---

## PARTE I — Backlog integrado y north-star

**North-star:** *% de tareas cerradas al 100% sin que el usuario tenga que revisar tu trabajo.*

| Prio | Bloque | Por qué |
|---|---|---|
| **P0** | CaMeL wired + valla autoprotección + Spotlighting | cierra las 2 vías 🔴; precondición de toda skill que lea contenido no confiable |
| **P1** | cognición→contexto · ledger encadenado · candado numérico · constrained decoding · router modelos | foso (comprensión, VeriFactu, cero fallos, Jetson) |
| **P1-cuña** | WhatsApp Cobros + Morosidad → Facturae + VeriFactu → Visión → Open Banking + SII → Skill G | el producto de la cuña, por ROI×deadline |
| **P2** | `sandbox/` completo + unificar gate `safety_class` | contención total para autonomía F4 |

---

## PARTE J — Datos de mercado obtenidos

- IA en cuidado de mayores: **56,78B USD (2025) → 387,52B (2035)**, CAGR 21,3%.
- WhatsApp recordatorios de pago: hasta **3x** cobro; utility ~80% más barato; España ~€0,0311/msg utility.
- VeriFactu: multas hasta **50.000€/ejercicio**.
- Morosidad: interés legal de demora 2026 = **10,15%** + 40€ automáticos.

---

## PARTE K — Reglas inviolables al implementar

LLM no ejecuta · cifras/consecuentes por código determinista (Decimal) · gate humano a todo efecto externo ·
local-first · todo deja recibo (DoD) · no tocar pesos · `Skill D` no contamina el núcleo / `Skill A`
reemplazable · D-86 anti-dispersión (cerrar cuña 1 antes de otra) · D-90 radar con fuente antes de construir ·
"hecho" lo declara `scripts/verify.py` + check verde de GitHub, no tú · rama/worktree + arnés (test) antes de tocar.

---

## PARTE L — Estado del trabajo y siguiente paso

- **Hecho:** 6 rondas de diseño (45 vueltas) + 45 señales de radar, todo en la PR #57. **0 implementación.**
- **Siguiente paso único:** abrir rama desde main e implementar **P0** (CaMeL + valla + spotlighting) con
  test de inyección, `scripts/verify.py` verde, PR. **No abrir skills hasta que P0 esté 🟢.**
