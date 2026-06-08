# Objetivos Globales de Loombit
**Documento vivo — Fecha: 2026-06-07**
Fuente de verdad consolidada extraída de `jetson-ai-operator` y `loombit-operator`.
Honestidad obligatoria: nada marcado como "hecho" sin recibo real.

> **Nota (2026-06-08):** este documento es la **visión original**. El estado vivo (qué está 🟢/🟡)
> se lleva en `docs/ESTADO_Y_ROADMAP.md` y la síntesis actual en `docs/DESTILADO_LOOMBIT.md`.
> Algunas líneas de estado de abajo son históricas: hoy el OAuth está conectado, el **primer
> correo real está enviado 🟢** y el instructor es **Qwen2.5-14B**.

---

## 1. Misión central del producto

**Loombit Operator** es un runtime de operador de IA local-first que teje contexto, memoria y acciones en el mundo real. El mismo binario sirve como operador administrativo de oficina, auditor industrial, nodo de inspección o cerebro de robótica según las skills y el hardware instalados.

El núcleo es **blanco y reutilizable**. El comportamiento de dominio vive en **skills instalables**.

---

## 2. Las dos métricas de éxito (sin ambigüedad)

### 2.1 100% Operatividad
Cada capacidad anunciada funciona contra servicios reales (no mocks), verificada con recibo auditable. Cero capacidades 🟡 vendidas como 🟢.

### 2.2 100% Autonomía Supervisada
Para los flujos del alcance elegido, el operador recorre el bucle completo sin trabajo manual humano, pero con aprobación humana en toda acción externa:

```
PERCIBIR  →  PLANEAR  →  PREPARAR  →  PEDIR APROBACIÓN  →  EJECUTAR  →  RECIBO  →  APRENDER
```

"Supervisada" significa humano en el bucle en el paso EJECUTAR para todo efecto externo. La autonomía real está en PERCIBIR → PLANEAR → PREPARAR y en la anticipación.

---

## 3. Estrategia de producto: cuñas de mercado

La mayor lección del repo anterior fue la dispersión. El plan ahora sigue un orden estricto de cuñas.

### Cuña 1 — Operador Local de Oficina (ACTIVA — camino crítico)
**Mercado objetivo:** PYMES y autónomos en España.
**Skill principal:** Skill Blanca No. 1 — Trabajo Administrativo General.
**Primer flujo vertical a elegir (decisión pendiente de Fernando):**
- Seguimiento de cobros, o
- Intake de facturas

**Criterio de cierre de cuña 1:** operatividad y autonomía al 100% en ese flujo antes de abrir cuña 2.

### Cuña 2 — Loombit Edge Box / Industrial (APARCADA hasta cerrar cuña 1)
Una caja local, muchas skills. El mismo runtime sirve para:
- Auditor industrial de diagnóstico (primera skill monetizable).
- Inspección visual industrial.
- Monitor de sitio remoto.

### Cuñas opcionales (APARCADAS — sin fecha)
- Rover creador / asistente físico.
- Operaciones rurales y acuáticas (España vaciada, piscifactorías, riego, puertos).
- Asistente deportivo (fútbol, árbitro local, clips).
- ConstruIA Escudo (diferido hasta que Skill Blanca administrativa sea reutilizable).

---

## 4. Objetivos técnicos por área

### 4.1 Runtime y arquitectura
- Núcleo blanco: `main.py` solo monta routers; lógica de dominio en módulos.
- Ningún fichero supera ~400 líneas.
- CI con `black` + `ruff` + cobertura de tests en verde permanente.
- Despliegue final en **NVIDIA Jetson Orin NX 16GB**.
- Desarrollo en Windows + WSL + Docker.

### 4.2 Skill Blanca — Administración General (Fase activa)
- ActionPackage v0.2: validator, Action Inbox bridge, enrichment desde EvidenceGraph.
- CaseFile / Receipt / EvidenceGraph: persistencia local auditada.
- Bucle de autonomía supervisada completo (7 pasos) por cada flujo.
- Autonomía plan: decide prepare / block / ask por acción individual.
- Autonomía cycle: anticipa artefactos locales antes de la aprobación.
- Worker profile: perfil de patrones, bloqueadores y oportunidades de skill.
- Preferencias de operador aprendidas de decisiones accept / edit / cancel.
- Scheduler de autonomía local para rondas seguras recurrentes.
- Morning brief determinista: cola activa, foco, bloqueadores, readiness.
- Perfiles de contexto y plantillas candidatas desde patrones repetidos.
- Gates de calidad antes de promover plantillas; monitor de salud post-aprobación.
- Inteligencia de empresa: CompanyProfile, ServiceCatalog, RoleMap, SkillOpportunity.

