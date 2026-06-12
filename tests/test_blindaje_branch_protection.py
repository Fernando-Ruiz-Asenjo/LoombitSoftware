"""Guardian ADITIVO (complementa test_gate_integridad.py): el workflow branch-protection-as-code
existe y declara el estado FUERTE. Si alguien lo borra o lo debilita, el check `quality` se pone
ROJO y no se puede fundir (enforce_admins). Determinista, sin LLM, parte del muro. Radar 2026-06-12.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows" / "branch-protection.yml"


def test_existe_el_workflow_branch_protection_as_code():
    assert (
        WF.exists()
    ), "falta .github/workflows/branch-protection.yml (auto-curación de la protección)"


def test_el_workflow_declara_el_estado_fuerte():
    t = WF.read_text(encoding="utf-8")
    for needed in (
        "branches/main/protection",
        '"enforce_admins": true',
        '"require_code_owner_reviews": true',
        '"required_approving_review_count": 1',
        '"allow_force_pushes": false',
        '"contexts": ["quality"]',
    ):
        assert needed in t, f"el workflow ya no exige «{needed}» (¿protección debilitada?)"


def test_el_workflow_se_autocura_en_cron():
    t = WF.read_text(encoding="utf-8")
    assert (
        "schedule" in t and "cron" in t
    ), "el workflow ya no se re-aplica periódicamente (auto-curación perdida)"
