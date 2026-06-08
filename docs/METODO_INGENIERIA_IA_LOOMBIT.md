# Método de ingeniería de IA de Loombit — construir con método, no a tientas

> Destilado de cómo construyen sistemas con LLM los que esto ya les funciona (Anthropic, OpenAI,
> la comunidad de evals, la investigación de agentes que aprenden). El objetivo es dejar de ir
> "dando tumbos y con suerte" y seguir un **método repetible**. *Generado 2026-06-08. Vivo.*

## 0. El diagnóstico (por qué hace falta esto)

Hasta ahora cada arreglo ha sido una corrección reactiva verificada "a ojo" una vez. Eso es
trial-and-error: frágil y no acumula. El campo tiene un método mejor, y es **medible**.

## 1. El método central: evals dirigidas por análisis de error

El consenso (Hamel Husain & Shreya Shankar, el mismo material que se enseña en OpenAI/Anthropic):
**no se empieza imaginando evals; se empieza mirando fallos reales.** El bucle:

1. **Recoger trazas reales** de uso (las tenemos: `runtime/local/conversations/*.jsonl`, `agent_runs.json`).
2. **Análisis de error**: leer las trazas y anotar en abierto qué falla (metodología de investigación cualitativa).
3. **Taxonomía de fallos**: agrupar las notas en categorías y **contar frecuencias**.
4. **Escribir evals para los fallos que SÍ ocurren** (no los imaginados): asserts deterministas o juez-LLM.
5. **Iterar midiendo**: ningún cambio se da por bueno hasta que mueve la métrica del eval. Cero "a ojo".

Esto es el antídoto exacto a "ir a tientas": se mide el fallo real, se ataca por frecuencia, se verifica con número.

## 2. Patrones de arquitectura fiable (12-Factor Agents · Anthropic)

- **El LLM se espolvorea SOLO donde el razonamiento probabilístico aporta; el resto es software bien
  hecho.** Los agentes que aguantan en producción "no son seres autónomos mágicos: son software
  tradicional bien hecho con LLM en los puntos justos". → Resuelve con **principio** la tensión
  código-vs-modelo: el *dato/identidad/dinero* es código; el *criterio/redacción/intención* es el LLM.
- **Pasos pequeños y componibles** (prompt chaining, routing) en vez de un megaprompt que lo haga todo
  y rezar. Descomponer una tarea en subtareas claras sube la fiabilidad.
- **Evaluador–Optimizador** (generar → criticar contra rúbrica → refinar, con límite de reintentos):
  separar "generar" de "criticar" da más calidad que un solo disparo. Es la versión productizada de la auto-crítica.
- **Estado y control de flujo FUERA del LLM**; **salidas estructuradas + validación + guardas que
  fallan en cerrado**. Nunca se confía un identificador (email, IBAN, NIF) a lo que "salga" del modelo.

## 3. Aprendizaje sin fine-tuning (general, agnóstico al dominio)

Coincide con vuestra doctrina ("aprender = memoria operativa, NO pesos"). El estado del arte:

- **Reflexion** (Shinn et al.): el agente **reflexiona en lenguaje** sobre el resultado y guarda la
  lección en memoria episódica; en el siguiente intento la usa. Sin tocar pesos. Es "que piense lo que hizo".
- **ExpeL**: extrae reglas comparando trayectorias buenas vs malas — con un **aviso clave**: no metas
  todo lo aprendido en cada prompt; **recupera solo lo relevante** (si no, escala fatal).
- **Memoria por capas con procedencia** (MemGPT/Letta): caliente (perfil/tarea), reciente, archivo; con
  **verdad preservada** para no cristalizar basura (justo el bug de `jana.espinal`).
- **DSPy** (Stanford): no se afinan los prompts a mano por prueba-y-error; se **optimizan contra una
  métrica** con ejemplos. Un 14B con pipeline optimizado supera al few-shot estándar por mucho. → La
  alternativa sistemática a que yo edite el prompt cinco veces a ojo.

**Clave:** el aprendizaje es **una sola pieza general** (reflexión → lección → recuperar relevante),
no código por tarea. Correos hoy, facturas mañana, sin volver a tocar el "aprender".

## 4. El instrumento de medida: LLM-como-juez

