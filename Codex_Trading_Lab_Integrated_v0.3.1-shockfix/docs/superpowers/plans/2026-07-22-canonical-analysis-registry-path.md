# Canonical Analysis Registry Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route every supported Zenith analysis session on this workstation to one workspace-level Analysis Performance Registry, with one path resolver and one writer-coordination protocol.

**Architecture:** A typed `RegistryPaths` resolver loads workspace configuration before any analysis side effect and derives all Registry files from one `--registry-root`. Mutating orchestration owns one canonical lease across ledger append and SQLite rebuild; CLIs and the workspace launcher consume the resolver and never derive Registry paths from output directories.

**Tech Stack:** Python 3.11+, `pathlib`, `argparse`, JSON, pytest, PowerShell 7/Windows PowerShell, existing `ctl_analysis_registry` ledger/index/lease modules.

## Global Constraints

- Canonical root: `D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry`.
- Manual Only; `trade_write_enabled=false` and `auto_execution_enabled=false`.
- Validate Registry configuration before output creation, MT5 capture, or Registry mutation.
- Existing ledgers and evidence are immutable; this plan does not import, concatenate, overwrite, or delete them.
- All canonical mutators use `<root>/writer.lease.json` and `<root>/operations.jsonl`.
- Historical unpatched tools are not canonical writers.

---

## File Structure

- `src/ctl_analysis_registry/paths.py`: immutable paths object, config loading, normalization, canonical/non-canonical classification, and override validation.
- `src/ctl_analysis_registry/coordination.py`: canonical lease acquisition helper used by Registry mutators.
- `src/ctl_analysis_registry/integration.py`: consume `RegistryPaths`; hold one lease for registration plus index rebuild.
- `src/ctl_analysis_registry/backfill.py`: use canonical lease and operations paths supplied by `RegistryPaths`.
- `src/ctl_analysis_registry/catchup.py`: use the same canonical lease path.
- `src/ctl_analysis_registry/__init__.py`: export the public path and coordination interfaces.
- `tools/update_market_analysis.py`: resolve Registry configuration before any output or MT5 activity.
- `tools/record_analysis_registry.py`: default to canonical root and acquire the shared writer lease.
- `tools/rebuild_analysis_registry.py`: default to canonical root and acquire the shared writer lease around index replacement.
- `tools/verify_analysis_registry.py`: resolve canonical defaults while retaining labeled read-only inspection mode.
- `tools/inventory_analysis_registries.py`: find and report known legacy Registry roots without mutation.
- `tests/test_analysis_registry_paths.py`: resolver/configuration tests.
- `tests/test_analysis_registry_coordination.py`: cross-writer lease tests.
- `tests/test_analysis_registry_cli_paths.py`: CLI ordering and output-contract tests.
- `tests/test_analysis_registry_workspace_launcher.py`: launcher parity tests from different working directories.
- `AGENTS.md`, `skills.md`, `skills/ctl-market-read/SKILL.md`: route Registry-producing analysis through the workspace launcher.
- Workspace `runtime/analysis_registry/registry.json`: workstation configuration and producer contract.
- Workspace `tools/run_zenith_analysis.ps1`: stable launcher outside Git worktrees.

---

### Task 1: Canonical Registry path resolver

**Files:**
- Create: `src/ctl_analysis_registry/paths.py`
- Modify: `src/ctl_analysis_registry/__init__.py`
- Create: `tests/test_analysis_registry_paths.py`

**Interfaces:**
- Produces: `DEFAULT_WORKSPACE_CONFIG`, `RegistryPaths`, `RegistryPathError`, `load_registry_paths(config_path: Path = DEFAULT_WORKSPACE_CONFIG, registry_root: Path | None = None) -> RegistryPaths`, and `resolve_registry_paths(canonical_root: Path, registry_root: Path | None = None, mutation_overrides: Mapping[str, Path | None] | None = None) -> RegistryPaths`.
- `RegistryPaths` fields: `root`, `ledger`, `sqlite`, `evidence`, `config`, `lease`, `operations`, `mode`, `config_schema_version`, `producer_version`.

- [ ] **Step 1: Write failing resolver tests.**

