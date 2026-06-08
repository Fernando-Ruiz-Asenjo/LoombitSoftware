# Nota para reconciliar al fundir `feat/mcp-server` (sesión paralela)

> No edito `DECISIONES.md` ni `ESTADO_Y_ROADMAP.md` para no colisionar con la
> sesión principal. Aquí dejo los parches propuestos; al fundir, trasládalos al
> sitio que toque (ajusta el número D-NN al siguiente libre).

## Entrada propuesta para `docs/DECISIONES.md` (siguiente libre, p.ej. D-23)

**D-23 — Servidor MCP: Loombit como servidor del Model Context Protocol (`Skill A`).** Estado 🟢 protocolo · 🟡 capacidades envueltas.
- *Elegido:* adaptador **puro sobre el `tool_registry`** (`mcp_server.py` = protocolo JSON-RPC 2.0; `routers/mcp.py` = transporte Streamable HTTP en `POST /mcp`). **Cero dependencias nuevas** (no se añade el SDK `mcp`): se implementa el protocolo sobre el JSON/FastAPI que ya hay. Refleja el registry → sin catálogo duplicado y reemplazable (cumple taxonomía: no mueve dominio al núcleo).
- *Gate (regla nº 1):* el human-in-the-loop **vive en el servidor**, no en el cliente. `tools/call` **bloquea sin ejecutar** (`isError` + `requires_human_approval`) toda tool con `requires_approval`, de categoría `pilot`/`computer` (control de escritorio) o `safety_class` sensible. Solo se auto-ejecutan lectura/preparación. Hallazgo: las `desktop_*` son categoría `pilot` (no `computer`) → se incluyó `pilot` explícitamente para no dejar abierto el control del ratón/teclado por MCP.
- *Recibo:* verificado contra el app real (uvicorn) con **dos clientes**: `scripts/mcp_probe.py` (TCP real) y el **MCP Inspector oficial** (independiente). Handshake + `tools/list` (47) + `tools/call` (lectura ejecuta, `gmail_send` bloqueado). Recibo en `runtime/local/mcp_server/`.
- *Alternativas descartadas:* (a) usar el SDK `mcp` como servidor stdio → añade dependencia pesada y proceso aparte, peor para local-first y para reusar el registry; (b) transporte SSE completo → innecesario para un server de solo-tools (stateless); se deja la puerta abierta para *prompts/resources*.
- *Reversible:* sí; es 1 módulo + 1 router + 1 línea de montaje en `main.py`. Quitarlo no afecta a nada más.

## Parche propuesto para `docs/ESTADO_Y_ROADMAP.md`

En "Adopción de tendencias IA", fila **#5 Servidor MCP**:

| 5 | Servidor MCP | ~~⬜ pendiente~~ → **🟢 protocolo / 🟡 capacidades** — adaptador sobre el `tool_registry`, transporte Streamable HTTP en `POST /mcp`, con gate de aprobación server-side; verificado con MCP Inspector real. Ver `MCP_SERVER_LOOMBIT.md`. |

(Opcional) En "Lo construido": añadir
- **Servidor MCP (`Skill A`)**: `mcp_server.py` + `routers/mcp.py`, 22 tests (protocolo + gate + HTTP e2e). Loombit expuesto como servidor MCP, sin deps nuevas, respetando los gates.
