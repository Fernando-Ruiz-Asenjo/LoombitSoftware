"""
anticipacion.py — "la autonomía que se gana" (niveles A0–A3). Núcleo blanco, determinista.

Derivado del hábito (`habitos.py`), gradúa CUÁNTO anticipa Loombit un asunto:

  A0  Reactivo            — solo actúa si lo pides (o lo sueles ignorar → silencio).
  A1  Sugiere             — lo propone en el feed; aún no prepara.
  A2  Pre-redacta         — deja el borrador en preview, a un clic.
  A3  Anticipa y agenda   — lo prepara ANTES de que lo pidas, arriba del todo, con su contexto.

INVARIANTE (techo duro, codificado): NINGÚN nivel —ni A3— autoriza el efecto externo (enviar,
pagar, crear evento, borrar). Eso lo aprueba SIEMPRE el humano con un toque. Lo único que sube con
la confianza es la PREPARACIÓN y la PRIORIDAD. No existe "A4 = envía solo".

Transiciones: se SUBE con una racha de aprobaciones sin rechazo; se BAJA al instante con un rechazo
(se gana lento, se pierde rápido). Las cifras las decide el CÓDIGO, no el LLM.
Ver docs/INVESTIGACION_ASISTENTE_PROACTIVO_2026.md (§3).
"""

from __future__ import annotations

from typing import Any

NIVELES = ("A0", "A1", "A2", "A3")

ETIQUETAS = {
    "A0": "Reactivo — solo si lo pides",
    "A1": "Sugiere",
    "A2": "Pre-redacta (borrador a un clic)",
    "A3": "Anticipa y agenda",
}

# Racha de aprobaciones consecutivas (sin rechazo) para alcanzar cada nivel.
_UMBRAL_A2 = 3
_UMBRAL_A3 = 5


def nivel_desde_habito(habito: dict[str, Any], *, umbral_a3: int = _UMBRAL_A3) -> dict[str, Any]:
    """Nivel de anticipación A0–A3 desde un hábito (`habitos.habito(...)`). Determinista.

    - "sueles_ignorar" → A0 (silencio).
    - racha ≥ umbral_a3 → A3 · racha ≥ 3 → A2 · racha ≥ 1 → A1.
    - racha 0 pero patrón de fondo "sueles_aceptar" → A1 (sigue sugiriendo tras un rechazo puntual).
    """
    veredicto = habito.get("veredicto", "sin_patron")
    racha = int(habito.get("racha_aceptadas", 0))

    if veredicto == "sueles_ignorar":
        nivel = "A0"
    elif racha >= umbral_a3:
        nivel = "A3"
    elif racha >= _UMBRAL_A2:
        nivel = "A2"
    elif racha >= 1:
        nivel = "A1"
    elif veredicto == "sueles_aceptar":
        nivel = "A1"  # patrón positivo de fondo: no se queda mudo tras un rechazo puntual
    else:
        nivel = "A0"

    return {
        "nivel": nivel,
        "etiqueta": ETIQUETAS[nivel],
        "racha": racha,
        "anticipa": nivel in ("A2", "A3"),  # ¿prepara borrador?
        "requiere_aprobacion_humana": True,  # SIEMPRE, en todos los niveles (techo duro)
    }


def nivel_de(
    habitos: Any, tipo: str, sujeto: str, *, umbral_a3: int = _UMBRAL_A3
) -> dict[str, Any]:
    """Conveniencia: nivel de anticipación para (tipo, sujeto) leyendo el ledger de hábitos."""
    return nivel_desde_habito(habitos.habito(tipo, sujeto), umbral_a3=umbral_a3)


def transicion(antes: str, ahora: str) -> dict[str, Any] | None:
    """Describe un cambio de nivel (para dejar recibo). None si no cambió."""
    if antes == ahora:
        return None
    return {"de": antes, "a": ahora, "sube": NIVELES.index(ahora) > NIVELES.index(antes)}


def requiere_aprobacion_humana(nivel: str) -> bool:
    """Techo duro: el efecto externo requiere aprobación humana en CUALQUIER nivel. Siempre True."""
    return True
