# FÁBRICA × Mafia IA — automejora en 2º plano (mejorar el motor que mejora a Loombit)

> Aplica lo destilado de la newsletter Mafia IA (`../mafia-ia-destilado/`) a la **Fábrica de Skills**
> y a la **herramienta de errores de código** (`fabrica/interno.py` + `reparar.py`), para **automatizar
> y mejorar la automejora en segundo plano**. Anclado al código real (`necesidad.py`, `interno.py`,
> `reparar.py`, `ciclo.py`, `red.py`, `aprendizaje.py`). *Generado: 2026-06-09.*
>
> **Premisa honesta:** la Fábrica ya es **fuerte y gobernada** (detectar→redactar→validar→proponer con
> auto‑reparación, arnés de 7 puertas, guard de API que impide borrar símbolos públicos, tests en repo
> aislado, linaje DGM/ADAS, **nunca aplica**, SkillsBench‑aware). Mafia IA **no la reinventa**: aporta
> 5 piezas concretas que la hacen **aprender entre ciclos** y **correr sola, barata, en 2º plano**.

---

## 1 · Qué tiene hoy (código) y qué le falta para "automejora real en 2º plano"

| Pieza | Hoy | Hueco para automejora continua |
|---|---|---|
| `necesidad.py` | Detección determinista: huecos auto‑reportados por el agente + tools que fallan ≥2× | Salta directo a "redactar 1 tool"; **no explora enfoques** antes |
| `interno.py` (errores de código) | ruff‑B, TODO, >400 líneas, prompts→GEPA, huecos de eval — solo **`.py`**, prioridad **estática** | Ciego a `.html/.js/.css` (¡el monolito de 2.552 líneas de `index.html` NO lo ve!); sin complejidad/seguridad/código‑muerto; no aprende de lo que el humano acepta/rechaza |
| `reparar.py` | Diff validado (parse+black+ruff) + guard de API + tests aislados, **nunca escribe** | No hay **memoria de qué reparaciones funcionaron/se rechazaron** (cada propuesta nace de cero) |
| `ciclo.py` | Orquesta con auto‑reparación (realimenta el fallo del arnés N intentos) + linaje | El `feedback` se **acumula** entre intentos (riesgo de *context rot*); el linaje guarda fitness pero **no destila un playbook reutilizable** |
| `aprendizaje.py` (daemon) | Reindex del RAG por defecto; Reflexion proactiva **opt‑in** (caro en local) | No corre la Fábrica/GEPA en 2º plano; falta el **lazo autónomo barato y presupuestado** |
| `red.py` | Radar GitHub/HN/arXiv/BOE con procedencia → revisión humana | El texto externo llega crudo al coder (**inyección** / hype sin filtro) |

---

## 2 · Las 5 mejoras (de Mafia IA, sin romper la gobernanza)

### Mejora 1 · El **Playbook de la Fábrica** (ACE, #10) — *la de mayor impacto*
ACE = *Agentic Context Engineering*: convertir la experiencia en un **playbook de reglas con contadores
helpful/harmful**, actualizado por **deltas** (nunca reescrito), que el ejecutor consulta. La Fábrica es
**exactamente** el caso de uso (un agente que se automejora) y hoy **no tiene** esa memoria: cada
`redactar`/`proponer_parche` nace de cero.

- **Qué:** un nuevo `fabrica/playbook.py` (memoria procedimental de autoría): bullets con `id`,
  `contenido` (2‑3 frases accionables: "al redactar una tool de tipo X, haz Y; evita Z"), `tags`,
  **`helpful`/`harmful`** y `fuente`. Persistido local (JSON), idempotente, deduplicado.
- **Cómo se llena (delta, sin reescribir):**
  - Cuando el arnés (`validacion`) **falla** una puerta → se destila una regla "evita …" (`harmful++` del patrón).
  - Cuando una propuesta **pasa y el humano la APRUEBA** → la regla que la guió suma `helpful++`.
  - Cuando el humano **RECHAZA** o los tests van rojos al aplicar → `harmful++` y se deprecia.