### 4.3 Conectores de oficina
- **Gmail:** send real (OAuth Google) — 🟢 **verificado** (envío real 2026-06-07, recibo con message_id).
- **Google Calendar:** create event real — actualmente 🟡 fake-tested.
- **Microsoft Graph:** sendMail y createEvent — actualmente 🟡 fake-tested.
- **Gmail read-only:** pendiente.
- **Outlook / M365 read-only:** pendiente.
- **Google Drive:** búsqueda y lectura — pendiente de piloto real.
- **Google Contacts:** lookup de destinatarios por nombre — pendiente real.
- **Outbox local:** `.eml` + recibo JSON — 🟢 funciona sin credenciales cloud.
- **Calendario local:** `.ics` + recibo JSON — 🟢 funciona sin credenciales cloud.
- **SMTP real:** pendiente configuración y piloto.

**Objetivo OAuth:** app real en Google Cloud con scopes mínimos, flujo local completo (authorization-url → callback → token store → refresh → disconnect). 1 correo real enviado + 1 evento creado = Fase 1 cerrada.

### 4.4 Desktop Observer y Skill Pilot
- Desktop Observer: módulo genérico de observación local con consentimiento.
- Desktop Context Observer: metadatos de ventana/proceso sin capturas.
- Desktop Accessibility: inventario de controles UI Automation sin leer valores privados.
- App Context Router: mapea app observada a proveedor correcto antes del fallback por captura.
- Source Onboarding Draft: de contexto de app a perfil de fuente candidato.
- Skill Pilot: ejecutor de secuencias locales auditables (URL open, foco, clic, tipeo, hotkeys).
- Pendiente: adaptadores UI Automation para Chrome, Edge, Explorer, Outlook, Office, ERP/CRM.
- Pendiente: ejecutor y verificador de secuencias de navegador sobre Skill Pilot.

### 4.5 Modelos de lenguaje locales
- Rol `instructor`: Qwen2.5-14B-Instruct — razonamiento administrativo (fallback largo: Qwen2.5-7B-1M).
- Rol `coder`: Qwen2.5-Coder 7B — código, esquemas, tests.
- Cola de LM jobs persistente y auditable.
- Skill Coding Blanca: deliberación local de dos modelos con consensus validator.
- Sin fine-tuning de pesos; el aprendizaje es memoria operativa (casos, recibos, plantillas).
- Target hardware de inferencia edge: Jetson Orin NX con llama.cpp / llama-server.

### 4.6 Documentos y ficheros
- Organización de carpetas local con journal, rollback (deshacer) y recibos HTML.
- Auditor de contenido local: texto, DOCX, XLSX — señales de importes, fechas, VAT, emails, tareas.
- Ejecución de trabajo documental: copias de trabajo versionadas sin tocar el original.
- Pendiente: ingesta PDF/OCR, extracción estructurada de DOCX/XLSX, normalización de proveedores.

### 4.7 UI y dashboard
- Dashboard local sin JSON expuesto al usuario no técnico.
- Vista principal: "Pedir Trabajo", "Hacer Trabajo", resultado humano, estado traducido.
- Paneles técnicos (EvidenceGraph, ActionPackage, recibos) plegados bajo demanda.
- Filtros de casos: estado, fuente, texto.
- Registro de consentimiento con revocación de fuente en 1 clic.
- Objetivo Fase 4: usuario no técnico completa el flujo sin ver JSON.

### 4.8 Seguridad y privacidad
- Política de seguridad determinista: allow / warn / block / escalate.
- Gate de actor: bloquea preparación si contacto externo no verificado, conflicto, o decisor interno faltante.
- Sin subida a la nube por defecto.
- Sin acción irreversible sin aprobación explícita.
- Toda acción externa deja recibo local.
- Consentimiento explícito por fuente antes de cualquier lectura.
- Credenciales y datos de cliente fuera del repo, siempre.

---

## 5. Hoja de ruta por fases (loombit-operator)

| Fase | Objetivo | Criterio de salida |
|---|---|---|
| **0** Fundación limpia ✅ | Repo nuevo, CI verde, estructura de routers | `main.py` < 100 líneas, CI verde en `main` |
| **1** Verdad de conectores | OAuth real Google, 1 correo real, 1 evento real | Recibos 🟢 de envío y creación contra cuenta de prueba |
| **2** Percepción real (read-only) | Gmail + Calendar + Drive → morning brief real | Brief del día con datos reales y consentimiento explícito |
| **3** Bucle end-to-end cuña 1 | Flujo vertical completo × 5 sin intervención manual fuera de la aprobación | Recibos en cada paso, repetible |
| **4** UI humana | Dashboard sin JSON para usuario no técnico | Usuario no técnico completa el flujo sin ver JSON |
| **5** Memoria y aprendizaje | Daemon de memoria operativa recurrente | Daemon programado + propuesta de al menos 1 plantilla desde casos reales |
| **6** Endurecimiento + Skill Pilot navegador | Consentimiento, revoca, export de recibos, Skill Pilot verificado | Export de recibos, revoca en 1 clic, Skill Pilot completa tarea verificada |
| **7** Edge / Jetson | Benchmark real en Jetson Orin NX | Benchmark medido en la placa (requiere comprar hardware) |

