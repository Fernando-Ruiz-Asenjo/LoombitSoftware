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

## Bucle de trabajo

1. Partir de un issue u objetivo documentado.
2. Leer `README.md`, `docs/PLAN_MAESTRO_100.md` y `docs/DEFINITION_OF_DONE.md` antes de tocar código.
3. Rama por cambio no trivial.
4. Cambios acotados al objetivo.
5. Validar antes de dar por terminado: `black --check`, `ruff check`, `pytest`.
6. PR con: objetivo, ficheros cambiados, salida de tests, y limitaciones conocidas.
7. Si bloqueado, documentar el bloqueo. No inventar.

## Reglas de código

- Módulos Python pequeños y explícitos. Ningún fichero > ~400 líneas.
- `main.py` solo monta routers; la lógica vive en módulos de dominio.
- Cada módulo de runtime nuevo trae al menos un test enfocado.
- Núcleo blanco y reutilizable; el dominio va en skills o product profiles.
- Credenciales y datos de cliente fuera del repo, siempre.
