"""Shared typed records for the legal graph foundation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Literal


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
    relation_type: str = "CITES"
    resolution_status: Literal["resolved", "unresolved", "ambiguous"] = "unresolved"
    source_legal_fragment_id: str = ""
    target_legal_section_id: str = ""
    unresolved_target_evidence: dict[str, Any] = field(default_factory=dict)
    raw_reference_text: str = ""
    normalized_reference_text: str = ""


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
