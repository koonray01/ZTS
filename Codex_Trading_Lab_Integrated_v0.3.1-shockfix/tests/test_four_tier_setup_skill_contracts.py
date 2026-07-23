from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_agent_contract_routes_four_tier_setups_once() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "four-tier" in text.lower()
    assert "CONDITIONAL_WATCH_SETUP" in text
    assert "one fresh snapshot" in text.lower()
    assert "one Registry registration" in text


def test_primary_skill_exposes_required_setup_status_fields() -> None:
    text = (ROOT / "skills/ctl-market-analysis-registry/SKILL.md").read_text(encoding="utf-8")
    for token in (
        "setup_generation_id", "setup_variant_count", "scorable_setup_count",
        "non_scorable_setup_count", "scheduled_jobs", "order_actions=0",
        "permission_leakage=0",
    ):
        assert token in text
    assert "--four-tier-setups" in text
    assert "EXPLORATORY" in text
    assert "NORMAL" in text


def test_supporting_skills_cannot_recapture_or_reregister() -> None:
    for relative in (
        "skills/ctl-scenario-planner/SKILL.md",
        "skills/ctl-entry-evaluator/SKILL.md",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "do not capture another snapshot" in text.lower()
        assert "do not duplicate registry writes" in text.lower()
        assert "retrospective" in text.lower()
