# Baremos, pruebas y cómo llevamos D-1…D-9 hasta GOLDEN — 2026-06-10

> Encargo de Fernando: «saca una lista de los baremos, pruebas y cómo hemos aplicado los tests para
> mejorar los D hasta golden». Aquí está, en 3 partes: (1) los BAREMOS (qué cuenta como «golden»),
> (2) las PRUEBAS (el arsenal, por capa), (3) cómo cada D llegó a golden (o por qué aún no).
> Fuente de los hallazgos: `docs/AUDITORIA_DISENO_CEREBRO_2026-06-10.md`.

---

## 1) BAREMOS — los criterios que definen «golden»

Un fix NO está «golden» por pasar una prueba en vivo (eso es anecdótico). Tiene que cumplir TODOS:

| # | Baremo | De dónde sale |
|---|---|---|
| B1 | **No mentir (DoD).** Nunca un «✅» sin recibo real de una tool que tuvo éxito. | CLAUDE.md regla nº1 |
| B2 | **Las cifras las calcula CÓDIGO**, no el LLM (extracción + cálculo deterministas). | Brújula |
| B3 | **No sobre-abstener.** Rehusar algo que Loombit SÍ puede = tan malo como fabricar (falso positivo). | Auditoría |
| B4 | **Comportamiento IDÉNTICO en refactors** (D-2): mover código no cambia la respuesta. | Reparación Canónica |
| B5 | **Verificado por RECIBO EN VIVO**, no solo por test (el 14B real, mismo motor que el server). | Brújula / DoD |
| B6 | **~1% de error, DETECTABLE** (los fallos que queden, visibles para corregir a mano o repasar). | Fernando |
| B7 | **Blindado en el GATE** con un test DETERMINISTA: si un cambio lo rompe, `verify.py` se pone ROJO. | RC |
| B8 | **Compounding**: cada fix se queda como regresión permanente; los siguientes ciclos lo re-chequean. | Fernando |
| B9 | **Nunca «100%».** Se reporta cobertura por recibo, no una garantía. | Brújula |

**Escalera de madurez** (un D sube peldaño a peldaño hasta golden):

```
1. Prueba en vivo (anecdótica)         → "funciona una vez"
2. Batería funcional en vivo (14B real) → comportamiento ESTADÍSTICO (N escenarios)
3. Arnés / tests DUROS adversariales    → presión por ángulos distintos
4. Auditoría CAJA-BLANCA (determinista) → falsos positivos/negativos, agujeros de regex
5. GOLDEN en el gate (B7)               → blindaje permanente, ROJO si regresa
```

---

## 2) PRUEBAS — el arsenal, por capa

| Capa | Fichero | Qué es | LM | Nº |
|---|---|---|---|---|
| **Golden** (gate) | `tests/test_cerebro_golden.py` | piezas deterministas del cerebro | No | 90+ |
| **Golden** (gate) | `tests/test_descomposicion.py` | A1 + clasificador LLM (con fake) | No | 10 |
| **Golden** (gate) | `tests/test_dominio_tools.py` | tools de dominio (303, cobro, factura) | No | 17 |
| **Auditoría** (gate) | `scripts/auditoria_d1d2d3.py` | **125 sondas adversariales, 10 ciclos** | No | 125 |
| **Funcional vivo** | `scripts/funcional_live{,2,3,4}.py` | el 14B real, escenarios E2E | Sí | ~190 |
| **Design-probes** | `scripts/funcional_live5.py` | sondea CARENCIAS (comparativas, multi-entidad…) | Sí | 24 |
| **Tests duros** | `scripts/test_duros_d1d2d3.py` | adversarial en vivo, por familia D1/D2/D3 | Sí | 24 |
| **Arnés presión** | `scripts/presion_cerebro.py` | 19 escenarios de presión | Sí | 19 |
| **GATE** | `scripts/verify.py` | black + ruff + pytest + evals F1-F8 | No | — |

> Clave: lo DETERMINISTA (golden + auditoría) vive en el GATE (B7). Lo VIVO (baterías) da el recibo
> del 14B real (B5) pero no entra en CI (necesita LM Studio).

---

## 3) APLICACIÓN — cómo cada D llegó a golden

