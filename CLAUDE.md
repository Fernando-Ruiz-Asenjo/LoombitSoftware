# CLAUDE.md — Contexto de proyecto para agentes de código

> Este fichero es la fuente de verdad para cualquier agente de IA (Claude Code,
> Copilot, Codex, etc.) que trabaje en este repositorio. Léelo entero antes de
> tocar código. Si contradice lo que crees saber, este fichero manda.

---

## Qué es Loombit

**Loombit Operator** es un runtime de operador de IA local-first. Teje contexto,
memoria y acciones en el mundo real. El núcleo es **blanco y reutilizable**; el
comportamiento de dominio vive en **skills instalables**. El mismo binario puede
ser operador de oficina, auditor industrial o cerebro de robótica según las
skills y el hardware instalados.

- Desarrollo: Windows + WSL + Docker.
- Despliegue objetivo: NVIDIA Jetson Orin NX 16GB.
- LLM local: Qwen2.5-7B-Instruct (rol `instructor`) + Qwen2.5-Coder-7B (rol `coder`) vía LM Studio / llama.cpp.

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

### Qué NO tocar ahora
- Industrial, inspección, rover, acuático, deportes → están en `docs/PARKED.md`.
- Fine-tuning de pesos de modelos → fuera de alcance, el aprendizaje es memoria operativa.
- Jetson benchmark → requiere comprar hardware; no bloquea el resto.

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
| Runtime | FastAPI + Python 3.10+ |
| Settings | Pydantic Settings |
| LLM local (instructor) | Qwen2.5-7B-Instruct-1M vía LM Studio |
| LLM local (coder) | Qwen2.5-Coder-7B-Instruct vía LM Studio |
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
| `docs/OBJETIVOS_GLOBALES_LOOMBIT.md` | Visión completa, cuñas de mercado, fases, pendientes |
| `docs/PLAN_MAESTRO_100.md` | Hoja de ruta detallada hacia 100% operatividad + autonomía |
| `docs/DEFINITION_OF_DONE.md` | Qué significa "hecho". Obligatorio antes de cualquier PR |
| `docs/CAPACIDADES_Y_HERRAMIENTAS.md` | Con qué construimos cada fase |
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
| Gmail send | 🟡 fake-tested | OAuth local implementado pero no probado contra cuenta real |
| Google Calendar create | 🟡 fake-tested | Ídem |
| Microsoft Graph sendMail | 🟡 fake-tested | Ídem |
| Microsoft Graph createEvent | 🟡 fake-tested | Ídem |
| Outbox local (.eml) | 🟢 | Sin credenciales cloud |
| Calendario local (.ics) | 🟢 | Sin credenciales cloud |
| Gmail read-only | ⬜ pendiente | No implementado |
| Outlook read-only | ⬜ pendiente | No implementado |
| Calendar read-only | ⬜ pendiente | No implementado |
| Google Contacts | ⬜ pendiente | No implementado |

El objetivo inmediato es llevar Gmail send y Google Calendar create de 🟡 a 🟢.

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

Es la skill de dominio principal activa. Su backend está completo (checkpoint 75 en el
repo anterior). Los módulos clave que ya existen:

- `skill_blanca_connector_execution.py` — ejecución de conectores controlada.
- `skill_blanca_oauth.py` — OAuth local Google/Microsoft.
- `skill_blanca_operational_config.py` — config operativa.
- `lm_jobs.py` / `llm.py` — cola de LM jobs y cliente LLM.
- `skill_loader.py` — cargador de manifests.

Al migrar código del repo anterior, marcar siempre el estado real (🟡/🟠/🟢).
No migrar el `main.py` monolítico (2674 líneas): repartir en `routers/` por dominio.

---

## Lo que nunca hace este operador (sin excepción)

- Ejecutar una acción externa sin aprobación explícita del humano.
- Subir datos del usuario a la nube sin consentimiento.
- Marcar una capacidad como 🟢 sin recibo de ejecución real.
- Fine-tuning de pesos de modelos.
- Movimiento físico autónomo (rover, robótica) en producción.
