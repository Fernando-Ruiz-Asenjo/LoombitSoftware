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

## Cómo se alimenta este radar
1. **Claude (yo), de forma continua** — al trabajar, propongo aquí lo que veo de vanguardia aplicable.
2. **Routine "tech/normativa radar"** (futura) — barrido periódico de normativa (BOE/AEAT) y estado del arte → nuevas filas con fuente.
3. **Del propio sistema** — la Fábrica de Skills detecta carencias reales y las sube aquí.

> Nota: cuando una idea madura y se decide, se mueve a `INNOVACIONES.md` (con DoD) y al roadmap.
