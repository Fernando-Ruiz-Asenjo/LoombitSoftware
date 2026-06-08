"""
galaxia.py — agrega el negocio del usuario como un "sistema estelar" (sol · planetas · aristas).

Es el cerebro de datos de la vista Galaxia (`docs/GALAXIA_LOOMBIT.md`): NO inventa nada, solo
**agrega lo que ya existe** en un grafo `{sol, nodos, aristas}`:

- **Sol** = la entidad (empresa del usuario, de la memoria) + KPIs vivos (total a cobrar, vencidas,
  aprobaciones pendientes, correos sin leer).
- **Planetas-contacto** = a quién más tratas (de Enviados, reusa `routers/home._contactos_de_gmail`),
  con `peso` = frecuencia y `temperatura` = intensidad de trato (brillo).
- **Planetas-cuenta** = cuentas a cobrar (de `cuentas_cobrar`), con `estado` (vencida/proxima/
  pendiente) y `dias` a vencer → la vista las acerca al centro cuanto más urgentes (gravedad semántica).
- **Aristas contacto↔cuenta** = la relación cliente↔factura (por nombre/dominio). **No se pintan por
  defecto** (anti-"hairball", §10 del diseño): solo al hacer foco en un planeta.

Determinista; el LLM no interviene. `store` y `contactos` son inyectables para tests aislados
(nunca se tocan Gmail ni el store de producción en los tests).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

from .cobros import days_overdue
from .config import AppSettings, get_settings
from .cuentas_cobrar import CuentasCobrarStore

# Formas societarias y conectores que NO identifican a una contraparte (evitan falsos positivos
# al casar contacto↔cuenta): "Acme SL" casa con el contacto de Acme por "acme", no por "sl".
_STOP = {
    "sl",
    "sa",
    "slu",
    "sau",
    "scp",
    "sociedad",
    "limitada",
    "anonima",
    "the",
    "and",
    "del",
    "las",
    "los",
    "com",
    "www",
    "gmail",
    "hotmail",
    "outlook",
    "yahoo",
}


def _norm(s: str) -> str:
    """minúsculas + sin acentos (para casar 'José' con 'jose')."""
    nfkd = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _tokens(s: str) -> set[str]:
    """Tokens significativos de un nombre (>=3 chars, sin formas societarias ni dominios genéricos)."""
    return {t for t in re.split(r"[^a-z0-9]+", _norm(s)) if len(t) >= 3 and t not in _STOP}


def _tokens_contacto(c: dict) -> set[str]:
    """Tokens que identifican a un contacto: su nombre + local-part y dominio del email."""
    email = (c.get("email") or "").lower()
    local, _, dominio = email.partition("@")
    raiz_dominio = dominio.split(".")[0] if dominio else ""
    return _tokens(c.get("name", "")) | _tokens(local) | _tokens(raiz_dominio)


def _empareja(contacto_tokens: set[str], cuenta_cliente: str) -> bool:
    """¿La cuenta (por su `cliente`) pertenece a este contacto? Solapamiento de tokens significativos."""
    return bool(contacto_tokens & _tokens(cuenta_cliente))


def _nombre_entidad() -> str:
    try:
        from .agent.memory import get_memory

        owner = get_memory().owner
        return owner.get("company") or owner.get("name") or "Mi negocio"
    except Exception:
        return "Mi negocio"


def _aprobaciones_pendientes() -> int:
    try:
        from .agent import AgentStatus
        from .agent.run import AgentStore

        return len(AgentStore().list(status=AgentStatus.PENDING_APPROVAL))
    except Exception:
        return 0


def _contactos_por_defecto(settings: AppSettings) -> tuple[list[dict], str]:
    """Contactos reales: Enviados (frecuencia) con fallback a memoria. Honesto: '' si no hay."""
    from .routers.home import _contactos_de_gmail, _contactos_de_memoria

    contactos = _contactos_de_gmail(settings)
    if contactos:
        return contactos, "gmail"
    contactos = _contactos_de_memoria()
    return contactos, ("memoria" if contactos else "vacio")


def _correos_sin_leer(settings: AppSettings, contactos: list[dict]) -> int | None:
    """Best-effort: nº de correos sin leer (14 días) de tus contactos. None si no hay scope/token
    (Gmail readonly da 403 hasta publicar la app) — la vista lo oculta en ese caso."""
    try:
        import httpx

        from .skill_blanca_oauth import fresh_access_token

        token = fresh_access_token(settings, "google")
        emails = [c["email"].lower() for c in contactos if c.get("email")]
        if not token or not emails:
            return None
        q = "is:unread newer_than:14d from:(" + " OR ".join(emails) + ")"
        with httpx.Client(timeout=8) as cl:
            r = cl.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers={"Authorization": f"Bearer {token}"},
                params={"q": q, "maxResults": 50},
            )
            if r.status_code != 200:
                return None
            return len(r.json().get("messages", []))
    except Exception:
        return None


def build_galaxia(
    *,
    settings: AppSettings | None = None,
    today: str | date | None = None,
    store: CuentasCobrarStore | None = None,
    contactos: list[dict] | None = None,
) -> dict:
    """Agrega el sistema estelar del negocio en `{sol, nodos, aristas, meta}`.

    `store` y `contactos` inyectables para tests (sin Gmail ni store de producción).
    """
    settings = settings or get_settings()

    # 1) Planetas-contacto (peso=frecuencia, temperatura=intensidad de trato)
    if contactos is None:
        contactos, fuente = _contactos_por_defecto(settings)
    else:
        fuente = "inyectado"
    max_veces = max((int(c.get("veces", 1) or 1) for c in contactos), default=1) or 1
    nodos: list[dict] = []
    indice_contactos: list[tuple[str, set[str]]] = []
    for c in contactos:
        email = (c.get("email") or "").lower()
        if not email:
            continue
        nid = f"c:{email}"
        peso = int(c.get("veces", 1) or 1)
        temperatura = round(0.35 + 0.65 * (peso / max_veces), 3)  # brillo en [0.35, 1.0]
        nodos.append(
            {
                "id": nid,
                "tipo": "contacto",
                "etiqueta": c.get("name") or email.split("@")[0],
                "email": email,
                "peso": peso,
                "temperatura": temperatura,
            }
        )
        indice_contactos.append((nid, _tokens_contacto(c)))

    # 2) Planetas-cuenta (estado por semáforo, dias=urgencia) + 3) aristas contacto↔cuenta
    store = store or CuentasCobrarStore(settings=settings)
    aristas: list[dict] = []
    for cu in store.pendientes():
        od = days_overdue(cu.vencimiento, today)  # >0 = vencida
        faltan = -od  # >0 = aún no vence; <=0 = vencida (días en negativo)
        if od > 0:
            estado = "vencida"
        elif 0 <= faltan <= 7:
            estado = "proxima"
        else:
            estado = "pendiente"
        nid = f"f:{cu.id}"
        nodos.append(
            {
                "id": nid,
                "tipo": "cuenta",
                "etiqueta": cu.cliente,
                "importe": cu.importe,
                "estado": estado,
                "dias": faltan,  # urgencia: <=0 vencida, pequeño = inminente → la vista la acerca al centro
                "vencimiento": cu.vencimiento,
                "concepto": cu.concepto,
            }
        )
        for cnid, ctokens in indice_contactos:
            if _empareja(ctokens, cu.cliente):
                aristas.append({"origen": cnid, "destino": nid, "tipo": "cliente"})

    # 4) Sol + KPIs vivos
    pend = store.pendientes()
    sol = {
        "nombre": _nombre_entidad(),
        "kpis": {
            "total_cobrar": round(sum(c.importe for c in pend), 2),
            "vencidas": len(store.vencidas(today)),
            "proximas": len(store.proximas(7, today)),
            "aprobaciones": _aprobaciones_pendientes(),
            "correos_sin_leer": _correos_sin_leer(settings, contactos),
        },
    }

    return {
        "sol": sol,
        "nodos": nodos,
        "aristas": aristas,
        "meta": {
            "fuente_contactos": fuente,
            "generado": datetime.now().isoformat(timespec="seconds"),
            "n_contactos": sum(1 for n in nodos if n["tipo"] == "contacto"),
            "n_cuentas": sum(1 for n in nodos if n["tipo"] == "cuenta"),
            "n_aristas": len(aristas),
        },
    }
