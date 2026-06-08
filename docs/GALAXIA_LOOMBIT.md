# La Galaxia de Loombit — el negocio del usuario como un sistema estelar vivo

> Diseño aterrizado de la idea de Fernando: una ventana dentro de Loombit donde el negocio del
> usuario (o el usuario) se ve como un **sistema estelar** — un sol en el centro y "planetas"
> (contactos/destinatarios, facturas, documentos, cuentas) en sus **órbitas**, todo muy visible,
> ordenado, e **interactuable entre sí**. *Generado 2026-06-08. Encaja en Fase 4 (UI humana).*

## 1. Por qué es la pieza correcta

Gmail/Google te dan **listas planas** (bandeja, una tabla de eventos, una carpeta de Drive). No te
muestran las **relaciones**: que esta factura es de este cliente, que ese cliente te debe 1.250 €
y lleva 9 días sin contestar al correo que le mandaste. La Galaxia **es justo eso que Google no
tiene**: el mapa relacional y vivo de tu negocio, en una sola pantalla, donde actuar.

No sustituye al chat (el operador): es su **mapa**. El chat ejecuta; la Galaxia muestra el estado
del mundo y deja **actuar tocando**.

## 2. El modelo (sol · órbitas · planetas · lunas · aristas)

- **Sol (centro) = la entidad**: la empresa del usuario (o el usuario). Muestra su nombre y unos
  pocos KPIs vivos: total a cobrar, nº vencidas, correos sin contestar, aprobaciones pendientes.
- **Órbitas = categorías**, de dentro (urgente/cercano) a fuera (frío):
  - **Contactos/destinatarios** — planetas = personas/empresas con las que tratas. **Tamaño** =
    frecuencia real (a quien más escribes, mayor — reusa el ranking de Enviados). **Color** = estado
    de la relación (te debe / te respondió / silencio).
  - **Facturas / cuentas a cobrar** — planetas = importes. **Color semáforo**: vencida 🔴, próxima 🟠,
    cobrada 🟢. **Tamaño** = importe.
  - **Documentos** — planetas = PDFs/ficheros (facturas escaneadas, contratos).
  - **Eventos/tareas** — planetas = citas y pendientes.
- **Lunas (satélites)**: un planeta-contacto tiene de lunas SUS facturas, correos y documentos. Así
  la relación se ve como jerarquía orbital (el cliente y, girando a su alrededor, lo que le debes/te debe).
- **Aristas (líneas)** = relaciones explícitas: factura ↔ cliente ↔ hilo de correo. Al señalar un
  planeta se ilumina toda su **constelación**.

## 3. Mis mejoras a la idea (esto la convierte en algo que Google no puede copiar)

1. **Gravedad semántica** — lo urgente/reciente es **atraído hacia el centro**. Una factura vencida o
   un contacto esperando respuesta migran a la **órbita interior**: "lo que necesita atención AHORA"
   es, literalmente, lo más cercano a ti. El radio orbital codifica prioridad, no decoración.
2. **El tiempo como órbita** — las facturas orbitan más rápido / más cerca cuanto más cerca está su
   vencimiento. Un vistazo = sabes qué se cae esta semana.
3. **Drag-to-act (no es un dashboard, es un escritorio)** — arrastrar un planeta sobre otro **dispara
   una acción** del operador, con su aprobación:
   - factura → contacto = *reclamar cobro* (usa `dunning_plan`).
   - documento → contacto = *enviar documento*.
   - contacto → órbita Eventos = *agendar una cita*.
   - correo → factura = *vincular* (este pago es de esta factura → concilia).
4. **Vivo con el daemon** — los planetas **laten/brillan** cuando hay novedad: un contacto que acaba
   de responder pulsa en cian; una vencida pulsa en rojo. La Galaxia y el panel "Novedades" son **dos
   vistas del mismo cerebro proactivo**.
5. **Zoom por niveles** — *galaxia* (todo el negocio) → *sistema* (el mundo de UN cliente: sus
   facturas, correos, eventos) → *planeta* (el detalle de UNA factura, con su hilo y su recibo).
