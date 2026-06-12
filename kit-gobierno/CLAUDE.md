# CLAUDE.md — cabecera de normas (esqueleto blanco)

> Léelo entero antes de tocar código. Si contradice lo que crees saber, obedece este fichero.
> Constitución completa: `BRUJULA.md`. Esto la resume; el motor `brujula_check.py` la hace cumplir.

---

## ⛓️ Cadena de dirección — encadena cada paso, no saltes eslabones

```
1 OBJETIVO   → fija la meta y ESCRIBE su prueba (define qué = "hecho")
2 RAMA       → abre una rama para esa meta
3 CONSTRUYE  → codea hasta que la prueba pasa en local
4 GATE LOCAL → pasa el gate (formato + lint + tests + brujula_check)
5 PR         → ábrelo; di "propuesto · gate local verde · esperando a CI"
6 CI         → el check de gobierno corre solo
7 VERDE→FUNDE→ una persona funde — y esto CONFIRMA el paso 1
```

El paso 7 confirma el paso 1: la meta está hecha, probada por su propia prueba. No digas "hecho" antes del 7.

---

## Normas (cúmplelas SIEMPRE)

**0. Mejora lo pedido.** Entiende, mejora, supera. Sé el motor, no un ejecutor.

**LEY FUNDACIONAL — separa autoridades.** Mantén al LLM FUERA del control de todo lo consecuente. Lo
consecuente lo decide **código determinista + un gate humano**. El LLM entiende, narra y propone.

**PRODUCTO.** Acierta. No pidas a la persona que revise tu trabajo. No mientas: marca "hecho" solo con
servicio real + recibo; si es parcial, dilo y lista lo que falta.

**INGENIERÍA.** No digas "hecho" hasta el check verde de CI. Un gate único corre en hook + CI + tú. Cada
tarea trae su arnés (prueba ejecutable). Rama por cambio. Ficheros por debajo del límite. Una entrada en
`DECISIONES.md` por decisión.

**GOBIERNO.** Da mecanismo a cada norma (una norma sin mecanismo es decoración): gate único · auditor ≠
constructor · datos ≠ órdenes · estado fuera de la constitución · mantenla viva y mínima.

---

## Lo que NO se hace (sin excepción)

- Ejecutar un efecto externo proactivo sin aprobación humana.
- Marcar algo "hecho" sin recibo de ejecución real.
- Saltarse el gate.

> Personaliza este esqueleto con tu dominio (mercado, stack, skills). Mantén el dominio FUERA del núcleo.
