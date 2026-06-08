# Tendencias IA 2025-2026 — Inspiración estratégica para Loombit
**Investigación de vanguardia aplicada al producto. Qué existe, qué se puede adoptar, qué nos diferencia.**
*Generado: 2026-06-07*

---

## 1. El cambio fundamental: de reactivo a proactivo

La tendencia más importante de 2025-2026 no es técnica — es conceptual.

**Antes (2023-2024):** el usuario le dice al agente qué hacer. El agente responde.

**Ahora (2025-2026):** el agente detecta qué necesita el usuario antes de que lo pida y lo prepara. El usuario solo aprueba.

Esto tiene un nombre: **Proactive AI** o **Post-Prompting Era**. Los sistemas más avanzados (Copilot, Gemini, Claude) están migrando hacia aquí. Lo que diferenciará a Loombit no es que responda bien a lo que se le pide — eso ya lo hace ChatGPT. Lo que diferenciará a Loombit es que **anticipa**, **detecta**, **prepara** y solo interrumpe al humano cuando es necesario.

> "Un asistente proactivo resume hilos de correo antes de que los abras, sube documentos relevantes antes de una reunión, redacta agendas basándose en tu calendario — sin que nadie se lo haya pedido."

**Aplicación directa a Loombit:** el morning brief del día, la detección de facturas vencidas, el aviso de declaraciones próximas — todo eso es proactividad. Está en el plan. Hay que construirlo con convicción porque es exactamente hacia donde va el mercado.

---

## 2. Agentes multi-especialista (Multi-Agent Systems)

El estado del arte en 2026 no es un único agente que lo hace todo. Son **equipos de agentes especializados** que se coordinan:

- Un agente lee y clasifica el correo entrante.
- Otro extrae datos estructurados de facturas PDF.
- Otro consulta el estado de cobros.
- Otro redacta el recordatorio.
- Un orquestador coordina a todos y presenta el resultado al humano.

Cada agente es pequeño, enfocado y rápido. El orquestador tiene la visión completa.

**Por qué importa para Loombit:** el núcleo blanco de Loombit es exactamente esta arquitectura. Las skills son agentes especializados. El motor ReAct es el orquestador. Esto no es casualidad — es la arquitectura correcta. Hay que mantenerla y no colapsar todo en un único agente monolítico.

**Referencia técnica:** LangGraph (stateful orchestration), n8n 2.0 (70+ AI nodes con memoria persistente), LlamaIndex (document intelligence). Estos son los frameworks que están definiendo el estándar.

---

## 3. Memoria de agente — El diferencial real

El mayor problema de los asistentes de IA actuales es la **amnesia**. Cada conversación empieza desde cero. Loombit ya tiene `agent/memory.py`. Eso es ventaja competitiva real si se construye bien.

La investigación de 2025 ha convergido en **cuatro tipos de memoria** (inspirados en la psicología cognitiva):

| Tipo | Qué guarda | Ejemplo en Loombit |
|---|---|---|
| **Episódica** | Eventos pasados concretos | "El 15 de mayo enviamos un recordatorio a Construcciones Martínez" |
| **Semántica** | Conocimiento sobre el mundo del usuario | "Construcciones Martínez siempre paga tarde. Su contacto es Luis García." |
| **Procedural** | Cómo hacer las cosas | "Para los recordatorios de cobro, primero tono educado, luego formal, luego legal" |
| **Working** | El contexto de la tarea actual | "Estoy procesando la factura 2026/0042" |

**Lo más avanzado del campo:** Graphiti (Zep) — un grafo de conocimiento temporal que conecta episodios, entidades y relaciones a lo largo del tiempo. No es una lista de hechos: es un mapa de quién es quién, qué pasó, cuándo y cómo se relaciona todo.

**Aplicación concreta:** Loombit debe construir un perfil por empresa cliente/proveedor que aprende: patrones de pago, contactos, preferencias de comunicación, historial de incidencias. Esto convierte al agente en un verdadero colaborador que conoce el negocio, no en un chatbot genérico.

---

## 4. Inteligencia documental — La puerta de entrada al trabajo real

