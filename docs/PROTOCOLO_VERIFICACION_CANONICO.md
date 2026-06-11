# 🔒 Protocolo de Verificación Canónico — «Hecho lo declara GitHub, no el LLM»

> **Estado: CANÓNICO (D-66).** Esto es la Ley Fundacional aplicada al propio agente: *el LLM nunca está
> en el camino de control de confianza*. Por tanto **"hecho" no es lo que el agente diga** — es **un check
> verde en GitHub** que el humano puede ver sin fiarse de nadie. El agente PROPONE; el gate DISPONE; GitHub
> CONFIRMA.

---

## 0. Por qué existe

Un agente puede afirmar "está hecho / 🟢 / funciona" en falso (ha pasado: D-58). Si la prueba de que algo
está hecho es **la palabra del agente**, no hay prueba. La única salida honesta es que **cada tarea
produzca un resultado chequeable por máquina**, que ese resultado lo **confirme un tercero que el agente no
controla (GitHub CI)**, y que **solo entonces** se considere hecho y se pueda fundir.

> Regla raíz: **NINGUNA afirmación de "hecho" sin un check verde en GitHub que la respalde.** Si no hay check,
> no está hecho — está, como mucho, "propuesto".

---

## 1. El algoritmo (para CUALQUIER tarea pedida)

```
HACER(tarea T):
  1. ARNÉS PRIMERO. Escribe una prueba ejecutable que codifique "lo que se pide":
       - falla SIN la solución (rojo verificado), pasa CON ella (verde).
       - si T toca comportamiento de servidor → incluye una prueba EN VIVO (scripts/live_smoke.py).
       - si T toca cifras/€/fechas → invariantes (fuzz) + casos límite (auditoría).
     Sin arnés NO se empieza. Una tarea sin prueba chequeable no es "hecho posible".

  2. IMPLEMENTA T hasta que el arnés pase.

  3. GATE LOCAL (la puerta canónica):
       python scripts/verify.py --strict --live
     Si está ROJO → NO se sube. Se arregla. (Predicción ≠ hecho.)

  4. SUBE solo si el gate local está VERDE:
       git push  (rama por cambio)

  5. GITHUB CONFIRMA. El CI (.github/workflows/ci.yml) corre EL MISMO gate (--strict --live)
     en runners que el agente NO controla. El check `quality` es el árbitro.
       - check VERDE  → ESTO, y solo esto, es el recibo de "hecho". Se puede fundir.
       - check ROJO   → NO está hecho. El agente lo arregla y vuelve a 3. No discute con el check.

  6. EL AGENTE NUNCA DECLARA "HECHO". Reporta "propuesto · gate local verde · esperando a GitHub" hasta
     que el check de GitHub está verde. El estado 🟢 lo otorga el check, no la narración.
```

---

## 2. La puerta canónica — un solo gate, tres lo corren

`scripts/verify.py` es la **única** puerta. La corren **el hook de pre-commit, el CI y el agente** — el
mismo código, sin drift (§GOB-2). Niveles acumulativos:

| Nivel | Qué añade | Caza |
|---|---|---|
| normal | black + ruff (`.`) + pytest (incl. goldens e inyección) + auditorías deterministas + fuzz de invariantes | regresión · higiene · falsos +/− · violación de invariantes |
| `--strict` | **mutation testing** | tests **de mentira** (tautológicos, sin dientes) |
| `--live` | **test en vivo**: arranca el servidor real y ejerce los endpoints por HTTP | que el sistema **corriendo** se comporte como se pide |

**El CI corre `--strict --live`** → el merge exige TODO lo comprobable. El hook corre el nivel normal
(rápido); CI es el superconjunto estricto que re-confirma.

---

## 3. Qué SÍ garantiza y qué NO (honestidad de límite)

- **SÍ:** que el comportamiento conocido no ha regresado; que el camino crítico (€, fechas, cobros, 303,
  routing, seguridad) cumple invariantes sobre miles de casos; que los tests tienen dientes; que el sistema
  corriendo responde como se pide. Todo **reproducible por el humano** (`python scripts/verify.py --strict --live`)
  y **confirmado por GitHub**.
- **NO (residuo declarado):** un check verde **no** prueba que el diseño sea el mejor, ni cubre código sin
  arnés, ni —de momento— detecta automáticamente una afirmación 🟢 falsa en prosa. Por eso la **regla nº1**
  sigue viva: el agente etiqueta honesto y, sobre todo, **deja que el check sea quien diga "hecho"**.
- **Pendiente (siguiente vuelta de §GOB):** `validate_brujula.py` (compilar la tabla norma→mecanismo),
  prohibir `--no-verify` de forma efectiva, e independencia auditor≠constructor (§GOB-3).

---

## 4. Cómo lo verifica el humano (sin fiarse del agente)

1. **El check de GitHub** en el PR (pestaña *Actions* / el check `quality`): verde o rojo, lo pone GitHub.
2. **Reproducir el gate** en local: `python scripts/verify.py --strict --live`.
3. **Leer el diff**, no la narración: `git diff main...<rama>`.
4. **Ver qué se tocó**: `git log --oneline`.

Si el agente dice "verde" y el check está rojo, se ve al instante. Esa es la idea: **la verdad no pasa por
la palabra del agente.**
