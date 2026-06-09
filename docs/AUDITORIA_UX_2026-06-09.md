# AUDITORÍA UX PROFUNDA — por qué hoy NO es TOP y cómo lo será

> Encargo de Fernando (2026-06-09): *«quiero una auditoría y un análisis profundo para cambiar la
> experiencia de usuario; esta debe ser TOP, y ahora no lo es».* Esto es el diagnóstico, con
> **evidencia viva** (no de memoria) y un plan priorizado. Acompaña a `EXPERIENCIA_LOOMBIT.md` (la
> visión + slices S0-S7): aquel es el plano; **este es el estado real medido contra el plano**.

## 0 · Método (cómo se auditó — esto importa)

- **En vivo, en el Chrome real de Fernando** (extensión), contra el Loombit en `:8787` **con Google
  conectado de verdad** (token válido en disco). El navegador interno de Claude **no vale**: no tiene
  la red ni la sesión de Google, así que lo que pinta sale de la caché de comprensión en disco, no de
  una llamada viva. (Corrección de método de Fernando, aplicada.)
- **Tres superficies auditadas:** (1) la home actual `/` = monolito `static/index.html` (2.625 líneas);
  (2) la nueva Tela `/static/loombit.html` (239 líneas); (3) la Galaxia (vista «Mapa» de la nueva Tela).
- **Datos reales** en pantalla: el telar tejió 8 hilos derivados del Gmail real (David Valentín,
  Proyecto Generali, indexación Search Console, impuestos 2T…). No hay placeholders.

## 1 · Veredicto en una frase

**El cerebro es de primera y los datos son reales, pero la piel está partida en dos productos a medio
hacer** — una home antigua y potente pero ruidosa, y una Tela nueva preciosa pero coja —, y **ninguna
de las dos cumple aún, entera, las 10 leyes que el propio equipo se fijó**. No es un problema de gusto:
es de *coherencia, foco y remate*. La buena noticia: el 80 % del salto a TOP es **integración y pulido
de lo que ya existe**, no construir de cero.

## 2 · Lo que YA está bien (honestidad: no todo es malo)

- **Te recibe con trabajo hecho, no con un cursor vacío** (cuando carga): el telar real es el activo
  diferencial y funciona. Es la mejor decisión de producto que hay aquí.
- **La confianza está presente:** «🔒 nada ha salido de tu máquina» visible en ambas superficies.
- **Semáforo** como lenguaje de color (bordes de hilo) — buena base transversal.
- **La nueva Tela** tiene la dirección correcta: revelación progresiva L0→L2, tarjeta canónica con
  procedencia, y la conmutación **Hoy↔Mapa** (Galaxia orbital anti-hairball, con sol «Tu negocio
  3.890 €» y nodos por semáforo). El sistema de diseño violeta→cian es agradable y propio.
- **Consola de Loombit limpia** (los warnings vistos eran todos de MetaMask, no nuestros).

## 3 · Hallazgos por severidad (con evidencia + ley violada + arreglo)

### 🔴 P0 — rompen la sensación TOP hoy mismo

