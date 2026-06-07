# Migración desde jetson-ai-operator

Nace limpio, pero no tiramos lo bueno. Criterio: solo migra lo que es 🟢 o núcleo sano.

## Traer (núcleo blanco sano)
- `runtime`, `config` (settings Pydantic), `safety` (política determinista), `telemetry`.
- `skill_blanca_connector_execution.py` — bien diseñado; revísalo contra el DoD y márcalo 🟠 hasta el piloto real (Fase 1).
- `skill_blanca_oauth.py`, `skill_blanca_operational_config.py`.
- `lm_jobs.py`, `llm.py`, `skill_loader.py`.
- Tests de contrato existentes (renómbralos como 🟡).

## Reescribir al traer
- `main.py` (2674 líneas) -> NO se migra tal cual. Se reparte en `routers/` por dominio.
- Documentación de estado -> aplicar emojis de estado del DoD; quitar "Confirmed Working" sobre capacidades 🟡.

## NO traer (al menos no al camino crítico)
- `experiments/EXP_001.../training/` — artefactos de prompts/respuestas del LLM. A repo/rama aparte.
- Skills fuera de la cuña 1 (industrial, inspección, remote-site, rover, acuático, deportes) -> ver PARKED.md.

## Cómo
1. Copiar módulo a `loombit_operator/`.
2. Extraer sus rutas de `main.py` a un `routers/<dominio>.py`.
3. Pasar `black`, `ruff`, `pytest`.
4. Marcar estado real (🟡/🟠/🟢) en el doc del módulo.
