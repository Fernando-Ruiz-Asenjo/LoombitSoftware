# Investigación 7 — EL TELAR: cómo Google/MS/Glean ponen contexto, y cómo Loombit lo hace MEJOR (local)

> Destilación de los **mecanismos reales** (no la superficie) de cómo los asistentes saben
> "quién es quién", construyen contexto y se adelantan — y la **reinterpretación creativa**
> para Loombit, aprovechando el foso local. **Agrupado para implementar cuando Fernando lo diga.**
> *2026-06-08.*

---

## A. CÓMO LO HACEN (mecanismo destilado)

Los tres grandes (Google Gemini/Workspace, Microsoft 365 Copilot, Glean) usan **la misma
receta de 3 piezas**:

1. **"Quién es quién" → grafo de conocimiento (knowledge graph).**
   Enlazan **personas ↔ contenido ↔ interacciones**. La identidad no se declara: se **infiere**
   de la frecuencia y el tipo de interacción (a quién escribes, sobre qué, con quién aparece en
   reuniones/hilos). Copilot lo monta sobre el **Microsoft Graph**; Gemini sobre el **Workspace
   Knowledge Graph**; Glean construye un **personal graph** (rol, proyectos, metas, preferencias)
   destilado de correos, docs, chats y búsquedas.

2. **"Poner contexto" → índice semántico + RAG.**
   Indexan TODO tu contenido como **vectores** (semantic index) y, al actuar, **recuperan en
   tiempo real** los trozos relevantes y los meten en la ventana de contexto (RAG). Heredan los
   **permisos** ("si tú puedes abrirlo, el modelo puede leerlo"). Clave honesta: **Gemini NO
   memoriza ni aprende tus preferencias de forma permanente** — recupera por sesión.

3. **"Adelantarse" → monitor continuo de eventos + acción.**
   Un daemon **ingiere de continuo** los flujos (correo, calendario, APIs), y un modelo decide
   **cuándo intervenir aporta valor**. Glean: "daily action bot" (qué tienes que hacer hoy) +
   "plan my day". Spark: corre 24/7 en la nube. El patrón: **vigilar → detectar señal → preparar
   → ofrecer**, no esperar a que preguntes.

**Herramientas similares y su truco:**
- **MS Copilot**: Graph + Semantic Index = el "quién es quién + contexto" mejor documentado.
- **Glean**: el grafo PERSONAL editable por el usuario (ve/edita/borra lo que el sistema cree de ti).
- **Superhuman Go**: integra 100+ apps, "sabe lo que tú sabes" y pule el tono.
- **Motion/Reclaim**: una sola tarea (calendario) perfecta — foco brutal.

---

## B. EL FALLO DE TODOS ELLOS (la grieta por donde entra Loombit)

- **Su telar se detiene en su jardín vallado.** El grafo de Google ve Workspace; el de Copilot ve
  M365. **Ninguno ve tus ficheros locales, tu escritorio, tu banca, la AEAT, tu WhatsApp.**
- **Tus datos salen a su nube** (Spark corre en Google Cloud). Privacidad = política, no física.
- **No te recuerdan de verdad** (Gemini no aprende preferencias permanentes). Resetean.
- **Genéricos y en inglés/US.** Cero profundidad administrativa española.

---

## C. EL TELAR DE LOOMBIT (la reinterpretación creativa, local y mejor)

**Loombit = telar.** Un telar teje hilos sueltos en UNA tela. La tesis: Loombit es **el único
telar que puede tejer TODOS tus hilos — porque vive en tu máquina**. No es un eslogan: es la
arquitectura. Las 3 piezas, en LOCAL y más allá:

1. **El grafo de relaciones LOCAL** (quién es quién, pero tuyo y en disco).
   Semilla ya construida: galaxia (contactos por frecuencia/temperatura) + `galaxia_intel`
   (destila el contexto real de cada contacto: importes con procedencia, asuntos, fechas) +
   memoria de entidad (IBAN, antifraude). **Leap:** un grafo personal que enlaza
   persona ↔ correos ↔ facturas ↔ pagos ↔ conversaciones ↔ ficheros locales ↔ trámites — y es
   **tuyo, nunca sale**. Google jamás tejerá tu carpeta local ni tu banca.

2. **El índice semántico LOCAL** (contexto en TODO, instantáneo y privado).
   Un índice de **embeddings on-device** sobre tu correo + ficheros → recuperación de contexto
   al instante, sin nube. **Leap UX:** "pasa por encima de cualquier nombre, factura o correo y
   el telar te muestra el hilo entero" (quién es, historia, dinero, qué hay pendiente). Contexto
   tejido, en todas partes, gratis y privado.

3. **El daemon que teje de continuo** (adelantarse, con calidez).
   El daemon (hoy APAGADO) se enciende y pasa de "vigilar respuestas" a **tejer la tela de la
   mañana**: lo importante de hoy + lo ya preparado. **Leap de producto:** no un panel frío que
   consultas, sino una presencia **cálida y desenfadada** que se asoma — "oye, esto… ya te lo dejé
   tejido". Personalidad de telar.

### Lo que SOLO Loombit puede (más allá de Google)
- **Aprende de ti de verdad** (Gemini no): memoria local + Fábrica de Skills que **teje skills
  nuevas de tus patrones repetidos**. Cada semana te queda mejor. Un asistente de nube resetea;
  un telar local recuerda.
- **Contexto que Google jamás verá**: escritorio (Pilot), banca, AEAT/VeriFactu, ficheros locales,
  WhatsApp.
- **Instantáneo y offline** (la nube tiene latencia; Spark es US-only).
- **Privacidad física**: "nada ha salido de tu máquina", en cada acción.

### La experiencia (telar: cálido, smooth, divertido, fricción CERO)
- **Anticipa → tú CONFIRMAS, casi nunca inicias.** Cero formularios, cero JSON.
- **La interacción ES el telar**: tiras de un hilo (arrastras en la galaxia, escribes una palabra)
  y se teje la acción.
- **Cálido y desenfadado**: voz amable, celebra los logros, animaciones suaves, instantáneo.

---

## D. BACKLOG AGRUPADO (para implementar cuando Fernando dé la señal)

> Todo es **mejorar lo que ya hay**, en orden de "se nota":
1. **Encender + enriquecer el daemon** → la tela de la mañana (proactividad real, scopes actuales).
2. **Grafo de relaciones local** (unir galaxia + galaxia_intel + memoria en un grafo persona-céntrico).
3. **Índice semántico local** (embeddings on-device) → contexto en todo, hover-para-ver-el-hilo.
4. **Lecturas Google ampliadas** (Drive/Docs/Sheets) cuando re-consientas → más hilos que tejer.
5. **Personalidad + UX telar** (voz cálida, smooth, cero fricción, celebra).
6. **Fábrica de Skills** que teje skills nuevas de tus patrones (el aprendizaje que la nube no da).

### Fuentes
- [Google Workspace Intelligence (knowledge graph)](https://workspace.google.com/blog/product-announcements/introducing-workspace-intelligence) · [Gemini personal intelligence](https://www.mindstudio.ai/blog/google-gemini-personal-intelligence-ai-search-your-data)
- [MS 365 Copilot — semantic index](https://learn.microsoft.com/en-us/microsoftsearch/semantic-index-for-copilot) · [Copilot + Graph](https://www.m365.fm/blog/how-copilot-uses-microsoft-graph-behind-the-scenes/)
- [Glean — proactive personal graph](https://thelettertwo.com/2026/02/17/glean-assistant-proactive-ai-coworker/) · [Superhuman Go](https://superhuman.com/products/go-ai-assistant)
