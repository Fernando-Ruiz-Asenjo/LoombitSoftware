# BLINDAJE — cómo se protege el muro, y cómo se auto-protege

> Pedido por Fernando (2026-06-12): «arregla los fallos, blinda el método en GitHub, y blinda que si
> pides bajar el blindaje te bloqueen». Esto documenta lo que YA había + lo que se añadió, con honestidad
> sobre qué está enforced y qué es un interruptor tuyo.

## Lo que YA existía en `main` (no se duplicó)
- **Guardian del gate:** `tests/test_gate_integridad.py` — falla si se debilita `verify.py`, si el CI deja
  de correr `--strict --live`, si se borran tests en masa (suelo 885), si bajan los iters de fuzz, o si se
  vacía un candado. Corre en el check **`quality`** (requerido + `enforce_admins`) → **ya enforced**.
- **Mutación:** `scripts/mutation_test.py`. **Brújula/conducta:** `tests/test_brujula_cumplimiento.py`,
  `tests/test_conducta.py` (+ `conducta.py`, recibos cuantificables).
- **Auditor independiente:** `.github/CODEOWNERS` enruta TODO el repo a `@construiaapp` (auditor ≠ constructor).

## Lo que se AÑADIÓ (radar 2026-06-12)
1. **Hook local `~/.claude/hooks/blindaje_guard.py`** (PreToolUse): bloquea al agente si intenta
   `--no-verify`, `push --force`, túneles (cloudflared/ngrok), debilitar branch protection, apagar hooks,
   quitar black/ruff/pytest del CI, ampliar `_HOSTS_LOCALES`, o desactivar el propio guardia. **Verificado
   en vivo** (14/14 + prueba de fuego). Se gestiona desde la UI `/hooks`.
2. **`.github/workflows/branch-protection.yml`** — branch-protection-as-code **auto-curativo**: re-aplica el
   estado fuerte (checks `[quality]`, `enforce_admins`, review de CODEOWNERS obligatoria, sin force-push) en
   cron/push → debilitar a mano es efímero. Blindado por `tests/test_blindaje_branch_protection.py`.

## INTERRUPTORES que dependen de TI (tu cuenta; no se fuerzan)
1. **Activar la review obligatoria del auditor** (cierra el gap honesto del CODEOWNERS, `reviews=0` hoy):
   ```bash
   gh api -X PUT repos/Fernando-Ruiz-Asenjo/LoombitSoftware/branches/main/protection --input - <<'JSON'
   { "required_status_checks": {"strict": true, "contexts": ["quality"]},
     "enforce_admins": true,
     "required_pull_request_reviews": {"require_code_owner_reviews": true, "required_approving_review_count": 1},
     "restrictions": null, "allow_force_pushes": false, "allow_deletions": false }
   JSON
   ```
   Tras esto, cada PR exige el Approve de `@construiaapp` (tu auditor) → no te auto-bloquea como dueño.
2. **PAT para la auto-curación**: crea un PAT con `admin:repo` y guárdalo como secret `BLINDAJE_PAT`
   (Settings → Secrets → Actions). Sin él, el workflow de auto-curación avisa y no corre.
3. **OpenSSF Allstar** (vigilancia continua + reversión externa, defensa en profundidad): instala la app
   `ossf/allstar` en el repo y añade su config de `branch_protection` con `action: fix`. *(No incluido en
   este PR porque su formato de config conviene verificarlo contra el README de Allstar antes de afirmarlo
   — honestidad: no doy por hecho lo que no he probado en vivo.)*
