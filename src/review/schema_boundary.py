"""Candidate/review schema placeholders without review workflow behavior."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CandidateReviewSchemaBoundary:
    candidate_label: str = "Candidate"
    support_label: str = "CandidateSupport"
    review_state_property: str = "review_state"
    grounding_flags_property: str = "grounding_flags"
    isolation_state_property: str = "isolation_state"
    runtime_metadata_property: str = "runtime_metadata"

    def constraint_names(self) -> list[str]:
        return [
            "candidate_id_unique",
            "candidate_support_id_unique",
        ]

    def placeholder_properties(self) -> list[str]:
        return [
            "candidate_id",
            "support_reference_id",
            self.review_state_property,
            self.grounding_flags_property,
            self.isolation_state_property,
            self.runtime_metadata_property,
        ]

    def assert_no_workflow_behavior(self) -> None:
        """Document that this module owns schema identity only."""
        return None
