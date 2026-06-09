"""
galaxia_intel.py — destila contexto REAL de las conversaciones de Gmail (sin inventar nada).

Para un contacto, lee sus correos recientes (enviados + recibidos) y extrae, **con procedencia**:
- los últimos asuntos + fechas (de qué va la relación, en sus propias palabras),
- importes en € que aparezcan **literalmente** en el texto (regex DETERMINISTA — el número NUNCA
  lo pone el LLM, como exige la disciplina del repo: D-09/D-14), cada uno con el correo de origen,
- referencias de factura/presupuesto mencionadas.

Read-only. Best-effort: si no hay token/scope, devuelve `{disponible: False}`. Es percepción: no
envía nada. El número se muestra junto al texto y asunto de donde sale → auditable, no inventado.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field

from .config import AppSettings, get_settings

# Importe pegado a € o EUR:  "1.250,00 €" · "1250€" · "1.250 EUR" · "350 euros"
_AMOUNT_POST = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)\s?(?:€|eur(?:os)?\b)",
    re.IGNORECASE,
)
# Importe con el símbolo delante:  "€ 1.250,00" · "EUR 350"
_AMOUNT_PRE = re.compile(
    r"(?:€|eur(?:os)?\b)\s?(\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)",
    re.IGNORECASE,
)
# Referencia de documento:  "factura F-2024-12" · "presupuesto 1043" · "nº 990" · "albarán 22/A".
# La referencia debe contener un DÍGITO (un nº de factura lo tiene) → así no cuela "factura de"
# ni la palabra "no" como si fuera "nº" (bug: la clase [ºo°] casaba la 'o' de "no").
_REF = re.compile(
    r"\b(factura|fra\.?|presupuesto|ppto\.?|albar[aá]n|pedido|invoice|n[º°]|núm\.?|nro\.?)\s*[:#]?\s*"
    r"([A-Za-z]{0,3}[-/]?\d[A-Za-z0-9\-/\.]{0,16})",
    re.IGNORECASE,
)


@dataclass
class ContactoIntel:
    email: str
    disponible: bool = False
    n_mensajes: int = 0
    ultimos_asuntos: list[dict] = field(default_factory=list)  # {asunto, fecha, mio}
    importes: list[dict] = field(default_factory=list)  # {raw, valor, asunto, fecha}
    referencias: list[dict] = field(default_factory=list)  # {ref, asunto}
    resumen: str = ""  # opcional (LLM, solo redacta a partir de asuntos reales)

    def to_dict(self) -> dict:
        return {
            "email": self.email,
            "disponible": self.disponible,
            "n_mensajes": self.n_mensajes,
            "ultimos_asuntos": self.ultimos_asuntos,
            "importes": self.importes,
            "referencias": self.referencias,
            "resumen": self.resumen,
        }


def normalizar_importe(raw: str) -> float | None:
    """'1.250,00' → 1250.0 (formato español: punto=miles, coma=decimal). Determinista.
    Si solo hay punto y deja 3 cifras detrás, es separador de miles ('1.250' → 1250)."""
    s = raw.strip().replace(" ", "")
    try:
        if "," in s:  # la coma es el decimal; los puntos son miles
            s = s.replace(".", "").replace(",", ".")
            return round(float(s), 2)
        if "." in s:
            entero, _, dec = s.rpartition(".")
            # '1.250' (3 cifras) = miles; '12.50' (2 cifras) = decimal
            s = (entero + dec) if len(dec) == 3 else s
            return round(float(s), 2)
        return float(s)
    except ValueError:
        return None


def _importes_de(texto: str) -> list[tuple[str, float]]:
    """Importes en € hallados LITERALMENTE en el texto, normalizados. Sin LLM."""
    out: list[tuple[str, float]] = []
    vistos: set[str] = set()
    for m in list(_AMOUNT_POST.finditer(texto)) + list(_AMOUNT_PRE.finditer(texto)):
        raw = m.group(1)
        val = normalizar_importe(raw)
        if val is None or val <= 0 or raw in vistos:
            continue
        vistos.add(raw)
        out.append((raw, val))
    return out


def _referencias_de(texto: str) -> list[str]:
    out: list[str] = []
    for m in _REF.finditer(texto):
        tipo = m.group(1).rstrip(".").lower()
        num = m.group(2).rstrip(".,/-")
        if tipo in {"n", "nº", "n°", "núm", "nro"}:
            tipo = "nº"
        ref = f"{tipo} {num}".strip()
        if ref not in out:
            out.append(ref)
    return out[:6]


def _texto_de_payload(payload: dict) -> str:
    """Extrae el texto plano de un mensaje Gmail (format=full), recorriendo las partes."""
    if not payload:
        return ""
    mime = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data")
    if mime == "text/plain" and data:
        return _b64(data)
    trozos: list[str] = []
    for parte in payload.get("parts", []) or []:
        trozos.append(_texto_de_payload(parte))
    if trozos:
        return "\n".join(t for t in trozos if t)
    # Sin text/plain: cae a text/html aplanado
    if mime == "text/html" and data:
        return re.sub(r"<[^>]+>", " ", _b64(data))
    return ""


def _b64(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "===").decode("utf-8", "replace")
    except Exception:
        return ""


def distill_contacto(
    email: str,
    *,
    name: str = "",
    settings: AppSettings | None = None,
    max_msgs: int = 8,
    use_llm: bool = False,
) -> ContactoIntel:
    """Destila contexto real de los correos con `email`. Read-only, best-effort."""
    settings = settings or get_settings()
    intel = ContactoIntel(email=email.lower())
    try:
        import httpx

        from .skill_blanca_oauth import fresh_access_token

        token = fresh_access_token(settings, "google")
        if not token:
            return intel
        h = {"Authorization": f"Bearer {token}"}
        q = f"from:{email} OR to:{email}"
        with httpx.Client(timeout=12) as c:
            r = c.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers=h,
                params={"q": q, "maxResults": max_msgs},
            )
            if r.status_code != 200:
                return intel
            msgs = r.json().get("messages", []) or []
            intel.disponible = True
            intel.n_mensajes = len(msgs)
            asuntos_vistos: set[str] = set()
            imp_vistos: set[str] = set()
            for m in msgs:
                mr = c.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{m['id']}",
                    headers=h,
                    params={"format": "full"},
                )
                if mr.status_code != 200:
                    continue
                data = mr.json()
                payload = data.get("payload", {})
                hdrs = {x["name"].lower(): x["value"] for x in payload.get("headers", [])}
                asunto = (hdrs.get("subject", "") or "(sin asunto)").strip()
                fecha = _fecha_corta(hdrs.get("date", ""))
                mio = email.lower() not in (hdrs.get("from", "").lower())
                if asunto not in asuntos_vistos:
                    asuntos_vistos.add(asunto)
                    intel.ultimos_asuntos.append(
                        {"asunto": asunto[:120], "fecha": fecha, "mio": mio}
                    )
                texto = f"{asunto}\n{data.get('snippet', '')}\n{_texto_de_payload(payload)}"
                for raw, val in _importes_de(texto):
                    clave = f"{val}"  # mismo importe en el hilo "Re:" → una vez (el más reciente)
                    if clave in imp_vistos:
                        continue
                    imp_vistos.add(clave)
                    intel.importes.append(
                        {"raw": raw, "valor": val, "asunto": asunto[:120], "fecha": fecha}
                    )
                for ref in _referencias_de(texto):
                    if ref not in [x["ref"] for x in intel.referencias]:
                        intel.referencias.append({"ref": ref, "asunto": asunto[:120]})
        intel.importes.sort(key=lambda x: x["valor"], reverse=True)
        intel.ultimos_asuntos = intel.ultimos_asuntos[:6]
        intel.referencias = intel.referencias[:8]
        if use_llm and intel.ultimos_asuntos:
            intel.resumen = _resumen_llm(name or email, intel.ultimos_asuntos)
    except Exception:
        return intel
    return intel


def _fecha_corta(date_header: str) -> str:
    """'Wed, 03 Jun 2026 10:12:00 +0200' → '2026-06-03'. Best-effort."""
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(date_header)
        return dt.date().isoformat() if dt else ""
    except Exception:
        return ""


def _resumen_llm(quien: str, asuntos: list[dict]) -> str:
    """Una línea de contexto de la relación a partir de los ASUNTOS reales. El LLM solo redacta;
    jamás aporta cifras (las cifras van por el camino determinista)."""
    try:
        from .llm import LLMClient

        lista = "; ".join(a["asunto"] for a in asuntos[:6])
        messages = [
            {
                "role": "system",
                "content": (
                    "Eres Loombit. En UNA frase en español, di de qué trata la relación con este "
                    "contacto basándote SOLO en los asuntos de correo que te paso. No inventes datos "
                    "ni cifras. Si no está claro, dilo brevemente."
                ),
            },
            {"role": "user", "content": f"Contacto: {quien}. Asuntos recientes: {lista}"},
        ]
        return LLMClient().chat(messages, max_tokens=80).content.strip()
    except Exception:
        return ""
