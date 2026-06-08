# Routines de Loombit — diseño y traspaso desde Claude Code

> Objetivo: dar a Loombit **agentes proactivos programados** (como las "Routines" de
> Claude Code: Briefing, Email triage, Health check…) traspasando su **operativa, su
> sabiduría de diseño, la implementación y la solidez** — sobre el código que Loombit ya
> tiene, y respetando la regla nº1 (nada es 🟢 sin ejecución real con recibo).
> *Generado: 2026-06-08. Fases objetivo: 2 (proactividad) y 5 (scheduler/daemon).*

Esto **no es una feature nueva pegada con celo**: es la *columna vertebral* que ya implican
la Fase 2 (morning brief), la Fase 5 (daemon proactivo), el semáforo de confianza (#2) y el
brief de 5 líneas (#4). Una rutina = un agente con disparador, alcance y entrega.

---

## 1. Cómo lo hace Claude Code (el modelo observable → la sabiduría)

Una Routine de Claude Code es la composición de cinco cosas:

```
Routine = { disparador, objetivo(prompt), conectores con alcance, entrega, estado }
```

**Dos tipos de disparador:**
- **Tiempo (cron):** "weekdays at 14:30 CEST", "daily at 14:00", "every lunes 18:00" — con zona horaria.
- **Evento:** "Activado por pull request closed" — webhook/trigger ante un suceso externo.

**Siete principios de diseño que hay que copiar (la sabiduría):**
1. **Separar el disparador del trabajo.** Un mismo ejecutor (el agente) sirve para N rutinas; el cron/evento solo decide *cuándo*.
2. **Plantilla primero.** Se ofrecen rutinas pre-hechas (Briefing, Email triage…) para no obligar a diseñar desde cero.
3. **Preparar, no disparar (human-in-the-loop por defecto).** El triage *clasifica y redacta borradores*; no envía. El operador aprueba lo que sale al exterior.
4. **Alcance mínimo de capacidad.** Cada rutina declara solo los conectores que necesita (Gmail, Calendar, Slack…). Mínimo privilegio.
5. **Idempotencia + cursor de estado.** La rutina recuerda qué ya procesó (último email, último timestamp) para no duplicar en cada ejecución.
6. **Recibo + observabilidad.** Cada ejecución deja rastro auditable (corrió / falló / qué hizo). Se *ve* que corrió.
7. **Fallo ruidoso.** Una ejecución que falla avisa y no muere en silencio; reintentos acotados.

---

## 2. Diseño para Loombit (sobre el código que ya existe)

### 2.1 Modelo `Routine` (nuevo — primitiva de núcleo blanco)
`loombit_operator/routines.py` (<400 líneas), persistido en `runtime/local/routines.json`:

```
Routine:
  id, name, enabled
  trigger: { type: "cron"|"event", cron: "0 8 * * 1-5", tz: "Europe/Madrid", event: "<nombre>" }
  objective: prompt/spec del trabajo (o referencia a skill + params)
  scope: { connectors: [...], tools: [...] }        # mínimo privilegio
  delivery: { output: "brief"|"draft"|"notice",
              safety: SkillSafetyClass }             # semáforo (#2)
  state: { last_run, cursor }                        # idempotencia
```

### 2.2 Scheduler (`loombit_operator/scheduler.py`)
- Bucle de fondo arrancado por `launcher.py` (junto a uvicorn/bandeja). **APScheduler** (cron + tz, robusto) o tick `asyncio`+`croniter` si se quiere cero-dependencia.
- Al dispararse una rutina → crea un **`LMJob`/`AgentRun`** → ejecuta el **agente** con el *scope* de la rutina → produce resultado → escribe **recibo** en `runtime/local/` → aplica **semáforo**:
  - `PASSIVE` → se auto-completa (archivar, clasificar).
  - `ASSISTED`/`SAFETY_SENSITIVE` → crea un `AgentRun` en `PENDING_APPROVAL` (estado que **ya existe**) y lo muestra en la UI para 1-toque.
- **Disparador por evento:** endpoint webhook en `routers/routines.py` al que postean sucesos (watcher local de carpeta, o futuras integraciones).

### 2.3 Reutilización — lo que NO hay que reinventar (la solidez)

| Pieza de Claude Code | Pieza de Loombit que ya existe | Estado |
|---|---|---|
| Ejecución del agente | `agent/loop.py` (ReAct) | ✅ |
| Ciclo de vida del trabajo | `lm_jobs.py` (PENDING/RUNNING/COMPLETED/FAILED, persistido) | 🟡 (falta cablear a router+llm) |
| Human-in-the-loop | `AgentRun` `PENDING_APPROVAL`/`PENDING_QUESTION` | ✅ |
| Gate "solo/aprobación/firma" | `SkillSafetyClass` (`skills.py`) | ✅ (sin cablear) |
| Recibos / observabilidad | `runtime/local/` (patrón DoD del correo 🟢) | ✅ |
| Conectores con alcance | `tools/connectors.py` (gmail, calendar…) | 🟡/🟢 |
| Estado/cursor + aprendizaje | `EntityProfile` / `agent/memory.py` | 🟡 |
| Arranque del daemon | `launcher.py` (bandeja + uvicorn) | ✅ |

**Lo único nuevo de fondo: el scheduler + el modelo `Routine`.** Todo lo demás se ensambla.

---

## 3. Plantillas a enviar (mapeo CC → dominio Loombit)

| Plantilla Claude Code | Equivalente Loombit | Conectores | Entrega |
|---|---|---|---|
| Briefing | **Brief diario** (Fase 2, formato 5 líneas #4) | Gmail+Calendar (lectura) + cobros/conciliación (#1) | brief, PASSIVE |
| Email triage | **Triage de correo** (clasifica + borradores urgentes) | Gmail | draft, ASSISTED |
| System health check | **Radar de cobros/vencimientos** (facturas vencidas → recordatorio) | banco + dunning (#1) | draft, ASSISTED |
| Issue triage | **Radar de plazos fiscales / Sede** (303, notificaciones) | Sede/DEH (#5, Fase 6) | notice, SAFETY_SENSITIVE |
| Dependency update check | **Radar de contratos recurrentes** (#9, seguros/suscripciones) | banco | notice, ASSISTED |
| Release notes drafter (evento) | **Acción al cerrar un trato/pedido** (genera factura borrador) | — | draft, ASSISTED |

---

## 4. Solidez / DoD (cuándo una rutina es 🟢)

Una rutina está 🟢 **solo** cuando: ha disparado en su horario real, ha hecho trabajo real
contra el servicio real, ha dejado **recibo** auditable, y la **ruta de fallo bloquea limpio**.
Checklist de robustez (la solidez a traspasar):
- **Idempotencia** por `cursor` (no reprocesar lo ya hecho).
- **Cron con zona horaria** correcta (Europe/Madrid).
- **Recibo por ejecución** (corrió / falló / saltó-sin-cambios) en `runtime/local/`.
- **Fallo ruidoso** + reintentos acotados; nunca morir en silencio.
- **Mínimo privilegio** de conectores por rutina.
- **Human-in-the-loop por defecto** (sin acción externa sin aprobación) vía semáforo.

---

## 5. Mapa a fases

- **Fase 2:** scheduler MVP (cron) + plantilla **Brief diario** → cierra el "morning brief".
- **Fase 5:** daemon completo (el criterio de salida es *"scheduler/daemon proactivo"*) + plantillas que aprenden (#7).
- **Fase 6:** disparadores por evento + rutina **Sede/DEH** (#5) + gates de consentimiento.

---

## 6. Primer corte vertical — ✅ IMPLEMENTADO y verificado (2026-06-08)

Implementado en `routines.py` + `scheduler.py` + `routers/routines.py` (+ daemon opt-in y
`lifespan` en `main.py`), con **15 tests** y **ejecución real verificada contra el 14B** (el
Brief diario generó un brief real vía `POST /routines/{id}/run`, recibo en `runtime/local/`).
Lo más pequeño que demostró el patrón completo de punta a punta:

1. `Routine` (modelo + store JSON) + cablear `lm_jobs` al `llm.py` real.
2. `scheduler.py` con **una** rutina cron: **Brief diario** a las 08:00 Europe/Madrid.
3. Ejecuta vía `agent/loop.py`, produce el **brief de 5 líneas** (#4), escribe **recibo** en `runtime/local/`.
4. Semáforo: el brief es PASSIVE (solo informa); si propone una acción, va a `PENDING_APPROVAL`.
5. **DoD 🟢:** el scheduler dispara solo a su hora, genera un brief real con datos reales y deja recibo; matar el proceso y reiniciar no duplica (idempotencia por cursor).

Esto valida scheduler + modelo + ejecución + recibo + semáforo de una vez, y deja el raíl
montado para las demás plantillas.
