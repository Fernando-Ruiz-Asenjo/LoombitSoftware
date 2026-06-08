# Servidor MCP de Loombit (`Skill A`)

> Expone las capacidades de Loombit como un **servidor MCP** (Model Context
> Protocol), el estándar abierto para que clientes/agentes descubran y llamen
> herramientas. Corresponde a la tendencia **#5 (Servidor MCP)** del roadmap.
>
> **Estado: 🟢 protocolo · 🟡 capacidades envueltas.** El servidor habla MCP de
> verdad (verificado con un cliente MCP independiente real, ver "Recibo"); las
> herramientas que expone heredan el estado de su conector (p.ej. `calendar_create`
> sigue 🟡 hasta su primer evento real).

## Por qué

Hace de Loombit algo que **otros agentes pueden conducir** (Claude Desktop,
Cursor, otro Loombit, el MCP Inspector…) sin acoplarse a su HTTP interno. Es el
reverso del flywheel: igual que Loombit pilota apps, ahora puede ser pilotado de
forma estándar y segura. Y, por diseño, **reutiliza el `tool_registry`**: no hay
catálogo duplicado.

## Arquitectura (Skill A reemplazable, sin lógica de dominio)

```
loombit_operator/
├── mcp_server.py        ← lógica de protocolo PURA (JSON-RPC 2.0 + métodos MCP).
│                          Refleja el tool_registry; cero lógica de dominio.
└── routers/mcp.py       ← wiring HTTP (transporte Streamable HTTP): POST /mcp.
```

- Es un **adaptador**: si cambia el `tool_registry`, el servidor MCP cambia solo.
- No asume sector ni cliente; no mueve vocabulario al núcleo (cumple la taxonomía).
- **Cero dependencias nuevas**: el protocolo se implementa sobre FastAPI + el JSON
  que ya usamos (no se añade el SDK `mcp`).

### Métodos soportados

| Método | Qué hace |
|---|---|
| `initialize` | Negocia versión de protocolo y anuncia capacidades + `serverInfo` + `instructions`. |
| `notifications/initialized` | Notificación del cliente (sin respuesta → HTTP 202). |
| `tools/list` | Catálogo del registry: `name`, `description`, `inputSchema`, `annotations` y `_meta.loombit`. |
| `tools/call` | Ejecuta una tool **respetando el gate** (ver abajo). |
| `ping` | Salud. |

Versiones de protocolo: `2025-06-18`, `2025-03-26`, `2024-11-05` (negocia a la
pedida si la soporta; si no, a la más reciente). Soporta mensajes sueltos y batch.

## El GATE de seguridad (regla nº 1 de Loombit)

**El operador nunca ejecuta un efecto externo sin aprobación humana.** Un cliente
MCP arbitrario no es de fiar para hacer ese human-in-the-loop, así que el gate
vive **en el servidor** (defensa en profundidad). Una `tools/call` se **bloquea**
(no se ejecuta; devuelve `isError: true` con `status: requires_human_approval` y
los argumentos preparados) si la tool:

- tiene `requires_approval=True` (p.ej. `gmail_send`, `calendar_create`, `run_shell`), **o**
- es de categoría `pilot` o `computer` (controla ratón/teclado/pantalla del usuario), **o**
- tiene `safety_class` sensible (`safety_sensitive` / `blocked_by_default`).

Las tools de **lectura/preparación** (leer fichero, listar carpeta, `gmail_search`,
`contacts_find`, `web_fetch`, `read_invoice`…) **sí** se ejecutan al llamarlas.

`GET /mcp/info` resume en claro qué tools se auto-ejecutan y cuáles exigen aprobación.

## Cómo arrancarlo

El router se monta con el resto en `main.py`, así que con Loombit en marcha ya está:

```powershell
python -m loombit_operator.launcher            # :8787, endpoint en /mcp
# o, aislado, en otro puerto:
python -m uvicorn loombit_operator.main:app --port 8799
```

## Conectar un cliente MCP

**MCP Inspector (oficial, para probar):**
```bash
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8787/mcp \
    --transport http --method tools/list
```

**Claude Desktop / Cursor** (config `mcpServers`, transporte HTTP):
```json
{
  "mcpServers": {
    "loombit": { "type": "http", "url": "http://127.0.0.1:8787/mcp" }
  }
}
```

## Recibo (🟢 de protocolo)

Verificado contra el **app real** (uvicorn) con **dos clientes**:

1. `scripts/mcp_probe.py` (cliente httpx sobre TCP real) — handshake + `tools/list`
   (47 tools) + `tools/call` de lectura ejecutada + `gmail_send` bloqueado.
2. **MCP Inspector oficial** (`@modelcontextprotocol/inspector`, cliente
   independiente) — `tools/list` y `tools/call`: `list_directory` ejecuta
   (`isError:false`); `gmail_send` → `isError:true`, `requires_human_approval`,
   **sin enviar nada**.

Reproducir: arranca Loombit y `python scripts/mcp_probe.py http://127.0.0.1:8787/mcp`.
El recibo se guarda en `runtime/local/mcp_server/receipt_protocol.json`.

## Limitaciones / siguiente

- **🟡 de las capacidades envueltas**: el servidor habla MCP 🟢, pero cada tool
  hereda su estado real (p.ej. `calendar_create` 🟡 hasta su primer evento real).
- Stateless (sin sesiones MCP ni stream servidor→cliente): el `GET /mcp` responde
  405. Suficiente para tools; si en el futuro se quieren *prompts/resources* o
  notificaciones servidor→cliente, se añade la capa SSE.
- Pendiente (opcional): exponer **resources** (recibos, expedientes en
  `runtime/local/`) y **prompts** del oficio administrativo; un modo "solo lectura"
  configurable; autenticación si alguna vez se expone fuera de `127.0.0.1`.
```
