# Fábrica de Skills — aprendizaje continuo y auto-autoría (local-first)

> Loombit **aprende del proceso, del usuario y de internet** para crear y mejorar sus
> propias skills — el análogo administrativo del `skill-creator`. Local-first, **sin tocar
> pesos** (el aprendizaje es memoria operativa + prompts + manifests), **con evals** y
> **con procedencia**. *Generado: 2026-06-08. Fases: 5 (núcleo) y transversal.*

## Estado: 🟡 construido (2026-06-08) — `loombit_operator/fabrica/` (Skill X)

El núcleo de auto-autoría GOBERNADA ya existe y está testeado (+16 tests; D-39). Diseño destilado
del estado del arte 2025-26 (ver `RADAR_INNOVACION.md` barrido 4). Mapa de módulos:

| Módulo | Qué hace |
|---|---|
| `fabrica/seguridad.py` | **Gate de seguridad** (linchpin): AST allowlist + sandbox de builtins recortados. El código auto-escrito no se ejecuta sin vetarse. |
| `fabrica/validacion.py` | **Arnés grado-foso** (la recompensa verificable): 7 puertas en cascada — seguridad→contrato→black→ruff→import→**su eval**→sin regresión. |
| `fabrica/necesidad.py` | Detecta huecos ÚTILES (lo que el agente pidió + tools que fallan en bucle). No micro-tweaks. |
| `fabrica/autoria.py` | Redacta la tool con el **coder local** + lazo de auto-reparación (realimenta el fallo del arnés). |
| `fabrica/propuesta.py` | Store gobernado + **linaje** con fitness. Estado PENDIENTE→APROBADA solo por gate humano. |
| `fabrica/ciclo.py` | Orquesta `detectar→redactar→validar→proponer`. **Solo propone, nunca aplica.** |
| `fabrica/materializar.py` | Tras aprobar, materializa la tool en cuarentena `generadas/` (re-verificada) y la registra. |
| `fabrica/fuentes.py` | **El abanico**: registro EXPANDIBLE de fuentes de oportunidad (dentro + fuera + meta). |
| `fabrica/red.py` | **Lo de FUERA**: radar de inteligencia (GitHub/HackerNews/arXiv/BOE) que trae mejoras con cita. |
| `fabrica/meta.py` | **Meta**: la Fábrica amplía su propio abanico de escenarios (auto-mejora del motor). |
| `fabrica/interno.py` | **Lo de DENTRO (código en uso)**: marca bugs (ruff-B), TODO/FIXME, ficheros >400 líneas, prompts (GEPA), huecos de eval. |
| `fabrica/reparar.py` | Propone una reparación del código/prompt en uso como **diff validado con gate** (no escribe; guard de API en uso). |
| `fabrica/oportunidades.py` | Store de hallazgos de la Red/cognición/meta (inteligencia citada) para revisión humana. |
| `routers/fabrica.py` | API `/fabrica/*` (ciclo, propuestas, oportunidades, aprobar, descartar, estado). |

**La línea dura aplicada:** evolucionamos el andamiaje (código/tools/manifests), **nunca los pesos**.
**Por qué gobernado:** SkillsBench (2025) mide que la auto-generación SIN verificación iterativa
**empeora** el sistema; el validador-foso + gate humano + local es lo que la vuelve net-positiva.
**Pendiente a 🟢:** ciclo contra el coder real proponiendo tools útiles de carencias reales; promoción
Skill X→estable tras N aprobaciones; sandbox en contenedor (hardening).

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
