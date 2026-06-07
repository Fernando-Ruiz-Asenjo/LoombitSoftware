# Conocimiento del oficio administrativo (España) — base para Loombit

> **Propósito.** Destilar qué es realmente el trabajo administrativo en España, qué se
> espera de quien lo ejerce, con qué herramientas, en qué ritmo y en qué sectores, para
> que Loombit no solo *mueva datos* sino que *entienda el oficio*. Este documento es la
> fuente de verdad de dominio de la **Skill Blanca No. 1 — Trabajo Administrativo General**.
> Fecha: 2026-06-07. Documento vivo. Honestidad obligatoria (ver `DEFINITION_OF_DONE.md`).

---

## 0. Lectura para Loombit: cómo usar este documento

Cada sección termina con un bloque **→ Loombit** que traduce el conocimiento del oficio
a capacidades, gates de seguridad o supuestos de prueba. El objetivo no es que Loombit
sepa "teoría administrativa", sino que en el bucle PERCIBIR → PLANEAR → PREPARAR →
APROBAR → EJECUTAR → RECIBO → APRENDER, en cada paso, tenga el contexto que tendría un
administrativo competente con 5 años de oficio. La regla mental es: *"¿qué comprobaría,
qué prepararía y qué dudaría una persona con experiencia antes de hacer esto?"*

---

## 1. Qué es el trabajo administrativo

El trabajo administrativo es la **maquinaria invisible** que mantiene a una organización
operando: registrar, clasificar, comunicar, cobrar, pagar, archivar y cumplir plazos.
No produce el bien o servicio que vende la empresa, pero sin él la empresa se detiene.
Su valor está en el **rigor** (un número mal apuntado es dinero perdido), la **trazabilidad**
(todo debe poder demostrarse después) y el **cumplimiento de plazos** (lo fiscal y lo legal
no esperan).

### Los cuatro perfiles (de menor a mayor responsabilidad)

- **Auxiliar administrativo.** Tareas de apoyo: grabación de datos, archivo, atención
  telefónica, registro de entrada/salida de documentos, escaneo, mecanografía de
  documentos a partir de órdenes. Es el grano fino de la oficina.
- **Administrativo.** Tramita expedientes completos, gestiona compraventa (pedidos,
  albaranes, facturas), lleva tesorería básica (cobros, pagos, conciliación), atiende a
  clientes y proveedores, prepara documentación contable.
- **Técnico en gestión administrativa / Técnico superior en administración y finanzas.**
  Asume contabilidad, gestión financiera, fiscalidad básica, RR.HH. (nóminas, altas/bajas),
  y coordina procesos. Toma decisiones dentro de un marco.
- **Gestor administrativo (oficio colegiado).** Profesión regulada: representa a personas
  físicas y jurídicas ante la Administración, tramita declaraciones fiscales, altas/bajas
  en Seguridad Social, constitución de empresas, tráfico, extranjería. Requiere titulación
  universitaria (Derecho, Economía, ADE) y colegiación. **No confundir con "asesor"**, que
  no es figura regulada y orienta sin necesariamente tramitar.

**Asesoría vs. gestoría (distinción clave para el mercado de Loombit).** La asesoría
*aconseja* (fiscal, laboral, contable); la gestoría *ejecuta el trámite*. En la práctica,
en la PYME española muchos despachos son ambas cosas. Loombit, en su cuña 1, automatiza la
parte de *ejecución administrativa* (preparar y tramitar con aprobación humana), no la de
asesoramiento jurídico-fiscal, que requiere criterio profesional y colegiación.

**→ Loombit.** El perfil que Loombit emula en la cuña 1 es el **administrativo / técnico**,
no el gestor colegiado. Esto fija el techo de responsabilidad: Loombit *prepara* trámites
y comunicaciones; *no representa* legalmente ni firma como profesional colegiado. Todo lo
que roce asesoramiento regulado debe escalar a humano (gate de competencia).

---

## 2. El temario del oficio (destilado de la FP)

Las dos titulaciones de referencia en España son el **Grado Medio en Gestión Administrativa**
y el **Grado Superior en Administración y Finanzas**. Destilando sus módulos, el oficio se
organiza en siete grandes áreas de competencia. Esto es, en esencia, el "currículo" que
Loombit debe dominar por skills.

