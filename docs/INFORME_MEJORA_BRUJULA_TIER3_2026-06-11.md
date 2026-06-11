# Informe de mejora — BRÚJULA y gobierno · TIER 3 (el techo de los techos)

**Fecha:** 2026-06-11 · **Autor:** agente (Claude), a petición de Fernando ("termina este informe
hasta llegar al techo de los techos").
**Qué es:** el cierre de la serie. Tier 1 (dar dientes a cada norma) → Tier 2 (unificar, hacer el
sistema auto-empujarse, independencia) → **Tier 3 (el límite real, y por qué no hay un Tier 4 que no
sea esto mismo dicho de otra forma).**

---

## La pregunta honesta: ¿existe el techo?

Sí, y se puede nombrar. El gobierno de un agente no sube infinitamente: choca con **cuatro verdades
irreducibles**. El techo de los techos es el diseño que las alcanza a todas y reconoce que más allá ya
no es ingeniería de Loombit, sino física, matemática y psicología humana.

---

## Verdad 1 — No puedes hacer SEGURO al LLM; solo puedes SACARLO de la base de confianza

**Dato, no opinión** (verificado en la investigación): incluso un modelo *entrenado explícitamente*
contra su constitución la viola bajo presión, y la tasa baja entre generaciones **pero nunca llega a 0**
(15,0 %→2,0 % en la familia Claude; arXiv 2605.24229). Corolario duro: **toda estrategia que dependa de
que el LLM "se comporte" tiene un suelo de fallo > 0 por construcción.**

El techo, entonces, no es "alinear mejor el 14B". Es **minimizar la Base de Confianza (TCB,
*Trusted Computing Base*)**: el conjunto de cosas que *tienen* que ser correctas para que Loombit sea
fiable. El asíntota es:

> **El LLM aporta CERO a toda decisión consecuente.** Todo lo consecuente (€, fechas, IBAN, impuestos,
> qué tool se ejecuta y con qué parámetros, el efecto externo) lo decide un **núcleo determinista
> pequeño y verificable** + el **gate humano**. Lo que el LLM hace (entender, narrar, proponer) es, por
> construcción, **incapaz de causar daño** porque nunca toca el camino de control de confianza.

Esto es la **Ley de Separación de Autoridades** del Tier 2 §1 llevada a su extremo: no es una norma más,
es el *invariante* que define el techo. El Capability Policy Plane es su implementación; el techo es que
ese plano sea **toda** la superficie consecuente, y que sea **pequeño**.

---

## Verdad 2 — El piso formal: probar, no testear

Testear es muestrear; el adversario juega en el espacio que no muestreaste. El piso por encima del
testing es **demostrar propiedades**:

- Especificar el Policy Plane en un **sistema de tipos de flujo de información** (information-flow
  typing): etiquetar cada dato como `confiable`/`no-confiable` y **probar la no-interferencia** — *un
  dato no-confiable (cuerpo de un correo, web, doc) no puede influir en una salida o un control
  consecuente.* Esta es la dirección de **CaMeL formal** (arXiv 2503.18813), no su versión en prompt.
- El núcleo fiscal/contable como **funciones puras verificables** (property-based testing exhaustivo →
  y donde el riesgo lo justifique, verificación formal de las invariantes: "el 303 nunca asigna una
  compra al bucket de ventas", "una cuenta por cobrar nunca es negativa") en vez de goldens puntuales.

**Coste medido, no gratis** (verificado): la seguridad demostrable de CaMeL resolvió el 77 % de tareas
frente al 84 % sin defensa — **~7 puntos de utilidad a cambio de garantía**. El techo no es "prueba todo":
es **probar el núcleo consecuente y solo ese**, donde el coste de utilidad se paga porque el daño es real
(fiscal, dinero, efectos externos). Fuera de ahí, el coste de probar supera el beneficio (Verdad 4).

---

## Verdad 3 — El residuo que NINGÚN gobierno elimina (aquí está el techo de verdad)

Por encima de la TCB mínima formalmente verificada, queda un residuo **irreducible**. Nombrarlo ES el
techo, porque pretender eliminarlo es el autoengaño definitivo:

1. **El gate humano es socialmente atacable.** Ponemos al humano en el lazo porque la decisión necesita
   juicio — pero el humano se puede engañar (un correo que fabrica urgencia para que Fernando apruebe sin
   mirar). Mitigable (mostrar procedencia, resaltar lo anómalo, IBAN nuevo en rojo), **nunca eliminable**.
2. **La brecha spec ≠ intención.** Puedes *probar* que el código cumple la especificación; **no puedes
   probar que la especificación es lo que Fernando de verdad quería.** Es el límite tipo Gödel/frame
   problem del gobierno: la última milla entre "correcto" y "lo correcto" la cierra un humano, siempre.
3. **La base sigue teniendo cimientos que confías a ciegas:** los pesos del modelo local (un 14B
   envenenado en origen), el SO, el hardware (Jetson), las dependencias (cadena de suministro). La TCB se
   *encoge*, no desaparece.
4. **El suelo de fallo > 0** (Verdad 1). El DoD honesto de seguridad **nunca dice "0 %"**; dice "<X %
   medido + defensa en profundidad + detección del resto". Cualquier informe que prometa 0 es teatro.

**Implicación de brújula:** una norma de cierre — *"la seguridad y la corrección son `defensa en
profundidad MEDIDA + residuo declarado`, nunca un absoluto. Quien prometa 0 % o 100 %, miente
(regla nº1)."* Esto ya vive en el espíritu de "predicción ≠ hecho"; el Tier 3 lo hace literal.

---

## Verdad 4 — El meta-techo: el gobierno también tiene ROI negativo (saber PARAR)

El error final, el más sutil, es creer que más gobierno siempre es mejor. No lo es: un mecanismo que
cuesta 10 % de utilidad por 0,5 % de garantía **resta**. El techo de los techos no es "máximo gobierno"
— es **gobierno PROVABLEMENTE MÍNIMO**:

> El conjunto **más pequeño** de mecanismos que alcanza la garantía, con una **regla permanente contra
> el bloat de gobierno**: cada mecanismo nuevo justifica su coste de utilidad, y el sensor (Tier 2 §4)
> puede *retirar* (Tier 2 §5) el que deja de pagarse. **Un sistema que gobierna su propio gobierno y se
> detiene cuando el coste marginal supera la seguridad marginal.**

Aplicado a Loombit: la TCB mínima + el núcleo formal del riesgo real + el gate humano + el sensor que
vigila la deuda — y **nada más**. 40 documentos que se contradicen no son "mucho gobierno": son
*entropía*, lo contrario del gobierno. El techo es *menos, demostrado*, no *más, esperado*.

---

## Por qué NO hay un Tier 4 (de ingeniería)

Cualquier "siguiente piso" que se proponga cae en una de estas cuatro verdades:
- ¿"Mejor modelo que no falle"? → Verdad 1: suelo > 0, sácalo de la TCB.
- ¿"Más pruebas / más formal"? → Verdad 2: ya está, y tiene coste; aplícalo solo al núcleo.
- ¿"Defensa total"? → Verdad 3: el residuo (humano, spec≠intención, hardware) es irreducible.
- ¿"Más mecanismos de control"? → Verdad 4: pasa el ROI a negativo; el techo es mínimo, no máximo.

Lo que queda *por encima* ya **no es ingeniería de Loombit**: es teoría de la computación (spec≠intención),
psicología (ingeniería social del gate), y seguridad de cadena de suministro/hardware. Se gestionan
(procedencia, mostrar lo anómalo, firmar dependencias, modelo de confianza del hardware), no se
"resuelven". **Ese es el techo de los techos: una TCB mínima formalmente verificada, un residuo
declarado con honestidad, y un gobierno que sabe cuándo parar.**

---

## El techo, en una página (lo que la brújula v2 debe encarnar)

1. **Invariante fundacional:** el LLM, cero en el camino de control consecuente. Todo lo demás cuelga de aquí.
2. **Superficie única:** Capability Policy Plane = toda la autoridad consecuente, y pequeña.
3. **Núcleo probado:** information-flow + invariantes fiscales demostradas donde el daño es real; testing fuera.
4. **Independencia:** quien construye ≠ quien audita; mutantes y held-out adversariales y opacos.
5. **Auto-empuje:** sensor de drift + deuda normativa que el sistema lee primero; no depende de que Fernando empuje.
6. **Honestidad de límite:** `<X% medido + residuo declarado`, nunca 0/100; el gate humano y la brecha
   spec≠intención son parte del diseño, no un fallo a ocultar.
7. **Mínimo, no máximo:** gobierno provablemente mínimo, que retira lo que no se paga y se detiene.

> **¿Hay algo por encima de esto?** No de ingeniería. Por encima está aceptar que la fiabilidad perfecta
> no existe y diseñar para el residuo con honestidad — que es, exactamente, la regla nº1 de la brújula
> llevada hasta el final. **El techo de los techos del gobierno de Loombit es la honestidad, hecha
> arquitectura.**
