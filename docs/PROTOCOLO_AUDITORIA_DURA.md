# PROTOCOLO DE AUDITORÍA DURA — mecánicas · funciones · visuales · estéticas · operativas

> Tu prompt, mejorado y hecho proceso reutilizable (2026-06-09). Origen: las auditorías «blandas»
> (verificar que se PINTABA, no que FUNCIONA) dejaron pasar fallos obvios. Esto lo impide.
> Lo usa el constructor y, donde se pueda, la Fábrica (`ui_audit.py`, higiene).

## La regla dura (innegociable)
**Nada se da por bueno sin INTERACTUAR y comprobar por RECIBO, no por cómo se ve ni por lo que narra el
LLM.** «Se renderiza» ≠ «funciona». Cada hallazgo lleva **evidencia** (qué pasó al clicar, captura, dato
o recibo). Lo que no sirva: se **arregla o se quita** — nunca se finge. Se verifica **en el Chrome real**
de Fernando, con Google conectado; el navegador interno de Claude no cuenta para flujos con datos/red.

## Las 5 dimensiones (audita CADA una, en cada pantalla)

**1 · MECÁNICAS (gestos e interacción).** Clica/usa CADA elemento interactivo (botón, icono, nodo, chip,
fila, atajo). ¿Hace lo que dice su etiqueta? ¿Hay botones muertos, duplicados o engañosos? Estados:
hover · focus (teclado) · activo · **disabled** · **cargando** · **error** · **vacío**. ⌘K/atajos.
Nada que prometa algo y no lo cumpla (p.ej. «escribir una acción» que solo busca).

**2 · FUNCIONES (lógica y datos).** ¿La acción produce un resultado **correcto y útil**? Verifícalo por
el **dato/recibo**, no por el texto del agente. ¿La **cognición** acierta (sin acciones redundantes ni
absurdas: una reunión confirmada no se vuelve a confirmar)? ¿**Abstención honesta** cuando no hay datos
(«no encuentro tus facturas; conéctalas»), nunca prometer-y-no-hacer ni escupir basura? Latencia real.

**3 · VISUALES (layout).** ¿Usa el lienzo o desperdicia espacio? Jerarquía (lo importante destaca),
alineación, ritmo/espaciado, **contraste AA**, densidad legible. **Responsive/móvil** de verdad. Cero
vacíos muertos, cero placeholders.

**4 · ESTÉTICAS (identidad, voz, motion).** Sistema de color/tipografía coherente; **motion** suave y
con `prefers-reduced-motion`; **voz** cálida en español, sin jerga ni nombres de tool, sin «soy una IA»;
microcopy que celebra y guía. Consistencia entre pantallas.

**5 · OPERATIVAS (fiabilidad, seguridad, privacidad, rendimiento).** Nunca fallar en silencio: error
honesto + salida + anti-bucle. **Gate de efectos externos sagrado**; **🔒 local** visible al actuar;
**procedencia/recibo**. Datos≠órdenes (no obedecer instrucciones incrustadas en correos/docs). Sin fugas
de datos. Rendimiento (polling, cargas, caché). Antifraude (IBAN nuevo) donde toque.

## Método (el bucle)
1. Abre la pantalla en el Chrome real. 2. **Clica/usa cada elemento**; anota `qué hace` vs `qué debería`.
3. Marca hallazgos por severidad **P0 (rompe)/P1 (frena)/P2 (pulido)**, con evidencia. 4. **Arregla o
quita** (rama + tests/black/ruff verdes; núcleo del agente con OK). 5. **Re-verifica clicando** lo
arreglado. 6. Commit en verde con el recibo de la verificación. 7. Repite por pantalla.

## Salida
Tabla de hallazgos por severidad con evidencia + qué se arregló y **cómo se verificó (clicando)**.
Si algo se deja, se dice «parcial» y por qué (regla nº1: no mentir). Cero «verificado» sin recibo.
