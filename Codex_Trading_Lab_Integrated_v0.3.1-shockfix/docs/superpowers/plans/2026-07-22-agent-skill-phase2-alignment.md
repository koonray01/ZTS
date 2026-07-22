# Agent and Skill Phase 2 Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one token-efficient market-analysis orchestration skill and align repository Agent, skill index, and domain skills with the current canonical Phase 2 Registry workflow without claiming unavailable capabilities.

**Architecture:** `AGENTS.md` owns global routing and safety, `skills.md` is a compact intent index, and new `ctl-market-analysis-registry` owns the ordered foreground workflow. Existing domain skills keep narrow responsibilities and delegate current-market orchestration upward. Text-contract tests enforce trigger precedence, canonical path usage, capability-aware failure statuses, no-background/no-broker safety, and duplication limits.

**Tech Stack:** Markdown Agent/Skill instructions, YAML frontmatter, Python 3.14, pytest, Git worktrees.

## Global Constraints

- Current/live Registry-producing analysis resolves through `D:\MyWork\AlgoTrade\OS\Zenith Trading System\tools\run_zenith_analysis.ps1` and the workspace canonical configuration.
- The canonical Registry root is `D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry`.
- Do not imply that the Zenith launcher accepts a Chat envelope.
- Chat integration unavailable is `CHAT_REGISTRATION_BLOCKED`; incomplete persisted external provenance is `EXTERNAL_EVIDENCE_PARTIAL`.
- Catch-up is bounded and foreground-only; there is no persistent background worker.
- `trade_write_enabled=false`, `auto_execution_enabled=false`, `order_actions=0`, and `permission_leakage=0` remain mandatory.
- Part 3 is explicit, eligibility-gated, and separate from analysis/Registry recording.
- `AGENTS.md`, `skills.md`, and domain skills must not duplicate the orchestration workflow.
- This plan changes instructions and validation only; it does not change deterministic analysis, Registry code, policy, or broker behavior.

---

### Task 1: Capture routing failures as executable documentation contracts

**Files:**
- Create: `tests/test_market_analysis_registry_skill.py`
- Create: `reports/analysis_registry/market_skill_pressure_baseline_20260722.md`

**Interfaces:**
- Consumes: current `AGENTS.md`, `skills.md`, and `skills/*/SKILL.md` text.
- Produces: pytest helpers `read_text(path: str) -> str` and `frontmatter(path: str) -> dict[str, str]`, plus failing contracts used by Tasks 2 and 3.

- [ ] **Step 1: Record seven baseline pressure prompts and observed gaps**

Create the report with this exact scenario table:

```markdown
| Intent | Expected primary route | Baseline gap |
|---|---|---|
| current XAUUSD analysis | ctl-market-analysis-registry | orchestration skill absent |
| Zenith plus external analysis | ctl-market-analysis-registry | no capability-aware Chat status |
| historical performance audit | ctl-evidence-audit | no explicit precedence |
| analysis from another worktree | ctl-market-analysis-registry | canonical path exists but delegation is implicit |
| unavailable Chat registration | ctl-market-analysis-registry | CHAT_REGISTRATION_BLOCKED absent |
| Registry write failure | ctl-market-analysis-registry | independent status contract absent from skills |
| explicit Part 3 | ctl-part3-preexecute | precedence not declared in skill index |
```

State that the baseline is a documentation-routing evaluation, not a market prediction or performance result.

- [ ] **Step 2: Write the failing text-contract tests**

