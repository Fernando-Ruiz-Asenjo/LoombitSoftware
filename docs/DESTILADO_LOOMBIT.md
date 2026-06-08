# Destilado de Loombit — qué es, su filosofía y su operativa (norte)

> El único documento que hay que leer para "entender Loombit hoy". Destila los 26 docs del
> repo a través de la operativa y la filosofía actuales. Arriba del todo en la jerarquía
> documental. *Generado: 2026-06-08. Vivo.*

## 1. Qué es Loombit (en una frase)

Un **sistema operativo administrativo local-first que se mejora solo**: percibe el trabajo
real de una PYME/autónomo, prepara el trabajo, pide aprobación, ejecuta, deja recibo y
**aprende** — y con ese aprendizaje fabrica y afina sus propias skills.

No es "un asistente que responde". Es un operador que **anticipa, prepara y aprende**, con
el humano aprobando todo efecto externo.

## 2. La filosofía (lo innegociable)

1. **No se puede mentir (DoD).** Nada es 🟢 sin ejecución real contra el servicio real, con recibo. Si es parcial, se dice "parcial". (`DEFINITION_OF_DONE.md`)
2. **Privacidad estructural, no política.** Los datos no salen de la máquina; no es una promesa, es imposibilidad técnica.
3. **Autonomía supervisada.** El humano está en el bucle en el paso EJECUTAR para todo efecto externo. La autonomía vive en percibir→planear→preparar→anticipar.
4. **Aprendizaje = memoria operativa, NO fine-tuning de pesos.** Se aprende en memoria, prompts y manifests.
5. **Anti-dispersión.** Una cuña a la vez (ahora: Operador de Oficina, PYMES/autónomos España). El resto en `PARKED.md`.
6. **Proactividad e innovación permanente.** El sistema (y Claude) traen ideas de vanguardia sin que haya que pedirlas (`RADAR_INNOVACION.md`).

## 3. La operativa (el sistema)

**El bucle es la columna vertebral:**
```
PERCIBIR → PLANEAR → PREPARAR → PEDIR APROBACIÓN → EJECUTAR → RECIBO → APRENDER
```

**Tres subsistemas lo rodean y forman un volante (flywheel):**

```
        ┌──────────── SKILLS (D/W/A) ────────────┐
        │  el SABER del dominio, en capas          │
   ROUTINES ──ejecutan──> el BUCLE ──generan──> EXPERIENCIA
   (scheduler)                                      │
        └──> FÁBRICA DE SKILLS <── aprende de ──────┘
             (proceso + usuario + internet) → crea/afina SKILLS
```

- **Skills** (`ARQUITECTURA_SKILLS.md`): el conocimiento (Skill D: cobros, fiscal, laboral, banca, documental) sobre primitivas neutras (Skill W Admin Core) con conectores reemplazables (Skill A). Conocimiento ≠ primitiva ≠ conector.
- **Routines** (`ROUTINES_LOOMBIT.md`): agentes proactivos programados (cron/evento) que ejecutan el bucle solos y dejan recibo, con semáforo de aprobación.
- **Fábrica de Skills** (`FABRICA_DE_SKILLS.md`): aprende del proceso, del usuario y de internet para crear/afinar skills (loop tipo skill-creator, con evals y procedencia).

## 4. Las dos métricas de éxito (solo dentro de la cuña 1)

- **Operatividad 100%** = toda capacidad anunciada en 🟢 (DoD).
- **Autonomía supervisada 100%** = el bucle entero sin trabajo manual humano salvo la aprobación de efectos externos.

## 5. Principios de ingeniería de vanguardia (cómo se construye bien)

- **Evals de primera clase:** los supuestos A-G/I-X son los tests; una skill no es 🟢 sin pasarlos.
- **Verificación determinista del dinero:** IVA/totales/intereses en código; el LLM solo narra.
- **Procedencia + abstención:** lo legal/fiscal cita su fuente; si duda, escala (no inventa).
- **Autonomía que se gana:** el semáforo sube de tier lo que el usuario aprueba repetidamente.
- **Auto-crítica (Reflexion):** revisión del propio borrador antes de presentarlo en alto riesgo.

## 6. Mapa documental (jerarquía — qué leer para qué)

| Nivel | Documento | Para qué |
|---|---|---|
| **Norte** | este `DESTILADO_LOOMBIT.md` | entender el todo |
| **Operativo** | `CLAUDE.md` | reglas para trabajar en el repo |
| **Vivo** | `ESTADO_Y_ROADMAP.md` | dónde estamos, qué sigue (fuente canónica de estado) |
| **Sistema** | `ARQUITECTURA_SKILLS` · `ROUTINES_LOOMBIT` · `FABRICA_DE_SKILLS` | el cómo del flywheel |
| **Producto** | `INSIGHTS_PRODUCTO_Y_SUPUESTOS` · `INNOVACIONES` · `RADAR_INNOVACION` | mercado, supuestos, ideas |
| **Dominio** | `investigacion/*` · `DOMINIO_*` · `CONOCIMIENTO_OFICIO_*` · `BANCO_SUPUESTOS_*` | el saber administrativo |
| **Visión (histórica)** | `OBJETIVOS_GLOBALES` · `PLAN_MAESTRO_100` | la intención original (ver §7) |

## 7. Honestidad del destilado (qué emergió al releer todo)

- **Coherencia, no giro:** la operativa nueva (routines/fábrica/semáforo) ya estaba latente en `OBJETIVOS_GLOBALES` §4.2; aquí solo se le da nombre, estructura y técnica actual.
- **Hechos a reconciliar (obsoletos):** `CAPACIDADES_Y_HERRAMIENTAS` ("no puedo hacer push a GitHub" — ya no es cierto; instructor 7B→14B); `README` ("Fase 0" → Fase 1-2); `OBJETIVOS`/`PLAN_MAESTRO` (Gmail 🟡→🟢, OAuth conectado, instructor 14B).
- **Hueco:** `CLAUDE.md` referencia `docs/SKILLS.md` (no existe aún); `ARQUITECTURA_SKILLS.md` lo cubre en parte.
- **Canon vs histórico:** estado se lleva en `ESTADO_Y_ROADMAP`; `OBJETIVOS`/`PLAN_MAESTRO` quedan como visión original (no se reescriben con cada avance).
