"""
recipients.py — Skill W Administration Core: resolución determinista de destinatario.

Cierra F3: ante varias coincidencias para un nombre ("Jana"), elige la MÁS PROBABLE por
**confianza de la fuente** y **frecuencia de trato** — no la adivina el modelo. Y NUNCA ofrece un
contacto `auto` (capturado de un envío, no verdad confirmada): así el `jana.espinal` cristalizado
no puede volver a colarse. Si hay empate real entre fuentes fiables, devuelve "ambiguo" → preguntar.

Neutro: no sabe de correos ni IVA; consume `Candidato` y devuelve el orden. El dominio decide qué
hacer con el resultado (lo usa el tool `contacts_find`).
"""

from __future__ import annotations

from dataclasses import dataclass

# Confianza por procedencia: lo confirmado (manual/google) manda; lo auto-capturado NO resuelve.
_TRUST = {"manual": 2, "google": 2, "auto": 0}


@dataclass
class Candidato:
    name: str
    email: str
    source: str = "google"  # google | manual | auto
    veces: int = 0  # frecuencia de trato (times_contacted)

    @property
    def confianza(self) -> int:
        return _TRUST.get(self.source, 0)


def rank_candidatos(cands: list[Candidato]) -> list[Candidato]:
    """Dedup por email (se queda con la mayor confianza/frecuencia) y ordena por confianza y luego
    por frecuencia. Determinista (desempate estable por nombre)."""
    por_email: dict[str, Candidato] = {}
    for c in cands:
        email = c.email.lower().strip()
        if not email:
            continue
        prev = por_email.get(email)
        if prev is None:
            por_email[email] = c
        else:
            mejor_fuente = prev.source if prev.confianza >= c.confianza else c.source
            por_email[email] = Candidato(
                prev.name or c.name, email, mejor_fuente, max(prev.veces, c.veces)
            )
    return sorted(por_email.values(), key=lambda c: (c.confianza, c.veces, c.name), reverse=True)


def resolver_destinatario(
    cands: list[Candidato],
) -> tuple[str, Candidato | None, list[Candidato]]:
    """Devuelve (estado, mejor, ranking). estado ∈ {resuelto, ambiguo, vacio}.
    Excluye los `auto`: no son fuente fiable de resolución (raíz del bug `jana.espinal`)."""
    ranking = rank_candidatos([c for c in cands if c.confianza > 0])
    if not ranking:
        return "vacio", None, []
    if len(ranking) == 1:
        return "resuelto", ranking[0], ranking
    a, b = ranking[0], ranking[1]
    empatan = (a.confianza, a.veces) == (b.confianza, b.veces)
    return ("ambiguo", None, ranking) if empatan else ("resuelto", ranking[0], ranking)
