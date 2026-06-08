# Plataforma de inteligencia administrativa y fiscal — análisis de arquitecto

> Análisis de diseño (no implementación) para integrar en Loombit una plataforma fiscal/
> administrativa para España. El 303 es el **caso de entrada**, no el producto. El patrón
> invariante: *documentos → IA extrae/calcula/detecta/explica → humano valida → se presenta
> → llega justificante → expediente cerrado e inmutable*. **Regla legal inamovible:** la IA
> prepara y asiste; la validez la dan el titular, su certificado, la presentación aceptada y
> el justificante oficial. Nunca se marca "presentado" sin justificante real; nunca se
> fabrican CSV/NRC. *Generado: 2026-06-08.*

---

## Parte 1 — Respuestas técnicas

### 1. Encaje arquitectónico
**`Skill D Fiscal`** (dominio) sobre **`Skill W Administration Core`** (núcleo blanco), con
un **router** delgado para la API. El motor de expedientes/trazabilidad/extracción es **W**
(reutilizable por laboral, mercantil, DGT…); la lógica del 303 y la casuística AEAT son **D**.

**Se reutiliza (no se reinventa):**
- **Motor ReAct** (`agent/loop.py`): orquesta el flujo extraer→clasificar→calcular→explicar.
- **Memoria** (`agent/memory.py`, `EntityProfile`): pasa a ser la **memoria fiscal por entidad** (histórico, patrones, incidencias, gate antifraude IBAN ya existente).
- **Conectores OAuth** (`skill_blanca_oauth`, Gmail/Drive): la **entrada real** (ver C).
- **Routines** (recién hechas): el **calendario fiscal proactivo** y el monitor del buzón DEH.
- **Semáforo** (`SkillSafetyClass`): toda acción fiscal es `SAFETY_SENSITIVE` → aprobación humana obligatoria.
- **docs_intel**: base del extractor de facturas.

**Se construye nuevo:** el motor de **Expediente/CaseFile** (W), la lógica fiscal (D),
extracción con visión (Qwen-VL/Qwen3-VL), y los adaptadores Sede/RED (`Skill A`, Fase 6+).

### 2. Modelo de datos
JSON plano **no basta** para expedientes multi-entidad con consultas e integridad. →
**SQLite embebido** (stdlib, local-first, ACID, consultable). **Separación entre clientes:**
una BD por entidad bajo `runtime/local/entities/<entity_id>/fiscal.db` + justificantes como
ficheros con hash al lado. Ventajas: aislamiento físico real, export/borrado por cliente en
1 paso (RGPD), y escala natural a la gestoría (80 clientes = 80 ficheros independientes). Los
stores JSON actuales (routines, agent_runs) se quedan para estado de app; el dominio fiscal va a SQLite.

### 3. IA local para fiscal
- **Extracción de campos**: PDF con texto → `pypdf` (ya es dependencia) + 14B para estructurar; **PDF escaneado → visión** (Qwen2.5-VL ya descargado, o **Qwen3-VL** del radar L3) o OCR (Tesseract/Paddle) como fallback.
- **Razonamiento fiscal**: el 14B **sí** razona casuística española con buenos prompts + **RAG con procedencia** (BOE/AEAT citado). Pero **NO hace aritmética**: IVA, totales, intereses, prorrata se calculan **en código determinista** (radar R2); el LLM solo extrae, clasifica, explica y **detecta riesgos**.
- **Casuística compleja** (prorrata, inversión de sujeto pasivo, criterio de caja, recargo de equivalencia): se modela como **reglas deterministas** en `Skill D Fiscal`; el LLM **clasifica el caso y avisa**, y ante duda **se abstiene y escala** (radar R3). Nunca adivina.
- **Prompts necesarios**: (a) extracción estructurada de factura; (b) clasificación de tipo de operación/IVA; (c) detección de riesgo/incoherencia; (d) explicación en lenguaje claro para el humano.

