# HANDOFF — Arquitectura de plataforma LoomBit (Qwen motor / LoomBit SO)

> **Para la próxima sesión.** Punto de entrada ÚNICO a este flujo. Si solo lees un fichero, lee este;
> el detalle vive en `docs/ARQUITECTURA_PLATAFORMA_LOOMBIT.md` (§0–23) y `docs/RADAR.jsonl`.
> Rama: `claude/loombit-ai-architecture-nsyw5r` · PR draft **#57** (CI verde en el doc).

---

## 1. Qué se hizo (estado: SOLO DISEÑO, 0 implementación)

- Diseño consolidado de LoomBit como SO que gobierna a Qwen: *Qwen propone → LoomBit valida → el
  operador aprueba → las tools ejecutan → todo queda registrado.* Doc: `docs/ARQUITECTURA_PLATAFORMA_LOOMBIT.md`.
- **6 rondas de mejora adversarial** (45 vueltas), cada una verificada contra el código real:
  - §18 (R1) red team + contratos del sandbox + backlog
  - §19 (R2) cognición · ledger · determinismo de cifras · coste Jetson
  - §20 (R3) skills de la cuña (VeriFactu/cobros)
  - §21 (R4) familia Skill D fiscal TRIPLE + mejoras de núcleo
  - §22 (R5) skills NO adyacentes (prueba del kernel blanco)
  - §23 (R6) más skills no adyacentes + mejoras
- **45 señales de radar** con fuente real en `docs/RADAR.jsonl` (`scripts/auditoria_radar.py` verde).
- ⚠️ **Nada de esto está implementado en código.** Es análisis. La siguiente sesión debe CONSTRUIR.

---

## 2. Estado honesto de las 5 leyes (auditado contra el código)

| Ley | Estado real | Evidencia |
|---|---|---|
| 1. Qwen propone, código dispone | 🟢 | `loop.py:706` → `AUTHORITY_PLANE.autorizar()` |
| 2. Datos ≠ órdenes (CaMeL) | **🟠 DORMIDA** | `loop.py:706` NO pasa `contenido_no_confiable` → el filtro nunca dispara |
| 3. Gate humano efectos externos | 🟢 con fuga | `gmail_send` auto-envía si destinatario "claro" |
| 4. Local-first | 🟢 (solo red) | `seguridad_web.py`; NO contiene la ejecución |
| 5. Todo deja recibo | 🟢 | `AgentStore` + `runtime/local/` |

**2 vías 🔴 del red team (lo más urgente):**
1. **El agente puede reescribir sus guardarraíles:** `tools/base.py::_write_file` escribe en cualquier
   ruta (incluido `loop.py`, `authority_plane.py`, `.env`, token store). Escalada total.
2. **Inyección → acción consecuente:** con CaMeL dormido, un IBAN/importe de un correo de cliente puede
   fluir a una propuesta de cobro (la amenaza EXACTA de la cuña de morosidad).

---

## 3. Backlog priorizado (la tabla que manda)

| Prio | Acción | Archivos | Esfuerzo |
|---|---|---|---|
| **P0a** | Wirear CaMeL: pasar `contenido_no_confiable` en `loop.py:706` + cubrir IBAN/importe + test de inyección | `agent/loop.py`, `policy/authority_plane.py`, tests | bajo |
| **P0b** | Valla de autoprotección en `write_file`/`run_shell` (deny `loombit_operator/**`, `.env`, token store) | `tools/base.py`, nuevo `sandbox/policy.py` | bajo-medio |
| **P0c** | Spotlighting: delimitadores aleatorios al inyectar contenido leído | `agent/contexto.py`, `authority_plane.sanear_dato` | bajo |
| **P1a** | Cognición → contexto: inyectar estado de expediente/comprensión antes del ReAct | `agent/contexto.py`, `expedientes.py`, `comprension.py` | medio |
| **P1b** | `AgentStore` → eventos en la cadena de hashes del CaseFile (el ledger YA existe en `expedientes.py`) | `agent/run.py`, `expedientes.py` | bajo-medio |
| **P1c** | Candado de procedencia numérica + property tests sobre `calcular_303` | `policy/authority_plane.py`, `skill_d_fiscal/modelo_303.py` | bajo |
| **P1d** | Constrained decoding (gramática llama.cpp/XGrammar) para extracción crítica | `llm.py` | medio |
| **P1e** | Router de modelos (7B→14B solo lo duro) + presupuesto VRAM/latencia (Jetson) | `llm.py`, `config.py` | medio |
| **P2** | `sandbox/` completo (policy+runner+límites) + unificar gate por `safety_class` (loop+MCP) | nuevo `sandbox/`, `tools/registry.py`, `agent/loop.py` | medio-alto |

