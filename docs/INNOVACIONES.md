# Innovaciones aplicables — de la investigación al roadmap

> Ideas extraídas de la investigación de campo (`docs/investigacion/`) y de las tendencias
> (`IA_TENDENCIAS_INSPIRACION_LOOMBIT.md`). Cada una está anclada a **un dato real**, al
> **código que ya existe**, a su **fase** y a un **criterio DoD** (cuándo pasa a 🟢).
> Honestidad obligatoria: esto son ideas priorizadas, **no** capacidades hechas.
> *Generado: 2026-06-08. Alcance: fases 1-6 (la 7/Jetson queda fuera por ahora).*

**Leyenda** — Esfuerzo: 🟢 bajo · 🟡 medio · 🔴 alto. ⭐ = meter primero.

---

## Multiplicadores de fuerza (cambian *cómo* se hacen las fases, alto apalancamiento)

### 1. ⭐ Extracto bancario como fuente de verdad → conciliación automática
- **Qué:** ingerir el extracto (PDF o PSD2) y conciliarlo contra las facturas emitidas → marcar cobradas/vencidas y detectar movimientos sin identificar.
- **Dato:** *"el extracto es el documento más fiable de un autónomo, no puede falsificarse"* (OPERATIVA_PYMES §2.3); frustración nº4 *"no sé en qué estado están las cosas"* (OPERATIVA_PANTALLA §6).
- **Construye sobre:** motor de cobros (`cobros`, dunning Ley 3/2004) + `docs_intel`.
- **Fase:** 2 (alimenta el brief) + 3 (cierra cobros).
- **DoD 🟢:** dado un extracto real + facturas, marca cobradas/vencidas con recibo y detecta ≥1 movimiento no identificado.
- **Esfuerzo:** 🟡 (variedad de formatos de banco). Alto valor.

### 2. ⭐ Semáforo de confianza (ya tienes el enum) → autonomía supervisada real
- **Qué:** clasificar **cada acción preparada** en niveles y solo interrumpir al humano en los que toca: archivar = automático; recordatorio = 1 toque; modelo fiscal = aprobación explícita.
- **Dato:** la **cadena de aprobaciones** del trabajador (OPERATIVA_PANTALLA §4.3).
- **Construye sobre:** `SkillSafetyClass` ya existe en `skills.py` (PASSIVE / ASSISTED / SAFETY_SENSITIVE / BLOCKED_BY_DEFAULT) + gates del `agent/loop.py`.
- **Fase:** transversal — ejecución (3), UI (4), consentimiento (6).
- **DoD 🟢:** cada acción lleva su clase y el loop solo pide aprobación en SAFETY_SENSITIVE+; verificado en 3 acciones reales.
- **Esfuerzo:** 🟡. Materializa la "autonomía supervisada" del CLAUDE.md.

### 3. Captura única → propaga a todos lados (anti-doble-entrada)
- **Qué:** un dato capturado una vez (NIF de un cliente nuevo) se propaga a plantilla de presupuesto, factura y ficha de cliente.
- **Dato:** frustración nº1 *"tengo que meter lo mismo en dos o tres sitios"* (OPERATIVA_PANTALLA §6).
- **Construye sobre:** `EntityProfile` (`agent/memory.py`).
- **Fase:** 3.
- **DoD 🟢:** capturar un cliente una vez → aparece sin re-teclear en presupuesto + factura + ficha.
- **Esfuerzo:** 🟡.

### 4. ⭐ El brief de 5 líneas como UX central (no un dashboard)
- **Qué:** la interfaz proactiva es lenguaje natural de ≤5 líneas con acciones de un toque, no un panel de métricas.
- **Dato:** Supuesto I pide literal *"un briefing de 5 líneas"* (INFORME §11); criterio de salida de la Fase 4: *"usuario no técnico completa el flujo sin ver JSON"*.
- **Construye sobre:** morning brief (Fase 2) + UI `static/index.html`.
- **Fase:** 2 (contenido) + 4 (forma).
- **DoD 🟢:** brief diario real en ≤5 líneas NL con acciones de 1 toque; un no-técnico lo entiende sin ver JSON.
- **Esfuerzo:** 🟢-🟡.

---

## Foso (lo que Zapier / n8n / ChatGPT no pueden copiar)

### 5. Monitor del buzón Sede/DEH/Lexnet con resumen en claro
- **Qué:** Skill Pilot vigila la Sede Electrónica / DEH / Lexnet; al llegar algo, lo resume en español llano, explica consecuencias y mete el plazo en el calendario.
- **Dato:** notificación de Hacienda que nadie ve (OPERATIVA_PYMES §6.4); supuestos E (Lexnet) y VI (auditoría).
- **Construye sobre:** Skill W Pilot + adaptador de navegador (Playwright/CDP, pendiente).
- **Fase:** 6.
- **DoD 🟢:** detecta una notificación real nueva, la resume en claro y crea el plazo en calendario.
- **Esfuerzo:** 🔴 (portales sin API, frágiles). Diferenciador fuerte.

