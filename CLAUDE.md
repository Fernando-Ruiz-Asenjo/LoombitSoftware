# CLAUDE.md — Contexto de proyecto para agentes de código

> Este fichero es la fuente de verdad para cualquier agente de IA (Claude Code,
> Copilot, Codex, etc.) que trabaje en este repositorio. Léelo entero antes de
> tocar código. Si contradice lo que crees saber, este fichero manda.

---

## 🧭 BRÚJULA — normas que dirigen Loombit (aplícalas SIEMPRE, sin que haya que recordarlas)

> Doc canónico: `docs/BRUJULA.md`. Esto es el resumen que gobierna cada turno. Si dudas, vuelve aquí.

**0. Mejora lo que se te pide.** No te quedes en la orden literal: entiéndela, mejórala y ve más
allá. Si Fernando pide X, entrega X **mejor de lo que pidió**. Eres el motor, no un ejecutor.

**NORTE (qué es y para quién).** Loombit = el operador administrativo **privado** del autónomo/PYME
español. **Foso: LOCAL (los datos no salen de la máquina) · español · administrativo profundo.**
Hazlo igual o mejor que Google/los grandes; que sean más grandes NO es excusa.

**PRODUCTO (cómo entiende y trata al usuario).**
- **Cognición, no extracción.** Comprende los hilos: quién es quién, de qué va, en qué estado. De ahí
  derivan reuniones, notificaciones, plazos — con su contexto. No pesques un dato suelto.
- **Acierta al 100 %. NUNCA pidas al usuario que revise tu trabajo.** Si le pides que confirme o
  compruebe lo que tú deberías saber, has fallado. La confianza lo es TODO.
- **Cero fallos · fricción cero · UX cálida.** Anticipa y prepara; el usuario solo confirma efectos
  externos. Nada de menús pasivos ni "¿le doy?".
- **No mentir (DoD).** 🟢 = servicio real + recibo. Las cifras las calcula CÓDIGO determinista; el LLM
  comprende/narra. Si es parcial, di "parcial", con la lista de lo que falta.
- **Blanco (Skill W).** Nada hardcodeado de usuario/cliente; se personaliza luego.

**INGENIERÍA (cómo construir).**
- **Rama/worktree por cambio. Verifica EN VIVO antes de afirmar nada.** Tests + `black` + `ruff`
  verdes (el pre-commit gate los exige). El **núcleo del agente** se funde con OK de Fernando (lo
  pre-autoriza); **rebasa antes** de fundir.
- Ficheros < ~400 líneas; el dominio vive en skills/routers, no en el núcleo blanco. Una entrada en
  `docs/DECISIONES.md` por decisión. Verifica contra el CÓDIGO, no contra las notas.

**INNOVACIÓN (el motor, siempre encendido).**
- **Sé el motor de innovación.** Trae ideas de vanguardia, mira más allá de lo pedido, **cruza
  skills, experimenta, propón tools/skills nuevas**. Decide y sorprende.
- **El radar VIVE:** destila tendencias y competidores de verdad (no un doc muerto) y conviértelo en
  propuestas concretas para Loombit. Si algo se puede automatizar (una routine), automatízalo.

---

## Qué es Loombit

**Loombit Operator** es un runtime de operador de IA local-first. Teje contexto,
memoria y acciones en el mundo real. El núcleo es **blanco y reutilizable**; el
comportamiento de dominio vive en **skills instalables**. El mismo binario puede
ser operador de oficina, auditor industrial o cerebro de robótica según las
skills y el hardware instalados.

- Desarrollo: Windows + WSL + Docker.
- Despliegue objetivo: NVIDIA Jetson Orin NX 16GB.
- LLM local: Qwen2.5-14B-Instruct (rol `instructor`) + Qwen2.5-Coder-7B (rol `coder`)
  vía LM Studio en `http://localhost:1234/v1`.
- Servidor: FastAPI en `http://127.0.0.1:8787`. UI single-page en `loombit_operator/static/index.html`.
- Arranque: `python -m loombit_operator.launcher` (si el puerto 8787 está ocupado por una
  instancia vieja, matarla primero: `netstat -ano | findstr :8787` → `taskkill /PID <pid> /F`).

