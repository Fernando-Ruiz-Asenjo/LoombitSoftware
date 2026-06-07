# Plan Maestro — Loombit a 100% operatividad y 100% autonomía supervisada

Fecha: 2026-06-07. Documento vivo. Honestidad obligatoria (ver DEFINITION_OF_DONE.md).

## 0. Qué significa "100%" (sin ambigüedad)

Dos métricas separadas. No se mezclan.

**Operatividad 100%** = cada capacidad anunciada del alcance elegido está en estado
🟢 (DoD): funciona contra el servicio real, con recibo, ruta de fallo y test. Cero
capacidades 🟡 vendidas como hechas.

**Autonomía supervisada 100%** = para los flujos del alcance elegido, el operador
completa el bucle entero sin que el humano tenga que hacer el trabajo manual, pero
**aprobando cada acción externa**:

```
PERCIBIR (correo/calendario/documentos reales)
   -> PLANEAR (acciones + entidades + riesgos)
      -> PREPARAR (borradores/artefactos locales, sin efecto externo)
         -> PEDIR APROBACIÓN (resultado humano, no JSON)
            -> EJECUTAR (solo tras aprobación)
               -> RECIBO (auditable)
                  -> APRENDER (memoria operativa)
```

"Con supervisión" = humano en el bucle en el paso EJECUTAR para todo efecto externo.
La autonomía está en PERCIBIR→PLANEAR→PREPARAR y en anticipar; nunca en disparar
acciones externas a ciegas.

## 1. Decisión estratégica previa: foco

El mayor riesgo del proyecto anterior fue la dispersión (oficina + industrial +
inspección + rover + acuático + deportes + robótica a la vez). **Antes de la Fase 1
hay que elegir UNA cuña y congelar el resto.**

Recomendación: **Operador Local de Oficina para PYMES/autónomos en España**, con un
primer flujo vertical concreto (propuesta: *seguimiento de cobros* o *intake de
facturas*, porque tienen entrada clara, valor medible y baja ambigüedad legal).

Todo lo demás (industrial, acuático, rover, Jetson-robótica) pasa a `docs/PARKED.md`:
no se borra, pero sale del camino crítico hasta cerrar la cuña 1.

> Decisión pendiente de Fernando: ¿cuña 1 = "seguimiento de cobros" o "intake de
> facturas"? El plan abajo sirve para cualquiera de las dos.

## 2. Fases (cada una con criterio de salida medible)

### Fase 0 — Fundación limpia  ·  Salida: repo nuevo verde
- Repo `loombit-operator` con estructura por routers, CI con black+ruff+cobertura.
- `DEFINITION_OF_DONE.md` y `AGENTS.md` activos.
- Migrar del repo viejo solo el núcleo que ya es 🟢/sano (ver MIGRACION).
- **Hecho cuando:** CI verde en `main`, `main.py` < 100 líneas montando routers.

### Fase 1 — Verdad de conectores (cerrar la brecha "fake-tested")  ·  Salida: 1 correo real
Este es el paso que convierte el "humo honesto" en producto.
- Crear app OAuth real en Google Cloud (cliente, redirect, scopes mínimos: Gmail send, Calendar events, People readonly).
- Flujo OAuth local: authorization-url -> callback -> token store redactado -> refresh -> disconnect.
- **Enviar 1 correo real** a una cuenta de prueba. **Crear 1 evento real.** Probar refresh y 3 rutas de fallo.
- **Hecho cuando:** existen recibos 🟢 de envío de correo y creación de evento contra cuenta real, y la ruta de fallo bloquea limpio.

### Fase 2 — Percepción real (read-only)  ·  Salida: brief real del día
- Lectura read-only de Gmail (hilos, etiquetas), Calendar (eventos) y Drive/documentos locales aprobados.
- EvidenceGraph construido desde datos reales del usuario (no demo_workspaces).
- Morning brief generado desde correo/calendario reales.
- **Hecho cuando:** el operador produce un brief del día con datos reales y consentimiento explícito por fuente.

### Fase 3 — Bucle de autonomía supervisada end-to-end (cuña 1)  ·  Salida: 1 flujo cerrado
- Implementar el flujo vertical elegido completo: percibir -> planear -> preparar -> aprobar -> ejecutar -> recibo -> aprender.
- Gates de seguridad: destinatario identificado, actor verificado, permiso de fuente, política de empresa.
- **Hecho cuando:** un caso real del flujo recorre el bucle entero con aprobación humana y deja recibos en cada paso, repetible 5 veces sin intervención manual fuera de la aprobación.

### Fase 4 — UI humana  ·  Salida: panel sin JSON
- Dashboard que muestra "listo / bloqueado / necesita configuración" y resultado humano; el JSON técnico queda en panel de detalle bajo demanda.
- Acciones: pedir trabajo, ver, aprobar/editar/cancelar, ver recibo.
- **Hecho cuando:** un usuario no técnico completa el flujo de la Fase 3 sin ver JSON.

### Fase 5 — Memoria y aprendizaje operativo continuo  ·  Salida: daemon estable
- Ciclo de aprendizaje desde casos/recibos/preferencias corriendo de forma recurrente.
- Convierte patrones estables en plantillas propuestas o tickets de skill (con gate de calidad).
- **Hecho cuando:** el daemon corre programado, registra ciclos y propone al menos una plantilla a partir de casos reales. (NO es fine-tuning de pesos; es memoria operativa.)

### Fase 6 — Endurecimiento y Skill Pilot navegador  ·  Salida: seguro y auditable
- Registro de consentimiento, scope por fuente, pausa/revoca/export fáciles.
- Skill Pilot: pasar de "secuencias explícitas" a planner + verifier sobre navegador y accesibilidad Windows.
- Revisión de seguridad (subagente) de toda ruta con efecto externo.
- **Hecho cuando:** existe export de recibos, revoca de fuente en 1 clic, y el Skill Pilot completa una tarea de navegador verificada.

### Fase 7 — Edge / Jetson  ·  Salida: benchmark real
- Portar runtime a Jetson Orin NX, servir Qwen con llama.cpp/llama-server, medir latencia/tok-s reales.
- **Hecho cuando:** hay un benchmark real sobre la placa (requiere comprar hardware). Hasta entonces, todo "Jetson" se marca 🟡.

## 3. Orden recomendado y por qué

Fases 0→1→2→3→4 son el camino crítico al producto vendible (oficina). 5 y 6 endurecen.
7 es paralelo y depende de comprar hardware. **No tocar 7 hasta cerrar 3.**

## 4. Riesgos y cómo los matamos

- **Volver a la dispersión** -> `docs/PARKED.md` + DoD bloquean alcance fuera de cuña 1.
- **"Hecho" falso** -> DoD con recibo real obligatorio en cada PR.
- **Monolito** -> límite de ~400 líneas/fichero y main.py solo monta routers.
- **Fuga de datos de cliente** -> consentimiento por fuente, todo local, secretos fuera del repo.
- **Dependencia de un solo proveedor** -> capa de conectores con modos (local_outbox/SMTP/Google/Microsoft) ya existe; mantenerla.

## 5. Métrica de avance (tablero simple)

Operatividad = nº capacidades 🟢 / nº capacidades anunciadas en la cuña 1.
Autonomía = nº pasos del bucle automatizados (con aprobación) / 7.
Ambas deben llegar a 100% **solo dentro de la cuña 1** antes de abrir la cuña 2.
