# Fábrica de Skills — aprendizaje continuo y auto-autoría (local-first)

> Loombit **aprende del proceso, del usuario y de internet** para crear y mejorar sus
> propias skills — el análogo administrativo del `skill-creator`. Local-first, **sin tocar
> pesos** (el aprendizaje es memoria operativa + prompts + manifests), **con evals** y
> **con procedencia**. *Generado: 2026-06-08. Fases: 5 (núcleo) y transversal.*

## Por qué importa
Es la pieza que convierte a Loombit de "buen asistente" en "sistema que mejora solo".
Junto con Routines y la familia de Skills forma un **volante**:
**Routines** generan experiencia → la **Fábrica** la procesa → mejores **Skills** → que las **Routines** usan.

## Las 3 fuentes de aprendizaje

### 1. Del proceso (trajectory mining / auto-mejora)
- **Señal:** cada `AgentRun` + recibo en `runtime/local/` (qué tareas se repiten, dónde falla o loopea, qué tools se usan).
- **Mecanismo:** pase de reflexión sobre los runs → patrones a memoria **procedural** → propone una skill/plantilla nueva o un arreglo.
- **Ejemplo:** "siempre fallo extrayendo facturas del proveedor Z → ticket para mejorar el extractor".

### 2. Del usuario (preference learning local)
- **Señal:** cada **aprobar / editar / rechazar** en el gate del semáforo es una etiqueta. El *diff* entre lo propuesto y lo enviado es oro.
- **Mecanismo:** alimenta memoria **procedural + semántica** (`EntityProfile`) y refina el prompt de la skill. **Autonomía graduada:** lo aprobado N veces sube `ASSISTED`→`PASSIVE`.
- **Ejemplo:** "siempre suaviza el tono de los recordatorios → aprende ese tono".

### 3. De internet (RAG con procedencia + Claude/web + routine)
- **Señal:** normativa (BOE/AEAT), mejores prácticas, "lo último". **Canal:** RAG con **cita de fuente** + **Claude (yo) + web** + una routine **"tech/normativa radar"** periódica.
- **Mecanismo:** del conocimiento + los patrones, **redacta una skill nueva** (manifest + system prompt + supuestos como evals).
- **Ejemplo:** "VeriFactu cambia en 2027 → propone actualizar `Skill D Fiscal` con la fuente".

## El loop de autoría (skill-creator, versión Loombit)
```
detectar necesidad → borrador Skill X (experimental) → tests = supuestos como EVALS
   → medir → iterar → revisión humana → promover a Skill D
```
Una skill auto-creada **empieza como `Skill X` y NO gobierna comportamiento hasta promoverse**
(regla de la taxonomía). Los **supuestos A-G/I-X son el banco de evals** (ver `INNOVACIONES.md`).

## Restricciones duras (honestidad — no negociables)
- **Sin fine-tuning de pesos** (regla del proyecto): el aprendizaje vive en memoria, prompts y manifests.
- **Los datos del usuario no salen de la máquina** sin consentimiento; el RAG de internet es de fuentes públicas.
- **Toda afirmación legal/fiscal lleva cita** y, si no hay certeza, **abstención + escalado** (no inventar).
- **Verificación determinista del dinero:** IVA/totales/intereses se calculan en código; el LLM solo narra.

## DoD de una skill auto-creada (cuándo pasa de X a D 🟢)
Pasa sus supuestos-eval contra datos reales, deja recibo, tiene fuente para sus afirmaciones,
la ruta de fallo bloquea limpio, y un humano la ha revisado y promovido.
