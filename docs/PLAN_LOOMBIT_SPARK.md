# Plan — Loombit como el Spark privado del autónomo español

> Aprobado por Fernando (2026-06-11). Objetivo: que **Loombit** (el producto) haga
> todo lo que hace **Gemini Spark** (agente proactivo 24/7, vigila la bandeja, corre
> workflows, encadena tareas, aprende skills de ti, consulta antes de actuar), pero en
> su clave: **local** (los datos no salen de la máquina), **español administrativo
> profundo** y **bajo el gobierno** (cada 🟢 con recibo; ver `docs/BRUJULA_ALGORITMO.md`).
>
> Donde Spark es genérico y cloud, Loombit es íntimo, local y experto. Lo que NO se copia
> a propósito: ejecución en la nube, Drive/Sheets/Slides/YouTube genéricos, y la autonomía
> sin confirmar efectos externos (rompería el foso).

## Mapa de paridad (Spark → Loombit, verificado contra el código 2026-06-11)

| Feature de Gemini Spark | En Loombit | Estado |
|---|---|---|
| Agente 24/7 en segundo plano | Daemon local + `scheduler.py` (`SchedulerDaemon`) | 🟡 base puesta |
| Vigila la bandeja / triggers de email | Telar lee Gmail real; `reply_watch_executor` | 🟡 |
| Redacta respuestas en tu estilo | Borrador + aprobación; estilo vía memoria/GEPA | 🟡 |
| Workflows programados (cron/condicional) | Motor de Routines (`routines.py`) | 🟢 base |
| To-do priorizado / brief diario | `brief_executor` + "tela de la mañana" | 🟢 |
| Bloquear calendario para foco | Calendar create 🟢; auto-bloqueo no | 🟡 |
| Tareas multi-paso entre apps | Agent loop + tools | 🟡 |
| Investigar en webs / comparar | Skill Pilot navegador pendiente | ⬜ |
| Apps: Gmail/Calendar | Gmail send 🟢, Calendar create 🟢 | 🟢 |
| Apps: Drive/Docs/Sheets/Slides/Maps | — (fuera del foso admin) | ⬜ |
| Skills enseñables (aprende de ti) | Fábrica de Skills + GEPA | 🟡 motor, falta UX |
| Skills auto-disparadas por repetición | Routines + Fábrica | 🟡 |
| Permisos opt-in + confirma acciones graves | Gate D-20 (efecto externo → humano) | 🟢 |
| Memoria persistente entre tareas/tiempo | `agent/memory.py` + RAG + EntityProfile | 🟢 |
| Tools externas vía MCP | Servidor MCP 🟢; cliente MCP pendiente | 🟡 |
| Paneles Task/Schedule/Skill + "trabajando…" | Telar/galaxia/chat; faltan paneles + latido | 🟡 |

## Fases

### S0 — Cimientos honestos *(pendiente humano)*
Fundir el gobierno (PR #8/#10) + activar branch protection (status check `verify`
requerido + Code Owners). Sin esto, la "paridad de features" no sería verificable.

### S1 — Agente proactivo 24/7 **visible** *(la identidad de Spark)*
El daemon local vigila bandeja + calendario + cobros + plazos y teje un feed de hilos
accionables; la UI muestra un estado vivo "Loombit está trabajando…" y cada acción a un
clic / "Aprobar todo".
- **Reutiliza:** `scheduler.py`, `routine_executors.py`, `routers/routines.py` (`/feed`),
  `telar.py`, `static/loombit.html`.
- **🟢 cuando:** con Gmail real, el daemon detecta ≥1 trigger real sin que el usuario
  pregunte, lo surfacea con la acción preparada, recibo guardado. (UI 🟡 hasta verificar
  en escritorio real.)

### S2 — Skills enseñables *(la feature estrella de Spark)*
"Enséñale" en lenguaje natural una tarea repetida → Loombit la convierte en routine/skill
reutilizable auto-disparada (cron o evento).
- **Reutiliza:** Fábrica de Skills, GEPA, `skill_loader`, motor de Routines. **Falta:**
  captura NL → manifest + panel de activación.
- **🟢 cuando:** el usuario describe 1 skill en NL, Loombit la crea y la dispara en un
  caso real, recibo — bajo el gobierno (arnés antes de auto-aplicar; humano aprueba
  efectos externos).

### S3 — Paneles de gestión *(las superficies de Spark)*
Paneles **Tareas / Agenda (workflows) / Skills** + buscador (RAG semántico local).
- **🟢 cuando:** los 3 paneles muestran estado real del backend (no mocks) y el buscador
  devuelve resultados del índice local.

### S4 — Encadenado multi-paso *(el "multi-app" de Spark, en clave admin)*
Cadena e2e: leer factura (intake) → expediente → 303 / plan de cobro → borrador →
*(humano aprueba)* → enviar/conciliar.
- **Depende del linchpin: intake real** (Gmail adjuntos + extractor).
- **🟢 cuando:** una cadena real de punta a punta con recibo en cada paso.

### S5 — Aprende de ti *(estilo + memoria)*
Estilo de redacción aprendido de correos pasados (ghostwriter), perfil del owner, memoria
de relaciones (galaxia / EntityProfile).
- **🟢 cuando:** un borrador en el estilo del usuario validado contra ejemplos reales.

### S6 — Tools externas vía MCP *(el ecosistema de Spark, en clave admin)*
Cliente MCP para herramientas verificadas; en admin = AEAT/Sede, banca N43, VeriFactu.
- **🟢 cuando:** 1 integración externa real bajo el gobierno.

## Transversales
- El **gobierno** gobierna cada fase (🟢 = recibo reproducible).
- La **deuda de arquitectura** (`agent/loop.py` 1338, `agent/memory.py` 964, `telar.py`
  806) se refactoriza con arnés cuando una fase toque ese fichero.

## Estado de ejecución
- **S1 — en curso** (2026-06-11): primer corte = latido del daemon (`SchedulerDaemon.status()`)
  + endpoint `GET /routines/status` ("Loombit está trabajando…"). Backend unit-tested 🟢;
  pulido de UI 🟡 hasta verificación en escritorio real.