### A. Comunicación empresarial y atención al cliente
Redacción de comunicaciones internas y externas, atención presencial/telefónica/digital,
gestión de quejas y reclamaciones, servicio postventa, protocolo y registro de la
comunicación. Incluye el uso correcto del correo electrónico como canal formal.

### B. Operaciones administrativas de compraventa
El ciclo comercial completo: pedido → albarán → factura → cobro/pago. Cálculo de
descuentos, IVA, portes; formas y medios de pago; envío y recepción de mercancías;
gestión de stock básica.

### C. Técnica contable y tratamiento de la documentación contable
Partida doble, el ciclo contable, libros obligatorios, registro de facturas emitidas y
recibidas, amortizaciones, cierre de ejercicio. El administrativo no siempre "lleva la
contabilidad", pero sí prepara y clasifica su documentación soporte.

### D. Operaciones de tesorería
Control de cobros y pagos, conciliación bancaria, gestión de liquidez, medios de pago
(transferencia, recibo SEPA, pagaré, confirming, factoring), previsión de tesorería.
**Esta es el área central de la cuña 1 (seguimiento de cobros).**

### E. Operaciones administrativas de recursos humanos
Contratos, nóminas, seguros sociales (TC), altas/bajas en Seguridad Social, control
horario y de ausencias, gestión documental del personal.

### F. Ofimática y tratamiento informático de la información
Procesador de textos, hoja de cálculo (el caballo de batalla real: tablas dinámicas,
buscarV/XLOOKUP, fórmulas, formato), bases de datos, gestión de archivos digitales,
correo y agenda, firma digital. La FP moderna añade **digitalización aplicada** (automatización).

### G. Empresa, Administración y marco jurídico
Cómo funciona la empresa y la Administración pública, trámites de constitución y
funcionamiento, contratación privada y con el sector público, derecho mercantil y laboral
básico, fiscalidad de la empresa, y **procedimiento administrativo** (la Ley 39/2015:
cómputo de plazos, registro, notificaciones, representación). El Grado Superior añade
organización del Estado, UE y actuación de la empresa ante las AA.PP.

**→ Loombit.** Estas siete áreas son el mapa natural de **skills instalables**. La cuña 1
ataca **D (tesorería/cobros)** apoyada en **B (compraventa)**, **A (comunicación)** y **F
(ofimática)**. El área **G** no es una skill ejecutora sino *conocimiento de fondo* que debe
estar embebido en los gates: cómputo de plazos, validez de notificaciones, representación.

---

## 3. El día a día: el ritmo administrativo

El trabajo administrativo tiene una cadencia. Loombit debe entender que hay tareas que se
disparan **por evento**, otras **por calendario**, y que el calendario fiscal-laboral
español marca el pulso. Esta es una de las claves para pasar de "operador reactivo" a
"operador que anticipa" (el paso PERCIBIR → anticipar del plan maestro).

### Tareas diarias (por evento o continuas)
- Abrir y clasificar el correo entrante (físico y electrónico); registrar entrada.
- Atender llamadas, correos y visitas; derivar o resolver.
- Emitir facturas de las ventas/servicios del día.
- Registrar facturas recibidas de proveedores.
- Revisar movimientos bancarios y conciliar lo identificable.
- Actualizar la agenda: citas, reuniones, plazos, vencimientos.
- Archivar (digital y físico) lo tramitado, con su criterio de clasificación.

### Tareas semanales
- Revisión de cobros pendientes y vencidos (aging de clientes) → recordatorios.
- Preparación de pagos a proveedores según vencimientos.
- Conciliación bancaria de la semana.
- Reposición de material; pequeñas compras.
- Reporte de horas/ausencias del personal.

### Tareas mensuales
- Cierre de facturación del mes; cuadre de ingresos.
- Nóminas y seguros sociales (en torno a fin de mes / primeros del siguiente).
- Conciliación bancaria mensual completa.
- Conciliación de saldos de clientes y proveedores.
- Previsión de tesorería del mes siguiente.

### Tareas trimestrales (el "pico" del calendario fiscal)
- **Liquidaciones de IVA** (modelo 303) y **retenciones IRPF** (111 alquileres 115, etc.):
  hasta el día 20 de abril, julio, octubre y enero.
- Resumen y preparación de documentación para la asesoría/gestoría.

