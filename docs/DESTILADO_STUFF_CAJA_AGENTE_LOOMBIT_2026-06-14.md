# DESTILADO — La "Stuff", la Caja, el Agente Autónomo Local y la UI Adaptativa (Loombit)

> **Qué es esto:** destilación de una investigación de mercado/innovación con tres gorras
> (ingeniero senior de agentes IA · director de marketing prosumer · director de think tank).
> **Método:** 5 vueltas del harness `deep-research` (fan-out web + verificación adversarial a 3 votos
> por afirmación). Solo entra lo que sobrevivió a la verificación; lo refutado está al final.
> **La Vuelta 5 (UI generativa/adaptativa) se añadió el 2026-06-14 como §11.**
> **Fecha:** 2026-06-14. **Filtro duro aplicado a CADA idea:** valor alto/muy alto · utilidad
> grande/muy grande · visión y trayectoria · **gancho monetizable**. **Foso:** LOCAL. **Ley:** el
> LLM propone / el código dispone + gate humano para el efecto externo consecuente.
>
> **Honestidad de alcance:** la Vuelta 1 (mercado fiscal/GTM España: precios de Holded/Quipu,
> Kit Digital, timing VeriFactu) seguía corriendo al cerrar este documento; sus cifras de
> competidores **no están verificadas aquí** y se marcan como *pendiente V1*. Muchos benchmarks de
> modelos son *self-reported* (sin leaderboard neutral); el OCR en **español no está benchmarkeado**
> en ningún candidato. No se inventa nada: lo no verificado se dice.

---

## 0. La tesis en seis líneas

Loombit = **una caja donde escribes cualquier tarea y la hace**. Si la tarea cae *dentro de la caja*
(skill conocida) → vía rápida y determinista. Si cae *fuera* → un **agente autónomo de computer-use
LOCAL** la resuelve. Ese "fallthrough a agente autónomo local" es un **nicho de mercado vacío y
verificado**: ni Raycast, ni Asyar, ni Open Interpreter lo ocupan. Loombit gana por **tres fosos a la
vez** que nadie combina: **local** (datos en la máquina) + **seguridad por construcción** (donde
OpenClaw es un agujero) + **IA local ilimitada** (coste marginal cero, donde Raycast mide tokens). La
trayectoria es **cuña → plataforma**: entrar por un dolor agudo y convertirse en la capa-Stuff
indispensable de cualquiera ante un ordenador.

---

## 1. El hueco existe y está VACÍO (verificado, 3-0)

- **Raycast tiene la caja, no el agente.** Resuelve lenguaje natural → herramienta sobre las
  extensiones instaladas (AI Extensions) y enruta el texto no reconocido a la IA (*Fallback
  Commands → Quick AI*). Pero **NO cae a un agente que controle el ordenador** cuando no hay
  extensión. Su CEO lo llama "visión futura" y admite que los agentes actuales "en general, no
  funcionan". *(manual.raycast.com/ai/ai-extensions, techbuzz.ai)*
- **Asyar** (lanzador open-source local-first, Tauri/Rust, Ollama) tiene skills + agente con
  tool-calling, pero **sus agentes no son autónomos** para tareas abiertas. *(github.com/Xoshbin/asyar)*
- **Open Interpreter** ejecuta código en local contra **LM Studio `localhost:1234`** — el mismo
  patrón que ya usas — y es la mejor plantilla del fallthrough, pero es terminal de código, no caja
  de producto. *(github.com/OpenInterpreter/open-interpreter)*

**Conclusión:** el patrón "caja → fast-path skill → fallthrough a agente autónomo LOCAL" no lo ocupa
nadie. Es exactamente Loombit. **Apuesta contrarian #1.**

---

## 2. Arquitectura de la Caja (3 capas + reconciliación autonomía/gate)

```
  Escribes en la caja
        │
        ▼
  [1] ROUTER DETERMINISTA            ← encoder (ModernBERT/semantic-router), NO un LLM
        │   emite categoría + confianza; el CÓDIGO decide
        ├─► skill conocida ─────────► [FAST PATH] ejecución determinista (ya lo tienes)
        │
        └─► tarea abierta ─────────► [2] AGENTE AUTÓNOMO LOCAL (fallthrough)
                                          plan jerárquico proactivo (Agent-S2)
                                          + grounder GUI (Holo1.5-7B)
                                          + ejecución de código local (Open Interpreter)
                                                │
                                                ▼
                                          [3] GATE HUMANO  ← SOLO en efecto externo consecuente
                                              (enviar, pagar, presentar, borrar)
```

