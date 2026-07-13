from __future__ import annotations

from typing import Any


def build_outcome_label_queue(intake: dict[str, Any]) -> dict[str, Any]:
    """Select only ready candidates for independent closed-bar labeling.

    This function never infers an outcome. A queue item remains unlabeled until
    an external/reviewer process supplies post-capture closed bars.
    """

    items: list[dict[str, Any]] = []
    for record in intake.get("records", []):
        for candidate in record.get("candidates", []):
            if candidate.get("status") != "READY_FOR_PERMISSION_REVIEW":
                continue
            items.append({
                "label_id": f"LABEL_{record['intake_id']}_{candidate['candidate_id']}",
                "intake_id": record["intake_id"],
                "snapshot_id": record["snapshot_id"],
                "capture_time": record["capture_time"],
                "symbol": record["symbol"],
                "source": record["source"],
                "partition": record["partition"],
                "candidate": candidate,
                "label_status": "NEEDS_CLOSED_BAR_REVIEW",
                "outcome_classification": None,
                "realized_r": None,
                "label_source": None,
            })
    return {
        "schema_version": "0.1.0",
        "mode": "INDEPENDENT_OUTCOME_LABEL_QUEUE",
        "source": intake.get("source"),
        "symbol": intake.get("symbol"),
        "partition": intake.get("partition"),
        "items": items,
        "summary": {
            "labelable_candidate_count": len(items),
            "labeled_count": 0,
            "unlabeled_count": len(items),
        },
        "readiness": "READY_FOR_LABELING" if items else "NO_LABELABLE_CANDIDATES",
        "execution_permission_effect": "NONE",
        "limitations": [
            "Only READY_FOR_PERMISSION_REVIEW candidates enter this queue.",
            "Outcomes require independent post-capture closed-bar evidence.",
            "An empty queue is not evidence of no trading edge; it indicates no qualifying candidate was observed.",
        ],
    }
