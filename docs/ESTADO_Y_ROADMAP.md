# Estado y roadmap de Loombit — ¿cómo vamos?

> Documento vivo. Honestidad obligatoria (`DEFINITION_OF_DONE.md`): 🟢 = funciona
> contra el servicio/realidad con recibo; 🟡 = código completo + tests (sin piloto
> real); 🟠 = parcial; ⬜ = pendiente; 🔴 = bloqueado.
> Actualizado: 2026-06-08.

## Foto global
- **Repo**: limpio y profesional, historial sano, LICENSE propietaria, `.gitignore`/`.gitattributes`.
- **CI**: verde (black + ruff + pytest). **115 tests**.
- **Arquitectura**: núcleo blanco + skills + ReAct; FastAPI en `:8787`; LLM local (Qwen vía LM Studio).

## Avance por fases

| Fase | Objetivo | Estado | Qué falta para cerrarla |
|---|---|---|---|
| 0 · Fundación limpia | Repo, CI, estructura | ✅ Cerrada | — |
| 1 · Verdad de conectores | OAuth real Google + 1 correo + 1 evento reales | 🔴 Bloqueada (#28) | Crear cliente "App de escritorio" en Google Console (Fernando) + piloto real con recibo |
| 2 · Percepción real (Morning Brief) | Brief diario con datos reales | 🟠 En curso | Store de cuentas a cobrar + servicio de brief (las 3 piezas base ya están) |
| 3 · Bucle e2e cuña 1 (cobros) | Flujo cobros completo ×5 sin intervención | 🟠 Cerebro listo | Orquestación e2e + recibos 🟢 |
| 4 · UI humana | Dashboard no técnico | 🟠 Parcial | Home + botón Conectar Google hechos; falta dashboard |
| 5 · Memoria y aprendizaje | Daemon de memoria proactiva | 🟡 Memoria lista | Scheduler/daemon proactivo |
| 6 · Endurecimiento + navegador | Consentimiento, export, Skill Pilot navegador | ⬜ | Adaptador Playwright/CDP, contrato de coordenadas |
| 7 · Edge / Jetson | Benchmark en Jetson Orin NX | ⬜ | Comprar hardware |

## Conectores (estado honesto)

| Conector | Estado |
|---|---|
| OAuth Google (flujo escritorio: PKCE, auto-refresh, token cifrado, botón home) | 🟡 código; 🟢 cifrado verificado en Windows |
| Gmail send / Calendar create | 🟡 (pendiente piloto real → Fase 1) |
| Outbox local (.eml) / Calendario local (.ics) | 🟢 |

## Adopción de tendencias IA 2025-2026 (ver `ROADMAP_TENDENCIAS_IA.md`)

| # | Tendencia | Estado |
|---|---|---|
| 1 | Proactividad (morning brief) | 🟠 cerebro de cobros listo; falta el brief |
| 3 | Memoria de empresa (`EntityProfile`) | 🟡 hecho (IBANs, pago, incidencias, **gate antifraude**) |
| 4 | Inteligencia documental (facturas) | 🟡 hecho (extractor + endpoint + tool, cruce albarán) |
| 6 | Computer Use / Pilot | 🟡 reforzado (DPI, UIA accesibilidad-primero, gates) |
| 8 | Qwen2.5-VL (escaneados) | ⬜ pendiente (modelo) |
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
1. **Morning Brief + store de cuentas a cobrar** (cierra el MVP de Fase 2). *(siguiente)*
2. **Piloto real de cobros** end-to-end → primer recibo 🟢 (necesita LM Studio + datos).
3. **Desbloquear #28** (Fernando: cliente escritorio en Google Console) → Fase 1 🟢.
4. Qwen2.5-VL local (facturas escaneadas), servidor MCP, adaptador navegador.
5. Convertir el banco de supuestos S-01…S-15 en **tests de comportamiento**.

## Bloqueadores / dependen de Fernando
- **#28**: crear el cliente OAuth "App de escritorio" en Google Console y pasar el `client_id`.
- **LM Studio** corriendo para probar el agente de punta a punta.