**La reconciliación clave** ("totalmente autónomo" vs "gate humano para todo efecto externo"): el
agente es **autónomo en lo local, la lectura y el cómputo**; el gate **solo salta en el efecto
externo consecuente**. Esto no es una limitación inventada: **Raycast, Asyar y Open Interpreter los
tres piden aprobación humana por defecto** — el gate es el **estándar esperado** del sector. Loombit
lo **mejora en UX**: ellos gatean *todo*; tú solo lo que importa. El sitio natural del gate es el
"Worker-compuerta" del patrón Agent-S2 (ver §3/§4).

---

## 3. Modelos concretos (verificados; con licencia/VRAM/benchmark)

| Rol en Loombit | Modelo | Licencia | Tamaño/VRAM | Benchmark (verificado) | Encaje |
|---|---|---|---|---|---|
| **Grounder GUI** (dónde clicar) | **Holo1.5-7B** | Apache-2.0 | ~8B, ~5-6GB INT4 → **cabe en 16GB** | ScreenSpot-v2 **93.31**, ScreenSpot-Pro **57.94** (self-rep.) | **FUERTE** — drop-in Qwen2.5-VL |
| Agente computer-use (alt.) | UI-TARS-1.5-7B | Apache-2.0 | 8B, cabe en 16GB | *números públicos REFUTADOS — no citar* | CON AJUSTE |
| Grounder de máxima precisión | Gelato-30B-A3B (MoE) | Apache-2.0 | 30B total → **borde/over 16GB** | SS-Pro **63.88**, OSWorld-G **69.15** (self-rep.) | CON AJUSTE (contrarian/upside) |
| **Router de la "caja"** | **vLLM Semantic Router** (ModernBERT+LoRA) | Apache-2.0 | encoder ligero (corre sin GPU) | +10.2pp MMLU-Pro, ~−47% latencia (paper, 2 baselines) | **FUERTE** — enrutado determinista |
| **OCR intake F-5** | **PaddleOCR-VL-0.9B** | Apache-2.0 | 0.9B → cabe de sobra | OmniDocBench fuerte | **FUERTE** — *español sin benchmark* |
| OCR intake F-5 (alt. MIT) | dots.ocr | MIT | ~3B, ~6-7GB | OmniDocBench tablas/layout top | FUERTE — *español sin benchmark* |
| OCR (evitar por licencia) | MinerU2.5-1.2B | **AGPL-3.0 (pesos)** | 1.2B | OmniDocBench **75.2** (no 86.2) | RELEVANTE — riesgo copyleft |

**Recomendación de stack:** router `ModernBERT` → fast-path; fallthrough con **Open Interpreter**
(código local) + **Holo1.5-7B** (grounding visual) + **Agent-S2 loop** (replanificación); intake F-5
con **PaddleOCR-VL** (o dots.ocr si prefieres MIT). **Validar en vivo** VRAM/latencia en Jetson y la
precisión en **facturas españolas reales** antes de declarar nada 🟢 (los benchmarks son self-reported
y el español no está medido).

---

## 4. Qué robamos de cada referencia

- **Raycast** → la caja NL + *Fallback Commands* + **plugins MCP que corren en LOCAL** (stdio/JSON-RPC)
  + el gate de aprobación por defecto. El patrón de extensibilidad ya resuelto.
- **OpenClaw / ClawHub** → el **estándar abierto SKILL.md de Anthropic** (adoptado por 40+ tools, incl.
  Claude Code) y el **registro público de skills** con **manifiesto declarativo de permisos por skill**.
  → Loombit puede ser **estándar-compatible** (portabilidad + reutilizar el ecosistema) en vez de
  inventar formato propio. *Pero* su seguridad es un desastre (ver §7): ese es nuestro argumento de venta.