Para medir calidad abierta (¿es un buen correo?) se usa un LLM con **rúbrica explícita y criterios
separados** ("no se presenta como bot", "asunto deducido del cuerpo", "firma del usuario"), evidencia
concreta y no descriptores vagos. Más fiable en **pairwise** (A vs B) que en nota absoluta; mitigar
sesgo de posición (aleatorizar orden) y de longitud.

## 5. APLICADO — análisis de error de NUESTRAS trazas reales

Taxonomía sacada de `conversations/*.jsonl` + `agent_runs.json` (datos reales, no imaginados):

| # | Fallo (evidencia real) | Frecuencia | Patrón que lo cura (§) |
|---|---|---|---|
| F1 | Pregunta el asunto ("¿Qué asunto le quieres dar al correo a Jana?") | alta (repetido) | LLM espolvoreado: lo deduce; barrera de código (§2). *Ya mitigado.* |
| F2 | **Inventa/equivoca el destinatario** (`jana.espinal@gmail.com`) y a veces pregunta, a veces inventa | alta | Nunca confiar identificador al modelo; resolver por frecuencia o preguntar; guarda fail-closed (§2) |
| F3 | Dos fuentes de contacto incoherentes: `contacts_find` (Google, no halla "Jana Wall") vs memoria (tenía `jana.espinal`) | media | Una resolución única, rankeada, con procedencia (§2,§3) |
| F4 | Se presenta como bot ("soy un agente autónomo…") | media | Rúbrica + evaluador-optimizador (§2,§4) |
| F5 | Cristaliza un dato falso en memoria y lo reutiliza | media | Memoria con verdad/procedencia, revocable (§3) |
| F6 | Bucle hasta max_steps (20) sin recuperarse; repite el mismo error entre runs idénticos | alta | Reflexión que aprende del fallo (§3); routing/recuperación (§2) |
| F7 | `\n` literal y salidas triviales (asunto vacío, cuerpo "Hola") | media | Salida estructurada + validación (§2) |
| F8 | Decenas de runs huérfanos en "running" martilleando el 14B | alta (higiene) | Estado/ciclo de vida fuera del LLM, limpieza (§2) |

## 6. El plan (orden por frecuencia × palanca, medido con evals)

1. **Construir el eval-set** que codifica F1–F8 como casos (entrada → comportamiento esperado), con
   asserts deterministas (F2,F3,F7,F8) + juez-LLM con rúbrica (F4). Es el instrumento; sin él seguimos a ciegas.
2. **F2/F3 (destinatario)** — resolución única por frecuencia, cero invención, guarda fail-closed. Medir contra el eval.
3. **F5/F6 (aprendizaje general)** — la pieza de Reflexión+memoria con procedencia (§3), agnóstica al dominio.
4. **F4 (calidad)** — evaluador-optimizador con rúbrica; más adelante, optimizar el prompt estilo DSPy contra el eval.
5. **F8 (higiene de runs)** — ciclo de vida y limpieza fuera del LLM.

Regla nueva, innegociable: **cada cambio se mide contra el eval-set; si no mueve la métrica, no se da por hecho.**

## 7. Encaje con la doctrina que ya tenéis

Esto no es ajeno a Loombit: es la versión **rigurosa** de lo que ya creéis. "Los supuestos
(A-G/S-01…) son los tests" (`INSIGHTS_PRODUCTO_Y_SUPUESTOS.md`) **es** eval-driven development; el DoD
(🟢 con recibo) **es** medir antes de afirmar; "auto-crítica/Reflexion" ya está en el `DESTILADO`. Lo
que faltaba era el **instrumento** (el eval-set) y la **disciplina** (medir cada cambio). Eso es lo que fija este doc.

## Fuentes

- [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
- [12-Factor Agents (HumanLayer)](https://www.humanlayer.dev/12-factor-agents)
- [Hamel Husain & Shreya Shankar — LLM Evals / Error Analysis](https://hamel.dev/blog/posts/evals-faq/)
- [Reflexion (Shinn et al., arXiv 2303.11366)](https://arxiv.org/abs/2303.11366)
- [DSPy (Stanford, arXiv 2310.03714)](https://arxiv.org/abs/2310.03714)
- [Letta/MemGPT — Agent Memory](https://www.letta.com/blog/agent-memory)
- [Evidently — LLM-as-a-judge](https://www.evidentlyai.com/llm-guide/llm-as-a-judge)
- [Evaluator-Optimizer pattern](https://www.agentpatterns.ai/agent-design/evaluator-optimizer/)
