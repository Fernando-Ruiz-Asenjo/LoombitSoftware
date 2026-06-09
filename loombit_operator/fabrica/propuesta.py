"""
propuesta.py — store gobernado de propuestas de skill + archivo/linaje (Skill X).

Una propuesta validada se guarda como PENDIENTE y espera el gate humano. El estado SOLO pasa a
APROBADA por acción humana explícita (`aprobar`) — la Fábrica nunca se auto-aplica. Se guardan
también las DESCARTADAS y las FALLIDAS: son el linaje (DGM/ADAS), peldaños con su fitness que
informan los siguientes intentos. Persistido en `runtime/local/propuestas_skill.json`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import AppSettings, get_settings
from .modelos import EstadoPropuesta, PropuestaSkill


def _ruta_por_defecto(settings: AppSettings) -> Path:
    return settings.agent_run_store_path.parent / "propuestas_skill.json"


class PropuestaStore:
    """Almacén JSON de propuestas. Mismo patrón robusto que `AgentStore` (escritura atómica)."""

    def __init__(self, store_path: Path | None = None, settings: AppSettings | None = None) -> None:
        active = settings or get_settings()
        self.store_path = store_path or _ruta_por_defecto(active)
        self._propuestas: dict[str, PropuestaSkill] = {}
        self.load_error: str | None = None
        self._load()

    # ── Altas y consultas ───────────────────────────────────────────────────────

    def add(self, propuesta: PropuestaSkill) -> PropuestaSkill:
        self._propuestas[propuesta.id] = propuesta
        self._save()
        return propuesta

    def get(self, propuesta_id: str) -> PropuestaSkill:
        try:
            return self._propuestas[propuesta_id]
        except KeyError as exc:
            raise KeyError(f"Propuesta no encontrada: {propuesta_id}") from exc

    def list(self, estado: EstadoPropuesta | None = None) -> list[PropuestaSkill]:
        props = list(self._propuestas.values())
        if estado is not None:
            props = [p for p in props if p.estado == estado]
        return sorted(props, key=lambda p: p.created_at, reverse=True)

    def mejor_pendiente(self) -> PropuestaSkill | None:
        """El mejor peldaño aún sin decidir (mayor fitness): lo que conviene revisar primero."""
        pendientes = self.list(EstadoPropuesta.PENDIENTE)
        return max(pendientes, key=lambda p: p.fitness, default=None)

    # ── Gate humano (las ÚNICAS transiciones a aprobada/descartada) ──────────────

    def aprobar(self, propuesta_id: str, nota: str = "") -> PropuestaSkill:
        """Acción HUMANA: autoriza la propuesta. No materializa por sí sola el artefacto — eso lo
        hace `materializar.escribir_tool_aprobada` como paso explícito y reviewable."""
        return self._decidir(propuesta_id, EstadoPropuesta.APROBADA, nota)

    def descartar(self, propuesta_id: str, nota: str = "") -> PropuestaSkill:
        """Acción HUMANA: rechaza la propuesta (queda en el linaje como peldaño descartado)."""
        return self._decidir(propuesta_id, EstadoPropuesta.DESCARTADA, nota)

    def _decidir(self, propuesta_id: str, estado: EstadoPropuesta, nota: str) -> PropuestaSkill:
        prop = self.get(propuesta_id)
        if prop.estado != EstadoPropuesta.PENDIENTE:
            raise ValueError(
                f"La propuesta ya está {prop.estado.value}, no se puede {estado.value}"
            )
        from datetime import UTC, datetime

        prop.estado = estado
        prop.decision_humana = nota
        prop.updated_at = datetime.now(UTC).isoformat()
        self._save()
        return prop

    def snapshot(self) -> dict[str, Any]:
        props = self.list()
        por_estado = {e.value: 0 for e in EstadoPropuesta}
        for p in props:
            por_estado[p.estado.value] += 1
        return {
            "store_path": str(self.store_path),
            "load_error": self.load_error,
            "count": len(props),
            "por_estado": por_estado,
        }

    # ── Persistencia (escritura atómica, tolerante a JSON corrupto) ──────────────

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        text = self.store_path.read_text(encoding="utf-8")
        if not text.strip():
            return
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            self.load_error = f"propuestas store JSON inválido: {exc}"
            return
        props: dict[str, PropuestaSkill] = {}
        errores: list[str] = []
        for i, d in enumerate(raw.get("propuestas", [])):
            try:
                p = PropuestaSkill.from_dict(d)
                props[p.id] = p
            except (KeyError, TypeError, ValueError) as exc:
                errores.append(f"propuesta[{i}]: {exc}")
        self._propuestas = props
        self.load_error = "; ".join(errores) if errores else None

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 1, "propuestas": [p.to_dict() for p in self.list()]}
        tmp = self.store_path.with_suffix(f"{self.store_path.suffix}.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.store_path)