El administrativo trabaja con documentos: facturas, contratos, albaranes, nóminas, extractos bancarios. Un agente que no puede leer e interpretar documentos no puede hacer trabajo administrativo real.

**Estado del arte 2025-2026:**

El paradigma ha cambiado de OCR clásico (leer texto) a **Document Intelligence** (entender estructura y contexto):

```
OCR → Computer Vision (layout) → LLM (significado) → RAG (lógica de negocio) → Output estructurado
```

**Precisión alcanzada:** 95-99% en documentos complejos vs. 80% del OCR tradicional.

**Modelos/plataformas de referencia:**
- **LlamaParse** (LlamaIndex) — parser de documentos para agentes, muy bueno con PDFs complejos.
- **Google Document AI** — 60+ procesadores preentrenados para facturas, contratos, recibos.
- **Amazon Textract** — extracción de tablas y formularios.
- **Tesseract + Qwen-VL local** — opción 100% local y privada.

**Lo que Loombit necesita:**
1. Un módulo de ingesta de documentos: PDF → texto estructurado + campos extraídos.
2. Campos mínimos de una factura: número, fecha, proveedor, NIF, base imponible, IVA, total, vencimiento, IBAN.
3. Cruce automático: factura recibida vs. albarán registrado → detecta discrepancias.
4. Todo local, todo privado — los datos de clientes nunca salen de la máquina.

---

## 5. MCP — El estándar que lo cambia todo

**Model Context Protocol (MCP)** es el protocolo abierto que Anthropic publicó en noviembre 2024 y donó a la Linux Foundation en diciembre 2025. En junio 2026 es el estándar de facto para conectar agentes de IA con herramientas y datos externos.

**Por qué es importante:**
- OpenAI, Google, Microsoft, AWS, Hugging Face, LangChain — todos lo han adoptado.
- Más de 5.800 servidores MCP publicados en la comunidad.
- 97 millones de descargas mensuales del SDK.
- VS Code, Cursor, Claude Desktop, ChatGPT — todos hablan MCP.

**Lo que significa para Loombit:** cada conector que construyes (Gmail, Calendar, Drive, Holded, Sage, AEAT...) debería exponerse como un servidor MCP. Esto hace que Loombit sea interoperable con cualquier cliente MCP del mercado — no solo con su propia UI. Es una ventaja de distribución enorme.

**Roadmap MCP 2026:** Tasks API para operaciones asíncronas de larga duración (exactamente lo que necesita Loombit para tareas de fondo), autenticación enterprise (SSO, audit trails), y estandarización de agente a agente.

---

## 6. Computer Use y GUI Agents — El futuro de la integración sin API

Uno de los mayores problemas de automatización es que muchos sistemas no tienen API: ERPs viejos, portales web del gobierno, software legacy, la sede electrónica de Hacienda.

**Computer Use** es la solución: el agente ve la pantalla y opera con ratón y teclado, igual que un humano.

**Estado 2026:**
- **Anthropic Claude Computer Use** — portable, funciona en VMs, contenedores, escritorios remotos. El más maduro para uso general.
- **OpenAI CUA (Computer Using Agent)** — optimizado para web, lanzado en abril 2026.
- **Google Gemini/Mariner** — browser-native, DOM-aware.
- **Benchmarks** (OSWorld, WebArena, OdysseyBench) — evalúan capacidad de completar tareas reales en office apps.

**Aplicación a Loombit:** Skill W Pilot ya está construido. Es una ventaja competitiva real. Lo que lo hace especial frente a Zapier o n8n: puede operar sistemas que no tienen API — el portal de la Seguridad Social, la sede de Hacienda, ERPs legacy. Eso es irreemplazable para PYME española.

---

## 7. Voz — La interfaz natural del trabajador

El administrativo está constantemente haciendo cosas: tecleando, al teléfono, atendiendo al público. Escribir al agente es fricción. Hablarle es natural.

**Estado 2025-2026:**
- **OpenAI GPT-Realtime-Whisper** — streaming, ultra baja latencia, transcripción en tiempo real mientras se habla.
- **Deepgram Nova-3** — construido para agentes de voz en tiempo real.
- **Fireflies.ai** — graba reuniones, extrae action items, los integra con CRM/proyectos.
- **AssemblyAI** — diarización (quién habló), capítulos, resúmenes, items de acción.

