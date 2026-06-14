# Runner self-hosted — disparar Loombit en vivo desde GitHub sin subir credenciales

**Para qué:** que Claude (en la nube) pueda **ordenar a GitHub** ejecutar un flujo real (p. ej. el envío de
un cobro), GitHub lo **ejecute en TU ordenador**, guarde el **registro** de qué hizo y cómo fue, y Claude
**lea** ese registro — todo **sin que tu token de Google salga de tu máquina** (foso local-first).

El truco es un **runner self-hosted**: un proceso que corre en tu ordenador y recoge los trabajos que GitHub
le manda. La ejecución y las credenciales son locales; GitHub solo orquesta y registra.

## Alta del runner (una vez, con teclado — ~5 min)

1. En GitHub: **repo → Settings → Actions → Runners → New self-hosted runner**.
2. Elige tu sistema (Windows). GitHub te da los comandos exactos con un **token de registro** (no se puede
   pre-generar aquí; cópialos de esa pantalla). Algo como:
   ```powershell
   # descargar
   mkdir actions-runner; cd actions-runner
   # ... (Invoke-WebRequest del paquete que te muestra GitHub) ...
   # configurar (pega el token que te da GitHub)
   ./config.cmd --url https://github.com/Fernando-Ruiz-Asenjo/LoombitSoftware --token <TOKEN_DE_GITHUB>
   # arrancar
   ./run.cmd
   ```
3. Deja `./run.cmd` corriendo (o instálalo como servicio: `./svc.cmd install` + `./svc.cmd start`).
4. Comprueba en **Settings → Actions → Runners** que aparece **Idle** (verde).

## Requisitos cada vez que se dispare

- El runner está **activo** (Idle/online).
- **Loombit encendido** en tu equipo (`http://127.0.0.1:8787`) con **OAuth de Google conectado**.
- En tu `.env`: `LOOMBIT_OPERATOR_SKILL_BLANCA_CONNECTOR_WRITES_ENABLED=true` y
  `LOOMBIT_OPERATOR_COBROS_PILOTO_DESTINO_SEGURO=admin@construiaapp.com`.
- `python` disponible en el PATH del runner.

## Cómo se dispara

El workflow `.github/workflows/piloto-cobro.yml` es `workflow_dispatch` (botón "Run workflow" en la pestaña
**Actions**, o Claude lo dispara por API). Corre `scripts/piloto_cobro_vivo.py` en tu equipo → envío real →
el **recibo queda en el log del job**, que Claude lee.

> El workflow debe estar en la rama **por defecto** (`main`) para que aparezca el botón y para dispararlo por
> API. Por eso primero se funde el PR que lo trae; luego ya queda disponible.
