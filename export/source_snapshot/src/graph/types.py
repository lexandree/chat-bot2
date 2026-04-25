"""Shared graph-side types for provenance, review state, and legal graph artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


TRUST_STATES = {"draft", "verified", "rejected", "deprecated"}
REVIEW_STATES = {"pending", "approved", "rejected", "deprecated"}
ALLOWED_SOURCE_TYPES = {"law", "official_guidance"}
RUNTIME_CONTOURS = {"managed_paid", "operator_managed"}
TEMPORAL_MODES = {"current_default", "as_of_date"}
VALIDATION_RESULT_MODES = {"baseline", "enriched", "structural_baseline", "semantic_enriched"}


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class ProvenanceRecord:
    source_id: str
    source_type: str
    source_ref: str
    imported_at: datetime = field(default_factory=utc_now)
    extractor_version: str = "manual-v1"
    freshness_status: str = "current"


@dataclass(slots=True)
class TrustState:
    state: str = "draft"

    def __post_init__(self) -> None:
        if self.state not in TRUST_STATES:
            raise ValueError(f"Unsupported trust state: {self.state}")


@dataclass(slots=True)
class SourceDocument:
    source_id: str
    source_type: str
    title: str
    jurisdiction: str
    language: str
    source_uri_or_ref: str
    published_at: str = ""
    effective_from: str = ""
    retrieved_at: str = ""
    freshness_note: str = ""
    checksum: str = ""

    def __post_init__(self) -> None:
        if self.source_type not in ALLOWED_SOURCE_TYPES:
            raise ValueError(f"Unsupported source type: {self.source_type}")


@dataclass(slots=True)
class SourceFragment:
    fragment_id: str
    source_id: str
    ordinal: int
    text: str
    start_ref: str = ""
    end_ref: str = ""
    language: str = ""
    checksum: str = ""


@dataclass(slots=True)
class CandidateEntity:
    candidate_entity_id: str
    entity_type: str
    canonical_name: str
    aliases: tuple[str, ...] = ()
    language: str = ""
    run_id: str = ""
    review_state: str = "pending"
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.review_state not in REVIEW_STATES:
            raise ValueError(f"Unsupported review state: {self.review_state}")


@dataclass(slots=True)
class CandidateClaim:
    candidate_claim_id: str
    claim_type: str
    claim_text: str
    normalized_claim_text: str
    source_confidence: float
    run_id: str
    review_state: str = "pending"
    created_at: datetime = field(default_factory=utc_now)
    approved_at: str = ""
    rejected_at: str = ""

    def __post_init__(self) -> None:
        if self.review_state not in REVIEW_STATES:
            raise ValueError(f"Unsupported review state: {self.review_state}")


@dataclass(slots=True)
class EnrichmentRunRecord:
    run_id: str
    run_name: str
    status: str
    runtime_contour: str
    effective_llm_backend: str = ""
    effective_embedding_backend: str = ""
    llm_model_id: str = ""
    embedding_model_id: str = ""
    extraction_policy_version: str = ""
    source_scope_ref: str = ""
    created_at: datetime = field(default_factory=utc_now)
    started_at: str = ""
    updated_at: str = ""
    finished_at: str = ""
    processed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    resume_cursor: int = 0

    def __post_init__(self) -> None:
        if self.runtime_contour not in RUNTIME_CONTOURS:
            raise ValueError(f"Unsupported runtime contour: {self.runtime_contour}")


@dataclass(slots=True)
class ValidationQuestionSet:
    question_set_id: str
    name: str
    source_strategy: str
    scope_note: str
    created_at: datetime = field(default_factory=utc_now)
    version: str = "v1"


@dataclass(slots=True)
class ValidationQuestion:
    question_id: str
    question_set_id: str
    prompt_text: str
    language: str
    expected_topic: str
    success_outcome: str
    expected_support_refs: tuple[str, ...] = ()


@dataclass(slots=True)
class ValidationRunResult:
    validation_result_id: str
    run_id: str
    question_id: str
    mode: str
    observed_support_refs: tuple[str, ...] = ()
    outcome_label: str = ""
    review_notes: str = ""
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.mode not in {"baseline", "enriched"}:
            raise ValueError(f"Unsupported validation mode: {self.mode}")


@dataclass(slots=True)
class LegalAct:
    law_code: str
    title: str
    jurisdiction: str = "DE"
    language: str = "de"
    source_uri_or_ref: str = ""
    published_at: str = ""
    valid_from: str = ""
    valid_to: str = ""
    current_version: bool = True


@dataclass(slots=True)
class LegalSection:
    section_id: str
    law_code: str
    section_ref: str
    title: str
    body_text: str
    valid_from: str = ""
    valid_to: str = ""
    version_key: str = "current"
    is_current: bool = True


@dataclass(slots=True)
class LegalFragment:
    fragment_id: str
    section_id: str
    ordinal: int
    text: str
    start_ref: str = ""
    end_ref: str = ""
    checksum: str = ""


@dataclass(slots=True)
class LegalReference:
    reference_id: str
    source_section_id: str
    raw_reference_text: str
    normalized_reference_text: str
    target_law_code: str
    target_section_ref: str
    reference_type: str
    resolution_state: str


@dataclass(slots=True)
class PropositionCandidate:
    proposition_candidate_id: str
    proposition_text: str
    proposition_type: str
    run_id: str
    review_state: str = "pending"
    created_at: datetime = field(default_factory=utc_now)
    approved_at: str = ""
    rejected_at: str = ""
    isolation_state: str = ""

    def __post_init__(self) -> None:
        if self.review_state not in REVIEW_STATES:
            raise ValueError(f"Unsupported review state: {self.review_state}")


@dataclass(slots=True)
class PropositionSupport:
    support_id: str
    proposition_candidate_id: str
    fragment_id: str
    section_id: str
    citation_text: str
    support_role: str = "primary"


@dataclass(slots=True)
class ExtractionRun:
    run_id: str
    run_name: str
    status: str
    run_mode: str
    runtime_contour: str
    effective_llm_backend: str = ""
    effective_embedding_backend: str = ""
    llm_model_id: str = ""
    embedding_model_id: str = ""
    prompt_or_policy_version: str = ""
    created_at: datetime = field(default_factory=utc_now)
    started_at: str = ""
    updated_at: str = ""
    finished_at: str = ""
    processed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    resume_cursor: int = 0

    def __post_init__(self) -> None:
        if self.runtime_contour not in RUNTIME_CONTOURS:
            raise ValueError(f"Unsupported runtime contour: {self.runtime_contour}")


@dataclass(slots=True)
class ValidationCaseSet:
    validation_set_id: str
    name: str
    scope_note: str
    created_at: datetime = field(default_factory=utc_now)
    version: str = "v1"


@dataclass(slots=True)
class ValidationCase:
    case_id: str
    validation_set_id: str
    prompt_text: str
    case_type: str
    expected_support_refs: tuple[str, ...]
    expected_outcome: str
    as_of_date: str = ""


@dataclass(slots=True)
class ValidationResult:
    validation_result_id: str
    run_id: str
    case_id: str
    mode: str
    observed_support_refs: tuple[str, ...] = ()
    outcome_label: str = ""
    review_notes: str = ""
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.mode not in VALIDATION_RESULT_MODES:
            raise ValueError(f"Unsupported validation mode: {self.mode}")