```python
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR = ROOT / "skills" / "ctl-market-analysis-registry" / "SKILL.md"
DOMAIN_SKILLS = (
    "ctl-market-read", "ctl-scenario-planner", "ctl-entry-evaluator",
    "ctl-evidence-audit", "ctl-live-event-review", "ctl-part3-preexecute",
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

def test_orchestrator_declares_current_market_triggers_and_canonical_route():
    text = read_text(ORCHESTRATOR)
    metadata = frontmatter(ORCHESTRATOR)
    assert metadata["name"] == "ctl-market-analysis-registry"
    assert metadata["description"].startswith("Use when")
    for token in ("current", "live", "both", "Scalping", "Daytrade"):
        assert token in metadata["description"] or token in text
    assert r"D:\MyWork\AlgoTrade\OS\Zenith Trading System\tools\run_zenith_analysis.ps1" in text
    assert r"D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry" in text

def test_orchestrator_is_capability_aware_and_foreground_only():
    text = read_text(ORCHESTRATOR)
    for token in (
        "CHAT_REGISTRATION_BLOCKED", "EXTERNAL_EVIDENCE_PARTIAL",
        "PHASE2_ENABLED_NO_EVENTS", "INSUFFICIENT_EVIDENCE",
        "bounded foreground catch-up", "not a background",
    ):
        assert token in text
    assert "launcher accepts a Chat envelope" not in text

def test_agent_and_index_define_one_primary_route_per_intent():
    combined = read_text("AGENTS.md") + read_text("skills.md")
    for token in (
        "ctl-market-analysis-registry", "ctl-evidence-audit",
        "ctl-live-event-review", "ctl-part3-preexecute",
    ):
        assert token in combined
    assert "one primary route" in combined.lower()

def test_domain_skills_have_valid_frontmatter_and_delegate_without_copying_flow():
    for name in DOMAIN_SKILLS:
        path = ROOT / "skills" / name / "SKILL.md"
        metadata = frontmatter(path)
        assert metadata["name"] == name
        assert metadata["description"].startswith("Use when")
        text = read_text(path)
        assert "ctl-market-analysis-registry" in text
        assert text.count("run_zenith_analysis.ps1") <= 1
        assert len(text.splitlines()) <= 80

def test_safety_language_is_present_without_claiming_edge():
    text = read_text(ORCHESTRATOR)
    for token in (
        "trade_write_enabled=false", "auto_execution_enabled=false",
        "order_actions=0", "permission_leakage=0", "Part 3",
    ):
        assert token in text
    assert "validated trading edge" not in text.lower()
```

- [ ] **Step 3: Run the new tests and confirm RED**

Run: `python -m pytest -q tests/test_market_analysis_registry_skill.py`

Expected: FAIL because `skills/ctl-market-analysis-registry/SKILL.md` does not exist and existing domain skills lack YAML frontmatter/delegation.

- [ ] **Step 4: Commit the RED contracts**

```powershell
git add tests/test_market_analysis_registry_skill.py reports/analysis_registry/market_skill_pressure_baseline_20260722.md
git commit -m "test: define phase two agent skill contracts"
```

---

### Task 2: Add the canonical orchestration skill and global routing

**Files:**
- Create: `skills/ctl-market-analysis-registry/SKILL.md`
- Modify: `AGENTS.md`
- Modify: `skills.md`

**Interfaces:**
- Consumes: Task 1 trigger, canonical path, status, and safety assertions.
- Produces: one primary routing table and the full ordered foreground workflow.

- [ ] **Step 1: Create the orchestration skill with valid YAML frontmatter**

Use this structure, keeping the finished file below 160 lines:

```markdown
---
name: ctl-market-analysis-registry
description: Use when a user requests current or live market analysis, a market update, Zenith plus external analysis, a comparison, or Scalping/Daytrade setups that must use fresh MT5 evidence and the canonical Analysis Performance Registry.
---

# Market Analysis Registry Orchestration

## Core contract

Use one fresh read-only snapshot, preserve Zenith and Chat attribution, record measurable decisions before outcomes, run bounded foreground catch-up, and report independent analysis, evidence, Registry, catch-up, and safety statuses.

## Canonical paths

- Launcher: `D:\MyWork\AlgoTrade\OS\Zenith Trading System\tools\run_zenith_analysis.ps1`
- Registry: `D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry`
- Resolve the implementation checkout from `registry.json`; never derive Registry storage from cwd, worktree, session ID, or analysis output.

## Ordered workflow

1. Capture a fresh `LIVE_MT5` snapshot and require terminal connected, `FRESH`, QC `PASS`, and zero-write safety.
2. Run deterministic Zenith analysis on that snapshot.
3. When the user requests both/external analysis, gather timestamped sources without replacing the MT5 quote.
4. Build a structured `CHAT_MODEL` envelope bound to the same snapshot before presenting its conclusion.
5. Register only through an available supported structured boundary. If unavailable, report `CHAT_REGISTRATION_BLOCKED`; never claim the launcher accepts a Chat envelope.
6. Classify output as `ZENITH_CANDIDATE`, `CONDITIONAL_WATCH_SETUP`, or `NO_SETUP`. Missing machine-readable fields remain `NON_SCORABLE`.
7. Run bounded foreground catch-up. This is not a background service.
8. Verify the canonical Registry and report IDs, jobs, coverage, and safety.

## Status contract

Report `analysis_status`, `external_evidence_status`, `registry_recording_status`, `catchup_status`, and `safety_status` independently. Use `EXTERNAL_EVIDENCE_PARTIAL` when URLs/retrieval times/content hashes are not persisted. `PHASE2_ENABLED_NO_EVENTS` and `INSUFFICIENT_EVIDENCE` describe coverage, not failure or edge.

## Safety

Require `trade_write_enabled=false`, `auto_execution_enabled=false`, `order_actions=0`, and `permission_leakage=0`. Analysis, a Candidate, Registry recording, or comparison never invokes Part 3 or grants Permission.
```

