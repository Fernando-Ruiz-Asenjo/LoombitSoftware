# Kit de gobierno — instalar y BLINDAR

Un kit blanco y reutilizable que hace que **las normas y el `CLAUDE.md` se apliquen solos**: si un cambio
no las cumple, el check sale rojo y **no pasa**.

## Qué trae

| Fichero | Para qué |
|---|---|
| `brujula_check.py` | **El motor.** Mira el diff y BLOQUEA si no se aplica la parte mecánica de las normas. |
| `gobierno.workflow.yml` | El workflow de CI que corre el motor en cada PR. |
| `CLAUDE.md` | Esqueleto de la cabecera de normas (resumen que el agente lee cada turno). |
| `BRUJULA.md` | Esqueleto de la constitución + gobierno (las normas blancas). |
| `pull_request_template.md` | Obliga a rellenar la checklist del proceso en cada PR. |
| `CODEOWNERS` | Plantilla auditor≠constructor (quien escribe no se aprueba a sí mismo). |

## Instalar (5 minutos)

1. Copia al **raíz** de tu repo: `brujula_check.py`, `CLAUDE.md`, `BRUJULA.md`, `DECISIONES.md` (créalo vacío).
2. Copia `gobierno.workflow.yml` → `.github/workflows/gobierno.yml`.
3. Copia `pull_request_template.md` y `CODEOWNERS` → `.github/`.
4. En `brujula_check.py`, edita el bloque **CONFIG** (carpetas de código, carpeta de tests, límite de líneas).
5. En `CODEOWNERS`, pon la cuenta **auditora** (≠ la que programa) como dueña de los ficheros del gate.

## BLINDAR (los candados — sin esto es solo una señal, no un muro)

En **Settings → Branches** (o **Rules**) de tu repo, protege `main` con:

- ☑ **Require status checks to pass** → elige el check **`brujula`** (= "si no aplica, no pasa").
- ☑ **Require a pull request before merging** + **Require review from Code Owners** (auditor≠constructor).
- ☑ **Require linear history** + **Block force pushes** (historia inforjable, append-only).
- ☑ **Do not allow bypassing the above settings** (ata también a los admins).

Con eso, las normas dejan de depender de la buena voluntad: **el código que no las cumple no llega a `main`.**

## La verdad honesta (qué blinda y qué no)

- 🟥 **Blinda lo mecánico:** tamaño, arnés del módulo nuevo, registro de decisión al tocar normas, no saltar el gate.
- ⬜ **No mecaniza el juicio** (¿se entendió el problema?, ¿la UX es buena?): eso lo declara y lo manda a la
  **review humana** (Code Owner). Ninguna máquina lo hace verde — fingirlo sería mentir.

El muro real es **el check + la protección de rama**. El `CLAUDE.md` y las normas son la ley; este kit es
quien la hace cumplir.