**Lo que se puede hacer con voz en Loombit:**
- "Loombit, acaba de llamar el proveedor Suministros Norte diciendo que nos manda una factura rectificativa por 240 euros menos." → Loombit lo registra, lo vincula a la factura en disputa, crea el seguimiento.
- Dictar una nota de reunión → Loombit extrae tareas, asignaciones, fechas y las pone en el calendario.
- Transcribir una llamada con un cliente → detectar compromisos → crear recordatorio.

**Tecnología:** Whisper (OpenAI, open source) corre local. Es privado. Es el punto de entrada más natural para un working class que no quiere escribir prompts.

---

## 8. Modelos pequeños locales — La apuesta correcta para privacidad y coste

**El panorama de SLMs (Small Language Models) en 2026:**

Los mejores modelos para edge/local (7B-9B parámetros, caben en 8-16GB VRAM):

| Modelo | Fortaleza | Relevante para Loombit |
|---|---|---|
| **Qwen2.5-7B-Instruct-1M** | 1M tokens contexto, razonamiento general | ✅ Ya en uso como instructor |
| **Qwen2.5-Coder-7B** | Código, estructuras, JSON | ✅ Ya en uso como coder |
| **Qwen2.5-VL-7B** | Visión — lee imágenes, PDFs escaneados | 🔥 Añadir para document intelligence |
| **Mistral 7B Instruct** | Muy rápido, buena instrucción | Alternativa al instructor |
| **Phi-3 Mini (3.8B)** | Pequeñísimo, cabe en móvil | Para futuro Jetson edge |
| **Llama 3.2 (1B/3B)** | Ultra ligero para edge extremo | Jetson Orin NX |

**La tendencia clave:** producción usa modelos locales para el 60-80% de las consultas, reservando la nube para las más complejas. Loombit ya está en este camino — es la arquitectura correcta.

**Qwen2.5-VL** (visión) es la adición más urgente: con él, Loombit puede leer facturas PDF escaneadas, contratos en imagen, extractos bancarios — sin OCR externo, sin nube, sin coste por llamada.

---

## 9. Automatización de workflows — Lo que hacen los líderes del mercado

**n8n 2.0 (enero 2026):** integración nativa con LangChain, 70+ AI nodes, memoria persistente entre ejecuciones, soporte para LLMs locales, human-in-the-loop. Es el más poderoso para equipos técnicos.

**Zapier Agents (fuera de beta 2025):** 8.000+ apps, agentes que planean sus propios pasos en vez de seguir triggers rígidos.

**Make/Maia:** construye automatizaciones desde lenguaje natural.

**Lo que Loombit tiene que ellos no tienen:**
1. **Privacidad total** — n8n puede ser self-hosted, pero sus agentes siguen llamando a APIs externas con datos del usuario. Loombit procesa todo local.
2. **Conocimiento del dominio administrativo español** — ninguno de estos tools entiende el modelo 303, el Sistema RED, la Ley 3/2004 de morosidad, o VeriFactu.
3. **Skill Pilot** — puede operar sistemas sin API. Zapier y n8n no pueden.
4. **Memoria de empresa** — aprende los patrones del negocio específico del usuario, no es genérico.

---

## 10. Lo que viene — Capacidades emergentes para el roadmap futuro

### Agentes que se auto-mejoran
Los sistemas más avanzados están empezando a detectar sus propios puntos de fallo y proponer mejoras. En Loombit: el agente podría detectar que siempre falla en extraer facturas de un proveedor concreto y crear un ticket para mejorar el extractor.

### Razonamiento extendido (Extended Thinking)
Claude 3.7 Sonnet, DeepSeek R1, QwQ — modelos que "piensan en voz alta" antes de responder, con cadenas de razonamiento de miles de tokens. Para casos complejos (¿esta operación tiene implicaciones fiscales?) esto es transformador. Ya es accesible por API.

