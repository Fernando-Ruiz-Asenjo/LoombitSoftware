"""
skill_loader.py — carga de manifests de skills desde disco (Skill W).

Migrado desde `jetson-ai-operator`. Lee los `*.json` del directorio de manifests
(`settings.skill_manifest_dir`, por defecto `skills/`) y construye un
`SkillRegistry`. Sin lógica de dominio.

Estado: 🟡 migrado y unit-tested. El cableado a un endpoint de recarga
(`reload_skills`) queda pendiente.
"""

import json
from pathlib import Path
from typing import Any

from .config import AppSettings, get_settings
from .skills import SkillManifest, SkillRegistry


class SkillManifestError(ValueError):
    pass


class SkillManifestLoader:
    def __init__(
        self, manifest_dir: Path | None = None, settings: AppSettings | None = None
    ) -> None:
        active_settings = settings or get_settings()
        self.manifest_dir = manifest_dir or active_settings.skill_manifest_dir

    def load(self) -> SkillRegistry:
        registry = SkillRegistry()
        if not self.manifest_dir.exists():
            return registry
        if not self.manifest_dir.is_dir():
            raise SkillManifestError(f"Skill manifest path is not a directory: {self.manifest_dir}")

        for path in sorted(self.manifest_dir.glob("*.json")):
            registry.register(self.load_manifest(path))
        return registry

    def load_manifest(self, path: Path) -> SkillManifest:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SkillManifestError(f"Invalid JSON in skill manifest {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise SkillManifestError(f"Skill manifest must be a JSON object: {path}")

        try:
            return SkillManifest.from_dict(raw)
        except (KeyError, TypeError, ValueError) as exc:
            raise SkillManifestError(f"Invalid skill manifest {path}: {exc}") from exc

    def snapshot(self) -> dict[str, Any]:
        return {
            "manifest_dir": str(self.manifest_dir),
            "exists": self.manifest_dir.exists(),
        }
