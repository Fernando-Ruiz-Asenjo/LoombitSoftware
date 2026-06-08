# Modelos locales de Loombit — inventario funcional

> Naming **por función** sin renombrar ficheros: el rol vive en la config del proyecto
> (`loombit_operator/config.py`) y aquí se documenta el mapeo. Así no se rompe el índice
> de LM Studio ni el auto-load (JIT). Servidor LM Studio: `http://localhost:1234/v1`.
> *Actualizado: 2026-06-08.*

## Mapeo función → modelo

| Función | Clave LM Studio (API `model`) | Params | Quant | Tamaño | Rol en config |
|---|---|---|---|---|---|
| **Instructor** (cerebro del agente ReAct) | `qwen2.5-14b-instruct` | 14B | Q4_K_M | 8.99 GB | `llm_model_name` (default) |
| **Coder** (código, JSON, estructuras) | `qwen2.5-coder-7b-instruct` | 7B | Q4_K_M | 4.68 GB | `llm_coder_model_name` |
| **Instructor-light** (fallback, contexto 1M) | `qwen2.5-7b-instruct-1m` | 7B | Q4_K_M | 4.68 GB | alternativa (no default) |
| **Visión** (ojos del Pilot, facturas escaneadas) | `qwen/qwen2.5-vl-7b` (+mmproj) | 7B | Q4_K_M | 6.04 GB | ⚠️ **sin cablear todavía** |
| **Embeddings** (memoria / RAG) | `text-embedding-nomic-embed-text-v1.5` | — | — | 84 MB | embeddings |

## Notas honestas (DoD)

- **El agente usa el rol por defecto** (`LLMClient()` en `agent/loop.py`) → su modelo es `llm_model_name`. Por eso el swap a 14B se hace ahí.
- **El swap a 14B está verificado** contra la API real (2026-06-08): ante "manda un correo…", el 14B **genera asunto y cuerpo y llama a `send_email` sin preguntar** (`finish_reason=tool_calls`). El 7B no seguía esa regla de forma fiable (ver commit `7d66ede`).
- **La visión (VL-7B) NO está cableada.** `docs_intel.py`/`docs.py` marcan la visión como *"pendiente"* y el Pilot es *accesibilidad-primero* (`tools/pilot.py`: "funcional sin vision"). El VL queda **descargado pero NO cargado**; se carga solo cuando se cablee la lectura de facturas escaneadas / pantalla.

## Cómo cargar (contexto y VRAM)

RTX 5080 16 GB. El instructor necesita contexto amplio (system prompt + tools + historial); el VL venía con 4096 (insuficiente).

```powershell
# Instructor 14B: contexto 16k, 1 slot, full GPU  (~8.4 GiB en VRAM)
lms load qwen2.5-14b-instruct -c 16384 --parallel 1 --gpu max -y

# Coder bajo demanda (JIT lo carga solo al primer uso del rol coder)
# Visión solo cuando se cablee:
# lms unload qwen2.5-14b-instruct   # libera VRAM si hiciera falta
# lms load qwen/qwen2.5-vl-7b -c 8192 --gpu max -y
```

**Estrategia VRAM:** instructor(14B) cargado por defecto; coder a JIT; VL solo on-demand
(14B ~8.4 GB + coder ~4.7 GB ≈ 13 GB caben; el VL 6 GB no entra a la vez con el 14B).

## Limpieza realizada (2026-06-08)
- Borrado `Qwen2.5-7B-Instruct-f16.gguf` (14.19 GB) — huérfano f16 en la raíz de
  `~/.lmstudio/models`, no indexado por LM Studio, duplicado del 7B que ya está en Q4_K_M.