### 6. Memoria de empresa como grafo temporal (evolución de `EntityProfile`)
- **Qué:** aprender el comportamiento **real** por cliente/proveedor (paga a 45 días aunque la factura diga 30; contacto; canal preferido; incidencias) y que el dunning personalice tono y timing.
- **Dato:** 4 tipos de memoria + grafo temporal estilo Graphiti (IA_TENDENCIAS §3); INFORME §12.3.4.
- **Construye sobre:** `agent/memory.py` + `EntityProfile` (ya con gate antifraude IBAN).
- **Fase:** 3 (usa el patrón) + 5 (lo aprende).
- **DoD 🟢:** el perfil aprende el patrón de pago real de un cliente y el dunning ajusta timing/tono en consecuencia.
- **Esfuerzo:** 🟡-🔴.

### 7. Plantillas que aprenden (memoria procedural) — *es el criterio de salida de Fase 5*
- **Qué:** *"he visto que mandas este recordatorio 3 veces; ¿lo guardo como plantilla?"*. Auto-mejora desde el uso real.
- **Dato:** memoria procedural (IA_TENDENCIAS §3); criterio Fase 5: *"≥1 plantilla propuesta desde casos reales"*.
- **Construye sobre:** `agent/memory.py` + skill manifests.
- **Fase:** 5.
- **DoD 🟢:** tras N casos similares, propone una plantilla; el usuario la acepta y se reutiliza en el siguiente caso.
- **Esfuerzo:** 🟡.

---

## Quick wins (alto valor, poco código)

### 8. Velocidad de respuesta a leads
- **Qué:** borrador instantáneo y personalizado de respuesta a lead entrante (email/WhatsApp), listo para 1 toque.
- **Dato:** *"el 78% de los leads se cierra con quien responde primero"* (OPERATIVA_PYMES §3.5).
- **Fase:** 2/3.
- **DoD 🟢:** ante un lead real, borrador personalizado con su contexto en segundos, listo para enviar con 1 toque.
- **Esfuerzo:** 🟢.

### 9. Radar de contratos recurrentes
- **Qué:** registrar seguros/alquileres/suscripciones/cuota de autónomo desde el extracto y avisar 30 días antes de la renovación con el delta de importe.
- **Dato:** el seguro que se renueva +12% sin que nadie lo autorice (OPERATIVA_PYMES §6.6).
- **Construye sobre:** #1 (conciliación bancaria).
- **Fase:** 2.
- **DoD 🟢:** detecta ≥1 contrato recurrente del extracto y avisa antes de la renovación con el delta.
- **Esfuerzo:** 🟢-🟡.

### 10. Cruce factura↔albarán + auto-fix de rechazos de mutua
- **Qué:** detectar discrepancias factura recibida vs albarán/pedido; para mutuas, corregir el código de rechazo y proponer reenvío.
- **Dato:** *20% de facturas a mutuas rechazadas, 70% por un código corregible automáticamente* (Supuesto D, OPERATIVA_PYMES §7); document intelligence (IA_TENDENCIAS §4).
- **Construye sobre:** `docs_intel` (extractor de facturas + endpoint + tool `read_invoice`).
- **Fase:** 3.
- **DoD 🟢:** detecta una discrepancia real factura/albarán y, para una mutua, propone la corrección del código.
- **Esfuerzo:** 🟡.

---

## Mapa innovación → fase

| # | Innovación | Fase | Construye sobre | Esfuerzo | ⭐ |
|---|---|---|---|---|---|
| 1 | Conciliación bancaria | 2 + 3 | cobros + docs_intel | 🟡 | ⭐ |
| 2 | Semáforo de confianza | 3 / 4 / 6 | `SkillSafetyClass` | 🟡 | ⭐ |
| 3 | Captura única | 3 | `EntityProfile` | 🟡 | |
| 4 | Brief de 5 líneas (UX) | 2 + 4 | morning brief + UI | 🟢-🟡 | ⭐ |
| 5 | Monitor Sede/DEH/Lexnet | 6 | Pilot + navegador | 🔴 | |
| 6 | Memoria grafo temporal | 3 + 5 | `memory.py` | 🟡-🔴 | |
| 7 | Plantillas que aprenden | 5 | `memory.py` | 🟡 | |
| 8 | Velocidad de leads | 2/3 | agente + conectores | 🟢 | |
| 9 | Radar contratos recurrentes | 2 | #1 | 🟢-🟡 | |
| 10 | Cruce factura/albarán + mutuas | 3 | `docs_intel` | 🟡 | |

## Secuencia recomendada

1. **Ahora (refuerza Fase 2-3):** #4 (brief 5 líneas) + #1 (conciliación bancaria) + #2 (semáforo). Juntos hacen el brief y los cobros honestos y "mágicos", y reutilizan código ya escrito.
2. **Quick wins en cuanto haya datos:** #8 (leads) y #9 (contratos recurrentes, sobre #1).
3. **Fase 3 profunda:** #3 (captura única) + #10 (factura/albarán + mutuas).
4. **Fase 5:** #6 (grafo temporal) + #7 (plantillas que aprenden — cierra el criterio de fase).
5. **Fase 6:** #5 (monitor Sede/DEH/Lexnet) junto al adaptador de navegador y WhatsApp.