### ✅ D-1 · Routing por regex no escala → clasificador LLM de respaldo
- **Baremo clave:** B3 (no mis-rutear), B7, B8. Una frase nueva debe rutear SIN añadir un regex.
- **Pruebas aplicadas:** golden `test_clasificar_intencion_*`, `test_merece_clasificar_*` (fake LLM);
  e2e vivo («¿cuánto me adeudan?» / «anotar una venta» → rutean); arnés 19/19; tests duros D1 **8/8**;
  auditoría **D1 22/22** + ciclos C1/C7/C9/C10 (mayúsculas, conflictos, multivuelta, inyección).
- **Bugs que cazaron:** el regex devolvía un positivo ERRÓNEO (303) que el LLM no rescataba; la
  conciliación se iba a cobros_pendientes; «mete en el sistema lo que le facturé… más su IVA» → 303.
- **Golden de cierre:** `test_factura_coloquial_rutea_a_factura`, `test_clasificar_*`, + auditoría en gate.

### ✅ D-2 · Dominio fiscal en el núcleo blanco → hook de guardas en la skill
- **Baremo clave:** B4 (comportamiento idéntico), B3, B7.
- **Pruebas aplicadas:** golden `test_registro_guardas_aplica_dominio_fiscal` (el hook);
  **8/8 en vivo** (retención/IBAN/modelo abstienen igual tras mover); tests duros D2 **8/8**;
  auditoría **D2 25/25** + ciclos C4 (retención variantes) / C5 (modelo) / C6 (IBAN).
- **Bugs que cazaron:** IBAN no casaba «apúntame»/«REGÍSTRAME» (acentos); modelo solo con la palabra
  «modelo» (no «el 130 del pago fraccionado»); retención no casaba «me retienen» (conjugación);
  **falsos positivos** «no me retienen» / «exenta de retención» / «0% de retención» / «el 130 €» / «el 190 €».
- **Golden de cierre:** `test_modelo_por_numero_suelto_y_nombre`, `test_es_registro_con_retencion_*`,
  el hook, + auditoría en gate.

### ✅ D-3 · Los números los pone el 14B → extractor + corrector deterministas
- **Baremo clave:** B2 (cifras por código), B3 (conservador: 0 o >1 importes → no corrige), B7.
- **Pruebas aplicadas:** golden `test_parsear_importe_es_*`, `test_corregir_importe_*`;
  **3/3 e2e** (negativa base -200, total-vs-base 2000, IVA incluido 1000); tests duros D3 **8/8**
  (incl. año-like base 2026); auditoría **D3 19/19** + ciclos C3 (números límite) / C8 (sobre-corrección).
- **Bugs que cazaron:** un año-like (2000/2026) se excluía como importe; el IVA no se recalculaba en
  «IVA incluido»; el 14B usaba `base_imponible`/`tipo_iva`; **sobre-corrección** en «el 50% de los 2000».
- **Golden de cierre:** `test_parsear_importe_es_excluye_*`, `test_corregir_importe_*`, + auditoría en gate.

> **Resumen de los 3:** auditoría **125/125 · 0 hallazgos**, cableada al gate
> (`test_auditoria_fuerte_d1d2d3_en_el_gate`). 8 falsos positivos/negativos cazados y blindados.

### ⏳ D-4…D-9 · AÚN NO en golden (no se les han aplicado pruebas todavía)
| D | Estado | Por qué aún no |
|---|---|---|
| D-4 comparativas/tendencias | Pendiente | Producto NUEVO (no deuda); falta tool + golden |
| D-5 telar financiero | Pendiente | Producto NUEVO |
| D-6 tests por string-matching | Pendiente | Mejora de la herramienta (asertar sobre `steps`) |
| D-7 foco del force-tool hand-tuneado | Pendiente | Derivar el foco de la naturaleza de la tool |
| D-8 fiscal estrecho (solo 303) | Pendiente | **Decisión de Fernando (#8/#9)** |
| D-9 aviso fiscal = prompt, no KB | Pendiente | **Decisión de Fernando (#1)** |
| D-2 parte 2 (args por-tool al hook) | Pendiente | Follow-up técnico de D-2 |

**Camino para llevarlos a golden** (mismo método): batería en vivo que HOY falle → fix limpio y
determinista → golden en el gate (B7) → auditoría caja-blanca de los casos límite → 0 hallazgos.