| # | Hallazgo (evidencia viva) | Ley rota | Arreglo |
|---|---|---|---|
| P0-1 | **Dos productos divergentes.** La home `/` (2.625 líneas, potente: chat, sidebar, conexiones, fábrica, entregables) y la Tela nueva (239 líneas, bonita pero sin chat/sidebar/acciones reales) **conviven sin paridad**. El usuario no sabe cuál es Loombit. | §2 «un solo lienzo» | Converger en UNA. La Tela nueva es el destino estético; debe **absorber** la potencia de la home antes de promoverse a `/`. |
| P0-2 | **Doble saludo apilado en la home.** Tras cargar, se ve el telar «Buenos días, Fernando» **y debajo** el intro de chat vacío «Hola, Fernando · Soy Oficina Loombit» con 4 tarjetas demo. Dos bienvenidas que se pisan. | §1, §9.1 (mata el cursor vacío) | El intro de chat vacío es un anti-patrón; el chat debe ser copiloto omnipresente (cajón), no una segunda home. Quitar el intro cuando hay telar. |
| P0-3 | **5-6 s de pantalla en blanco al arrancar.** En frío, ambas superficies muestran solo el saludo y **el telar entra varios segundos después**; el primer pintado se siente vacío. | §1 «te recibe con lo ya hecho» | Estado **«tejiendo…»** (skeleton del telar, ya está la metáfora) + servir el telar cacheado al instante y refrescar en 2º plano. |
| P0-4 | **La aprobación flota desconectada.** El aviso «1 acción pendiente de aprobar · Enviar un correo a david.valentin@…» aparece arriba-derecha, **lejos del hilo** al que pertenece. | §2, §5.2 (aprobaciones inline) | Aprobación **inline en su hilo**, con la tarjeta canónica (porqué+procedencia+🔒+semáforo+1 toque). |
| P0-5 | **La cognición no llega a la tarjeta.** `/telar` no trae campo `porqué` (solo `detalle`), así que la tarjeta L2 **repite el detalle** como «Porqué». Suena tonto, no inteligente. | §7.2 «el porqué en 1 línea» | Que `/telar` derive un **porqué real** (causa+dato) por hilo + procedencia tipada + importe/IBAN en cobros. |

### 🟠 P1 — frenan el «se nota inteligente / cómodo»

| # | Hallazgo | Ley | Arreglo |
|---|---|---|---|
| P1-1 | **Espacio desperdiciado.** A 1278 px el contenido vive en una columna estrecha centrada con enormes márgenes vacíos. Se siente a medio vestir. | §11 listón | Layout que respire pero use el ancho: telar + copiloto/contexto a la derecha, o columnas. |
| P1-2 | **Polling a martillazos.** Aprobaciones cada **3 s**, feed 10 s, cuentas 15 s, galaxia 30 s — para siempre (decenas de `/agent/runs` en la red). | §9 fiabilidad/coste | Backoff + pausar en pestaña oculta + idealmente SSE/eventos del daemon (la barra «🔔 laten por evento» del plano). |
| P1-3 | **Acciones sin recibo visible en la nueva Tela.** Los botones (Ver/Gestionar) no cierran el lazo con micro-celebración + recibo + «+min ahorrados» como promete §4.3/§5.2. | §8, §4.3 | Cablear el cierre de acción a recibo + contador. |
| P1-4 | **Hover (L1) sin explotar.** El plano hace del hover el superpoder («hover = el hilo entero»); hoy L1 apenas existe — se va directo de L0 a L2 por clic. | §3, §4.4 | Implementar L1 en hover (contexto sin clic). |
| P1-5 | **Tiempo ahorrado estático.** «14 min» y «🔔 1 nuevo» se ven fijos; no se sabe si son reales o de muestra. | §8, §1 útil 100% | Conectar a datos reales (libro de minutos) y que **suba** al cerrar acciones. |

### 🟡 P2 — pulido que separa «bien» de «delicioso»

- Microcopy aún con restos fríos/genéricos en la home («Soy Oficina Loombit. Controlo el escritorio…»)
  vs la voz cálida del plano §6.
- Sin estados de foco/teclado evidentes ni ⌘K (paleta) todavía (§5.1).
- Motion: la animación `tejer` es bonita pero su *timing* deja ver el vacío (ligar a P0-3).
- Densidad tipográfica: el `detalle` bajo cada título es pequeño y de bajo contraste.
- Responsive/móvil sin verificar (la operativa real del autónomo es muchas veces el teléfono).

## 4 · Benchmark contra el estado del arte (patrones, no copia)