- **Open Interpreter** → el bucle del fallthrough (ejecutar código local) ya contra `localhost:1234`.
- **Agent-S2** (arXiv 2504.00906) → **replanificación jerárquica proactiva** (regenera la cola del plan
  tras cada subtarea = recuperación de errores durable) + **mixture-of-grounding** (enruta cada acción
  al experto: Holo1.5 visual / PaddleOCR-VL textual). El **Worker-compuerta** = el sitio del gate humano.
- **Pieces** → la **capa de memoria local "siempre encendida"** (captura a nivel SO + grafo + consulta
  temporal en NL), con filtrado PII y toggle on-device. Es "cognición, no extracción" hecha producto.

---

## 5. La "Stuff" por persona — skills de alto valor

> Cada una con veredicto de encaje + etiquetas del filtro (V=valor, U=utilidad, M=gancho monetizable,
> E=esfuerzo, R=riesgo). Lo de bajo valor se ha descartado y no aparece.

### A) Quien TRABAJA con el ordenador
1. **Orquestador multi-app / anti-toggle (el fallthrough).** "Coge esto de A, transfórmalo, ponlo en B".
   Antídoto al *toggle tax* (HBR: ~1.200 cambios de app/día). **FUERTE** · V muy alto · U muy grande ·
   M directo (suscripción Pro) · E alto · R medio.
2. **Memoria local "siempre encendida" (estilo Pieces).** Captura por-app/PII → grafo → "¿qué estaba
   haciendo el martes con X?". **Coste de cambio que se acumula.** **FUERTE** · V muy alto · U muy grande ·
   M directo (Pro/per-seat) · E alto · R medio (permisos SO/privacidad).
3. **Form-filler universal LOCAL (web + PDF)** que tira de tu memoria local. Hueco sin ocupar (todos
   son cloud y silados). **FUERTE/contrarian** · V muy alto · M directo (Pro + por-formulario) · E medio-alto.

### B) Quien hace GESTIONES / vida (fuera del gremio)
4. **Intake de facturas F-5 (OCR local).** Desbloquea cobros + 303 + galaxia de golpe. **Es el
   bloqueador nº 1.** **FUERTE** · V muy alto · U muy grande · M directo (es el ancla de pago) · E medio.
5. **Operador de trámites España.** Vigila/asegura citas (Sede/SS/DGT/salud) y prerellena formularios
   con tu identidad, dentro de ToS — "no pierdas tu plazo/prestación" (OCU: la cita previa falla de
   verdad). **CON AJUSTE** · U muy grande · M directo (pack premium) · E medio-alto · **R alto** (ToS +
   guardarraíl ético: NO replicar la mafia de bots que revende citas a 50-300€).
6. **Cazador de suscripciones/cobros ocultos.** Revisa extractos locales, detecta suscripciones zombi.
   Ahorro tangible = fácil de cobrar. **CON AJUSTE** · M directo (% del ahorro / Pro) · E medio.

### C) Quien tiene OCIO con el ordenador
7. **Bibliotecario de medios local.** Fotos/vídeo/descargas: organiza, renombra, deduplica, busca por
   contenido con VL local. El caos de ficheros que todos sufren. **CON AJUSTE** · U grande · M indirecto
   (feature Pro) · E medio · R bajo.
8. **Automatizador de tareas repetitivas de ocio/creación** (resúmenes, conversiones, flujos repetidos).
   **RELEVANTE/contrarian** — evidencia de monetización más floja; explorar, no apostar fuerte aún.

> **Nota honesta:** el área de OCIO es donde la investigación verificada es más débil. Las ideas 7-8 se
> proponen con menos confianza que A/B; conviene validarlas antes de invertir.

---

## 6. Monetización y trayectoria cuña → plataforma

- **Plantilla probada (Raycast):** lanzador gratis + Pro 8-10 $/mes + add-on de IA aparte. La gente
  paga por **reemplazar 3-4 micro-apps con una**.
