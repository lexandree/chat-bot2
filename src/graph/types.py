"""Shared typed records for the legal graph foundation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Literal

RELATION_TYPES = (
    "CITES",
    "DEFINES",
    "APPLIES_IF",
    "REQUIRES",
    "EXCEPTION_TO",
    "EXCLUDES_IF",
    "AMENDS",
    "SUPERSEDED_BY",
)
MANDATORY_CLASSIFIER_RELATION_TYPES = (
    "CITES",
    "DEFINES",
    "APPLIES_IF",
    "REQUIRES",
    "EXCEPTION_TO",
)
DEFERRED_RELATION_TYPES = ("EXCLUDES_IF", "AMENDS", "SUPERSEDED_BY")
RESOLUTION_STATUSES = ("resolved", "out_of_scope", "unresolved", "ambiguous")
UNRESOLVED_REASONS = (
    "missing_target_in_corpus",
    "out_of_scope_law",
    "ambiguous_target",
    "parse_incomplete",
    "target_without_law_code",
)
UNIT_STATUSES = ("active", "inactive")
TARGET_UNIT_STATUSES = ("active", "inactive", "missing_target_in_corpus", "out_of_scope_law")
TEMPORAL_EVIDENCE_STATUSES = ("available", "partial", "not_available", "not_applicable")
CLASSIFIER_POLICY_VERSION = "legal-ref-context-v1"
STRUCTURE_CLASS_RULES_VERSION = "structure-class-rules-v1"
STRUCTURE_CLASSES = (
    "inactive_skipped",
    "mixed_content",
    "definition_heavy",
    "list_heavy",
    "simple_paragraph",
    "unknown",
)
STRUCTURAL_WORKFLOW_MODES = ("seed_neighborhood", "law_scope_overview")
STRUCTURAL_WORKFLOW_DIRECTIONS = ("outgoing", "incoming", "both")
STRUCTURAL_WORKFLOW_SECTION_ROLES = (
    "seed",
    "resolved_neighbor",
    "scope_member",
    "cross_scope_context",
    "inactive_context",
)
MISSING_TARGET_INVENTORY_STATUSES = (
    "not_provided",
    "available",
    "missing_file",
    "stale",
    "scope_mismatch",
)
INVENTORY_MATCH_STATUSES = ("matched", "not_found", "not_checked", "stale_inventory")
STRUCTURAL_WORKFLOW_DEFAULT_BOUNDS = {
    "direction": "outgoing",
    "max_depth": 1,
    "fanout_limit": 25,
    "node_limit": 100,
    "edge_limit": 500,
    "source_sample_limit": 5,
}
STRUCTURAL_WORKFLOW_MAX_BOUNDS = {
    "max_depth": 2,
    "fanout_limit": 100,
    "node_limit": 1000,
    "edge_limit": 5000,
    "source_sample_limit": 20,
}


def to_plain_dict(value: Any) -> Any:
    """Convert dataclass records into JSON-serializable primitives."""
    if is_dataclass(value):
        return {key: to_plain_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): to_plain_dict(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_plain_dict(item) for item in value]
    return value


@dataclass(slots=True)
class SelectedScope:
    law_codes: list[str] = field(default_factory=list)
    source_families: list[str] = field(default_factory=lambda: ["law"])

    def normalized_law_codes(self) -> list[str]:
        return sorted({code.strip() for code in self.law_codes if code.strip()})

    def as_dict(self) -> dict[str, list[str]]:
        data: dict[str, list[str]] = {"source_families": list(self.source_families)}
        if self.law_codes:
            data["law_codes"] = self.normalized_law_codes()
        return data


@dataclass(slots=True)
class SourceDocument:
    source_document_id: str
    source_family: str
    jurisdiction: str
    language: str
    law_code: str
    source_uri: str = ""
    local_reference: str = ""
    publication_date: str = ""
    effective_date: str = ""
    retrieved_at: str = ""
    source_version_id: str = ""
    source_revision_marker: str = ""
    build_date: str = ""
    freshness_metadata: dict[str, Any] = field(default_factory=dict)
    checksum: str = ""


@dataclass(slots=True)
class SourceFragment:
    source_fragment_id: str
    source_document_id: str
    law_code: str
    section_reference: str
    title: str
    body_text: str
    order_index: int
    checksum: str
    source_version_id: str = ""
    source_revision_marker: str = ""
    build_date: str = ""
    status_marker_text: str = ""


@dataclass(slots=True)
class LegalAct:
    legal_act_id: str
    law_code: str
    title: str
    source_family: str = "law"
    jurisdiction: str = "DE"
    language: str = "de"
    valid_from: str = ""
    valid_to: str = ""
    is_current: bool = True


@dataclass(slots=True)
class LegalSection:
    legal_section_id: str
    legal_act_id: str
    law_code: str
    section_reference: str
    title: str
    normalized_reference: str
    valid_from: str = ""
    valid_to: str = ""
    version_identity: str = "current"
    is_current: bool = True
    unit_status: Literal["active", "inactive"] = "active"
    status_marker_text: str = ""
    source_document_id: str = ""
    source_fragment_id: str = ""
    source_version_id: str = ""
    source_revision_marker: str = ""
    build_date: str = ""
    content_checksum: str = ""


@dataclass(slots=True)
class LegalFragment:
    legal_fragment_id: str
    legal_section_id: str
    source_fragment_id: str
    text: str
    order_index: int
    checksum: str


@dataclass(slots=True)
class LegalReference:
    legal_reference_id: str
    source_legal_section_id: str
    target_law_code: str
    target_section_reference: str
    source_legal_fragment_id: str = ""
    source_fragment_id: str = ""
    law_code: str = ""
    raw_reference_text: str = ""
    normalized_reference_text: str = ""
    target_legal_section_id: str = ""
    target_unit_status: str = ""
    unresolved_reason: str = ""
    subsection_anchor: dict[str, Any] = field(default_factory=dict)
    context_before: str = ""
    context_text: str = ""
    context_after: str = ""
    context_checksum: str = ""
    primary_relation_type: str = "CITES"
    secondary_relation_signals: list[str] = field(default_factory=list)
    classifier_policy_version: str = CLASSIFIER_POLICY_VERSION
    relation_type: str = "CITES"
    resolution_status: Literal["resolved", "out_of_scope", "unresolved", "ambiguous"] = "unresolved"
    unresolved_target_evidence: dict[str, Any] = field(default_factory=dict)
    effective_from: str = ""
    effective_until: str = ""
    publication_date: str = ""
    source_version_id: str = ""
    source_revision_marker: str = ""
    build_date: str = ""
    temporal_context_text: str = ""
    temporal_context_checksum: str = ""
    temporal_evidence_status: Literal["available", "partial", "not_available", "not_applicable"] = (
        "not_applicable"
    )


@dataclass(slots=True)
class ParsedReferenceCandidate:
    parsed_reference_id: str
    source_legal_section_id: str
    source_legal_fragment_id: str
    source_fragment_id: str
    law_code: str
    raw_reference_text: str
    normalized_reference_text: str
    target_law_code: str
    target_section_reference: str
    target_law_code_explicit: bool = False
    subsection_anchor: dict[str, Any] = field(default_factory=dict)
    context_before: str = ""
    context_text: str = ""
    context_after: str = ""
    context_checksum: str = ""
    primary_relation_type: str = "CITES"
    secondary_relation_signals: list[str] = field(default_factory=list)
    classifier_policy_version: str = CLASSIFIER_POLICY_VERSION
    effective_from: str = ""
    effective_until: str = ""
    publication_date: str = ""
    source_version_id: str = ""
    source_revision_marker: str = ""
    build_date: str = ""
    temporal_context_text: str = ""
    temporal_context_checksum: str = ""
    temporal_evidence_status: Literal["available", "partial", "not_available", "not_applicable"] = (
        "not_applicable"
    )

    @property
    def relation_type(self) -> str:
        return self.primary_relation_type


@dataclass(slots=True)
class RelationshipRefreshReport:
    refresh_id: str
    selected_scope: dict[str, Any]
    classifier_policy_version: str
    started_at: str
    finished_at: str
    processed_fragment_count: int = 0
    created_reference_count: int = 0
    updated_reference_count: int = 0
    created_edge_count: int = 0
    updated_edge_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    status: Literal["completed", "failed"] = "completed"
    counts_by_relation_type: dict[str, int] = field(default_factory=dict)
    counts_by_resolution_status: dict[str, int] = field(default_factory=dict)
    counts_by_target_unit_status: dict[str, int] = field(default_factory=dict)
    counts_by_unresolved_reason: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RelationshipVerificationReport:
    selected_scope: dict[str, Any]
    classifier_policy_version: str
    counts_by_relation_type: dict[str, int]
    counts_by_resolution_status: dict[str, int]
    counts_by_target_unit_status: dict[str, int] = field(default_factory=dict)
    counts_by_unresolved_reason: dict[str, int] = field(default_factory=dict)
    sample_reference_ids: list[str] = field(default_factory=list)
    sample_edge_ids: list[str] = field(default_factory=list)
    unresolved_reference_evidence: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_reference_evidence: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class RelationshipQualityArtifact:
    artifact_id: str
    selected_scope: dict[str, Any]
    classifier_policy_version: str
    generated_at: str
    counts_by_relation_type: dict[str, int]
    counts_by_source_unit_status: dict[str, int]
    counts_by_target_unit_status: dict[str, int]
    counts_by_resolution_status: dict[str, int]
    counts_by_unresolved_reason: dict[str, int]
    sample_edges_by_relation_type: dict[str, list[dict[str, Any]]]
    sample_reference_evidence: list[dict[str, Any]]
    top_unresolved_targets: list[dict[str, Any]]
    top_missing_targets: list[dict[str, Any]]
    source_to_relation_coverage: dict[str, Any]
    fanout_summary: dict[str, Any]
    temporal_metadata_completeness: dict[str, Any]
    deferred_relation_strategy: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        payload = to_plain_dict(self)
        for forbidden in ("answer_text", "answer", "generated_answer"):
            payload.pop(forbidden, None)
        return payload


@dataclass(slots=True)
class GraphReadinessReport:
    status: Literal["ready", "failed"]
    database_name: str
    schema_objects: list[str]
    vector_dimensions: int
    candidate_review_placeholders_present: bool
    connectivity_checked: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LoadRunReport:
    load_run_id: str
    selected_scope: dict[str, Any]
    write_semantics: str = "idempotent_upsert"
    processed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    source_document_count: int = 0
    source_fragment_count: int = 0
    legal_section_count: int = 0
    legal_reference_count: int = 0
    unresolved_reference_count: int = 0
    counts_by_source_unit_status: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EmbeddingRunReport:
    embedding_run_id: str
    selected_scope: dict[str, Any]
    embedding_profile_id: str
    model_id: str
    backend_name: str
    routing_mode: str
    vector_dimensions: int
    normalized: bool
    processed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    failure_reason: str | None = None


@dataclass(slots=True)
class VerificationReport:
    selected_scope: dict[str, Any]
    source_document_count: int = 0
    source_fragment_count: int = 0
    legal_act_count: int = 0
    legal_section_count: int = 0
    legal_fragment_count: int = 0
    legal_reference_count: int = 0
    unresolved_reference_count: int = 0
    counts_by_source_unit_status: dict[str, int] = field(default_factory=dict)
    embedding_count: int = 0
    embedding_profile_ids: list[str] = field(default_factory=list)
    vector_dimensions: list[int] = field(default_factory=list)
    backend_names: list[str] = field(default_factory=list)
    candidate_review_placeholders_present: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DeletionReport:
    selected_scope: dict[str, Any]
    matched_records: int = 0
    removed_records: int = 0
    skipped_records: int = 0
    retained_related_records: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StructuralRetrievalResult:
    query_reference: dict[str, str]
    matched_legal_section_id: str
    source_references: list[str]
    relation_types: list[str]
    depth_limit: int
    fanout_limit: int
    node_limit: int
    visited_count: int
    unresolved_target_evidence: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        payload = to_plain_dict(self)
        for forbidden in ("answer_text", "answer", "generated_answer"):
            payload.pop(forbidden, None)
        return payload


@dataclass(slots=True)
class StructuralWorkflowRequest:
    workflow_mode: str
    seed_legal_section_ids: list[str] = field(default_factory=list)
    law_codes: list[str] = field(default_factory=list)
    direction: str = STRUCTURAL_WORKFLOW_DEFAULT_BOUNDS["direction"]
    max_depth: int = STRUCTURAL_WORKFLOW_DEFAULT_BOUNDS["max_depth"]
    allowed_relation_types: list[str] = field(default_factory=lambda: list(RELATION_TYPES))
    fanout_limit: int = STRUCTURAL_WORKFLOW_DEFAULT_BOUNDS["fanout_limit"]
    node_limit: int = STRUCTURAL_WORKFLOW_DEFAULT_BOUNDS["node_limit"]
    edge_limit: int = STRUCTURAL_WORKFLOW_DEFAULT_BOUNDS["edge_limit"]
    source_sample_limit: int = STRUCTURAL_WORKFLOW_DEFAULT_BOUNDS["source_sample_limit"]
    include_boundary_stops: bool = True
    include_inactive_sections: bool = True

    def as_dict(self) -> dict[str, Any]:
        return to_plain_dict(self)


@dataclass(slots=True)
class WorkflowSectionNode:
    legal_section_id: str
    law_code: str
    section_reference: str
    unit_status: str
    depth: int
    role: str
    legal_act_id: str = ""
    normalized_reference: str = ""
    title: str = ""
    status_marker_text: str = ""
    source_document_id: str = ""
    source_fragment_id: str = ""
    source_version_id: str = ""
    source_revision_marker: str = ""
    build_date: str = ""
    content_checksum: str = ""


@dataclass(slots=True)
class ResolvedTraversalEdge:
    source_legal_section_id: str
    target_legal_section_id: str
    relation_type: str
    depth: int
    legal_reference_ids: list[str]
    source_fragment_ids: list[str] = field(default_factory=list)
    target_law_code: str = ""
    target_section_reference: str = ""
    target_unit_status: str = ""
    classifier_policy_version: str = ""
    effective_from: str = ""
    effective_until: str = ""
    publication_date: str = ""
    source_version_id: str = ""
    source_revision_marker: str = ""
    build_date: str = ""
    temporal_evidence_status: str = ""
    cycle_boundary: bool = False
    truncated: bool = False


@dataclass(slots=True)
class CoverageBoundaryStop:
    boundary_id: str
    source_legal_section_id: str
    source_fragment_id: str
    legal_reference_id: str
    raw_reference_text: str
    normalized_reference_text: str | None
    target_law_code: str
    target_section_reference: str
    reason: str
    count: int
    source_samples: list[dict[str, Any]]
    inventory_match: str = "not_checked"


@dataclass(slots=True)
class WorkflowQualitySummary:
    workflow_mode: str
    visited_section_count: int
    resolved_edge_count: int
    resolved_edges_by_relation_type: dict[str, int]
    boundary_stop_count: int
    boundary_stops_by_reason: dict[str, int]
    truncation_count: int
    cycle_boundary_count: int
    inactive_section_count: int
    provenance_completeness: dict[str, Any]
    missing_target_inventory_status: str
    skipped_path_count: int = 0


@dataclass(slots=True)
class StructuralWorkflowArtifact:
    artifact_id: str
    artifact_type: str
    generated_at: str
    workflow_id: str
    workflow_request: dict[str, Any]
    selected_scope: dict[str, Any]
    sections: list[dict[str, Any]]
    resolved_edges: list[dict[str, Any]]
    coverage_boundary_stops: list[dict[str, Any]]
    quality_summary: dict[str, Any]
    ordering_policy: dict[str, Any]
    source_relationship_quality_artifact: str = ""
    missing_target_inventory_reference: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        payload = to_plain_dict(self)
        for forbidden in ("answer_text", "answer", "generated_answer"):
            payload.pop(forbidden, None)
        return payload


@dataclass(slots=True)
class CorpusReadinessArtifact:
    artifact_id: str
    selected_scope: dict[str, Any]
    generated_at: str
    structure_class_rules_version: str
    counts_by_unit_status: dict[str, int]
    counts_by_structure_class: dict[str, int]
    active_unit_samples: list[dict[str, Any]]
    inactive_unit_samples: list[dict[str, Any]]
    complexity_summary: dict[str, Any]
    excluded_semantic_candidates: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        payload = to_plain_dict(self)
        for forbidden in ("answer_text", "answer", "generated_answer"):
            payload.pop(forbidden, None)
        return payload


@dataclass(slots=True)
class GraphSnapshotArtifact:
    snapshot_id: str
    selected_scope: dict[str, Any]
    source_scope: dict[str, Any]
    counts: dict[str, int]
    labels: dict[str, int]
    relation_types: dict[str, int]
    sample_ids: dict[str, list[str]]
    source_coverage: dict[str, Any]
    embedding_profile_metadata: dict[str, Any]
    unresolved_reference_evidence: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return to_plain_dict(self)


@dataclass(slots=True)
class LegacyAufenthGBaselineGraphSnapshotArtifact(GraphSnapshotArtifact):
    baseline_scope: dict[str, Any] = field(default_factory=dict)
    baseline_origin: str = "legacy_aufenthg_graph_scope"


@dataclass(slots=True)
class SnapshotComparisonReport:
    comparison_id: str
    new_snapshot_id: str
    baseline_snapshot_id: str
    matching: dict[str, Any]
    missing: dict[str, Any]
    extra: dict[str, Any]
    summary_counts: dict[str, int]
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return to_plain_dict(self)
