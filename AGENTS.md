# Guía de operación para agentes (humanos y de IA)

GitHub es la fuente de verdad para código, issues, PRs y CI. Cualquier helper
(Codex, modelos locales, Cowork, etc.) es reemplazable y debe respetar estas reglas.

## Regla nº1: no se puede mentir

Está prohibido marcar algo como "hecho", "funcionando" o "100%" sin cumplir la
`docs/DEFINITION_OF_DONE.md`. En concreto:

- "fake-tested" / mock = el contrato del código es correcto. NO es operatividad real.
- Una capacidad que toca un servicio externo (Gmail, Graph, Calendar, SMTP) solo
  está "hecha" tras **una ejecución real contra una cuenta de prueba, con recibo guardado**.
- Si algo es parcial, se dice "parcial" y se enlaza qué falta. Sin adornos.

## Disciplina permanente — CODIFICADA, no por recordatorio

Estas responsabilidades no dependen de que nadie las recuerde: las **fuerza el código**.

- **No se afirma "hecho" sin probarlo.** La puerta es `python scripts/verify.py` (black + ruff +
  pytest, que incluye el eval-set F1-F8). El **hook `.githooks/pre-commit` BLOQUEA el commit** si
  está en rojo (actívalo en un clon nuevo: `git config core.hooksPath .githooks`). CI corre lo mismo.
- **Cada arreglo lleva su eval.** El método es eval-driven (`docs/METODO_INGENIERIA_IA_LOOMBIT.md`):
  análisis de error sobre trazas reales → taxonomía → eval → medir. Auto-chequeo: `/health/selfcheck`
  y `python -m evals.runner`. El servidor lo corre solo al arrancar y avisa si hay rojo.
- **Probar EN VIVO, no asumir.** Lo que toca un servicio real (Gmail, Calendar, el 14B) se verifica
  contra el servicio real con recibo (DoD). Los evals `needs_llm` lo ejercitan.
- **No inventar datos** (destinatario, IBAN, NIF): resolver contra la fuente o preguntar. En código
  (guardas fail-closed), no confiado al modelo (principio 12-factor: el LLM solo donde aporta juicio).
- **Proactividad e innovación sin que se pida.** Traer ideas de vanguardia y **buscar métodos en
  internet** antes de construir. La routine **"Mejora continua"** lo codifica (propone próximos pasos
  + temas a investigar partiendo del auto-chequeo).

## Bucle de trabajo

1. Partir de un issue u objetivo documentado.
2. Leer `README.md`, `docs/PLAN_MAESTRO_100.md` y `docs/DEFINITION_OF_DONE.md` antes de tocar código.
3. Rama por cambio no trivial.
4. Cambios acotados al objetivo.
5. **Validar con `python scripts/verify.py`** (la puerta única) antes de dar por terminado. El
   pre-commit lo vuelve a correr y bloquea si falla.
6. PR con: objetivo, ficheros cambiados, salida de tests, y limitaciones conocidas.
7. Si bloqueado, documentar el bloqueo. No inventar.

## Reglas de código

- Módulos Python pequeños y explícitos. Ningún fichero > ~400 líneas.
- `main.py` solo monta routers; la lógica vive en módulos de dominio.
- Cada módulo de runtime nuevo trae al menos un test enfocado.
- Núcleo blanco y reutilizable; el dominio va en skills o product profiles.
- Credenciales y datos de cliente fuera del repo, siempre.