- [ ] **Step 2: Replace duplicated Agent workflow with routing and invariants**

In `AGENTS.md`, retain existing repository boundary and safety rules, then add a compact `Market-analysis routing` section containing:

```markdown
- Use one primary route per request.
- Current/live/update/both/setup -> `ctl-market-analysis-registry`.
- Historical performance/evidence audit -> `ctl-evidence-audit`.
- Position/live-event review -> `ctl-live-event-review`.
- Explicit eligible Part 3 -> `ctl-part3-preexecute`.
- Domain skills may assist the primary route but must not recapture evidence or repeat Registry writes.
```

Replace detailed Registry workflow duplication with a link to `skills/ctl-market-analysis-registry/SKILL.md`. Preserve all broker-write and Permission prohibitions.

- [ ] **Step 3: Convert `skills.md` into a compact intent index**

List the four primary routes, then list the three supporting domain skills (`ctl-market-read`, `ctl-scenario-planner`, `ctl-entry-evaluator`). Link to the orchestration skill for the workflow and keep the shared safety invariants in one short section.

- [ ] **Step 4: Run the global routing tests**

Run: `python -m pytest -q tests/test_market_analysis_registry_skill.py -k "orchestrator or agent_and_index or safety"`

Expected: orchestration/global tests PASS; domain frontmatter test remains FAIL until Task 3.

- [ ] **Step 5: Commit the orchestration boundary**

```powershell
git add AGENTS.md skills.md skills/ctl-market-analysis-registry/SKILL.md
git commit -m "feat: add canonical market registry orchestration skill"
```

---

### Task 3: Align and minimize the six domain skills

**Files:**
- Modify: `skills/ctl-market-read/SKILL.md`
- Modify: `skills/ctl-scenario-planner/SKILL.md`
- Modify: `skills/ctl-entry-evaluator/SKILL.md`
- Modify: `skills/ctl-evidence-audit/SKILL.md`
- Modify: `skills/ctl-live-event-review/SKILL.md`
- Modify: `skills/ctl-part3-preexecute/SKILL.md`

**Interfaces:**
- Consumes: `ctl-market-analysis-registry` primary orchestration boundary from Task 2.
- Produces: valid trigger-focused skill metadata and narrow local instructions, each at most 80 lines.

- [ ] **Step 1: Add trigger-focused YAML frontmatter to every domain skill**

Use exact names and descriptions:

```yaml
ctl-market-read: Use when the primary market-analysis workflow needs a compact deterministic market-state summary from validated evidence.
ctl-scenario-planner: Use when the primary market-analysis workflow needs rule-based primary and alternative scenarios with observable invalidation and wait conditions.
ctl-entry-evaluator: Use when the primary market-analysis workflow needs deterministic Candidate comparison, geometry, RR, lifecycle, and missing-condition evaluation without Permission.
ctl-evidence-audit: Use when a user requests historical performance, Registry integrity, evidence provenance, unresolved claims, or an audit rather than a new current-market snapshot.
ctl-live-event-review: Use when a user requests read-only position monitoring or review of a significant live watcher event.
ctl-part3-preexecute: Use when a user explicitly requests deterministic Part 3 review for a currently eligible READY_FOR_PERMISSION_REVIEW Candidate.
```

