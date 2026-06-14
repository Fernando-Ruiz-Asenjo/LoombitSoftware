# EL MURO — el equipo de defensa de Loombit

> **Qué es.** El Muro es el **equipo** que hace cumplir la Brújula y defiende el NORTE. No es un proceso
> suelto ni un fichero: es un conjunto de **agentes monitores individuales que actúan como uno**. De cara
> afuera, un equipo con nombre; por dentro, piezas independientes y reemplazables.
>
> **Lo que NO es (clave).** El Muro **no es la ley ni el destino**. La ley es la **Brújula**
> (`docs/BRUJULA.md`); el destino es el **NORTE**. El Muro los **vigila y los hace cumplir** — y se mantiene
> separado de ellos a propósito: es la **Separación de Autoridades** (Ley Fundacional) aplicada al propio
> gobierno. La ley y quien la aplica no se mezclan; si se fundieran, la policía se escribiría sus leyes.
>
> **Lema:** *el LLM propone, El Muro dispone.* (El Muro es el código determinista que dispone.)
> **Decisión:** D-102. **Adoptado:** 2026-06-14.

---

## 1. Las capas (El Muro es la de abajo)

```
NORTE      ← el destino: qué es Loombit y para quién                 [el PORQUÉ]
  ▲ lo defiende
BRÚJULA    ← la ley que apunta al NORTE (constitución + gobierno)    [el QUÉ / CÓMO]
  ▲ la hace cumplir
EL MURO    ← el EQUIPO que ejecuta la vigilancia                     [el QUIÉN]
```

El Muro **integra la *vigilancia* de las tres capas, no su contenido**: vigila que el NORTE se respete, que
la Brújula se aplique y que el gobierno no se manipule — sin *ser* ninguno.

---

## 2. Los miembros del equipo

| Miembro | Ruta | Qué vigila | Se activa por | Permanencia |
|---|---|---|---|---|
| **Gate canónico** | `scripts/verify.py` | la puerta única: orquesta a casi todos | hook + CI + manual | gate-time |
| Auditoría caja-blanca D1-D3 | `scripts/auditoria_d1d2d3.py` | 3 fixes de diseño (449 sondas) | `verify.py` | gate-time |
| Auditoría del cobro | `scripts/auditoria_cobro.py` | Ley 3/2004 (demora/escalada) + 5000 fuzz | `verify.py` | gate-time |
| Fuzz de invariantes | `scripts/fuzz_invariantes.py` | propiedades invariantes (5000/propiedad) | `verify.py` | gate-time |
| **Foso LOCAL** | `scripts/auditoria_foso_local.py` | **vigila el NORTE**: ningún egress sin declarar | `verify.py` | gate-time |
| Cadena de gobierno | `scripts/auditoria_cadena.py` | tamper-evidence (SHA-256) del registro | `verify.py` | gate-time |
| **Brújula per-diff** | `scripts/auditoria_brujula.py` | **vigila la Brújula**: ¿aplicada en este cambio? | `verify.py` | gate-time |
| Promesas | `scripts/auditoria_promesas.py` | ¿el código hace lo pedido? (criterios probados) | `verify.py` | gate-time |
| **Radar vivo+fresco** | `scripts/auditoria_radar.py` | innovación obligatoria (señal ≤45 días) | `verify.py` | gate-time |
| Mutación | `scripts/mutation_test.py` | que los tests tengan dientes | `verify.py --strict` (CI) | gate-time |
| Test en vivo | `scripts/live_smoke.py` | servidor real, HTTP real | `verify.py --live` (CI) | gate-time |
| Candados anti-debilitamiento | `tests/test_gate_integridad.py` (+ brújula/gobierno/conducta) | que no se quite ni un check ni se bajen suelos | `pytest` | gate-time |
| Recibos de conducta | `loombit_operator/conducta.py` | conducta cuantificable (D-58/D-70) | `tests/test_conducta.py` | gate-time |
| El muro de GitHub (CI) | `.github/workflows/ci.yml` | `--strict --live` obligatorio antes de merge | push/PR a `main` | always-on |
| Auditor independiente | `.github/CODEOWNERS` + `branch-protection.yml` | constructor ≠ auditor; protección de `main` | PR + cron | always-on |
| **Centinela continuo** | `loombit_operator/el_muro_centinela.py` | salud de El Muro 24/7 (radar fresco, cadena íntegra) | Routine cron PASSIVE | **always-on** (🟢 propuesto · espera CI) |

---

## 3. Qué autoridad vigila cada quién

- **NORTE** (el foso LOCAL) → `auditoria_foso_local.py` (los datos no salen de la máquina).
- **Brújula** (la ley aplicada) → `auditoria_brujula.py` (¿la aplicaste en *este* diff?, D-80) +
  `test_brujula_cumplimiento.py` (tabla sin celdas vacías, deuda de tamaño).
- **Gobierno** (la historia infalsificable) → cadena (`auditoria_cadena.py`), candados
  (`test_gate_integridad.py`), recibos (`conducta.py`), cobertura del gobierno (`test_gobierno_cobertura.py`).

---

## 4. Permanencia — "actualizados y activados permanentemente" (pedido: TODO)

Estado (3d, 2026-06-14 · 🟢 propuesto · gate local verde · espera CI): la permanencia total se materializó así:

1. **Centinela continuo.** `loombit_operator/el_muro_centinela.py`: Routine **PASSIVE always-on** que corre en
   bucle los chequeos read-only de salud (radar fresco ≤45 días + cadena íntegra) y deja recibo en
   `runtime/local/`. Cableado vía `build_scheduler_con_centinela()`, que **envuelve** el scheduler por defecto
   sin tocar `routine_executors.py` (respeta su deuda de tamaño). Arnés: `tests/test_el_muro_centinela.py`.
2. **Candados endurecidos.** `tests/test_gate_integridad.py` ahora exige que el centinela y esta carta no se
   puedan borrar ni vaciar (un miembro de El Muro no se desactiva en silencio).
3. **Miembros dormidos despertados.** `core.hooksPath` reapuntado a `.githooks` (el gate local vuelve a
   dispararse en cada commit) y `mypy` instalado (faltaba y degradaba el type-check en silencio).

> **K2:** Fernando lo definió como **alias de un mecanismo ya existente**; ese mecanismo ya es miembro de El
> Muro (arriba). Cuando concrete cuál, se le añade la etiqueta "K2" — sin cambiar nada más.

---

## 5. Honestidad de límite

El Muro hace el registro **infalsificable**, no **verdadero**: una cadena a prueba de manipulación de
mentiras sigue siendo mentiras. La verdad la sigue dando **el check verde de GitHub** (§GOB-2b: "hecho lo
declara GitHub, no el agente"). El Muro impide que se borre/altere la historia o se debilite la defensa sin
que se note — y defiende, no decide el contenido de la ley.