---

## Regla nº 1: no se puede mentir

**Una capacidad no está "hecha" sin una ejecución real contra el servicio real,
con recibo guardado.** Ver `docs/DEFINITION_OF_DONE.md`.

Estados de una capacidad:
- 🟡 Contrato (mock/fake-tested): el código compila y los tests con HTTP simulado pasan.
- 🟠 Parcial: funciona contra el servicio real solo bajo condiciones; lista explícita de lo que falta.
- 🟢 Hecho: funciona contra el servicio real, repetible, con recibo auditable.

Está **prohibido** marcar algo 🟢 sin cumplir el DoD. Si es parcial, se dice "parcial".

---

## Fase actual: Fase 1 — Verdad de conectores

Estamos en la **Fase 1**. La Fase 0 (fundación limpia) ya está cerrada.

### Qué hay que hacer en Fase 1
1. Crear el flujo OAuth local completo para Google:
   - `authorization-url` → callback → token store (redactado) → refresh → disconnect.
2. **Enviar 1 correo real** a una cuenta de prueba vía Gmail API.
3. **Crear 1 evento real** en Google Calendar.
4. Probar refresh de token y 3 rutas de fallo: token caducado, permiso faltante, destinatario inválido.
5. Guardar recibos 🟢 auditables de cada operación en `runtime/local/`.

**La Fase 1 está cerrada cuando existen recibos 🟢 de envío de correo y creación
de evento contra cuenta real, y la ruta de fallo bloquea limpio.**

> **✅ #28 resuelto (2026-06-08):** la app OAuth "App de escritorio" está creada en Google
> Cloud Console, la cuenta real está conectada y el token está cifrado en disco. **Gmail send
> ya está 🟢** (envío real verificado el 2026-06-07, recibo con `message_id`). **Calendar create
> también 🟢** (evento real 2026-06-08, `event_id` `vmovd103mbb40u7ek3ehb5jsa0`). **Fase 1 CERRADA.**

### Qué NO tocar ahora
- Industrial, inspección, rover, acuático, deportes → están en `docs/PARKED.md`.
- Fine-tuning de pesos de modelos → fuera de alcance, el aprendizaje es memoria operativa.
- Jetson benchmark → requiere comprar hardware; no bloquea el resto.

---

## Cuña de mercado activa

- **Mercado:** PYMES y autónomos en España.
- **Skill principal:** `Skill D Skill Blanca Administration` — Trabajo Administrativo General.
- **Primer flujo vertical (decide Fernando):** seguimiento de cobros **ó** intake de facturas.
- **Criterio de cierre:** operatividad y autonomía al 100 % en ese flujo antes de abrir la cuña 2.

Camino crítico sin dispersión: **Fase 1 → 2 → 3 → 4**.

## Estado real del repo (snapshot 2026-06-07)

Verificado contra el código, no contra notas previas:

- ✅ Repo limpio: historial profesional, LICENSE propietaria, CI verde
  (`black --check` + `ruff check` + `pytest`, 84 tests). Árbol sin cambios pendientes.
- ✅ **OAuth modo escritorio**: PKCE (S256), auto-refresh, token cifrado en reposo
  (keyring/DPAPI, 🟢 verificado en Windows), botón "Conectar Google" en el home.
  Pendiente 🟢: piloto real (cliente "App de escritorio" en Google Console + 1 envío real).
- ✅ **Skill W Pilot reforzada**: DPI-awareness (per-monitor v2), tecleo Unicode-seguro
  (acentos/€ vía portapapeles), `wait_for_window`/`click_accessibility`/`screen_changed`
  con endpoint + lógica + executor, y **accesibilidad-primero** (`ui_snapshot` UIA).
  El prompt del agente codifica la jerarquía API→navegador→UIA→coordenadas y los gates.
  Pendiente 🟢: verificación en escritorio real; pendiente build: adaptador de navegador
  (Playwright/CDP) y contrato de escalado de coordenadas.
- ✅ `lm_jobs.py`, `skills.py` y `skill_loader.py` migrados (🟡, unit-tested; sin montar en routers).

---

## Arquitectura — reglas obligatorias

