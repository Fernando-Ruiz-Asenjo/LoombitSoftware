"""
oportunidades.py — store de los HALLAZGOS de las fuentes (RED/COGNICION/META) para revisión.

No todas las oportunidades son una tool que se redacta: las de la Red (competencia, mercado,
normativa, técnicas) y las META son INTELIGENCIA con cita que el humano revisa y lleva al roadmap.
Aquí se persisten (con dedup, para no repetir el mismo hallazgo cada ciclo) y se marcan atendidas.
Las que SÍ son tool van por `PropuestaStore` (con su arnés). Persistido en
`runtime/local/oportunidades.json`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..config import AppSettings, get_settings
from .modelos import Necesidad


def _clave(nec: Necesidad) -> str:
    return nec.procedencia[0] if nec.procedencia else nec.titulo


class OportunidadStore:
    """Almacén JSON de hallazgos. Cada entrada = la Necesidad + estado (nueva/atendida) + cuándo."""

    def __init__(self, store_path: Path | None = None, settings: AppSettings | None = None) -> None:
        active = settings or get_settings()
        self.store_path = store_path or active.agent_run_store_path.parent / "oportunidades.json"
        self._items: dict[str, dict[str, Any]] = {}
        self._load()

    def registrar(self, necesidades: list[Necesidad]) -> list[Necesidad]:
        """Añade los hallazgos NUEVOS (dedup por procedencia). Devuelve solo los que no existían."""
        nuevos: list[Necesidad] = []
        for nec in necesidades:
            clave = _clave(nec)
            if clave in self._items:
                continue
            self._items[clave] = {
                "necesidad": nec.to_dict(),
                "estado": "nueva",
                "visto_en": datetime.now(UTC).isoformat(),
            }
            nuevos.append(nec)
        if nuevos:
            self._save()
        return nuevos

    def list(self, estado: str | None = None) -> list[dict[str, Any]]:
        items = list(self._items.values())
        if estado:
            items = [i for i in items if i["estado"] == estado]
        return sorted(items, key=lambda i: i["necesidad"].get("prioridad", 0), reverse=True)

    def marcar_atendida(self, clave: str) -> bool:
        for k, item in self._items.items():
            if k == clave or item["necesidad"].get("id") == clave:
                item["estado"] = "atendida"
                self._save()
                return True
        return False

    def snapshot(self) -> dict[str, Any]:
        items = list(self._items.values())
        return {
            "store_path": str(self.store_path),
            "count": len(items),
            "nuevas": sum(1 for i in items if i["estado"] == "nueva"),
        }

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        try:
            raw = json.loads(self.store_path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return
        self._items = dict(raw.get("items", {}))

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 1, "items": self._items}
        tmp = self.store_path.with_suffix(f"{self.store_path.suffix}.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.store_path)