6. **Identidad de marca** — sol y órbitas en violeta→cian (como el halo del Pilot); estados en
   semáforo. Coherente con lo ya construido.

## 4. Interacciones

- **Hover** planeta → tooltip con lo clave (importe, vencimiento, último contacto).
- **Clic** → *focus*: el planeta pasa a ser sol temporal y su constelación orbita a su alrededor.
- **Doble clic** → abre el detalle en el chat (leer entero / actuar), reusando lo ya hecho.
- **Arrastrar** un planeta sobre otro → acción (con tarjeta de aprobación; nada se envía sin tu OK).
- **Buscar** → el planeta se ilumina y se trae a primer plano.

## 5. De dónde sale cada planeta (casi todo ya existe)

| Planeta | Fuente (ya en el repo) |
|---|---|
| Contactos (tamaño=frecuencia) | `routers/home.py::_contactos_de_gmail` (Enviados) + memoria |
| Facturas / cuentas a cobrar (color=estado) | `cuentas_cobrar.py` (`/cuentas`) |
| Documentos | `docs_intel` / carpeta de facturas |
| Eventos | Google Calendar (pendiente vista de lectura) |
| Novedades (brillo) | `/routines/feed` (daemon) |

→ El MVP no necesita inventar datos: agrega lo que ya tenemos en un **grafo (nodos + aristas)**.

## 6. MVP (slice 1, verificable — DoD 🟢)

1. **Endpoint `GET /galaxia`** que agrega: sol (entidad + KPIs), planetas-contacto (de Enviados,
   con `peso`=frecuencia), planetas-cuenta (de `/cuentas`, con `estado`), y **aristas**
   contacto↔cuenta (por `cliente`). Devuelve `{ sol, nodos[], aristas[] }`. Con su test.
2. **Vista** en la UI (canvas/SVG, layout orbital o force-directed, sin dependencia pesada o con D3):
   sol en el centro, contactos en una órbita (tamaño=peso), cuentas en otra (color=estado), líneas
   contacto↔cuenta. Hover = tooltip. Clic = focus.
3. **Verificación 🟢**: con datos reales (tus contactos + una factura emitida) la Galaxia pinta el
   cliente y su factura vencida unidos por una arista; refresca solo.

*Slices siguientes:* drag-to-act (reclamar/enviar/agendar), latido por novedad, zoom por niveles,
órbita de documentos y eventos.

## 7. Encaje en la roadmap

Esto es el corazón de **Fase 4 (UI humana / dashboard)** y, a la vez, el diferenciador de producto.
No bloquea Fase 3 (cobros e2e); se puede construir en paralelo a la lógica de cobros porque consume
sus datos. Recomendado: MVP de la Galaxia tras (o junto a) el primer slice de Fase 3.

## 8. El resto de gaps de Google, aterrizados (de la comparativa)

Priorizados por "cuánto te obliga a salir de Loombit":

1. **Bandeja de correo en Loombit** (alta) — panel que lista correo reciente (Gmail API: leer),
   abre el hilo entero y deja actuar (el agente redacta/responde). MVP: lista no-leídos/recientes →
   abrir hilo → responder. *Encaja con la órbita "correos" de la Galaxia.*
2. **Vista de Calendar** (media) — leer y mostrar la agenda (ya creamos eventos; falta leer/ver/mover).
   MVP: agenda de la semana + crear desde la UI. *Encaja con la órbita "eventos".*
3. **Ficheros / Drive** (media-baja) — listar y previsualizar documentos (Drive API). *Órbita "documentos".*
4. Secundarios (etiquetas, snooze, temas, multicuenta, offline): no son de operador; aparcados.

**Idea clave:** los tres gaps (correo, calendario, ficheros) no son pantallas sueltas — son **las
órbitas de la Galaxia**. Construir la Galaxia y construir esas vistas es **el mismo trabajo** visto
de dos maneras: cada gap es una órbita más de planetas con los que interactuar.

