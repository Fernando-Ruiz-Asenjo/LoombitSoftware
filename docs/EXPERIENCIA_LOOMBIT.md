# EXPERIENCIA LOOMBIT — rediseño total de la UX (excelencia, fricción 0)

> Propuesta de rediseño **completo** de la experiencia. No es maquillaje: replantea la
> arquitectura de interacción para que Loombit se **sienta** lo que ya **es** por dentro
> (operador local que anticipa, prepara y aprende). Aterriza la visión EL TELAR
> (`investigacion/INVESTIGACION_7_EL_TELAR.md`) + la Galaxia (`GALAXIA_LOOMBIT.md`) y aplica lo
> destilado de la newsletter Mafia IA (ver `../mafia-ia-destilado/`). *Generado: 2026-06-09.*
>
> **Estado:** propuesta (doc). La UI hoy es un **monolito** `static/index.html` (2.552 líneas /
> 125 KB, todo inline). Este doc es el plano para reconstruirla por componentes y por slices con DoD.

---

## 0 · El brief, en una frase
**Que al abrir Loombit el autónomo sienta que "esto ya me conoce, ya me ha quitado trabajo de la
mesa, y nada ha salido de mi ordenador" — y que cerrar Loombit le dé un poco de vértigo.**
Indispensable = la sensación de que sin él la oficina va más lenta y con más miedo a equivocarse.

---

## 1 · Las métricas‑sensación, hechas medibles (sin esto, es palabrería)

| Sensación buscada | Proxy medible (DoD de la UX) |
|---|---|
| **Fricción 0%** | *Time‑to‑value* < 2 min en el primer arranque (de abrir a "ya te dejé esto preparado"). **0** formularios libres, **0** JSON, **0** nombres de tool a la vista. Toda acción a **1 toque** (máx 2 con confirmación de efecto externo). |
| **Útil 100%** | Cada elemento de la UI nace de un dato real con endpoint (`/telar`, `/galaxia`, `/cuentas`, `/routines/feed`, `/agent/memory`…). Cero placeholders, cero "lorem". |
| **Se nota inteligente** | Te recibe con lo **ya hecho** (no con un cursor vacío). Cada propuesta trae **un porqué en 1 línea**. **Hover = el hilo entero** (contexto sin clic). Anticipa la siguiente acción. **Se abstiene con honestidad** cuando duda. |
| **Cómodo / te quita trabajo** | Caminos de 1 gesto; nada que recordar; el sistema trae, tú confirmas. **Contador de tiempo ahorrado** visible. |
| **Indispensable** | **Antes/Después semanal** ("esta semana te quité 4 h 20 m de la mesa: 12 cobros preparados, 3 plazos cazados…"). El "telar de la mañana" como primer reflejo del día. |
| **Confianza (la base de todo)** | En cada acción externa: **procedencia** (de dónde salió el dato) + **🔒 nada salió de tu máquina** + **semáforo** + **recibo**. La confianza es la UI, no una pestaña de ajustes. |

---

## 2 · Las 10 leyes de la UX de Loombit (gobiernan TODA pantalla)

1. **Anticipa → prepara → el usuario confirma. Casi nunca inicia.** El cursor vacío es un fracaso de
   producto. Loombit habla primero, con trabajo ya hecho. *(EL TELAR · BRÚJULA)*
2. **Un solo lienzo vivo, no un menú de pestañas.** Tela (la mañana), Galaxia (el mapa), Chat
   (el copiloto) y Aprobaciones son **vistas del mismo cerebro**, no apps distintas. Se transita con
   continuidad espacial, nunca "navegando". *(mata la fragmentación actual home/chat/telar/galaxia/sala)*
