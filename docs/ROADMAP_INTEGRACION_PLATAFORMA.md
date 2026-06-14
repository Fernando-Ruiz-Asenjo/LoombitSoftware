# Integración en el ROADMAP — plataforma LoomBit (hub para otro hilo)

> **Para otro hilo de LoomBit.** Este documento es el **HUB**: te dice cómo integrar todo el trabajo de
> arquitectura/skills en el roadmap existente y te deja **todo a mano** (catálogo de skills, upgrades de
> núcleo, índice de documentación, índice del radar, agenda de investigación, reglas para convertir una
> propuesta en tarea). Generado en la rama `claude/loombit-ai-architecture-nsyw5r` · PR #57.
>
> **Cómo usarlo:** (1) lee §1 para el encaje en fases · (2) §2 para el catálogo priorizado · (3) §3 para
> los upgrades de núcleo · (4) §4-5 índices de docs y radar · (5) §6 agenda de investigación · (6) §7
> reglas de integración. La fuente de verdad del estado vive en `docs/ESTADO_Y_ROADMAP.md` (§META-4); este
> doc NO duplica estado fechado, propone DÓNDE encajan las piezas.

---

## 0. TL;DR para integrar

- El trabajo es **DISEÑO** (9 rondas, ~105 vueltas, ~80 skills, 63 señales de radar). **0 implementación.**
- **Lo primero del roadmap NO es una skill: es P0 de seguridad** (cierra 2 vías 🔴 y desbloquea el resto).
- **2 upgrades de núcleo** desbloquean medio catálogo: **divulgación selectiva** y **modo "actúa por mí con gate"**.
- La **cuña 1** (autónomo español: VeriFactu + cobros) se cierra en la **Fase 3** (bucle e2e cobros con
  recibo 🟢 ×5). Las skills de la cuña encajan en Fases 2-3; las no adyacentes son **VISIÓN post-cuña** (D-86).
- **Tesis grande** para enmarcar el roadmap largo: *LoomBit = capa de soberanía personal (el agente LOCAL
  que representa al usuario frente a instituciones y empresas).* Ver §8.

---

## 1. Encaje en las fases del roadmap (`docs/ESTADO_Y_ROADMAP.md`)

| Pieza | Fase del roadmap | Prioridad | Nota |
|---|---|---|---|
| **P0 seguridad** (CaMeL wired + valla autoprotección `write_file` + spotlighting) | transversal, ANTES de todo | **P0** | cierra red team 🔴; precondición de toda skill que lea contenido no confiable |
| Cognición→contexto · ledger encadenado (AgentStore→CaseFile) · candado numérico | Fase 2-3 (núcleo de la cuña) | P1 | reusa `expedientes.py`, `comprension.py`, `modelo_303.py` |
| `Skill A` Visión Documental + Gastos OCR + Norma 43 (**intake**) | Fase 2 (datos antes del bucle) | P1 | "primero INTAKE de facturas" ya está en el roadmap (F-5) |
| `Skill A` WhatsApp Cobros + `Skill D` Morosidad + Radar Predictivo | **Fase 3** (cierra cuña 1) | P1 | el bucle e2e de cobros es el camino crítico |
| `Skill D` VeriFactu + Facturae + SII + 130/111/115 + Calendario + 390/190 | Fase 3-4 (completar cuña) | P1-P2 | deadlines: VeriFactu jul-2026/2027, Facturae RD238 oct-2026 |
| Constrained decoding · router de modelos (Jetson) | Fase 4-5 (robustez/coste) | P2 | "cero fallos" + viabilidad edge |
| `sandbox/` completo + unificar gate por `safety_class` | antes de autonomía proactiva | P2 | habilita Routines proactivas seguras |
| Skills **no adyacentes** (salud, legal, consumidor, etc.) | **post-cuña (VISIÓN)** | radar | D-86: cerrar cuña 1 al 100% antes de abrir cuña 2 |

---

## 2. Catálogo COMPLETO de skills propuestas (~80) — backlog navegable

> Código de autoridad: C>W>G>D>A>X. Estado de TODAS = **propuesta (⬜)**. "Reusa" = qué del repo aprovecha.

