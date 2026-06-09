# Estado del arte de skills/herramientas vs. Loombit — análisis de huecos e implementación

> Destilado y fusión de un barrido amplio (2026-06-08) de asistentes/agentes de IA: correo, asistente
> ejecutivo/agenda, contabilidad/AP, software autónomos España, IA local/privada, OCR de documentos,
> MCP/Agent Skills y computer-use/RPA. Cruzado contra lo que Loombit **tiene de verdad** (módulos del
> repo, no notas). Objetivo: ver el mapa completo, dónde estamos fuertes, dónde hay hueco, y cómo
> cerrarlo — siempre desde el foso: **local · español · administrativo profundo · cognición**.
> Mantener vivo (regla 0 de la brújula: mejóralo).

## 1. Mapa de capacidades (estado del arte → Loombit)

Leyenda Loombit: ✅ sólido · 🟡 parcial/empezado · ❌ no existe.

| Familia | Qué hace el estado del arte (fusión) | Loombit hoy (módulo) | Hueco |
|---|---|---|---|
| **Percepción / triaje** | Triaje por prioridad (Importante/Notif/Marketing), silenciar ruido (SaneBox), comprensión de hilos, extracción de tareas, urgencia/sentimiento | ✅ `comprension.py` (cognición tipada con estado/importancia/acción); ✅ `telar.py` | 🟡 silenciar/archivar ruido automático; clasificación persistente con etiquetas |
| **Memoria / RAG** | RAG **local** sobre tu histórico (PyGPT, LocalAI+ES, LM Studio+RAG) — base de "buscar en todo", estilo, procedencia | ✅ memoria operativa (`agent/memory.py`); 🟡 galaxia/intel | ❌ **índice semántico local + RAG** sobre correos/docs/histórico — falta la pieza fundacional |
| **Redacción / acción** | Borradores a un clic, **redacción en TU voz** (aprende del "Enviados"), composición con procedencia | ✅ borrador + firma como usuario (`reply-watch`, `gmail_send` con gate); 🟡 procedencia (fiscal cita BOE) | ❌ **estilo propio** (aprender tu voz); aplicar procedencia a respuestas |
| **Agenda / scheduling** | Auto-schedule, defender focus, resolver conflictos, prep de briefing, follow-ups, send-time | 🟡 leer calendario + crear evento con gate (`skill_blanca_calendar*`); ✅ reconciliación correo×calendario (`comprension`) | ❌ scheduling inteligente, detectar/avisar conflictos, defender focus, recordatorios de salida |
| **Finanzas — cobros** | Seguimiento de morosos, intereses | ✅ **`cobros.py`+`tipos_demora.py` (Ley 3/2004, interés BCE+8, único y local)** | 🟡 `Banca N43` + lazo factura→cobro a 🟢 |
| **Finanzas — intake/contab.** | OCR factura (header 97%, **line-items lo difícil**, CV+LLM), three-way matching, GL coding, conciliación bancaria | 🟡 `docs_intel_vision.py` (Qwen-VL, falta cargar/verificar), `conciliacion.py`, `skill_d_fiscal/intake.py` | ❌ line-items robustos; ❌ matching factura↔cobro↔banco; ❌ codificación contable |
| **Finanzas — fiscal ES** | Asistente IVA/IRPF español (renn), modelos, **VeriFactu emisión** (obligatorio, multa 50k€) | 🟡 `skill_d_fiscal/modelo_303.py`; 🟡 `expedientes.py` (base VeriFactu) | ❌ **VeriFactu emisión conforme**; 130/111/115; calendario fiscal (✅ en telar) |
| **Privacidad / local** | Local hosting, datos no salen, memoria persistente (Jan.ai, AutonoTools offline) | ✅ **todo local** (Qwen vía LM Studio), ✅ memoria, ✅ tokens cifrados | ❌ el RAG local (arriba); convertir "local" en **bandera/sello visible** |
| **Acción en el mundo** | Computer-use/browser (Simular, Qwen agentic CU, Comet), RPA+agente juntos | 🟡 **Pilot** (`tools/pilot.py`, `routers/computer.py`, UIA, DPI, tecleo Unicode) | ❌ adapter de navegador (Playwright/CDP) + verificación en escritorio real |
| **Interoperabilidad** | **MCP** (10k+ servers, estándar Linux Foundation), **Agent Skills** (estándar abierto Anthropic) | ✅ Loombit **expone** MCP (`mcp_server.py`); ✅ skills propias (`skills.py`/`skill_loader.py`) | ❌ Loombit como **MCP client** (consumir 10k servers); 🟡 compat con el estándar Agent Skills |
| **Proactividad** | Brief de la mañana, sugerencias y follow-ups sin pedir | ✅ `telar.py` + `routines.py`/`scheduler.py` + `comprension` | 🟡 routines proactivas reales (cobros, tech-radar, VeriFactu-reloj) |