```
loombit_operator/
├── main.py           ← solo crea la app y monta routers. NADA más.
├── routers/          ← un router por dominio (<400 líneas cada uno)
├── runtime/
│   └── local/        ← recibos JSON/HTML, token store, outbox .eml, .ics
└── skills/           ← manifests JSON de skills instalables
```

- `main.py` tiene un único trabajo: crear la app FastAPI y montar routers.
- Ningún fichero supera **~400 líneas**.
- El núcleo no contiene lógica de dominio vertical; eso va en skills o routers específicos.
- Credenciales y datos de cliente **fuera del repo**, siempre (`.env` / token store local).

---

## Stack técnico

| Capa | Tecnología |
|---|---|
| Runtime | FastAPI + uvicorn + httpx, Python 3.10+ |
| Servidor / UI | `http://127.0.0.1:8787` + single-page `static/index.html` |
| Settings | Pydantic Settings |
| LLM local (instructor) | Qwen2.5-14B-Instruct vía LM Studio (`http://localhost:1234/v1`) (fallback largo: Qwen2.5-7B-Instruct-1M) |
| LLM local (coder) | Qwen2.5-Coder-7B-Instruct vía LM Studio (`http://localhost:1234/v1`) |
| Conectores cloud | Google OAuth2 (Gmail, Calendar, Drive, People) |
| Conectores cloud | Microsoft Graph (Outlook, Calendar) |
| Outbox local | `.eml` + `.ics` (sin credenciales cloud) |
| Almacenamiento | JSON / JSONL local en `runtime/local/` |
| Tests | pytest + mocks HTTP para contratos 🟡 |
| CI | black + ruff + pytest en GitHub Actions |
| Despliegue edge | NVIDIA Jetson Orin NX + llama.cpp / llama-server |

---

## Documentos clave (leer antes de implementar)

| Documento | Para qué |
|---|---|
| `docs/DESTILADO_LOOMBIT.md` | **NORTE** — qué es Loombit, filosofía y operativa (el flywheel Skills×Routines×Fábrica); el único doc para entender el todo |
| `docs/OBJETIVOS_GLOBALES_LOOMBIT.md` | Visión original/histórica: cuñas de mercado, fases, pendientes |
| `docs/PLAN_MAESTRO_100.md` | Hoja de ruta detallada hacia 100% operatividad + autonomía |
| `docs/DEFINITION_OF_DONE.md` | Qué significa "hecho". Obligatorio antes de cualquier PR |
| `docs/CAPACIDADES_Y_HERRAMIENTAS.md` | Con qué construimos cada fase |
| `docs/CONOCIMIENTO_OFICIO_ADMINISTRATIVO.md` | Fuente de verdad de dominio: el oficio administrativo (España) y sus gates |
| `docs/DOMINIO_ADMINISTRATIVO_LOOMBIT.md` | Mapa completo del dominio admin: tareas, herramientas, supuestos A-H, capacidades PERCIBIR→APRENDER |
| `docs/BANCO_SUPUESTOS_LOOMBIT.md` | Banco de supuestos S-01…S-15 para exprimir al operador (futuros tests de comportamiento) |
| `docs/IA_TENDENCIAS_INSPIRACION_LOOMBIT.md` | Inspiración estratégica: tendencias IA 2025-2026 aplicadas a Loombit |
| `docs/ROADMAP_TENDENCIAS_IA.md` | Traducción de esas tendencias a trabajo de código concreto y orden de ataque |
| `docs/INSIGHTS_PRODUCTO_Y_SUPUESTOS.md` | Insights accionables: datos de mercado verificados, caso WhatsApp, supuestos sectoriales como tests de comportamiento, mapa de capacidades |
| `docs/MODELOS_LOOMBIT.md` | Inventario funcional de modelos locales (instructor 14B / coder / visión), mapeo a config, comandos de carga y estrategia de VRAM |
| `docs/INNOVACIONES.md` | Innovaciones aplicables de la investigación, mapeadas a fase, código existente y criterio DoD |
| `docs/ROUTINES_LOOMBIT.md` | Diseño del motor de agentes proactivos programados (cron/evento), traspaso desde las Routines de Claude Code sobre el código existente |
| `docs/SKILLS.md` | Taxonomía canónica de skills (C/W/G/D/A/X), precedencia, skills activas y familia Skill D |
| `docs/ARQUITECTURA_SKILLS.md` | Descomposición del dominio admin en familia de Skill D + Skill W Core + Skill A; las 3 capas (conocimiento/primitiva/conector) |
| `docs/PLATAFORMA_FISCAL_ANALISIS.md` | Análisis de arquitecto de la plataforma fiscal/administrativa (303 como entrada): encaje, datos, IA local, Sede/certificado, slice, gestoría, riesgos, oportunidades |
| `docs/DECISIONES.md` | Bitácora de decisiones de los bloques autónomos (con alternativas descartadas y reversibilidad) |
| `docs/FABRICA_DE_SKILLS.md` | Aprendizaje continuo y auto-autoría de skills (del proceso, del usuario, de internet); loop tipo skill-creator, local-first, con evals y procedencia |
| `docs/RADAR_INNOVACION.md` | Radar vivo de ideas de vanguardia mantenido proactivamente por Claude (+ futura routine tech-radar) |
| `docs/investigacion/INFORME_GLOBAL_TRABAJO_OFICINA.md` | Investigación global del trabajo de oficina: 15 roles, país por país, herramientas, supuestos I-X, mapa de capacidades |
| `docs/investigacion/OPERATIVA_PYMES_AUTONOMOS_ORDENADOR.md` | Operativa sector por sector de PYMEs/autónomos con el ordenador + ecosistema WhatsApp + supuestos A-G |
| `docs/investigacion/OPERATIVA_EN_PANTALLA_DIA_A_DIA.md` | Nivel pantalla: qué hace cada perfil con el ordenador, ciclo de cada documento, 5 niveles de capacidad de Loombit |
| `docs/OAUTH_GOOGLE_SETUP.md` | Guía paso a paso para conectar Google (Fase 1) |
| `docs/PARKED.md` | Qué está aparcado y no hay que tocar |
| `AGENTS.md` | Bucle de trabajo para agentes: cómo abrir rama, validar, hacer PR |