| Producto | Qué hacen TOP | Qué robamos para Loombit |
|---|---|---|
| **Superhuman / Linear** | velocidad percibida, teclado primero, ⌘K, *optimistic UI* (la acción se ve hecha al instante). | ⌘K ya decidido; **optimistic UI** en aprobar/enviar (recibo inmediato, reconcilia detrás). |
| **Arc / Raycast** | un lienzo, no pestañas; comando como ciudadano de primera; transiciones espaciales. | la tesis Tela↔Galaxia↔Hilo por zoom; copiloto omnipresente. |
| **Things / Stripe Dashboard** | jerarquía visual impecable, *empty states* que enseñan, números con significado. | tarjeta canónica con porqué+importe; matar el «empty state» con el telar. |
| **Notion AI / Copilots** | el asistente *vive donde trabajas*, no en otra pestaña. | el chat como cajón inline, su salida cae como hilo. |
| **Apple HIG / Vercel** | *reduced-motion*, skeletons, foco, contraste AA. | skeleton de carga (P0-3), accesibilidad como base. |

**Diferencial que ninguno tiene y debemos gritar:** *cognición local del hilo* (hover = todo el
contexto que Google no te da) + *foso de privacidad* (🔒 nada sale) + *español administrativo profundo*.
Eso es lo que convierte «otro dashboard bonito» en **indispensable**.

## 5 · El plan — cómo esto reordena el roadmap S0-S7

El plano `EXPERIENCIA_LOOMBIT.md` ya tiene los slices correctos; la auditoría los **prioriza por dolor
real medido** y añade los arreglos P0 como puerta previa:

1. **Ola 1 (P0 — la convergencia):** matar el doble saludo (P0-2) · skeleton «tejiendo» + telar cacheado
   instantáneo (P0-3) · aprobación inline con tarjeta canónica (P0-4) · `porqué` real en `/telar` (P0-5).
   → *Resultado:* la home deja de sentirse partida y vacía. Es el 80 % de la sensación.
2. **Ola 2 (paridad → promover):** S4 chat copiloto omnipresente + sidebar/settings/Google en la Tela
   nueva → **paridad verificada EN VIVO** → promover `/static/loombit.html` a `/` (P0-1). Cablear la
   Galaxia a `/galaxia`. Trocear el monolito en componentes (Tela/Galaxia/Chat/Tarjeta/BarraViva).
3. **Ola 3 (inteligencia sentida):** hover L1 (P1-4) · optimistic UI + recibo + contador real (P1-3,
   P1-5) · polling→eventos (P1-2) · layout que usa el ancho (P1-1).
4. **Ola 4 (delicioso):** voz/microcopy §6 · ⌘K · motion fino · accesibilidad · responsive (P2).

**Regla de oro (BRÚJULA):** cada ola en rama, **verificada EN VIVO en el Chrome real con Google**,
tests/black/ruff verdes, y **0 regresión de features** antes de promover nada a `/`.

## 5bis · RONDA 2 — pruebas DURAS en vivo (ejercitando acciones reales, no render)

> Encargo de Fernando: *«quiero pruebas más duras… hazte preguntas sobre facilidad, usabilidad, si
> tiene sentido la acción, lo que devuelve… mi experiencia es mala».* Probado en su Chrome real con
> Google conectado, contra el server vivo (proceso independiente, no preview). Verificado por RECIBO,
> no por la narración del LLM.

**Arreglado y verificado (esta ronda):**
- **F-1 · jerga de tools en la respuesta.** El 14B contestó «…usando `calendar_search`» (¡tool
  alucinada!). → Saneador por código `tool_labels.humanize_user_text` en `run.mark_completed`. ✅
- **F-2 · volcado de CÓDIGO como respuesta.** A «¿qué reuniones tengo esta semana?» devolvió
  `for day in …: print(…)`. → `looks_like_code`/`safe_user_result`: basura → mensaje honesto con
  salida. Reverificado en vivo: ahora responde en cristiano. ✅
- **F-3 · aprobación a ciegas.** La tarjeta solo decía «Enviar un correo a X», sin el borrador. →
  ahora muestra el `proposed_action` completo (qué se envía) antes de aprobar. ✅
