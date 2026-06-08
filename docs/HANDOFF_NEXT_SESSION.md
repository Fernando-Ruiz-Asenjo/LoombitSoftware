# Handoff — contexto para la siguiente sesión

> Estado al cerrar la sesión del 2026-06-08 (larga, centrada en el correo + codificar la disciplina).
> Repo canónico: `C:\Users\fernando\loombit-new`. Entorno: `.venv` (Python 3.12). `main` sincronizado con `origin`.

## Cómo se trabaja aquí (innegociable, ya en código)
- **Verificar antes de afirmar.** Puerta única: `python scripts/verify.py` (black + ruff + pytest con el eval-set F1-F8). El **hook `.githooks/pre-commit` BLOQUEA** el commit si está en rojo (`git config core.hooksPath .githooks`).
- **Publicar verificando el remoto:** `python scripts/publish.py` (empuja la rama actual y comprueba `origin == HEAD`). NUNCA cantar "pushed OK" por el eco (esta sesión se coló un push falso por estar en otra rama).
- **Probar EN VIVO**, no asumir. Cada arreglo lleva su **eval** (`evals/`). Auto-chequeo: `/health/selfcheck` y `python -m evals.runner` (corre solo al arrancar el server y avisa si hay rojo).
- **12-factor:** identificadores/dinero/identidad en código (guardas fail-closed); el LLM solo donde aporta juicio. **NO inventar datos.**
- **Proactividad:** investigar en internet y proponer mejoras **sin que lo pida Fernando** (routine "Mejora continua"). Método completo en `docs/METODO_INGENIERIA_IA_LOOMBIT.md` y `AGENTS.md`.
- **Fernando** quiere honestidad brutal, fricción 0 en el producto, odia que le pregunten obviedades y que se afirme sin verificar. Repo local-first; el humano aprueba efectos externos y consentimientos OAuth.

## Resuelto esta sesión (correo/contactos — F1-F8, taxonomía en `evals/taxonomy.py`)
Verificado EN VIVO contra el 14B: el agente pide el email de Jana (no lo inventa, no dice "Espinal") y firma los correos como Fernando.
- **F1** no pregunta el asunto · **F2** no inventa destinatario (guarda fail-closed: solo email del usuario o de `contacts_find`) · **F4** no se delata como bot **y firma como el dueño** (el `run()` del loop ahora inyecta la memoria/identidad) · **F5** no cristaliza ni "lava" contactos (procedencia; `contacts_find` no se cachea; procedimientos sin datos literales) · **F7** normaliza `\n` literal · **F3** resuelve por confianza+frecuencia y busca en "otros contactos".
- Arranque sólido: `venv` 3.12 + `scripts/start_loombit.ps1` + `Loombit.vbs` + icono de escritorio (sin PyInstaller).
- UI estilo Google: panel izquierdo con **Procesos diarios** + **Contactos habituales** (`routers/home.py`).
- **Bóveda de credenciales** cifrada (`credentials.py` + `routers/credentials.py`): das una credencial una vez, Loombit la usa.
- **Observador Pilot semántico** (`pilot/observer.py`, opt-in, OFF): app/ventana, **NUNCA teclas ni pantalla** (no keylogger).

## Bloqueado en una acción de Fernando
- **Publicar la app Google OAuth a "Producción"** (Google Cloud Console → Pantalla de consentimiento OAuth → "Publicar app"). Es **uso personal → sin verificación de Google**; quita la caducidad de 7 días del modo "Testing" → deja de pedir re-autorización. Hasta entonces, `gmail.readonly` y `contacts.other.readonly` dan **403**, así que NO encuentra contactos por Gmail/otros-contactos (por eso pregunta el email).

## Pendiente / próximos pasos
1. ✅ **Pilot verificado EN VIVO (2026-06-08).** `scripts/pilot_demo.py` ejecutado en escritorio real: cartel + cursor real (movimiento determinista probado con log de coordenadas exactas) + abre Google Console. Además, **señal visible PROPIA de Loombit** añadida y verificada (D-18): **halo de perímetro violeta→cian + halo de cursor** en colores de marca (antes el halo era el naranja de Claude/Computer-Use, no de Loombit). 🟢. *Pendiente de cablear el overlay al executor del agente (hoy solo en el demo).*
2. Tras publicar la app Google: verificar que **"Contactos habituales"** se llena solo (analiza Enviados) y que el agente resuelve a la Jana real (otros-contactos).
3. **Cablear Pilot → bóveda** (autofill de logins con credenciales guardadas) + UI para añadir credenciales.
4. Procesos del panel sin tool del agente (Registrar factura, Reclamar cobro, Conciliación): cablearlos como tools (p.ej. `plan_cobro` sobre `cobros.py`) o marcarlos honestamente — hoy son medio callejón.
5. **Observador:** muestreo continuo opt-in + `resumen_procesos` → alimentar la Fábrica de Skills para **proponer automatizaciones**.
6. Cerrar **Fase 1**: 1 evento real en Calendar (mismo patrón que Gmail send, ya 🟢).

## Recordatorio del DoD
🟢 = funciona contra el servicio/realidad con recibo · 🟡 = código + tests sin piloto real · no marcar 🟢 lo que es 🟡.
