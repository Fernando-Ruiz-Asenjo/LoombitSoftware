# Insights de producto y supuestos — extracción accionable

> Síntesis operativa de la investigación de campo (jun 2026). Destila los tres informes
> grandes en lo que mueve el proyecto: datos de mercado, el caso WhatsApp, el backlog de
> supuestos para tests de comportamiento y el mapa de capacidades vs. realidad.
> *Generado: 2026-06-08. No dupliques aquí los informes — esto es el índice accionable.*

**Fuentes** (en `docs/investigacion/`):
- [`INFORME_GLOBAL_TRABAJO_OFICINA.md`](investigacion/INFORME_GLOBAL_TRABAJO_OFICINA.md) — global, 15 roles, país por país, supuestos I-X, mapa de capacidades.
- [`OPERATIVA_PYMES_AUTONOMOS_ORDENADOR.md`](investigacion/OPERATIVA_PYMES_AUTONOMOS_ORDENADOR.md) — sector por sector, ecosistema WhatsApp, supuestos A-G.
- [`OPERATIVA_EN_PANTALLA_DIA_A_DIA.md`](investigacion/OPERATIVA_EN_PANTALLA_DIA_A_DIA.md) — nivel pantalla/teclado, ciclo de cada documento, 5 niveles de capacidad.
- Estratégico: [`IA_TENDENCIAS_INSPIRACION_LOOMBIT.md`](IA_TENDENCIAS_INSPIRACION_LOOMBIT.md).

---

## 1. Datos de mercado verificados

Cifras para priorizar producto y para el discurso comercial:

| Dato | Cifra | Implicación |
|---|---|---|
| Tiempo en tareas administrativas | **10 días/mes** por PYME (Qonto + IO Investigación, 2026) | El dolor es masivo y medible |
| Ese tiempo impide trabajo estratégico | **55%** de las PYMES lo dicen | Argumento de venta directo |
| Españoles que usan WhatsApp a diario | **92%** | WhatsApp es el canal real, no el email |
| Prefieren contactar empresas por WhatsApp | **68%** (sobre email/teléfono) | Justifica WhatsApp como objetivo del Pilot |
| Comunicación de negocio por WhatsApp | hasta **80%** en autónomos | Los pedidos/citas viven ahí, fuera de todo sistema |
| Transportistas autónomos con herramienta digital | solo **25%** | Mercado virgen + obligación legal inminente |
| Leads inmobiliarios que cierra quien responde primero | **78%** | La velocidad de respuesta es el producto |
| Facturas a mutuas sanitarias rechazadas en 1ª pasada | hasta **20%** (70% por error de código auto-resoluble) | Caso de uso de alto ROI casi automatizable |
| PYMES en España (<10 empleados el 95%) | **+3,3 M** | Tamaño de mercado |
| Autónomos registrados en España (2025) | **+3,3 M** | Cada uno con su carga administrativa |

**Plazos regulatorios = ventanas de oportunidad:**
- **eCMR obligatorio: septiembre 2026** (Ley 9/2025) — transporte.
- **VeriFactu: empresas enero 2027, autónomos julio 2027** — facturación electrónica firmada.
- Hay **25.000 €** en ayudas a digitalización del transporte (hasta jun 2026).

---

## 2. WhatsApp — por qué es el próximo objetivo del Pilot

WhatsApp es "la herramienta invisible": ningún informe de software empresarial la captura porque
es informal, pero es **donde ocurre el negocio real** de la PYME española. Por eso es objetivo de Pilot:

1. **Es donde llegan los pedidos** → un pedido por WhatsApp debe registrarse en el sistema.
2. **Es donde se confirman las citas** → deben sincronizarse con el calendario.
3. **Es donde se negocia** → los acuerdos verbales son la fuente de verdad de muchas transacciones.
4. **Es donde el cliente dice que no pagará** → la gestión de impagados pasa por ahí.

**El problema que resuelve:** hoy todo eso vive en el móvil de **una** persona. Si enferma, se va o
cambia de móvil, la información desaparece — sin registro, sin trazabilidad, sin historia.

**Encaje técnico:** Skill W Pilot lee WhatsApp Web (con permiso del usuario), extrae compromisos
(pedidos, citas, importes) y los registra. Es el patrón "navegador con gates" que ya validamos al
conectar Google: el humano da el consentimiento, el operador no toca credenciales. Refuerza la
necesidad del **adaptador de navegador (Playwright/CDP)** del roadmap (Fase 6).

