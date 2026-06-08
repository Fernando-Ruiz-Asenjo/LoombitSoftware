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
