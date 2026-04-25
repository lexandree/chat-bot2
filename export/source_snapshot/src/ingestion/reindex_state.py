"""Operational state models for resumable reindex and enrichment jobs."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ReindexJob:
    job_id: str
    target_profile_id: str
    backend_name: str
    status: str = "planned"
    processed_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    resume_cursor: int = 0


@dataclass(slots=True)
class ReindexItemState:
    entity_id: str
    state: str = "pending"
    last_error: str = ""


@dataclass(slots=True)
class ReindexExecutionState:
    job: ReindexJob
    items: list[ReindexItemState] = field(default_factory=list)


@dataclass(slots=True)
class EnrichmentRunItemState:
    source_id: str
    state: str = "pending"
    last_error: str = ""


@dataclass(slots=True)
class EnrichmentRunRecord:
    run_id: str
    run_name: str
    runtime_contour: str
    source_scope_ref: str
    extraction_policy_version: str
    question_set_ref: str
    mode: str
    status: str = "planned"
    effective_llm_backend: str = ""
    effective_embedding_backend: str = ""
    llm_model_id: str = ""
    embedding_model_id: str = ""
    processed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    resume_cursor: int = 0
    created_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class EnrichmentExecutionState:
    run: EnrichmentRunRecord
    items: list[EnrichmentRunItemState] = field(default_factory=list)


@dataclass(slots=True)
class LegalExtractionItemState:
    fragment_id: str
    state: str = "pending"
    last_error: str = ""


@dataclass(slots=True)
class LegalExtractionRunState:
    run_id: str
    run_name: str
    runtime_contour: str
    run_mode: str
    prompt_or_policy_version: str
    source_scope_ref: str = ""
    validation_set_ref: str = ""
    status: str = "planned"
    effective_llm_backend: str = ""
    effective_embedding_backend: str = ""
    llm_model_id: str = ""
    embedding_model_id: str = ""
    processed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    resume_cursor: int = 0
    created_at: str = ""
    updated_at: str = ""
    finished_at: str = ""


@dataclass(slots=True)
class LegalExtractionExecutionState:
    run: LegalExtractionRunState
    items: list[LegalExtractionItemState] = field(default_factory=list)
