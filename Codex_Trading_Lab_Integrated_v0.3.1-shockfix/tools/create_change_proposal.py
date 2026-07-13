from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ctl_knowledge_learning.proposals import build_change_proposal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a non-deploying change proposal.")
    parser.add_argument("--type", required=True, choices=["CANDIDATE_RULE", "POLICY_UPDATE", "SKILL_UPDATE"])
    parser.add_argument("--target", required=True)
    parser.add_argument("--to-version", required=True)
    parser.add_argument("--rationale", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    proposal = build_change_proposal(
        proposal_type=args.type,
        target_id=args.target,
        from_version=None,
        to_version=args.to_version,
        rationale=args.rationale,
        evidence_refs=[],
        tests_required=["unit", "integration", "replay", "shadow"],
        shadow_plan="Run in shadow mode before any approval.",
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    print(json.dumps({"proposal_id": proposal["proposal_id"], "human_approved": False, "deployed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
