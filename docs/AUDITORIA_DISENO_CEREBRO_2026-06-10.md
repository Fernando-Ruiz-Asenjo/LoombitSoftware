# Auditoría de DISEÑO del cerebro (más allá de los bugs) — 2026-06-10

> Encargo de Fernando (ciclo 4/50): «analiza más allá de los errores — problemas de DISEÑO, mal
> PLANTEAMIENTO, carencias en el PROCESO CREATIVO». Esto NO es la lista de bugs (esa va en
> `AUDITORIA_LOOP_2026-06-09.md`); es la crítica de arquitectura/producto, fundada en lo que han
> revelado los 4 ciclos de presión. Cada hallazgo: TIPO · SEVERIDAD · evidencia · recomendación · DUEÑO.

## 🔭 Meta-observación (la más importante)

**~80% de los «bugs» de los ciclos 1-3 NO eran bugs de cálculo: eran de ROUTING o de EXTRACCIÓN** — el
14B no llegaba a la tool correcta, o llegaba con el argumento mal. El cálculo determinista (cobro, 303,
facturación) casi nunca falla. Esto apunta a DOS problemas de diseño de raíz (D-1 y D-3), no a diez bugs
sueltos. Seguir parcheando regex/short-circuits es tratar síntomas. **El diseño que escala es: clasificar
con LLM + extraer con código + calcular con código.** Hoy hacemos: clasificar con regex + extraer con LLM
+ calcular con código → justo invertido en las dos capas que fallan.

## Tabla de hallazgos

