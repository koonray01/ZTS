"""Deterministic directional outcome policy implementations."""

from __future__ import annotations

from typing import Any

from .identity import stable_id


def _base(decision: dict[str, Any], job: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "outcome_id": stable_id("MODEL_OUTCOME", decision["decision_id"], job["horizon"], decision["labeling_policy_version"]),
        "decision_id": decision["decision_id"], "decision_type": "DIRECTIONAL",
        "system": decision["system"], "horizon": job["horizon"],
        "original_policy_version": decision["labeling_policy_version"],
        "evidence_refs": list(evidence.get("evidence_refs", [])),
        "safety": dict(decision.get("safety", {})),
    }


def label_directional(
    decision: dict[str, Any],
    job: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    result = _base(decision, job, evidence)
    qc = evidence.get("qc") if isinstance(evidence.get("qc"), dict) else {}
    if qc.get("status") != "PASS":
        reasons = list(qc.get("reasons", []))
        result.update(
            classification="AMBIGUOUS" if "EVIDENCE_CONFLICT" in reasons else "INVALID_INPUT",
            reason_codes=reasons or ["EVIDENCE_QC_NOT_PASS"],
        )
        return result
    terminal = evidence.get("terminal") if isinstance(evidence.get("terminal"), dict) else {}
    if terminal.get("status") != "PASS":
        result.update(
            classification="INSUFFICIENT_FOLLOWUP",
            reason_codes=[str(terminal.get("reason") or "TERMINAL_BAR_UNAVAILABLE")],
        )
        return result
    terminal_bar = terminal.get("bar") if isinstance(terminal.get("bar"), dict) else {}
    terminal_mid = terminal_bar.get("mid_close")
    conditional = decision.get("decision_subtype") == "CONDITIONAL_DIRECTIONAL"
    if conditional:
        reference = job.get("evaluation_reference_price")
        atr = job.get("evaluation_atr")
    else:
        reference = (decision.get("reference_price") or {}).get("value")
        atr = (decision.get("atr") or {}).get("value")
    if not all(isinstance(value, (int, float)) for value in (terminal_mid, reference, atr)) or float(atr) <= 0:
        result.update(classification="INVALID_INPUT", reason_codes=["REFERENCE_ATR_OR_TERMINAL_INVALID"])
        return result
    direction = decision.get("direction")
    if direction not in {"BULLISH", "BEARISH"}:
        result.update(classification="INVALID_INPUT", reason_codes=["DIRECTION_NOT_BINARY"])
        return result
    sign = 1.0 if direction == "BULLISH" else -1.0
    signed_return_atr = sign * (float(terminal_mid) - float(reference)) / float(atr)
    classification = "CORRECT" if signed_return_atr >= 0.25 else "INCORRECT" if signed_return_atr <= -0.25 else "NEUTRAL"
    highs = [float(bar["mid_high"]) for bar in evidence.get("bars", []) if isinstance(bar.get("mid_high"), (int, float))]
    lows = [float(bar["mid_low"]) for bar in evidence.get("bars", []) if isinstance(bar.get("mid_low"), (int, float))]
    if direction == "BULLISH":
        mfe = (max(highs) - float(reference)) / float(atr) if highs else None
        mae = (min(lows) - float(reference)) / float(atr) if lows else None
    else:
        mfe = (float(reference) - min(lows)) / float(atr) if lows else None
        mae = (float(reference) - max(highs)) / float(atr) if highs else None
    result.update(
        classification=classification, reason_codes=[],
        evaluation_reference_price=float(reference), evaluation_atr=float(atr),
        terminal_mid=float(terminal_mid), signed_return_atr=signed_return_atr,
        mfe_atr=mfe, mae_atr=mae,
    )
    return result