```python
def test_cwd_output_and_session_do_not_change_canonical_paths(tmp_path, monkeypatch):
    canonical = tmp_path / "runtime" / "analysis_registry"
    first = resolve_registry_paths(canonical)
    monkeypatch.chdir(tmp_path / "worktree")
    second = resolve_registry_paths(canonical)
    assert first == second
    assert first.ledger == canonical.resolve() / "events.jsonl"
    assert first.lease == canonical.resolve() / "writer.lease.json"

def test_partial_mutation_override_fails_without_creating_root(tmp_path):
    canonical = tmp_path / "canonical"
    with pytest.raises(RegistryPathError, match="partial mutation-path override"):
        resolve_registry_paths(canonical, mutation_overrides={"ledger": tmp_path / "x.jsonl"})
    assert not canonical.exists()
```

- [ ] **Step 2: Run tests and verify RED.**

Run: `python -m pytest tests/test_analysis_registry_paths.py -q`

Expected: collection fails because `ctl_analysis_registry.paths` does not exist.

- [ ] **Step 3: Implement the immutable resolver.**

```python
@dataclass(frozen=True)
class RegistryPaths:
    root: Path
    ledger: Path
    sqlite: Path
    evidence: Path
    config: Path
    lease: Path
    operations: Path
    mode: Literal["CANONICAL", "NON_CANONICAL"]
    config_schema_version: str
    producer_version: str

def resolve_registry_paths(canonical_root: Path, registry_root: Path | None = None,
                           mutation_overrides: Mapping[str, Path | None] | None = None) -> RegistryPaths:
    selected = (registry_root or canonical_root).resolve()
    supplied = {k: Path(v).resolve() for k, v in (mutation_overrides or {}).items() if v is not None}
    if supplied and set(supplied) != {"ledger", "sqlite", "evidence", "lease", "operations"}:
        raise RegistryPathError("partial mutation-path override")
    values = supplied or {
        "ledger": selected / "events.jsonl", "sqlite": selected / "index.sqlite",
        "evidence": selected / "evidence", "lease": selected / "writer.lease.json",
        "operations": selected / "operations.jsonl",
    }
    return RegistryPaths(selected, values["ledger"], values["sqlite"], values["evidence"],
                         selected / "registry.json", values["lease"], values["operations"],
                         "CANONICAL" if selected == canonical_root.resolve() else "NON_CANONICAL",
                         "ANALYSIS_REGISTRY_CONFIG_V0_1", "CTL_ANALYSIS_REGISTRY_V0_2")
```

`load_registry_paths` must parse strict JSON keys `schema_version`, `canonical_root`, `implementation_root`, and `producer_version`; reject relative paths, unknown schema versions, or producer mismatch; and perform no `mkdir` or writes.

- [ ] **Step 4: Run resolver tests and full Phase 2 path-independent tests.**

Run: `python -m pytest tests/test_analysis_registry_paths.py tests/test_analysis_registry_phase2_storage.py -q`

Expected: PASS.

- [ ] **Step 5: Commit.**

```text
git add src/ctl_analysis_registry/paths.py src/ctl_analysis_registry/__init__.py tests/test_analysis_registry_paths.py
git commit -m "feat: add canonical registry path resolver"
```

### Task 2: Unify writer coordination

**Files:**
- Create: `src/ctl_analysis_registry/coordination.py`
- Modify: `src/ctl_analysis_registry/integration.py`
- Modify: `src/ctl_analysis_registry/backfill.py`
- Modify: `src/ctl_analysis_registry/catchup.py`
- Modify: `src/ctl_analysis_registry/__init__.py`
- Create: `tests/test_analysis_registry_coordination.py`
- Modify: `tests/test_analysis_registry_phase2_integration.py`
- Modify: `tests/test_analysis_registry_phase2_backfill.py`
- Modify: `tests/test_analysis_registry_phase2_catchup.py`

**Interfaces:**
- Consumes: `RegistryPaths` from Task 1 and existing `RegistryWriterLease`.
- Produces: `acquire_registry_writer(paths: RegistryPaths, owner_id: str, now: datetime, ttl_seconds: int = 60) -> RegistryWriterLease`.
- `register_current_analysis(..., paths: RegistryPaths, now: datetime, lease: RegistryWriterLease | None = None) -> dict[str, Any]` owns a lease only when one is not supplied.

- [ ] **Step 1: Write failing common-lease tests.**

```python
def test_all_mutators_contend_on_one_canonical_lease(paths, now):
    held = acquire_registry_writer(paths, "session-a", now)
    try:
        with pytest.raises(LeaseBusyError):
            acquire_registry_writer(paths, "session-b", now)
        assert paths.lease.name == "writer.lease.json"
        assert list(paths.root.parent.rglob("*.lease.json")) == [paths.lease]
    finally:
        held.release()
```