| # | Tipo | Sev | Hallazgo | Dueño |
|---|---|---|---|---|
| D-1 | Diseño | **ALTA** | Routing por REGEX = whack-a-mole; no escala al lenguaje natural | Claude (+OK Fernando, toca núcleo) |
| D-2 | Arquitectura | **ALTA** | Lógica de DOMINIO fiscal metida en el núcleo BLANCO (`loop.py`) | Claude (deuda que introduje) |
| D-3 | Planteamiento | **ALTA** | Los NÚMEROS los extrae el 14B, no un extractor determinista (la brújula dice «cifras por código») | Claude |
| D-4 | Carencia creativa | MED-ALTA | Sin razonamiento COMPARATIVO/temporal (el autónomo piensa en evolución) | Producto (Fernando) |
| D-5 | Carencia creativa | MEDIA | El telar teje correos+calendario, NO la salud FINANCIERA proactiva | Producto |
| D-6 | Planteamiento | MEDIA | Los tests asertan por string-matching (frágil); mejor sobre la ESTRUCTURA (steps) | Claude |
| D-7 | Diseño | MEDIA | El FOCO del force-tool se ajusta a mano por intención (sin principio) | Claude |
| D-8 | Carencia creativa | MEDIA | Producto fiscal estrecho: solo el 303 (130/111/349 abstienen) | Fernando (#8/#9) |
| D-9 | Planteamiento | BAJA-MED | El aviso fiscal es anteposición de prompt, no una KB que cite | Fernando (#1) |

---

## D-1 · Routing por regex no escala (ALTA) — ✅ HECHO (2026-06-10)

> **RESUELTO (aditivo, bajo riesgo).** El regex (`intencion_consecuente`) sigue siendo el FAST-PATH
> barato; cuando NO casa pero la petición tiene señal de dominio (`merece_clasificar`), un
> **clasificador LLM** (`descomposicion.clasificar_intencion`, temp 0, menú cerrado, confianza ≥0.6)
> cubre la cola larga. Así una frase nueva que el regex no previó la clasifica el LLM — **se acabó
> añadir un regex por cada fraseo**. Data-gate: cobro/303/factura SIN dato no se fuerzan (que pregunte).
> Verificado EN VIVO: «¿cuánto me ADEUDAN mis clientes?» (regex None) → cobros_pendientes; «ANOTAR una
> VENTA a Endesa de 500€» (regex None) → registrar_factura. +2 golden (fake LLM) + gate verde + arnés
> sin regresión (el fast-path preserva el comportamiento; el LLM solo se llama cuando el regex falla).


**Síntoma repetido:** cada ciclo amplío `intencion.py` — `vencid→venc`, «mis ingresos», `retención→reten`,
modelos AEAT, `_texto_para_intencion`… Es whack-a-mole: cada fraseo nuevo del usuario = un gap = un parche.
El lenguaje natural tiene infinitas formas de decir «cuánto me deben»; la regex nunca las cubrirá todas.

**Planteamiento equivocado:** usamos regex para lo que el LLM hace BIEN (clasificar intención) y el LLM
para lo que el código hace bien (las cifras). Está invertido.

**Recomendación:** el **clasificador de intención por LLM** (temp 0, JSON, exactamente como ya hace
`agent/descomposicion.py::descomponer` para A1) pasa a ser el **router PRIMARIO**; el regex queda como
fast-path barato (si casa claro, ahorra la llamada) y como fallback. El LLM clasifica a un MENÚ cerrado
(no inventa), con confianza; las cifras siguen por código. Ya tenemos la pieza (A1) — generalizarla.
**Coste:** +1 llamada LLM por turno ambiguo (mitigable con el fast-path regex). **Dueño:** Claude, con OK
de Fernando (es el núcleo del agente).

## D-2 · Dominio fiscal en el núcleo BLANCO (ALTA, deuda mía) — ✅ HECHO (2026-06-10)

> **RESUELTO.** Nuevo hook BLANCO `agent/guardas.py` (registro genérico `registro_guardas`); las 3
> guardas fiscales (retención IRPF, IBAN inválido, modelos AEAT) movidas a
> `skill_d_fiscal/guardas_fiscales.py` y registradas al cargar la skill. `loop.py` ya NO contiene
> lógica de IRPF/IBAN/modelos: solo consulta el hook antes del ReAct (`registro_guardas.aplicar`).
> Verificado: comportamiento IDÉNTICO (8/8 en vivo: retención/IBAN/modelo abstienen igual) + gate verde
> + golden del hook (`test_registro_guardas_aplica_dominio_fiscal`). −~90 líneas de dominio en el
> núcleo blanco. Queda como follow-up extraer también las correcciones de ARGS por-tool (fecha/periodo/
> 303-líneas) a un hook de tool-args (D-2 parte 2).


**La deuda de diseño más clara, y la introduje yo en estos ciclos.** `loop.py` (núcleo BLANCO,
reutilizable) tiene ahora short-circuits de DOMINIO fiscal español: `_es_registro_con_retencion`,
`_lleva_retencion`, `_iban_invalido_a_guardar`, `_modelo_no_modelado`, `_corregir_periodo_303`… Eso
**viola la BRÚJULA**: «el dominio vive en skills/routers, NO en el núcleo blanco». Además `loop.py` pasa
de 1400 líneas (la regla es <~400). Un Loombit «auditor industrial» o «cerebro de robótica» (el mismo
binario blanco) arrastraría el IRPF y el IBAN español. Mal.

**Recomendación:** una capa de **guardas de dominio pre-intent** registrable (lista de
`(detector, mensaje)` que el dominio aporta), viviendo en `skill_d_fiscal`. `loop.py` solo hace:
`for guard in self.domain_guards: if guard.applies(task): return guard.respond(...)`. El núcleo blanco
queda limpio; lo fiscal vuelve a su skill. **Dueño:** Claude. **Es el primer refactor que propongo hacer**
(con verificación: el comportamiento no debe cambiar, solo el sitio del código).

## D-3 · Los números los pone el 14B, no el código (ALTA) — ✅ HECHO (2026-06-10)

> **RESUELTO.** Extractor determinista `parsers.parsear_importe_es` (es-ES: `1.234,56`/`-200`/`2500`,
> excluye %, días, fechas y años) + corrector `loop._corregir_importe` que recalcula
> `plan_cobro.total` / `registrar_factura.base` desde el texto (caso «IVA incluido» → base=imp/(1+tipo)
> recalculando el IVA). Conservador: 0 o >1 importes → no corrige. El e2e destapó+arregló DOS bugs
> encadenados: (a) routing — un REGISTRO con base+IVA mis-rutaba a `resumen_financiero` (exclusión
> `_REGISTRO_FACTURA` en `intencion`); (b) args — el 14B usa `base_imponible`/`tipo_iva`
> (`_normalizar_alias_factura`). Verificado EN VIVO 3/3: negativa (base **-200**+IVA -42 = -242, el caso
> flaky del ciclo 3, RESUELTO), total-vs-base (base 2000), IVA incluido (base 1000+IVA 210=1210). +3
> golden + gate verde.

La brújula manda «las cifras las calcula CÓDIGO». Lo cumplimos en el CÁLCULO (cobro/303 deterministas),
pero NO en la EXTRACCIÓN: `registrar_factura(base=…)`, `plan_cobro(total=…)` reciben el número de lo que
el 14B extrajo del texto — y el 14B **garbea** (ciclo 3: «-200» → registró -827,96; el cobro a veces
confunde total con base; los importes en palabras/«1k»/«millón y medio» son una incógnita —los mide la
batería v5). El dato entra por la capa equivocada.

**Recomendación:** un **extractor determinista** (regex/parsing) de importes (€, miles/decimales
es-ES, palabras, %), fechas (ya existe `parsear_fecha`) y tipos de IVA, que **pre-rellene los args** del
force-tool ANTES de pasárselos al modelo —o que CORRIJA los del modelo, como ya hace
`_corregir_fecha_cobro`/`_corregir_periodo_303` para las fechas. Extender ese patrón a los IMPORTES.
**Dueño:** Claude. Cierra de raíz una familia entera de fallos de extracción.

## D-4 · Sin razonamiento comparativo/temporal (MED-ALTA, carencia de producto) — ✅ HECHO (2026-06-10)

> **RESUELTO.** Nueva tool determinista `resumen_comparativo(unidad)` (dominio.py): compara un periodo
> con el ANTERIOR (mes/trimestre/año) — facturado, gastos, beneficio, con la variación en € y en %
> (maneja anterior=0 sin inventar %). Routing `_es_comparativa` en intencion.py (intención
> `comparativo`) + en el menú del clasificador LLM. Corrector determinista de `unidad` desde el texto.
> **PREDICCIÓN del futuro EXCLUIDA** (de comparativa Y de facturacion) → abstención honesta (no se
> muestra el pasado como si fuera el futuro). Verificado EN VIVO: «¿facturé más este mes que el
> pasado?» → «junio vs mayo: 2000 € vs 1000 € → +1000 € (+100%)»; «¿cuánto voy a facturar el mes que
> viene?» → STEPS=[] abstención. Golden (periodos/variación/routing/corrector) + 17 casos en la
> auditoría (gate) + e2e 3/3. Limitación v1: compara ACTUAL-vs-anterior, no pares arbitrarios (el
> encabezado dice siempre qué periodos compara → honesto).


Loombit responde «cuánto facturé en junio» pero no «¿facturé más que en mayo?», «¿va mejorando?»,
«¿mi mejor mes?», «a este ritmo, ¿cuánto en el año?». El autónomo **piensa en evolución**, no en
fotos sueltas. Hoy abstiene (honesto) o, peor, podría fabricar una comparación. **Recomendación:** tool
`resumen_comparativo` (mes vs mes, trimestre vs trimestre, interanual) — trivial sobre los datos que ya
hay; + abstención dura en PREDICCIÓN del futuro. **Dueño:** producto (proponérselo a Fernando; es
construible y de alto valor percibido).

## D-5 · El telar no teje las finanzas (MEDIA, carencia de producto) — ✅ HECHO (2026-06-10)

> **RESUELTO.** El telar ya tejía cobros vencidos + calendario fiscal (303); le faltaba la SÍNTESIS
> proactiva de la salud financiera. Nuevo hilo **PULSO FINANCIERO** (`_hilo_pulso` + fuente
> `_fuente_pulso_financiero` en telar.py): la facturación del último mes CERRADO vs el anterior
> (reusa los helpers DETERMINISTAS de D-4 — cruce de skills), con la variación en %. Si BAJÓ → 📉
> urgencia 2 (atención); si subió → 📈 urgencia 1. Compara meses COMPLETOS (no parte un mes en curso,
> que sería injusto). Best-effort: sin datos → None → no inventa un hilo. El autónomo VE su tendencia
> sin pedirla. Golden (`_hilo_pulso` + tejido + fuente con entidad aislada) + 6 casos en la auditoría
> (gate). Pendiente futuro (D-5 v2): moroso recurrente, facturas a punto de prescribir.


Hay síntesis proactiva del día (telar: correos+calendario+plazos), pero NADA proactivo de la SALUD
FINANCIERA: «tu beneficio cayó este trimestre», «3 facturas a punto de prescribir», «el 303 de este
trimestre te saldrá alto», «Acme te paga tarde sistemáticamente». La data está (facturas registradas);
falta tejerla. **Recomendación:** hilos FINANCIEROS en el telar. **Dueño:** producto.

## D-6 · Tests por string-matching (MEDIA, mejora de la propia herramienta)

Las baterías asertan `"200" in x` sobre el texto narrado — frágil («200» casa en «2026»; depende de cómo
narre el 14B). **Mejor diseño:** asertar sobre la ESTRUCTURA — `r.steps` (tool + args + resultado de la
tool como datos), que es determinista, en vez del texto. **Dueño:** Claude (endurece todas las baterías).

## D-7 · El foco del force-tool se hand-tunea (MEDIA)

He quitado `task_done` del foco de facturacion/cobros_pend/resumen_financiero/factura uno a uno, sin un
principio. **Debería derivarse de la naturaleza de la tool:** una tool de LECTURA-agregada pura → fuerza
la tool (sin escape); una de ESCRITURA con args requeridos → permite `ask_user` si falta un dato. Si se
deriva, no hay que acordarse caso por caso. **Dueño:** Claude.

## D-8 / D-9 · Decisiones de Fernando (producto/política)

- **D-8:** producto fiscal estrecho (solo 303; 130/111/349/115 abstienen). El autónomo los necesita.
  Decisión #8/#9 (construir el 130/retención). **Dueño:** Fernando.
- **D-9:** el aviso fiscal regulado de-autoritativiza pero el 14B sigue inventando el específico (IVA
  fisioterapia). KB-curada-que-cite vs rehúsa-específicos. Decisión #1. **Dueño:** Fernando.

---

## Orden recomendado (lo que YO haría, por ROI)

1. **D-2** (extraer dominio del núcleo blanco) — limpio, sin cambiar comportamiento, paga deuda mía. Ya.
2. **D-3** (extractor determinista de importes) — cierra una familia entera de fallos de extracción.
3. **D-1** (router LLM como primario) — el cambio estructural de mayor calado; requiere tu OK.
4. **D-6** (tests sobre estructura) — endurece la herramienta de presión.
5. **D-7** (derivar el foco) — pequeño, principia lo ad-hoc.
6. **D-4/D-5** (comparativas + telar financiero) — producto, alto valor; proponer.
7. **D-8/D-9** — tus decisiones.
