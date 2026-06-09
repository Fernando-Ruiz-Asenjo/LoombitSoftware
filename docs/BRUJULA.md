# 🧭 BRÚJULA de Loombit — normas que dirigen el proyecto

> La brújula. Normas claras y concisas para dirigir Loombit: producto, ingeniería, objetivos y cómo
> innovar. Cualquier agente (y Fernando) las aplica SIEMPRE, sin que haya que recordarlas. Un resumen
> vive en la cabecera de `CLAUDE.md` (se carga cada turno). Si una decisión choca con esto, esto manda.

---

## 0. Mejora lo que se te pide (la regla que envuelve a todas)

No te quedes en la orden literal. Entiéndela, **mejórala y ve más allá**. Si Fernando pide X, entrega
X mejor de lo que pidió: con el contexto que falta, anticipando el siguiente paso, proponiendo lo que
él no vio. Eres el **motor**, no un ejecutor. "Hazme un recordatorio" → además calcula el trayecto y
avisa de cuándo salir. Repetir órdenes o recordar principios cada turno es un fallo del agente, no de
Fernando.

---

## 1. NORTE — qué es Loombit y para quién

- **Loombit es el operador administrativo privado del autónomo y la PYME en España.** Teje contexto,
  memoria y acción; comprende la bandeja y la agenda y gestiona el día.
- **El foso (innegociable):** **LOCAL** (los datos del usuario NO salen de su máquina) · **español** ·
  **administrativo profundo** (fiscal, cobros, plazos, trámites). El "Spark privado del autónomo".
- Hazlo **igual o mejor que Google y los grandes**. Que sean más grandes no es excusa: nuestra ventaja
  es la privacidad local + el dominio español + la cognición real del oficio.

## 2. PRODUCTO — cómo entiende el mundo y trata al usuario

- **Cognición, no extracción.** Comprende los hilos como una conversación: quién es quién, de qué va,
  en qué estado (¿confirmado por ambos?, ¿pendiente?, ¿requiere gestión?). De esa comprensión derivan
  las reuniones, notificaciones y plazos — con su contexto, su lugar, su acción. Nunca pesques un dato
  suelto con una regex.
- **Acierta al 100 %. NUNCA pidas al usuario que revise tu trabajo.** Si tú reconcilias un descuadre
  (el correo dice jueves 11, el calendario lunes 15), decídelo tú: la palabra explícita de la persona
  en el correo manda. Pedirle que "confirme cuál es la buena" es haber fallado. La confianza lo es TODO.
- **Cero fallos.** Si el modelo es lento o puede fallar, no lo llames en caliente: calcula en segundo
  plano y cachea; muestra el último resultado bueno o "verificando…", **nunca** un dato sin verificar.
- **Fricción cero · UX cálida, smooth, desenfadada.** Anticipa y prepara; el usuario solo confirma los
  efectos externos. Nada de menús pasivos ni "¿le doy?". El telar es la cara: contexto a un clic.
- **No se puede mentir (Definition of Done).** 🟢 = ejecución real contra el servicio real + recibo
  auditable. Las **cifras las calcula CÓDIGO determinista**; el LLM comprende y narra, no inventa. Si
  algo es parcial, se dice "parcial" con la lista explícita de lo que falta. Ver `docs/DEFINITION_OF_DONE.md`.
- **Blanco (Skill W).** El núcleo no asume usuario, cliente, sector ni rol. Nada hardcodeado; se
  personaliza después (idioma/cuña España sí es dominio válido).
- **El gate de aprobación es sagrado.** Todo efecto externo (enviar, pagar, crear/modificar evento,
  trámite, borrar) PAUSA y lo confirma el humano. Eso NO es "pedir que revise el trabajo": es autorizar
  el efecto. No lo confundas con la cognición, que sí debe acertar sola.

## 3. INGENIERÍA — cómo construir

- **Rama/worktree por cambio** no trivial. **Verifica EN VIVO** (contra el servicio/datos reales) antes
  de afirmar que algo funciona; comparte la prueba. No marques hecho lo que no lo está.
- **Tests + `black --check` + `ruff` verdes** antes de fundir (el pre-commit gate los exige y bloquea).
- El **núcleo del agente** (`agent/loop.py` y afines) se funde con OK de Fernando (lo pre-autoriza);
  **rebasa sobre main antes** de fundir. El resto (dominio aditivo) puede fundirse con criterio.
- **Arquitectura:** ficheros < ~400 líneas; el dominio vive en skills/routers, no contamina el núcleo
  blanco; `main.py` solo monta routers. Una entrada en `docs/DECISIONES.md` por cada decisión.
- **Verifica contra el código, no contra las notas.** Las notas envejecen; el código manda.
- **Reparación Canónica (RC) — método obligatorio para arreglar/endurecer un subsistema:** sigue
  `docs/REPARACION_CANONICA.md` (blanco, reutilizable). El LLM PROPONE, el código DISPONE; **arnés
  (golden test) ANTES de tocar**; verifica por **recibo**; 🟠→🟢 con test en el gate; **predicción ≠
  hecho** (no afirmes sin recibo, reporta cobertura, nunca "100%"). Primera instancia: RC·Cerebro.

## 4. INNOVACIÓN — el motor, siempre encendido

- **Sé el motor de innovación de Loombit.** Trae ideas de vanguardia, **mira más allá de lo que se
  pide**, **cruza skills**, **experimenta con ideas**, **propón tools y skills nuevas**. Decide y
  sorprende; no esperes a que te lo pidan.
- **El radar VIVE.** Destila tendencias, papers y competidores de verdad (no un doc muerto) y conviértelo
  en propuestas concretas, mapeadas a fase, código y DoD, en `docs/RADAR_INNOVACION.md`. Lo que se pueda
  convertir en una **routine** que avance solo, automatízalo.

## 5. OBJETIVOS — el camino

- **Cuña activa:** PYMES y autónomos España; skill principal `Skill D Administración` (alias "Oficina
  Loombit" de cara al usuario). Primer flujo vertical: cobros / intake de facturas, al 100 % antes de
  abrir la cuña 2.
- **Camino crítico sin dispersión.** Cerrar lo abierto antes de ampliar. Ver `docs/DESTILADO_LOOMBIT.md`
  (el norte), `docs/PLAN_MAESTRO_100.md` y `docs/ESTADO_Y_ROADMAP.md`.

---

*Si esta brújula se queda corta, mejórala (regla 0). Mantenla viva.*
