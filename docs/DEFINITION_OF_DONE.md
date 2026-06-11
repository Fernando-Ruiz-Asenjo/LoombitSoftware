# Definition of Done (DoD) — Loombit

Una capacidad pasa por tres estados y solo uno cuenta como "hecho". El objetivo de
este documento es que **nadie** (ni Codex, ni un modelo local, ni yo) pueda volver
a decir "ya está" sin prueba.

> **Canónico (§GOB-2b, D-66): «hecho» lo declara GitHub, no el agente.** El árbitro de 🟢 es un **check
> verde en GitHub CI** corriendo el gate canónico `scripts/verify.py --strict --live` — no la palabra de
> nadie. Algoritmo completo: `docs/PROTOCOLO_VERIFICACION_CANONICO.md`.

## Los tres estados

| Estado | Qué significa | Evidencia exigida |
|---|---|---|
| 🟡 Contrato (mock) | El código compila y los tests con HTTP simulado pasan | Test en `tests/` que inyecta `http_post`/`http_get` falsos |
| 🟠 Parcial | Funciona contra el servicio real solo bajo condiciones | Recibo de 1 ejecución real + lista explícita de lo que falta |
| 🟢 Hecho | Funciona contra el servicio real, repetible, con seguridad | Ver checklist 🟢 abajo |

"fake-tested" en la documentación significa 🟡. Nunca 🟢.

## Checklist 🟢 "Hecho" (capacidad con efecto externo)

Una skill/conector con efecto externo (correo, evento, escritura, compra) está
🟢 solo si TODO esto es cierto y está enlazado en el PR:

1. Credenciales reales configuradas fuera del repo (`.env` / token store).
2. **Una ejecución real contra una cuenta de prueba** (no mock) completada.
3. Recibo auditable guardado en `runtime/local/` (JSON) con el efecto externo y el ID del proveedor.
4. Ruta de fallo probada (token caducado / permiso faltante / destinatario inválido → bloqueo limpio con motivo).
5. Gate de aprobación humana antes del efecto externo (autonomía supervisada).
6. Rollback o "deshacer" documentado, o justificación de por qué no aplica.
7. Test automatizado del contrato (🟡) que no se rompe.
8. La UI muestra resultado humano, no JSON crudo.

## Checklist 🟢 "Hecho" (capacidad solo-lectura / local)

1. Lee/escribe únicamente dentro de roots aprobados (consentimiento explícito).
2. Una ejecución real sobre datos reales del usuario, con recibo.
3. No filtra datos fuera de la máquina.
4. Test de contrato verde.

## Regla de redacción en STATE/README

- Prohibido listar capacidades 🟡 bajo un encabezado "Confirmed Working".
- Cada capacidad lleva su emoji de estado. Si no tiene emoji, se considera 🟡.