---

## Bucle de trabajo obligatorio

1. Partir de un objetivo documentado (issue o sección del plan).
2. Leer `docs/DEFINITION_OF_DONE.md` antes de tocar código.
3. Rama por cambio no trivial.
4. Cambios acotados al objetivo; no ampliar alcance.
5. Validar antes de dar por terminado: `black --check`, `ruff check`, `pytest`.
6. PR con: objetivo, ficheros cambiados, salida de tests, limitaciones conocidas, estado 🟡/🟠/🟢.
7. Si bloqueado, documentar el bloqueo. **No inventar ni marcar como hecho lo que no lo está.**

---

## Conectores de oficina — estado actual

| Conector | Estado | Notas |
|---|---|---|
| Gmail send | 🟢 **verificado** | Envío real a cuenta de prueba el 2026-06-07; recibo en `runtime/local/skill_blanca_connector_outbox/` (message_id `19ea478e791867b0`, respuesta API Gmail) |
| Google Calendar create | 🟢 **verificado** | Evento real creado el 2026-06-08 (`event_id` `vmovd103mbb40u7ek3ehb5jsa0`); recibo en `runtime/local/skill_blanca_connector_outbox/` |
| Microsoft Graph sendMail | 🟡 fake-tested | Ídem |
| Microsoft Graph createEvent | 🟡 fake-tested | Ídem |
| Outbox local (.eml) | 🟢 | Sin credenciales cloud |
| Calendario local (.ics) | 🟢 | Sin credenciales cloud |
| Gmail read-only | ⬜ pendiente | No implementado |
| Outlook read-only | ⬜ pendiente | No implementado |
| Calendar read-only | ⬜ pendiente | No implementado |
| Google Contacts | ⬜ pendiente | No implementado |

Gmail send 🟢 (2026-06-07) y Calendar create 🟢 (2026-06-08, `event_id` `vmovd103mbb40u7ek3ehb5jsa0`). **Fase 1 CERRADA** (envío de correo + creación de evento reales, con recibo).

---

## Taxonomía canónica de skills

