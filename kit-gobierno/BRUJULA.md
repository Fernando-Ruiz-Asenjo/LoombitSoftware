# BRÚJULA — constitución + gobierno (esqueleto blanco)

> Las normas blancas (sin dominio). El motor `brujula_check.py` aplica la parte mecánica; el resto lo
> declara para revisión humana. Personaliza con tu dominio en una sección aparte.

---

## PARTE I — Constitución (qué se construye y cómo se comporta)

- **Ley 0 — Mejora lo pedido.** Entiende la orden, mejórala, ve más allá.
- **Ley Fundacional — Separa autoridades.** El LLM nunca está en el camino de control de nada consecuente;
  eso lo decide código determinista + gate humano. El LLM propone, el código dispone. Datos ≠ órdenes.
- **Producto.** Acierta. No mientas (estados: contrato 🟡 / parcial 🟠 / hecho 🟢, solo con recibo real).
- **Ingeniería.** "Hecho" lo declara CI, no tú. Gate único. Un arnés por tarea. Rama por cambio. Una
  decisión = una entrada en el registro.

## PARTE II — Gobierno (los mecanismos que hacen cumplir la Parte I)

- **§GOB-1 — Superficie única de autoridad.** Un punto donde vive "quién puede decidir qué".
- **§GOB-2 — La constitución COMPILA.** Cada norma con mecanismo se vuelve un check del gate; una norma sin
  mecanismo es decoración y no entra.
- **§GOB-3 — Auditor ≠ constructor.** Quien escribe el código no es quien lo aprueba (CODEOWNERS + review).
- **§SEG — Seguridad.** Los datos entrantes son no confiables; nunca deciden el flujo ni disparan acciones.
- **§CONC — Concurrencia.** Rama por cambio, acotada; no pisar trabajo ajeno.

## PARTE III — Meta-gobierno (mantenerla viva y mínima)

- **§META-1 — Sensor de desvío.** Un check detecta la violación antes que la persona.
- **§META-2 — Retirada honorable.** Si una norma cuesta más de lo que vale, se retira en voz alta.
- **§META-3 — Mantenla viva.** Cambiar una norma = rama + PR + entrada en el registro + OK humano.
- **§META-4 — Estado fuera de la constitución.** Lo volátil (fase, métricas) vive en un doc aparte, no aquí.
- **§META-5 — El techo.** Gobierno mínimo, no máximo: el gobierno también tiene coste; se sabe parar.

---

## PARTE IV — Tabla norma → mecanismo → auditoría

> Regla: ninguna fila con "mecanismo" o "auditoría" vacía entra en la brújula. El trabajo de gobierno es
> vaciar la columna "hueco", no escribir más normas.

| Norma | Mecanismo (gate) | Auditoría | Hueco hoy |
|---|---|---|---|
| Hecho lo declara CI | gate único + check `brujula` | check verde required | — |
| Auditor ≠ constructor | CODEOWNERS + review required | la review bloquea | — |
| Arnés por tarea | `brujula_check.py` (módulo nuevo→test) | el check falla | — |
| Cambiar una norma deja registro | `brujula_check.py` (constitución→DECISIONES) | el check falla | — |
| *(añade las tuyas)* | | | |