Add integration/backfill/catch-up tests that inject the same `RegistryPaths`, hold `paths.lease`, and assert each mutator returns or raises its documented busy result without creating an alternate lease or index.

- [ ] **Step 2: Run tests and verify RED.**

Run: `python -m pytest tests/test_analysis_registry_coordination.py tests/test_analysis_registry_phase2_integration.py tests/test_analysis_registry_phase2_backfill.py tests/test_analysis_registry_phase2_catchup.py -q`

Expected: FAIL because mutators derive different lease suffixes and do not accept `RegistryPaths`.

- [ ] **Step 3: Implement the coordination helper and refactor orchestration.**

```python
def acquire_registry_writer(paths: RegistryPaths, owner_id: str, now: datetime,
                            ttl_seconds: int = 60) -> RegistryWriterLease:
    return RegistryWriterLease.acquire(paths.lease, owner_id, ttl_seconds,
                                       now=now, operation_log=paths.operations)
```

Keep `rebuild_index()` as a lease-free storage primitive. Callers that mutate the canonical index must acquire `paths.lease` before invoking it. Do not acquire a nested lease inside `rebuild_index()`.

- [ ] **Step 4: Run focused and complete Registry tests.**

Run: `python -m pytest tests/test_analysis_registry_coordination.py tests/test_analysis_registry_phase2_*.py tests/test_analysis_registry.py -q`

Expected: PASS.

- [ ] **Step 5: Commit.**

```text
git add src/ctl_analysis_registry/coordination.py src/ctl_analysis_registry/integration.py src/ctl_analysis_registry/backfill.py src/ctl_analysis_registry/catchup.py src/ctl_analysis_registry/__init__.py tests/test_analysis_registry_coordination.py tests/test_analysis_registry_phase2_integration.py tests/test_analysis_registry_phase2_backfill.py tests/test_analysis_registry_phase2_catchup.py
git commit -m "fix: unify analysis registry writer coordination"
```

### Task 3: Standardize Registry CLIs and side-effect ordering

**Files:**
- Modify: `tools/update_market_analysis.py`
- Modify: `tools/record_analysis_registry.py`
- Modify: `tools/rebuild_analysis_registry.py`
- Modify: `tools/verify_analysis_registry.py`
- Create: `tests/test_analysis_registry_cli_paths.py`

**Interfaces:**
- Consumes: `load_registry_paths`, `resolve_registry_paths`, `acquire_registry_writer`.
- Every CLI accepts `--registry-config` and `--registry-root`; normal defaults come from workspace configuration.
- Every JSON response includes `registry_root`, `registry_mode`, `registry_config_schema_version`, and `registry_producer_version`.

- [ ] **Step 1: Write failing CLI contract and ordering tests.**

```python
def test_update_validates_registry_before_output_or_mt5(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: calls.append("mkdir"))
    monkeypatch.setattr(update_market_analysis, "MetaTrader5SnapshotAdapter",
                        lambda: calls.append("adapter"))
    code = update_market_analysis.main([
        "--output", str(tmp_path / "out"),
        "--registry-config", str(tmp_path / "missing.json"),
    ])
    assert code != 0
    assert calls == []

def test_cli_summary_reports_canonical_registry(metadata):
    assert metadata["registry_mode"] == "CANONICAL"
    assert Path(metadata["registry_root"]).is_absolute()
```

Refactor each `main` to accept `argv: Sequence[str] | None = None` so tests exercise parsing without subprocess or live MT5.

- [ ] **Step 2: Run tests and verify RED.**

Run: `python -m pytest tests/test_analysis_registry_cli_paths.py -q`

Expected: FAIL because CLIs require individual paths or derive from `out.parent`, and update creates output before Registry validation.

- [ ] **Step 3: Implement canonical CLI behavior.**

In `update_market_analysis.main`, call `load_registry_paths(...)` immediately after `parse_args` and before `Path(a.output).mkdir`, adapter construction, or capture. Remove `registry_root = out.parent / "analysis_registry"` and pass the resolved object into integration.

In record and rebuild commands, acquire `acquire_registry_writer(paths, owner_id, now)` before the first mutation and release in `finally`. Verify remains lease-free and labels an explicitly inspected external file as `NON_CANONICAL`.