### 2.1 Cuña 1 — autónomo español (VeriFactu + cobros) — construir primero
| Skill | Cód. | Reusa | Fuente radar |
|---|---|---|---|
| WhatsApp Cobros | A | `decisions_cobros.py` | WhatsApp 3x |
| Morosidad (interés 10,15% + 40€) | D | cálculo Decimal | Ley 3/2004 |
| Radar de Morosidad Predictivo | D | histórico `expedientes` (ML local) | chatfin AR |
| Visión Documental (Qwen-VL) | A | `read_invoice` + candado nº | SLM/Qwen-VL |
| Gastos & Tickets OCR (homologado AEAT) | A | Visión Documental | okticket |
| Conector Norma 43 (C43) | A | `conciliacion_cobros.py` | quipu N43 |
| Open Banking (AISP, OPT-IN) | A | conciliación | PSD2 AISP |
| Conector AEAT/Sede (certificado) | A | — | (conector que falta) |
| VeriFactu | D | `expedientes` (chain) + `verifactu.py` | b2brouter |
| Facturae (XML + FACe) | D | — | RD 238/2026 |
| SII (libros IVA) | D | — | sage |
| Modelo 130 + 111 + 115 | D | cálculo Decimal | calendario AEAT |
| Calendario Fiscal AEAT | D | plazos/telar | cuéntica |
| Resumen Anual (390/190) | D | agrega trimestrales | — |
| Presupuestos → Factura | D | — | — |
| CRM ligero | D | `expedientes` (CaseFile) | — |
| Simulador Fiscal What-if | D | candado determinista | Hazel |
| Auditoría Inversa (simulacro inspección) | X | `guardas_fiscales` + ledger | (kernel) |
| Profesor / Explicador (303) | X | narración≠cifra | (kernel) |
| Anti-Fraude Fiscal (phishing AEAT/DGT) | D | reglas oficiales | AEAT |
| Runway / Salud Financiera (13 sem.) | D | expedientes + N43 | centime |
| Negociador de Proveedores | D | gate | — |
| Optimizador de Tesorería | D | — | — |
| Asistente de Inspección en vivo | D | expedientes | — |
| Conector TPV/e-commerce (Stripe/Shopify) | A | intake | — |
| Primer Empleado (alta TGSS, contrato) | D | — | — |
| Agente-a-Agente fiscal (A2A) | A | `mcp_server.py` | A2A LF |
| Del cobro al 303 (orquesta todo) | G | todas las anteriores | — |

### 2.2 Skills creativas (emergen del kernel) — alto valor, evaluables ya
| Skill | Cód. | Primitivo único | Fuente |
|---|---|---|---|
| Gemelo de Procedimiento (aprende viéndote) | X | Pilot-observer + fábrica | arXiv 2511.04137 |
| Cazador de Ayudas (Kit Digital IA) | D | perfil local + RAG + plazos | upliora |
| Abogado del Diablo (pre-mortem pre-gate) | C/X | gate + `reflexion.py` | arXiv 2405.16334 |
| Buzón Unificado (hilo por persona) | A | `comprension.py` | edesk |
| Caja Negra / Máquina del Tiempo | X | cadena hashes `verify_chain` | (kernel) |

### 2.3 No adyacentes (VISIÓN/radar — prueba del kernel blanco)
| Skill | Cód. | Reusa | Fuente |
|---|---|---|---|
| **Traductor de Burocracia** (+anti-fraude) | X | Profesor + Visión + plazos | lovepoundbury / AEAT |
| Salud Personal / Cuidado de Mayores | D | `expedientes` multi-tenant | Amazon/MS Health; 56B→387B |
| Legal/Contratos | D | plazos + `comprension` | GC.ai |
| Segundo Cerebro (PKM) | W/D | `rag.py` + `mcp_server` | Obsidian+MCP |
| Estudio/Tutor (repetición espaciada) | D | `rag.py` + `scheduler.py` | mystudylife |
| Finanzas Personales (hogar) | D | conciliación + Decimal | SenticMoney |
| Búsqueda de Empleo (Kanban) | D | `expedientes` (CaseFile) | skillscouter |
| Smart Home (local) | A | Adapter/Pilot + Voz | Home Assistant |
| Accesibilidad (verbosidad adaptativa) | D/A | Pilot + Voz + visión | Nature AURA |
| Visión Ambiental | A | conector Qwen-VL | Seeing AI |
| Voz local (Whisper.cpp) | X | ASR/TTS local | Home Assistant |
| Defensor del Consumidor (anti dark-patterns) | X | Pilot + gate | FTC/EU DFA |
| Negociador Personal (móvil/luz/coche) | X | modo "actúa por mí" | CarEdge / agent economy |
| CISO Personal / Guardián Digital | X | local | — |
| Apoderado Digital (gemelo cognitivo) | X | memoria + reglas | — |
| Compañero de Duelo (no terapia) | X | local + guardarraíles | — |
| Ejecutor Digital / Acompañante de Trámites | X | `expedientes` (checklist+chain) | swiftprobate |
| Legado Digital | X | ledger + divulgación selectiva | digital afterlife |
| Cápsula del Tiempo Familiar | X | liberación condicional | — |
| Coach de Decisiones de Vida | X | Pre-mortem+Investigador+Diario | — |
| Investigador Personal (deep research) | X | RAG + web_fetch | agentic.ai |
| Investigador Científico/Ciudadano | X | RAG + procedencia | — |
| Memoria de Relaciones | X | `comprension.py` | — |
| Radar de Renovaciones | X | predictivo + dark-patterns | FTC/EU |
| Director de la Casa | X | routines | — |
| Onboarding/Enseñar | X | Gemelo de Procedimiento | — |
| Diario de Vida Verificable | X | cadena hashes + divulgación selectiva | eIDAS2 |
| Pre-mortem de Decisiones Personales | X | `reflexion.py` | — |