### Agents-as-APIs / A2A (Agent to Agent)
Google lanzó el protocolo A2A en 2025: agentes que se llaman entre sí directamente, sin humano de por medio, con contratos de interfaz definidos. El supervisor de Loombit podría delegar en un agente especialista de IVA, que a su vez consulta a un agente de normativa tributaria.

### Memoria temporal y grafos de conocimiento
**Graphiti/Zep**: grafos de conocimiento que mantienen relaciones temporales. No solo sabe que "Pérez es cliente" sino que "Pérez era cliente desde 2019, dejó de serlo en 2022, volvió en 2024 con condiciones distintas". Esto es la diferencia entre un CRM y un asistente que realmente conoce el negocio.

### Facturación electrónica estructurada (VeriFactu)
Con VeriFactu obligatorio a partir de 2027, cada factura en España será un documento XML firmado digitalmente con código QR. Un agente que genere, firme, envíe y archive facturas cumpliendo VeriFactu automáticamente es una propuesta de valor enorme para PYME española — y ningún chatbot genérico lo hace.

### OCR con modelos de visión local
Qwen2.5-VL y LLaVA permiten leer PDFs escaneados, fotos de tickets y contratos directamente desde imagen, sin OCR de terceros, sin coste de API, sin privacidad comprometida. Para una PYME que trabaja con documentos físicos escaneados (que es la mayoría), esto es fundamental.

---

## 11. Mapa de adopción para Loombit — Qué adoptar y cuándo

### Ahora (Fase 1-2)
- ✅ **Proactividad** — morning brief, vencimientos, alertas sin que nadie las pida (ya en el plan)
- ✅ **MCP** — exponer conectores como servidores MCP para interoperabilidad
- ✅ **Memoria en grafo** — evolucionar `memory.py` hacia perfiles por empresa/cliente/proveedor
- ✅ **Document Intelligence** — módulo de ingesta de facturas PDF con Qwen2.5-VL local

### Fase 3-4
- 🔜 **Voz** — entrada por Whisper local; dictar notas, registrar llamadas
- 🔜 **Multi-agente explícito** — separar el agente clasificador del extractor del redactor
- 🔜 **VeriFactu** — generación de facturas electrónicas cumpliendo el nuevo estándar

### Fase 5-6 (futuro)
- 🔮 **Razonamiento extendido** — activar extended thinking en casos de alta complejidad fiscal/legal
- 🔮 **A2A** — agentes especializados que se llaman entre sí
- 🔮 **Auto-mejora** — el agente detecta sus fallos y propone mejoras al desarrollador

---

## 12. La diferenciación real de Loombit en 2026

El mercado está lleno de asistentes de IA genéricos. Lo que Loombit puede hacer que nadie más hace:

**1. Privacidad estructural, no política.** Los datos nunca salen de la máquina del usuario. No hay promesa de privacidad — hay imposibilidad técnica de fuga. Para un autónomo español con datos de clientes, esto es un argumento de venta real.

**2. Conocimiento del marco legal y fiscal español.** Entiende el modelo 303, la Ley 3/2004, la fecha límite del sistema RED, qué es VeriFactu. GPT-4 también lo sabe, pero no está integrado en el flujo de trabajo — Loombit sí.

**3. Skill Pilot — opera lo que no tiene API.** La sede de Hacienda, el portal de la Seguridad Social, el ERP legacy que usa el cliente de toda la vida. Ningún Zapier ni n8n puede hacer esto.

**4. Memoria de empresa que crece.** Aprende que Construcciones Martínez paga tarde, que el proveedor X siempre manda facturas mal puestas, que el gerente prefiere los resúmenes cortos. Se convierte en un colaborador que conoce el negocio.

**5. El bucle completo, sin salir de Loombit.** Lee → entiende → planea → prepara → pregunta → ejecuta → archiva → aprende. Sin cambiar de herramienta. Eso es fricción cero.

---

*Fuentes: Google Cloud AI Agent Trends 2026, Anthropic MCP documentation, LlamaIndex Document AI, arXiv research papers (LEGOMem, Graphiti, ContextAgent), Gartner 2025 AI predictions, McKinsey 2025 AI survey, TodoFP Ministerio de Educación.*