3. **El contexto vive en el hover (revelación progresiva L0→L1→L2).** Pasa por encima de un nombre,
   factura o correo y aparece **el hilo entero** (quién es, historia, dinero, qué falta) sin abrir nada.
   *(Context Engineering #03 + EL TELAR)*
4. **Cero formularios, cero JSON, cero jerga.** Tiras del hilo (arrastras, escribes una palabra,
   tocas un chip) y se teje la acción. El usuario nunca ve `gmail_send` ni un campo "to:".
5. **La confianza es la interfaz.** Procedencia + 🔒 local + semáforo + recibo, **siempre visibles** en
   el momento de actuar — no escondidos. *(Anti‑alucinación #05 · foso local #02)*
6. **Nunca pidas revisar lo que deberías saber.** Si Loombit pide "¿confirmas el email de Jana?",
   ha fallado: que lo resuelva (frecuencia real) y solo confirme el **efecto externo**. *(BRÚJULA)*
7. **Lenguaje humano, cálido y desenfadado — en español, nunca corporativo, nunca "soy una IA".**
   Celebra los logros, respira con animaciones suaves. *(#26 impacto emocional)*
8. **Muestra el tiempo que ahorras.** Cada acción cerrada suma a un contador; cada semana, un
   antes/después. El valor se *siente* porque se *ve*. *(#12 indispensable)*
9. **Fiabilidad = UX. Nunca falles en silencio.** Si algo no se puede, dilo y ofrece la salida; jamás
   re‑pausa muda ni bucle. Honestidad > parecer mágico. *(#06 OpenClaw: el hype que se rompe pierde)*
10. **Piensa CONTIGO, no por ti.** En lo ambiguo no adivina a ciegas ni te abruma: te muestra 2‑3
    caminos con su porqué y tú eliges en 1 toque. Te hace sentir más listo, no reemplazado. *(#16)*

---

## 3 · La rearquitectura: de 6 pantallas sueltas a UN telar

**Hoy (fragmentado):** Home · Chat · Telar (panel) · Galaxia · Sala (GEPA/Fábrica) · Aprobaciones —
cada una su sitio. El usuario "navega". Eso es fricción y rompe la sensación de un único cerebro.

**Propuesta — un workspace con una espina y tres profundidades de zoom:**

```
                 ┌─────────────────────────────────────────────┐
   barra viva →  │  🔒 local · ⏱ esta semana: 4h20m · 🔔 2 nuevo │   (presencia, no menú)
                 ├─────────────────────────────────────────────┤
                 │                                             │
   EL TELAR  ←   │   LA TELA DE HOY  (lo importante, ya tejido) │  ⌘K  (paleta: salta/actúa)
   (home, la     │   ── hilos accionables, 1 toque ──           │
    mañana)      │                                             │
                 │   [⤢ Mapa]  ↔  conmuta a la GALAXIA          │  ← Chat copiloto SIEMPRE presente
                 └─────────────────────────────────────────────┘     (cajón inferior, se expande)
```

- **Capa 1 · La Tela (home, la mañana).** Lo primero que ves: **hilos** que el daemon ya tejió
  (cobros preparados, plazos cazados en la bandeja, calendario fiscal, correos sin responder,
  aprobaciones). Cada hilo = una frase humana + su acción a 1 toque + "Aprobar todo". *(reusa `/telar`)*
- **Capa 2 · La Galaxia (el mapa, mismo lienzo, zoom out).** El negocio como sistema estelar
  (sol+órbitas, anti‑hairball, gravedad semántica, drag‑to‑act, ⌘K). No es otra pantalla: es **alejar
  la cámara** desde la Tela. *(reusa `/galaxia` + canvas ya hecho)*
- **Capa 3 · El Planeta/Hilo (el detalle).** Foco en una factura/cliente/hilo: su constelación, su
  recibo, su historia — y actuar. Se abre **en contexto**, no en una ruta nueva.
- **El Chat = copiloto omnipresente**, no una pestaña: un cajón inferior siempre a mano que se expande;
  ejecuta lo que escribes y **deja su rastro como un hilo más** en la Tela. Smalltalk responde al
  instante (ya está). *(reusa el chat + smalltalk)*
- **Aprobaciones = tarjetas inline** donde ocurren (en el hilo, no en un buzón aparte).
- **La Sala (Fábrica/GEPA) = backstage.** No es una pestaña de uso diario; **se asoma sola** cuando hay
  algo que proponer ("he aprendido a hacer X mejor, ¿lo activo?"). El usuario normal casi no la ve.

> **Tesis:** Tela = *lo de hoy*; Galaxia = *el mapa de todo*; Hilo = *el detalle*. Tres profundidades
> del **mismo** lienzo, con transiciones continuas (zoom), nunca un cambio de "página".

---

## 4 · Momento a momento (lo minucioso — aquí se gana o se pierde)

### 4.1 Primer arranque (time‑to‑value < 2 min, fricción 0)
- **No** un wizard de 6 pasos. Una sola frase cálida + **un botón**: "Conecta tu Google y te enseño tu
  semana en 30 segundos." El nombre del `owner` se **deriva** de Google al conectar (no lo pidas).
- Mientras conecta: micro‑animación del telar tejiendo (no un spinner frío).
- Al volver: la Tela **ya está tejida** con datos reales (sus correos, su agenda, su primer plazo
  detectado). El primer "wow" es ver **su** mundo ordenado sin haber configurado nada.
- **Cero antes del valor:** nada de "elige tu plan / tu sector / tu tono". Eso se infiere y se ajusta
  después, solo si hace falta.

### 4.2 La mañana (el reflejo diario, la indispensabilidad)
- Loombit **habla primero**, cálido: *"Buenos días. Te he dejado tejido lo de hoy. Lo urgente: 2
  facturas vencen esta semana — ya tienes los recordatorios escritos."*
- Estructura de la Tela: **L0** titulares (1 línea por hilo) → **hover L1** (el porqué + contexto) →
  **toque L2** (el detalle + actuar). Revelación progresiva: nada abruma, todo está a un gesto.
- Barra viva arriba: **⏱ tiempo ahorrado** acumulándose, **🔒 local**, **🔔 novedades** (laten).

### 4.3 Un cobro (el flujo estrella, de percibir a recibo)
1. La Tela: *"Construcciones Mar te debe 1.250 € — 9 días sin contestar. Te preparé el 2º aviso."*
2. **Hover** → el hilo: la factura, el correo enviado, el historial de pagos del cliente ("suele
   pagar +12 días tarde"), el IBAN conocido. Todo con **procedencia**.
3. **Toque** → tarjeta de aprobación (§5.2): el correo redactado en **tu voz**, semáforo verde, "🔒
   local hasta que pulses Enviar". Botón **Enviar** (único efecto externo, 1 toque).
4. Al enviar: micro‑celebración suave + **recibo** ("enviado, te lo guardo") + **+8 min** al contador.
5. Si aparece un **IBAN nuevo** para ese cliente: **gate antifraude visible** — "ojo, IBAN distinto al
   habitual; verifícalo por teléfono antes de pagar." La seguridad como acto de cuidado, no como error.

### 4.4 Leer un hilo de correo (hover‑para‑ver‑el‑hilo)
- En cualquier sitio donde salga un nombre/asunto: **hover** = quién es, de qué va, en qué estado,
  cuánto te debe, qué hay pendiente — **sin abrir el correo**. El contexto tejido es el superpoder que
  Google no te da en local. *(EL TELAR §C2)*

### 4.5 Una petición ambigua (el momento "pensar contigo")
- Si escribes "prepara lo del trimestre" y hay ambigüedad real, Loombit **no** suelta un formulario ni
  adivina a ciegas: ofrece **2‑3 caminos con su porqué** ("¿el 303 del 2T (vence el 20) o el resumen
  de gastos?") como chips. 1 toque resuelve. Te sientes acompañado, no interrogado. *(#16 · Super Loop)*

### 4.6 Un error / un límite (fiabilidad = UX)
- Nada de spinner eterno ni re‑pausa muda. Mensaje humano y honesto: *"No he podido leer ese PDF
  (parece escaneado). Lo paso por reconocimiento — dame 15 s — o súbelo de nuevo."* Siempre una salida.
- Anti‑flailing: si una acción falla 2 veces, **cambia de estrategia** y lo dice; nunca repite a ciegas.

### 4.7 El resumen semanal (el gancho de indispensabilidad)
- Cada viernes (o al abrir tras el finde): un **antes/después** cálido — *"Esta semana te quité 4 h 20 m
  de la mesa: 12 cobros, 3 plazos cazados, 8 correos redactados. Y aprendí 2 cosas nuevas sobre cómo
  trabajas."* Es la prueba emocional del valor. *(#12 · #26)*

---

## 5 · Gramática de interacción (los gestos y las piezas)

### 5.1 Los gestos (pocos, consistentes)
- **Tirar del hilo / drag‑to‑act:** arrastrar un planeta sobre otro dispara la acción (factura→cliente =
  reclamar; documento→cliente = enviar; cliente→eventos = agendar). *(Galaxia §3)*
- **⌘K (paleta de comandos):** salta a cualquier planeta o dispara una acción por lenguaje ("reclamar a
  Mar", "agenda con David"). La precisión que el espacio no da. *(de Superhuman, ya decidido)*
- **Hover:** revela el hilo (L1). **Toque:** actúa/abre (L2). **Doble toque:** al chat con ese contexto.
- **1 toque para confirmar** cualquier efecto externo. Nada más.

### 5.2 Anatomía de la tarjeta de aprobación (la pieza más importante)
```
┌────────────────────────────────────────────┐
│ 📨 Recordar pago a Construcciones Mar        │  ← qué, en humano
│ "Hola, te recuerdo la factura 24/0312…"      │  ← el resultado YA redactado, en tu voz
│ ───────────────────────────────────────     │
│ Porqué: vence en 3 días · suele pagar tarde  │  ← el porqué en 1 línea (inteligente)
│ Fuente: factura 24/0312 + tu hilo del 2/6 🔗 │  ← procedencia (confianza)
│ 🔒 nada saldrá hasta que pulses Enviar        │  ← privacidad sentida
│        [ Editar ]        [ ✅ Enviar ]        │  ← 1 toque; editar opcional, nunca obligatorio
└────────────────────────────────────────────┘
```
- **Semáforo** en el borde (🟢 listo / 🟠 revisa esto / 🔴 bloqueado por gate). El color *es* el estado.
- "Editar" existe pero **nunca es obligatorio** (si lo fuera, habríamos fallado la ley 6).

### 5.3 Piezas persistentes
- **Barra viva** (no menú): 🔒 local · ⏱ ahorrado · 🔔 novedades (laten por evento del daemon).
- **Chip de procedencia** (🔗): toca y ves de qué dato exacto salió algo. Confianza a demanda.
- **El semáforo** como lenguaje transversal (cobros, conciliación, propuestas de la Fábrica).

---

## 6 · Voz y motion (extensión de Skill C Skins)

- **Voz:** cálida, breve, desenfadada, **en español de tú**, con oficio administrativo. Nunca "como IA
  no puedo…", nunca corporativo, nunca jerga técnica. Firma el trabajo como **el usuario**, no como
  Loombit (lección F4). Celebra sin pasarse ("hecho ✅", "uno menos").
  - *Antes (frío):* "Operación completada. message_id 19ea…" → *Después:* "Enviado a Mar ✅ Te aviso si responde."
  - *Antes:* "Error: token expired" → *Después:* "Se me caducó el permiso de Google; reconéctalo en 1 toque 👇"
- **Motion:** identidad **violeta→cian** (halo del Pilot); transiciones por **zoom** (Tela↔Galaxia↔Hilo),
  nunca cortes de página; **latido** suave de un planeta al haber novedad; micro‑celebración al cerrar
  una acción; el telar **tejiendo** como estado de carga (nunca un spinner pelado). Todo suave, 60 fps,
  respetando *prefers‑reduced‑motion*.

---

## 7 · Mecánicas de "se nota inteligente" (trucos concretos, no magia)

1. **Te recibe con lo ya hecho** (no con un cursor). El primer mensaje es trabajo, no saludo vacío.
2. **El porqué en 1 línea** en cada propuesta (causa + dato). Saber *por qué* lo hizo = confianza.
3. **Hover = el hilo entero.** Demuestra que "lo entiende", no que "lo busca".
4. **Recuerda y referencia:** "como con el cliente Pérez el mes pasado". *(memoria operativa ya existe)*
5. **Anticipa el siguiente paso:** tras enviar un aviso, ofrece "te aviso si no responde en 3 días".
6. **Se abstiene con honestidad** cuando duda — y eso, contraintuitivamente, **sube** la confianza
   (#05). Mejor "esto no lo sé seguro, verifícalo" que inventar con aplomo.
7. **Aprende a la vista:** "he notado que siempre suavizas el tono de los recordatorios — ya lo hago."
   *(la Fábrica/aprendizaje, hecho visible y celebrado)*

---

## 8 · El motor de indispensabilidad (que enganche de verdad)

- **Libro de tiempo ahorrado:** cada acción cerrada estima minutos ahorrados (determinista, conservador)
  → contador en la barra + resumen semanal antes/después. *(#12)*
- **Proactividad cálida con tope:** el daemon teje la mañana y **se asoma** con novedades, pero **nunca
  spamea**; respeta horas; agrupa. La presencia es bienvenida, no intrusiva.
- **Cada semana queda mejor:** la Fábrica teje skills de tus patrones; la UX lo **muestra** ("esta
  semana aprendí 2 cosas"). Un asistente de nube resetea; el telar local recuerda — y lo demuestra.

---

## 9 · Anti‑patrones a MATAR (lista de la compra del rediseño)

- ❌ Cursor de chat vacío como home. ✅ La Tela ya tejida.
- ❌ Pestañas/menú que obligan a "navegar". ✅ Un lienzo con zoom.
- ❌ Formularios, campos `to:`, JSON, nombres de tool. ✅ Lenguaje + 1 gesto.
- ❌ "¿Confirmas el email de X?" / "¿le doy?". ✅ Resuelto; solo confirmas el efecto externo.
- ❌ Muros de texto. ✅ L0→L1→L2 progresivo.
- ❌ Spinner eterno / fallo en silencio / re‑pausa muda. ✅ Estado honesto + salida + anti‑flailing.
- ❌ Privacidad escondida en ajustes. ✅ 🔒 "nada salió de tu máquina" en el momento de actuar.
- ❌ Tono corporativo / "soy una IA". ✅ Voz humana, cálida, en tu nombre.

---

## 10 · Plan de construcción (slices con DoD — accionable, no solo visión)

> **Regla:** rama/worktree; el núcleo del agente con OK de Fernando; **mata el monolito**: trocea
> `static/index.html` (2.552 líneas) en componentes (Tela, Galaxia, Chat, Tarjeta, BarraViva) +
> un sistema de tokens (color/typography/motion = Skill C Skins) y un único bus de estado.

| Slice | Qué entrega | DoD 🟢 |
|---|---|---|
| **S0 · Tokens + esqueleto** | Sistema de diseño (violeta→cian, semáforo, motion, tipografía) + shell del lienzo único + barra viva (🔒/⏱/🔔) | El shell carga datos reales de `/telar` y `/galaxia`; 0 regресión de lo vivo |
| **S1 · La Tela como home** | La mañana tejida (reusa `/telar`) con L0→hover L1→toque L2 + "Aprobar todo" | Con Gmail real, teje ≥1 hilo real (plazo/cobro) y actúa a 1 toque, con recibo |
| **S2 · Tarjeta de aprobación canónica** | La pieza §5.2 (porqué + procedencia + 🔒 + semáforo + 1 toque), usada por cobros/fiscal/conciliación | Un cobro real se aprueba desde la tarjeta y deja recibo; gate IBAN se ve |
| **S3 · Continuidad Tela↔Galaxia↔Hilo** | Zoom continuo entre las 3 profundidades (sin cambio de página) reusando el canvas | Transición fluida verificada; foco enseña solo su constelación |
| **S4 · Chat copiloto omnipresente** | Cajón inferior expandible; su salida cae como hilo en la Tela; smalltalk instantáneo | Una orden por chat ejecuta y aparece como hilo; "hola" responde <0,5 s |
| **S5 · Tiempo ahorrado + resumen semanal** | Libro de minutos + antes/después | El contador sube con acciones reales; el resumen cuadra con los recibos |
| **S6 · Voz & microcopy + motion** | Reescritura de todos los textos a la voz §6 + animaciones suaves + reduced‑motion | Auditoría: 0 textos corporativos/jerga; celebra al cerrar; 60 fps |
| **S7 · La Sala que se asoma** | La Fábrica/GEPA deja de ser pestaña: notifica una propuesta cuando la hay | Una propuesta real de la Fábrica aparece como aviso y se aprueba/descarta |

**Orden recomendado:** S0→S1→S2 primero (es el 80% de la sensación con datos que ya existen), luego
S3‑S6, y S7 al final. Cada slice **verificable EN VIVO** antes de fundir (regla nº1, sin mentir).

---

## 11 · Definición de "delicioso" (el listón)
Un autónomo abre Loombit a las 9:00, **no escribe nada**, y en 20 segundos ha mandado 2 recordatorios
de cobro en su voz, ha visto que un plazo fiscal está cubierto, y lee *"🔒 nada ha salido de tu
máquina · te he ahorrado 14 min"*. Sonríe. No vuelve a abrir Gmail en toda la mañana. **Eso** es la meta.