- [ ] **Step 4: Run CLI and Registry regression tests.**

Run: `python -m pytest tests/test_analysis_registry_cli_paths.py tests/test_analysis_registry*.py -q`

Expected: PASS.

- [ ] **Step 5: Commit.**

```text
git add tools/update_market_analysis.py tools/record_analysis_registry.py tools/rebuild_analysis_registry.py tools/verify_analysis_registry.py tests/test_analysis_registry_cli_paths.py
git commit -m "feat: route registry CLIs through canonical root"
```

### Task 4: Workspace launcher and operator routing

**Files:**
- Create outside repository: `D:\MyWork\AlgoTrade\OS\Zenith Trading System\tools\run_zenith_analysis.ps1`
- Create outside repository: `D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry\registry.json`
- Modify: `AGENTS.md`
- Modify: `skills.md`
- Modify: `skills/ctl-market-read/SKILL.md`
- Create: `tests/test_analysis_registry_workspace_launcher.py`

**Interfaces:**
- Launcher parameters: `-Output <absolute-or-relative-path>`, `-Symbol XAUUSD`, `-Bars 60`, `-NoH4`, and `-ResolveOnly`.
- `-ResolveOnly` prints the resolved implementation and Registry metadata without MT5 access or filesystem mutation.

- [ ] **Step 1: Write failing launcher parity test.**

```python
@pytest.mark.skipif(shutil.which("powershell") is None, reason="PowerShell unavailable")
def test_launcher_resolves_same_root_from_checkout_and_worktree(project_root, worktree_root):
    outputs = []
    for cwd in (project_root, worktree_root):
        run = subprocess.run(["powershell", "-NoProfile", "-File", str(LAUNCHER),
                              "-ResolveOnly"], cwd=cwd, text=True, capture_output=True, check=True)
        outputs.append(json.loads(run.stdout))
    assert outputs[0]["registry_root"] == outputs[1]["registry_root"]
    assert outputs[0]["implementation_root"] == outputs[1]["implementation_root"]
```

- [ ] **Step 2: Run test and verify RED.**

Run: `python -m pytest tests/test_analysis_registry_workspace_launcher.py -q`

Expected: FAIL because workspace launcher and configuration do not exist.

- [ ] **Step 3: Create strict workspace configuration and launcher.**

`registry.json` content:

```json
{
  "schema_version": "ANALYSIS_REGISTRY_CONFIG_V0_1",
  "canonical_root": "D:\\MyWork\\AlgoTrade\\OS\\Zenith Trading System\\runtime\\analysis_registry",
  "implementation_root": "D:\\MyWork\\AlgoTrade\\OS\\Zenith Trading System\\.worktrees\\live-analysis-main\\Codex_Trading_Lab_Integrated_v0.3.1-shockfix",
  "producer_version": "CTL_ANALYSIS_REGISTRY_V0_2"
}
```

The launcher reads this JSON, rejects missing/non-absolute paths and producer mismatch, supports `-ResolveOnly`, and otherwise invokes `<implementation_root>\tools\update_market_analysis.py` with `--registry-config`, `--registry-root`, output, symbol, bars, and optional `--no-h4`. It must not fall back to the caller's checkout.

- [ ] **Step 4: Update operator contracts.**

Add one canonical rule to `AGENTS.md`, `skills.md`, and `skills/ctl-market-read/SKILL.md`: Registry-producing current-market analysis must invoke the workspace launcher; direct historical-checkout execution is diagnostic-only and must not write the canonical Registry.

- [ ] **Step 5: Run launcher parity and skill-contract tests.**

Run: `python -m pytest tests/test_analysis_registry_workspace_launcher.py tests/test_skill_context_security.py tests/test_integrated_repository.py -q`

Expected: PASS, with `-ResolveOnly` producing identical JSON from checkout and worktree and no MT5 access.

- [ ] **Step 6: Commit repository-owned files.**

```text
git add AGENTS.md skills.md skills/ctl-market-read/SKILL.md tests/test_analysis_registry_workspace_launcher.py
git commit -m "docs: route Zenith sessions through canonical launcher"
```

Record workspace-level launcher and config hashes in the validation report because they are intentionally outside Git.

### Task 5: Legacy inventory and acceptance verification

**Files:**
- Create: `tools/inventory_analysis_registries.py`
- Create: `tests/test_analysis_registry_inventory.py`
- Create: `reports/analysis_registry/canonical_registry_validation_20260722.md`