- **Ventaja estructural de Loombit (contrarian #2):** IA **local = coste marginal cero** → ofrecer
  **"IA ilimitada"** donde Raycast tiene que medir tokens cloud. Es margen, no eslogan.
- **Tercera palanca = marketplace de skills** (modelo ClawHub) sobre el **estándar SKILL.md**: skills
  de pago, con permisos declarativos. Efecto de red local + comunidad.
- **Cuarta palanca = licencia local** (perpetua/anual) para quien no quiere suscripción — encaja con
  el foso local.
- **Trayectoria:** puerta por un **dolor agudo y de pago** (cuña fiscal/cobros con deadline VeriFactu,
  o trámites España) → ensanchar a la **capa-Stuff** (memoria, form-filler, orquestación) → plataforma
  con marketplace. *(Cifras de mercado/competidores España: pendiente V1.)*

---

## 7. Riesgos y trampas (para no repetirlas)

- **El "do-everything assistant" horizontal genérico FRACASA** sin foso ni gancho ni cuña aguda. Por eso
  Loombit ancla en foso local + un dolor inicial concreto, no en "haz cualquier cosa" a secas.
- **Seguridad de skills (lección OpenClaw, aviso de Microsoft):** instalar una skill = instalar código
  privilegiado; el runtime funde **código no confiable + instrucciones no confiables** en un bucle.
  → Loombit debe tratar **toda skill de terceros como código no confiable** (leer/sandbox/permisos
  declarativos + CaMeL). Es el foso de seguridad **y** el mensaje de marketing ("el poder sin el agujero").
- **Computer-use sigue fallando** (OSWorld ~72-82% SOTA): el **gate humano antes del efecto es la red
  obligatoria**; no prometer autonomía total.
- **Español OCR sin benchmark · benchmarks self-reported · sin cifra de VRAM en Jetson:** validar en vivo
  antes de afirmar. Predicción ≠ hecho.
- **Ventana de trámites puede cerrarse:** Interior pilota passkeys/portal centralizado 2026.

---

## 8. Apuestas contrarian (marcadas)

1. **El fallthrough a agente autónomo LOCAL** — nadie lo ocupa (§1).
2. **IA local ilimitada como arma de precio** — invierte la estructura de coste de los cloud (§6).
3. **La seguridad como producto** — convertir el agujero de OpenClaw en la razón de compra (§7).
4. **Form-filler local + unificado (web+PDF)** — hueco sin ocupar (§5.3).
5. **Memoria on-device como coste de cambio** — el cloud no puede igualarlo por privacidad (§5.2).

---

## 9. Qué construir ya (orden propuesto)

1. **F-5 intake de facturas con OCR local** (PaddleOCR-VL/dots.ocr) + score de confianza por línea +
   gate. *Desbloquea cobros/303/galaxia. Es el cuello de botella.*
2. **El router determinista de la caja** (ModernBERT/semantic-router) → fast-path skills conocidas.
3. **El fallthrough mínimo** (Open Interpreter local + gate solo en efecto externo) para tareas abiertas
   simples; medir al estilo OSWorld, sin prometer autonomía total.
4. **Grounder Holo1.5-7B** cuando el fallthrough necesite controlar GUI; validar VRAM/latencia en Jetson.
5. **Capa de memoria local** (captura + grafo + consulta NL) como coste de cambio y base del form-filler.
6. **Estándar SKILL.md + manifiesto de permisos** como cimiento del futuro marketplace.

Cada uno con su arnés ejecutable y verificado en vivo antes de declararse 🟢 (Definición de Hecho).

---

## 10. Honestidad — qué se REFUTÓ (no usar)

- UI-TARS-1.5-7B: 94.2/61.6 ScreenSpot y 42.5/42.1 OSWorld/WAA → **refutado**, no citar.
- vLLM embedding-routing "10-50ms" → **refutado**.
- MinerU2.5 OmniDocBench "~86.2" → es **75.2**.
- "23 min para reconcentrarse", "$450B/año", "47s de atención", "2-3h/día en tareas repetitivas",
  precios de Rewind/Superhuman → **refutados** (humo de blogs reciclado).
- "local-first es requisito" para agentes personales → es **diferenciador, no requisito universal**.

**Fuentes clave verificadas:** manual.raycast.com · raycast.com/pricing · microsoft.com/security/blog
(OpenClaw, 19-feb-2026) · agentskills.io · github.com/openclaw/clawhub · github.com/OpenInterpreter ·
github.com/Xoshbin/asyar · huggingface.co/Hcompany/Holo1.5-7B · github.com/vllm-project/semantic-router ·
arxiv.org/abs/2510.08731 · arxiv.org/html/2504.00906v1 · huggingface.co/PaddlePaddle/PaddleOCR-VL ·
github.com/rednote-hilab/dots.ocr · pieces.app · hbr.org (toggling) · ocu.org (cita previa, 16-mar-2026).

> Señales añadidas a `docs/RADAR.jsonl` (D-90) el 2026-06-14 a partir de este destilado: ver el radar.

---

## 11. Vuelta 5 — UI generativa/adaptativa: el operador que CREA su propia interfaz (verificado 2026-06-14)

> **Pregunta:** ¿cuál es el estado del arte 2026 en interfaces que un agente genera/modifica sobre la
> marcha, y qué de ello es adoptable por un runtime **local-first** (FastAPI + Qwen local, single-page)
> para que Loombit materialice su pantalla según la tarea? **Resultado del harness:** 6 ángulos →
> 24 fuentes → 115 afirmaciones → 25 verificadas a 3 votos → **6 hallazgos sobreviven, 5 refutados**.
> **Honestidad de alcance:** **2 de los 5 ejes pedidos (malleable software · protocolos server-driven
> UI/AG-UI/MCP-UI) NO produjeron ni una afirmación verificada** → se marcan **pendiente V6**, NO como
> ausencia. Las fuentes se llegaron a descargar (son *leads*), pero ninguna afirmación pasó el 3-votos.

### 11.1 Lo verificado (qué adoptar · vigilar · descartar)

| Hallazgo | Veredicto | Voto | Encaje LOCAL |
|---|---|---|---|
| **Patrón "el LLM propone la UI / el código la dispone"** (tldraw `sanitizeAction`/`applyAction`: el LLM emite intents estructurados; código determinista valida, corrige IDs, normaliza y aplica; el modelo NUNCA toca el estado) | **ADOPTAR el patrón (oro)** | 3-0 | ✅ es la ley de Loombit aplicada a la UI |
| **Vercel AI SDK *Data Stream Protocol*** (SSE, agnóstico de lenguaje) servible desde **FastAPI + Qwen local** sin nube Vercel ni Node (plantilla oficial vercel-labs + `py-ai-datastream`) | **ADOPTAR el transporte (opcional)** | 3-0 | ✅ corre local; provider = endpoint OpenAI-compat local |
| **LÍMITE CRÍTICO:** ese protocolo transporta texto/tool-calls/**datos, NO componentes React**; el render de componentes ricos sigue siendo **capa JS/React** | (restricción del anterior) | 3-0 | ⚠️ no hay vía verificada Python-puro→componentes ricos |
| **Vercel AI SDK RSC / `streamUI`** (componentes React server-side) | **NO construir sobre ello** — experimental, pausado, Vercel migra a hooks | 3-0 | n/a |
| **Thesys C1** (GenUI-as-a-Service, GA abr-2025, OpenAI-compat, el más maduro) | **DESCARTAR por defecto** — cloud-only, manda datos a LLMs cloud de terceros; self-host solo en tier enterprise "Scale" | 3-0 | ❌ falla el foso LOCAL (vigilar como referencia de diseño) |
| **tldraw SDK licensing:** source-available, NO open source; producción ~6.000 $/año (hobby gratis con marca de agua); claves validan **client-side offline** | **copiar el PATRÓN, no embeber el SDK** sin pagar | 3-0 | ⚠️ compatible local-first pero ship comercial paga |

### 11.2 La lección que REFUERZA la ley de Loombit (no la contradice)

**Ninguna fuente verificada muestra la UI generada como camino de confianza para efectos consecuentes.**
Solo la capa de saneamiento de tldraw se acerca — y es **explícitamente NO un gate de seguridad** (es
integridad del lienzo, no frontera de confianza). → **Conclusión de producto:** la UI adaptativa de
Loombit es **capa de presentación/propuesta, jamás el camino de control**. El gate humano + el código
determinista siguen siendo el ÚNICO camino de confianza para €/IBAN/fechas/envíos. La adaptatividad
**ensancha la comprensión y la propuesta; nunca el efecto**. Esto encaja exacto con la Ley Fundacional
(Separación de Autoridades): el LLM puede *dibujar* la pantalla, pero el botón "enviar/pagar/presentar"
pasa por código + tarjeta, no por el markup que emitió el modelo.

### 11.3 Arquitectura propuesta — UI adaptativa local-first (propose/dispose para la interfaz)

```
  LLM local (Qwen) ──propone──► INTENT DE UI estructurado (JSON: tipo de vista + componentes + datos)
                                       │   (NO HTML/JS arbitrario: eso sería inyección)
                                       ▼
  CÓDIGO DETERMINISTA  ← valida/sanea contra un VOCABULARIO CERRADO de componentes (whitelist)
   (patrón tldraw)        corrige, normaliza, rechaza lo no permitido
                                       │
                                       ▼
  single-page UI de Loombit  ← instancia SOLO los componentes del catálogo (vanilla/JS hoy)
                                       │
                                       ▼  (si la vista dispara un efecto externo consecuente)
  GATE HUMANO (tarjeta)  ← el submit NO pasa por el markup del modelo; pasa por código + confirmación
```

Claves: (a) **vocabulario CERRADO** de componentes (el modelo *elige* de un catálogo; el código
*instancia*), nunca markup libre; (b) el catálogo neutro vive en el **núcleo blanco** (reutilizable),
los componentes de dominio en **skills**; (c) la **vía Python-native** (renderizar componentes ricos
sin React, vía esquema JSON server-driven) es el hueco real de nuestro stack → es lo que hay que
resolver, y es justo lo que NO se investigó esta vuelta (ver pendiente V6).

### 11.4 Honestidad — pendiente (V6) y refutado

**PENDIENTE V6 (no investigado / 0 afirmaciones verificadas — NO es ausencia):**
- **Malleable software / end-user programming** (Ink&Switch, malleable.systems, Geoffrey Litt/potluck):
  0 verificadas → vuelta dedicada. *Leads* descargados: `inkandswitch.com/essay/malleable-software`,
  `geoffreylitt.com/2023/03/25/llm-end-user-programming.html`.
- **Protocolos server-driven UI / agente↔UI** (shadcn registry-as-protocol, **AG-UI**, **MCP-UI /
  MCP-apps**, Google **A2UI**, Airbnb Epoxy, micro-frontends): 0 verificadas → **es la vía Python-native
  para render sin JS, el hueco real de Loombit**; merece su propia vuelta. *Leads*:
  `blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/`, `developers.googleblog.com` (A2UI),
  `docs.ag-ui.com`.
- **¿Crayon** (lib OSS sobre la que se construye C1) reutilizable standalone en local? Abierto.
- **¿Cómo se garantiza el gate cuando la UI es LLM-generada?** Ninguna fuente lo cubre → diseño nuestro (§11.3).

**REFUTADO (no usar):**
- "Las GenUI APIs están atadas a React/Next.js solo" → **refutado 1-2** (el data protocol sí sirve a no-JS).
- "El *data protocol* V5 no funciona con FastAPI" → **refutado 0-3** (sí funciona).
- "El ejemplo oficial FastAPI está roto/desactualizado" → **refutado 0-3**.
- "C1 es hosted-only sin opción local" → **refutado 1-2** (existe self-host enterprise "Scale").
- "tldraw AI usa un endpoint HTTP genérico → Python+Qwen podría servirlo directo" → **refutado 1-2**.

**Fuentes clave verificadas (V5):** `ai-sdk.dev/docs/ai-sdk-ui/stream-protocol` ·
`vercel.com/templates/ai/ai-sdk-python-streaming` · `github.com/vercel-labs/ai-sdk-preview-python-streaming` ·
`github.com/elementary-data/py-ai-datastream` · `ai-sdk.dev/docs/ai-sdk-rsc` · `thesys.dev/pricing` ·
`docs.thesys.dev/guides/what-is-thesys-c1` · `tldraw.dev/docs/ai` · `tldraw.dev/community/license` ·
`tldraw.dev/sdk-features/license-key`. (Run del harness: `wf_91899f87-01b`, 107 agentes, 2026-06-14.)
