# Piloto: enviar un recordatorio de cobro REAL por Gmail (D-90)

> El primer **🟢 externo** de la cuña: que un recordatorio salga de verdad por tu Gmail. Esto se corre
> **en tu equipo** (el agente, desde la nube, no llega a tu navegador ni a tu cuenta de Google).
>
> Seguridad (§SEG-4): durante el piloto **TODO** envío por Gmail va a un **destino seguro** (tu buzón),
> **nunca a un cliente real**. El destino seguro acordado es `admin@construiaapp.com`.

## 0. Pre-requisitos

- Google OAuth conectado una vez (ver `docs/OAUTH_GOOGLE_SETUP.md`).
- En `.env` (gitignored, nunca versionado):

```ini
LOOMBIT_OPERATOR_SKILL_BLANCA_GOOGLE_OAUTH_ENABLED=true
LOOMBIT_OPERATOR_SKILL_BLANCA_CONNECTOR_WRITES_ENABLED=true
LOOMBIT_OPERATOR_COBROS_PILOTO_DESTINO_SEGURO=admin@construiaapp.com
```

## 1. Arrancar y comprobar OAuth

```powershell
python -m loombit_operator.launcher
# GET http://127.0.0.1:8787/skill-blanca/oauth/google/status  →  connected: true
```

Si `connected: false`, sigue `docs/OAUTH_GOOGLE_SETUP.md` (start → autorizar → callback).

## 2. Crear una factura vencida (datos de prueba)

```bash
curl -X POST http://127.0.0.1:8787/cuentas -H "Content-Type: application/json" \
  -d '{"cliente":"Cliente Demo SL","importe":1210.0,"vencimiento":"2026-05-01"}'
```

## 3. Ver el cobro pendiente y copiar su `cuenta_id`

```bash
curl http://127.0.0.1:8787/cobros/pendientes
```

## 4. Aprobar → ENVÍO REAL por Gmail (al destino seguro)

```bash
curl -X POST http://127.0.0.1:8787/cobros/aprobar -H "Content-Type: application/json" \
  -d '{"cuenta_id":"<EL_ID_DEL_PASO_3>","via":"gmail"}'
```

Respuesta esperada (recibo 🟢):

```json
{ "ok": true, "cuenta_id": "...",
  "recibo": { "enviado": true, "via": "gmail", "destino": "admin@construiaapp.com",
              "recibo": { "message_id": "...", "dod": "🟢", "receipt_path": "runtime/local/..." } } }
```

## 5. Confirmar el 🟢 (DoD)

- [ ] Llega el correo a **admin@construiaapp.com** (no a ningún cliente).
- [ ] El cuerpo lleva las cifras EXACTAS por código (saldo + 40 € art. 8 + interés de demora → total reclamable).
- [ ] Queda el recibo JSON en `runtime/local/skill_blanca_connector_outbox/` con `message_id` y `dod: 🟢`.

Con eso, `envio-cobro` pasa de 🟡 a **🟢** (servicio real + recibo). Guarda el recibo.

## Notas

- `via` omitido o `"outbox"` → escribe un `.eml` local (sin credenciales). Útil para ensayar sin enviar.
- `via:"gmail"` sin `COBROS_PILOTO_DESTINO_SEGURO` configurado → **422** (no envía a ciegas).
- Sin aprobación (no llamar a `/aprobar`) → no sale nada. El gate de efecto vive dentro del envío.
- **Frontera:** esto envía el recordatorio; la presentación VeriFactu a la Sede AEAT sigue fuera (certificado).
