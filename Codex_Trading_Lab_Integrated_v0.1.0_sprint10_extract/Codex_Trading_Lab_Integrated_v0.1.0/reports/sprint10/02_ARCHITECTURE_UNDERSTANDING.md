# Sprint 10 Architecture Understanding

Confirmed active flow:

Snapshot -> Basic Eyes -> Advanced Eyes -> Market Fusion -> Scenario Tree -> Entry Candidates -> Limit Eligibility -> Part 3 Permission -> Manual Execution Proposal -> Live Watcher -> Codex Job Queue -> Codex Worker -> Replay & Training -> Knowledge & Learning.

## Separation Confirmed

- Opportunity is not permission.
- Scenario rank is not probability.
- `LIMIT_READY` is not trade approval.
- Worker interpretation is not deterministic fact.
- Replay result is not live result.
- Observation is not production rule.
- Hypothesis is not validated finding.
- Approved policy requires human approval.

## Layer Ownership

- Snapshot/QC: `ctl_mt5_snapshot` and existing snapshot schema.
- Basic/Advanced Eyes: deterministic perception packages.
- Decision Core: fusion, scenario, entry candidate construction.
- Permission Agent: deterministic Part 3 only.
- Live Runtime: session, watcher, queue, locks, position-monitoring state.
- Codex Worker: scripted or provider-backed interpretation with allowlisted tools only.
- Replay/Knowledge: separate learning streams and promotion gates.

No layer was given broker-write authority.
