from __future__ import annotations

import argparse, json, sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Sequence
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from ctl_decision_core import run_decision_core
from ctl_mt5_snapshot import EvidenceStore, MetaTrader5SnapshotAdapter, SnapshotUnavailable
from ctl_mt5_snapshot.utils import sanitize_id
from ctl_analysis_registry.identity import stable_id
from ctl_analysis_registry.integration import register_analysis_and_catchup
from ctl_analysis_registry.paths import DEFAULT_WORKSPACE_CONFIG, RegistryPathError, load_registry_paths

def _candidate_delta(previous: dict | None, current: dict) -> dict:
    current_items = current.get("entry_packet", {}).get("candidates", [])
    previous_items = (previous or {}).get("entry_packet", {}).get("candidates", [])
    current_by_id = {item["candidate_id"]: item for item in current_items}
    previous_by_id = {item["candidate_id"]: item for item in previous_items}
    disappeared = [item for key, item in previous_by_id.items() if key not in current_by_id]
    current_shapes = {(item.get("side"), item.get("entry_type")) for item in current_items}
    current_sides = {item.get("side") for item in current_items}
    expired = [item["candidate_id"] for item in disappeared if item.get("status") == "EXPIRED"]
    superseded = [item["candidate_id"] for item in disappeared if item.get("side") in current_sides and item.get("status") != "EXPIRED"]
    superseded_reasons = {
        item["candidate_id"]: (
            "SAME_SIDE_AND_ENTRY_TYPE_REGENERATED"
            if (item.get("side"), item.get("entry_type")) in current_shapes
            else "SCENARIO_FAMILY_CHANGED_ENTRY_TYPE_NO_LONGER_APPLICABLE"
        )
        for item in disappeared
        if item["candidate_id"] in superseded
    }
    unexpected = [item["candidate_id"] for item in disappeared if item["candidate_id"] not in set(expired + superseded)]
    return {
        "previous_snapshot_id": (previous or {}).get("snapshot_id"),
        "current_snapshot_id": current.get("snapshot_id"),
        "previous_count": len(previous_items),
        "current_count": len(current_items),
        "expired": expired,
        "superseded": superseded,
        "superseded_reasons": superseded_reasons,
        "semantic_deduplicated": [],
        "new": [key for key in current_by_id if key not in previous_by_id],
        "unexpected_disappearance": unexpected,
        "unexpected_disappearance_count": len(unexpected),
    }

def main(argv: Sequence[str] | None = None)->int:
    p=argparse.ArgumentParser(description="Capture fresh read-only MT5 snapshot and analyze it.")
    p.add_argument("--symbol",default="XAUUSD"); p.add_argument("--bars",type=int,default=60); p.add_argument("--output",required=True); p.add_argument("--no-h4",action="store_true"); p.add_argument("--previous-decision",type=Path)
    p.add_argument("--registry-ledger",type=Path); p.add_argument("--registry-sqlite",type=Path); p.add_argument("--registry-evidence",type=Path); p.add_argument("--catchup-max-jobs",type=int,default=25)
    p.add_argument("--registry-config",type=Path,default=DEFAULT_WORKSPACE_CONFIG); p.add_argument("--registry-root",type=Path)
    a=p.parse_args(argv)
    try:
        paths=load_registry_paths(a.registry_config,registry_root=a.registry_root)
        individual={"ledger":a.registry_ledger,"sqlite":a.registry_sqlite,"evidence":a.registry_evidence}
        if any(value is not None for value in individual.values()):
            raise RegistryPathError("individual Registry paths are unsupported; use --registry-root")
    except RegistryPathError as exc:
        print(json.dumps({"status":"REGISTRY_CONFIG_INVALID","message":str(exc),"trade_write_enabled":False,"auto_execution_enabled":False}),file=sys.stderr)
        return 4
    out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    adapter=MetaTrader5SnapshotAdapter(); now=datetime.now(timezone.utc)
    snap=adapter.capture(symbol=a.symbol,run_id=sanitize_id("MARKET_ANALYSIS_"+now.strftime("%Y%m%dT%H%M%SZ")),bars=a.bars,include_h4=not a.no_h4)
    (out/"snapshot.json").write_text(json.dumps(snap,indent=2,sort_keys=True),encoding="utf-8"); EvidenceStore(out/"evidence").write_raw_snapshot(snap)
    decision=run_decision_core(snap); (out/"decision_state.json").write_text(json.dumps(decision,indent=2),encoding="utf-8")
    previous = json.loads(a.previous_decision.read_text(encoding="utf-8")) if a.previous_decision else None
    delta = _candidate_delta(previous, decision); (out/"candidate_delta.json").write_text(json.dumps(delta,indent=2),encoding="utf-8")
    registry=register_analysis_and_catchup(
        decision_state=decision,snapshot=snap,analysis_id=stable_id("ANALYSIS",snap["snapshot_id"],decision.get("generated_at") or snap.get("capture_time")),
        ledger_path=paths.ledger,sqlite_path=paths.sqlite,
        evidence_root=paths.evidence,adapter=adapter,now=now,max_jobs=a.catchup_max_jobs,paths=paths,
    )
    print(json.dumps({"snapshot_id":snap["snapshot_id"],"source":snap.get("source"),"freshness":snap.get("freshness",{}).get("status"),"qc":snap.get("qc",{}).get("decision"),"candidate_count":len(decision.get("entry_packet",{}).get("candidates",[])),"candidate_delta":delta,**paths.metadata(),**registry,"trade_write_enabled":False,"auto_execution_enabled":False}))
    return 0 if snap.get("source")=="LIVE_MT5" and snap.get("qc",{}).get("decision")=="PASS" else 2
if __name__=="__main__":
    try: raise SystemExit(main())
    except SnapshotUnavailable as e: print(json.dumps({"status":"REAL_MT5_UNAVAILABLE","message":str(e),"trade_write_enabled":False}),file=sys.stderr); raise SystemExit(3)
