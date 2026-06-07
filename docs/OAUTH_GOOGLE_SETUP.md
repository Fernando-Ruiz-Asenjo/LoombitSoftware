# Configurar Google OAuth (Fase 1 / bloqueador #28)

Esta guía desbloquea Gmail send y Calendar create (🟡 → 🟢). El código del flujo
OAuth ya está implementado (`routers/skill_blanca_oauth.py` + `skill_blanca_oauth.py`).
Lo único que falta son las **credenciales** y conectar la cuenta una vez.

> Las credenciales viven **solo en `.env`** (gitignored). Nunca en `.env.example`
> ni en ningún fichero versionado.

## 1. Credenciales en Google Cloud Console

1. Entra en <https://console.cloud.google.com/> con la cuenta del proyecto
   **LOOMBIT ADMINISTRATIVO** (client_id `171458314429-…apps.googleusercontent.com`).
2. **APIs y servicios → Biblioteca**: habilita (si no lo están):
   - Gmail API
   - Google Calendar API
   - People API
3. **APIs y servicios → Pantalla de consentimiento OAuth**:
   - Tipo *Externo* (o *Interno* si es Workspace propio).
   - En *Usuarios de prueba* añade la cuenta de Gmail con la que vas a probar.
   - Scopes: `gmail.send`, `calendar.events`, `contacts.readonly`.
4. **APIs y servicios → Credenciales → ID de cliente de OAuth**:
   - Crea (o convierte) un cliente de tipo **"App de escritorio"** — es el que
     permite la redirección a `127.0.0.1` (loopback) y usa **PKCE**. En este tipo
     el `client_secret` no es confidencial y es opcional.
   - En **URIs de redirección autorizados** añade **exactamente**:
     ```
     http://127.0.0.1:8787/skill-blanca/oauth/google/callback
     ```
   - Copia el **client_id** (y el `client_secret` si lo hubiera). El token que se
     obtenga se guarda **cifrado en reposo** con el almacén de credenciales del SO.

## 2. Configurar `.env`

En `C:\Users\fernando\loombit-new\.env` ya están puestas las claves. Solo pega el secret:

```ini
LOOMBIT_OPERATOR_SKILL_BLANCA_GOOGLE_OAUTH_ENABLED=true
LOOMBIT_OPERATOR_SKILL_BLANCA_GOOGLE_CLIENT_ID=171458314429-…apps.googleusercontent.com
LOOMBIT_OPERATOR_SKILL_BLANCA_GOOGLE_CLIENT_SECRET=<pega aquí el secret real>
LOOMBIT_OPERATOR_SKILL_BLANCA_GOOGLE_REDIRECT_URI=http://127.0.0.1:8787/skill-blanca/oauth/google/callback
```

Sustituye `PEGA_AQUI_EL_CLIENT_SECRET` por el valor real.

## 3. Arrancar y conectar la cuenta

```powershell
# Si el puerto 8787 está ocupado por una instancia vieja:
netstat -ano | findstr :8787
taskkill /PID <pid> /F

python -m loombit_operator.launcher
```

1. Comprueba que está listo:
   `GET http://127.0.0.1:8787/skill-blanca/oauth/google/status`
   → debe mostrar `enabled: true, configured: true, connected: false`.
2. Obtén la URL de autorización:
   `GET http://127.0.0.1:8787/skill-blanca/oauth/google/start`
   → copia `authorization_url` y ábrela en el navegador.
3. Acepta los permisos con la cuenta de prueba. Google redirige a `/callback`,
   que intercambia el `code` y guarda el token en `runtime/local/`.
   Verás una página "✅ Google conectado".
4. Confirma: `GET …/google/status` → `connected: true`,
   `access_token_present: true`, `refresh_token_present: true`.

## 4. Cerrar la Fase 1 (DoD)

Para pasar Gmail send y Calendar create a 🟢 (ver `docs/DEFINITION_OF_DONE.md`):

- [ ] Enviar **1 correo real** a una cuenta de prueba y guardar recibo en `runtime/local/`.
- [ ] Crear **1 evento real** en Google Calendar y guardar recibo.
- [ ] Probar **refresh** de token (caduca el access_token y se renueva con el refresh).
- [ ] Probar **3 rutas de fallo**: token caducado, permiso/scope faltante, destinatario inválido.

Desconectar (borra el token local, reversible, no toca `.env`):
`DELETE http://127.0.0.1:8787/skill-blanca/oauth/google/disconnect`