### Tareas anuales
- **Resúmenes anuales** (modelo 390 IVA, 190 retenciones) en enero.
- Cierre contable del ejercicio; cuentas anuales y su depósito en el Registro Mercantil.
- **Renta y Sociedades** (modelo 200) en su campaña.
- Archivo y custodia del ejercicio cerrado (plazo legal de conservación: 4 años fiscal,
  6 años mercantil como referencias habituales — verificar caso).

**→ Loombit.** El **morning brief** (Fase 2) debe construirse sobre este ritmo: no es solo
"qué hay en tu bandeja hoy", sino *"hoy es 14 de julio, faltan 6 días para el cierre del
303; tienes 3 facturas sin cobrar que pasaron el día 61; el viernes vence el pago a
proveedor X"*. El **scheduler de autonomía** (Fase 5) debe codificar estos vencimientos
recurrentes. El calendario fiscal español es un conocimiento de dominio que debe vivir en
una tabla mantenible, no hardcodeado.

---

## 4. Las herramientas reales (con qué se trabaja)

El administrativo español medio no vive en un solo programa: salta entre el correo, la hoja
de cálculo, el software de facturación/contabilidad, el banco online y los portales de la
Administración. Loombit no sustituye a estas herramientas; **orquesta el trabajo entre ellas**.

### Ofimática y comunicación (la base de todo)
- **Hoja de cálculo (Excel / Google Sheets / LibreOffice Calc).** La herramienta reina.
  Listados de clientes, control de cobros, cuadres, previsiones. El supuesto práctico de
  oposiciones se juega aquí.
- **Procesador de textos (Word / Google Docs).** Cartas, contratos, comunicaciones formales.
- **Correo y agenda (Outlook / Gmail / Google Calendar).** Canal formal y planificación.

### Facturación y contabilidad PYME/autónomo
- **En la nube:** Contasimple (Cegid), Quipu, Billage, Holded, Sage 50/Sage Despachos,
  Alegra, FacturaDirecta. Muy usados por autónomos y micropymes.
- **Despachos y empresas mayores:** Sage Despachos Connected, A3 (Wolters Kluwer),
  ContaPlus (histórico), SAP Business One, Microsoft Dynamics (Navision), Odoo (modular).
- Todos están migrando a **cumplimiento Verifactu** (ver §5).

### Gestión de empresa y equipos
- **CRM:** HubSpot, Pipedrive, Zoho — gestión comercial y de contactos.
- **RR.HH.:** Factorial (nóminas, fichaje, ausencias, documentos), Sage, A3Nom.
- **ERP:** SAP, Dynamics, Odoo para quien integra todo.

### Banca y Administración
- Banca electrónica (cada entidad), normas SEPA (adeudos y transferencias).
- Sede electrónica de la AEAT, Seguridad Social (Sistema RED / SILTRA), DGT, registros.
- **Certificado digital / Cl@ve / firma electrónica:** llave de acceso a todo lo público.

**→ Loombit.** Diseñar pensando en que el dato vive repartido. Los **conectores** (Gmail,
Calendar, Drive, Microsoft 365) son los puentes a estas herramientas. La hoja de cálculo
es tan central que Loombit debe leer y producir XLSX con soltura (skill de documento). El
**certificado digital** es terreno sensible: Loombit *prepara* el trámite pero **nunca**
introduce credenciales ni firma por el usuario (es acción prohibida; humano en el bucle).

---

## 5. Marco normativo que un administrativo DEBE conocer (2026)

Un administrativo competente en España hoy no puede ignorar tres frentes normativos. Loombit
debe llevarlos embebidos en sus gates, porque condicionan qué es "hacer bien" una tarea.

### 5.1 Facturación: Verifactu y factura electrónica B2B
Hay **tres obligaciones distintas que la gente confunde**, con calendarios separados:

1. **Factura a Administraciones Públicas (B2G).** Electrónica y obligatoria desde 2015
   (Ley 25/2013), vía FACe.
2. **Sistemas de facturación verificables — Verifactu** (Reglamento del RD 1007/2023,
   desarrollado por normativa posterior). Regula los *requisitos técnicos del software*
   de facturación (registros encadenados, inalterables, con posibilidad de envío a la
   AEAT). Calendario de referencia: obligatorio para sujetos del Impuesto sobre Sociedades
   desde **el 1 de enero de 2026** y para el resto de empresas y autónomos desde
   **el 1 de julio de 2026**. Las fechas han sufrido prórrogas; **verificar siempre la
   vigente** antes de afirmar nada (la honestidad del DoD aplica también aquí).
