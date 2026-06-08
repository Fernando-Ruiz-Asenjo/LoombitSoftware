# Handoff — siguiente sesión (estado al 2026-06-08, ~20:00)

> Guardado de TODO para arrancar una sesión nueva sin perder contexto. Léelo entero.
> Repo canónico: `C:\Users\fernando\loombit-new` (Windows, PowerShell). App: `python -m
> loombit_operator.launcher` (FastAPI :8787). Verifica SIEMPRE contra el código, no las notas.

## TL;DR
Loombit avanzó de "herramienta dura que conduces tú" a **operador proactivo y cálido** (la visión
EL TELAR). `main` = **`3e74735`**, **server vivo en :8787** con todo lo desplegado. Quedan **2 ramas
mías sin fundir** (docs + blanqueado) y un frente claro por delante (fiabilidad del agente).

## Lo DESPLEGADO y VIVO en `main` (:8787)
- **La tela de la mañana** (`telar.py` + `GET /telar` + panel al abrir): teje el día en hilos
  accionables (agenda, cobros, correos sin responder, **plazos detectados en la bandeja**,
  **calendario fiscal del autónomo**, aprobaciones). Cada hilo con su acción a un clic → "Aprobar
  todo". Verificado EN VIVO con el Gmail real (encontró un plazo real + el 303 del 2T).
- **Galaxia viva + drag-to-act** (pre-carga + chips arrastrables → acción).
- **Servidor MCP** (`/mcp`, protocolo 🟢, gate server-side).
- **Operador proactivo + nombres humanos** + **resumen del día en el chat** (`daily_brief`).
- **Qwen2.5-VL para facturas escaneadas** (🟡, falta cargar el VL + un escaneo real).
- **Fixes**: aprobar evento ya no re-pausa, gmail_search, task_done colgante, "← Volver al chat",
  detalle en "Aprobar todo".
Decisiones en `docs/DECISIONES.md` (D-28…D-31). Estado en `docs/ESTADO_Y_ROADMAP.md` (ya sincronizado).

## Ramas SIN FUNDIR (esperan OK de Fernando para merge a main)
1. **`feat/blanco-owner`** (worktree `loombit-par-blanco`, HEAD `2d14cac`) — **BLANQUEADO**: quitar el
   "Fernando" hardcodeado; la identidad del usuario es dinámica (del `owner`, configurable), fallback
   neutro. memory default vacío, telar/`/home/context` exponen `owner`, UI dinámica. **368 tests verdes.**
   *Listo para fundir.*
2. **`docs/investigacion-5-6`** (worktree `loombit-par-docs2`, HEAD `814b317`) — **Investigaciones 5
   (auditoría dura + radar de Skills), 6 (mejorar lo que hay), 7 (EL TELAR: cómo Google/MS/Glean ponen
   contexto/identidad/anticipación + visión local)**. Solo docs. *Listo para fundir.*

Para fundir cualquiera: `cd loombit-new && git merge --ff-only <rama>` (Fernando pre-autoriza el merge
+ reinicio :8787). Rebasar antes si main se movió.

## Cabos sueltos / gaps detectados
- **Falta onboarding del `owner`**: con el blanqueado, un usuario NUEVO arranca con nombre vacío. Hay
  que capturarlo (pantalla simple o derivarlo de Google al conectar). La memoria guardada de Fernando
  ya tiene su nombre, así que él sigue viéndolo.
- **Worktree `loombit-par-telar`**: el directorio quedó BLOQUEADO al desregistrarlo (cosmético;
  `git worktree prune` + borrar el dir cuando se libere).
- **Deuda de arquitectura** (regla ~400 líneas): `agent/memory.py` 950, `tools/pilot.py` 694,
  `routers/computer.py` 673, `agent/loop.py` 647, etc. + `CLAUDE.md` aún dice "Fase actual: Fase 1"
  (cerrada en D-24). Refactor coordinado.

## PRÓXIMOS PASOS (orden propuesto, de Investigación 6)
1. **Frente 2 — fiabilidad/fricción cero** (lo que estaba a punto de empezar): el bug de **re-pausa
   silenciosa al fallar una aprobación** (`loop.resume`) + **anti-flailing** del agente (cortar tras 2
   errores de la misma tool; decirle "esa tool no existe / arg inválido"). TOCA el núcleo del agente
   (`loop.py`) → construir en rama, NO auto-desplegar sin que Fernando lo vea.
2. **Cobros e2e a 🟢** (el hueco del producto): tabla de tipos BCE+8 por semestre (que el interés deje
   de abstenerse) + `Skill A Banca N43` + lazo factura→cuenta candidata.
3. **Supuestos S-01…S-15 → evals deterministas** + métrica de cobertura (`selfcheck` ya reporta huecos).
4. **El grafo de relaciones local** (unir galaxia + galaxia_intel + memoria) y **el índice semántico
   local** (contexto en todo, hover-para-ver-el-hilo) — backlog de EL TELAR (Investigación 7).
5. **VeriFactu** (`Skill D Fiscal`): reloj legal 2027 + multa 50k€; `expedientes.py` ya es la base.

## REGLAS DE TRABAJO (innegociables — Fernando insiste)
- **BLANCO (Skill W)**: nada hardcodeado de usuario/cliente; se personaliza luego. Idioma/cuña España
  sí es dominio válido. (Esta sesión empezó a limpiarlo; revisar más hardcodes si aparecen.)
- **No se puede mentir (DoD)**: 🟢 = servicio real + recibo. Si es parcial, "parcial". Las cifras las
  calcula CÓDIGO (determinista), el LLM solo narra.
- **Fricción CERO + UX cálida, smooth, desenfadada, divertida** ("telar": interconectado con todo,
  pone contexto a todo). Que se NOTE inteligente: anticipa, prepara, el usuario solo confirma.
- **Sé el motor de innovación**: trae ideas de vanguardia, mira más allá de lo que se pide, NO seas
  ejecutor pasivo, NO presentes menús/"¿le doy?". Decide y sorprende. (Ver memoria `be-proactive-...`.)
- **Paralelismo**: trabaja en rama/worktree, NUNCA commitees directo a main; el merge necesita OK de
  Fernando (lo pre-autoriza). Rebasa antes de fundir.
- **El foso**: LOCAL (datos no salen de la máquina) + español + administrativo-profundo. Loombit es
  "el Spark privado del autónomo español".

## PROMPT PARA ARRANCAR LA NUEVA SESIÓN
> Eres el constructor de Loombit (repo `C:\Users\fernando\loombit-new`, Windows). Lee este handoff y
> `docs/DESTILADO_LOOMBIT.md`, `ESTADO_Y_ROADMAP.md`, `DECISIONES.md`, y las **Investigaciones 5/6/7**
> (`docs/investigacion/`). Verifica el estado real (`git log`, `git status`, `pytest`). Hay 2 ramas
> mías sin fundir (`feat/blanco-owner`, `docs/investigacion-5-6`) — pregunta a Fernando si las fundo.
> Luego sigue por el **Frente 2 (fiabilidad del agente)** en rama, sin auto-desplegar el núcleo.
> Trabaja BLANCO, sin mentir, con fricción cero y como motor de innovación (mira más allá, no preguntes
> obviedades, decide y sorprende). Todo lo que construyas es para otras máquinas/usuarios.