---

## 3. Mapa de capacidades de Loombit en pantalla (5 niveles)

De `OPERATIVA_EN_PANTALLA` §8 — el orden en que Loombit gana terreno en la pantalla del usuario:

1. **Redactar y generar** — correos (presentación, seguimiento, recordatorio, reclamación), presupuestos desde anteriores, facturas desde presupuesto, informes de estado, actas.
2. **Buscar y recopilar** — info que falta en el email, documento en su carpeta, estado de un pago en el banco, teléfono/email de un contacto, datos de cliente del historial.
3. **Organizar y clasificar** — archivar el documento recibido, actualizar el Excel de seguimiento, registrar la factura, ordenar la bandeja por prioridad.
4. **Monitorizar y alertar** — factura vencida sin cobrar, notificación en la Sede Electrónica, plazo del 303, cliente que no responde, documento que falta en el expediente.
5. **Presentar y enviar (con aprobación)** — mandar el presupuesto/factura, presentar el modelo fiscal, confirmar la cita, dar de alta al empleado.

**Jerarquía de valor percibido** (INFORME §12.2) — construir en este orden:
N1 "ahorra tiempo en lo de cada día" → N2 "hace lo que yo olvidaba" → N3 "lo que me llevaba horas" → N4 "lo que yo no podía hacer".

---

## 4. Las 10 tareas más automatizables y los 5 sectores de mayor ROI

**Tareas universales** (OPERATIVA_PYMES §8.1) — emitir facturas (100% lo hacen), seguimiento de
cobros (2-5 h/sem), preparar datos para la gestoría (2-4 h/mes), presupuestos (80%), gestión de
citas/agenda (75%), confirmaciones de cita (→ 0 min), gestión de impagados, pedidos a proveedores,
control de plazos fiscales (reactivo → proactivo), remesas/cobros recurrentes (→ 0 min).

**Sectores de mayor ROI** (OPERATIVA_PYMES §8.2): 1) Gestoría/Asesoría, 2) Salud/Clínicas (mutuas),
3) Servicios y oficios (fontanero/electricista/pintor), 4) Comercio y tienda online multicanal,
5) Profesional liberal (abogado/arquitecto/consultor).

---

## 5. Lo que Loombit debe saber en cada interacción

Checklist de contexto para el system prompt del agente (OPERATIVA_PANTALLA §7):
- **Tarea:** ¿para quién? ¿plazo? ¿quién aprueba? ¿qué info falta que aún no tenemos?
- **Destino:** ¿email o WhatsApp? ¿a qué dirección/número? ¿con copia? ¿hace falta recibo de envío?
- **Restricciones:** ¿formato/plantilla obligatoria? ¿datos que no pueden incluirse (NDA, precios)? ¿tono por cliente?
- **Historial:** ¿hicimos algo similar antes? ¿hay documentos base de esta persona? ¿qué pasó la última vez?

---

## 6. Backlog de supuestos → tests de comportamiento

Los supuestos son escenarios reales con entrada, flujo esperado y documentos a producir. Son los
candidatos directos a **tests de comportamiento** (próximo paso del roadmap). Junto con los ya
existentes en [`BANCO_SUPUESTOS_LOOMBIT.md`](BANCO_SUPUESTOS_LOOMBIT.md) (S-01…S-15) y los A-H de
[`DOMINIO_ADMINISTRATIVO_LOOMBIT.md`](DOMINIO_ADMINISTRATIVO_LOOMBIT.md), forman la batería de QA.

### 6.1 Supuestos sectoriales A-G (de OPERATIVA_PYMES §7)

| # | Escenario | Capacidad clave que prueba |
|---|---|---|
| A | Fontanero: caos de fin de mes (6 sin facturar, 4 sin cobrar, 303 mañana) | Resumen de pendientes + generación masiva de facturas + cálculo 303 |
| B | Peluquería: hueco por cancelación de última hora | Proactividad + WhatsApp a lista de espera + reasignación de cita |
| C | Transportista: primer eCMR (obligatorio sept 2026) | Generación de documento legal nuevo + firma digital + automatización recurrente |
| D | Clínica dental: 12 facturas de mutua rechazadas | Detección de patrón de error + corrección y reenvío (70% auto) + escalado del resto |
| E | Abogado: requerimiento con plazo de 10 días en Lexnet | Monitorización de buzón + cálculo de plazo + alerta + agenda ("diaria") |
| F | Academia: remesa mensual de 87 cuotas | Generación automática + fichero SEPA + envío + gestión de rechazos |
| G | Tienda online: Black Friday multicanal (300 pedidos) | Consolidación Amazon/Etsy/web + stock + carritos abandonados |

