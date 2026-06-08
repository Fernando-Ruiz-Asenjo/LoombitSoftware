# Roadmap de implementación — Tendencias IA 2025-2026 → código

> Traduce `IA_TENDENCIAS_INSPIRACION_LOOMBIT.md` (inspiración estratégica) a trabajo de
> ingeniería concreto: qué construir, con qué tecnología, sobre qué módulo y en
> qué orden. Honestidad obligatoria (`DEFINITION_OF_DONE.md`): nada es 🟢 sin
> ejecución real con recibo.

## Principios que fija el documento
- **Proactivo, no reactivo**: el agente anticipa y prepara; el humano aprueba.
- **Multi-agente**: skills = agentes especializados; ReAct = orquestador. Ya es la arquitectura.
- **Privacidad estructural**: todo local. Es imposibilidad técnica de fuga, no una promesa.
- **Diferenciadores propios**: Skill Pilot (opera sin API), memoria de empresa, dominio fiscal español.

## Mapa tendencia → implementación

| # | Tendencia | Estado en Loombit | Solución técnica concreta | Prioridad |
|---|-----------|-------------------|---------------------------|-----------|
| 1 | Proactividad (morning brief, vencimientos) | ⬜ por construir | Servicio `briefing` que cruza facturas + vencimientos (Ley 3/2004) + agenda y emite alertas; scheduler en Fase 5 | Now |
| 2 | Multi-agente | ✅ arquitectura (skills + ReAct) | Separar explícitamente roles clasificador/extractor/redactor sobre `tools/registry` + `agent/loop` | Fase 3-4 |
| 3 | **Memoria de empresa** (el diferencial) | 🟠 `agent/memory.py` (episódica+procedural+contactos) | **Añadir `EntityProfile`**: perfil por empresa/NIF con IBANs conocidos, comportamiento de pago, incidencias, contactos, prefs. Base para cobros y gate antifraude IBAN | **Now (en curso)** |
| 4 | Inteligencia documental (facturas PDF) | ⬜ por construir | Módulo `docs_intel`: PDF→texto (pypdf/pdfplumber) + extractor de campos ES (nº, fecha, NIF, base, IVA, total, vencimiento, IBAN) + cruce factura/albarán. Visión con **Qwen2.5-VL local** para escaneados | Now |
| 5 | MCP (estándar de interoperabilidad) | ⬜ por construir | Exponer los conectores como **servidor MCP** (`mcp` SDK) para que Loombit hable con cualquier cliente MCP | Now |
| 6 | Computer Use / GUI agents | ✅ **Skill W Pilot** (DPI, UIA, accesibilidad-primero) | Pendiente: adaptador navegador (Playwright/CDP) + contrato de coordenadas + verificación post-acción | Fase 3-4 |
| 7 | Voz | ⬜ por construir | **Whisper local** (open source) para dictado/transcripción → tareas/eventos. Privado | Fase 3-4 |
| 8 | Modelos locales (SLM) | ✅ Qwen2.5-7B instructor + Coder | **Añadir Qwen2.5-VL-7B** para documentos escaneados (urgente para #4) | Now |
| 9 | Workflows | ✅ ventaja (Pilot + dominio + memoria) | Mantener el bucle completo dentro de Loombit; no depender de n8n/Zapier | — |
| 10 | Emergentes (auto-mejora, extended thinking, A2A, grafo temporal, VeriFactu, OCR-VL) | parcial (`proposals` ya capta carencias) | Grafo temporal estilo Graphiti sobre `EntityProfile`; VeriFactu XML+QR firmado; A2A vía MCP | Fase 5-6 |
| 11 | — | — | (mapa de adopción del propio documento) | — |
| 12 | Diferenciación | en construcción | Privacidad + dominio ES + Pilot + memoria de empresa + bucle completo | transversal |

## Orden de ataque (camino crítico, alineado con la cuña 1 = cobros)
1. **`EntityProfile` (memoria de empresa)** — base de cobros y del gate antifraude IBAN. *(en curso)*
2. **Document Intelligence** — leer la factura (nº, importe, vencimiento, IBAN) es la entrada del flujo de cobros.
3. **Briefing proactivo** — cruzar facturas + vencimientos → "facturas vencidas hoy".
4. **Qwen2.5-VL local** — para facturas escaneadas.
5. **Servidor MCP** — interoperabilidad y distribución.
6. Resto por fases (voz, navegador CDP, VeriFactu, grafo temporal, A2A).

Cada pieza es local, privada y testeable. La verificación 🟢 de cada flujo exige
ejecución real con recibo, según el DoD.