Toda skill lleva un código de autoridad. Es obligatorio en títulos de hilo,
documentación, manifests y planificación. Ver `docs/SKILLS.md` para la fuente completa.

| Código | Nombre | Rol |
|---|---|---|
| `Skill C` | Canonical | Gobierna: nombrado, seguridad, estética, arquitectura de plataforma |
| `Skill W` | White Kernel | Núcleo limpio sin sesgo de dominio, sector ni cliente |
| `Skill G` | Golden Path | Flujo recomendado construido sobre C y W |
| `Skill D` | Domain | Especialización sectorial/comercial; depende de W, no lo contamina |
| `Skill A` | Adapter | Conector, bridge de hardware, proveedor, entorno |
| `Skill X` | Experimental | Lab/prototipo; no puede gobernar comportamiento estable |

Precedencia: `Skill C > Skill W > Skill G > Skill D > Skill A > Skill X`

### Skills activas con nombre canónico

| Nombre canónico | Alias de compatibilidad | Estado |
|---|---|---|
| `Skill C Loombit Skins` | — | Documenta reglas de diseño/UI/estética |
| `Skill W Loombit Coding` | Skill Coding Blanca | Núcleo limpio de trabajo de código |
| `Skill W Loombit Pilot` | Skill Pilot Blanca | Control local de escritorio, genérico y reutilizable |
| `Skill W Loombit Administration Core` | — | Primitivas admin neutras (a extraer cuando proceda) |
| `Skill D Skill Blanca Administration` | Skill Blanca Administracion | Trabajo administrativo de oficina — skill principal activa |
| `Skill A Google Workspace Connector` | — | Conector OAuth Google (Gmail, Calendar, Drive, People) |

Reglas:
- Un `Skill D` **no puede mover vocabulario ni lógica** al núcleo blanco.
- Un `Skill W` **no puede asumir sector, cliente ni rol** concreto.
- Un `Skill A` **debe ser reemplazable** sin cambiar el comportamiento por encima.
- Un `Skill X` **debe promoverse** antes de afectar comportamiento estable.

---

## Skill D Skill Blanca Administration — estado actual

Es la skill de dominio principal activa. Su backend estaba completo (checkpoint 75) en el
**repo anterior** `jetson-ai-operator`. Estado real de los módulos clave **en `loombit-new`**:

| Módulo | En loombit-new | Nota |
|---|---|---|
| `skill_blanca_oauth.py` | ✅ presente | OAuth local Google/Microsoft |
| `skill_blanca_gmail.py` | ✅ presente | Gmail send (🟡) |
| `skill_blanca_calendar.py` | ✅ presente | Calendar create (🟡) |
| `llm.py` | ✅ presente | Cliente LLM |
| `agent/memory.py` | ✅ presente | Memoria persistente entre sesiones |
| `lm_jobs.py` | ❌ pendiente migrar | Cola de LM jobs (en `jetson-ai-operator`) |
| `skill_loader.py` | ❌ pendiente migrar | Cargador de manifests (en `jetson-ai-operator`) |
| `skill_blanca_connector_execution.py` | ❌ pendiente migrar | Ejecución de conectores controlada |
| `skill_blanca_operational_config.py` | ❌ pendiente migrar | Config operativa |

Al migrar código del repo anterior, marcar siempre el estado real (🟡/🟠/🟢).
No migrar el `main.py` monolítico (2674 líneas): repartir en `routers/` por dominio.
Fuente de migración más reciente:
`C:\Users\fernando\Documents\Codex\2026-06-06\proyecto-jetson\jetson-ai-operator\jetson_operator\`.

---

## Lo que nunca hace este operador (sin excepción)

- Ejecutar una acción externa **autónoma/proactiva** sin aprobación del humano. (Matiz D-20: si el
  usuario PIDE la acción con parámetros inequívocos —p.ej. un correo a un destinatario claro—, su
  petición ES la autorización y se ejecuta sin tarjeta; lo ambiguo y lo proactivo sí se confirman.)
- Subir datos del usuario a la nube sin consentimiento.
- Marcar una capacidad como 🟢 sin recibo de ejecución real.
- Fine-tuning de pesos de modelos.
- Movimiento físico autónomo (rover, robótica) en producción.
