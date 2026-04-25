"""Review actions for candidate claims and enrichment outputs."""

from __future__ import annotations


ALLOWED_DECISIONS = {"approve": "verified", "reject": "rejected", "deprecate": "deprecated"}
CANDIDATE_REVIEW_STATES = {"pending", "approved", "rejected", "deprecated"}
CANDIDATE_DECISIONS = {"approve": "approved", "reject": "rejected", "deprecate": "deprecated"}


def apply_review_decision(claim: dict[str, object], decision: str) -> dict[str, object]:
    if decision not in ALLOWED_DECISIONS:
        raise ValueError(f"Unsupported review decision: {decision}")
    updated = dict(claim)
    updated["trust_state"] = ALLOWED_DECISIONS[decision]
    updated["decision"] = decision
    return updated


def initialize_candidate_review_state(item: dict[str, object]) -> dict[str, object]:
    updated = dict(item)
    updated["review_state"] = "pending"
    updated["trusted"] = False
    return updated


def apply_candidate_review_decision(item: dict[str, object], decision: str) -> dict[str, object]:
    if decision not in CANDIDATE_DECISIONS:
        raise ValueError(f"Unsupported candidate review decision: {decision}")
    updated = dict(item)
    updated["review_state"] = CANDIDATE_DECISIONS[decision]
    updated["decision"] = decision
    return updated


def build_candidate_review_task(
    item: dict[str, object],
    *,
    assigned_reviewer: str = "moderator",
) -> dict[str, object]:
    return {
        "candidate_claim_id": item.get("candidate_claim_id"),
        "run_id": item.get("run_id"),
        "assigned_reviewer": assigned_reviewer,
        "status": "pending",
        "review_state": item.get("review_state", "pending"),
    }


def build_proposition_review_task(
    item: dict[str, object],
    *,
    assigned_reviewer: str = "moderator",
) -> dict[str, object]:
    return {
        "proposition_candidate_id": item.get("proposition_candidate_id"),
        "run_id": item.get("run_id"),
        "assigned_reviewer": assigned_reviewer,
        "status": "pending",
        "review_state": item.get("review_state", "pending"),
    }
