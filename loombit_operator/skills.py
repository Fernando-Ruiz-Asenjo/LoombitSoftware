"""
skills.py — modelo de skills instalables (Skill W, núcleo blanco).

Migrado desde `jetson-ai-operator`. Define el manifest de una skill y un
registro en memoria. Sin lógica de dominio: el comportamiento vertical vive en
los manifests JSON que carga `skill_loader.py`.

Estado: 🟡 migrado y unit-tested; aún no montado en routers de la app.
"""

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class SkillCategory(StrEnum):
    CORE = "core"
    AUTOMATION = "automation"
    VISION = "vision"
    AUDIO = "audio"
    MOBILITY = "mobility"
    TELEMETRY = "telemetry"
    SAFETY = "safety"
    INTEGRATION = "integration"
    CUSTOM = "custom"


class SkillSafetyClass(StrEnum):
    PASSIVE = "passive"
    ASSISTED = "assisted"
    SAFETY_SENSITIVE = "safety_sensitive"
    BLOCKED_BY_DEFAULT = "blocked_by_default"


def _as_string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a list")
    if not all(isinstance(item, str) for item in value):
        raise TypeError(f"{field_name} must contain only strings")
    return value


@dataclass(frozen=True)
class SkillManifest:
    name: str
    display_name: str
    version: str
    category: SkillCategory
    description: str
    capabilities: list[str] = field(default_factory=list)
    requires_llm: bool = False
    required_hardware: list[str] = field(default_factory=list)
    safety_class: SkillSafetyClass = SkillSafetyClass.PASSIVE
    enabled_by_default: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["category"] = self.category.value
        data["safety_class"] = self.safety_class.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillManifest":
        return cls(
            name=str(data["name"]),
            display_name=str(data["display_name"]),
            version=str(data["version"]),
            category=SkillCategory(data["category"]),
            description=str(data["description"]),
            capabilities=_as_string_list(data.get("capabilities", []), "capabilities"),
            requires_llm=bool(data.get("requires_llm", False)),
            required_hardware=_as_string_list(
                data.get("required_hardware", []),
                "required_hardware",
            ),
            safety_class=SkillSafetyClass(data.get("safety_class", SkillSafetyClass.PASSIVE)),
            enabled_by_default=bool(data.get("enabled_by_default", False)),
            metadata=dict(data.get("metadata", {})),
        )


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillManifest] = {}

    def register(self, manifest: SkillManifest) -> None:
        if manifest.name in self._skills:
            raise ValueError(f"Skill '{manifest.name}' is already registered")
        self._skills[manifest.name] = manifest

    def get(self, name: str) -> SkillManifest:
        try:
            return self._skills[name]
        except KeyError as exc:
            raise KeyError(f"Skill '{name}' is not registered") from exc

    def list(self, category: SkillCategory | None = None) -> list[SkillManifest]:
        skills = list(self._skills.values())
        if category is not None:
            skills = [skill for skill in skills if skill.category == category]
        return sorted(skills, key=lambda skill: skill.name)

    def snapshot(self) -> dict[str, Any]:
        skills = self.list()
        return {
            "count": len(skills),
            "skills": [skill.to_dict() for skill in skills],
        }


skill_registry = SkillRegistry()