- [ ] **Step 2: Give each skill one local contract**

Each file must contain only:

- `## Role` with its narrow responsibility;
- `## Delegation` naming `ctl-market-analysis-registry` for current-market orchestration and stating it must not restart capture/registration;
- `## Required output` with local fields;
- `## Prohibited` preserving raw-evidence, deterministic-output, broker-write, Permission, and policy restrictions.

Only `ctl-market-read` may repeat the launcher once because its existing canonical route is operationally relevant. Other domain skills link to the orchestration skill without repeating paths.

- [ ] **Step 3: Run all Agent/Skill contracts and confirm GREEN**

Run: `python -m pytest -q tests/test_market_analysis_registry_skill.py`

Expected: all tests PASS.

- [ ] **Step 4: Run existing skill security regressions**

Run: `python -m pytest -q tests/test_skill_context_security.py tests/test_contracts_safety_cli.py`

Expected: all tests PASS; Markdown skills do not change runtime skill-manifest behavior.

- [ ] **Step 5: Commit domain-skill alignment**

```powershell
git add skills/ctl-market-read/SKILL.md skills/ctl-scenario-planner/SKILL.md skills/ctl-entry-evaluator/SKILL.md skills/ctl-evidence-audit/SKILL.md skills/ctl-live-event-review/SKILL.md skills/ctl-part3-preexecute/SKILL.md
git commit -m "docs: align domain skills with registry orchestration"
```

---

### Task 4: Validate behavior, token boundaries, and repository compatibility

**Files:**
- Modify: `reports/analysis_registry/market_skill_pressure_baseline_20260722.md`
- Modify: `tests/test_market_analysis_registry_skill.py`

**Interfaces:**
- Consumes: all instruction files from Tasks 2 and 3.
- Produces: final pressure-validation evidence and repository verification results.

- [ ] **Step 1: Re-run the seven pressure scenarios with the new skill**

For every baseline row, record:

- selected primary route;
- whether a fresh snapshot is required;
- expected Registry behavior;
- expected independent failure status;
- whether Part 3 is allowed;
- confirmation that no background or broker action is implied.

The expected routes must match the Task 1 table exactly. `both-system analysis` must return `CHAT_REGISTRATION_BLOCKED` when structured registration is unavailable, and Registry failure must remain visible independently from analysis completion.

- [ ] **Step 2: Add compactness and duplication assertions**

```python
def test_instruction_ownership_is_compact_and_nonduplicated():
    agent = read_text("AGENTS.md")
    index = read_text("skills.md")
    orchestration = read_text(ORCHESTRATOR)
    assert orchestration.count("## Ordered workflow") == 1
    assert "## Ordered workflow" not in agent
    assert "## Ordered workflow" not in index
    assert len(index.splitlines()) <= 80
    assert len(orchestration.splitlines()) <= 160
```

- [ ] **Step 3: Run focused and full repository verification**

```powershell
python -m pytest -q tests/test_market_analysis_registry_skill.py
python -m pytest -q
$validationOutput = Join-Path $env:TEMP 'zenith-agent-skill-phase2-validation.json'
python tools/run_all_validation.py --output $validationOutput
python tools/validate_contracts.py
git diff --check
git status --short
```

Expected: focused tests pass; repository suite passes with zero failures;
integrated validation reports all checks passed; contract validation reports
PASS; only the intended pressure report remains modified before the final
commit.

- [ ] **Step 4: Commit final validation evidence**

```powershell
git add reports/analysis_registry/market_skill_pressure_baseline_20260722.md tests/test_market_analysis_registry_skill.py
git commit -m "test: validate phase two market skill routing"
```

- [ ] **Step 5: Request independent review before merge**

Review the branch from `main` through `HEAD`, focusing on trigger precedence,
unavailable-capability truthfulness, canonical path consistency, token
duplication, safety language, and whether any instruction can accidentally
invoke Part 3 or broker actions.