- **F-4 · acción del hilo que FINGÍA.** El botón cantaba «Hecho ✅» sin ejecutar. → ahora ejecuta de
  verdad (`/agent/run`) o marca «Visto». ✅
- **Verificado OK:** envío de correo real a la propia dirección (recibo `message_id` real, destinatario
  correcto).

**Abierto (los que de verdad hacen que la experiencia sea mala) — por prioridad:**
- **F-5 🔴 · features estrella VACÍAS.** `/cuentas` vacío, galaxia 0 €, sin facturas cargadas →
  **cobros y 303 no tienen datos**. La promesa central no se puede cumplir. Falta **intake de facturas**
  (subir carpeta / conectar). Es producto/roadmap, no un parche.
- **F-6 🔴 · el agente flaquea sin datos.** «Preparar borrador 303» → *completed, 0 steps*, promete y no
  hace nada, pregunta dónde están las facturas (prohibido) y se corta a media frase. Debería **mirar de
  verdad** (list_directory/read_invoice) o **abstenerse con honestidad y una salida** («no encuentro
  facturas del 2T; súbelas o conéctalas y te lo preparo»). Nunca prometer-y-no-hacer.
- **F-7 🟠 · «esta semana» infra-responde.** Solo devuelve eventos de HOY (no hay tool de semana); se
  deja la reunión del jueves con David. Falta `calendar_week` o ampliar `daily_brief` a la semana.
- **F-8 🟠 · spinner muerto.** «Procesando ●●●» 15-25 s sin decir qué hace. Mostrar los PASOS en vivo
  («mirando tu agenda…», «redactando…») en vez de un punto suspensivo.
- **F-9 🟠 · telar inestable.** El contenido cambia en cada refresco (la comprensión del 14B es no
  determinista) → sensación de inestabilidad. Estabilizar (fijar orden/criterio, cachear más, o votar).
- **F-10 🟡 · optimismo prematuro.** La acción del hilo dice «lo he dejado listo» ANTES de que el agente
  termine. Debería decir «preparando…» y confirmar al terminar.

**Lectura de conjunto:** la UX de superficie ya está mucho mejor (Olas 1-2 + estos fixes), pero la
*sensación de valor* falla por **F-5/F-6**: sin datos cargados, las funciones estrella van vacías y el
agente improvisa en vez de guiar. El siguiente salto de experiencia REAL es **intake de facturas +
abstención honesta con salida**, no más maquillaje.

---

## 5ter · RONDA 3 — auditoría DURA visual · estética · funcionalidad

> Encargo: *«otra auditoría DURA de visual, estética, funcionalidad».* Mirando los píxeles con ojo
> crítico en el Chrome real (1280px), no de pasada.

**Home `/` (la UI diaria):**
- **V-1 🔴 · se desperdicia ~60% del lienzo.** El contenido vive en una columna estrecha centrada
  (~500px); bandas vacías enormes a izquierda y derecha y **todo el tercio inferior en negro** hasta el
  input, que flota solo abajo. Se siente **a medio terminar / barato**. Un producto TOP llena el lienzo
  con intención (2 columnas: tela + contexto/galaxia, o tela más ancha).
- **V-2 🟠 · jerarquía plana.** Todas las filas del telar pesan igual (icono + título + subtítulo gris
  diminuto + pill). El semáforo es solo un borde fino. Lo urgente y «lo más importante» no destacan.
- **V-3 🟠 · botones indistinguibles.** «Ver» (leer) y «Redactar respuesta»/«Preparar borrador»
  (efecto) son el MISMO pill degradado. No se distingue una acción inocua de una con efecto externo.
- **V-4 🟡 · contraste/densidad.** Los subtítulos (`detalle`) son pequeños y de bajo contraste; cuesta
  leerlos. El `porque` real (que ya calcula el backend) ni se muestra en la home (solo en la Tela nueva).