**Interfaces:**
- Produces: `inventory_registries(search_roots: Sequence[Path], canonical_root: Path) -> dict[str, Any]`.
- Inventory fields: `registry_root`, `canonical`, `ledger_exists`, `ledger_bytes`, `sqlite_exists`, `last_modified`, and `mutation_performed=false`.

- [ ] **Step 1: Write failing read-only inventory test.**

```python
def test_inventory_reports_split_registries_without_mutation(tmp_path):
    legacy = tmp_path / "checkout" / "outputs" / "analysis_registry"
    legacy.mkdir(parents=True)
    ledger = legacy / "events.jsonl"
    ledger.write_text("{}\n", encoding="utf-8")
    before = ledger.read_bytes()
    report = inventory_registries([tmp_path], tmp_path / "runtime" / "analysis_registry")
    assert report["registries"][0]["canonical"] is False
    assert report["mutation_performed"] is False
    assert ledger.read_bytes() == before
```

- [ ] **Step 2: Run test and verify RED.**

Run: `python -m pytest tests/test_analysis_registry_inventory.py -q`

Expected: collection fails because the inventory module does not exist.

- [ ] **Step 3: Implement inventory and run it on approved roots.**

Scan only the workspace root, `D:\zreg`, and `D:\zreg2`; do not scan unrelated drives. Report directories named `analysis_registry` containing `events.jsonl` or `index.sqlite`. Never open files for writing.

- [ ] **Step 4: Run the complete acceptance matrix.**

Run:

```text
python -m pytest tests/test_analysis_registry.py tests/test_analysis_registry_phase2_*.py tests/test_analysis_registry_paths.py tests/test_analysis_registry_coordination.py tests/test_analysis_registry_cli_paths.py tests/test_analysis_registry_workspace_launcher.py tests/test_analysis_registry_inventory.py -q
python tools/validate_contracts.py
powershell -NoProfile -File "D:\MyWork\AlgoTrade\OS\Zenith Trading System\tools\run_zenith_analysis.ps1" -ResolveOnly
python tools/inventory_analysis_registries.py --search-root "D:\MyWork\AlgoTrade\OS\Zenith Trading System" --search-root D:\zreg --search-root D:\zreg2 --canonical-root "D:\MyWork\AlgoTrade\OS\Zenith Trading System\runtime\analysis_registry"
```

Expected: all tests and contracts PASS; launcher reports the approved canonical root; inventory reports split legacy Registries with `mutation_performed=false`; no legacy ledger timestamp or hash changes.

- [ ] **Step 5: Write validation evidence.**

Document commands, exit codes, test counts, resolved root, implementation root, producer/config versions, launcher/config SHA-256 hashes, legacy inventory, zero broker writes, and explicit statement that migration was not performed.

- [ ] **Step 6: Commit.**

```text
git add tools/inventory_analysis_registries.py tests/test_analysis_registry_inventory.py reports/analysis_registry/canonical_registry_validation_20260722.md
git commit -m "test: validate canonical analysis registry routing"
```

### Task 6: Integration review and deployment decision

**Files:**
- Review only; no planned production-file changes.

**Interfaces:**
- Consumes all deliverables from Tasks 1-5.
- Produces a verified commit range and an explicit merge/deployment recommendation.

- [ ] **Step 1: Review the implementation against the approved spec.**

Check every acceptance criterion in `docs/superpowers/specs/2026-07-22-canonical-analysis-registry-path-design.md` against a test or validation artifact. Reject silent fallback, alternate lease paths, output-derived Registry paths, and live-ledger writes from tests.

- [ ] **Step 2: Run final clean verification.**

Run:

```text
python -m pytest -q
python tools/run_all_validation.py --output outputs/canonical_registry_integrated_validation
python tools/validate_contracts.py
git diff --check
git status --short
```

Expected: tests and validation PASS; only known user-owned/unrelated changes, if any, remain; no new Registry appears below an analysis output tree.

- [ ] **Step 3: Request code review.**

Use `superpowers:requesting-code-review` against the complete implementation commit range. Resolve findings using `superpowers:receiving-code-review` and rerun Step 2.

- [ ] **Step 4: Prepare integration choice.**

Use `superpowers:finishing-a-development-branch` to present merge, PR, keep-branch, or cleanup options. Do not migrate legacy ledgers as part of integration.