### 4. Skill Pilot como presentador oficial (Fase 2+)
- **Lo que falta hoy**: el **adaptador de navegador** (Playwright/CDP, ya pendiente en el roadmap), contrato de coordenadas/escalado, y verificador de pasos en la Sede.
- **Certificado digital (FNMT/DNIe) — regla de oro de seguridad**: Loombit **nunca** toca la clave privada. El certificado vive en el almacén del SO / el navegador del usuario; el Pilot **conduce el navegador del usuario** donde el cert ya está instalado, y **el humano da el clic de firma/envío**. Loombit no firma ni posee la clave.
- **Captura del justificante**: descargar el PDF/justificante que devuelve la AEAT, guardarlo en el expediente con **hash**, y solo entonces marcar la operación 🟢. Sin justificante, no hay "presentado".

### 5. Separación Skill W vs Skill D
- **`Skill W Administration Core` (núcleo blanco, reutilizable):** Expediente/CaseFile, ciclo de vida del documento, extracción genérica, Plazo, **gate de aprobación (semáforo)**, Recibo, **trazabilidad inmutable**.
- **`Skill D Fiscal` (dominio España):** definición de modelos (303/130/111/115/347/390/200…), cálculo del 303, casuística AEAT, calendario tributario, reglas de riesgo. Depende de W; **no contamina** W.

### 6. Primer slice vertical (dado Fase 1 + OAuth en curso, sin Sede automatizada)
**Intake de facturas + borrador de 303 (solo lectura; el humano presenta a mano).**
- **Entrada:** una factura PDF con texto (subida manual o, mejor, por email — ver C).
- **Proceso:** extraer campos (pypdf + 14B) → clasificar IVA → acumular en un **Expediente** del trimestre → al cierre, **calcular determinista** IVA devengado/deducible → generar **borrador de 303 + explicación + avisos de riesgo**.
- **Salida:** un borrador de 303 (cifras + explicación) que el humano presenta a mano en la Sede; **recibo 🟢 solo cuando el humano pega el justificante** devuelto.
- **Qué debe existir:** motor de Expediente (W), extractor de factura (extender `docs_intel`), cálculo IVA determinista (D), plantilla de borrador 303. **Sin** Sede, **sin** certificado.
- **Por qué este**: demuestra el patrón completo **con cero riesgo legal** (la IA nunca presenta).

### 7. Riesgos reales (honestidad)
| Riesgo | Cuándo aprieta | Mitigación |
|---|---|---|
| OCR/extracción de mala calidad | desde el día 1 con escaneados | empezar **solo texto** (pypdf); visión después; **el humano valida siempre los campos extraídos** |
| Casuística fiscal edge (prorrata, ISP, caja, recargo) | Fase 3 | reglas deterministas + **abstención y escalado**; nunca adivinar; cubrir primero el régimen general |
| Multi-tenant local-first | al meter varias entidades | **BD por entidad** (aislamiento físico) + scoping estricto; tests de no-cruce |
| Integración Sede Electrónica | Fase 6+ | nunca envío headless automático; **humano en el clic**; el portal cambia → verificador + fallback manual |
| Certificado digital | Fase 6+ | **nunca** tener la clave; conducir el navegador del usuario; firma = acto humano; responsabilidad legal del titular |

---

## Parte 2 — Más allá del brief

### A. Oportunidades que el brief no ve
- **Expediente × memoria = inteligencia fiscal proactiva.** Con el histórico por entidad, Loombit detecta anomalías: *"tu IVA va un 40% por encima de lo habitual del T2, revisa"*, *"el año pasado dedujiste este seguro y este trimestre falta"*. Eso no lo da un gestor humano sin horas.
- **Documentos con MÁS dolor que el 303:** el **buzón DEH/Sede** (un requerimiento no visto = sanción; nadie lo vigila bien — valor altísimo), el **347** (cuadre con terceros), el **390** (cuadre anual con los 4 trimestres), el **IS/Modelo 200** (lo más caro y complejo), y **nóminas + Sistema RED** (recurrente, mensual). El 303 es el más conocido, no el más doloroso.
- **Calendario fiscal proactivo por entidad** (cada empresa tiene su combinación de modelos/plazos) → una Routine que prepara con antelación. El patrón Expediente sirve para **cualquier** trámite oficial (AEAT, SS, DGT, subvenciones).