---

## 3. Upgrades de NÚCLEO (Skill W) — habilitan el catálogo

| # | Upgrade | Archivos | Desbloquea |
|---|---|---|---|
| K1 | **Wirear CaMeL** (pasar `contenido_no_confiable` en `loop.py:706` + IBAN/importe) | `agent/loop.py`, `policy/authority_plane.py` | toda skill que lea contenido no confiable |
| K2 | **Valla de autoprotección** (`fs_deny`) en `write_file`/`run_shell` | `tools/base.py`, nuevo `sandbox/policy.py` | autonomía F4; corta auto-reescritura |
| K3 | **Spotlighting** (delimitadores aleatorios al inyectar) | `agent/contexto.py`, `authority_plane.sanear_dato` | anti prompt-injection (OWASP LLM01) |
| K4 | **Cognición→contexto** (expediente/comprensión antes del ReAct) | `agent/contexto.py`, `expedientes.py`, `comprension.py` | que el agente actúe con cognición |
| K5 | **Ledger único** (AgentStore→cadena de hashes del CaseFile) | `agent/run.py`, `expedientes.py` | recibo inmutable + VeriFactu + Caja Negra |
| K6 | **Candado de procedencia numérica** + property tests 303 | `policy/authority_plane.py`, `modelo_303.py` | determinismo por construcción |
| K7 | **Constrained decoding** (gramática llama.cpp/XGrammar) | `llm.py` | extracción 100% válida |
| K8 | **Router de modelos** + presupuesto VRAM/latencia | `llm.py`, `config.py` | viabilidad Jetson |
| K9 | **Divulgación selectiva** (credenciales verificables, ZK; eIDAS2) | nuevo `policy/` + `expedientes.py` | compartir lo justo; Legado/Diario/Facturae |
| K10 | **Modo "actúa por mí" con gate** (negociar/cancelar/alegar) | `policy/authority_plane.py`, tools nuevas | Negociador/Defensor/Renovaciones |
| K11 | **`sandbox/` completo** (policy+runner+límites) + unificar gate `safety_class` | nuevo `sandbox/`, `tools/registry.py`, `agent/loop.py` | autonomía proactiva segura |

---

## 4. Índice de documentación (qué mirar para qué)

| Documento | Para qué |
|---|---|
| `docs/SINTESIS_COMPLETA_LOOMBIT.md` | **Todo lo hablado** consolidado (A-M): leyes, Qwen, capas, red team, regulación, técnica, mercado, skills |
| `docs/ARQUITECTURA_PLATAFORMA_LOOMBIT.md` | Diseño + 9 rondas. §0-16 base · §18 red team/sandbox · §19 cognición/ledger/cifras/coste · §20 skills cuña · §21 fiscal triple · §22 no adyacentes · §23 más no adyacentes · §24 creativas · §25 maduración+adyacentes · §26 fuera de la caja (tesis soberanía) |
| `docs/HANDOFF_ARQUITECTURA_PLATAFORMA.md` | Arranque rápido + backlog accionable P0→P2 |
| `docs/ROADMAP_INTEGRACION_PLATAFORMA.md` | **Este hub** (integración roadmap + catálogo + índices) |
| `docs/RADAR.jsonl` | 63 señales con FUENTE (ver §5) |
| `docs/DECISIONES.md` → D-99 | Entrada de bitácora de este flujo |
| `docs/ESTADO_Y_ROADMAP.md` | **Fuente de verdad del estado** (fases, tests, conectores) — §META-4 |
| Código clave | `agent/loop.py`, `policy/authority_plane.py`, `llm.py`, `rag.py`, `tools/registry.py`+`base.py`, `expedientes.py`, `comprension.py`, `skill_d_fiscal/`, `mcp_server.py`, `seguridad_web.py` |

---

## 5. Índice del radar (`docs/RADAR.jsonl`) — temas para futuras investigaciones