3. **Factura electrónica obligatoria entre empresas (B2B)** de la **Ley Crea y Crece**
   (Ley 18/2022, art. 12). Pendiente de reglamento de desarrollo y supeditada a una
   excepción comunitaria; su entrada efectiva se ha venido aplazando (referencias a
   2027). **No dar por hecha una fecha sin comprobarla.**

El incumplimiento de Verifactu puede acarrear sanciones elevadas (referencias de hasta
decenas de miles de euros por ejercicio). Por eso un software que *toca* facturas debe
ser escrupuloso.

### 5.2 Morosidad y plazos de pago (núcleo de la cuña 1)
Regulado por la **Ley 3/2004** (modificada por la Ley 15/2010 y la Ley Crea y Crece):

- **Plazo de pago:** 30 días naturales por defecto desde la entrega del bien o servicio
  (o recepción de factura, lo que ocurra antes); ampliable por pacto hasta un **máximo de
  60 días**. Cláusulas que superen 60 días en perjuicio del acreedor son nulas.
- **Intereses de demora automáticos** desde el día siguiente al vencimiento (día 61 en el
  máximo), **sin necesidad de reclamación previa**. Tipo = tipo del BCE + 8 puntos
  (referencias recientes en torno al 10–11% anual; **es variable, comprobar el semestre**).
- **Compensación fija por costes de cobro: 40 € por factura impagada** (art. 8), automática.
- **Reclamación judicial:** el **proceso monitorio** es la vía típica para deuda dineraria
  documentada (factura, albarán, email de conformidad sirven como principio de prueba).
- **Novedad relevante (Ley Orgánica 1/2025):** se introducen **medios adecuados de solución
  de controversias (MASC)** como requisito previo a muchas reclamaciones judiciales civiles.
  Esto cambia el flujo de recobro: antes de ir al juzgado, hay que intentar/documentar un
  MASC. Loombit debe conocer este paso.

### 5.3 Protección de datos y procedimiento administrativo
- **RGPD / LOPDGDD:** todo dato de cliente/proveedor/empleado es dato personal. Minimización,
  finalidad, conservación limitada, seguridad. Nada de datos fuera de la máquina sin base.
- **Ley 39/2015 (procedimiento administrativo común):** cómputo de plazos (días hábiles vs.
  naturales; sábados son inhábiles administrativos; si el último día es inhábil pasa al
  siguiente hábil; el festivo local cuenta como inhábil donde aplica), representación
  (acreditación), registro y notificaciones electrónicas. Esto es lo que cae en los
  supuestos de oposición y es **conocimiento de fondo crítico para no equivocar un plazo**.

**→ Loombit.** Estos tres frentes se traducen en **gates deterministas**:
- *Gate de facturación:* si una factura va a emitirse, ¿el software/registro cumple
  Verifactu? Si no, advertir.
- *Gate de cobros:* calcular vencimiento, día 61, interés de demora aplicable y los 40 €
  con la norma vigente, y conocer que el escalón judicial exige MASC previo.
- *Gate de datos:* nunca exfiltrar datos personales; consentimiento por fuente.
- *Gate de plazos:* todo cómputo de plazos administrativos usa calendario de días hábiles
  con festivos nacionales/autonómicos/locales. **Nunca** estimar "a ojo" un plazo legal.

---

## 6. El oficio por sectores

El mismo administrativo cambia de piel según dónde trabaje. Loombit debe entender estas
variaciones porque determinan el vocabulario, los documentos y los flujos.

### Gestoría / Asesoría
El cliente *es* la administración de otras empresas. Volumen alto de: presentación de
modelos fiscales, nóminas y seguros sociales de las empresas cliente, altas/bajas en
Seguridad Social, constitución de sociedades, comunicación con la AEAT y la TGSS. Trabajo
muy estacional (picos trimestrales y anuales). Documentación de terceros → máxima exigencia
de confidencialidad y trazabilidad.

### Despacho profesional (abogados, arquitectos, médicos por cuenta propia)
Administración de la propia actividad: agenda de citas/vistas, facturación de honorarios
(a menudo con provisiones de fondos), gestión documental de expedientes, plazos procesales
o de proyecto, relación con colegios profesionales. El plazo es sagrado (un plazo procesal
perdido es responsabilidad grave).