### B. Qué lo hace difícil de copiar (no "la IA")
- **Histórico fiscal acumulado por entidad** (años de 303/347/justificantes + patrones). Un rival que empieza de cero no tiene nada; el coste de cambio **crece cada año**.
- **Correcciones aprendidas**: cada vez que el humano edita un borrador, Loombit aprende los tics de esa entidad (este proveedor, esta deducción). Corpus propietario que crece.
- **Archivo de trazabilidad/justificantes inmutable**: valioso por sí mismo (inspecciones) y atado a Loombit.
- **La combinación**: local/privado + profundidad legal española + Skill Pilot operando Sede/RED. Cloud no puede dar privacidad estructural; la IA genérica no opera la Sede; los extranjeros no saben de derecho español.

### C. Qué cambia con acceso al email (Gmail/Outlook)
**Lo cambia todo.** Las facturas de proveedores **llegan por email**; las nóminas y extractos también; los avisos de notificación DEH también. Con ingesta automática, la "entrada" deja de ser fricción (subir documentos) y pasa a ser **magia** (Loombit ya lo tiene): vigila la bandeja, extrae facturas según llegan, las clasifica y archiva, y cruza con la DEH para cazar requerimientos antes del plazo. **Recomendación fuerte: el email read-only (Fase 2) es el verdadero desbloqueo del producto**, no el upload manual.

### D. Modelo de negocio que el brief no explora: la GESTORÍA
El brief apunta al autónomo. Pero el **gestor/asesor (50-500 clientes)** es mucho mejor cliente: **1 cliente = 80 entidades = 80× datos y valor**. Loombit se vuelve el "recolector+preparador del lado del cliente" de la gestoría: recopila y prepara, el gestor revisa y presenta (él tiene el certificado y la autoridad). B2B2C, recurrente, pegajoso, con **distribución masiva** (el gestor ya tiene la cartera). Posicionar como **superpoder del gestor, no su reemplazo** (si no, lo temen). Lo mismo para colaboradores sociales y despachos.

### E. Qué hace que el usuario no pueda irse (valor real, no lock-in artificial)
El **expediente acumulado** (años de presentaciones + justificantes + tics aprendidos por entidad) y la **memoria proactiva** que conoce su ritmo fiscal. Irse = perder el rastro auditable y el operador que conoce tu negocio. Los datos son locales y exportables (sin lock-in artificial); el foso es que **nadie puede replicar el contexto acumulado, el comportamiento aprendido y la confianza ganada con presentaciones correctas**.

---

## Parte 3 — Mi opinión directa (qué cambiaría del planteamiento)

1. **No liderar con "presentar el 303".** Presentar un modelo mal tiene consecuencias legales reales; es el paso más arriesgado (cert, Sede). **Lideraría con percibir y preparar**: intake de facturas + conciliación + calendario fiscal + **monitor DEH/requerimientos** — valor enorme **sin que la IA toque jamás una presentación legal**. La presentación (borrador → humano presenta) llega después, cuando hay confianza. *Percibir y preparar antes que disparar* — es exactamente la filosofía de Loombit.
2. **Diseñar para la gestoría desde el día 1**, no para el autónomo suelto → multi-entidad de entrada (de ahí SQLite por entidad, no JSON plano).
3. **El email es la entrada real**, no el upload manual. Priorizar Gmail/Outlook read.
4. **El número nunca lo pone el LLM** (cálculo determinista + cita de fuente + abstención). En fiscal, alucinar es inaceptable; esta disciplina es el foso de confianza.

> Resumen: el brief describe un buen producto vertical (303). El producto **grande** es el
> **motor de expedientes oficiales** (W) + **memoria fiscal proactiva** + **la gestoría como
> canal**, con el 303 como primera prueba de un patrón que cubre toda la Administración española.