- **Cómo se usa:** `autoria.redactar` y `reparar.proponer_parche` reciben **las K reglas más relevantes**
  a la necesidad (recuperación por relevancia, no volcado — patrón ExpeL, igual que `relevant_lessons`
  en `memory.py`). El coder local mejora **sin tocar pesos** (regla del proyecto), solo con mejor contexto.
- **Encaje:** reutiliza el patrón ya probado en `agent/memory.py` (lecciones con `times_used`); aquí se
  añade el contador `harmful` y la priorización por **(helpful − harmful)**. Cierra el "refinar Fase 5".
- **DoD:** una tool que falló por el mismo motivo dos veces deja de proponerse igual; recibo del delta.

### Mejora 2 · El **bucle autónomo en 2º plano** (AutoResearch/Ralph, #01) — *automatizar la automejora*
El método de #01 (Karpathy AutoResearch + Ralph): **proponer → ejecutar → medir contra una métrica →
conservar si mejora, descartar si no → repetir, reseteando contexto cada iteración** (evita *context rot*).

- **Métrica, no solo pass/fail:** el arnés es binario; añadir un **fitness continuo** al `Veredicto`
  (puertas pasadas + cobertura de su eval + simplicidad) para que el linaje **ordene** y el playbook
  aprenda qué enfoques puntúan más alto (ya hay `fitness` en el linaje DGM/ADAS — elevarlo a señal del bucle).
- **Ralph (contexto fresco):** en `ciclo._atacar_necesidad`, no acumular el `feedback` íntegro entre
  intentos; **resetear** y pasar solo el **delta destilado** (resumen del fallo + reglas del playbook).
  Menos tokens, menos deriva — clave en hardware local.
- **Daemon presupuestado (la pieza nueva):** extender `aprendizaje.py`/Routines con un **lazo de Fábrica
  oportunista**: corre en **idle/off‑peak**, con **cupo de tokens** y **cap de tiempo**, respetando la
  regla "NO lanzar jobs LLM pesados durante el uso interactivo". El **escaneo `interno.py` (sin LLM)**
  corre a menudo; la **autoría/GEPA (con LLM)** corre rara vez y budgeted. Idempotente, best‑effort.
- **DoD:** con LM Studio libre, el daemon corre 1 ciclo, deja ≤N propuestas PENDIENTES con recibo, y
  **se abstiene** si el cupo se agota — sin tocar la experiencia interactiva.

