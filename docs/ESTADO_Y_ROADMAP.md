# Estado y roadmap de Loombit — ¿cómo vamos?

> Documento vivo. Honestidad obligatoria (`DEFINITION_OF_DONE.md`): 🟢 = funciona
> contra el servicio/realidad con recibo; 🟡 = código completo + tests (sin piloto
> real); 🟠 = parcial; ⬜ = pendiente; 🔴 = bloqueado.
> Actualizado: 2026-06-08.

## Foto global
- **Repo**: limpio y profesional, historial sano, LICENSE propietaria, `.gitignore`/`.gitattributes`.
- **CI**: verde (black + ruff + pytest). **138 tests**.
- **Arquitectura**: núcleo blanco + skills + ReAct; FastAPI en `:8787`; LLM local (instructor **Qwen2.5-14B**, coder 7B, vía LM Studio). Ver `MODELOS_LOOMBIT.md`.

## Avance por fases

| Fase | Objetivo | Estado | Qué falta para cerrarla |
|---|---|---|---|
| 0 · Fundación limpia | Repo, CI, estructura | ✅ Cerrada | — |
| 1 · Verdad de conectores | OAuth real Google + 1 correo + 1 evento reales | 🟠 Correo 🟢 enviado | #28 resuelto. Correo real enviado con recibo (`message_id` 19ea478e791867b0, 2026-06-07). Falta: crear 1 evento real (con recibo) |
| 2 · Percepción real (Morning Brief) | Brief diario con datos reales | 🟠 En curso | Store de cuentas a cobrar + servicio de brief (las 3 piezas base ya están) |
| 3 · Bucle e2e cuña 1 (cobros) | Flujo cobros completo ×5 sin intervención | 🟠 Cerebro listo | Orquestación e2e + recibos 🟢 |
| 4 · UI humana | Dashboard no técnico | 🟠 Parcial | Home + botón Conectar Google hechos; falta dashboard |
| 5 · Memoria y aprendizaje | Daemon de memoria proactiva | 🟡 Memoria lista | Scheduler/daemon proactivo |
| 6 · Endurecimiento + navegador | Consentimiento, export, Skill Pilot navegador | ⬜ | Adaptador Playwright/CDP, contrato de coordenadas |
| 7 · Edge / Jetson | Benchmark en Jetson Orin NX | ⬜ | Comprar hardware |

## Conectores (estado honesto)

| Conector | Estado |
|---|---|
| OAuth Google (escritorio: PKCE, auto-refresh, token cifrado, botón home) | 🟢 **CONECTADO con cuenta real (2026-06-08)**; token cifrado en disco; refresh presente |
| Gmail send | 🟢 **ENVÍO REAL VERIFICADO (2026-06-07)** — recibo en `runtime/local/skill_blanca_connector_outbox/` (`message_id` `19ea478e791867b0`, respuesta API Gmail) |
| Calendar create | 🟡 (ya conectado; falta el primer evento real con recibo) |
| Outbox local (.eml) / Calendario local (.ics) | 🟢 |

## Adopción de tendencias IA 2025-2026 (ver `ROADMAP_TENDENCIAS_IA.md`)

| # | Tendencia | Estado |
|---|---|---|
| 1 | Proactividad (morning brief) | 🟠 cerebro de cobros listo; falta el brief |
| 3 | Memoria de empresa (`EntityProfile`) | 🟡 hecho (IBANs, pago, incidencias, **gate antifraude**) |
| 4 | Inteligencia documental (facturas) | 🟡 hecho (extractor + endpoint + tool, cruce albarán) |
| 6 | Computer Use / Pilot | 🟡 reforzado (DPI, UIA accesibilidad-primero, gates) |
| 8 | Qwen2.5-VL (escaneados) | ⬜ pendiente (modelo descargado, **sin cablear**) |
| 5 | Servidor MCP | ⬜ pendiente |
| 7 | Voz (Whisper local) | ⬜ pendiente |
| 10 | VeriFactu, grafo temporal, A2A | ⬜ futuro |

## Lo construido en esta sesión
- **Saneado del repo**: historial reescrito, LICENSE, CI verde, deps Windows con markers.
- **OAuth escritorio**: PKCE, auto-refresh, **token cifrado** (keyring/DPAPI), botón "Conectar Google", guía.
- **Skill Pilot**: DPI-awareness, tecleo Unicode, `ui_snapshot` (UIA), 3 tools nuevas en executor, jerarquía + gates en el prompt.
- **Migración**: `lm_jobs`, `skills`, `skill_loader` del repo anterior.
- **Memoria de empresa** (`EntityProfile`) con gate antifraude de IBAN.
- **Inteligencia documental** (`docs_intel`) + endpoint `/docs-intel/invoice` + tool `read_invoice`.
- **Motor de cobros** (`cobros`, Ley 3/2004).
- **Docs de dominio** al repo: oficio administrativo, banco de supuestos, dominio, tendencias.