- **V-5 🟡 · sidebar esquelético.** «Procesos diarios», «Contactos», «Cuentas a cobrar» son cabeceras
  colapsadas sin contenido; «Historial: sin conversaciones»; mucho hueco vacío. Da sensación de vacío.
- **V-6 🟡 · topbar críptica.** Iconos diminutos sin etiqueta apretados en la esquina (Fábrica, redactar,
  +, ajustes): descubribilidad pobre.

**Fábrica (🏭):**
- **V-7 🔴 · expone las tripas al usuario.** La Sala de la Fábrica es una **pestaña primaria** del usuario
  y muestra el **código fuente interno de Loombit** («Posible bug B008 en `routers/agent.py:186`»,
  «Riesgo S112 en `agent/loop.py:608`», rutas de fichero). Un autónomo no debe ver eso: confunde, asusta
  y rompe el principio BLANCO. Debe ser **backstage** (solo builder / tras flag), como dice §3 («se asoma
  sola»). *Funciona bien y con datos reales — es problema de AUDIENCIA y ubicación, no de bug.*
- (+) La Fábrica SÍ usa bien el ancho (3 columnas) — irónicamente mejor compuesta que la home.

**Responsive:** no verificado (la herramienta no reflejó el redimensionado). Sospecha alta de que el
monolito NO es responsive (sidebar de ancho fijo, layout de escritorio) → **móvil sin comprobar**, y el
autónomo trabaja mucho desde el teléfono. Pendiente de verificar de verdad.

## 5quater · PRIORIDAD FUSIONADA (todas las rondas — qué mover primero)

> Fusión de la Ronda 2 (funcional) + Ronda 3 (visual). Ordenado por impacto en «se siente TOP / útil».

1. **🔴 F-5 · features estrella sin datos** (intake de facturas). Sin esto, cobros/303/galaxia van vacíos.
2. **🔴 F-6 · el agente flaquea sin datos** → abstención honesta con salida (no prometer-y-no-hacer).
3. **🔴 V-1 · la home desperdicia el lienzo** → layout que respira y usa el ancho (o promover la Tela nueva).
4. **🔴 V-7 · la Fábrica expone el código interno al usuario** → backstage tras flag.
5. **🟠 V-2/V-3 · jerarquía y botones** → diferenciar urgencia y acción-con-efecto.
6. **🟠 F-7 · «esta semana»** → tool de agenda semanal.
7. **🟠 F-8 · spinner muerto** → mostrar los pasos en vivo.
8. **🟠 F-9 · telar no determinista** → estabilizar.
9. **🟡 V-4/V-5/V-6, F-10, responsive** → contraste, sidebar, topbar, optimismo, móvil.

**YA ARREGLADO (verde):** F-1 jerga de tools · F-2 volcado de código · F-3 aprobación a ciegas · F-4
acción que fingía · (Olas 1-2) doble saludo, telar instantáneo, porqué real, aprobación en columna,
galaxia real, chat copiloto, Google, acción real.

---

## 6 · La definición de TOP (el listón con el que se mide el resultado)

Fernando abre Loombit a las 9:00. En **<1 s** ve su día ya tejido (no un blanco). **No escribe nada**.
Pasa el ratón por «Construcciones Mar» y ve, sin abrir nada, quién es, cuánto debe y desde cuándo. Un
toque: el 2º aviso ya redactado en su voz, con el porqué y la procedencia, 🔒 hasta pulsar Enviar. Lo
envía: micro-celebración + «hecho, te aviso si responde · +8 min». Ve que el 303 está cubierto. Lee
«🔒 nada ha salido de tu máquina · te he ahorrado 14 min». Sonríe. No abre Gmail en toda la mañana.
**Cuando todo eso pasa sin pensar, es TOP.** Hoy faltan: el remate del primer segundo, la unidad de un
solo producto, y que la tarjeta suene inteligente. Eso es lo que arregla este plan.