---

# Profundización con investigación (2026-06-08)

> Antes de construir, se investigaron enfoques reales (librerías de grafos, CRMs relacionales,
> lienzos espaciales, técnicas de visualización). Esto **destila** lo aplicable y **corrige** la idea.

## 9. Qué existe ahí fuera (y qué tomamos / evitamos)

- **CRMs relacionales** (Dex, Clay, Monica, YourPond): el patrón que funciona no es "una galaxia"
  sino **fuerza de la relación** (Dex muestra qué conexiones *crecen o se enfrían*), **enriquecido
  proactivamente** desde correo/calendario (Clay construye y actualiza tu red solo) y, en el caso de
  **Monica, local/auto-alojado** (= nuestra privacidad). → **Tomamos**: temperatura de relación +
  auto-construcción desde Enviados (ya lo hacemos) + local-first como diferencial.
- **Lienzos espaciales / PKM** (Heptabase, Kosmik, Scrintal, Obsidian Canvas/graph): organizar como
  "papeles en una mesa", lo espacial le va a quien piensa en relaciones; lo lista a quien tría. →
  **Lección**: la Galaxia es la **vista de conjunto y relación**, NO el sitio para triar/buscar fino.
- **Clientes de correo IA** (Shortwave, Superhuman): Shortwave = panel multi-vista (Calendar,
  *Activity* de quién abrió/respondió, *todo el correo de un contacto*) + *Tasklet* (automatiza flujos
  en lenguaje natural); Superhuman = **command palette** (⌘K hace cualquier cosa sin ratón) + velocidad.
  El mercado se parte en "organizar el trabajo" vs "ejecutarlo más rápido". → **Loombit es la tercera
  posición, más fuerte: lo HACE por ti y te enseña el mapa vivo de tu negocio.** Tomamos: command
  palette (precisión) + "todo de un contacto" = las **lunas** de su planeta.
- **Librerías de grafos** (D3-force, Cytoscape.js, Sigma/graphology): Cytoscape = mejor equilibrio
  interactividad/algoritmos (canvas, ~3-5k nodos); Sigma/WebGL para decenas de miles; D3 = control
  total pero mucho trabajo. → Para una PYME (decenas–cientos de entidades) **no necesitamos un motor
  de grafos**; ver §11.

## 10. La corrección crítica: huir del "hairball"

El hallazgo más importante de la investigación: un grafo nodo-arista con todo conectado se convierte
en una **maraña ("hairball") inusable a partir de ~30 nodos**. Si pintáramos contactos+facturas+
correos+documentos+eventos con todas sus líneas a la vez, sería ruido. Cómo lo evita la Galaxia
**por construcción** (no por parche):

1. **Órbitas = sin aristas por defecto.** El layout radial codifica la relación por **posición**
   (órbita = categoría, radio = prioridad/urgencia, ángulo/cercanía = agrupación), no por líneas.
   La investigación de *radial layouts* lo confirma: "las aristas consumen mucho espacio; el radial es
   *edgeless*". **Las líneas solo aparecen al hacer foco/hover en UN planeta** (su constelación), nunca
   todas a la vez. Esto, solo, mata la maraña.
2. **Focus + Context con zoom semántico** (técnica académica establecida; p. ej. *MoireGraphs*: focus+
   context radial con nodos visuales). Tres niveles donde **cambia la codificación, no solo la escala**:
   - **Galaxia** (conjunto): sol + KPIs + los ~12-15 planetas que importan + **cinturones** para el resto.
   - **Sistema** (foco en una entidad): esa entidad pasa al centro y sus **lunas radian a su alrededor**
     (layout radial *parent-centered*): sus facturas, sus correos, sus eventos.
   - **Planeta** (detalle): se abre en el chat para leer entero / actuar (reusa lo ya hecho).