### Sanitario / clínica
Citación de pacientes, gestión de historiales (dato de salud = categoría especial RGPD,
máxima protección), facturación a mutuas y aseguradoras, autorizaciones, control de
consentimientos informados, gestión de agenda de profesionales.

### Construcción / industria
Albaranes y certificaciones de obra, control de proveedores y subcontratas, documentación
de prevención de riesgos (PRL) y coordinación de actividades empresariales (CAE),
seguimiento de cobros a menudo a 60+ días, gestión de avales y garantías.

### Comercio / hostelería / servicios
Caja diaria y arqueo, facturación simplificada (tickets), control de stock, pedidos a
proveedores, conciliación de TPV y plataformas de delivery, gestión de personal por turnos.

**→ Loombit.** El **núcleo blanco** se mantiene igual; lo que cambia entre sectores es la
**skill instalada** (vocabulario, plantillas, documentos y gates específicos). La
arquitectura "núcleo blanco + skills" es exactamente la respuesta correcta a esta realidad.
La cuña 1 debe elegir UN sector piloto para el primer flujo (recomendación: servicios /
comercio B2B, donde el seguimiento de cobros a 30–60 días es dolor puro y la ambigüedad
legal es baja).

---

## 7. Competencias transversales (lo que hace bueno a un administrativo)

Más allá de las tareas, el oficio premia un conjunto de cualidades que Loombit debe imitar
en su *comportamiento*, no solo en sus funciones:

- **Rigor numérico y documental.** Un IBAN, un importe o un NIF mal copiado tiene
  consecuencias reales. Cero tolerancia a la invención de datos (esto enlaza con la regla
  nº 1 del proyecto: no se puede mentir; no se puede "rellenar" un dato que no se tiene).
- **Cumplimiento de plazos.** El calendario manda. Anticipar siempre mejor que reaccionar.
- **Trazabilidad y archivo.** Todo lo hecho debe poder demostrarse después (= el **recibo**
  auditable del plan maestro es la versión Loombit de esto).
- **Discreción.** Maneja información sensible de la empresa y de terceros.
- **Comunicación clara y educada.** Sobre todo en cobros: firme pero sin romper la relación
  comercial.
- **Saber cuándo escalar.** Un buen administrativo sabe qué decide él y qué consulta al
  jefe, al asesor o al abogado. (= el **gate de aprobación humana**.)

**→ Loombit.** Estas competencias *son* el comportamiento esperado del operador. El "no
inventar datos", el "anticipar plazos", el "dejar recibo" y el "escalar lo que no te
corresponde" no son features opcionales: son la definición de hacer el trabajo *bien*.
Cualquier eval de Loombit debe puntuar estas competencias, no solo si la acción se ejecutó.

---

## 8. Síntesis: del oficio a las skills de Loombit

| Área del oficio | Skill / capacidad Loombit | Fase | Gates clave |
|---|---|---|---|
| Comunicación y atención (A) | Redacción de correos/cartas con aprobación | 1–3 | Actor verificado, tono, no inventar hechos |
| Compraventa (B) | Lectura de pedidos/albaranes/facturas | 2–3 | Extracción fiel, no alucinar importes |
| Contabilidad (C) | Clasificación de documentación soporte | 2 | Solo lectura, consentimiento de fuente |
| **Tesorería / cobros (D)** | **Seguimiento de cobros (cuña 1)** | **3** | **Plazos morosidad, 40€, MASC, día 61** |
| RR.HH. (E) | (Aparcado para cuña posterior) | — | Dato personal, RGPD reforzado |
| Ofimática (F) | Lectura/producción XLSX, agenda, correo | 1–4 | — |
| Empresa/Admin/Jurídico (G) | Conocimiento de fondo en gates | transversal | Cómputo de plazos, Verifactu, representación |

**Conclusión para dirección.** La cuña 1 (seguimiento de cobros) es la elección correcta
no solo por mercado, sino porque concentra el conocimiento más *codificable y verificable*
del oficio: plazos legales deterministas, importes calculables, un flujo con principio
(factura vencida) y fin (cobro o escalado), y un marco normativo claro (Ley 3/2004). Es el
flujo donde Loombit puede demostrar antes un recibo 🟢 real y donde el valor para la PYME
es inmediato y medible (días de cobro reducidos = caja).

Ver el banco de supuestos en `BANCO_SUPUESTOS_LOOMBIT.md` para exprimir cada una de estas
capacidades y, sobre todo, para probar que Loombit **bloquea limpio** cuando debe.
