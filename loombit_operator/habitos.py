"""
habitos.py — el motor que APRENDE DE LOS HÁBITOS del usuario. Núcleo blanco, determinista.

Loombit prepara trabajo proactivo (responder un correo, reclamar un cobro…) y lo deja para que
el usuario apruebe. Este motor registra QUÉ decide el usuario sobre cada sugerencia (aceptar /
rechazar / editar / ignorar) y deriva, **por código** (no por LLM, no se inventa), un patrón:

  - "sueles_aceptar"  → anticípalo y súbelo de prioridad (lo dejas preparado el primero).
  - "sueles_ignorar"  → no lo cuentes como noticia (baja prioridad / silencia).

Y materializa el principio del Norte ("la autonomía se GANA: sube de tier lo que el usuario
aprueba repetidamente", DESTILADO §5): tras una racha de aprobaciones sin rechazos, marca
`autonomia_sugerida` para PROPONER subir la anticipación de ese asunto — nunca para auto-ejecutar
un efecto externo (eso siempre lo aprueba el humano). Lo que sube es PERCIBIR→PREPARAR→ANTICIPAR,
jamás EJECUTAR. Persistencia local en `runtime/local/habitos.json`.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Decisiones que el usuario puede tomar sobre una sugerencia. "editada" = la aprobó tras
# retocarla (cuenta como aceptación, con matiz); "ignorada" = la dejó pasar sin actuar.
DECISIONES = ("aceptada", "editada", "rechazada", "ignorada")
_POSITIVAS = ("aceptada", "editada")
_NEGATIVAS = ("rechazada", "ignorada")


def _ahora() -> str:
    return datetime.now(UTC).isoformat()


def _norm(sujeto: str) -> str:
    return (sujeto or "").lower().strip()


class HabitLedger:
    """Libro de decisiones del usuario + derivación determinista de hábitos.

    Parámetros (afinables, con defaults prudentes):
      min_obs          decisiones mínimas para hablar de un patrón (no se juzga con 1 dato).
      umbral_alto/bajo propensión (aceptadas/decididas) para "sueles_aceptar"/"sueles_ignorar".
      racha_autonomia  aprobaciones SEGUIDAS sin rechazo para sugerir subir la anticipación.
    """

    def __init__(
        self,
        path: Path | None = None,
        *,
        min_obs: int = 3,
        umbral_alto: float = 0.8,
        umbral_bajo: float = 0.2,
        racha_autonomia: int = 5,
    ) -> None:
        self.path = path or Path("runtime/local/habitos.json")
        self.min_obs = max(1, int(min_obs))
        self.umbral_alto = umbral_alto
        self.umbral_bajo = umbral_bajo
        self.racha_autonomia = max(1, int(racha_autonomia))
        self._obs: list[dict[str, Any]] = []
        self._load()

    # ── Registro ──────────────────────────────────────────────────────────────

    def registrar(
        self, tipo: str, sujeto: str, decision: str, meta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Apunta una decisión del usuario sobre una sugerencia (tipo, p.ej. 'respuesta'; sujeto,
        p.ej. el email del contacto). Persiste. Devuelve el hábito recalculado para ese sujeto."""
        if decision not in DECISIONES:
            raise ValueError(f"decisión no válida: {decision!r} (usa {DECISIONES})")
        self._obs.append(
            {
                "tipo": tipo,
                "sujeto": sujeto,
                "decision": decision,
                "ts": _ahora(),
                "meta": meta or {},
            }
        )
        self._save()
        return self.habito(tipo, sujeto)

    # ── Derivación de hábitos ─────────────────────────────────────────────────

    def _decisiones(self, tipo: str, sujeto: str) -> list[dict[str, Any]]:
        s = _norm(sujeto)
        return [o for o in self._obs if o["tipo"] == tipo and _norm(o["sujeto"]) == s]

    def habito(self, tipo: str, sujeto: str) -> dict[str, Any]:
        """El patrón aprendido para (tipo, sujeto): conteos, propensión, veredicto, racha y si
        se sugiere subir la anticipación. Todo determinista, sin LLM."""
        ds = self._decisiones(tipo, sujeto)
        n = len(ds)
        aceptadas = sum(1 for o in ds if o["decision"] in _POSITIVAS)
        rechazadas = sum(1 for o in ds if o["decision"] in _NEGATIVAS)
        decididas = aceptadas + rechazadas
        propension = round(aceptadas / decididas, 3) if decididas else 0.0

        veredicto = "sin_patron"
        if n >= self.min_obs and decididas:
            if propension >= self.umbral_alto:
                veredicto = "sueles_aceptar"
            elif propension <= self.umbral_bajo:
                veredicto = "sueles_ignorar"

        racha = 0  # aprobaciones consecutivas desde la decisión más reciente hacia atrás
        for o in reversed(ds):
            if o["decision"] in _POSITIVAS:
                racha += 1
            else:
                break

        autonomia_sugerida = veredicto == "sueles_aceptar" and racha >= self.racha_autonomia
        return {
            "tipo": tipo,
            "sujeto": sujeto,
            "n": n,
            "aceptadas": aceptadas,
            "rechazadas": rechazadas,
            "propension": propension,
            "veredicto": veredicto,
            "racha_aceptadas": racha,
            "autonomia_sugerida": autonomia_sugerida,
        }

    def prioridad(self, tipo: str, sujeto: str) -> float:
        """Score 0..1 para ORDENAR las sugerencias (0.5 neutro). Sube con la propensión y con la
        confianza (nº de datos): lo que sueles aceptar se prepara el primero."""
        v = self.habito(tipo, sujeto)
        if v["n"] == 0:
            return 0.5
        confianza = min(1.0, v["n"] / self.min_obs)
        return round(0.5 + (v["propension"] - 0.5) * confianza, 3)

    def silenciar(self, tipo: str, sujeto: str) -> bool:
        """¿Bajar el ruido? True si el usuario suele ignorar este asunto (no lo cuentes como noticia)."""
        return self.habito(tipo, sujeto)["veredicto"] == "sueles_ignorar"

    def resumen(self, limite: int = 10) -> list[dict[str, Any]]:
        """Los hábitos con patrón FUERTE (aceptar/ignorar), ordenados por evidencia. Para narrar
        'lo que ya sé de ti' y para que el telar/brief anticipe y priorice."""
        claves: "OrderedDict[tuple[str, str], bool]" = OrderedDict()
        for o in self._obs:
            claves[(o["tipo"], _norm(o["sujeto"]))] = True
        fuertes = []
        for tipo, sujeto in claves:
            v = self.habito(tipo, sujeto)
            if v["veredicto"] != "sin_patron":
                fuertes.append(v)
        fuertes.sort(key=lambda v: (v["n"], v["propension"]), reverse=True)
        return fuertes[:limite]

    # ── Persistencia ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self.path.exists():
            self._obs = []
            return
        try:
            text = self.path.read_text(encoding="utf-8")
            data = json.loads(text) if text.strip() else {}
            obs = data.get("observaciones", [])
            self._obs = [o for o in obs if o.get("decision") in DECISIONES]
        except (json.JSONDecodeError, OSError):
            self._obs = []

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(
                    {"version": 1, "observaciones": self._obs}, indent=2, ensure_ascii=False
                ),
                encoding="utf-8",
            )
            tmp.replace(self.path)
        except OSError:
            pass


# ── Singleton ─────────────────────────────────────────────────────────────────

_ledger: HabitLedger | None = None


def get_habits(path: Path | None = None) -> HabitLedger:
    global _ledger
    if _ledger is None:
        _ledger = HabitLedger(path)
    return _ledger