3. **Cinturón de asteroides para la cola larga.** Los contactos fríos / facturas viejas no se pintan
   como planetas: se agrupan en un **cinturón** (un anillo de "polvo") expandible. Es la técnica
   anti-hairball de *agrupar en nodos de nivel superior*, pero coherente con la metáfora.
4. **Temperatura de relación** (de Dex): un planeta **brilla y se acerca** al interactuar, y **se
   enfría/atenúa** si llevas semanas sin trato → empuja a la acción ("hace 3 meses que no hablas con X").
5. **Gravedad semántica** (idea original, ahora validada): lo urgente es atraído al centro.
6. **Command palette** (de Superhuman): ⌘K para **saltar a cualquier planeta o disparar una acción**
   ("reclamar a Jana", "agenda con David"). Lo espacial da la visión; la paleta da la precisión y la
   velocidad — cubre justo donde "las listas ganan al grafo".

## 11. Decisión técnica

- **Render: canvas propio con layout orbital DETERMINISTA** (no físico). Motivos: (a) la metáfora
  "sistema estelar" es bespoke y queremos control total del aspecto (marca violeta→cian, el halo);
  (b) un layout determinista por órbitas **no produce maraña** (no hay física que enrede); (c) cero
  dependencia pesada, local-first, encaja en la single-page actual. Aristas solo en foco.
- **Cuándo subir a una librería**: si algún día necesitamos algoritmos de grafo (caminos, comunidades)
  o miles de nodos, **Cytoscape.js** (interactividad+algoritmos) o **Sigma+graphology** (WebGL, escala).
  Para una PYME no hace falta; se deja documentado como salida.
- **Datos**: un único `GET /galaxia` agrega lo que ya existe (§5) en `{ sol, nodos[], aristas[] }`,
  con `peso`, `estado`, `temperatura` y `urgencia` por nodo → el canvas coloca por órbita/radio.

## 12. MVP revisado (anti-hairball desde el día 1)

1. `GET /galaxia`: sol (entidad + KPIs) · nodos contacto (peso=frecuencia, temperatura=recencia) ·
   nodos cuenta (estado, urgencia=días a vencer) · **aristas solo contacto↔cuenta** (no se pintan
   salvo foco). + test.
2. Canvas orbital determinista: sol al centro, órbita de contactos (tamaño=peso, brillo=temperatura),
   órbita de cuentas (color=estado, radio=urgencia → las que vencen, más adentro), **cinturón** para
   la cola. **Hover** = tooltip; **clic** = foco (parent-centered, aparecen sus líneas); **⌘K** = saltar.
3. 🟢 cuando, con datos reales, la vista coloca tus contactos y sus facturas vencidas hacia el centro,
   sin maraña, y al hacer foco en un cliente aparecen solo SUS líneas.

*Siguientes slices*: drag-to-act, latido por novedad (daemon), órbitas de correo/eventos/documentos
(= los 3 gaps de Google), zoom semántico completo.

## Fuentes
- [JS graph libs (Cytoscape/Sigma/D3) — comparación](https://www.cylynx.io/blog/a-comparison-of-javascript-graph-network-visualisation-libraries/) · [Cytoscape.js](https://js.cytoscape.org/)
- [Personal CRMs (Dex/Clay/Monica/YourPond)](https://getdex.com/guides/finding-the-right-personal-crm/)
- [PKM espacial (Kosmik/Heptabase/Obsidian)](https://www.kosmik.app/blog/best-pkm-apps)
- [El problema del "hairball" y cómo arreglarlo](https://cambridge-intelligence.com/how-to-fix-hairballs/) · [Por qué el grafo no siempre es ideal (DISSINET)](https://dissinet.cz/news/articles/why-is-the-graph-visualisation-not-always-an-ideal-way-to-display-network-data)
- [Focus+Context / zoom semántico](https://www.researchgate.net/publication/221006041_MoireGraphs_Radial_FocusContext_Visualization_and_Interaction_for_Graphs_with_Visual_Nodes)
- [Shortwave vs Superhuman (email IA, command center)](https://zapier.com/blog/shortwave-vs-superhuman/)
