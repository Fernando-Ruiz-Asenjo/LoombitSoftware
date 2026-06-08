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

## Cómo se alimenta este radar
1. **Claude (yo), de forma continua** — al trabajar, propongo aquí lo que veo de vanguardia aplicable.
2. **Routine "tech/normativa radar"** (futura) — barrido periódico de normativa (BOE/AEAT) y estado del arte → nuevas filas con fuente.
3. **Del propio sistema** — la Fábrica de Skills detecta carencias reales y las sube aquí.

> Nota: cuando una idea madura y se decide, se mueve a `INNOVACIONES.md` (con DoD) y al roadmap.