## 2. Lectura fusionada — dónde estamos y dónde no

- **Lo que YA es nuestro foso (y nadie cloud puede igualar):** cognición local de la bandeja + cobros
  Ley 3/2004 + todo local + el Pilot que opera apps sin API. Eso no lo tiene Holded/Quipu (cloud,
  sin cognición) ni los del barrido (inglés, genéricos). **AutonoTools** (iOS, offline) es el único que
  comparte el ángulo local — pero es pasivo (no agente, no cognición).
- **El hueco fundacional #1 es el RAG/índice semántico local.** Es la pieza que TODOS tienen y nosotros
  no, y la que **desbloquea varias cosas**: buscar en todo tu histórico, redacción con tu voz, procedencia,
  y la memoria del galaxia. Construirlo local = foso (RAG privado sobre TUS datos).
- **El hueco de mayor "se nota" es el día gestionado:** encadenar la comprensión en acción (agenda
  inteligente + rutas + recordatorios + prep). Cruza skills que ya tenemos.
- **El hueco que es dinero/ley es el fiscal:** VeriFactu emisión (reloj 2027, multa 50k€) + intake de
  line-items + conciliación a 🟢. Es la cuña.
- **El hueco de apalancamiento es la interoperabilidad:** ser **MCP client** nos da 10k integraciones
  gratis; alinear con **Agent Skills** estándar hace nuestras skills portables.

## 3. Plan de implementación (prioridad por foso × esfuerzo)

| Prio | Qué | Por qué | Cómo (cruzando lo que hay) |
|---|---|---|---|
| **P1** | **Índice semántico + RAG local** | pieza fundacional; desbloquea estilo, búsqueda y procedencia; foso (privado) | embeddings locales (LM Studio) sobre correos/docs/memoria → store vectorial local; API `recordar(query)`; lo consumen `comprension`, galaxia y el agente |
| **P1** | **El "día gestionado"** (E5 del radar) | lo más diferencial y visible; cruza 4 skills | `comprension`(reunión) → **Skill A Rutas (Maps)** → "sal a las 8:15" → recordatorio (calendar) → prep del hilo. Empezar por el caso David |
| **P2** | **Fiscal a 🟢:** VeriFactu emisión + intake line-items + conciliación | la cuña, reloj legal 2027, multa 50k€ | cargar el Qwen-VL en `docs_intel_vision`; `expedientes.py`→emisión VeriFactu (QR+hash); `Banca N43`→lazo factura↔cobro↔banco |
| **P2** | **Estilo propio** (redacción en tu voz) | iguala lo que todos venden, pero local | RAG (P1) sobre tu "Enviados" → few-shot de estilo en `gmail_send`/reply-watch |
| **P3** | **Loombit MCP client** | 10k integraciones gratis sin construirlas | cliente MCP que registra tools externas en `tools/registry`; gate de aprobación intacto |
| **P3** | **Compat Agent Skills** (estándar) | skills portables; subirse al estándar de facto | mapear `skill_loader` a folders de instrucciones del estándar |
| **P3** | **Pilot real** | foso "opera sin API" para la cola larga (sedes, bancos sin API) | adapter navegador (Playwright/CDP) + contrato de escalado de coords + verificación real |
| **P3** | **Routines vivas** | proactividad de verdad (no docs muertos) | tech-radar (auto-barrido), reloj VeriFactu, perseguidor de cobros, mantener `tipos_demora` |

## 4. Conclusión

Loombit no va por detrás: tiene el **núcleo difícil** (cognición local + admin español + gate + Pilot)
que los grandes no pueden replicar con datos privados. Los huecos son sobre todo **(a)** la base de RAG
local que apalanca varias features, **(b)** encadenar comprensión→acción (día gestionado), **(c)** cerrar
la cuña fiscal (VeriFactu/intake/conciliación), y **(d)** interoperar (MCP client + Agent Skills). El
orden P1→P3 ataca primero lo fundacional y lo más visible, sin dispersión.

*Fuentes (barrido 2026-06-08): Lindy/Motion/TeamCal (asistente ejecutivo) · Vic.ai/Zeni/Beancount
(contabilidad agéntica) · Holded/Quipu/Declarando/renn/AutonoTools (España) · Jan.ai/PyGPT/LocalAI
(IA local) · Rossum/Klippa/Veryfi (OCR) · Anthropic MCP + Agent Skills · Simular/Qwen CU (computer-use).
Ver también `RADAR_INNOVACION.md`.*
