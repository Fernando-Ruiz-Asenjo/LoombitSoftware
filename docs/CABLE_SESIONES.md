# El CABLE — conectar una sesión de la nube con una sesión del PC

> Conecta **esta** sesión (la nube, p. ej. Claude Code on the web) con una sesión que corre en
> **tu PC**, sin túnel ni pantalla remota. El medio que ambas alcanzan es **git**: un buzón sobre la
> rama `loombit-bridge`. La nube deja comandos; el PC los ejecuta y devuelve el resultado.

## Por qué así (y no control remoto directo)

La sesión de la nube vive en un contenedor aislado: **no** alcanza tu pantalla, ratón ni `127.0.0.1`
de tu equipo. Lo único que ambos lados comparten es el repositorio en GitHub. Por eso el cable es un
**buzón git** asíncrono (latencia de segundos), no una conexión en vivo.

Respeta la LEY FUNDACIONAL de Loombit: lo remoto **nunca** ejecuta a ciegas. Por defecto, **tú apruebas
cada comando en el PC** antes de que corra (`--gate prompt`).

## Arranque (lado PC — pégalo en la sesión de tu equipo, desde la carpeta del repo)

```
git pull
python scripts/bridge_local.py            # bucle; te pregunta s/N por cada comando
```

Variantes:

- `python scripts/bridge_local.py --once` — procesa lo pendiente y sale.
- `python scripts/bridge_local.py --gate allowlist` — sin preguntar, solo ejecuta lo que case con
  `scripts/bridge_allowlist.txt` (útil si la sesión del PC es un agente sin humano al teclado).
- `python scripts/bridge_local.py --gate off` — sin gate (bajo tu responsabilidad).

## Uso (lado nube — lo hace la sesión remota)

```
python scripts/bridge_send.py --init                       # crea la rama-buzón (una vez)
python scripts/bridge_send.py --shell powershell "Get-Date"
python scripts/bridge_send.py --shell bash "uname -a" --timeout 120
```

`bridge_send.py` encola el comando, lo empuja y espera en `outbox/` hasta que el PC responde.

## Protocolo

Rama `loombit-bridge`, ramas de datos efímera (no mezclar con código):

- `inbox/<id>.json` — comando de la nube: `{id, ts, shell, cmd, cwd}`.
- `outbox/<id>.json` — resultado del PC: `{id, ts, cmd, exit, stdout, stderr, approved}`.

El PC no re-ejecuta un comando que ya tenga su `outbox/<id>.json`.

## Límites honestos

- **Asíncrono**, no tiempo real: depende del intervalo de sondeo y de `git push/fetch`.
- No es pantalla remota ni control del ratón: ejecuta **comandos**, devuelve **texto**.
- Requiere que ambos lados tengan acceso de escritura al repo y red a GitHub.
- El gate humano por defecto es lo que impide que la nube sea una puerta trasera a tu PC.
