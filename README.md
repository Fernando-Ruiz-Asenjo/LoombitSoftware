# Loombit Operator

**Operador de IA local-first que teje contexto, memoria y acciones en el mundo real.**

Loombit Operator es un runtime de operador de IA con un **núcleo blanco** (genérico y
reutilizable) que adquiere comportamiento de dominio mediante **skills instalables**.
El mismo binario sirve como operador administrativo de oficina, auditor industrial,
nodo de inspección o cerebro de robótica, según las skills y el hardware instalados.

Desarrollo en Windows + WSL + Docker. Despliegue final en NVIDIA Jetson Orin NX.

> Este repositorio sucede a `jetson-ai-operator`. Nace limpio, con foco y con una
> regla innegociable: **una capacidad no está "hecha" sin una ejecución real con
> recibo.** Ver `docs/DEFINITION_OF_DONE.md`.

## Objetivo del producto

Llevar a Loombit a:

1. **100% de operatividad** — cada capacidad anunciada funciona contra servicios
   reales (no contra mocks), verificada con un piloto y un recibo auditable.
2. **100% de autonomía supervisada** — para los flujos del alcance elegido, el
   operador percibe contexto real, planea, prepara, **pide aprobación humana**,
   ejecuta tras la aprobación, guarda recibo y aprende. Humano en el bucle en
   toda acción externa.

El plan detallado está en `docs/PLAN_MAESTRO_100.md`.

## Documentos fuente de verdad

- `docs/PLAN_MAESTRO_100.md` — hoja de ruta hacia 100% operatividad + autonomía supervisada.
- `docs/CAPACIDADES_Y_HERRAMIENTAS.md` — con qué construimos cada fase (conectores, skills, runtime).
- `docs/DEFINITION_OF_DONE.md` — qué significa "hecho" (regla de honestidad).
- `docs/MIGRACION_DESDE_jetson-ai-operator.md` — qué traer del repo anterior y qué dejar.

## Arranque de desarrollo

```bash
python -m pip install -r requirements.txt
python -m pytest
# python -m uvicorn loombit_operator.main:app --port 8787   (cuando exista main.py)
```

## Reglas de arquitectura

- El núcleo permanece blanco: el comportamiento de dominio vive en skills/routers.
- `main.py` solo crea la app y monta routers. Ningún fichero supera ~400 líneas.
- Credenciales y datos privados de cliente nunca entran al repositorio.
- "fake-tested" (mock) prueba el contrato del código, **no** la operatividad real.

## Estado

Fase 0 — fundación limpia. Ver `docs/PLAN_MAESTRO_100.md` para el avance por fases.
