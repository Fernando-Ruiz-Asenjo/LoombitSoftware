"""Tests de skills.py (migrados desde jetson-ai-operator)."""

import pytest

from loombit_operator.skills import (
    SkillCategory,
    SkillManifest,
    SkillRegistry,
    SkillSafetyClass,
)


def test_skill_registry_starts_blank():
    registry = SkillRegistry()

    assert registry.snapshot() == {"count": 0, "skills": []}


def test_skill_registry_registers_manifest():
    registry = SkillRegistry()
    manifest = SkillManifest(
        name="example.status",
        display_name="Example Status",
        version="0.1.0",
        category=SkillCategory.CORE,
        description="Example passive skill.",
        capabilities=["status.read"],
        safety_class=SkillSafetyClass.PASSIVE,
    )

    registry.register(manifest)

    snapshot = registry.snapshot()
    assert snapshot["count"] == 1
    assert snapshot["skills"][0]["name"] == "example.status"
    assert snapshot["skills"][0]["category"] == "core"
    assert snapshot["skills"][0]["enabled_by_default"] is False


def test_skill_registry_rejects_duplicate_names():
    registry = SkillRegistry()
    manifest = SkillManifest(
        name="example.status",
        display_name="Example Status",
        version="0.1.0",
        category=SkillCategory.CORE,
        description="Example passive skill.",
    )

    registry.register(manifest)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(manifest)


def test_skill_registry_filters_by_category():
    registry = SkillRegistry()
    registry.register(
        SkillManifest(
            name="vision.person_detect",
            display_name="Person Detection",
            version="0.1.0",
            category=SkillCategory.VISION,
            description="Example vision skill.",
        )
    )
    registry.register(
        SkillManifest(
            name="telemetry.heartbeat",
            display_name="Heartbeat",
            version="0.1.0",
            category=SkillCategory.TELEMETRY,
            description="Example telemetry skill.",
        )
    )

    skills = registry.list(category=SkillCategory.VISION)

    assert [skill.name for skill in skills] == ["vision.person_detect"]


def test_skill_manifest_from_dict():
    manifest = SkillManifest.from_dict(
        {
            "name": "diagnostic.scan",
            "display_name": "Diagnostic Scan",
            "version": "0.1.0",
            "category": "automation",
            "description": "Example diagnostic skill.",
            "capabilities": ["diagnostic.scan"],
            "requires_llm": True,
            "required_hardware": [],
            "safety_class": "assisted",
        }
    )

    assert manifest.name == "diagnostic.scan"
    assert manifest.category == SkillCategory.AUTOMATION
    assert manifest.requires_llm is True