## Próximos pasos (orden sugerido)
1. **Crear 1 evento real en Calendar** → cierra la Fase 1 🟢 (mismo patrón que el correo; OAuth y recibos ya están). *(siguiente)*
2. ✅ **Swap del instructor a Qwen2.5-14B-Instruct (Q4_K_M)** — HECHO 2026-06-08, verificado contra la API real (genera asunto/cuerpo y llama a la tool sin preguntar). Ver `MODELOS_LOOMBIT.md`.
3. **WhatsApp como objetivo del Pilot** — canal de negocio real (92% lo usa a diario, 68% prefiere WhatsApp a email/teléfono). Ver `INSIGHTS_PRODUCTO_Y_SUPUESTOS.md`.
4. 🟢 **Routines: scheduler + Brief diario** — verificado end-to-end (2026-06-08): motor + cron + recibo + semáforo + 15 tests + brief real contra el 14B. **Falta**: cablear fuentes reales (banco/Gmail) al brief + store de cuentas a cobrar (cierra MVP Fase 2). Ver `ROUTINES_LOOMBIT.md`.
5. **Piloto real de cobros** end-to-end → primer recibo 🟢 (necesita LM Studio + datos).
6. Qwen2.5-VL local (facturas escaneadas), servidor MCP, adaptador navegador.
7. Convertir los supuestos (S-01…S-15 + los nuevos A-G/I-X de investigación de campo) en **tests de comportamiento**.

## Innovaciones acopladas por fase

Ideas de la investigación de campo integradas en el plan (detalle, código base, DoD y esfuerzo en `INNOVACIONES.md`):

| Fase | Innovaciones que la refuerzan |
|---|---|
| 2 · Morning Brief | #4 brief de 5 líneas (UX) ⭐ · #1 conciliación bancaria ⭐ · #8 velocidad de leads · #9 radar de contratos recurrentes |
| 3 · Cobros e2e | #1 conciliación bancaria ⭐ · #2 semáforo de confianza ⭐ · #3 captura única · #6 memoria temporal · #10 cruce factura/albarán + mutuas |
| 4 · UI humana | #4 brief de 5 líneas ⭐ · #2 semáforo de confianza (visible) |
| 5 · Memoria y aprendizaje | #6 memoria grafo temporal · #7 plantillas que aprenden (cierra el criterio de fase) |
| 6 · Endurecimiento + navegador/WhatsApp | #5 monitor Sede/DEH/Lexnet · #2 gates de consentimiento · WhatsApp Pilot |

**Secuencia recomendada:** primero los multiplicadores que reutilizan código ya escrito —
#4 + #1 + #2 (refuerzan Fases 2-3)— luego quick wins (#8, #9), y el resto por fase. ⭐ = meter primero.

## Plataforma fiscal (análisis — pendiente de decidir)

Análisis de arquitecto en `PLATAFORMA_FISCAL_ANALISIS.md`: el 303 como **caso de entrada** de un
**motor de expedientes oficiales** (Skill W) + **`Skill D Fiscal`** + memoria fiscal proactiva.
**Propuestas clave a validar por Fernando** (cambian el brief): liderar con *percibir y preparar*
(intake + conciliación + calendario + monitor DEH), no con *presentar*; diseñar para la
**gestoría** (multi-entidad → SQLite por entidad); el **email** como entrada real. Primer slice:
intake de factura + borrador de 303 (el humano presenta), cero riesgo legal.

## Bloqueadores / dependen de Fernando
- ~~**#28**: crear el cliente OAuth "App de escritorio"~~ → ✅ **RESUELTO** el 2026-06-08
  (creado vía Pilot/navegador; cuenta real conectada, token cifrado).
- **LM Studio** corriendo para probar el agente de punta a punta (en marcha).

> Aprendizaje clave: el alta del cliente OAuth + la conexión se hicieron conduciendo el
> navegador con los gates intactos (humano da el consentimiento, el operador no toca
> credenciales). Es el patrón que el **adaptador de navegador (Playwright/CDP)** debe
> replicar dentro del propio Pilot para webs (vuelos, banca, AEAT…).