### 6.2 Supuestos avanzados I-X (de INFORME §11)

| # | Escenario | Capacidad clave que prueba |
|---|---|---|
| I | Ola de facturas de fin de mes (6 inputs en un día) | Clasificación de inputs + registro + conciliación + briefing de 5 líneas |
| II | Cliente moroso crónico (3 facturas, 12.400 €) | Intereses Ley 3/2004 (BCE+8%) + gastos de cobro + 3 tonos + timeline |
| III | Cierre trimestral en 2 horas (papel + email + Drive) | Ingesta multi-fuente (incl. escaneo) + consolidación + detección de huecos |
| IV | Contratación urgente (auxiliar dental en 5 días) | Oferta legal + checklist onboarding + contrato + alta SS antes del día 1 |
| V | Presupuestos que no cierran (3 sin respuesta) | Seguimiento proactivo + email personalizado + guion de llamada |
| VI | Auditoría sorpresa de Hacienda (IVA 3 ejercicios) | Índice documental + localización + detección de lagunas + dossier |
| VII | Onboarding de cliente en la gestoría (alta RETA) | Alta autónomo + calendario fiscal + estructura contable + 1er modelo |
| VIII | Reunión con el banco (renovar póliza 150 k €) | Estados financieros + ratios + resumen ejecutivo 1 pág + argumentario |
| IX | Expediente de IT (baja médica) | Plazos de partes + pago delegado SS + cálculo subsidio + nómina |
| X | Cierre del ejercicio fiscal (Modelo 200) | Verificar cierre + separar lo automatizable de lo que pide criterio asesor |

### 6.3 Flujos de jornada como tests de integración (de OPERATIVA_PANTALLA §2)

Seis perfiles con su día completo en acciones reales, útiles como escenarios e2e:
administrativa de PYME, comercial B2B, técnico/profesional, autónomo de servicios,
recepcionista de clínica, gestor de asesoría (80 clientes).

---

## 7. Estado: capacidades vs. necesidades reales

De INFORME §12.1, **actualizado con el estado real del repo** (2026-06-08):

| Necesidad | Estado Loombit | Fase |
|---|---|---|
| Enviar emails reales | 🟢 **verificado (2026-06-07)** | Fase 1 |
| Crear eventos en calendario | 🟡 fake-tested (OAuth conectado) | Fase 1 |
| Gestionar email (clasificar, priorizar, borradores) | ⬜ pendiente | Fase 2 |
| Morning brief proactivo | 🟠 cerebro de cobros listo; falta el brief | Fase 2 |
| Leer facturas PDF y extraer datos | 🟡 extractor determinista hecho; falta Qwen-VL | Fase 3 |
| Calcular IVA trimestral | ⬜ pendiente | Fase 3 |
| Gestionar cobros y recordatorios | 🟡 motor de dunning (Ley 3/2004) hecho | Fase 3 |
| Memoria de clientes y proveedores (`EntityProfile`) | 🟡 hecho (gate antifraude IBAN) | activo |
| Operar sistemas sin API (Skill Pilot) | 🟠 reforzado (DPI, UIA, gates) | Fase 6 |
| Flujo conversacional | 🟡 implementado | activo |
| Facturación VeriFactu | ⬜ pendiente | Fase 4+ |
| WhatsApp (leer compromisos, registrar) | ⬜ pendiente | Pilot / Fase 6 |

---

## 8. Los cinco diferenciadores (para el discurso y para no perder el norte)

1. **Privacidad estructural, no política** — los datos no salen de la máquina; imposibilidad técnica de fuga.
2. **Conocimiento del marco legal español** — Modelo 303, Ley 3/2004, Sistema RED, VeriFactu, convenios — aplicado al flujo, no genérico.
3. **Skill Pilot opera lo que no tiene API** — Sede de Hacienda, Seguridad Social, ERP legacy, banca.
4. **Memoria de empresa que crece** — aprende quién paga tarde, quién manda mal las facturas, qué prefiere el gerente.
5. **El bucle completo sin salir de Loombit** — leer → entender → planear → preparar → aprobar → ejecutar → archivar → aprender.
