"""
Tests de skill_loader.py (migrados desde jetson-ai-operator).

El test original `test_runtime_reload_skills` dependía de OperatorRuntime (no
migrado) y queda fuera de alcance.
"""

import json

import pytest

from loombit_operator.skill_loader import SkillManifestError, SkillManifestLoader


def write_manifest(directory, name="diagnostic.scan"):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name.replace('.', '_')}.json"
    path.write_text(
        json.dumps(
            {
                "name": name,
                "display_name": "Diagnostic Scan",
                "version": "0.1.0",
                "category": "automation",
                "description": "Reads approved operational inputs and proposes opportunities.",
                "capabilities": ["diagnostic.scan", "report.generate"],
                "requires_llm": True,
                "required_hardware": [],
                "safety_class": "assisted",
                "enabled_by_default": False,
                "metadata": {"market": "spain_sme"},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_loader_returns_blank_registry_when_directory_is_missing(tmp_path):
    loader = SkillManifestLoader(manifest_dir=tmp_path / "missing")

    registry = loader.load()

    assert registry.snapshot() == {"count": 0, "skills": []}


def test_loader_reads_json_manifest(tmp_path):
    manifest_dir = tmp_path / "skills"
    write_manifest(manifest_dir)

    registry = SkillManifestLoader(manifest_dir=manifest_dir).load()
    snapshot = registry.snapshot()

    assert snapshot["count"] == 1
    assert snapshot["skills"][0]["name"] == "diagnostic.scan"
    assert snapshot["skills"][0]["category"] == "automation"
    assert snapshot["skills"][0]["safety_class"] == "assisted"
    assert snapshot["skills"][0]["enabled_by_default"] is False


def test_loader_rejects_invalid_manifest(tmp_path):
    manifest_dir = tmp_path / "skills"
    manifest_dir.mkdir()
    (manifest_dir / "bad.json").write_text(
        json.dumps({"name": "bad", "category": "not-a-category"}),
        encoding="utf-8",
    )

    with pytest.raises(SkillManifestError, match="Invalid skill manifest"):
        SkillManifestLoader(manifest_dir=manifest_dir).load()


def test_loader_rejects_non_list_capabilities(tmp_path):
    path = write_manifest(tmp_path / "skills")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["capabilities"] = "diagnostic.scan"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(SkillManifestError, match="capabilities must be a list"):
        SkillManifestLoader(manifest_dir=tmp_path / "skills").load()