### Mejora 3 · **Super Loop** en la detección/autoría (#01) — explorar antes de redactar
Hoy `necesidad.py` detecta y `autoria.redactar` redacta **una** tool. El Super Loop Mental (#01) dice:
**mapear varios enfoques (obvios + contraintuitivos), elegir el más testable, y solo entonces ejecutar.**

- **Qué:** un paso ligero previo en `ciclo` (o en `autoria`): pedir al coder **2‑3 enfoques** para la
  necesidad con "qué probar / cómo medir / qué puede fallar", elegir por testabilidad/fitness esperado, y
  redactar **ese**. Sube la tasa de éxito en el primer intento (menos vueltas del arnés = menos tokens).
- **DoD:** medir tasa de aprobación a 1er intento antes/después en un set de necesidades de prueba.

### Mejora 4 · **Pase adversarial + higiene de afirmaciones** (#05 + #06) — antes de PENDIENTE
El arnés verifica sintaxis/estilo/tests, **no** "¿es buena y segura idea?". Y `red.py` mete texto
externo crudo (riesgo de inyección/supply‑chain — ver `../mafia-ia-destilado/ANALISIS-LOOMBIT.md` A5).

- **Abogado del Diablo (E4):** un pase barato sobre el borrador propuesto → "qué edge cases, qué riesgo
  de seguridad, qué supuesto oculto"; se adjunta a la propuesta para el gate humano (no bloquea, informa).
- **Higiene del radar (#06 OpenClaw):** tratar el texto de `red.py` como **dato citado, no instrucción**
  (fencing); una `Necesidad(fuente=RED)` con afirmación de número redondo/benchmark se marca **"no
  verificada"** y **no asciende** sin fuente primaria. Importar la regla de #06 como **checklist de
  adopción** (probar antes de fiarse; coste total; auditar seguridad) para todo hallazgo RED.
- **DoD:** un repo‑trampa con instrucciones embebidas no altera el código propuesto; una cifra sin fuente queda marcada.

### Mejora 5 · La **herramienta de errores de código** (`interno.py`) — que vea más y aprenda
- **Que vea lo que hoy es invisible:** extender el detector de tamaño/complejidad a **`.html/.js/.css`**
  y manifests → así `interno` **marca el monolito `static/index.html` (2.552 líneas)** como refactor #1
  (¡conecta con el rediseño de UX!). Hoy `_EXCLUIR` ignora `static` y solo mira `.py`.
- **Más detectores deterministas (sin LLM, baratos):** complejidad ciclomática (ruff `C901`/mccabe),
  **seguridad** (ruff `S`/flake8‑bandit — pertinente tras el análisis de seguridad), **código muerto**
  (vulture), imports sin usar. Cada uno con `file:line` y prioridad.
- **Prioridad que APRENDE (preference learning, "del usuario"):** ponderar la prioridad por **cuántas
  veces el humano actúa** sobre cada categoría (las reparaciones que aceptas suben; las que ignoras bajan)
  → alimenta el Playbook (Mejora 1). Hoy las prioridades son enteros fijos.
- **Auto‑pilotar GEPA:** `interno` ya marca prompts como candidatos GEPA, pero **nadie los corre**.
  El daemon (Mejora 2) lanza **GEPA real** sobre el prompt de más tráfico contra sus evals F1‑F8,
  presupuestado, y deja la mejora como **propuesta con diff** (GEPA ya existe y nunca escribe).
- **Cerrar el lazo con `reparar`:** cada señal de `interno` de tipo FIX puede generar (en 2º plano) una
  **propuesta de parche** vía `reparar.proponer_parche(..., validar_tests=True)` → diff validado a la cola
  PENDIENTE. La "herramienta de errores" pasa de **marcar** a **traer la reparación lista para tu OK**.
- **DoD:** `interno` marca `index.html` como oversize; una señal FIX real produce un diff que pasa el
  guard de API + tests aislados y queda PENDIENTE; la prioridad de una categoría sube tras aprobarla 3×.

---

## 3 · El daemon de automejora (cómo se orquesta todo, barato y seguro)

```
        ┌──────────────── DAEMON DE AUTOMEJORA (idle / off-peak, presupuestado) ───────────────┐
        │                                                                                       │
  FRECUENTE  →  interno.marcar()  (sin LLM, segundos)  → señales con file:line, prioridad       │
   (barato)        │                                                                            │
                   ▼                                                                            │
  RARO/BUDGET →  por cada señal/necesidad TOP:                                                   │
   (con LLM)       Super Loop (3 enfoques) → autoría/reparar (coder) ── consulta ──► PLAYBOOK    │
                   → arnés 7 puertas (+fitness) → pase adversarial (E4) ── actualiza ──► PLAYBOOK│
                   → PROPUESTA PENDIENTE (con diff/eval/abogado-del-diablo)                      │
        │                                                                                       │
        └────────────────────────────  NUNCA aplica · espera el GATE humano  ───────────────────┘
                         GEPA sobre el prompt de más tráfico (budget) ─┘
```
- **Gobernanza intacta:** solo **propone**; el humano aprueba; SkillsBench dice que sin verificación la
  auto‑generación **empeora** → el arnés + el gate + local es lo que la vuelve net‑positiva. No se toca.
- **Presupuesto:** cupo de tokens/tiempo por ventana; si se agota, se abstiene con honestidad (recibo).
- **Regla del proyecto:** sin fine‑tuning de pesos; todo vive en **playbook + prompts + manifests**.

---

## 4 · Plan por slices (DoD 🟢, rama/worktree, sin auto‑aplicar)

> **Estado (rama `feat/fabrica-automejora`):** ✅ **F1** Playbook ACE (`playbook.py`, `589defc`) ·
> ✅ **F2** interno+ ve UI/seguridad (`589defc`) · ✅ **F1b** Playbook cableado en autoría/reparar/gate
> (`6844f98`) · ✅ **F3** lazo interno→reparar (`mantenimiento.py`, `7dea205`) · ✅ **F4** el daemon
> nocturno usa el Playbook + parte de salud del código (`92b23ba`). **527 tests verdes**,
> black+ruff+pre‑commit OK. Pendientes (polish): F5 Super Loop+Ralph · F6 adversarial+higiene radar ·
> F7 auto‑GEPA. Sin merge a main (espera OK de Fernando).

| Slice | Entrega | DoD |
|---|---|---|
| **F1 · Playbook (ACE)** | `fabrica/playbook.py` (bullets + helpful/harmful + recuperación por relevancia); `autoria`/`reparar` lo consultan; `validacion`/gate lo actualizan por delta | Una regla dañina deja de guiar; recibo del delta; tests |
| **F2 · interno+** | Oversize/complejidad en `.html/.js/.css`; detectores `S`(seguridad)/`C901`/vulture; marca `index.html` | `interno` lista el monolito y ≥1 hallazgo de seguridad real, con `file:line` |
| **F3 · Lazo interno→reparar** | Señales FIX generan parche validado (guard API + tests aislados) a la cola PENDIENTE | Un FIX real produce un diff verde PENDIENTE, sin escribir |
| **F4 · Daemon presupuestado** | Routine de Fábrica en idle con cupo; interno frecuente / autoría rara | 1 ciclo nocturno deja ≤N propuestas + recibo; se abstiene al agotar cupo; cero impacto interactivo |
| **F5 · Super Loop + Ralph** | Explorar 3 enfoques antes de redactar; resetear contexto entre intentos (solo delta) | Sube la aprobación a 1er intento en el set de prueba; menos tokens/ciclo |
| **F6 · Adversarial + higiene radar** | Abogado del Diablo en cada propuesta; fencing + "no verificada" para hallazgos RED | Repo‑trampa no altera el código; cifra sin fuente marcada |
| **F7 · Auto‑GEPA** | El daemon corre GEPA sobre el prompt de más tráfico contra F1‑F8 | Una mejora de prompt real queda como diff PENDIENTE con scores |

**Orden:** F1→F2→F3 (memoria + ver más + cerrar el lazo de reparación = el grueso del valor), luego F4
(automatización), F5‑F7 (calidad). Cada slice **verificable en vivo** antes de fundir (regla nº1).

---

## 5 · Lo que NO hacer (mantener el foso)
- **No auto‑aplicar** nunca (ni en 2º plano): la Fábrica propone; el humano aprueba. *(SkillsBench)*
- **No adoptar hype** de `red.py` sin la checklist #06 (probar + coste total + auditoría). *(OpenClaw)*
- **No fine‑tuning de pesos**: la automejora vive en playbook/prompts/manifests.
- **No monopolizar el modelo local** en horario interactivo (presupuesto + idle).
- **No tratar texto externo como instrucción** (fencing + procedencia).

> En una frase: la Fábrica ya sabe **proponer y validar**; Mafia IA le da **memoria que aprende entre
> ciclos (ACE), un bucle barato que corre solo (AutoResearch/Ralph), ojos para ver más errores (interno+),
> y un filtro adversarial** — sin tocar la gobernanza que la hace net‑positiva.