> **ACCIÓN SIGUIENTE ÚNICA: P0 (a+b+c).** Cierra las 2 vías 🔴, es bajo esfuerzo y es precondición de
> TODA skill que lea contenido no confiable. Construir esto ANTES que cualquier skill.

---

## 4. Skills propuestas (catálogo, NO implementadas)

**Cuña activa (autónomo español · VeriFactu + cobros) — orden por valor×deadline:**
1. `Skill A WhatsApp Cobros` + `Skill D Morosidad` (Ley 3/2004: interés 10,15% + 40€, cálculo determinista) — máximo ROI.
2. `Skill D Facturae` (Crea y Crece, RD 238/2026, 1-oct-2026) + `Skill D VeriFactu` (reusa cadena de hashes de `expedientes.py`).
3. `Skill A Visión Documental` (Qwen-VL local) con constrained decoding.
4. `Skill A Open Banking (AISP)` + `Skill D SII`.
5. `Skill G "Del cobro al 303"` (orquesta todo).

> **Regulación: 3 obligaciones distintas** — VeriFactu (antifraude) ≠ Facturae (formato B2B, Crea y Crece) ≠ SII (libros IVA).

**NO adyacentes (VISIÓN/radar, prueba del kernel blanco — NO construir hasta cerrar la cuña 1):**
`Skill D Salud Personal`/Cuidado de Mayores · `Skill D Legal/Contratos` · `Skill W/D Segundo Cerebro` ·
`Skill D Estudio/Tutor` · `Skill D Finanzas Personales` · `Skill D Búsqueda de Empleo` ·
`Skill A Smart Home` · `Skill D/A Accesibilidad` · `Skill A Visión Ambiental` · `Skill X Voz local`.

**Tesis validada:** los 6 primitivos del kernel (loop+gate · `expedientes`/CaseFile · `rag.py` ·
`scheduler`/plazos · Adapter/`pilot` · visión Qwen-VL) cubren ~10 dominios no adyacentes **sin tocar el
núcleo**. Y el foso **local-first escala con la no-adyacencia** (salud/finanzas/menores = dato más sensible).

---

## 5. Reglas inviolables al implementar (no las rompas)

1. **El LLM no ejecuta nada** — solo propone; el loop actúa vía `ToolRegistry`/`authority_plane`.
2. **Cifras y consecuentes (IBAN/importe/fecha/impuesto/destinatario) = código determinista** (Decimal), nunca el texto del modelo.
3. **Gate humano para todo efecto externo** (`requires_approval`/`safety_sensitive` → `PENDING_APPROVAL`).
4. **Local-first** — datos no salen; servidor solo 127.0.0.1.
5. **Todo deja recibo** — sin recibo de ejecución real no hay 🟢 (DoD).
6. **NO tocar pesos** (fine-tuning fuera de alcance; aprendizaje = memoria/RAG).
7. **Una skill de dominio NO mueve vocabulario al núcleo blanco**; los Adapters (`Skill A`) son reemplazables.
8. **D-86 anti-dispersión:** cerrar la cuña 1 (VeriFactu+cobros) al 100% antes de abrir otra.
9. **D-90 radar:** antes de construir, busca en la web, aplica, deja señal con FUENTE en `docs/RADAR.jsonl`.
10. **"Hecho" lo declara el gate (`scripts/verify.py`) + check verde de GitHub**, no tú. Rama/worktree por cambio; arnés (test) antes de tocar.

---

## 6. Punteros

- Diseño completo + 6 rondas: `docs/ARQUITECTURA_PLATAFORMA_LOOMBIT.md` (§0–23).
- Radar (45 señales, fuente real): `docs/RADAR.jsonl`.
- Código clave: `agent/loop.py` (ReAct), `policy/authority_plane.py` (gate/CaMeL), `llm.py` (cliente Qwen),
  `rag.py`, `agent/memory.py`, `tools/registry.py` + `tools/base.py`, `expedientes.py` (CaseFile + cadena de
  hashes), `comprension.py`, `skill_d_fiscal/` (303/verifactu/cobros), `mcp_server.py`, `seguridad_web.py`.
- Constitución/normas: `CLAUDE.md`, `docs/BRUJULA.md`, `docs/DEFINITION_OF_DONE.md`, `docs/ESTADO_Y_ROADMAP.md`.
- PR: #57 (rama `claude/loombit-ai-architecture-nsyw5r`).

**Primera tarea recomendada para la próxima sesión:** abrir rama desde main, implementar **P0a+b+c** con
su test de inyección (golden ANTES de tocar), `scripts/verify.py` verde, PR. No abrir skills hasta que P0 esté 🟢.
