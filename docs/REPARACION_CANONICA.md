# REPARACIÓN CANÓNICA (RC) — método blanco para arreglar y endurecer cualquier subsistema

> **Skill C (canónico): gobierna el PROCESO de reparación.** Es **blanco/reutilizable**: vale para
> cualquier familia de Loombit (Cerebro, Manos/dominio, Conectores, Telar, UX, Fábrica…), no solo
> para una. Primera aplicación: **RC·Cerebro**. Cualquier agente (Claude, Copilot, la Fábrica) que
> arregle o endurezca algo SIGUE esto. Si choca con una nota, manda esto. Nace de una sesión donde
> las auditorías blandas ("se pinta = funciona") y las afirmaciones sin recibo rompieron la confianza.

## Principio rector
**El LLM PROPONE, el código DISPONE.** Nada consecuente (€, fechas, IBAN, impuestos, asignación de
campos, gates) lo decide el LLM. Lo consecuente es código determinista, testeable y por tanto fiable;
el LLM queda en pasos acotados y NO consecuentes (entender intención, narrar), con fallback.

## El ciclo RC (por cada ítem de una familia)
1. **INVENTARIAR — del CÓDIGO, no de notas.** Extrae el comportamiento REAL → algoritmo con
   `fichero:línea` y estado actual. (Las notas envejecen; el código manda.)
2. **DEFINIR LO CORRECTO.** Algoritmo objetivo + criterio de aceptación medible.
3. **ARNÉS PRIMERO.** Escribe el **golden test** que codifica lo correcto ANTES de tocar:
   - si **falla hoy** → bug confirmado (rojo honesto, no sorpresa luego);
   - si **pasa** → queda blindado contra regresiones.
   - Si el AS‑IS es incierto: primero un **test de caracterización** (captura lo actual) y luego el
     **test objetivo** (lo correcto) → así un refactor no rompe en silencio.
4. **CLASIFICAR la pieza.** *Determinista* → test exacto, **100% en el gate** (`verify.py`, sin modelo).
   *LLM* → **eval de comportamiento con UMBRAL** (p. ej. ≥9/10) y requiere LM Studio vivo (no CI puro).
5. **ARREGLAR o QUITAR.** Rama/worktree; ficheros < ~400 líneas; **blanco** donde toque (sin sesgo de
   usuario/cliente/sector); el núcleo del agente con OK de Fernando. Nunca fingir: si no se puede, se
   abstiene honesto y se anota.
6. **VERIFICAR POR RECIBO.** Test verde **y** prueba real (curl/clic en el Chrome real, dato, recibo).
   Jamás "se renderiza" = "funciona". Retira en voz alta los falsos positivos.
7. **GATE VERDE + COMMIT.** `python scripts/verify.py` verde; commit con el **recibo en el mensaje**
   (qué se probó + evidencia). Reversible: rama, fundible por PR.
8. **SCORECARD.** Marca 🟠/⚠️ → 🟢 en la tabla de la familia. **La familia es "fiable" cuando TODA su
   tabla está 🟢 con test en el gate** (métrica honesta = % en verde, nunca "100%" de boquilla).

## Reglas duras (reafirman la brújula)
- **Predicción ≠ hecho.** No afirmes que algo funciona/seguirá sin recibo. Reporta **cobertura**
  (qué probé + recibo + qué NO), nunca "100% / todo verificado".
- **Abstención honesta.** Si falta una mano, dilo claro y breve; no improvises un "plan manual".
- **Gate de efectos sagrado · Datos ≠ órdenes.**
- **Escape sin bloquear:** si hace falta una decisión de producto, anótala en «⭐ PARA FERNANDO» del
  log y sigue con otra cosa. No pares el trabajo a preguntar obviedades.
- **Concurrencia:** si otro agente puede compartir el árbol de trabajo, **aísla en `git worktree`**.

## Plantilla canónica por ítem (úsala igual en todas las familias)
```
## ALG-<FAMILIA>.<n> · <nombre>   <estado: ✅|🟢|🟠|⚠️|❌>
Propósito · Entrada · Salida
Algoritmo  (marca cada paso [CÓDIGO] determinista | [LLM] acotado)
Errores / casos límite
Golden (el test que lo blinda)
Mapa (fichero:línea)
```
**Convención de nombres:** algoritmos `ALG-<FAMILIA>.<n>`; tests `tests/test_<familia>_golden.py`;
docs `docs/ALGORITMO_<FAMILIA>_EXISTENTE.md` (AS‑IS) + el objetivo donde proceda.

## Artefactos por familia
1. `docs/ALGORITMO_<FAMILIA>_EXISTENTE.md` — inventario AS‑IS con estado.
2. `tests/test_<familia>_golden.py` — los golden, en el gate.
3. Una fila por familia en el **SCORECARD** (abajo).

## Definición de HECHO (refuerza `DEFINITION_OF_DONE.md`)
🟢 = comportamiento correcto **+ test en el gate + recibo real**. Sin recibo, no es 🟢. Lo del LLM
nunca es "🟢 100%": es "🟢 con eval ≥ umbral".

---

## SCORECARD de familias (vivo)
| Familia | Doc AS‑IS | Tests golden | % verde | Estado |
|---|---|---|---|---|
| **Cerebro** (RC·Cerebro, instancia #1) | `ALGORITMO_CEREBRO_EXISTENTE.md` | `tests/test_cerebro_golden.py` ✅ (44) | **código 100%** | 🟢 lo DETERMINISTA blindado (smalltalk, parser tolerante, saneadores, anti-email, normalización/guards, perfil pagador, anti-bucle, estados del run, memoria, telar) + ALG-0.1/0.2. Solo el LLM queda como eval con umbral. |
| Manos / dominio (cobro·303·factura·conciliación) | (en `ALGORITMO_CEREBRO.md` ALG‑3.x) | parcial (`test_dominio_tools.py`) | parcial | 🟠 |
| Conectores (Gmail·Calendar·Contacts) | *(pendiente)* | *(pendiente)* | — | ⬜ |
| Telar / cognición | (familia 5‑7 del cerebro) | *(pendiente)* | — | 🟠 |
| UX / shell | `AUDITORIA_UX_2026-06-09.md` | n/a | — | 🟠 |

> Aplicar RC a una familia nueva = repetir el ciclo 1‑8 con su plantilla y añadir su fila aquí.

## Instancia #1 — RC·Cerebro
Familias del cerebro y su estado: ver `docs/ALGORITMO_CEREBRO_EXISTENTE.md` (8 familias, ~40 ALG) y el
plan/orden en `docs/ALGORITMO_CEREBRO.md` (frontera de determinismo, orden de ataque, scorecard).
Orden: arnés → cimientos (contexto+reintento) → determinismo (parsers+validar) → relay+gate de datos →
resto 🟠→🟢 uno a uno.