**Orden crítico:** Fases 0→1→2→3→4 son el camino al producto vendible. Fases 5 y 6 endurecen. Fase 7 es paralela y depende de comprar hardware. No tocar 7 hasta cerrar 3.

---

## 6. Milestones completados (heredados de jetson-ai-operator)

- **M002** Core Runtime (FastAPI, settings, logging, health, monitor de sistema, tasks).
- **M003** Jetson Qwen Runtime (perfiles de hardware, GGUF, cliente llama.cpp/OpenAI-compat).
- **M004** Canonical Skill Foundation (registry en blanco, manifests, categorías, seguridad).
- **M005** Persistent Task Queue (almacenamiento JSON, máquina de estados, retry, API).
- **M006** Skill Loading (config de directorio, loader JSON, validación, reload sin ejecución dinámica).
- **M007** Sensors & Telemetry (contratos de eventos, JSONL persistente, heartbeat, adaptadores).
- **M008** Safety Policy (motor determinista, severidades, audit store, endpoints).
- **M009** Vision & Mobility (contratos de visión, bounding boxes, revisión de movimiento, sin ejecución autónoma).
- **M009B** Loombit Edge Box Strategy (identidad de producto clarificada, skill packs como unidad de dominio).
- **M010** Universal Product Profiles (manifest, validación en runtime, endpoints).
- **M010B/C/D** Live Roadmap Dashboard + Live Skill Tree + Skill Gap Planner.
- **M011** Industrial Edge AI Auditor (intake, scoring, report shape, sin autonomía).
- **M011B** Industrial Visual Inspection Pack.
- **M011B2** Base Connection Diagnostics.
- **M011C** Remote Site Monitor Pack.
- **M012** Jetson Deployment (guías JetPack/llama.cpp/Qwen, systemd, preflight endpoint; benchmark real pendiente).
- **M013** Operador Local de Oficina (Skill Blanca backend completo hasta checkpoint 75, dashboard, OAuth, conectores locales, Skill Pilot, aprendizaje operativo, company intelligence).

---

## 7. Pendiente prioritario (próximos pasos reales)

### Inmediato (desbloquea Fase 1)
- ✅ App OAuth real en Google Cloud creada y **cuenta conectada** (2026-06-08).
- ✅ **1 correo real enviado** con recibo 🟢 (message_id). Falta: 1 evento real en Calendar.
- Probar refresh de token y 3 rutas de fallo (token caducado, permiso faltante, destinatario inválido).

### Conectores read-only (Fase 2)
- Gmail read-only (hilos, etiquetas).
- Outlook / Microsoft 365 read-only.
- Calendar read-only (Google y Microsoft).
- Google Contacts: lookup por nombre de destinatario.

### Documentos (Fase 2-3)
- Ingesta PDF con OCR.
- Extracción estructurada de DOCX/XLSX (entidades, importes, fechas).
- Normalización de proveedores para el intake de facturas.

### UI (Fase 4)
- Reescritura producción del dashboard: resultado humano primero, detalles técnicos ocultos por defecto.
- Navegación por source-link desde el dashboard.
- Editor de reglas de organización más amigable.

### Skill Pilot y desktop (Fase 6)
- Adaptadores UI Automation por app: Chrome, Edge, Explorer, Outlook, Office, ERP/CRM frecuentes.
- Ejecutor y verificador de secuencias de navegador.
- Autofill local de perfil administrativo aprobado.

### Infraestructura
- Certificado de firma de código real + instalador firmado para pilotos Windows.
- Export de recibos de acción para todos los tipos de agente.
- Scheduler para tareas recurrentes de oficina.
- CI en ramas de feature.
- Política de retención de logs de runtime.

### Hardware (independiente, desbloquea Fase 7)
- Comprar Jetson Orin NX 16GB.
- Benchmark real: latencia, tok/s con llama.cpp + Qwen.

---

## 8. Riesgos y cómo los mitigamos

| Riesgo | Mitigación |
|---|---|
| Volver a la dispersión | `PARKED.md` + DoD bloquean alcance fuera de cuña 1 |
| "Hecho" falso | DoD exige recibo real en cada PR; emojis de estado obligatorios |
| Monolito | Límite de ~400 líneas/fichero; `main.py` solo monta routers |
| Fuga de datos de cliente | Consentimiento por fuente, todo local, secretos fuera del repo |
| Dependencia de un solo proveedor | Capa de conectores con modos local_outbox / SMTP / Google / Microsoft |
| Dispersión de modelos | Política de selección: instructor = Qwen 7B long-ctx, coder = Qwen Coder 7B |

---

## 9. Regla innegociable

> Una capacidad **no está "hecha"** sin una ejecución real contra un servicio real, con recibo guardado.
> Si es parcial, se dice "parcial". Sin adornos. (Ver `docs/DEFINITION_OF_DONE.md`)