Las 63 señales (cada una con FUENTE real y PROPUESTA) cubren, entre otras:
- **Regulación ES:** VeriFactu, Facturae/Crea y Crece (RD 238/2026), SII, modelos 130/111/115, calendario
  fiscal, Ley 3/2004 morosidad, phishing AEAT, gastos deducibles + OCR homologado, Norma 43.
- **Técnica IA:** constrained decoding, prompt injection/OWASP LLM01/spotlighting, SLM/Qwen-VL on-device,
  GEPA/Pareto, OSWorld, A2A/MCP/ACP, credenciales verificables + divulgación selectiva (eIDAS2),
  learning-from-demonstration, devil's advocate/anticipatory reflection.
- **Mercado/producto:** WhatsApp cobros (3x), open banking AISP, cuidado de mayores (56B→387B), agent
  economy/negociación (CarEdge), cash-flow (82% quiebras), dark patterns (FTC/EU), segundo cerebro,
  tutoría, finanzas personales local-first, accesibilidad.

> Para refrescar el radar (D-90, frescura ≤45 días): `python3 scripts/auditoria_radar.py`. Añade señal con
> `{fecha, tema, fuente(http), evidencia, hallazgo, propuesta}`.

---

## 6. Agenda de investigación futura (huecos no resueltos)

1. **Sandbox en Jetson:** ¿nsjail/firejail vs contenedor para tools `safety_sensitive`? Coste en Orin NX 16GB.
2. **Router de modelos:** ¿clasificador barato local para decidir 7B vs 14B? Presupuesto VRAM con 2 modelos + embeddings.
3. **Constrained decoding en LM Studio:** ¿soporta gramática/JSON-schema nativo, o hay que ir a llama.cpp directo?
4. **Divulgación selectiva (K9):** ¿SD-JWT / BBS+ encajan con el ledger de `expedientes`? ¿eIDAS2/EUDI Wallet integrable en local?
5. **A2A (K10/Skill A):** ¿exponer Agent Card sobre el `mcp_server` existente? Modelo de confianza M2M sin saltarse el gate.
6. **Conector AEAT/Sede:** certificado digital local + automatización de presentación (riesgo legal/seguridad — investigar a fondo).
7. **OCR homologado AEAT:** ¿qué exige la homologación para que el ticket digital tenga validez legal?
8. **ML de morosidad predictivo:** modelo interpretable (logístico/árbol) sobre datos propios; evitar caja negra; explicabilidad.
9. **Métrica north-star:** instrumentar "% tareas cerradas al 100% sin revisión humana" como eval continuo.

---

## 7. Reglas para convertir una propuesta en TAREA (no saltárselas)

1. **D-86 anti-dispersión:** no abrir skills no adyacentes hasta cerrar la cuña 1 (Fase 3, cobros e2e 🟢).
2. **P0 antes que skills:** K1+K2+K3 (CaMeL + valla + spotlighting) van primero; las skills que leen contenido no confiable son inyectables sin ellos.
3. **D-90 radar:** antes de construir, busca en la web, aplica, deja señal con FUENTE en `docs/RADAR.jsonl`.
4. **Arnés ANTES de tocar** (golden/test ejecutable; en vivo si toca el servidor). Rama/worktree por cambio.
5. **Leyes inviolables:** LLM no ejecuta · cifras/consecuentes por código determinista · gate humano a efectos externos · local-first · todo deja recibo (DoD) · no tocar pesos · `Skill D` no contamina el núcleo / `Skill A` reemplazable.
6. **"Hecho" lo declara `scripts/verify.py` + check verde de GitHub, no el hilo.** Estado honesto 🟡/🟠/🟢.
7. **Una entrada en `docs/DECISIONES.md` por decisión.** Ficheros < ~400 líneas (ratchet).

---

## 8. Marco estratégico para el roadmap largo (opcional, post-cuña)

**LoomBit = capa de soberanía personal: el agente LOCAL que representa al usuario frente a instituciones y
empresas en un mundo digital asimétrico.** Cada empresa tiene una IA para extraer al usuario; falta una IA
*de su lado*, y eso solo puede ser local. Piezas que lo habilitan (ya en el catálogo/upgrades): A2A+MCP,
credenciales verificables + divulgación selectiva, negociador/defensor/anti-fraude, ledger con procedencia.
La cuña fiscal (autónomo español) es el primer terreno donde la asimetría duele (Hacienda, banco, morosos);
la tesis escala a cualquier persona. **El foso es estructural:** local-first es lo que hace posible un
agente que trabaja PARA el usuario, no contra él. Usar como norte de cuña 2+, sin romper D-86.
