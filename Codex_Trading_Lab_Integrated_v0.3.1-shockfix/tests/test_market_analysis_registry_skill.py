from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR = ROOT / "skills" / "ctl-market-analysis-registry" / "SKILL.md"
DOMAIN_SKILLS = (
    "ctl-market-read",
    "ctl-scenario-planner",
    "ctl-entry-evaluator",
    "ctl-evidence-audit",
    "ctl-live-event-review",
    "ctl-part3-preexecute",
)


def read_text(path: str | Path) -> str:
    return (ROOT / path if isinstance(path, str) else path).read_text(encoding="utf-8")


def frontmatter(path: str | Path) -> dict[str, str]:
    text = read_text(path)
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"missing YAML frontmatter: {path}"
    result = {}
    for line in match.group(1).splitlines():
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def test_orchestrator_declares_current_market_triggers_and_canonical_route() -> None:
    text = read_text(ORCHESTRATOR)
    metadata = frontmatter(ORCHESTRATOR)
    assert metadata["name"] == "ctl-market-analysis-registry"
    assert metadata["description"].startswith("Use when")
    for token in ("current", "live", "both", "Scalping", "Daytrade"):
        assert token in metadata["description"] or token in text
    assert r"D:\MyWork\AlgoTrade\OS\Zenith Trading System\tools\run_zenith_analysis.ps1" in text
    assert r"D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry" in text


def test_orchestrator_is_capability_aware_and_foreground_only() -> None:
    text = read_text(ORCHESTRATOR)
    for token in (
        "CHAT_REGISTRATION_BLOCKED",
        "EXTERNAL_EVIDENCE_PARTIAL",
        "PHASE2_ENABLED_NO_EVENTS",
        "INSUFFICIENT_EVIDENCE",
        "bounded foreground catch-up",
        "not a background",
    ):
        assert token in text
    assert "launcher accepts a Chat envelope" not in text


def test_agent_and_index_define_one_primary_route_per_intent() -> None:
    combined = read_text("AGENTS.md") + read_text("skills.md")
    for token in (
        "ctl-market-analysis-registry",
        "ctl-evidence-audit",
        "ctl-live-event-review",
        "ctl-part3-preexecute",
    ):
        assert token in combined
    assert "one primary route" in combined.lower()


def test_domain_skills_have_valid_frontmatter_and_delegate_without_copying_flow() -> None:
    for name in DOMAIN_SKILLS:
        path = ROOT / "skills" / name / "SKILL.md"
        metadata = frontmatter(path)
        assert metadata["name"] == name
        assert metadata["description"].startswith("Use when")
        text = read_text(path)
        assert "ctl-market-analysis-registry" in text
        assert text.count("run_zenith_analysis.ps1") <= 1
        assert len(text.splitlines()) <= 80


def test_safety_language_is_present_without_claiming_edge() -> None:
    text = read_text(ORCHESTRATOR)
    for token in (
        "trade_write_enabled=false",
        "auto_execution_enabled=false",
        "order_actions=0",
        "permission_leakage=0",
        "Part 3",
    ):
        assert token in text
    assert "validated trading edge" not in text.lower()


def test_instruction_ownership_is_compact_and_nonduplicated() -> None:
    agent = read_text("AGENTS.md")
    index = read_text("skills.md")
    orchestration = read_text(ORCHESTRATOR)
    assert orchestration.count("## Run the foreground workflow") == 1
    assert "## Run the foreground workflow" not in agent
    assert "## Run the foreground workflow" not in index
    assert len(index.splitlines()) <= 80
    assert len(orchestration.splitlines()) <= 160
