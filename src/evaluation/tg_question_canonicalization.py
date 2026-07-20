"""Canonical legal question evaluation artifacts for Telegram QA candidates."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from time import perf_counter, sleep
from typing import Any, Iterable, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from evaluation.llm_runtime_profiles import (
    atomic_structured_output_adapter_version,
    load_atomic_runtime_profile_registry,
    resolve_atomic_runtime_stage,
)
from evaluation.prompts import (
    CANONICALIZATION_ADJUDICATOR_PROMPT_PROFILE,
    CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION,
    CANONICALIZATION_ATOMIC_CRITIC_PROMPT_PROFILE,
    CANONICALIZATION_ATOMIC_CRITIC_PROMPT_VERSION,
    CANONICALIZATION_ATOMIC_REPAIR_PROMPT_PROFILE,
    CANONICALIZATION_ATOMIC_REPAIR_PROMPT_VERSION,
    CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_PROFILE,
    CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_VERSION,
    CANONICALIZATION_PROMPT_EXAMPLES,
    CANONICALIZATION_PROMPT_EXAMPLE_SET_ID,
    CANONICALIZATION_PROMPT_VERSION,
    CANONICALIZATION_SYSTEM_INSTRUCTION,
    CANONICALIZATION_VERIFIER_PROMPT_PROFILE,
    CANONICALIZATION_VERIFIER_PROMPT_VERSION,
    EXPECTED_CANONICALIZATION_SCHEMA,
    LEGAL_INTENT_EXTRACTOR_PROMPT_PROFILE,
    LEGAL_INTENT_EXTRACTOR_PROMPT_VERSION,
    LEGAL_INTENT_PAIR_JUDGE_PROMPT_PROFILE,
    LEGAL_INTENT_PAIR_JUDGE_PROMPT_VERSION,
    load_prompt_profile_data,
)
from retrieval.embedding_profile import DOCUMENT_PREFIX, QUERY_PREFIX, EmbeddingProfile, validate_vector


CANONICALIZATION_CONTRACT_VERSION = "tg_question_canonicalization_v2"
CANONICALIZATION_IDENTITY_POLICY_VERSION = "tg_question_canonicalization_identity_v1"
CANONICALIZATION_ROUTING_POLICY_VERSION = "tg_question_canonicalization_routing_v2"
CANONICALIZATION_FINALIZATION_POLICY_VERSION = "tg_question_canonicalization_finalization_v1"
CANONICALIZATION_SNAPSHOT_POLICY_VERSION = "tg_question_canonicalization_snapshot_v2"
CANONICAL_EMBEDDING_POLICY_VERSION = "tg_canonical_query_embedding_v1"
ISSUE_CLUSTER_POLICY_VERSION = "tg_legal_issue_cluster_policy_v1"
COVERAGE_ANALYSIS_VERSION = "tg_legal_issue_coverage_v1"
CLUSTER_REVIEW_POLICY_VERSION = "tg_legal_issue_cluster_review_v2"
QUESTION_BANK_POLICY_VERSION = "tg_legal_question_bank_v2"
PROMOTION_POLICY_VERSION = "tg_legal_issue_final_case_promotion_v2"
REFERENCE_ANSWER_POLICY_VERSION = "reviewed_reference_answer_required_v1"
REVIEWED_DATASET_POLICY_VERSION = "tg_reviewed_canonical_evaluation_dataset_v2"
TEMPORAL_CURRENTNESS_POLICY_VERSION = "tg_temporal_currentness_review_v1"
LEGAL_INTENT_CANDIDATE_POLICY_VERSION = "tg_legal_intent_candidate_policy_v1"
LEGAL_INTENT_PAIR_POLICY_VERSION = "tg_legal_intent_pair_policy_v1"
LEGAL_INTENT_BENCHMARK_POLICY_VERSION = "tg_legal_intent_pair_benchmark_v1"
LEGAL_INTENT_REVIEW_POLICY_VERSION = "tg_legal_intent_pair_review_v1"
LEGAL_INTENT_EVALUATION_POLICY_VERSION = "tg_legal_intent_equivalence_evaluation_v1"
LEGAL_INTENT_SIMILARITY_BASELINE_POLICY_VERSION = "tg_legal_intent_similarity_baseline_v1"
LEGAL_INTENT_SLOT_COMPARATOR_POLICY_VERSION = "tg_legal_intent_slot_comparator_v1"
LEGAL_INTENT_EXTRACTOR_RUN_POLICY_VERSION = "tg_legal_intent_extractor_run_v1"
LEGAL_INTENT_PAIR_JUDGE_RUN_POLICY_VERSION = "tg_legal_intent_pair_judge_run_v1"
CANONICALIZATION_ATOMIC_CONTROLLER_POLICY_VERSION = "tg_question_canonicalization_atomic_controller_v6"
ATOMIC_FORMATTER_VERIFICATION_CONTRACT_VERSION = "atomic_verification_quotes_to_offsets_v1"

CANONICALIZATION_STATUSES = ("completed", "failed", "skipped")
EXCLUSION_REASONS = (
    "none",
    "non_legal_question",
    "not_standalone_question",
    "dialogue_fragment",
    "rhetorical_or_complaint_only",
    "spam_or_joke",
    "insufficient_context",
    "privacy_or_redaction_blocker",
    "malformed_input",
    "llm_failed",
)
CONFIDENCE_VALUES = ("low", "medium", "high")
ATOMIC_CLAIM_SUPPORT_VALUES = ("explicit", "necessary_inference", "unsupported", "unresolved")
ATOMIC_CLAIM_MATERIALITY_VALUES = ("low", "medium", "high")
ATOMIC_CLAIM_RELATION_KINDS = (
    "source_fact",
    "requested_outcome",
    "canonical_issue",
    "routing",
    "authority_context",
    "hidden_issue",
    "causal_dependency",
    "eligibility_condition",
    "legal_mechanism",
    "program_specificity",
    "quality_flag",
    "other",
)
ATOMIC_VERIFICATION_ROUTES = ("pass", "revise", "hold")
ATOMIC_CANDIDATE_FIELDS = (
    "canonical_question",
    "canonical_question_language",
    "legal_issue_frame",
    "legal_issue_frame_slug",
    "law_area",
    "facts",
    "desired_outcome",
    "authority_context",
    "hidden_issues",
    "is_legal_answer_required",
    "is_standalone_question",
    "exclusion_reason",
    "confidence",
    "quality_flags",
)
ATOMIC_CRITIC_FIELD_NAMES = {
    "canonical_question",
    "legal_issue_frame",
    "desired_outcome",
    "authority_context",
    "hidden_issues",
}
COVERAGE_STATUSES = ("covered", "partial", "uncovered", "excluded", "uncertain")
CLUSTER_REVIEW_DECISIONS = (
    "approve_question_bank",
    "approve_final_evaluation",
    "reject",
    "merge",
    "split",
    "needs_more_context",
    "uncertain",
)
REFERENCE_ANSWER_ACTIONS = (
    "none",
    "keep_selected_telegram_answer",
    "replace_manual",
    "needs_manual_answer",
)
TEMPORAL_RELEVANCE_STATES = (
    "current_reusable",
    "historical_but_generalizable",
    "transition_bound",
    "superseded_or_expired",
    "unresolved_currentness",
)
CURRENT_DEFAULT_TEMPORAL_STATES = ("current_reusable", "historical_but_generalizable")
TEMPORAL_BLOCKING_STATES = ("transition_bound", "superseded_or_expired", "unresolved_currentness")
PROMOTION_STATUSES = (
    "eligible",
    "blocked_missing_reference_answer",
    "blocked_temporal_currentness",
    "rejected",
)
LEGAL_INTENT_REVIEW_STATUSES = (
    "candidate",
    "review_approved",
    "review_rejected",
    "needs_more_context",
    "uncertain",
)
LEGAL_INTENT_PAIR_CLASSES = (
    "exact_duplicate",
    "same_legal_intent",
    "same_topic_different_issue",
    "related_context",
    "different",
    "uncertain",
)
LEGAL_INTENT_EQUIVALENCE_VALUES = (
    "safe_to_share_answer",
    "not_safe_to_share_answer",
    "safe_to_share_question",
    "not_safe_to_share_question",
    "uncertain",
)
LEGAL_INTENT_ANSWER_EQUIVALENCE_VALUES = (
    "safe_to_share_answer",
    "not_safe_to_share_answer",
    "uncertain",
)
LEGAL_INTENT_QUESTION_EQUIVALENCE_VALUES = (
    "safe_to_share_question",
    "not_safe_to_share_question",
    "uncertain",
)
LEGAL_INTENT_DOWNSTREAM_ACTIONS = (
    "allow_duplicate_removal",
    "allow_canonical_question_sharing",
    "allow_reference_answer_sharing",
    "allow_faq_pattern_grouping",
    "allow_retrieval_cluster_grouping",
    "route_human_review",
    "preserve_hard_negative",
)
LEGAL_INTENT_MATERIAL_SCALAR_SLOTS = (
    "law_area",
    "legal_domain",
    "actor",
    "subject",
    "current_status",
    "target_status",
    "desired_action",
    "legal_object",
    "location_scope",
    "temporal_condition",
    "operational_boundary",
)
LEGAL_INTENT_MATERIAL_LIST_SLOTS = ("authority_context", "third_party_context")
VERIFIER_VERDICTS = ("pass", "fail", "uncertain")
VERIFIER_RISK_LEVELS = ("none", "low", "medium", "high")
VERIFIER_SUGGESTED_ACTIONS = ("accept", "reject", "retry_qwen", "send_deepseek", "human_review")
ADJUDICATION_FINAL_RECOMMENDATIONS = ("accept", "reject", "retry_generator", "human_review")
DEEPSEEK_FINAL_RECOMMENDATIONS = ADJUDICATION_FINAL_RECOMMENDATIONS
CANONICALIZATION_REVIEW_DECISIONS = ("accept", "reject", "retry_qwen", "send_deepseek", "hold")
UNREVIEWED_POLICIES = ("hold", "first_pass")
AUTO_RETRY_BLOCKING_BAD_FIELDS = (
    "canonical_question",
    "exclusion_reason",
    "law_area",
)

CANONICALIZATION_FILTER_MODES = ("all", "law_or_topic", "legalish")
CANONICALIZATION_SAMPLE_POLICIES = ("balanced", "stable_hash")
CANONICALIZATION_REVIEW_PAYLOAD_VERSION = "tg_qa_canonicalization_review_payload_v1"
CANONICAL_TEXT_ROLES = ("canonical_question", "legal_issue_frame")

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
USERNAME_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{4,32}\b")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{6,}\d)(?!\w)")
SPACE_RE = re.compile(r"\s+")
SLUG_RE = re.compile(r"[^a-z0-9]+")
BEARER_TOKEN_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:api[-_ ]?key|authorization|token|secret)\b\s*[:=]\s*['\"]?[^'\"\s,;}]+"
)
API_KEY_VALUE_RE = re.compile(r"\b(?:sk|pk|ak|rk)-[A-Za-z0-9_-]{10,}\b")
CJK_RE = re.compile(
    r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\u3040-\u30FF\u31F0-\u31FF\uAC00-\uD7AF]"
)
PROVIDER_ERROR_CODE_RE = re.compile(
    r"(?i)(?:error code|status|http|<)\s*['\"]?\s*[:=]?\s*['\"]?<?\s*(\d{3})\b"
)
OPERATOR_ERROR_REASON_LIMIT = 1000
OPERATOR_PROGRESS_DETAIL_LIMIT = 280
OPERATOR_OUTPUT_RETRY_MAX_ATTEMPTS = 3
TRANSIENT_PROVIDER_ERROR_TYPE_NAMES = {
    "APIConnectionError",
    "APITimeoutError",
    "ConnectError",
    "ConnectTimeout",
    "ConnectionError",
    "InternalServerError",
    "OverloadedError",
    "RateLimitError",
    "ReadTimeout",
    "RemoteProtocolError",
    "ServiceUnavailableError",
    "TimeoutError",
    "TransportError",
    "URLError",
}


class RetryableOperatorOutputError(ValueError):
    """LLM output violated a local guard and should be regenerated."""


class AtomicInvocationError(RuntimeError):
    """Terminal atomic-stage failure with auditable metadata for every attempt."""

    def __init__(
        self,
        failure_reason: str,
        *,
        call_stage: str,
        attempt_records: Sequence[Mapping[str, Any]],
        retry_count: int,
        retry_exhausted: bool,
    ) -> None:
        super().__init__(failure_reason)
        self.call_stage = call_stage
        self.attempt_records = [dict(item) for item in attempt_records]
        self.retry_count = retry_count
        self.retry_exhausted = retry_exhausted


@dataclass(frozen=True)
class AtomicTwoStepRunner:
    """One semantic reasoning call followed by a no-reasoning schema call."""

    reasoning_runner: Any
    formatter_runner: Any
    reasoning_runtime_profile: Mapping[str, Any]
    formatter_runtime_profile: Mapping[str, Any]
    formatter_output_contract: str = "final_schema"


@dataclass(frozen=True)
class AtomicTwoStepInvocation:
    """Raw two-step outputs retained long enough to persist the bounded memo."""

    reasoning_raw: Any
    reasoning_memo: str
    formatter_raw: Any


TRANSIENT_PROVIDER_ERROR_PATTERNS = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "connection aborted",
    "connection error",
    "connection reset",
    "connection refused",
    "gateway timeout",
    "internal server error",
    "network",
    "overloaded",
    "rate limit",
    "server disconnected",
    "service unavailable",
    "temporarily unavailable",
    "timed out",
    "timeout",
    "too many requests",
    "try again",
)

class CanonicalizationResultPayload(BaseModel):
    """LLM output schema for one canonicalized Telegram question candidate."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(default="")
    task_scope: str = Field(default="question_candidate")
    candidate_id: str = Field(default="")
    canonicalization_run_id: str = Field(default="")
    canonicalization_contract_version: str = Field(default=CANONICALIZATION_CONTRACT_VERSION)
    prompt_version: str = Field(default=CANONICALIZATION_PROMPT_VERSION)
    runtime_contour: str = Field(default="operator_managed_batch_or_fixture")
    backend: str = Field(default="")
    model_id: str = Field(default="")
    status: str = Field(default="completed")
    failure_reason: str = Field(default="")
    canonical_question: str = Field(default="")
    canonical_question_language: str = Field(default="")
    legal_issue_frame: str = Field(default="")
    legal_issue_frame_slug: str = Field(default="")
    law_area: str = Field(default="")
    facts: list[str] = Field(default_factory=list)
    desired_outcome: str = Field(default="")
    authority_context: list[str] = Field(default_factory=list)
    hidden_issues: list[str] = Field(default_factory=list)
    is_legal_answer_required: bool = Field(default=False)
    is_standalone_question: bool = Field(default=False)
    exclusion_reason: str = Field(default="none")
    confidence: str = Field(default="low")
    quality_flags: list[str] = Field(default_factory=list)

    @field_validator(
        "task_id",
        "task_scope",
        "candidate_id",
        "canonicalization_run_id",
        "canonicalization_contract_version",
        "prompt_version",
        "runtime_contour",
        "backend",
        "model_id",
        "status",
        "failure_reason",
        "canonical_question",
        "canonical_question_language",
        "legal_issue_frame",
        "legal_issue_frame_slug",
        "law_area",
        "desired_outcome",
        "exclusion_reason",
        "confidence",
        mode="before",
    )
    @classmethod
    def _string_value(cls, value: Any) -> str:
        return "" if value is None else str(value)

    @field_validator("facts", "authority_context", "hidden_issues", "quality_flags", mode="before")
    @classmethod
    def _string_list_value(cls, value: Any) -> list[str]:
        return _as_string_list(value)

    @field_validator("is_legal_answer_required", "is_standalone_question", mode="before")
    @classmethod
    def _bool_value(cls, value: Any) -> bool:
        return _bool_value(value)

    @field_validator("canonical_question")
    @classmethod
    def _redacted_question(cls, value: str) -> str:
        return _redact_private_text(value.strip())

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: str) -> str:
        if value not in CANONICALIZATION_STATUSES:
            raise ValueError(f"invalid_status:{value}")
        return value

    @field_validator("confidence")
    @classmethod
    def _valid_confidence(cls, value: str) -> str:
        if value not in CONFIDENCE_VALUES:
            raise ValueError(f"invalid_confidence:{value}")
        return value

    @field_validator("exclusion_reason")
    @classmethod
    def _valid_exclusion_reason(cls, value: str) -> str:
        if value not in EXCLUSION_REASONS:
            raise ValueError(f"invalid_exclusion_reason:{value}")
        return value

    @model_validator(mode="after")
    def _valid_completed_inclusion(self) -> "CanonicalizationResultPayload":
        if self.status == "completed" and self.exclusion_reason == "none":
            if not self.canonical_question:
                raise ValueError("missing_canonical_question")
            if not _slugify(self.legal_issue_frame_slug or self.legal_issue_frame):
                raise ValueError("missing_legal_issue_frame_slug")
            if not self.is_legal_answer_required:
                raise ValueError("included_record_requires_legal_answer")
            if not self.is_standalone_question:
                raise ValueError("included_record_requires_standalone_question")
        return self


class LegalIntentCandidatePayload(BaseModel):
    """Structured candidate interpretation of one canonical legal question."""

    model_config = ConfigDict(extra="ignore")

    legal_intent_candidate_id: str = Field(default="")
    candidate_id: str = Field(default="")
    canonicalization_evidence_id: str = Field(default="")
    source_canonical_question: str = Field(default="")
    source_legal_issue_frame: str = Field(default="")
    law_area: str = Field(default="")
    legal_domain: str = Field(default="")
    actor: str = Field(default="")
    subject: str = Field(default="")
    current_status: str = Field(default="")
    target_status: str = Field(default="")
    desired_action: str = Field(default="")
    legal_object: str = Field(default="")
    authority_context: list[str] = Field(default_factory=list)
    third_party_context: list[str] = Field(default_factory=list)
    location_scope: str = Field(default="")
    temporal_condition: str = Field(default="")
    operational_boundary: str = Field(default="")
    material_slots_unknown: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    evidence_refs: list[dict[str, str]] = Field(default_factory=list)
    validation_flags: list[str] = Field(default_factory=list)
    confidence: str = Field(default="low")
    review_status: str = Field(default="candidate")
    policy_version: str = Field(default=LEGAL_INTENT_CANDIDATE_POLICY_VERSION)

    @field_validator(
        "legal_intent_candidate_id",
        "candidate_id",
        "canonicalization_evidence_id",
        "source_canonical_question",
        "source_legal_issue_frame",
        "law_area",
        "legal_domain",
        "actor",
        "subject",
        "current_status",
        "target_status",
        "desired_action",
        "legal_object",
        "location_scope",
        "temporal_condition",
        "operational_boundary",
        "confidence",
        "review_status",
        "policy_version",
        mode="before",
    )
    @classmethod
    def _string_value(cls, value: Any) -> str:
        return "" if value is None else str(value)

    @field_validator(
        "authority_context",
        "third_party_context",
        "material_slots_unknown",
        "ambiguities",
        "validation_flags",
        mode="before",
    )
    @classmethod
    def _string_list_value(cls, value: Any) -> list[str]:
        return _as_string_list(value)

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def _evidence_refs_value(cls, value: Any) -> list[dict[str, str]]:
        refs: list[dict[str, str]] = []
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for item in value:
                if isinstance(item, Mapping):
                    refs.append({str(key): str(val) for key, val in item.items()})
        return refs

    @field_validator("source_canonical_question")
    @classmethod
    def _redacted_question(cls, value: str) -> str:
        return _redact_private_text(value.strip())

    @field_validator("confidence")
    @classmethod
    def _valid_confidence(cls, value: str) -> str:
        if value not in CONFIDENCE_VALUES:
            raise ValueError(f"invalid_confidence:{value}")
        return value

    @field_validator("review_status")
    @classmethod
    def _valid_review_status(cls, value: str) -> str:
        if value not in LEGAL_INTENT_REVIEW_STATUSES:
            raise ValueError(f"invalid_review_status:{value}")
        return value


class LegalIntentPairDecisionPayload(BaseModel):
    """Structured candidate judgment for one legal-intent pair."""

    model_config = ConfigDict(extra="ignore")

    pair_decision_id: str = Field(default="")
    pair_id: str = Field(default="")
    decision_source: str = Field(default="")
    pair_class: str = Field(default="uncertain")
    answer_equivalence: str = Field(default="uncertain")
    canonical_question_equivalence: str = Field(default="uncertain")
    allowed_downstream_actions: list[str] = Field(default_factory=list)
    material_differences: list[dict[str, str]] = Field(default_factory=list)
    shared_material_facts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    short_reason: str = Field(default="")
    confidence: str = Field(default="low")
    risk: str = Field(default="medium")
    validation_flags: list[str] = Field(default_factory=list)
    policy_version: str = Field(default=LEGAL_INTENT_PAIR_POLICY_VERSION)
    runtime_metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "pair_decision_id",
        "pair_id",
        "decision_source",
        "pair_class",
        "answer_equivalence",
        "canonical_question_equivalence",
        "short_reason",
        "confidence",
        "risk",
        "policy_version",
        mode="before",
    )
    @classmethod
    def _string_value(cls, value: Any) -> str:
        return "" if value is None else str(value)

    @field_validator(
        "allowed_downstream_actions",
        "shared_material_facts",
        "unknowns",
        "ambiguities",
        "validation_flags",
        mode="before",
    )
    @classmethod
    def _string_list_value(cls, value: Any) -> list[str]:
        return _as_string_list(value)

    @field_validator("material_differences", mode="before")
    @classmethod
    def _material_differences_value(cls, value: Any) -> list[dict[str, str]]:
        differences: list[dict[str, str]] = []
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for item in value:
                if isinstance(item, Mapping):
                    differences.append({str(key): str(val) for key, val in item.items()})
        return differences

    @field_validator("runtime_metadata", mode="before")
    @classmethod
    def _runtime_metadata_value(cls, value: Any) -> dict[str, str]:
        if not isinstance(value, Mapping):
            return {}
        return {str(key): str(val) for key, val in value.items()}

    @field_validator("pair_class")
    @classmethod
    def _valid_pair_class(cls, value: str) -> str:
        if value not in LEGAL_INTENT_PAIR_CLASSES:
            raise ValueError(f"invalid_pair_class:{value}")
        return value

    @field_validator("answer_equivalence")
    @classmethod
    def _valid_answer_equivalence(cls, value: str) -> str:
        if value not in LEGAL_INTENT_ANSWER_EQUIVALENCE_VALUES:
            raise ValueError(f"invalid_answer_equivalence:{value}")
        return value

    @field_validator("canonical_question_equivalence")
    @classmethod
    def _valid_question_equivalence(cls, value: str) -> str:
        if value not in LEGAL_INTENT_QUESTION_EQUIVALENCE_VALUES:
            raise ValueError(f"invalid_canonical_question_equivalence:{value}")
        return value

    @field_validator("allowed_downstream_actions")
    @classmethod
    def _valid_actions(cls, value: list[str]) -> list[str]:
        invalid = sorted({item for item in value if item not in LEGAL_INTENT_DOWNSTREAM_ACTIONS})
        if invalid:
            raise ValueError(f"invalid_allowed_downstream_actions:{','.join(invalid)}")
        return value

    @field_validator("confidence")
    @classmethod
    def _valid_confidence(cls, value: str) -> str:
        if value not in CONFIDENCE_VALUES:
            raise ValueError(f"invalid_confidence:{value}")
        return value

    @field_validator("risk")
    @classmethod
    def _valid_risk(cls, value: str) -> str:
        if value not in VERIFIER_RISK_LEVELS:
            raise ValueError(f"invalid_risk:{value}")
        return value


class VerifierVerdictPayload(BaseModel):
    """Compact verifier schema for MiniMax/DeepSeek adjudication output."""

    model_config = ConfigDict(extra="forbid")

    verdict: str = Field(default="uncertain")
    confidence: int = Field(default=0, ge=0, le=100)
    risk: str = Field(default="medium")
    bad_fields: list[str] = Field(default_factory=list)
    short_reason: str = Field(default="")
    suggested_action: str = Field(default="human_review")

    @field_validator("verdict", mode="before")
    @classmethod
    def _valid_verdict(cls, value: Any) -> str:
        value = _strip_matching_quotes(value or "uncertain")
        if value not in VERIFIER_VERDICTS:
            raise ValueError(f"invalid_verdict:{value}")
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def _valid_confidence(cls, value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = _strip_matching_quotes(value).lower()
        if not text:
            return 0
        confidence_aliases = {
            "low": 35,
            "medium": 65,
            "high": 90,
        }
        if text in confidence_aliases:
            return confidence_aliases[text]
        return int(text)

    @field_validator("risk", mode="before")
    @classmethod
    def _valid_risk(cls, value: Any) -> str:
        value = _strip_matching_quotes(value or "medium")
        if value not in VERIFIER_RISK_LEVELS:
            raise ValueError(f"invalid_risk:{value}")
        return value

    @field_validator("suggested_action", mode="before")
    @classmethod
    def _valid_suggested_action(cls, value: Any) -> str:
        value = _strip_matching_quotes(value or "human_review")
        if value not in VERIFIER_SUGGESTED_ACTIONS:
            raise ValueError(f"invalid_suggested_action:{value}")
        return value

    @field_validator("bad_fields", mode="before")
    @classmethod
    def _string_list_value(cls, value: Any) -> list[str]:
        return _as_string_list(value)

    @field_validator("short_reason", mode="before")
    @classmethod
    def _string_value(cls, value: Any) -> str:
        return "" if value is None else str(value)

    @model_validator(mode="after")
    def _reason_required_for_non_pass(self) -> "VerifierVerdictPayload":
        if self.verdict in {"fail", "uncertain"} and not self.short_reason.strip():
            raise ValueError("missing_short_reason_for_non_pass_verdict")
        return self


class AdjudicationPayload(BaseModel):
    """Compact generic adjudication schema for escalated canonicalization records."""

    model_config = ConfigDict(extra="forbid")

    verdict: str = Field(default="uncertain")
    confidence: int = Field(default=0, ge=0, le=100)
    risk: str = Field(default="medium")
    bad_fields: list[str] = Field(default_factory=list)
    short_reason: str = Field(default="")
    final_recommendation: str = Field(default="human_review")

    @field_validator("verdict", mode="before")
    @classmethod
    def _valid_verdict(cls, value: Any) -> str:
        value = _strip_matching_quotes(value or "uncertain")
        if value not in VERIFIER_VERDICTS:
            raise ValueError(f"invalid_verdict:{value}")
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def _valid_confidence(cls, value: Any) -> int:
        return VerifierVerdictPayload._valid_confidence(value)

    @field_validator("risk", mode="before")
    @classmethod
    def _valid_risk(cls, value: Any) -> str:
        value = _strip_matching_quotes(value or "medium")
        if value not in VERIFIER_RISK_LEVELS:
            raise ValueError(f"invalid_risk:{value}")
        return value

    @field_validator("final_recommendation", mode="before")
    @classmethod
    def _valid_final_recommendation(cls, value: Any) -> str:
        value = _strip_matching_quotes(value or "human_review")
        aliases = {
            "retry_qwen": "retry_generator",
        }
        value = aliases.get(value, value)
        if value not in ADJUDICATION_FINAL_RECOMMENDATIONS:
            raise ValueError(f"invalid_final_recommendation:{value}")
        return value

    @field_validator("bad_fields", mode="before")
    @classmethod
    def _string_list_value(cls, value: Any) -> list[str]:
        return _as_string_list(value)

    @field_validator("short_reason", mode="before")
    @classmethod
    def _string_value(cls, value: Any) -> str:
        return "" if value is None else str(value)

    selected_candidate_key: str = Field(default="")

    @model_validator(mode="after")
    def _verdict_recommendation_consistency(self) -> "AdjudicationPayload":
        if self.verdict == "pass" and self.final_recommendation == "reject":
            raise ValueError("inconsistent_verdict_final_recommendation")
        if self.verdict == "fail" and self.final_recommendation == "accept":
            raise ValueError("inconsistent_verdict_final_recommendation")
        return self


DeepSeekAdjudicationPayload = AdjudicationPayload


class AtomicSourceSpanPayload(BaseModel):
    """Exact source span offered as support for one atomic claim."""

    model_config = ConfigDict(extra="forbid")

    start: int = Field(ge=0)
    end: int = Field(ge=0)
    quote: str = Field(default="")

    @field_validator("quote", mode="before")
    @classmethod
    def _string_value(cls, value: Any) -> str:
        return "" if value is None else str(value)

    @model_validator(mode="after")
    def _valid_offsets(self) -> "AtomicSourceSpanPayload":
        if self.end <= self.start:
            raise ValueError("source_span_end_must_exceed_start")
        if not self.quote:
            raise ValueError("source_span_quote_required")
        return self


class AtomicClaimVerdictPayload(BaseModel):
    """Independent source-grounding verdict for one deterministic field claim."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(default="")
    support: Literal["explicit", "necessary_inference", "unsupported", "unresolved"] = Field(
        default="unresolved"
    )
    relation_kind: Literal[
        "source_fact",
        "requested_outcome",
        "canonical_issue",
        "routing",
        "authority_context",
        "hidden_issue",
        "causal_dependency",
        "eligibility_condition",
        "legal_mechanism",
        "program_specificity",
        "quality_flag",
        "other",
    ] = Field(default="other")
    materiality: Literal["low", "medium", "high"] = Field(default="medium")
    source_spans: list[AtomicSourceSpanPayload] = Field(default_factory=list)
    correction: str = Field(default="")
    short_reason: str = Field(default="")

    @field_validator("claim_id", "correction", "short_reason", mode="before")
    @classmethod
    def _string_value(cls, value: Any) -> str:
        return "" if value is None else str(value)

    @field_validator("support", mode="before")
    @classmethod
    def _valid_support(cls, value: Any) -> str:
        normalized = _strip_matching_quotes(value or "unresolved")
        if normalized not in ATOMIC_CLAIM_SUPPORT_VALUES:
            raise ValueError(f"invalid_atomic_claim_support:{normalized}")
        return normalized

    @field_validator("relation_kind", mode="before")
    @classmethod
    def _valid_relation_kind(cls, value: Any) -> str:
        normalized = _strip_matching_quotes(value or "other")
        if normalized not in ATOMIC_CLAIM_RELATION_KINDS:
            raise ValueError(f"invalid_atomic_relation_kind:{normalized}")
        return normalized

    @field_validator("materiality", mode="before")
    @classmethod
    def _valid_materiality(cls, value: Any) -> str:
        normalized = _strip_matching_quotes(value or "medium")
        if normalized not in ATOMIC_CLAIM_MATERIALITY_VALUES:
            raise ValueError(f"invalid_atomic_materiality:{normalized}")
        return normalized

    @model_validator(mode="after")
    def _reason_for_nonpass(self) -> "AtomicClaimVerdictPayload":
        if self.support in {"unsupported", "unresolved"} and not self.short_reason.strip():
            raise ValueError("atomic_nonpass_claim_requires_reason")
        return self


class AtomicVerificationPayload(BaseModel):
    """Bounded verifier output for all deterministic claims in one candidate."""

    model_config = ConfigDict(extra="forbid")

    route: Literal["pass", "revise", "hold"] = Field(default="hold")
    claim_verdicts: list[AtomicClaimVerdictPayload] = Field(default_factory=list)
    short_reason: str = Field(default="")

    @field_validator("route", mode="before")
    @classmethod
    def _valid_route(cls, value: Any) -> str:
        normalized = _strip_matching_quotes(value or "hold")
        if normalized not in ATOMIC_VERIFICATION_ROUTES:
            raise ValueError(f"invalid_atomic_verification_route:{normalized}")
        return normalized

    @field_validator("short_reason", mode="before")
    @classmethod
    def _string_value(cls, value: Any) -> str:
        return "" if value is None else str(value)


class AtomicFormatterClaimVerdictPayload(BaseModel):
    """Offset-free claim verdict emitted by a no-reasoning formatter."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(default="")
    support: Literal["explicit", "necessary_inference", "unsupported", "unresolved"] = Field(
        default="unresolved"
    )
    relation_kind: Literal[
        "source_fact",
        "requested_outcome",
        "canonical_issue",
        "routing",
        "authority_context",
        "hidden_issue",
        "causal_dependency",
        "eligibility_condition",
        "legal_mechanism",
        "program_specificity",
        "quality_flag",
        "other",
    ] = Field(default="other")
    materiality: Literal["low", "medium", "high"] = Field(default="medium")
    source_quotes: list[str] = Field(default_factory=list)
    correction: str = Field(default="")
    short_reason: str = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def _legacy_source_spans_to_quotes(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        if "source_quotes" in payload or "source_spans" not in payload:
            return payload
        spans = payload.pop("source_spans")
        if isinstance(spans, Sequence) and not isinstance(spans, (str, bytes)):
            payload["source_quotes"] = [
                str(span.get("quote", ""))
                for span in spans
                if isinstance(span, Mapping) and str(span.get("quote", ""))
            ]
        else:
            payload["source_quotes"] = []
        return payload

    @field_validator("claim_id", "correction", "short_reason", mode="before")
    @classmethod
    def _string_value(cls, value: Any) -> str:
        return "" if value is None else str(value)

    @field_validator("source_quotes", mode="before")
    @classmethod
    def _source_quote_list(cls, value: Any) -> list[str]:
        return _as_string_list(value)

    @field_validator("support", mode="before")
    @classmethod
    def _valid_support(cls, value: Any) -> str:
        normalized = _strip_matching_quotes(value or "unresolved")
        if normalized not in ATOMIC_CLAIM_SUPPORT_VALUES:
            raise ValueError(f"invalid_atomic_claim_support:{normalized}")
        return normalized

    @field_validator("relation_kind", mode="before")
    @classmethod
    def _valid_relation_kind(cls, value: Any) -> str:
        normalized = _strip_matching_quotes(value or "other")
        if normalized not in ATOMIC_CLAIM_RELATION_KINDS:
            raise ValueError(f"invalid_atomic_relation_kind:{normalized}")
        return normalized

    @field_validator("materiality", mode="before")
    @classmethod
    def _valid_materiality(cls, value: Any) -> str:
        normalized = _strip_matching_quotes(value or "medium")
        if normalized not in ATOMIC_CLAIM_MATERIALITY_VALUES:
            raise ValueError(f"invalid_atomic_materiality:{normalized}")
        return normalized

    @model_validator(mode="after")
    def _reason_for_nonpass(self) -> "AtomicFormatterClaimVerdictPayload":
        if self.support in {"unsupported", "unresolved"} and not self.short_reason.strip():
            raise ValueError("atomic_nonpass_claim_requires_reason")
        return self


class AtomicFormatterVerificationPayload(BaseModel):
    """Strict formatter schema with quotes but no model-generated offsets."""

    model_config = ConfigDict(extra="forbid")

    route: Literal["pass", "revise", "hold"] = Field(default="hold")
    claim_verdicts: list[AtomicFormatterClaimVerdictPayload] = Field(default_factory=list)
    short_reason: str = Field(default="")

    @field_validator("route", mode="before")
    @classmethod
    def _valid_route(cls, value: Any) -> str:
        normalized = _strip_matching_quotes(value or "hold")
        if normalized not in ATOMIC_VERIFICATION_ROUTES:
            raise ValueError(f"invalid_atomic_verification_route:{normalized}")
        return normalized

    @field_validator("short_reason", mode="before")
    @classmethod
    def _string_value(cls, value: Any) -> str:
        return "" if value is None else str(value)


class AtomicRepairPayload(BaseModel):
    """One bounded repair proposal; metadata is overwritten by the controller."""

    model_config = ConfigDict(extra="forbid")

    repaired_claim_ids: list[str] = Field(default_factory=list)
    corrected_output: CanonicalizationResultPayload

    @field_validator("repaired_claim_ids", mode="before")
    @classmethod
    def _string_list_value(cls, value: Any) -> list[str]:
        return _as_string_list(value)


def emit_tg_qa_canonicalization_batch(
    *,
    candidates_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    filter_mode: str = "all",
    max_candidates: int = 0,
    candidate_offset: int = 0,
) -> dict[str, Any]:
    """Emit review-only canonicalization tasks from redacted 006 candidates."""

    if filter_mode not in CANONICALIZATION_FILTER_MODES:
        raise ValueError(f"filter_mode must be one of {', '.join(CANONICALIZATION_FILTER_MODES)}")
    candidates = [item for item in _read_jsonl(candidates_path) if _candidate_matches_filter(item, filter_mode)]
    offset = max(candidate_offset, 0)
    selected = candidates[offset:]
    if max_candidates > 0:
        selected = selected[:max_candidates]

    records = [_canonicalization_batch_item(candidate, candidates_path=candidates_path) for candidate in selected]
    batch_identity = _bind_canonicalization_batch_identity(records)
    _ensure_public_payload(records)
    _write_jsonl(output_path, records)
    summary = {
        "artifact_type": "tg_qa_canonicalization_batch_summary",
        "generated_at": _utc_timestamp(),
        "canonicalization_contract_version": CANONICALIZATION_CONTRACT_VERSION,
        "canonicalization_identity_policy_version": CANONICALIZATION_IDENTITY_POLICY_VERSION,
        **batch_identity,
        "prompt_version": CANONICALIZATION_PROMPT_VERSION,
        "prompt_profile_hash": _canonicalization_prompt_profile_hash(CANONICALIZATION_PROMPT_VERSION),
        "prompt_example_set_id": CANONICALIZATION_PROMPT_EXAMPLE_SET_ID,
        "prompt_example_count": len(CANONICALIZATION_PROMPT_EXAMPLES),
        "input_candidates_path": str(candidates_path),
        "output_path": str(output_path),
        "filter_mode": filter_mode,
        "candidate_offset": offset,
        "max_candidates": max_candidates,
        "available_candidate_count": len(candidates),
        "emitted_task_count": len(records),
        "counts_by_answer_candidate_status": _counts(
            str(record["input"].get("answer_candidate_status", "")) for record in records
        ),
        "counts_by_law_area_hint": _counts(
            label
            for record in records
            for label in _as_string_list(record["input"].get("topic_labels", []))
        ),
        "trust_boundary": "canonicalization_tasks_are_review_evidence_only",
    }
    _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def sample_tg_qa_canonicalization_batch(
    *,
    batch_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    sample_size: int = 50,
    sampling_policy: str = "balanced",
    sample_seed: str = "",
) -> dict[str, Any]:
    """Select a deterministic calibration or qualification slice."""

    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    if sampling_policy not in CANONICALIZATION_SAMPLE_POLICIES:
        raise ValueError(
            "sampling_policy must be one of "
            + ", ".join(CANONICALIZATION_SAMPLE_POLICIES)
        )
    normalized_seed = sample_seed.strip()
    if sampling_policy == "stable_hash" and not normalized_seed:
        raise ValueError("sample_seed is required for stable_hash sampling")
    batch_items = _read_jsonl(batch_path)
    _batch_identities, batch_identity = _canonicalization_batch_identity_index(batch_items)
    if sampling_policy == "stable_hash":
        selected = sorted(
            batch_items,
            key=lambda record: (
                sha256(
                    f"{normalized_seed}\0{record.get('task_id', '')}".encode("utf-8")
                ).hexdigest(),
                str(record.get("task_id", "")),
            ),
        )[:sample_size]
        sampling_policy_description = "deterministic_sha256_order_over_seed_and_task_id"
    else:
        buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for item in batch_items:
            source_input = item.get("input", {}) if isinstance(item.get("input"), Mapping) else {}
            status = str(source_input.get("answer_candidate_status", "")) or "unknown_status"
            labels = _as_string_list(source_input.get("topic_labels", []))
            topic = labels[0] if labels else "unknown_topic"
            buckets[(status, topic)].append(item)
        for records in buckets.values():
            records.sort(key=lambda record: str(record.get("task_id", "")))

        selected = []
        seen_task_ids: set[str] = set()
        bucket_keys = sorted(buckets)
        while len(selected) < sample_size and bucket_keys:
            progressed = False
            for key in list(bucket_keys):
                records = buckets[key]
                while records and str(records[0].get("task_id", "")) in seen_task_ids:
                    records.pop(0)
                if not records:
                    bucket_keys.remove(key)
                    continue
                record = records.pop(0)
                selected.append(record)
                seen_task_ids.add(str(record.get("task_id", "")))
                progressed = True
                if len(selected) >= sample_size:
                    break
            if not progressed:
                break
        sampling_policy_description = (
            "deterministic_round_robin_by_answer_status_and_first_topic_label"
        )

    sample_identity = _bind_canonicalization_batch_identity(selected)
    _ensure_public_payload(selected)
    _write_jsonl(output_path, selected)
    summary = {
        "artifact_type": "tg_qa_canonicalization_calibration_sample_summary",
        "generated_at": _utc_timestamp(),
        "source_batch_path": str(batch_path),
        "output_path": str(output_path),
        "canonicalization_identity_policy_version": CANONICALIZATION_IDENTITY_POLICY_VERSION,
        "source_canonicalization_batch_id": batch_identity["canonicalization_batch_id"],
        "source_canonicalization_batch_hash": batch_identity[
            "canonicalization_batch_hash"
        ],
        **sample_identity,
        "requested_sample_size": sample_size,
        "available_batch_item_count": len(batch_items),
        "emitted_sample_count": len(selected),
        "sampling_policy_id": sampling_policy,
        "sampling_policy": sampling_policy_description,
        "sample_seed": normalized_seed if sampling_policy == "stable_hash" else "",
        "selected_task_id_hash": _stable_json_hash(
            [str(item.get("task_id", "")) for item in selected]
        ),
        "counts_by_answer_candidate_status": _counts(
            str(item.get("input", {}).get("answer_candidate_status", ""))
            for item in selected
            if isinstance(item.get("input"), Mapping)
        ),
        "counts_by_law_area_hint": _counts(
            label
            for item in selected
            if isinstance(item.get("input"), Mapping)
            for label in _as_string_list(item.get("input", {}).get("topic_labels", []))
        ),
    }
    _write_json(summary_output_path, summary)
    return {"records": selected, "summary": summary}


def build_tg_qa_operator_provider_failure_retry_batch(
    *,
    batch_path: str | Path,
    results_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    batch_id_field: str = "task_id",
    result_id_field: str = "task_id",
    include_unprocessed: bool = False,
    max_items: int = 0,
) -> dict[str, Any]:
    """Build a retry batch from exhausted provider/transport failures only."""

    if max_items < 0:
        raise ValueError("max_items must be non-negative")
    if not batch_id_field:
        raise ValueError("batch_id_field is required")
    if not result_id_field:
        raise ValueError("result_id_field is required")

    batch_items = _read_jsonl(batch_path)
    results = _read_jsonl(results_path)
    batch_by_id: dict[str, dict[str, Any]] = {}
    batch_order: list[str] = []
    missing_batch_id_count = 0
    duplicate_batch_id_count = 0
    for item in batch_items:
        item_id = str(item.get(batch_id_field, ""))
        if not item_id:
            missing_batch_id_count += 1
            continue
        if item_id in batch_by_id:
            duplicate_batch_id_count += 1
            continue
        batch_by_id[item_id] = item
        batch_order.append(item_id)

    provider_failure_keys: Counter[str] = Counter()
    provider_failed_ids: set[str] = set()
    result_processed_ids: set[str] = set()
    failed_result_count = 0
    provider_failed_result_count = 0
    non_provider_failed_result_count = 0
    provider_failure_missing_id_count = 0
    for result in results:
        result_id = str(result.get(result_id_field, ""))
        if result_id:
            result_processed_ids.add(result_id)
        if str(result.get("status", "")) != "failed":
            continue
        failed_result_count += 1
        provider_failure_key = _operator_provider_failure_guard_key(result)
        if not provider_failure_key:
            non_provider_failed_result_count += 1
            continue
        provider_failed_result_count += 1
        provider_failure_keys[provider_failure_key] += 1
        if not result_id:
            provider_failure_missing_id_count += 1
            continue
        provider_failed_ids.add(result_id)

    missing_batch_item_for_provider_failure_count = len(provider_failed_ids - set(batch_by_id))
    unprocessed_ids = [item_id for item_id in batch_order if item_id not in result_processed_ids]
    retry_ids: list[str] = []
    for item_id in batch_order:
        if item_id in provider_failed_ids:
            retry_ids.append(item_id)
    if include_unprocessed:
        selected_ids = set(retry_ids)
        retry_ids.extend(item_id for item_id in unprocessed_ids if item_id not in selected_ids)
    if max_items > 0:
        retry_ids = retry_ids[:max_items]

    retry_items = [batch_by_id[item_id] for item_id in retry_ids if item_id in batch_by_id]
    output = _write_jsonl(output_path, retry_items)
    summary = {
        "artifact_type": "tg_qa_operator_provider_failure_retry_batch_summary",
        "generated_at": _utc_timestamp(),
        "batch_path": str(batch_path),
        "results_path": str(results_path),
        "output_path": str(output),
        "summary_output_path": str(summary_output_path),
        "batch_id_field": batch_id_field,
        "result_id_field": result_id_field,
        "include_unprocessed": include_unprocessed,
        "max_items": max_items,
        "batch_item_count": len(batch_items),
        "result_count": len(results),
        "failed_result_count": failed_result_count,
        "provider_failed_result_count": provider_failed_result_count,
        "provider_failed_unique_id_count": len(provider_failed_ids),
        "non_provider_failed_result_count": non_provider_failed_result_count,
        "provider_failure_missing_id_count": provider_failure_missing_id_count,
        "missing_batch_id_count": missing_batch_id_count,
        "duplicate_batch_id_count": duplicate_batch_id_count,
        "missing_batch_item_for_provider_failure_count": missing_batch_item_for_provider_failure_count,
        "unprocessed_batch_item_count": len(unprocessed_ids),
        "selected_retry_item_count": len(retry_items),
        "provider_failure_keys": dict(sorted(provider_failure_keys.items())),
    }
    _write_json(summary_output_path, summary)
    return {"output_path": output, "summary_output_path": Path(summary_output_path), "summary": summary}


def export_tg_qa_canonicalization_review_cards(
    *,
    batch_path: str | Path,
    html_output_path: str | Path,
    summary_output_path: str | Path,
    qwen_results_path: str | Path | None = None,
    verifier_results_path: str | Path | None = None,
    max_cards: int = 0,
) -> dict[str, Any]:
    """Create a dependency-light local HTML review surface for calibration triage."""

    batch_items = _read_jsonl(batch_path)
    if max_cards > 0:
        batch_items = batch_items[:max_cards]
    qwen_by_task = _records_by_task_id(_read_jsonl(qwen_results_path) if qwen_results_path else [])
    verifier_by_task = _records_by_task_id(_read_jsonl(verifier_results_path) if verifier_results_path else [])
    cards = [
        _review_card_record(
            item,
            qwen_result=qwen_by_task.get(str(item.get("task_id", ""))),
            verifier_result=verifier_by_task.get(str(item.get("task_id", ""))),
        )
        for item in batch_items
    ]
    _ensure_public_payload(cards)
    html_stem = Path(html_output_path).stem
    download_name = f"{html_stem}_decisions.jsonl"
    storage_key = f"tg007ReviewDecisions:{html_stem}"
    _write_text(
        html_output_path,
        _review_cards_html(cards, download_name=download_name, storage_key=storage_key),
    )
    summary = {
        "artifact_type": "tg_qa_canonicalization_review_cards_summary",
        "generated_at": _utc_timestamp(),
        "batch_path": str(batch_path),
        "qwen_results_path": str(qwen_results_path or ""),
        "verifier_results_path": str(verifier_results_path or ""),
        "html_output_path": str(html_output_path),
        "card_count": len(cards),
        "counts_by_answer_candidate_status": _counts(
            str(card.get("input", {}).get("answer_candidate_status", "")) for card in cards
        ),
        "review_ui_mode": "static_html_with_client_side_jsonl_export",
    }
    _write_json(summary_output_path, summary)
    return {"cards": cards, "summary": summary}


def import_tg_qa_canonicalization_review_decisions(
    *,
    batch_path: str | Path,
    qwen_results_path: str | Path,
    decisions_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    verifier_results_path: str | Path | None = None,
) -> dict[str, Any]:
    """Import partial human decisions from the canonicalization review UI."""

    batch_items = _read_jsonl(batch_path)
    qwen_results = _read_jsonl(qwen_results_path)
    verifier_results = _read_jsonl(verifier_results_path) if verifier_results_path else []
    tasks_by_id = {str(item.get("task_id", "")): item for item in batch_items}
    qwen_by_task = _records_by_task_id(qwen_results)
    verifier_by_task = _records_by_task_id(verifier_results)
    raw_decisions = _read_decision_records(decisions_path)
    seen_task_ids: set[str] = set()
    records: list[dict[str, Any]] = []
    counts = Counter()

    for raw in raw_decisions:
        record = _canonicalization_review_decision_record(
            raw,
            tasks_by_id=tasks_by_id,
            qwen_by_task=qwen_by_task,
            verifier_by_task=verifier_by_task,
        )
        task_id = str(record.get("task_id", ""))
        if task_id and task_id in seen_task_ids and record.get("status") != "failed":
            record["status"] = "failed"
            record["failure_reason"] = "duplicate_decision_for_task"
        if task_id:
            seen_task_ids.add(task_id)
        if record.get("status") == "failed":
            counts["failed"] += 1
        else:
            counts[str(record.get("decision", ""))] += 1
        records.append(record)

    _ensure_public_payload(records)
    _write_jsonl(output_path, records)
    summary = {
        "artifact_type": "tg_qa_canonicalization_review_decisions_summary",
        "generated_at": _utc_timestamp(),
        "batch_path": str(batch_path),
        "qwen_results_path": str(qwen_results_path),
        "verifier_results_path": str(verifier_results_path or ""),
        "source_decisions_path": str(decisions_path),
        "output_path": str(output_path),
        "processed_decision_count": len(raw_decisions),
        "imported_count": len(records),
        "failed_count": counts.get("failed", 0),
        "counts_by_decision": dict(sorted((k, v) for k, v in counts.items() if k != "failed")),
        "counts_by_review_evidence_binding_status": _counts(
            str(record.get("review_evidence_binding_status", "")) for record in records
        ),
        "decision_policy": "partial_review_decisions_are_routed_by_tg_question_canonicalization_routing_v2",
    }
    _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def build_tg_qa_canonicalization_routing(
    *,
    batch_path: str | Path,
    qwen_results_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    review_decisions_path: str | Path | None = None,
    verifier_results_path: str | Path | None = None,
    decision_ledger_output_path: str | Path | None = None,
    retry_qwen_batch_output_path: str | Path | None = None,
    send_deepseek_batch_output_path: str | Path | None = None,
    backlog_output_path: str | Path | None = None,
    unreviewed_policy: str = "hold",
    allow_legacy_identity: bool = False,
) -> dict[str, Any]:
    """Reconcile every task before routing review-gated canonicalization evidence."""

    if unreviewed_policy not in UNREVIEWED_POLICIES:
        raise ValueError(f"unreviewed_policy must be one of {', '.join(UNREVIEWED_POLICIES)}")

    batch_items = _read_jsonl(batch_path)
    expected_task_identities, batch_identity = _canonicalization_batch_identity_index(
        batch_items,
        allow_legacy_identity=allow_legacy_identity,
    )
    qwen_results = _read_jsonl(qwen_results_path)
    verifier_results = _read_jsonl(verifier_results_path) if verifier_results_path else []
    decision_records = [
        item
        for item in (_read_jsonl(review_decisions_path) if review_decisions_path else [])
        if str(item.get("status", "")) != "failed"
    ]
    batch_by_task = {str(item.get("task_id", "")): item for item in batch_items}
    qwen_by_task, qwen_without_task_id = _records_grouped_by_task_id(qwen_results)
    verifier_by_task, verifier_without_task_id = _records_grouped_by_task_id(verifier_results)
    decisions_by_task, decisions_without_task_id = _records_grouped_by_task_id(decision_records)

    accepted_results: list[dict[str, Any]] = []
    decision_ledger: list[dict[str, Any]] = []
    retry_qwen_batch: list[dict[str, Any]] = []
    send_deepseek_batch: list[dict[str, Any]] = []
    backlog: list[dict[str, Any]] = []
    counts = Counter()
    reconciliation_counts = Counter()

    def append_route(
        *,
        task_id: str,
        source_task: Mapping[str, Any],
        decision: str,
        decision_source: str,
        failure_reason: str = "",
        decision_record: Mapping[str, Any] | None = None,
        qwen_payload: Mapping[str, Any] | None = None,
        verifier_payload: Mapping[str, Any] | None = None,
        manual_failure_reason: str = "",
        manual_present: bool = False,
    ) -> dict[str, Any]:
        review = dict(decision_record or {})
        qwen = dict(qwen_payload or {})
        verifier = dict(verifier_payload or {})
        ledger_record = {
            "canonicalization_route_id": _stable_id(
                "tg-canonicalization-route",
                task_id,
                decision,
                review,
                failure_reason,
            ),
            "task_id": task_id,
            "candidate_id": str(source_task.get("candidate_id", "")) or str(qwen.get("candidate_id", "")),
            "decision": decision,
            "decision_source": decision_source,
            "decision_reason": str(review.get("decision_reason", "")),
            "reviewer_hash": str(review.get("reviewer_hash", "")),
            "reviewed_at": str(review.get("reviewed_at", "")),
            "review_decision_id": str(review.get("canonicalization_review_decision_id", "")),
            "review_payload_version": str(review.get("review_payload_version", "")),
            "review_payload_hash": str(review.get("review_payload_hash", "")),
            "review_evidence_binding_status": str(
                review.get("review_evidence_binding_status", "")
            ),
            "qwen_status": str(qwen.get("status", "")),
            "qwen_exclusion_reason": str(qwen.get("exclusion_reason", "")),
            "qwen_confidence": str(qwen.get("confidence", "")),
            "qwen_canonicalization_evidence_hash": str(qwen.get("canonicalization_evidence_hash", "")),
            "verifier_verdict": str(verifier.get("verdict", "")),
            "verifier_suggested_action": str(verifier.get("suggested_action", "")),
            "verifier_risk": str(verifier.get("risk", "")),
            "verifier_prompt_version": str(verifier.get("verifier_prompt_version", "")),
            "verifier_prompt_profile_hash": str(verifier.get("verifier_prompt_profile_hash", "")),
            "manual_canonicalization_status": (
                "invalid" if manual_failure_reason else ("present" if manual_present else "")
            ),
            "manual_canonicalization_failure_reason": manual_failure_reason,
            "canonicalization_batch_id": batch_identity["canonicalization_batch_id"],
            "canonicalization_batch_hash": batch_identity["canonicalization_batch_hash"],
            "routing_policy_version": CANONICALIZATION_ROUTING_POLICY_VERSION,
            "status": "failed" if failure_reason else "completed",
            "failure_reason": failure_reason,
        }
        decision_ledger.append(ledger_record)
        counts[decision] += 1
        if failure_reason:
            reconciliation_counts[failure_reason] += 1
        return ledger_record

    for source_task in batch_items:
        task_id = str(source_task.get("task_id", ""))
        qwen_group = qwen_by_task.get(task_id, [])
        decision_group = decisions_by_task.get(task_id, [])
        verifier_group = verifier_by_task.get(task_id, [])
        if len(qwen_group) != 1:
            reason = "missing_qwen_result_for_batch_task" if not qwen_group else "duplicate_qwen_results_for_batch_task"
            ledger_record = append_route(
                task_id=task_id,
                source_task=source_task,
                decision="hold",
                decision_source=reason,
                failure_reason=reason,
            )
            backlog.append(
                {
                    "task_id": task_id,
                    "candidate_id": ledger_record["candidate_id"],
                    "decision": "hold",
                    "decision_source": reason,
                    "failure_reason": reason,
                    "source_question_text_redacted": str(source_task.get("input", {}).get("question_text_redacted", "")),
                }
            )
            continue

        raw_qwen_payload = _extract_result_payload(qwen_group[0])
        qwen_payload, qwen_failure_reason = _validate_canonicalization_result(
            raw_qwen_payload,
            batch_by_task,
            default_run_id="",
            expected_task_identities=expected_task_identities,
            strict_identity=not allow_legacy_identity,
        )
        if qwen_failure_reason:
            qwen_payload = _failed_canonicalization_evidence(
                task_id=task_id,
                canonicalization_run_id=str(raw_qwen_payload.get("canonicalization_run_id", "")),
                failure_reason=qwen_failure_reason,
                source_task=source_task,
                raw_payload=raw_qwen_payload,
            )

        verifier_payload: dict[str, Any] = {}
        verifier_failure_reason = ""
        if verifier_results_path:
            if len(verifier_group) != 1:
                verifier_failure_reason = (
                    "missing_verifier_result_for_batch_task"
                    if not verifier_group
                    else "duplicate_verifier_results_for_batch_task"
                )
            else:
                verifier_payload = _extract_result_payload(verifier_group[0])
                verifier_evidence_hash = str(verifier_payload.get("canonicalization_evidence_hash", ""))
                qwen_evidence_hash = str(qwen_payload.get("canonicalization_evidence_hash", ""))
                if verifier_evidence_hash and qwen_evidence_hash and verifier_evidence_hash != qwen_evidence_hash:
                    verifier_failure_reason = "verifier_evidence_identity_mismatch"
                elif not verifier_evidence_hash and not allow_legacy_identity:
                    verifier_failure_reason = "verifier_missing_canonicalization_evidence_hash"

        decision: Mapping[str, Any] | None = None
        decision_failure_reason = ""
        if len(decision_group) > 1:
            decision_failure_reason = "duplicate_review_decisions_for_batch_task"
        elif decision_group:
            decision = decision_group[0]

        manual_payload, manual_failure_reason = _manual_canonicalization_payload_from_decision(
            decision,
            source_task=source_task,
        )
        manual_evidence: dict[str, Any] = {}
        if manual_payload and not manual_failure_reason:
            manual_evidence, manual_failure_reason = _validate_canonicalization_result(
                manual_payload,
                batch_by_task,
                default_run_id="",
                expected_task_identities=expected_task_identities,
                strict_identity=True,
            )

        effective_decision = _effective_canonicalization_decision(
            qwen_payload,
            decision,
            unreviewed_policy=unreviewed_policy,
        )
        decision_source = _effective_canonicalization_decision_source(
            qwen_payload,
            decision,
            unreviewed_policy=unreviewed_policy,
        )
        route_failure_reason = decision_failure_reason or verifier_failure_reason
        if qwen_failure_reason and not manual_evidence:
            effective_decision = "hold"
            decision_source = "invalid_qwen_result"
            route_failure_reason = qwen_failure_reason
        if decision_failure_reason:
            effective_decision = "hold"
            decision_source = decision_failure_reason

        ledger_record = append_route(
            task_id=task_id,
            source_task=source_task,
            decision=effective_decision,
            decision_source=decision_source,
            failure_reason=route_failure_reason,
            decision_record=decision,
            qwen_payload=qwen_payload,
            verifier_payload=verifier_payload,
            manual_failure_reason=manual_failure_reason,
            manual_present=bool(manual_evidence),
        )

        accepted_payload: dict[str, Any] = {}
        if effective_decision == "accept":
            if manual_evidence:
                accepted_payload = dict(manual_evidence)
            elif not qwen_failure_reason and str(qwen_payload.get("status", "")) == "completed":
                accepted_payload = dict(qwen_payload)
        if accepted_payload:
            accepted_payload["review_provenance"] = {
                "decision": "accept",
                "decision_source": decision_source,
                "review_status": "reviewed" if decision_source == "human_review" else "unreviewed_first_pass",
                "canonicalization_review_decision_id": ledger_record["review_decision_id"],
                "reviewer_hash": ledger_record["reviewer_hash"],
                "reviewed_at": ledger_record["reviewed_at"],
                "review_payload_version": ledger_record["review_payload_version"],
                "review_payload_hash": ledger_record["review_payload_hash"],
                "review_evidence_binding_status": ledger_record[
                    "review_evidence_binding_status"
                ],
                "decision_policy_version": str((decision or {}).get("decision_policy_version", "")),
                "routing_policy_version": CANONICALIZATION_ROUTING_POLICY_VERSION,
                "verifier": {
                    "verdict": str(verifier_payload.get("verdict", "")),
                    "suggested_action": str(verifier_payload.get("suggested_action", "")),
                    "risk": str(verifier_payload.get("risk", "")),
                    "canonicalization_evidence_hash": str(
                        verifier_payload.get("canonicalization_evidence_hash", "")
                    ),
                    "prompt_version": str(verifier_payload.get("verifier_prompt_version", "")),
                    "prompt_profile_hash": str(verifier_payload.get("verifier_prompt_profile_hash", "")),
                    "runtime_profile_hash": str(verifier_payload.get("runtime_profile_hash", "")),
                },
                "adjudication": dict(accepted_payload.get("adjudication_provenance", {}))
                if isinstance(accepted_payload.get("adjudication_provenance"), Mapping)
                else {},
            }
            accepted_results.append(accepted_payload)
            continue

        backlog.append(
            {
                "task_id": task_id,
                "candidate_id": ledger_record["candidate_id"],
                "decision": effective_decision,
                "decision_source": decision_source,
                "decision_reason": ledger_record["decision_reason"],
                "reviewer_hash": ledger_record["reviewer_hash"],
                "reviewed_at": ledger_record["reviewed_at"],
                "failure_reason": route_failure_reason,
                "manual_canonicalization_failure_reason": manual_failure_reason,
                "qwen_result": qwen_payload,
                "verifier_result": verifier_payload,
                "source_question_text_redacted": str(source_task.get("input", {}).get("question_text_redacted", "")),
            }
        )
        if effective_decision == "retry_qwen" and not qwen_failure_reason:
            retry_qwen_batch.append(
                _retry_qwen_batch_item(
                    source_task=source_task,
                    qwen_payload=qwen_payload,
                    verifier_payload=verifier_payload,
                    decision=decision or {},
                )
            )
        if effective_decision == "send_deepseek" and not qwen_failure_reason:
            send_deepseek_batch.append(
                _deepseek_adjudication_batch_item(
                    source_task=source_task,
                    qwen_payload=qwen_payload,
                    verifier_payload=verifier_payload,
                    decision=decision or {},
                )
            )

    for task_id in sorted(set(qwen_by_task) - set(batch_by_task)):
        reconciliation_counts["qwen_result_for_unknown_task"] += len(qwen_by_task[task_id])
        append_route(
            task_id=task_id,
            source_task={},
            decision="hold",
            decision_source="qwen_result_for_unknown_task",
            failure_reason="qwen_result_for_unknown_task",
        )
    for label, count in (
        ("qwen_results_missing_task_id", qwen_without_task_id),
        ("verifier_results_missing_task_id", verifier_without_task_id),
        ("review_decisions_missing_task_id", decisions_without_task_id),
    ):
        if count:
            reconciliation_counts[label] += count

    retry_qwen_batch_identity = _bind_canonicalization_batch_identity(retry_qwen_batch)
    _ensure_public_payload(accepted_results)
    _write_jsonl(output_path, accepted_results)
    if decision_ledger_output_path:
        _ensure_public_payload(decision_ledger)
        _write_jsonl(decision_ledger_output_path, decision_ledger)
    if retry_qwen_batch_output_path:
        _ensure_public_payload(retry_qwen_batch)
        _write_jsonl(retry_qwen_batch_output_path, retry_qwen_batch)
    if send_deepseek_batch_output_path:
        _ensure_public_payload(send_deepseek_batch)
        _write_jsonl(send_deepseek_batch_output_path, send_deepseek_batch)
    if backlog_output_path:
        _ensure_public_payload(backlog)
        _write_jsonl(backlog_output_path, backlog)

    summary = {
        "artifact_type": "tg_qa_canonicalization_routing_summary",
        "generated_at": _utc_timestamp(),
        "batch_path": str(batch_path),
        "qwen_results_path": str(qwen_results_path),
        "verifier_results_path": str(verifier_results_path or ""),
        "review_decisions_path": str(review_decisions_path or ""),
        "output_path": str(output_path),
        "decision_ledger_output_path": str(decision_ledger_output_path or ""),
        "retry_qwen_batch_output_path": str(retry_qwen_batch_output_path or ""),
        "send_deepseek_batch_output_path": str(send_deepseek_batch_output_path or ""),
        "backlog_output_path": str(backlog_output_path or ""),
        "accepted_result_count": len(accepted_results),
        "decision_ledger_count": len(decision_ledger),
        "retry_qwen_count": len(retry_qwen_batch),
        "send_deepseek_count": len(send_deepseek_batch),
        "backlog_count": len(backlog),
        "counts_by_decision": dict(sorted(counts.items())),
        "reconciliation_counts": dict(sorted(reconciliation_counts.items())),
        "canonicalization_identity_policy_version": CANONICALIZATION_IDENTITY_POLICY_VERSION,
        "routing_policy_version": CANONICALIZATION_ROUTING_POLICY_VERSION,
        "unreviewed_policy": unreviewed_policy,
        "allow_legacy_identity": allow_legacy_identity,
        **batch_identity,
        "retry_qwen_batch_identity": retry_qwen_batch_identity,
        "default_behavior_for_missing_review_decision": "hold_in_backlog",
    }
    _write_json(summary_output_path, summary)
    return {
        "accepted_results": accepted_results,
        "decision_ledger": decision_ledger,
        "retry_qwen_batch": retry_qwen_batch,
        "send_deepseek_batch": send_deepseek_batch,
        "backlog": backlog,
        "summary": summary,
    }


def _adjudication_task_identity_payload(item: Mapping[str, Any]) -> dict[str, Any]:
    """Return the immutable part of an adjudication task."""

    return {
        "task_id": str(item.get("task_id", "")),
        "candidate_id": str(item.get("candidate_id", "")),
        "canonicalization_batch_id": str(item.get("canonicalization_batch_id", "")),
        "canonicalization_batch_hash": str(item.get("canonicalization_batch_hash", "")),
        "adjudication_prompt_version": str(item.get("adjudication_prompt_version", "")),
        "source_question_text_redacted": str(item.get("source_question_text_redacted", "")),
        "question_date": str(item.get("question_date", "")),
        "candidates": [
            dict(candidate)
            for candidate in item.get("candidates", [])
            if isinstance(candidate, Mapping)
        ],
        "verifier_votes": [
            dict(vote)
            for vote in item.get("verifier_votes", [])
            if isinstance(vote, Mapping)
        ],
        "consensus_summary": dict(item.get("consensus_summary", {}))
        if isinstance(item.get("consensus_summary"), Mapping)
        else {},
        "human_triage": dict(item.get("human_triage", {}))
        if isinstance(item.get("human_triage"), Mapping)
        else {},
        "expected_output_schema": dict(item.get("expected_output_schema", {}))
        if isinstance(item.get("expected_output_schema"), Mapping)
        else {},
    }


def _bind_adjudication_batch_identity(records: Sequence[dict[str, Any]]) -> dict[str, str]:
    identities: list[dict[str, str]] = []
    seen_task_ids: set[str] = set()
    for record in records:
        task_id = str(record.get("task_id", ""))
        if not task_id:
            raise ValueError("adjudication batch contains task without task_id")
        if task_id in seen_task_ids:
            raise ValueError(f"adjudication batch contains duplicate task_id: {task_id}")
        seen_task_ids.add(task_id)
        record["adjudication_input_hash"] = _stable_json_hash(_adjudication_task_identity_payload(record))
        identities.append({"task_id": task_id, "adjudication_input_hash": record["adjudication_input_hash"]})
    batch_hash = _stable_json_hash(sorted(identities, key=lambda item: item["task_id"]))
    batch_id = f"tg-question-canonicalization-adjudication-batch:{batch_hash[:20]}"
    for record in records:
        record["adjudication_batch_id"] = batch_id
        record["adjudication_batch_hash"] = batch_hash
    return {"adjudication_batch_id": batch_id, "adjudication_batch_hash": batch_hash}


def build_tg_qa_canonicalization_adjudication_batch(
    *,
    batch_path: str | Path,
    candidate_result_specs: Sequence[str],
    verifier_result_specs: Sequence[str],
    output_path: str | Path,
    summary_output_path: str | Path,
    review_decisions_path: str | Path | None = None,
    mode: str = "non_unanimous",
    max_items: int = 0,
) -> dict[str, Any]:
    """Build generic adjudication tasks from one or more candidate and verifier result sets."""

    if mode not in {"all", "non_unanimous", "unanimous_only"}:
        raise ValueError("mode must be all, non_unanimous, or unanimous_only")
    if not candidate_result_specs:
        raise ValueError("candidate_result_specs must not be empty")

    batch_items = _read_jsonl(batch_path)
    batch_identities, batch_identity = _canonicalization_batch_identity_index(batch_items)
    batch_by_task = {str(item.get("task_id", "")): item for item in batch_items}
    candidate_specs = [_parse_keyed_path_spec(spec, label="candidate result") for spec in candidate_result_specs]
    verifier_specs = [_parse_candidate_verifier_path_spec(spec) for spec in verifier_result_specs]
    candidate_records_by_key = {
        key: _records_by_task_id(_read_jsonl(path))
        for key, path in candidate_specs
    }
    verifier_records_by_key = {
        (candidate_key, verifier_key): _records_by_task_id(_read_jsonl(path))
        for candidate_key, verifier_key, path in verifier_specs
    }
    decision_records = [
        item
        for item in (_read_jsonl(review_decisions_path) if review_decisions_path else [])
        if str(item.get("status", "")) != "failed"
    ]
    decisions_by_task = {str(item.get("task_id", "")): item for item in decision_records}

    records: list[dict[str, Any]] = []
    counts = Counter()
    escalation_reasons = Counter()
    expected_candidate_keys = [key for key, _ in candidate_specs]

    for task_id, source_task in batch_by_task.items():
        candidates: list[dict[str, Any]] = []
        candidate_id = str(source_task.get("candidate_id", ""))
        for candidate_key, _candidate_path in candidate_specs:
            raw = candidate_records_by_key[candidate_key].get(task_id)
            if raw is None:
                continue
            payload = _extract_result_payload(raw)
            candidate_id = candidate_id or str(payload.get("candidate_id", ""))
            candidates.append(_adjudication_candidate_entry(candidate_key, payload))

        verifier_votes: list[dict[str, Any]] = []
        for candidate_key, verifier_key, _verifier_path in verifier_specs:
            raw = verifier_records_by_key[(candidate_key, verifier_key)].get(task_id)
            if raw is None:
                continue
            payload = _extract_result_payload(raw)
            verifier_votes.append(_adjudication_verifier_vote_entry(candidate_key, verifier_key, payload))

        consensus_summary = _adjudication_consensus_summary(
            expected_candidate_keys=expected_candidate_keys,
            candidates=candidates,
            verifier_votes=verifier_votes,
        )
        unanimous = _bool_value(consensus_summary.get("unanimous", False))
        if mode == "non_unanimous" and unanimous:
            counts["filtered_unanimous"] += 1
            continue
        if mode == "unanimous_only" and not unanimous:
            counts["filtered_non_unanimous"] += 1
            continue
        for reason in _as_string_list(consensus_summary.get("escalation_reason_codes", [])):
            escalation_reasons[reason] += 1
        if unanimous:
            counts["unanimous"] += 1
        else:
            counts["non_unanimous"] += 1
        record = {
            "task_id": task_id,
            "candidate_id": candidate_id,
            "canonicalization_batch_id": batch_identity["canonicalization_batch_id"],
            "canonicalization_batch_hash": batch_identity["canonicalization_batch_hash"],
            "task_input_hash": batch_identities[task_id]["task_input_hash"],
            "canonicalization_contract_version": str(
                source_task.get("canonicalization_contract_version", "")
            ),
            "canonicalization_prompt_version": str(source_task.get("prompt_version", "")),
            "canonicalization_prompt_profile_hash": batch_identities[task_id]["prompt_profile_hash"],
            "adjudication_prompt_version": CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION,
            "source_question_text_redacted": str(source_task.get("input", {}).get("question_text_redacted", "")),
            "question_date": str(source_task.get("input", {}).get("question_date", "")),
            "candidates": candidates,
            "verifier_votes": verifier_votes,
            "consensus_summary": consensus_summary,
            "human_triage": {
                "decision": str(decisions_by_task.get(task_id, {}).get("decision", "")),
                "decision_reason": str(decisions_by_task.get(task_id, {}).get("decision_reason", "")),
                "reviewer_hash": str(decisions_by_task.get(task_id, {}).get("reviewer_hash", "")),
            },
            "expected_output_schema": {
                "verdict": "pass|fail|uncertain",
                "confidence": "0-100 integer",
                "risk": "none|low|medium|high",
                "bad_fields": "array[string]",
                "short_reason": "string",
                "final_recommendation": "accept|reject|retry_generator|human_review",
                "selected_candidate_key": "string",
            },
        }
        records.append(record)
        if max_items > 0 and len(records) >= max_items:
            break

    adjudication_batch_identity = _bind_adjudication_batch_identity(records)
    _ensure_public_payload(records)
    _write_jsonl(output_path, records)
    summary = {
        "artifact_type": "tg_qa_canonicalization_adjudication_batch_summary",
        "generated_at": _utc_timestamp(),
        "batch_path": str(batch_path),
        "output_path": str(output_path),
        "summary_output_path": str(summary_output_path),
        "review_decisions_path": str(review_decisions_path or ""),
        "candidate_result_specs": list(candidate_result_specs),
        "verifier_result_specs": list(verifier_result_specs),
        "mode": mode,
        "canonicalization_identity_policy_version": CANONICALIZATION_IDENTITY_POLICY_VERSION,
        **batch_identity,
        **adjudication_batch_identity,
        "adjudication_prompt_version": CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION,
        "adjudication_prompt_profile_hash": _canonicalization_prompt_profile_hash(
            CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION
        ),
        "max_items": max_items,
        "available_task_count": len(batch_items),
        "emitted_task_count": len(records),
        "counts": dict(sorted(counts.items())),
        "counts_by_escalation_reason": dict(sorted(escalation_reasons.items())),
        "trust_boundary": "adjudication_tasks_are_review_evidence_only",
    }
    _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def build_tg_qa_canonicalization_retry_batch_from_adjudication(
    *,
    batch_path: str | Path,
    adjudication_batch_path: str | Path,
    adjudication_results_path: str | Path | None = None,
    adjudication_results_paths: Sequence[str | Path] | None = None,
    output_path: str | Path,
    summary_output_path: str | Path,
    max_items: int = 0,
) -> dict[str, Any]:
    """Build generator retry tasks from adjudicator retry_generator decisions."""

    result_paths: list[str | Path] = []
    if adjudication_results_path:
        result_paths.append(adjudication_results_path)
    if adjudication_results_paths:
        result_paths.extend(adjudication_results_paths)
    if not result_paths:
        raise ValueError("at least one adjudication results path is required")

    batch_items = _read_jsonl(batch_path)
    _canonicalization_batch_identity_index(batch_items)
    adjudication_items = _read_jsonl(adjudication_batch_path)
    batch_by_task = {str(item.get("task_id", "")): item for item in batch_items}
    adjudication_by_task = _records_by_task_id(adjudication_items)
    adjudication_results_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    records: list[dict[str, Any]] = []
    counts = Counter()
    skipped_reasons = Counter()
    source_result_count = 0
    for result_index, result_path in enumerate(result_paths, start=1):
        result_key = _adjudication_results_key(result_path, result_index)
        for raw_result in _read_jsonl(_adjudication_results_path(result_path)):
            source_result_count += 1
            result = _extract_result_payload(raw_result)
            task_id = str(result.get("task_id", ""))
            if not task_id:
                skipped_reasons["missing_task_id"] += 1
                continue
            adjudication_results_by_task[task_id].append(
                _adjudication_result_retry_entry(result_key, result)
            )

    for task_id, adjudication_results in sorted(adjudication_results_by_task.items()):
        completed_results = [
            result for result in adjudication_results if str(result.get("status", "")) == "completed"
        ]
        if len(completed_results) != len(adjudication_results):
            skipped_reasons["human_review_before_retry:non_completed_adjudication"] += 1
            continue
        manual_results = [
            result for result in completed_results if _is_manual_adjudication_result(result)
        ]
        routing_results = manual_results or completed_results
        recommendations = {
            str(result.get("final_recommendation", ""))
            for result in routing_results
        }
        if recommendations != {"retry_generator"}:
            for recommendation in sorted(recommendations):
                skipped_reasons[f"final_recommendation:{recommendation or 'missing'}"] += 1
            continue
        source_task = batch_by_task.get(task_id)
        adjudication_item = adjudication_by_task.get(task_id)
        if source_task is None:
            skipped_reasons["missing_source_task"] += 1
            continue
        if adjudication_item is None:
            skipped_reasons["missing_adjudication_batch_item"] += 1
            continue
        selected_candidate_keys = {
            _selected_adjudication_candidate_key(result, adjudication_item)
            for result in routing_results
        }
        selected_candidate_keys = {key for key in selected_candidate_keys if key}
        if len(selected_candidate_keys) != 1:
            skipped_reasons["human_review_before_retry:selected_candidate_disagreement"] += 1
            continue
        representative_result = routing_results[0]
        selected_candidate_key = _selected_adjudication_candidate_key(
            representative_result,
            adjudication_item,
        )
        selected_candidate = _adjudication_candidate_by_key(adjudication_item, selected_candidate_key)
        if not selected_candidate:
            skipped_reasons["missing_selected_candidate"] += 1
            continue
        retry_triage = _retry_consensus_triage(
            adjudication_results=routing_results,
            adjudication_item=adjudication_item,
            selected_candidate_key=selected_candidate_key,
        )
        if str(retry_triage.get("route", "")) != "auto_retry":
            skipped_reasons[f"human_review_before_retry:{retry_triage.get('reason_code', 'unknown')}"] += 1
            continue
        records.append(
            _retry_generator_batch_item(
                source_task=source_task,
                adjudication_item=adjudication_item,
                selected_candidate=selected_candidate,
                adjudication_result=representative_result,
                adjudication_results=completed_results,
                retry_triage=retry_triage,
            )
        )
        counts["auto_retry"] += 1
        if max_items > 0 and len(records) >= max_items:
            break

    retry_batch_identity = _bind_canonicalization_batch_identity(records)
    _ensure_public_payload(records)
    _write_jsonl(output_path, records)
    summary = {
        "artifact_type": "tg_qa_canonicalization_adjudication_retry_batch_summary",
        "generated_at": _utc_timestamp(),
        "batch_path": str(batch_path),
        "adjudication_batch_path": str(adjudication_batch_path),
        "adjudication_results_path": str(result_paths[0]),
        "adjudication_results_paths": [str(path) for path in result_paths],
        "output_path": str(output_path),
        "summary_output_path": str(summary_output_path),
        "max_items": max_items,
        "canonicalization_identity_policy_version": CANONICALIZATION_IDENTITY_POLICY_VERSION,
        **retry_batch_identity,
        "source_result_count": source_result_count,
        "emitted_task_count": len(records),
        "counts": dict(sorted(counts.items())),
        "skipped_reasons": dict(sorted(skipped_reasons.items())),
        "trust_boundary": "retry_tasks_are_review_evidence_only",
    }
    _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def run_tg_qa_canonicalization_llm_batch(
    *,
    batch_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    endpoint_url: str,
    model_id: str,
    canonicalization_run_id: str,
    max_items: int = 0,
    timeout_seconds: int = 180,
    max_tokens: int = 1200,
    structured_output_method: str = "json_mode",
    provider: str = "openai",
    api_key_env: str = "",
    extra_body: Mapping[str, Any] | None = None,
    stop_on_failure: bool = False,
    runtime_contour: str = "opencode_go_openai_compatible_chat_completion",
    backend: str = "opencode",
    resume: bool = True,
    provider_max_attempts: int = 3,
    provider_retry_delay_seconds: float = 2.0,
    stop_after_consecutive_provider_failures: int = 0,
    progress: bool = False,
    checkpoint_output_path: str | Path | None = None,
    run_bundle_output_path: str | Path | None = None,
    log_path: str = "",
    chain: Any | None = None,
) -> dict[str, Any]:
    """Run Qwen-style canonicalization over a bounded batch with structured output."""

    if provider not in {"anthropic", "openai"}:
        raise ValueError("provider must be anthropic or openai")
    if structured_output_method not in {"function_calling", "json_mode", "json_schema"}:
        raise ValueError("structured_output_method must be function_calling, json_mode, or json_schema")
    if provider_max_attempts < 0:
        raise ValueError("provider_max_attempts must be non-negative")
    if provider_retry_delay_seconds < 0:
        raise ValueError("provider_retry_delay_seconds must be non-negative")
    if stop_after_consecutive_provider_failures < 0:
        raise ValueError("stop_after_consecutive_provider_failures must be non-negative")
    batch_items = _read_jsonl(batch_path)
    _task_identities, batch_identity = _canonicalization_batch_identity_index(batch_items)
    mismatched_prompt_tasks = [
        str(item.get("task_id", ""))
        for item in batch_items
        if str(item.get("prompt_version", "")) != CANONICALIZATION_PROMPT_VERSION
    ]
    if mismatched_prompt_tasks:
        raise ValueError(
            "canonicalization batch prompt_version does not match active profile; emit a new batch or set the matching prompt version"
        )
    runtime_profile = _operator_runtime_profile(
        stage="canonicalization",
        prompt_version=CANONICALIZATION_PROMPT_VERSION,
        prompt_profile_hash=_canonicalization_prompt_profile_hash(CANONICALIZATION_PROMPT_VERSION),
        provider=provider,
        runtime_contour=runtime_contour,
        backend=backend,
        model_id=model_id,
        structured_output_method=structured_output_method,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        extra_body=extra_body,
        input_batch_hash=batch_identity["canonicalization_batch_hash"],
    )
    resume_state = (
        _load_existing_operator_results(
            output_path,
            batch_items,
            stage="canonicalization",
            runtime_profile=runtime_profile,
            input_identity_field="task_input_hash",
        )
        if resume
        else _empty_operator_resume_state()
    )
    remaining_items = [
        item for item in batch_items if str(item.get("task_id", "")) not in resume_state["processed_task_ids"]
    ]
    selected_items = remaining_items[:max_items] if max_items > 0 else remaining_items
    started_at = _utc_timestamp()
    started = perf_counter()
    runner = chain or _build_canonicalization_chain(
        provider=provider,
        endpoint_url=endpoint_url,
        model_id=model_id,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        structured_output_method=structured_output_method,
        api_key_env=api_key_env,
        extra_body=extra_body,
    )
    counts = Counter()
    records: list[dict[str, Any]] = []
    checkpoint_path = Path(checkpoint_output_path or _operator_artifact_path(summary_output_path, "checkpoint"))
    bundle_path = Path(run_bundle_output_path or _operator_artifact_path(summary_output_path, "run_bundle"))
    checkpoint_task_ids = set(resume_state["processed_task_ids"])
    checkpoint_status_counts: Counter[str] = Counter(resume_state["status_counts"])
    progress_line = _OperatorProgress(
        enabled=progress,
        label="tg-qa-canonicalization-llm-run",
        total=len(selected_items),
    )
    output_handle = _open_jsonl_stream(output_path, append=resume and bool(resume_state["processed_task_ids"]))
    consecutive_provider_failure_key = ""
    consecutive_provider_failure_count = 0
    stopped_by_provider_failure_guard = False
    provider_failure_guard_trigger = ""
    try:
        for item_index, item in enumerate(selected_items, start=1):
            progress_line.update(
                item_index - 1,
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                skipped=counts.get("skipped", 0),
                last_status="request",
                detail=_operator_progress_detail("request", item_index, len(selected_items), item),
            )
            counts["processed"] += 1
            compact_payload = compact_canonicalization_llm_payload(item)
            attempts_used = 0
            item_started = perf_counter()
            last_raw_result: Any = None
            while True:
                attempts_used += 1
                try:
                    raw_result = runner.invoke({"task_payload": _json_for_prompt(compact_payload)})
                    last_raw_result = raw_result
                    record = _canonicalization_record_from_structured_output(
                        raw_result,
                        item,
                        canonicalization_run_id=canonicalization_run_id,
                        runtime_contour=runtime_contour,
                        backend=backend,
                        model_id=model_id,
                    )
                    break
                except Exception as exc:  # pragma: no cover - live endpoint failures vary
                    failure_reason = _operator_error_reason(exc)
                    retry_limit = _operator_retry_limit_for_exception(exc, provider_max_attempts)
                    if _operator_should_retry_exception(exc) and _operator_retry_allowed(
                        attempts_used,
                        retry_limit,
                    ):
                        if isinstance(exc, RetryableOperatorOutputError):
                            counts["output_retry"] += 1
                        else:
                            counts["provider_retry"] += 1
                        progress_line.update(
                            item_index - 1,
                            completed=counts.get("completed", 0),
                            failed=counts.get("failed", 0),
                            skipped=counts.get("skipped", 0),
                            last_status="retry",
                            detail=_operator_progress_detail(
                                f"retry {attempts_used + 1}/{_operator_retry_limit_label(retry_limit)}",
                                item_index,
                                len(selected_items),
                                item,
                                failure_reason=failure_reason,
                            ),
                        )
                        if not isinstance(exc, RetryableOperatorOutputError) and provider_retry_delay_seconds > 0:
                            sleep(provider_retry_delay_seconds)
                        continue
                    if _operator_should_retry_exception(exc):
                        if isinstance(exc, RetryableOperatorOutputError):
                            counts["output_retry_exhausted"] += 1
                        else:
                            counts["provider_retry_exhausted"] += 1
                    record = _operator_failed_canonicalization_record(
                        item,
                        canonicalization_run_id=canonicalization_run_id,
                        failure_reason=_operator_failure_reason_with_attempts(failure_reason, attempts_used),
                        runtime_contour=runtime_contour,
                        backend=backend,
                        model_id=model_id,
                    )
                    break
            record = _attach_runtime_metadata(
                _attach_operator_record_identity(
                    record,
                    stage="canonicalization",
                    input_item=item,
                    runtime_profile=runtime_profile,
                ),
                _operator_record_runtime_metadata(
                    last_raw_result,
                    request_duration_seconds=perf_counter() - item_started,
                    attempts_used=attempts_used,
                ),
            )
            counts[str(record.get("status", "failed"))] += 1
            records.append(record)
            _write_jsonl_stream_record(output_handle, record)
            checkpoint_task_ids.add(str(record.get("task_id", "")))
            checkpoint_status_counts[str(record.get("status", ""))] += 1
            _write_operator_checkpoint(
                checkpoint_output_path=checkpoint_path,
                stage="canonicalization",
                input_path=batch_path,
                output_path=output_path,
                runtime_profile=runtime_profile,
                processed_task_ids=checkpoint_task_ids,
                status_counts=checkpoint_status_counts,
            )
            progress_line.update(
                item_index,
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                skipped=counts.get("skipped", 0),
                last_status=str(record.get("status", "done")),
                detail=_operator_progress_detail(
                    str(record.get("status", "done")),
                    item_index,
                    len(selected_items),
                    item,
                    failure_reason=str(record.get("failure_reason", "")),
                ),
            )
            provider_failure_key = _operator_provider_failure_guard_key(record)
            if provider_failure_key:
                if provider_failure_key == consecutive_provider_failure_key:
                    consecutive_provider_failure_count += 1
                else:
                    consecutive_provider_failure_key = provider_failure_key
                    consecutive_provider_failure_count = 1
            else:
                consecutive_provider_failure_key = ""
                consecutive_provider_failure_count = 0
            if (
                stop_after_consecutive_provider_failures > 0
                and consecutive_provider_failure_count >= stop_after_consecutive_provider_failures
            ):
                stopped_by_provider_failure_guard = True
                provider_failure_guard_trigger = consecutive_provider_failure_key
                progress_line.update(
                    item_index,
                    completed=counts.get("completed", 0),
                    failed=counts.get("failed", 0),
                    skipped=counts.get("skipped", 0),
                    last_status="stopped",
                    detail=(
                        "provider_failure_guard "
                        f"{consecutive_provider_failure_count}/"
                        f"{stop_after_consecutive_provider_failures} "
                        f"{provider_failure_guard_trigger}"
                    ),
                )
                break
            if stop_on_failure and str(record.get("status", "")) == "failed":
                break
    finally:
        output_handle.close()
        progress_line.finish(
            counts.get("processed", 0),
            completed=counts.get("completed", 0),
            failed=counts.get("failed", 0),
            skipped=counts.get("skipped", 0),
        )

    completed_at = _utc_timestamp()
    duration = perf_counter() - started
    summary = {
        "artifact_type": "tg_qa_canonicalization_llm_run_summary",
        "generated_at": completed_at,
        "batch_path": str(batch_path),
        "output_path": str(output_path),
        "summary_output_path": str(summary_output_path),
        "canonicalization_run_id": canonicalization_run_id,
        "canonicalization_batch_id": batch_identity["canonicalization_batch_id"],
        "canonicalization_batch_hash": batch_identity["canonicalization_batch_hash"],
        "prompt_version": CANONICALIZATION_PROMPT_VERSION,
        "prompt_profile_hash": _canonicalization_prompt_profile_hash(CANONICALIZATION_PROMPT_VERSION),
        "runtime_profile": runtime_profile,
        "runtime_profile_hash": _stable_json_hash(runtime_profile),
        "endpoint_shape": _redacted_endpoint_shape(endpoint_url),
        "provider": provider,
        "runtime_contour": runtime_contour,
        "backend": backend,
        "model_id": model_id,
        "api_key_env": api_key_env,
        "auth_mode": "bearer_env" if api_key_env else "none",
        "structured_output_method": structured_output_method,
        "structured_output_adapter_version": atomic_structured_output_adapter_version(
            structured_output_method
        ),
        "extra_body_keys": sorted(extra_body.keys()) if isinstance(extra_body, Mapping) else [],
        "stop_on_failure": stop_on_failure,
        "stop_after_consecutive_provider_failures": stop_after_consecutive_provider_failures,
        "stopped_by_provider_failure_guard": stopped_by_provider_failure_guard,
        "provider_failure_guard_trigger": provider_failure_guard_trigger,
        "consecutive_provider_failure_count": consecutive_provider_failure_count,
        "unprocessed_count_due_to_provider_failure_guard": (
            len(selected_items) - counts.get("processed", 0) if stopped_by_provider_failure_guard else 0
        ),
        "resume": resume,
        "progress": progress,
        "provider_max_attempts": provider_max_attempts,
        "provider_retry_forever": provider_max_attempts == 0,
        "provider_retry_delay_seconds": provider_retry_delay_seconds,
        "max_items": max_items,
        "max_tokens": max_tokens,
        "timeout_seconds": timeout_seconds,
        "requested_item_count": len(selected_items),
        "remaining_item_count_before_run": len(remaining_items),
        "available_batch_item_count": len(batch_items),
        "processed_count": counts.get("processed", 0),
        "completed_count": counts.get("completed", 0),
        "failed_count": counts.get("failed", 0),
        "skipped_count": counts.get("skipped", 0),
        "provider_retry_count": counts.get("provider_retry", 0),
        "provider_retry_exhausted_count": counts.get("provider_retry_exhausted", 0),
        "output_retry_count": counts.get("output_retry", 0),
        "output_retry_exhausted_count": counts.get("output_retry_exhausted", 0),
        "resumed_existing_count": len(resume_state["processed_task_ids"]),
        "existing_status_counts": dict(sorted(resume_state["status_counts"].items())),
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": round(duration, 3),
        "items_per_second": round(len(selected_items) / duration, 3) if duration > 0 else 0,
        "trust_boundary": "canonicalization_results_are_review_evidence_only",
    }
    summary.update(_operator_runtime_summary(records))
    summary["checkpoint_output_path"] = str(checkpoint_path)
    summary["run_bundle_output_path"] = str(bundle_path)
    _write_json(summary_output_path, summary)
    _write_operator_checkpoint(
        checkpoint_output_path=checkpoint_path,
        stage="canonicalization",
        input_path=batch_path,
        output_path=output_path,
        runtime_profile=runtime_profile,
        processed_task_ids=checkpoint_task_ids,
        status_counts=checkpoint_status_counts,
    )
    _write_operator_run_bundle(
        bundle_output_path=bundle_path,
        checkpoint_output_path=checkpoint_path,
        summary_output_path=summary_output_path,
        result_output_path=output_path,
        stage="canonicalization",
        runtime_profile=runtime_profile,
        command_metadata={
            "command": "evaluation tg-qa-canonicalization-llm-run",
            "resume": resume,
            "max_items": max_items,
            "stop_on_failure": stop_on_failure,
            "stop_after_consecutive_provider_failures": stop_after_consecutive_provider_failures,
        },
        log_path=log_path,
    )
    return {"results": records, "summary": summary}


def run_tg_qa_canonicalization_verifier_batch(
    *,
    evidence_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    endpoint_url: str,
    model_id: str,
    verifier_run_id: str,
    provider: str = "anthropic",
    max_items: int = 0,
    timeout_seconds: int = 180,
    max_tokens: int = 1024,
    structured_output_method: str = "function_calling",
    api_key_env: str = "",
    extra_body: Mapping[str, Any] | None = None,
    stop_on_failure: bool = False,
    runtime_contour: str = "minimax_anthropic_compatible_tool_use",
    backend: str = "minimax",
    resume: bool = True,
    provider_max_attempts: int = 3,
    provider_retry_delay_seconds: float = 2.0,
    stop_after_consecutive_provider_failures: int = 0,
    progress: bool = False,
    checkpoint_output_path: str | Path | None = None,
    run_bundle_output_path: str | Path | None = None,
    log_path: str = "",
    chain: Any | None = None,
) -> dict[str, Any]:
    """Run compact verifier verdicts over locally valid canonicalization evidence."""

    if provider not in {"anthropic", "openai"}:
        raise ValueError("provider must be anthropic or openai")
    if provider_max_attempts < 0:
        raise ValueError("provider_max_attempts must be non-negative")
    if provider_retry_delay_seconds < 0:
        raise ValueError("provider_retry_delay_seconds must be non-negative")
    if stop_after_consecutive_provider_failures < 0:
        raise ValueError("stop_after_consecutive_provider_failures must be non-negative")
    evidence_records = _read_jsonl(evidence_path)
    input_batch_hash = _operator_input_batch_hash(
        evidence_records,
        identity_field="canonicalization_evidence_hash",
    )
    runtime_profile = _operator_runtime_profile(
        stage="verifier",
        prompt_version=CANONICALIZATION_VERIFIER_PROMPT_VERSION,
        prompt_profile_hash=_canonicalization_prompt_profile_hash(CANONICALIZATION_VERIFIER_PROMPT_VERSION),
        provider=provider,
        runtime_contour=runtime_contour,
        backend=backend,
        model_id=model_id,
        structured_output_method=structured_output_method,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        extra_body=extra_body,
        input_batch_hash=input_batch_hash,
    )
    resume_state = (
        _load_existing_operator_results(
            output_path,
            evidence_records,
            stage="verifier",
            runtime_profile=runtime_profile,
            input_identity_field="canonicalization_evidence_hash",
        )
        if resume
        else _empty_operator_resume_state()
    )
    remaining_records = [
        evidence for evidence in evidence_records if str(evidence.get("task_id", "")) not in resume_state["processed_task_ids"]
    ]
    selected_records = remaining_records[:max_items] if max_items > 0 else remaining_records
    started_at = _utc_timestamp()
    started = perf_counter()
    runner = chain or _build_verifier_chain(
        provider=provider,
        endpoint_url=endpoint_url,
        model_id=model_id,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        structured_output_method=structured_output_method,
        api_key_env=api_key_env,
        extra_body=extra_body,
    )
    counts = Counter()
    records: list[dict[str, Any]] = []
    checkpoint_path = Path(checkpoint_output_path or _operator_artifact_path(summary_output_path, "checkpoint"))
    bundle_path = Path(run_bundle_output_path or _operator_artifact_path(summary_output_path, "run_bundle"))
    checkpoint_task_ids = set(resume_state["processed_task_ids"])
    checkpoint_status_counts: Counter[str] = Counter(resume_state["status_counts"])
    progress_line = _OperatorProgress(
        enabled=progress,
        label="tg-qa-canonicalization-verifier-run",
        total=len(selected_records),
    )
    output_handle = _open_jsonl_stream(output_path, append=resume and bool(resume_state["processed_task_ids"]))
    consecutive_provider_failure_key = ""
    consecutive_provider_failure_count = 0
    stopped_by_provider_failure_guard = False
    provider_failure_guard_trigger = ""
    try:
        for item_index, evidence in enumerate(selected_records, start=1):
            progress_line.update(
                item_index - 1,
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                skipped=counts.get("skipped", 0),
                last_status="request",
                detail=_operator_progress_detail("request", item_index, len(selected_records), evidence),
            )
            counts["processed"] += 1
            if str(evidence.get("status", "")) != "completed":
                record = _skipped_verifier_record(
                    evidence,
                    verifier_run_id=verifier_run_id,
                    failure_reason=str(evidence.get("failure_reason", "non_completed_canonicalization_evidence")),
                    runtime_contour=runtime_contour,
                    backend=backend,
                    model_id=model_id,
                )
            else:
                verifier_payload = _compact_verifier_llm_payload(evidence)
                attempts_used = 0
                item_started = perf_counter()
                last_raw_result: Any = None
                while True:
                    attempts_used += 1
                    try:
                        raw_result = runner.invoke({"verifier_payload": _review_payload_for_prompt(verifier_payload)})
                        last_raw_result = raw_result
                        record = _verifier_record_from_structured_output(
                            raw_result,
                            evidence,
                            verifier_run_id=verifier_run_id,
                            runtime_contour=runtime_contour,
                            backend=backend,
                            model_id=model_id,
                        )
                        break
                    except Exception as exc:  # pragma: no cover - live endpoint failures vary
                        failure_reason = _operator_error_reason(exc)
                        if _operator_should_retry_exception(exc) and _operator_retry_allowed(
                            attempts_used,
                            provider_max_attempts,
                        ):
                            counts["provider_retry"] += 1
                            progress_line.update(
                                item_index - 1,
                                completed=counts.get("completed", 0),
                                failed=counts.get("failed", 0),
                                skipped=counts.get("skipped", 0),
                                last_status="retry",
                                detail=_operator_progress_detail(
                                    f"retry {attempts_used + 1}/{_operator_retry_limit_label(provider_max_attempts)}",
                                    item_index,
                                    len(selected_records),
                                    evidence,
                                    failure_reason=failure_reason,
                                ),
                            )
                            if provider_retry_delay_seconds > 0:
                                sleep(provider_retry_delay_seconds)
                            continue
                        if _operator_should_retry_exception(exc):
                            counts["provider_retry_exhausted"] += 1
                        record = _failed_verifier_record(
                            evidence,
                            verifier_run_id=verifier_run_id,
                            failure_reason=_operator_failure_reason_with_attempts(failure_reason, attempts_used),
                            runtime_contour=runtime_contour,
                            backend=backend,
                            model_id=model_id,
                        )
                        break
                record = _attach_runtime_metadata(
                    record,
                    _operator_record_runtime_metadata(
                        last_raw_result,
                        request_duration_seconds=perf_counter() - item_started,
                        attempts_used=attempts_used,
                    ),
                )
            if str(evidence.get("status", "")) != "completed":
                record = _attach_runtime_metadata(
                    record,
                    _operator_record_runtime_metadata(
                        None,
                        request_duration_seconds=0.0,
                        attempts_used=0,
                    ),
                )
            record = _attach_operator_record_identity(
                record,
                stage="verifier",
                input_item=evidence,
                runtime_profile=runtime_profile,
            )
            counts[str(record.get("status", "failed"))] += 1
            records.append(record)
            _write_jsonl_stream_record(output_handle, record)
            checkpoint_task_ids.add(str(record.get("task_id", "")))
            checkpoint_status_counts[str(record.get("status", ""))] += 1
            _write_operator_checkpoint(
                checkpoint_output_path=checkpoint_path,
                stage="verifier",
                input_path=evidence_path,
                output_path=output_path,
                runtime_profile=runtime_profile,
                processed_task_ids=checkpoint_task_ids,
                status_counts=checkpoint_status_counts,
            )
            progress_line.update(
                item_index,
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                skipped=counts.get("skipped", 0),
                last_status=str(record.get("status", "done")),
                detail=_operator_progress_detail(
                    str(record.get("status", "done")),
                    item_index,
                    len(selected_records),
                    evidence,
                    failure_reason=str(record.get("failure_reason", "")),
                ),
            )
            provider_failure_key = _operator_provider_failure_guard_key(record)
            if provider_failure_key:
                if provider_failure_key == consecutive_provider_failure_key:
                    consecutive_provider_failure_count += 1
                else:
                    consecutive_provider_failure_key = provider_failure_key
                    consecutive_provider_failure_count = 1
            else:
                consecutive_provider_failure_key = ""
                consecutive_provider_failure_count = 0
            if (
                stop_after_consecutive_provider_failures > 0
                and consecutive_provider_failure_count >= stop_after_consecutive_provider_failures
            ):
                stopped_by_provider_failure_guard = True
                provider_failure_guard_trigger = consecutive_provider_failure_key
                progress_line.update(
                    item_index,
                    completed=counts.get("completed", 0),
                    failed=counts.get("failed", 0),
                    skipped=counts.get("skipped", 0),
                    last_status="stopped",
                    detail=(
                        "provider_failure_guard "
                        f"{consecutive_provider_failure_count}/"
                        f"{stop_after_consecutive_provider_failures} "
                        f"{provider_failure_guard_trigger}"
                    ),
                )
                break
            if stop_on_failure and str(record.get("status", "")) == "failed":
                break
    finally:
        output_handle.close()
        progress_line.finish(
            counts.get("processed", 0),
            completed=counts.get("completed", 0),
            failed=counts.get("failed", 0),
            skipped=counts.get("skipped", 0),
        )

    completed_at = _utc_timestamp()
    duration = perf_counter() - started
    summary = {
        "artifact_type": "tg_qa_canonicalization_verifier_run_summary",
        "generated_at": completed_at,
        "evidence_path": str(evidence_path),
        "output_path": str(output_path),
        "summary_output_path": str(summary_output_path),
        "verifier_run_id": verifier_run_id,
        "verifier_prompt_version": CANONICALIZATION_VERIFIER_PROMPT_VERSION,
        "verifier_prompt_profile_hash": _canonicalization_prompt_profile_hash(
            CANONICALIZATION_VERIFIER_PROMPT_VERSION
        ),
        "runtime_profile": runtime_profile,
        "runtime_profile_hash": _stable_json_hash(runtime_profile),
        "endpoint_shape": _redacted_endpoint_shape(endpoint_url),
        "provider": provider,
        "runtime_contour": runtime_contour,
        "backend": backend,
        "model_id": model_id,
        "api_key_env": api_key_env,
        "auth_mode": "bearer_env" if api_key_env else "none",
        "structured_output_method": structured_output_method,
        "extra_body_keys": sorted(extra_body.keys()) if isinstance(extra_body, Mapping) else [],
        "stop_on_failure": stop_on_failure,
        "stop_after_consecutive_provider_failures": stop_after_consecutive_provider_failures,
        "stopped_by_provider_failure_guard": stopped_by_provider_failure_guard,
        "provider_failure_guard_trigger": provider_failure_guard_trigger,
        "consecutive_provider_failure_count": consecutive_provider_failure_count,
        "unprocessed_count_due_to_provider_failure_guard": (
            len(selected_records) - counts.get("processed", 0) if stopped_by_provider_failure_guard else 0
        ),
        "resume": resume,
        "progress": progress,
        "provider_max_attempts": provider_max_attempts,
        "provider_retry_forever": provider_max_attempts == 0,
        "provider_retry_delay_seconds": provider_retry_delay_seconds,
        "max_items": max_items,
        "max_tokens": max_tokens,
        "timeout_seconds": timeout_seconds,
        "requested_item_count": len(selected_records),
        "remaining_evidence_count_before_run": len(remaining_records),
        "available_evidence_count": len(evidence_records),
        "processed_count": counts.get("processed", 0),
        "completed_count": counts.get("completed", 0),
        "failed_count": counts.get("failed", 0),
        "skipped_count": counts.get("skipped", 0),
        "provider_retry_count": counts.get("provider_retry", 0),
        "provider_retry_exhausted_count": counts.get("provider_retry_exhausted", 0),
        "resumed_existing_count": len(resume_state["processed_task_ids"]),
        "existing_status_counts": dict(sorted(resume_state["status_counts"].items())),
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": round(duration, 3),
        "items_per_second": round(len(selected_records) / duration, 3) if duration > 0 else 0,
        "trust_boundary": "verifier_results_are_review_evidence_only",
    }
    summary.update(_operator_runtime_summary(records))
    summary["checkpoint_output_path"] = str(checkpoint_path)
    summary["run_bundle_output_path"] = str(bundle_path)
    _write_json(summary_output_path, summary)
    _write_operator_checkpoint(
        checkpoint_output_path=checkpoint_path,
        stage="verifier",
        input_path=evidence_path,
        output_path=output_path,
        runtime_profile=runtime_profile,
        processed_task_ids=checkpoint_task_ids,
        status_counts=checkpoint_status_counts,
    )
    _write_operator_run_bundle(
        bundle_output_path=bundle_path,
        checkpoint_output_path=checkpoint_path,
        summary_output_path=summary_output_path,
        result_output_path=output_path,
        stage="verifier",
        runtime_profile=runtime_profile,
        command_metadata={
            "command": "evaluation tg-qa-canonicalization-verifier-run",
            "resume": resume,
            "max_items": max_items,
            "stop_on_failure": stop_on_failure,
            "stop_after_consecutive_provider_failures": stop_after_consecutive_provider_failures,
        },
        log_path=log_path,
    )
    return {"results": records, "summary": summary}


def _atomic_verification_from_structured_output(raw_result: Any) -> AtomicVerificationPayload:
    payload = _structured_output_payload(raw_result) if raw_result is not None else {}
    return AtomicVerificationPayload.model_validate(_unwrap_structured_output_mapping(payload))


def _atomic_unique_source_span(source_text: str, quote: str) -> AtomicSourceSpanPayload | None:
    if not quote:
        return None
    start = source_text.find(quote)
    if start < 0 or source_text.find(quote, start + 1) >= 0:
        return None
    return AtomicSourceSpanPayload(start=start, end=start + len(quote), quote=quote)


def _atomic_verification_from_formatter_output(
    raw_result: Any,
    stage_payload: Any,
) -> AtomicVerificationPayload:
    payload = _structured_output_payload(raw_result) if raw_result is not None else {}
    formatted = AtomicFormatterVerificationPayload.model_validate(
        _unwrap_structured_output_mapping(payload)
    )
    if isinstance(stage_payload, Mapping):
        original_payload = dict(stage_payload)
    else:
        original_payload = json.loads(str(stage_payload))
    source_text = str(original_payload.get("source_question_text_redacted", ""))
    verdicts: list[AtomicClaimVerdictPayload] = []
    converted_to_unresolved = False
    for formatted_verdict in formatted.claim_verdicts:
        spans: list[AtomicSourceSpanPayload] = []
        seen_quotes: set[str] = set()
        for quote in formatted_verdict.source_quotes:
            if quote in seen_quotes:
                continue
            seen_quotes.add(quote)
            span = _atomic_unique_source_span(source_text, quote)
            if span is not None:
                spans.append(span)
        support = formatted_verdict.support
        short_reason = formatted_verdict.short_reason
        if support in {"explicit", "necessary_inference"} and not spans:
            support = "unresolved"
            converted_to_unresolved = True
            short_reason = (
                "Formatter could not resolve one unique exact source quote. "
                f"{short_reason}"
            ).strip()
        verdicts.append(
            AtomicClaimVerdictPayload(
                claim_id=formatted_verdict.claim_id,
                support=support,
                relation_kind=formatted_verdict.relation_kind,
                materiality=formatted_verdict.materiality,
                source_spans=spans,
                correction=formatted_verdict.correction,
                short_reason=short_reason,
            )
        )
    return AtomicVerificationPayload(
        route="hold" if converted_to_unresolved else formatted.route,
        claim_verdicts=verdicts,
        short_reason=formatted.short_reason,
    )


def _atomic_repair_from_structured_output(raw_result: Any) -> AtomicRepairPayload:
    payload = _structured_output_payload(raw_result) if raw_result is not None else {}
    return AtomicRepairPayload.model_validate(_unwrap_structured_output_mapping(payload))


def _atomic_reasoning_memo_from_raw_message(raw_result: Any) -> str:
    memo = "\n".join(_raw_message_text_blocks(raw_result)).strip()
    if not memo:
        raise ValueError("atomic_reasoning_memo_missing")
    return memo


def _atomic_reasoning_memo_artifact_from_text(memo: str) -> dict[str, Any]:
    sanitized = URL_RE.sub("[url]", memo)
    sanitized = EMAIL_RE.sub("[email]", sanitized)
    sanitized = BEARER_TOKEN_RE.sub("bearer [redacted]", sanitized)
    sanitized = CREDENTIAL_ASSIGNMENT_RE.sub("credential [redacted]", sanitized)
    sanitized = API_KEY_VALUE_RE.sub("[api-key-redacted]", sanitized)
    return {
        "memo": sanitized,
        "memo_sha256": sha256(memo.encode("utf-8")).hexdigest(),
        "memo_character_count": len(memo),
        "contract": "bounded_plain_text_decision_memo_v1",
    }


def _atomic_reasoning_memo_artifact(raw_result: Any) -> dict[str, Any] | None:
    if not isinstance(raw_result, AtomicTwoStepInvocation):
        return None
    return _atomic_reasoning_memo_artifact_from_text(raw_result.reasoning_memo)


def _atomic_invalid_output_artifact(raw_result: Any) -> dict[str, Any] | None:
    raw_message = raw_result.get("raw") if isinstance(raw_result, Mapping) else raw_result
    text = "\n".join(_raw_message_text_blocks(raw_message)).strip()
    if not text and isinstance(raw_result, Mapping):
        try:
            text = json.dumps(raw_result, ensure_ascii=False, default=str, sort_keys=True)
        except (TypeError, ValueError):
            text = ""
    if not text:
        return None
    sanitized = URL_RE.sub("[url]", text)
    sanitized = EMAIL_RE.sub("[email]", sanitized)
    sanitized = BEARER_TOKEN_RE.sub("bearer [redacted]", sanitized)
    sanitized = CREDENTIAL_ASSIGNMENT_RE.sub("credential [redacted]", sanitized)
    sanitized = API_KEY_VALUE_RE.sub("[api-key-redacted]", sanitized)
    return {
        "text": _truncate_text(sanitized, 50_000),
        "raw_text_sha256": sha256(text.encode("utf-8")).hexdigest(),
        "raw_text_character_count": len(text),
        "truncated": len(sanitized) > 50_000,
    }


def _atomic_formatter_retry_payload(exc: Exception, raw_result: Any) -> dict[str, str]:
    parsing_error = raw_result.get("parsing_error") if isinstance(raw_result, Mapping) else None
    feedback_source = parsing_error if parsing_error else exc
    return {
        "atomic_formatter_validation_feedback": _truncate_text(
            _sanitize_operator_error_text(str(feedback_source)),
            4_000,
        )
    }


def _atomic_stage_payload_for_formatter(stage_payload: Any, output_contract: str) -> Any:
    if output_contract != ATOMIC_FORMATTER_VERIFICATION_CONTRACT_VERSION:
        return stage_payload
    try:
        payload = dict(stage_payload) if isinstance(stage_payload, Mapping) else json.loads(
            str(stage_payload)
        )
    except (TypeError, ValueError):
        return stage_payload
    payload["expected_output_schema"] = AtomicFormatterVerificationPayload.model_json_schema()
    return _json_for_prompt(payload)


def _atomic_invoke_with_retry(
    runner: Any,
    payload: Mapping[str, Any],
    *,
    parser: Any,
    call_stage: str,
    provider_max_attempts: int,
    provider_retry_delay_seconds: float,
    stage_runtime_profile: Mapping[str, Any] | None = None,
) -> tuple[Any, Any, list[dict[str, Any]], int]:
    if not isinstance(runner, AtomicTwoStepRunner):
        return _atomic_invoke_single_with_retry(
            runner,
            payload,
            parser=parser,
            call_stage=call_stage,
            provider_max_attempts=provider_max_attempts,
            provider_retry_delay_seconds=provider_retry_delay_seconds,
            stage_runtime_profile=stage_runtime_profile,
        )

    reasoning_raw, reasoning_memo, reasoning_attempts, reasoning_retries = (
        _atomic_invoke_single_with_retry(
            runner.reasoning_runner,
            payload,
            parser=_atomic_reasoning_memo_from_raw_message,
            call_stage=f"{call_stage}_reasoning",
            provider_max_attempts=provider_max_attempts,
            provider_retry_delay_seconds=provider_retry_delay_seconds,
            stage_runtime_profile=runner.reasoning_runtime_profile,
        )
    )
    reasoning_attempts[-1]["reasoning_memo"] = _atomic_reasoning_memo_artifact_from_text(
        reasoning_memo
    )
    if len(payload) != 1:
        raise ValueError("atomic_two_step_payload_must_have_one_stage_variable")
    stage_payload = next(iter(payload.values()))
    formatter_payload = {
        "atomic_stage_payload": _atomic_stage_payload_for_formatter(
            stage_payload,
            runner.formatter_output_contract,
        ),
        "atomic_reasoning_memo": reasoning_memo,
        "atomic_formatter_validation_feedback": "",
    }
    formatter_parser = parser
    if runner.formatter_output_contract == ATOMIC_FORMATTER_VERIFICATION_CONTRACT_VERSION:
        formatter_parser = lambda raw: _atomic_verification_from_formatter_output(
            raw,
            stage_payload,
        )
    try:
        formatter_raw, parsed_result, formatter_attempts, formatter_retries = (
            _atomic_invoke_single_with_retry(
                runner.formatter_runner,
                formatter_payload,
                parser=formatter_parser,
                call_stage=f"{call_stage}_formatter",
                provider_max_attempts=provider_max_attempts,
                provider_retry_delay_seconds=provider_retry_delay_seconds,
                stage_runtime_profile=runner.formatter_runtime_profile,
                retry_payload_update=_atomic_formatter_retry_payload,
            )
        )
    except AtomicInvocationError as exc:
        raise AtomicInvocationError(
            str(exc),
            call_stage=exc.call_stage,
            attempt_records=[*reasoning_attempts, *exc.attempt_records],
            retry_count=reasoning_retries + exc.retry_count,
            retry_exhausted=exc.retry_exhausted,
        ) from exc
    return (
        AtomicTwoStepInvocation(
            reasoning_raw=reasoning_raw,
            reasoning_memo=reasoning_memo,
            formatter_raw=formatter_raw,
        ),
        parsed_result,
        [*reasoning_attempts, *formatter_attempts],
        reasoning_retries + formatter_retries,
    )


def _atomic_invoke_single_with_retry(
    runner: Any,
    payload: Mapping[str, Any],
    *,
    parser: Any,
    call_stage: str,
    provider_max_attempts: int,
    provider_retry_delay_seconds: float,
    stage_runtime_profile: Mapping[str, Any] | None = None,
    retry_payload_update: Any | None = None,
) -> tuple[Any, Any, list[dict[str, Any]], int]:
    attempts_used = 0
    attempt_records: list[dict[str, Any]] = []
    invoke_payload = dict(payload)
    while True:
        attempts_used += 1
        attempt_started = perf_counter()
        raw_result: Any = None
        try:
            raw_result = runner.invoke(dict(invoke_payload))
            parsed_result = parser(raw_result)
            attempt_metadata = _operator_record_runtime_metadata(
                raw_result,
                request_duration_seconds=perf_counter() - attempt_started,
                attempts_used=1,
            )
            attempt_metadata.update(
                {
                    "call_stage": call_stage,
                    "attempt_number": attempts_used,
                    "outcome": "completed",
                }
            )
            if stage_runtime_profile:
                attempt_metadata["stage_runtime_profile"] = dict(stage_runtime_profile)
                attempt_metadata["stage_runtime_profile_hash"] = _stable_json_hash(
                    dict(stage_runtime_profile)
                )
            attempt_records.append(attempt_metadata)
            return raw_result, parsed_result, attempt_records, max(attempts_used - 1, 0)
        except Exception as exc:
            effective_exc: Exception = exc
            original_failure_reason = _operator_error_reason(exc)
            error_text = _sanitize_operator_error_text(str(exc)).lower()
            if isinstance(exc, (ValidationError, ValueError)) or "structured_output_parsing_error" in error_text:
                effective_exc = RetryableOperatorOutputError(
                    f"atomic_structured_output_invalid:{type(exc).__name__}"
                )
            attempt_metadata = _operator_record_runtime_metadata(
                raw_result if raw_result is not None else getattr(exc, "llm_output", None),
                request_duration_seconds=perf_counter() - attempt_started,
                attempts_used=1,
            )
            attempt_metadata.update(
                {
                    "call_stage": call_stage,
                    "attempt_number": attempts_used,
                    "outcome": "failed",
                    "failure_reason": _operator_error_reason(effective_exc),
                }
            )
            if stage_runtime_profile:
                attempt_metadata["stage_runtime_profile"] = dict(stage_runtime_profile)
                attempt_metadata["stage_runtime_profile_hash"] = _stable_json_hash(
                    dict(stage_runtime_profile)
                )
            if effective_exc is not exc:
                attempt_metadata["output_validation_failure_reason"] = original_failure_reason
                invalid_output = _atomic_invalid_output_artifact(raw_result)
                if invalid_output is not None:
                    attempt_metadata["invalid_output"] = invalid_output
            attempt_records.append(attempt_metadata)
            should_retry = _operator_should_retry_exception(effective_exc)
            retry_limit = _operator_retry_limit_for_exception(effective_exc, provider_max_attempts)
            if should_retry and _operator_retry_allowed(
                attempts_used,
                retry_limit,
            ):
                if retry_payload_update is not None:
                    update = retry_payload_update(exc, raw_result)
                    if isinstance(update, Mapping):
                        invoke_payload.update(dict(update))
                if provider_retry_delay_seconds > 0:
                    sleep(provider_retry_delay_seconds)
                continue
            failure_reason = _operator_failure_reason_with_attempts(
                _operator_error_reason(effective_exc),
                attempts_used,
            )
            raise AtomicInvocationError(
                failure_reason,
                call_stage=call_stage,
                attempt_records=attempt_records,
                retry_count=max(attempts_used - 1, 0),
                retry_exhausted=should_retry,
            ) from exc


def _atomic_runtime_metadata(call_records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "call_count": len(call_records),
        "attempts_used": sum(_safe_int_value(item.get("attempts_used")) or 0 for item in call_records),
        "request_duration_seconds": round(
            sum(float(item.get("request_duration_seconds", 0.0) or 0.0) for item in call_records),
            3,
        ),
        "llm_usage_available": any(_bool_value(item.get("llm_usage_available", False)) for item in call_records),
    }
    for field_name in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens"):
        values = [
            _safe_int_value(item.get(field_name))
            for item in call_records
            if _safe_int_value(item.get(field_name)) is not None
        ]
        if values:
            metadata[field_name] = sum(value for value in values if value is not None)
    return metadata


def _atomic_cost_estimate(
    call_records: Sequence[Mapping[str, Any]],
    stage_runtimes: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Estimate uncached request cost from the registry price snapshot."""

    call_stage_to_runtime_stage = {
        "initial_verifier": "verifier",
        "final_verifier": "verifier",
        "initial_critic": "critic",
        "final_critic": "critic",
        "repair": "repair",
    }
    by_stage: dict[str, float] = defaultdict(float)
    priced_attempt_count = 0
    unpriced_attempt_count = 0
    unpriced_reason_counts: Counter[str] = Counter()
    for call_record in call_records:
        call_stage = str(call_record.get("call_stage", ""))
        component = "direct"
        for suffix, value in (("_reasoning", "reasoning"), ("_formatter", "formatter")):
            if call_stage.endswith(suffix):
                call_stage = call_stage[: -len(suffix)]
                component = value
                break
        runtime_stage = call_stage_to_runtime_stage.get(call_stage)
        if not runtime_stage or runtime_stage not in stage_runtimes:
            unpriced_attempt_count += 1
            unpriced_reason_counts["runtime_profile_missing"] += 1
            continue
        priced_runtime: Mapping[str, Any] = stage_runtimes[runtime_stage]
        cost_stage = runtime_stage
        if component == "formatter":
            formatter_runtime = priced_runtime.get("formatter_runtime")
            if not isinstance(formatter_runtime, Mapping):
                unpriced_attempt_count += 1
                unpriced_reason_counts["formatter_runtime_profile_missing"] += 1
                continue
            priced_runtime = formatter_runtime
            cost_stage = f"{runtime_stage}_formatter"
        elif component == "reasoning":
            cost_stage = f"{runtime_stage}_reasoning"
        pricing = priced_runtime.get("pricing_snapshot", {})
        if not isinstance(pricing, Mapping):
            unpriced_attempt_count += 1
            unpriced_reason_counts["pricing_snapshot_missing"] += 1
            continue
        input_rate = pricing.get("input_usd_per_million")
        output_rate = pricing.get("output_usd_per_million")
        input_tokens = _safe_int_value(call_record.get("input_tokens"))
        output_tokens = _safe_int_value(call_record.get("output_tokens"))
        if input_rate is None or output_rate is None:
            unpriced_attempt_count += 1
            unpriced_reason_counts["token_rate_missing"] += 1
            continue
        if input_tokens is None or output_tokens is None:
            unpriced_attempt_count += 1
            unpriced_reason_counts["usage_metadata_missing"] += 1
            continue
        cost = (
            input_tokens * float(input_rate) + output_tokens * float(output_rate)
        ) / 1_000_000
        by_stage[cost_stage] += cost
        priced_attempt_count += 1
    estimated_cost = round(sum(by_stage.values()), 8) if priced_attempt_count else None
    return {
        "estimated_uncached_cost_usd": estimated_cost,
        "estimated_uncached_cost_usd_by_stage": {
            stage: round(cost, 8) for stage, cost in sorted(by_stage.items())
        },
        "priced_attempt_count": priced_attempt_count,
        "unpriced_attempt_count": unpriced_attempt_count,
        "unpriced_reason_counts": dict(sorted(unpriced_reason_counts.items())),
        "cost_estimate_complete": priced_attempt_count > 0 and unpriced_attempt_count == 0,
        "basis": "registry_price_snapshot_full_input_rate_no_cache_discount",
    }


def _atomic_record_cost_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    estimates = [
        record.get("cost_estimate", {})
        for record in records
        if isinstance(record.get("cost_estimate"), Mapping)
    ]
    priced_costs = [
        float(estimate["estimated_uncached_cost_usd"])
        for estimate in estimates
        if estimate.get("estimated_uncached_cost_usd") is not None
    ]
    return {
        "estimated_uncached_cost_usd": (
            round(sum(priced_costs), 8) if priced_costs else None
        ),
        "cost_estimate_complete": bool(estimates)
        and all(
            _bool_value(estimate.get("cost_estimate_complete", False))
            for estimate in estimates
        ),
        "priced_record_count": len(priced_costs),
        "unpriced_record_count": len(estimates) - len(priced_costs),
        "cost_estimate_basis": (
            "registry_price_snapshot_full_input_rate_no_cache_discount"
        ),
    }


def _atomic_cumulative_output_metrics(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    metrics = {
        "record_count": len(records),
        "status_counts": _counts(str(record.get("status", "")) for record in records),
        "route_counts": _counts(str(record.get("route", "")) for record in records),
        "provider_retry_count": sum(
            _safe_int_value(record.get("provider_retry_count")) or 0
            for record in records
        ),
    }
    metrics.update(_operator_runtime_summary(records))
    metrics.update(_atomic_record_cost_summary(records))
    return metrics


def _atomic_candidate_state_from_repair(
    repair: AtomicRepairPayload,
    evidence: Mapping[str, Any],
    *,
    atomic_run_id: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
) -> dict[str, Any]:
    candidate = repair.corrected_output.model_dump(mode="json")
    candidate.update(
        {
            "task_id": str(evidence.get("task_id", "")),
            "task_scope": str(evidence.get("task_scope", "question_candidate")),
            "candidate_id": str(evidence.get("candidate_id", "")),
            "canonicalization_run_id": f"{atomic_run_id}:repair",
            "canonicalization_contract_version": CANONICALIZATION_CONTRACT_VERSION,
            "prompt_version": CANONICALIZATION_ATOMIC_REPAIR_PROMPT_VERSION,
            "runtime_contour": runtime_contour,
            "backend": backend,
            "model_id": model_id,
            "status": "completed",
            "failure_reason": "",
        }
    )
    candidate["legal_issue_frame_slug"] = _slugify(
        str(candidate.get("legal_issue_frame_slug", ""))
        or str(candidate.get("legal_issue_frame", ""))
    )
    validated = CanonicalizationResultPayload.model_validate(candidate).model_dump(mode="json")
    state = {
        **dict(evidence),
        **validated,
        "source_question_text_redacted": str(evidence.get("source_question_text_redacted", "")),
        "source_canonicalization_evidence_hash": str(evidence.get("canonicalization_evidence_hash", "")),
    }
    state["canonicalization_evidence_hash"] = _stable_json_hash(
        {
            "source_canonicalization_evidence_hash": state["source_canonicalization_evidence_hash"],
            "atomic_repair_prompt_version": CANONICALIZATION_ATOMIC_REPAIR_PROMPT_VERSION,
            "candidate": _atomic_candidate_payload(state),
        }
    )
    return state


def _atomic_changed_fields(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> list[str]:
    before_payload = _atomic_candidate_payload(before)
    after_payload = _atomic_candidate_payload(after)
    return sorted(
        field_name
        for field_name in before_payload
        if before_payload.get(field_name) != after_payload.get(field_name)
    )


def _atomic_allowed_repair_fields(controller: Mapping[str, Any]) -> set[str]:
    allowed = {
        str(item.get("field_name", ""))
        for item in controller.get("feedback", [])
        if isinstance(item, Mapping) and str(item.get("support", "")) == "unsupported"
    }
    if "legal_issue_frame" in allowed:
        allowed.add("legal_issue_frame_slug")
    return {field_name for field_name in allowed if field_name}


def _atomic_unsupported_indices_by_field(
    controller: Mapping[str, Any],
) -> dict[str, set[int]]:
    unsupported_indices: dict[str, set[int]] = defaultdict(set)
    for item in controller.get("feedback", []):
        if not isinstance(item, Mapping) or str(item.get("support", "")) != "unsupported":
            continue
        field_name = str(item.get("field_name", ""))
        field_index = _safe_int_value(item.get("field_index"))
        if field_name and field_index is not None:
            unsupported_indices[field_name].add(field_index)
    return unsupported_indices


def _atomic_apply_deterministic_list_repairs(
    candidate: Mapping[str, Any],
    before: Mapping[str, Any],
    controller: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Delete unsupported list atoms while preserving supported items exactly."""

    normalized = dict(candidate)
    normalizations: list[dict[str, Any]] = []
    unsupported_indices = _atomic_unsupported_indices_by_field(controller)
    for field_name in ("facts", "authority_context", "hidden_issues", "quality_flags"):
        removed_indices = unsupported_indices.get(field_name, set())
        if not removed_indices:
            continue
        before_items = _as_string_list(before.get(field_name, []))
        expected_items = [
            item for index, item in enumerate(before_items) if index not in removed_indices
        ]
        provided_items = _as_string_list(normalized.get(field_name, []))
        normalized[field_name] = expected_items
        normalizations.append(
            {
                "field_name": field_name,
                "unsupported_field_indices": sorted(removed_indices),
                "provided_items": provided_items,
                "normalized_items": expected_items,
                "proposal_changed": provided_items != expected_items,
            }
        )
    return normalized, normalizations


def _atomic_repair_scope_violations(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    controller: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Reject list rewrites outside the exact unsupported claim indices."""

    unsupported_indices = _atomic_unsupported_indices_by_field(controller)

    violations: list[dict[str, Any]] = []
    for field_name in ("facts", "authority_context", "hidden_issues", "quality_flags"):
        removed_indices = unsupported_indices.get(field_name, set())
        if not removed_indices:
            continue
        before_items = _as_string_list(before.get(field_name, []))
        expected_items = [
            item for index, item in enumerate(before_items) if index not in removed_indices
        ]
        actual_items = _as_string_list(after.get(field_name, []))
        if actual_items != expected_items:
            violations.append(
                {
                    "field_name": field_name,
                    "reason": "unsupported_list_items_must_be_removed_without_rewriting_supported_items",
                    "unsupported_field_indices": sorted(removed_indices),
                    "expected_items": expected_items,
                    "actual_items": actual_items,
                }
            )

    desired_indices = unsupported_indices.get("desired_outcome", set())
    if desired_indices:
        before_segments = _atomic_text_segments(before.get("desired_outcome", ""))
        actual_segments = _atomic_text_segments(after.get("desired_outcome", ""))
        supported_segments = [
            item for index, item in enumerate(before_segments) if index not in desired_indices
        ]
        supported_segment_set = set(supported_segments)
        retained_supported = [item for item in actual_segments if item in supported_segment_set]
        unsupported_originals = {
            item for index, item in enumerate(before_segments) if index in desired_indices
        }
        if retained_supported != supported_segments or unsupported_originals & set(actual_segments):
            violations.append(
                {
                    "field_name": "desired_outcome",
                    "reason": "supported_segments_must_be_preserved_and_unsupported_originals_replaced",
                    "unsupported_field_indices": sorted(desired_indices),
                    "expected_supported_segments": supported_segments,
                    "actual_segments": actual_segments,
                }
            )
    return violations


def _legacy_atomic_stage_runtime(
    *,
    stage: str,
    provider: str,
    endpoint_url: str,
    model_id: str,
    structured_output_method: str,
    max_tokens: int,
    timeout_seconds: int,
    request_parameters: Mapping[str, Any] | None,
) -> dict[str, Any]:
    parameters = dict(request_parameters or {})
    return {
        "profile_set_version": "legacy_cli_atomic_runtime_v1",
        "profile_registry_hash": "legacy_cli",
        "profile_id": f"legacy_cli:{provider}:{model_id}",
        "stage": stage,
        "provider": provider,
        "parameter_transport": (
            "anthropic_constructor" if provider == "anthropic" else "openai_extra_body"
        ),
        "endpoint_url": endpoint_url,
        "model_id": model_id,
        "reasoning_mode": "provider_default",
        "execution_mode": "direct_structured",
        "structured_output_method": structured_output_method,
        "max_tokens": max_tokens,
        "timeout_seconds": timeout_seconds,
        "temperature": 0.0 if provider == "openai" else None,
        "request_parameters": parameters,
        "request_parameters_hash": _stable_json_hash(parameters),
        "sdk_max_retries": 0,
        "pricing_snapshot": {},
    }


def _resolve_atomic_stage_runtimes(
    *,
    provider: str,
    endpoint_url: str,
    model_id: str,
    structured_output_method: str,
    timeout_seconds: int,
    verifier_max_tokens: int,
    critic_max_tokens: int,
    repair_max_tokens: int,
    extra_body: Mapping[str, Any] | None,
    runtime_profile_registry_path: str | Path | None,
    verifier_runtime_profile_id: str,
    critic_runtime_profile_id: str,
    repair_runtime_profile_id: str,
    verifier_formatter_runtime_profile_id: str,
    critic_formatter_runtime_profile_id: str,
    repair_formatter_runtime_profile_id: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    requested_profile_ids = {
        "verifier": verifier_runtime_profile_id,
        "critic": critic_runtime_profile_id,
        "repair": repair_runtime_profile_id,
    }
    requested_formatter_profile_ids = {
        "verifier": verifier_formatter_runtime_profile_id,
        "critic": critic_formatter_runtime_profile_id,
        "repair": repair_formatter_runtime_profile_id,
    }
    if any(requested_profile_ids.values()) or any(requested_formatter_profile_ids.values()):
        if not verifier_runtime_profile_id:
            raise ValueError("verifier_runtime_profile_id is required in registry profile mode")
        registry, registry_hash, _registry_path = load_atomic_runtime_profile_registry(
            runtime_profile_registry_path
        )
        effective_ids = {
            "verifier": verifier_runtime_profile_id,
            "critic": critic_runtime_profile_id or verifier_runtime_profile_id,
            "repair": repair_runtime_profile_id or verifier_runtime_profile_id,
        }
        stage_runtimes = {
            stage: resolve_atomic_runtime_stage(
                registry,
                profile_id=profile_id,
                stage=stage,  # type: ignore[arg-type]
                registry_hash=registry_hash,
            )
            for stage, profile_id in effective_ids.items()
        }
        for stage, stage_runtime in stage_runtimes.items():
            stage_runtime["execution_mode"] = "direct_structured"
            formatter_profile_id = requested_formatter_profile_ids[stage]
            if not formatter_profile_id:
                continue
            formatter_runtime = resolve_atomic_runtime_stage(
                registry,
                profile_id=formatter_profile_id,
                stage=stage,  # type: ignore[arg-type]
                registry_hash=registry_hash,
            )
            if str(formatter_runtime.get("reasoning_mode", "")) != "disabled":
                raise ValueError(
                    f"{stage}_formatter_runtime_profile_id must declare reasoning_mode=disabled"
                )
            stage_runtime["execution_mode"] = "reasoning_then_formatter"
            stage_runtime["formatter_runtime"] = formatter_runtime
            stage_runtime["formatter_output_contract"] = (
                ATOMIC_FORMATTER_VERIFICATION_CONTRACT_VERSION
                if stage in {"verifier", "critic"}
                else "final_schema"
            )
        return stage_runtimes, {
            "mode": "registry",
            "profile_set_version": registry.profile_set_version,
            "profile_registry_hash": registry_hash,
            "profile_registry_path": str(
                runtime_profile_registry_path
                or Path(
                    "src/evaluation/runtime_profiles/"
                    "tg_question_canonicalization_atomic_models_v2.json"
                )
            ),
            "formatter_profile_ids": {
                stage: profile_id
                for stage, profile_id in requested_formatter_profile_ids.items()
                if profile_id
            },
        }

    if not endpoint_url or not model_id:
        raise ValueError(
            "endpoint_url and model_id are required unless verifier_runtime_profile_id is set"
        )
    stage_runtimes = {
        "verifier": _legacy_atomic_stage_runtime(
            stage="verifier",
            provider=provider,
            endpoint_url=endpoint_url,
            model_id=model_id,
            structured_output_method=structured_output_method,
            max_tokens=verifier_max_tokens,
            timeout_seconds=timeout_seconds,
            request_parameters=extra_body,
        ),
        "critic": _legacy_atomic_stage_runtime(
            stage="critic",
            provider=provider,
            endpoint_url=endpoint_url,
            model_id=model_id,
            structured_output_method=structured_output_method,
            max_tokens=critic_max_tokens,
            timeout_seconds=timeout_seconds,
            request_parameters=extra_body,
        ),
        "repair": _legacy_atomic_stage_runtime(
            stage="repair",
            provider=provider,
            endpoint_url=endpoint_url,
            model_id=model_id,
            structured_output_method=structured_output_method,
            max_tokens=repair_max_tokens,
            timeout_seconds=timeout_seconds,
            request_parameters=extra_body,
        ),
    }
    return stage_runtimes, {
        "mode": "legacy_cli",
        "profile_set_version": "legacy_cli_atomic_runtime_v1",
        "profile_registry_hash": "legacy_cli",
        "profile_registry_path": "",
    }


def _atomic_stage_runtime_identity(stage_runtime: Mapping[str, Any]) -> dict[str, Any]:
    """Return the secret-free effective request profile persisted with a run."""

    identity = {
        key: value
        for key, value in {
            **dict(stage_runtime),
            "endpoint_shape": _redacted_endpoint_shape(str(stage_runtime.get("endpoint_url", ""))),
        }.items()
        if key not in {"endpoint_url", "pricing_snapshot", "formatter_runtime"}
    }
    formatter_runtime = stage_runtime.get("formatter_runtime")
    if isinstance(formatter_runtime, Mapping):
        identity["formatter_runtime"] = _atomic_stage_runtime_identity(formatter_runtime)
    return identity


def _atomic_component_runtime_identity(
    stage_runtime: Mapping[str, Any],
    *,
    component_role: str,
) -> dict[str, Any]:
    component_runtime = {
        key: value for key, value in stage_runtime.items() if key != "formatter_runtime"
    }
    identity = _atomic_stage_runtime_identity(component_runtime)
    identity["component_role"] = component_role
    return identity


def _atomic_pricing_snapshot_for_artifact(stage_runtime: Mapping[str, Any]) -> dict[str, Any]:
    pricing = stage_runtime.get("pricing_snapshot", {})
    if not isinstance(pricing, Mapping):
        return {}
    artifact = {key: value for key, value in pricing.items() if key != "source"}
    formatter_runtime = stage_runtime.get("formatter_runtime")
    if isinstance(formatter_runtime, Mapping):
        formatter_pricing = formatter_runtime.get("pricing_snapshot", {})
        artifact = {"reasoning": artifact}
        if isinstance(formatter_pricing, Mapping):
            artifact["formatter"] = {
                key: value for key, value in formatter_pricing.items() if key != "source"
            }
    return artifact


def _atomic_should_run_critic(
    *,
    enable_critic: bool,
    critic_policy: str,
    primary_controller: Mapping[str, Any],
) -> bool:
    if not enable_critic:
        return False
    if critic_policy == "always":
        return True
    return str(primary_controller.get("route", "hold")) == "pass"


def _atomic_sidecar_base(
    evidence: Mapping[str, Any],
    *,
    atomic_run_id: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
) -> dict[str, Any]:
    return {
        "artifact_type": "tg_qa_canonicalization_atomic_verify_repair_record",
        "task_id": str(evidence.get("task_id", "")),
        "candidate_id": str(evidence.get("candidate_id", "")),
        "canonicalization_evidence_id": str(evidence.get("canonicalization_evidence_id", "")),
        "canonicalization_evidence_hash": str(evidence.get("canonicalization_evidence_hash", "")),
        "atomic_run_id": atomic_run_id,
        "atomic_controller_policy_version": CANONICALIZATION_ATOMIC_CONTROLLER_POLICY_VERSION,
        "atomic_verifier_prompt_version": CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_VERSION,
        "atomic_critic_prompt_version": CANONICALIZATION_ATOMIC_CRITIC_PROMPT_VERSION,
        "atomic_repair_prompt_version": CANONICALIZATION_ATOMIC_REPAIR_PROMPT_VERSION,
        "runtime_contour": runtime_contour,
        "backend": backend,
        "model_id": model_id,
        "status": "completed",
        "failure_reason": "",
        "route": "hold",
        "repair_attempted": False,
        "trust_boundary": "atomic_verification_and_repair_are_review_evidence_only",
    }


def _write_atomic_stage_checkpoint(
    checkpoint_path: str | Path,
    *,
    stage: str,
    evidence: Mapping[str, Any],
    atomic_run_id: str,
    runtime_profile: Mapping[str, Any],
    record: Mapping[str, Any],
    call_records: Sequence[Mapping[str, Any]],
    provider_retry_count: int,
) -> dict[str, Any]:
    checkpoint = {
        "artifact_type": "tg_qa_canonicalization_atomic_stage_checkpoint",
        "updated_at": _utc_timestamp(),
        "stage": stage,
        "task_id": str(evidence.get("task_id", "")),
        "canonicalization_evidence_hash": str(evidence.get("canonicalization_evidence_hash", "")),
        "atomic_run_id": atomic_run_id,
        "runtime_profile_hash": _stable_json_hash(dict(runtime_profile)),
        "record": dict(record),
        "stage_runtime": [dict(item) for item in call_records],
        "provider_retry_count": provider_retry_count,
        "trust_boundary": "atomic_stage_checkpoint_is_private_review_evidence_only",
    }
    _ensure_public_payload(checkpoint)
    _write_json(checkpoint_path, checkpoint)
    return checkpoint


def _load_atomic_stage_checkpoint(
    checkpoint_path: str | Path,
    *,
    evidence: Mapping[str, Any],
    atomic_run_id: str,
    runtime_profile: Mapping[str, Any],
) -> dict[str, Any]:
    path = Path(checkpoint_path)
    if not path.exists():
        return {}
    try:
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_atomic_stage_checkpoint") from exc
    if not isinstance(checkpoint, Mapping):
        raise ValueError("invalid_atomic_stage_checkpoint_shape")
    if str(checkpoint.get("task_id", "")) != str(evidence.get("task_id", "")):
        return {}
    if str(checkpoint.get("stage", "")) not in {
        "initial_verified",
        "repair_completed",
        "final_primary_verified",
    }:
        return {}
    expected_identity = {
        "canonicalization_evidence_hash": str(evidence.get("canonicalization_evidence_hash", "")),
        "atomic_run_id": atomic_run_id,
        "runtime_profile_hash": _stable_json_hash(dict(runtime_profile)),
    }
    for field_name, expected_value in expected_identity.items():
        if str(checkpoint.get(field_name, "")) != expected_value:
            raise ValueError(f"atomic_stage_checkpoint_identity_mismatch:{field_name}")
    record = checkpoint.get("record", {})
    call_records = checkpoint.get("stage_runtime", [])
    if not isinstance(record, Mapping) or not isinstance(call_records, list):
        raise ValueError("invalid_atomic_stage_checkpoint_state")
    return dict(checkpoint)


def run_tg_qa_canonicalization_atomic_verify_repair_batch(
    *,
    evidence_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    atomic_run_id: str,
    endpoint_url: str = "",
    model_id: str = "",
    provider: str = "openai",
    max_items: int = 0,
    timeout_seconds: int = 300,
    verifier_max_tokens: int = 32768,
    critic_max_tokens: int = 32768,
    repair_max_tokens: int = 16384,
    max_repairs: int = 1,
    enable_critic: bool = False,
    critic_policy: str = "always",
    structured_output_method: str = "json_schema",
    api_key_env: str = "",
    extra_body: Mapping[str, Any] | None = None,
    runtime_profile_registry_path: str | Path | None = None,
    verifier_runtime_profile_id: str = "",
    critic_runtime_profile_id: str = "",
    repair_runtime_profile_id: str = "",
    verifier_formatter_runtime_profile_id: str = "",
    critic_formatter_runtime_profile_id: str = "",
    repair_formatter_runtime_profile_id: str = "",
    stop_on_failure: bool = False,
    runtime_contour: str = "operator_managed_atomic_verify_repair",
    backend: str = "opencode",
    resume: bool = True,
    provider_max_attempts: int = 3,
    provider_retry_delay_seconds: float = 2.0,
    progress: bool = False,
    checkpoint_output_path: str | Path | None = None,
    stage_checkpoint_output_path: str | Path | None = None,
    run_bundle_output_path: str | Path | None = None,
    log_path: str = "",
    verifier_chain: Any | None = None,
    critic_chain: Any | None = None,
    repair_chain: Any | None = None,
) -> dict[str, Any]:
    """Run independent atomic verification with at most one semantic repair."""

    if provider not in {"anthropic", "openai"}:
        raise ValueError("provider must be anthropic or openai")
    if structured_output_method not in {"function_calling", "json_mode", "json_schema"}:
        raise ValueError("structured_output_method must be function_calling, json_mode, or json_schema")
    if max_repairs not in {0, 1}:
        raise ValueError("max_repairs must be zero or one")
    if critic_policy not in {"always", "before_pass"}:
        raise ValueError("critic_policy must be always or before_pass")
    if provider_max_attempts < 0:
        raise ValueError("provider_max_attempts must be non-negative")
    if provider_retry_delay_seconds < 0:
        raise ValueError("provider_retry_delay_seconds must be non-negative")

    stage_runtimes, runtime_profile_registry = _resolve_atomic_stage_runtimes(
        provider=provider,
        endpoint_url=endpoint_url,
        model_id=model_id,
        structured_output_method=structured_output_method,
        timeout_seconds=timeout_seconds,
        verifier_max_tokens=verifier_max_tokens,
        critic_max_tokens=critic_max_tokens,
        repair_max_tokens=repair_max_tokens,
        extra_body=extra_body,
        runtime_profile_registry_path=runtime_profile_registry_path,
        verifier_runtime_profile_id=verifier_runtime_profile_id,
        critic_runtime_profile_id=critic_runtime_profile_id,
        repair_runtime_profile_id=repair_runtime_profile_id,
        verifier_formatter_runtime_profile_id=verifier_formatter_runtime_profile_id,
        critic_formatter_runtime_profile_id=critic_formatter_runtime_profile_id,
        repair_formatter_runtime_profile_id=repair_formatter_runtime_profile_id,
    )
    verifier_runtime = stage_runtimes["verifier"]
    critic_runtime = stage_runtimes["critic"]
    repair_runtime = stage_runtimes["repair"]
    active_stage_runtime_profiles = {
        "verifier": _atomic_stage_runtime_identity(verifier_runtime),
    }
    if enable_critic:
        active_stage_runtime_profiles["critic"] = _atomic_stage_runtime_identity(critic_runtime)
    if max_repairs:
        active_stage_runtime_profiles["repair"] = _atomic_stage_runtime_identity(repair_runtime)

    evidence_records = _read_jsonl(evidence_path)
    input_batch_hash = _operator_input_batch_hash(
        evidence_records,
        identity_field="canonicalization_evidence_hash",
    )
    verifier_profile_hash = _canonicalization_prompt_profile_hash(
        CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_VERSION
    )
    critic_profile_hash = _canonicalization_prompt_profile_hash(
        CANONICALIZATION_ATOMIC_CRITIC_PROMPT_VERSION
    )
    repair_profile_hash = _canonicalization_prompt_profile_hash(
        CANONICALIZATION_ATOMIC_REPAIR_PROMPT_VERSION
    )
    verifier_output_schema_hash = _stable_json_hash(AtomicVerificationPayload.model_json_schema())
    critic_output_schema_hash = verifier_output_schema_hash
    repair_output_schema_hash = _stable_json_hash(AtomicRepairPayload.model_json_schema())
    formatter_output_schema_hashes = {
        stage: _stable_json_hash(
            (
                AtomicFormatterVerificationPayload
                if stage in {"verifier", "critic"}
                else AtomicRepairPayload
            ).model_json_schema()
        )
        for stage in active_stage_runtime_profiles
        if isinstance(stage_runtimes[stage].get("formatter_runtime"), Mapping)
    }
    combined_prompt_versions = [CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_VERSION]
    if enable_critic:
        combined_prompt_versions.append(CANONICALIZATION_ATOMIC_CRITIC_PROMPT_VERSION)
    if max_repairs:
        combined_prompt_versions.append(CANONICALIZATION_ATOMIC_REPAIR_PROMPT_VERSION)
    combined_prompt_version = "+".join(combined_prompt_versions)
    active_component_runtimes: list[Mapping[str, Any]] = []
    for stage in active_stage_runtime_profiles:
        stage_runtime = stage_runtimes[stage]
        active_component_runtimes.append(stage_runtime)
        formatter_runtime = stage_runtime.get("formatter_runtime")
        if isinstance(formatter_runtime, Mapping):
            active_component_runtimes.append(formatter_runtime)
    active_max_tokens = [int(runtime["max_tokens"]) for runtime in active_component_runtimes]
    runtime_profile = _operator_runtime_profile(
        stage="atomic_verify_repair",
        prompt_version=combined_prompt_version,
        prompt_profile_hash=_stable_json_hash(
            {
                "verifier": verifier_profile_hash,
                "critic": critic_profile_hash if enable_critic else "disabled",
                "repair": repair_profile_hash if max_repairs else "disabled",
                "controller": CANONICALIZATION_ATOMIC_CONTROLLER_POLICY_VERSION,
                "enable_critic": enable_critic,
                "critic_policy": critic_policy,
                "max_repairs": max_repairs,
                "verifier_max_tokens": verifier_runtime["max_tokens"],
                "critic_max_tokens": critic_runtime["max_tokens"] if enable_critic else 0,
                "repair_max_tokens": repair_runtime["max_tokens"] if max_repairs else 0,
            }
        ),
        provider=str(verifier_runtime["provider"]),
        runtime_contour=runtime_contour,
        backend=backend,
        model_id=str(verifier_runtime["model_id"]),
        structured_output_method=str(verifier_runtime["structured_output_method"]),
        max_tokens=max(active_max_tokens),
        timeout_seconds=max(int(runtime["timeout_seconds"]) for runtime in active_component_runtimes),
        extra_body=verifier_runtime["request_parameters"],
        input_batch_hash=input_batch_hash,
    )
    runtime_profile["runtime_profile_registry"] = runtime_profile_registry
    runtime_profile["stage_runtime_profiles"] = active_stage_runtime_profiles
    runtime_profile["verifier_output_schema_hash"] = verifier_output_schema_hash
    runtime_profile["critic_output_schema_hash"] = (
        critic_output_schema_hash if enable_critic else "disabled"
    )
    runtime_profile["repair_output_schema_hash"] = (
        repair_output_schema_hash if max_repairs else "disabled"
    )
    runtime_profile["formatter_output_schema_hashes"] = formatter_output_schema_hashes
    resume_state = (
        _load_existing_operator_results(
            output_path,
            evidence_records,
            stage="atomic_verify_repair",
            runtime_profile=runtime_profile,
            input_identity_field="canonicalization_evidence_hash",
        )
        if resume
        else _empty_operator_resume_state()
    )
    remaining_records = [
        evidence
        for evidence in evidence_records
        if str(evidence.get("task_id", "")) not in resume_state["processed_task_ids"]
    ]
    selected_records = remaining_records[:max_items] if max_items > 0 else remaining_records
    missing_source_task_ids = [
        str(evidence.get("task_id", "")) or "<missing-task-id>"
        for evidence in selected_records
        if str(evidence.get("status", "")) == "completed"
        and not str(evidence.get("source_question_text_redacted", "")).strip()
    ]
    if missing_source_task_ids:
        preview = ", ".join(missing_source_task_ids[:10])
        suffix = " ..." if len(missing_source_task_ids) > 10 else ""
        raise ValueError(
            "atomic verification requires imported evidence with non-empty "
            f"source_question_text_redacted; missing for: {preview}{suffix}"
        )
    verifier_runner = verifier_chain or _build_atomic_runner_for_stage(
        stage="verifier",
        stage_runtime=verifier_runtime,
        api_key_env=api_key_env,
    )
    critic_runner = None
    if enable_critic:
        critic_runner = critic_chain or _build_atomic_runner_for_stage(
            stage="critic",
            stage_runtime=critic_runtime,
            api_key_env=api_key_env,
        )
    repair_runner = None
    if max_repairs:
        repair_runner = repair_chain or _build_atomic_runner_for_stage(
            stage="repair",
            stage_runtime=repair_runtime,
            api_key_env=api_key_env,
        )

    started_at = _utc_timestamp()
    started = perf_counter()
    counts = Counter()
    records: list[dict[str, Any]] = []
    checkpoint_path = Path(checkpoint_output_path or _operator_artifact_path(summary_output_path, "checkpoint"))
    stage_checkpoint_path = Path(
        stage_checkpoint_output_path or _operator_artifact_path(summary_output_path, "stage_checkpoint")
    )
    bundle_path = Path(run_bundle_output_path or _operator_artifact_path(summary_output_path, "run_bundle"))
    checkpoint_task_ids = set(resume_state["processed_task_ids"])
    checkpoint_status_counts: Counter[str] = Counter(resume_state["status_counts"])
    progress_line = _OperatorProgress(
        enabled=progress,
        label="tg-qa-canonicalization-atomic-verify-repair-run",
        total=len(selected_records),
    )
    output_handle = _open_jsonl_stream(
        output_path,
        append=resume and bool(resume_state["processed_task_ids"]),
    )
    try:
        for item_index, evidence in enumerate(selected_records, start=1):
            counts["processed"] += 1
            progress_line.update(
                item_index - 1,
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                skipped=counts.get("skipped", 0),
                last_status="request",
                detail=_operator_progress_detail("request", item_index, len(selected_records), evidence),
            )
            record = _atomic_sidecar_base(
                evidence,
                atomic_run_id=atomic_run_id,
                runtime_contour=runtime_contour,
                backend=backend,
                model_id=str(verifier_runtime["model_id"]),
            )
            record["atomic_critic_enabled"] = enable_critic
            record["atomic_critic_policy"] = critic_policy
            record["atomic_repair_enabled"] = bool(max_repairs)
            record["stage_runtime_profiles"] = active_stage_runtime_profiles
            record["stage_pricing_snapshots"] = {
                stage: _atomic_pricing_snapshot_for_artifact(stage_runtimes[stage])
                for stage in active_stage_runtime_profiles
            }
            call_records: list[dict[str, Any]] = []
            provider_retry_count = 0
            resumed_stage = ""
            if str(evidence.get("status", "")) != "completed":
                record.update(
                    {
                        "status": "skipped",
                        "failure_reason": str(evidence.get("failure_reason", ""))
                        or "non_completed_canonicalization_evidence",
                    }
                )
            else:
                try:
                    initial_ledger = build_canonicalization_atomic_claim_ledger(evidence)
                    stage_checkpoint = (
                        _load_atomic_stage_checkpoint(
                            stage_checkpoint_path,
                            evidence=evidence,
                            atomic_run_id=atomic_run_id,
                            runtime_profile=runtime_profile,
                        )
                        if resume
                        else {}
                    )
                    if stage_checkpoint:
                        resumed_stage = str(stage_checkpoint["stage"])
                        checkpoint_record = stage_checkpoint.get("record", {})
                        record.update(dict(checkpoint_record))
                        call_records = [
                            dict(item)
                            for item in stage_checkpoint.get("stage_runtime", [])
                            if isinstance(item, Mapping)
                        ]
                        provider_retry_count = _safe_int_value(
                            stage_checkpoint.get("provider_retry_count")
                        ) or 0
                        stored_ledger = record.get("initial_claim_ledger", {})
                        if not isinstance(stored_ledger, Mapping) or str(
                            stored_ledger.get("claim_ledger_hash", "")
                        ) != str(initial_ledger.get("claim_ledger_hash", "")):
                            raise ValueError("atomic_stage_checkpoint_initial_ledger_mismatch")
                        initial_verification = AtomicVerificationPayload.model_validate(
                            record.get("initial_verification", {})
                        )
                        initial_effective_verification = AtomicVerificationPayload.model_validate(
                            record.get("initial_combined_verification", record.get("initial_verification", {}))
                        )
                        initial_critic_merge = record.get("initial_critic_merge", {})
                        initial_primary_controller = canonicalization_atomic_verification_controller(
                            initial_verification,
                            initial_ledger,
                            str(evidence.get("source_question_text_redacted", "")),
                        )
                        initial_critic_executed = _bool_value(
                            record.get("initial_critic_executed", bool(initial_critic_merge))
                        )
                        record["resumed_stage_checkpoint"] = resumed_stage
                    else:
                        initial_payload = compact_canonicalization_atomic_verifier_payload(
                            evidence,
                            initial_ledger,
                        )
                        initial_raw, initial_verification, initial_attempts, retries = _atomic_invoke_with_retry(
                            verifier_runner,
                            {
                                "atomic_verifier_payload": _json_for_prompt(initial_payload),
                            },
                            parser=_atomic_verification_from_structured_output,
                            call_stage="initial_verifier",
                            provider_max_attempts=provider_max_attempts,
                            provider_retry_delay_seconds=provider_retry_delay_seconds,
                            stage_runtime_profile=active_stage_runtime_profiles["verifier"],
                        )
                        provider_retry_count += retries
                        call_records.extend(initial_attempts)
                        initial_reasoning_memo = _atomic_reasoning_memo_artifact(initial_raw)
                        if initial_reasoning_memo is not None:
                            record["initial_verifier_reasoning_memo"] = initial_reasoning_memo
                        initial_effective_verification = initial_verification
                        initial_critic_merge: Mapping[str, Any] = {}
                        initial_primary_controller = canonicalization_atomic_verification_controller(
                            initial_verification,
                            initial_ledger,
                            str(evidence.get("source_question_text_redacted", "")),
                        )
                        initial_critic_executed = _atomic_should_run_critic(
                            enable_critic=enable_critic,
                            critic_policy=critic_policy,
                            primary_controller=initial_primary_controller,
                        )
                        if initial_critic_executed:
                            assert critic_runner is not None
                            initial_critic_payload = compact_canonicalization_atomic_critic_payload(
                                evidence,
                                initial_ledger,
                                initial_verification,
                            )
                            initial_critic_ledger = initial_critic_payload["critic_claim_ledger"]
                            (
                                initial_critic_raw,
                                initial_critic_verification,
                                initial_critic_attempts,
                                retries,
                            ) = _atomic_invoke_with_retry(
                                critic_runner,
                                {
                                    "atomic_critic_payload": _json_for_prompt(initial_critic_payload),
                                },
                                parser=_atomic_verification_from_structured_output,
                                call_stage="initial_critic",
                                provider_max_attempts=provider_max_attempts,
                                provider_retry_delay_seconds=provider_retry_delay_seconds,
                                stage_runtime_profile=active_stage_runtime_profiles["critic"],
                            )
                            provider_retry_count += retries
                            call_records.extend(initial_critic_attempts)
                            initial_critic_reasoning_memo = _atomic_reasoning_memo_artifact(
                                initial_critic_raw
                            )
                            if initial_critic_reasoning_memo is not None:
                                record["initial_critic_reasoning_memo"] = (
                                    initial_critic_reasoning_memo
                                )
                            initial_critic_merge = merge_canonicalization_atomic_verifier_critic(
                                initial_verification,
                                initial_critic_verification,
                                initial_ledger,
                                initial_critic_ledger,
                                str(evidence.get("source_question_text_redacted", "")),
                            )
                            initial_effective_verification = AtomicVerificationPayload.model_validate(
                                initial_critic_merge["combined_verification"]
                            )
                            record.update(
                                {
                                    "initial_critic_claim_ledger": initial_critic_ledger,
                                    "initial_critic_verification": initial_critic_verification.model_dump(
                                        mode="json"
                                    ),
                                    "initial_critic_merge": initial_critic_merge,
                                    "initial_combined_verification": initial_effective_verification.model_dump(
                                        mode="json"
                                    ),
                                }
                            )
                        elif enable_critic:
                            record["initial_critic_skipped_reason"] = (
                                "primary_route_nonpass_under_before_pass_policy"
                            )
                    initial_controller = canonicalization_atomic_verification_controller(
                        initial_effective_verification,
                        initial_ledger,
                        str(evidence.get("source_question_text_redacted", "")),
                    )
                    if initial_critic_executed and not _bool_value(
                        initial_critic_merge.get("merge_valid", False)
                    ):
                        initial_controller["route"] = "hold"
                        initial_controller["reason_codes"] = sorted(
                            set(initial_controller.get("reason_codes", []))
                            | {"critic_structural_invalid"}
                            | set(initial_critic_merge.get("structural_reason_codes", []))
                        )
                    record.update(
                        {
                            "initial_claim_ledger": initial_ledger,
                            "initial_verification": initial_verification.model_dump(mode="json"),
                            "initial_primary_controller": initial_primary_controller,
                            "initial_critic_executed": initial_critic_executed,
                            "initial_controller": initial_controller,
                        }
                    )
                    route = str(initial_controller["route"])
                    if route == "pass":
                        record["route"] = "pass"
                    elif route == "hold" or max_repairs == 0:
                        record["route"] = "hold"
                        if route == "revise" and max_repairs == 0:
                            record["hold_reason_codes"] = ["semantic_repair_disabled"]
                    else:
                        assert repair_runner is not None
                        record["repair_attempted"] = True
                        if resumed_stage in {"repair_completed", "final_primary_verified"}:
                            repair = AtomicRepairPayload.model_validate(record.get("repair", {}))
                        else:
                            _write_atomic_stage_checkpoint(
                                stage_checkpoint_path,
                                stage="initial_verified",
                                evidence=evidence,
                                atomic_run_id=atomic_run_id,
                                runtime_profile=runtime_profile,
                                record=record,
                                call_records=call_records,
                                provider_retry_count=provider_retry_count,
                            )
                            repair_payload = compact_canonicalization_atomic_repair_payload(
                                evidence,
                                initial_controller,
                            )
                            repair_raw, repair, repair_attempts, retries = _atomic_invoke_with_retry(
                                repair_runner,
                                {
                                    "atomic_repair_payload": _json_for_prompt(repair_payload),
                                },
                                parser=_atomic_repair_from_structured_output,
                                call_stage="repair",
                                provider_max_attempts=provider_max_attempts,
                                provider_retry_delay_seconds=provider_retry_delay_seconds,
                                stage_runtime_profile=active_stage_runtime_profiles["repair"],
                            )
                            provider_retry_count += retries
                            call_records.extend(repair_attempts)
                            repair_reasoning_memo = _atomic_reasoning_memo_artifact(repair_raw)
                            if repair_reasoning_memo is not None:
                                record["repair_reasoning_memo"] = repair_reasoning_memo
                        normalized_repair_candidate, deterministic_list_repairs = (
                            _atomic_apply_deterministic_list_repairs(
                                repair.corrected_output.model_dump(mode="json"),
                                evidence,
                                initial_controller,
                            )
                        )
                        normalized_repair = repair.model_copy(
                            update={
                                "corrected_output": CanonicalizationResultPayload.model_validate(
                                    normalized_repair_candidate
                                )
                            }
                        )
                        repaired_state = _atomic_candidate_state_from_repair(
                            normalized_repair,
                            evidence,
                            atomic_run_id=atomic_run_id,
                            runtime_contour=runtime_contour,
                            backend=backend,
                            model_id=str(repair_runtime["model_id"]),
                        )
                        changed_fields = _atomic_changed_fields(evidence, repaired_state)
                        allowed_fields = _atomic_allowed_repair_fields(initial_controller)
                        unauthorized_fields = sorted(set(changed_fields) - allowed_fields)
                        expected_repair_ids = set(initial_controller.get("unsupported_claim_ids", []))
                        missing_repair_ids = sorted(expected_repair_ids - set(repair.repaired_claim_ids))
                        repair_scope_violations = _atomic_repair_scope_violations(
                            evidence,
                            repaired_state,
                            initial_controller,
                        )
                        record.update(
                            {
                                "repair": repair.model_dump(mode="json"),
                                "deterministic_list_repairs": deterministic_list_repairs,
                                "repaired_candidate": _atomic_candidate_payload(repaired_state),
                                "changed_fields": changed_fields,
                                "allowed_repair_fields": sorted(allowed_fields),
                                "unauthorized_changed_fields": unauthorized_fields,
                                "missing_repaired_claim_ids": missing_repair_ids,
                                "repair_scope_violations": repair_scope_violations,
                            }
                        )
                        if unauthorized_fields or missing_repair_ids or repair_scope_violations:
                            record["route"] = "hold"
                            hold_reasons: list[str] = []
                            if unauthorized_fields:
                                hold_reasons.append("repair_changed_unauthorized_fields")
                            if missing_repair_ids:
                                hold_reasons.append("repair_claim_ids_incomplete")
                            if repair_scope_violations:
                                hold_reasons.append("repair_violated_claim_scope")
                            record["hold_reason_codes"] = hold_reasons
                        else:
                            if resumed_stage != "final_primary_verified":
                                _write_atomic_stage_checkpoint(
                                    stage_checkpoint_path,
                                    stage="repair_completed",
                                    evidence=evidence,
                                    atomic_run_id=atomic_run_id,
                                    runtime_profile=runtime_profile,
                                    record=record,
                                    call_records=call_records,
                                    provider_retry_count=provider_retry_count,
                                )
                            final_ledger = build_canonicalization_atomic_claim_ledger(repaired_state)
                            if resumed_stage == "final_primary_verified":
                                stored_final_ledger = record.get("final_claim_ledger", {})
                                if not isinstance(stored_final_ledger, Mapping) or str(
                                    stored_final_ledger.get("claim_ledger_hash", "")
                                ) != str(final_ledger.get("claim_ledger_hash", "")):
                                    raise ValueError("atomic_stage_checkpoint_final_ledger_mismatch")
                                final_verification = AtomicVerificationPayload.model_validate(
                                    record.get("final_verification", {})
                                )
                            else:
                                final_payload = compact_canonicalization_atomic_verifier_payload(
                                    repaired_state,
                                    final_ledger,
                                )
                                (
                                    final_raw,
                                    final_verification,
                                    final_attempts,
                                    retries,
                                ) = _atomic_invoke_with_retry(
                                    verifier_runner,
                                    {
                                        "atomic_verifier_payload": _json_for_prompt(final_payload),
                                    },
                                    parser=_atomic_verification_from_structured_output,
                                    call_stage="final_verifier",
                                    provider_max_attempts=provider_max_attempts,
                                    provider_retry_delay_seconds=provider_retry_delay_seconds,
                                    stage_runtime_profile=active_stage_runtime_profiles["verifier"],
                                )
                                provider_retry_count += retries
                                call_records.extend(final_attempts)
                                final_reasoning_memo = _atomic_reasoning_memo_artifact(final_raw)
                                if final_reasoning_memo is not None:
                                    record["final_verifier_reasoning_memo"] = final_reasoning_memo
                                record.update(
                                    {
                                        "final_claim_ledger": final_ledger,
                                        "final_verification": final_verification.model_dump(mode="json"),
                                    }
                                )
                            final_primary_controller = canonicalization_atomic_verification_controller(
                                final_verification,
                                final_ledger,
                                str(repaired_state.get("source_question_text_redacted", "")),
                            )
                            final_critic_executed = _atomic_should_run_critic(
                                enable_critic=enable_critic,
                                critic_policy=critic_policy,
                                primary_controller=final_primary_controller,
                            )
                            record.update(
                                {
                                    "final_primary_controller": final_primary_controller,
                                    "final_critic_executed": final_critic_executed,
                                }
                            )
                            if final_critic_executed and resumed_stage != "final_primary_verified":
                                _write_atomic_stage_checkpoint(
                                    stage_checkpoint_path,
                                    stage="final_primary_verified",
                                    evidence=evidence,
                                    atomic_run_id=atomic_run_id,
                                    runtime_profile=runtime_profile,
                                    record=record,
                                    call_records=call_records,
                                    provider_retry_count=provider_retry_count,
                                )
                            final_effective_verification = final_verification
                            final_critic_merge: Mapping[str, Any] = {}
                            if final_critic_executed:
                                assert critic_runner is not None
                                final_critic_payload = compact_canonicalization_atomic_critic_payload(
                                    repaired_state,
                                    final_ledger,
                                    final_verification,
                                )
                                final_critic_ledger = final_critic_payload["critic_claim_ledger"]
                                (
                                    final_critic_raw,
                                    final_critic_verification,
                                    final_critic_attempts,
                                    retries,
                                ) = _atomic_invoke_with_retry(
                                    critic_runner,
                                    {
                                        "atomic_critic_payload": _json_for_prompt(final_critic_payload),
                                    },
                                    parser=_atomic_verification_from_structured_output,
                                    call_stage="final_critic",
                                    provider_max_attempts=provider_max_attempts,
                                    provider_retry_delay_seconds=provider_retry_delay_seconds,
                                    stage_runtime_profile=active_stage_runtime_profiles["critic"],
                                )
                                provider_retry_count += retries
                                call_records.extend(final_critic_attempts)
                                final_critic_reasoning_memo = _atomic_reasoning_memo_artifact(
                                    final_critic_raw
                                )
                                if final_critic_reasoning_memo is not None:
                                    record["final_critic_reasoning_memo"] = (
                                        final_critic_reasoning_memo
                                    )
                                final_critic_merge = merge_canonicalization_atomic_verifier_critic(
                                    final_verification,
                                    final_critic_verification,
                                    final_ledger,
                                    final_critic_ledger,
                                    str(repaired_state.get("source_question_text_redacted", "")),
                                )
                                final_effective_verification = AtomicVerificationPayload.model_validate(
                                    final_critic_merge["combined_verification"]
                                )
                                record.update(
                                    {
                                        "final_critic_claim_ledger": final_critic_ledger,
                                        "final_critic_verification": final_critic_verification.model_dump(
                                            mode="json"
                                        ),
                                        "final_critic_merge": final_critic_merge,
                                        "final_combined_verification": final_effective_verification.model_dump(
                                            mode="json"
                                        ),
                                    }
                                )
                            elif enable_critic:
                                record["final_critic_skipped_reason"] = (
                                    "primary_route_nonpass_under_before_pass_policy"
                                )
                            final_controller = canonicalization_atomic_verification_controller(
                                final_effective_verification,
                                final_ledger,
                                str(repaired_state.get("source_question_text_redacted", "")),
                            )
                            if final_critic_executed and not _bool_value(
                                final_critic_merge.get("merge_valid", False)
                            ):
                                final_controller["route"] = "hold"
                                final_controller["reason_codes"] = sorted(
                                    set(final_controller.get("reason_codes", []))
                                    | {"critic_structural_invalid"}
                                    | set(final_critic_merge.get("structural_reason_codes", []))
                                )
                            record.update(
                                {
                                    "final_claim_ledger": final_ledger,
                                    "final_verification": final_verification.model_dump(mode="json"),
                                    "final_controller": final_controller,
                                    "route": (
                                        "pass_repaired"
                                        if str(final_controller.get("route", "")) == "pass"
                                        else "hold"
                                    ),
                                }
                            )
                            if record["route"] == "hold":
                                record["hold_reason_codes"] = ["post_repair_verification_nonpass"]
                    record["provider_retry_count"] = provider_retry_count
                except AtomicInvocationError as exc:  # pragma: no cover - provider failures vary
                    provider_retry_count += exc.retry_count
                    call_records.extend(exc.attempt_records)
                    if exc.retry_exhausted:
                        counts["provider_retry_exhausted"] += 1
                    record.update(
                        {
                            "status": "failed",
                            "failure_reason": str(exc),
                            "failure_stage": exc.call_stage,
                            "provider_retry_count": provider_retry_count,
                            "route": "hold",
                        }
                    )
                except Exception as exc:  # pragma: no cover - provider failures vary
                    record.update(
                        {
                            "status": "failed",
                            "failure_reason": _operator_error_reason(exc),
                            "provider_retry_count": provider_retry_count,
                            "route": "hold",
                        }
                    )
            record["stage_runtime"] = call_records
            record = _attach_runtime_metadata(record, _atomic_runtime_metadata(call_records))
            record["cost_estimate"] = _atomic_cost_estimate(call_records, stage_runtimes)
            record = _attach_operator_record_identity(
                record,
                stage="atomic_verify_repair",
                input_item=evidence,
                runtime_profile=runtime_profile,
            )
            _ensure_public_payload(record)
            counts[str(record.get("status", "failed"))] += 1
            if str(record.get("status", "")) == "completed":
                counts[f"route:{record.get('route', 'hold')}"] += 1
            counts["provider_retry"] += provider_retry_count
            records.append(record)
            _write_jsonl_stream_record(output_handle, record)
            if str(record.get("status", "")) in {"completed", "skipped"}:
                _write_atomic_stage_checkpoint(
                    stage_checkpoint_path,
                    stage="item_completed",
                    evidence=evidence,
                    atomic_run_id=atomic_run_id,
                    runtime_profile=runtime_profile,
                    record={
                        "status": str(record.get("status", "")),
                        "route": str(record.get("route", "")),
                    },
                    call_records=[],
                    provider_retry_count=provider_retry_count,
                )
            checkpoint_task_ids.add(str(record.get("task_id", "")))
            checkpoint_status_counts[str(record.get("status", ""))] += 1
            _write_operator_checkpoint(
                checkpoint_output_path=checkpoint_path,
                stage="atomic_verify_repair",
                input_path=evidence_path,
                output_path=output_path,
                runtime_profile=runtime_profile,
                processed_task_ids=checkpoint_task_ids,
                status_counts=checkpoint_status_counts,
            )
            progress_line.update(
                item_index,
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                skipped=counts.get("skipped", 0),
                last_status=str(record.get("route", record.get("status", "done"))),
                detail=_operator_progress_detail(
                    str(record.get("route", record.get("status", "done"))),
                    item_index,
                    len(selected_records),
                    evidence,
                    failure_reason=str(record.get("failure_reason", "")),
                ),
            )
            if stop_on_failure and str(record.get("status", "")) == "failed":
                break
    finally:
        output_handle.close()
        progress_line.finish(
            counts.get("processed", 0),
            completed=counts.get("completed", 0),
            failed=counts.get("failed", 0),
            skipped=counts.get("skipped", 0),
        )

    completed_at = _utc_timestamp()
    duration = perf_counter() - started
    summary = {
        "artifact_type": "tg_qa_canonicalization_atomic_verify_repair_run_summary",
        "generated_at": completed_at,
        "evidence_path": str(evidence_path),
        "output_path": str(output_path),
        "summary_output_path": str(summary_output_path),
        "atomic_run_id": atomic_run_id,
        "atomic_controller_policy_version": CANONICALIZATION_ATOMIC_CONTROLLER_POLICY_VERSION,
        "atomic_verifier_prompt_version": CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_VERSION,
        "atomic_verifier_prompt_profile_hash": verifier_profile_hash,
        "atomic_verifier_output_schema_hash": verifier_output_schema_hash,
        "atomic_critic_enabled": enable_critic,
        "atomic_critic_policy": critic_policy,
        "atomic_critic_prompt_version": CANONICALIZATION_ATOMIC_CRITIC_PROMPT_VERSION,
        "atomic_critic_prompt_profile_hash": critic_profile_hash,
        "atomic_critic_output_schema_hash": critic_output_schema_hash,
        "atomic_repair_enabled": bool(max_repairs),
        "atomic_repair_prompt_version": CANONICALIZATION_ATOMIC_REPAIR_PROMPT_VERSION,
        "atomic_repair_prompt_profile_hash": repair_profile_hash,
        "atomic_repair_output_schema_hash": repair_output_schema_hash,
        "formatter_output_schema_hashes": formatter_output_schema_hashes,
        "runtime_profile": runtime_profile,
        "runtime_profile_hash": _stable_json_hash(runtime_profile),
        "runtime_profile_registry": runtime_profile_registry,
        "stage_runtime_profiles": active_stage_runtime_profiles,
        "stage_pricing_snapshots": {
            stage: _atomic_pricing_snapshot_for_artifact(stage_runtimes[stage])
            for stage in active_stage_runtime_profiles
        },
        "endpoint_shape": _redacted_endpoint_shape(str(verifier_runtime["endpoint_url"])),
        "provider": str(verifier_runtime["provider"]),
        "runtime_contour": runtime_contour,
        "backend": backend,
        "model_id": str(verifier_runtime["model_id"]),
        "model_ids_by_stage": {
            stage: str(stage_runtimes[stage]["model_id"])
            for stage in active_stage_runtime_profiles
        },
        "execution_modes_by_stage": {
            stage: str(stage_runtimes[stage].get("execution_mode", "direct_structured"))
            for stage in active_stage_runtime_profiles
        },
        "formatter_model_ids_by_stage": {
            stage: str(stage_runtimes[stage]["formatter_runtime"]["model_id"])
            for stage in active_stage_runtime_profiles
            if isinstance(stage_runtimes[stage].get("formatter_runtime"), Mapping)
        },
        "structured_output_method": str(verifier_runtime["structured_output_method"]),
        "max_repairs": max_repairs,
        "verifier_max_tokens": int(verifier_runtime["max_tokens"]),
        "critic_max_tokens": int(critic_runtime["max_tokens"]),
        "repair_max_tokens": int(repair_runtime["max_tokens"]),
        "formatter_max_tokens_by_stage": {
            stage: int(stage_runtimes[stage]["formatter_runtime"]["max_tokens"])
            for stage in active_stage_runtime_profiles
            if isinstance(stage_runtimes[stage].get("formatter_runtime"), Mapping)
        },
        "timeout_seconds": max(
            int(runtime["timeout_seconds"]) for runtime in active_component_runtimes
        ),
        "resume": resume,
        "progress": progress,
        "provider_max_attempts": provider_max_attempts,
        "provider_retry_delay_seconds": provider_retry_delay_seconds,
        "max_items": max_items,
        "available_evidence_count": len(evidence_records),
        "remaining_evidence_count_before_run": len(remaining_records),
        "requested_item_count": len(selected_records),
        "processed_count": counts.get("processed", 0),
        "completed_count": counts.get("completed", 0),
        "failed_count": counts.get("failed", 0),
        "skipped_count": counts.get("skipped", 0),
        "pass_count": counts.get("route:pass", 0),
        "pass_repaired_count": counts.get("route:pass_repaired", 0),
        "hold_count": counts.get("route:hold", 0),
        "provider_retry_count": counts.get("provider_retry", 0),
        "provider_retry_exhausted_count": counts.get("provider_retry_exhausted", 0),
        "resumed_existing_count": len(resume_state["processed_task_ids"]),
        "invocation_metrics_scope": "records_processed_in_current_invocation",
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": round(duration, 3),
        "items_per_second": round(len(selected_records) / duration, 3) if duration > 0 else 0,
        "trust_boundary": "atomic_verification_and_repair_are_review_evidence_only",
    }
    summary.update(_operator_runtime_summary(records))
    summary.update(_atomic_record_cost_summary(records))
    summary["cumulative_output_metrics"] = _atomic_cumulative_output_metrics(
        _read_jsonl(output_path)
    )
    summary["checkpoint_output_path"] = str(checkpoint_path)
    summary["stage_checkpoint_output_path"] = str(stage_checkpoint_path)
    summary["run_bundle_output_path"] = str(bundle_path)
    _write_json(summary_output_path, summary)
    _write_operator_checkpoint(
        checkpoint_output_path=checkpoint_path,
        stage="atomic_verify_repair",
        input_path=evidence_path,
        output_path=output_path,
        runtime_profile=runtime_profile,
        processed_task_ids=checkpoint_task_ids,
        status_counts=checkpoint_status_counts,
    )
    _write_operator_run_bundle(
        bundle_output_path=bundle_path,
        checkpoint_output_path=checkpoint_path,
        summary_output_path=summary_output_path,
        result_output_path=output_path,
        stage="atomic_verify_repair",
        runtime_profile=runtime_profile,
        command_metadata={
            "command": "evaluation tg-qa-canonicalization-atomic-verify-repair-run",
            "resume": resume,
            "max_items": max_items,
            "max_repairs": max_repairs,
            "enable_critic": enable_critic,
            "critic_policy": critic_policy,
            "stop_on_failure": stop_on_failure,
            "stage_checkpoint_output_path": str(stage_checkpoint_path),
            "runtime_profile_registry": runtime_profile_registry,
            "stage_runtime_profile_ids": {
                stage: profile["profile_id"]
                for stage, profile in active_stage_runtime_profiles.items()
            },
        },
        log_path=log_path,
    )
    return {"results": records, "summary": summary}


def run_tg_qa_canonicalization_adjudication_batch(
    *,
    batch_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    endpoint_url: str,
    model_id: str,
    adjudication_run_id: str,
    max_items: int = 0,
    timeout_seconds: int = 180,
    max_tokens: int = 1024,
    structured_output_method: str = "json_mode",
    api_key_env: str = "",
    provider: str = "openai",
    extra_body: Mapping[str, Any] | None = None,
    stop_on_failure: bool = False,
    runtime_contour: str = "opencode_go_openai_compatible_chat_completion",
    backend: str = "opencode",
    resume: bool = True,
    provider_max_attempts: int = 3,
    provider_retry_delay_seconds: float = 2.0,
    stop_after_consecutive_provider_failures: int = 0,
    progress: bool = False,
    checkpoint_output_path: str | Path | None = None,
    run_bundle_output_path: str | Path | None = None,
    log_path: str = "",
    chain: Any | None = None,
) -> dict[str, Any]:
    """Run generic adjudication over a manually selected adjudication batch."""

    if provider not in {"anthropic", "openai"}:
        raise ValueError("provider must be anthropic or openai")
    if structured_output_method not in {"function_calling", "json_mode", "json_schema"}:
        raise ValueError("structured_output_method must be function_calling, json_mode, or json_schema")
    if provider_max_attempts < 0:
        raise ValueError("provider_max_attempts must be non-negative")
    if provider_retry_delay_seconds < 0:
        raise ValueError("provider_retry_delay_seconds must be non-negative")
    if stop_after_consecutive_provider_failures < 0:
        raise ValueError("stop_after_consecutive_provider_failures must be non-negative")
    batch_items = _read_jsonl(batch_path)
    adjudication_batch_identity = _bind_adjudication_batch_identity(batch_items)
    mismatched_prompt_tasks = [
        str(item.get("task_id", ""))
        for item in batch_items
        if str(item.get("adjudication_prompt_version", "")) != CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION
    ]
    if mismatched_prompt_tasks:
        raise ValueError(
            "adjudication batch prompt version does not match active profile; build a new batch or set the matching prompt version"
        )
    runtime_profile = _operator_runtime_profile(
        stage="adjudication",
        prompt_version=CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION,
        prompt_profile_hash=_canonicalization_prompt_profile_hash(CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION),
        provider=provider,
        runtime_contour=runtime_contour,
        backend=backend,
        model_id=model_id,
        structured_output_method=structured_output_method,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        extra_body=extra_body,
        input_batch_hash=adjudication_batch_identity["adjudication_batch_hash"],
    )
    resume_state = (
        _load_existing_operator_results(
            output_path,
            batch_items,
            stage="adjudication",
            runtime_profile=runtime_profile,
            input_identity_field="adjudication_input_hash",
        )
        if resume
        else _empty_operator_resume_state()
    )
    remaining_items = [
        item for item in batch_items if str(item.get("task_id", "")) not in resume_state["processed_task_ids"]
    ]
    selected_items = remaining_items[:max_items] if max_items > 0 else remaining_items
    started_at = _utc_timestamp()
    started = perf_counter()
    runner = chain or _build_adjudication_chain(
        provider=provider,
        endpoint_url=endpoint_url,
        model_id=model_id,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        structured_output_method=structured_output_method,
        api_key_env=api_key_env,
        extra_body=extra_body,
    )
    counts = Counter()
    records: list[dict[str, Any]] = []
    checkpoint_path = Path(checkpoint_output_path or _operator_artifact_path(summary_output_path, "checkpoint"))
    bundle_path = Path(run_bundle_output_path or _operator_artifact_path(summary_output_path, "run_bundle"))
    checkpoint_task_ids = set(resume_state["processed_task_ids"])
    checkpoint_status_counts: Counter[str] = Counter(resume_state["status_counts"])
    progress_line = _OperatorProgress(
        enabled=progress,
        label="tg-qa-canonicalization-adjudication-run",
        total=len(selected_items),
    )
    output_handle = _open_jsonl_stream(output_path, append=resume and bool(resume_state["processed_task_ids"]))
    consecutive_provider_failure_key = ""
    consecutive_provider_failure_count = 0
    stopped_by_provider_failure_guard = False
    provider_failure_guard_trigger = ""
    try:
        for item_index, item in enumerate(selected_items, start=1):
            progress_line.update(
                item_index - 1,
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                skipped=counts.get("skipped", 0),
                last_status="request",
                detail=_operator_progress_detail("request", item_index, len(selected_items), item),
            )
            counts["processed"] += 1
            compact_payload = _compact_adjudication_payload(item)
            attempts_used = 0
            item_started = perf_counter()
            last_raw_result: Any = None
            while True:
                attempts_used += 1
                try:
                    raw_result = runner.invoke({"adjudication_payload": _review_payload_for_prompt(compact_payload)})
                    last_raw_result = raw_result
                    record = _adjudication_record_from_structured_output(
                        raw_result,
                        item,
                        adjudication_run_id=adjudication_run_id,
                        runtime_contour=runtime_contour,
                        backend=backend,
                        model_id=model_id,
                    )
                    break
                except Exception as exc:  # pragma: no cover - live endpoint failures vary
                    failure_reason = _operator_error_reason(exc)
                    if _operator_should_retry_exception(exc) and _operator_retry_allowed(
                        attempts_used,
                        provider_max_attempts,
                    ):
                        counts["provider_retry"] += 1
                        progress_line.update(
                            item_index - 1,
                            completed=counts.get("completed", 0),
                            failed=counts.get("failed", 0),
                            skipped=counts.get("skipped", 0),
                            last_status="retry",
                            detail=_operator_progress_detail(
                                f"retry {attempts_used + 1}/{_operator_retry_limit_label(provider_max_attempts)}",
                                item_index,
                                len(selected_items),
                                item,
                                failure_reason=failure_reason,
                            ),
                        )
                        if provider_retry_delay_seconds > 0:
                            sleep(provider_retry_delay_seconds)
                        continue
                    if _operator_should_retry_exception(exc):
                        counts["provider_retry_exhausted"] += 1
                    record = _failed_adjudication_record(
                        item,
                        adjudication_run_id=adjudication_run_id,
                        failure_reason=_operator_failure_reason_with_attempts(failure_reason, attempts_used),
                        runtime_contour=runtime_contour,
                        backend=backend,
                        model_id=model_id,
                    )
                    break
            record = _attach_runtime_metadata(
                _attach_operator_record_identity(
                    record,
                    stage="adjudication",
                    input_item=item,
                    runtime_profile=runtime_profile,
                ),
                _operator_record_runtime_metadata(
                    last_raw_result,
                    request_duration_seconds=perf_counter() - item_started,
                    attempts_used=attempts_used,
                ),
            )
            counts[str(record.get("status", "failed"))] += 1
            records.append(record)
            _write_jsonl_stream_record(output_handle, record)
            checkpoint_task_ids.add(str(record.get("task_id", "")))
            checkpoint_status_counts[str(record.get("status", ""))] += 1
            _write_operator_checkpoint(
                checkpoint_output_path=checkpoint_path,
                stage="adjudication",
                input_path=batch_path,
                output_path=output_path,
                runtime_profile=runtime_profile,
                processed_task_ids=checkpoint_task_ids,
                status_counts=checkpoint_status_counts,
            )
            progress_line.update(
                item_index,
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                skipped=counts.get("skipped", 0),
                last_status=str(record.get("status", "done")),
                detail=_operator_progress_detail(
                    str(record.get("status", "done")),
                    item_index,
                    len(selected_items),
                    item,
                    failure_reason=str(record.get("failure_reason", "")),
                ),
            )
            provider_failure_key = _operator_provider_failure_guard_key(record)
            if provider_failure_key:
                if provider_failure_key == consecutive_provider_failure_key:
                    consecutive_provider_failure_count += 1
                else:
                    consecutive_provider_failure_key = provider_failure_key
                    consecutive_provider_failure_count = 1
            else:
                consecutive_provider_failure_key = ""
                consecutive_provider_failure_count = 0
            if (
                stop_after_consecutive_provider_failures > 0
                and consecutive_provider_failure_count >= stop_after_consecutive_provider_failures
            ):
                stopped_by_provider_failure_guard = True
                provider_failure_guard_trigger = consecutive_provider_failure_key
                progress_line.update(
                    item_index,
                    completed=counts.get("completed", 0),
                    failed=counts.get("failed", 0),
                    skipped=counts.get("skipped", 0),
                    last_status="stopped",
                    detail=(
                        "provider_failure_guard "
                        f"{consecutive_provider_failure_count}/"
                        f"{stop_after_consecutive_provider_failures} "
                        f"{provider_failure_guard_trigger}"
                    ),
                )
                break
            if stop_on_failure and str(record.get("status", "")) == "failed":
                break
    finally:
        output_handle.close()
        progress_line.finish(
            counts.get("processed", 0),
            completed=counts.get("completed", 0),
            failed=counts.get("failed", 0),
            skipped=counts.get("skipped", 0),
        )

    completed_at = _utc_timestamp()
    duration = perf_counter() - started
    summary = {
        "artifact_type": "tg_qa_canonicalization_adjudication_run_summary",
        "generated_at": completed_at,
        "batch_path": str(batch_path),
        "output_path": str(output_path),
        "summary_output_path": str(summary_output_path),
        "adjudication_run_id": adjudication_run_id,
        "adjudication_batch_id": adjudication_batch_identity["adjudication_batch_id"],
        "adjudication_batch_hash": adjudication_batch_identity["adjudication_batch_hash"],
        "adjudication_prompt_version": CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION,
        "adjudication_prompt_profile_hash": _canonicalization_prompt_profile_hash(
            CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION
        ),
        "runtime_profile": runtime_profile,
        "runtime_profile_hash": _stable_json_hash(runtime_profile),
        "endpoint_shape": _redacted_endpoint_shape(endpoint_url),
        "provider": provider,
        "runtime_contour": runtime_contour,
        "backend": backend,
        "model_id": model_id,
        "api_key_env": api_key_env,
        "auth_mode": "bearer_env" if api_key_env else "none",
        "structured_output_method": structured_output_method,
        "extra_body_keys": sorted(extra_body.keys()) if isinstance(extra_body, Mapping) else [],
        "stop_on_failure": stop_on_failure,
        "stop_after_consecutive_provider_failures": stop_after_consecutive_provider_failures,
        "stopped_by_provider_failure_guard": stopped_by_provider_failure_guard,
        "provider_failure_guard_trigger": provider_failure_guard_trigger,
        "consecutive_provider_failure_count": consecutive_provider_failure_count,
        "unprocessed_count_due_to_provider_failure_guard": (
            len(selected_items) - counts.get("processed", 0) if stopped_by_provider_failure_guard else 0
        ),
        "resume": resume,
        "progress": progress,
        "provider_max_attempts": provider_max_attempts,
        "provider_retry_forever": provider_max_attempts == 0,
        "provider_retry_delay_seconds": provider_retry_delay_seconds,
        "max_items": max_items,
        "max_tokens": max_tokens,
        "timeout_seconds": timeout_seconds,
        "requested_item_count": len(selected_items),
        "remaining_item_count_before_run": len(remaining_items),
        "available_batch_item_count": len(batch_items),
        "processed_count": counts.get("processed", 0),
        "completed_count": counts.get("completed", 0),
        "failed_count": counts.get("failed", 0),
        "skipped_count": counts.get("skipped", 0),
        "provider_retry_count": counts.get("provider_retry", 0),
        "provider_retry_exhausted_count": counts.get("provider_retry_exhausted", 0),
        "resumed_existing_count": len(resume_state["processed_task_ids"]),
        "existing_status_counts": dict(sorted(resume_state["status_counts"].items())),
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": round(duration, 3),
        "items_per_second": round(len(selected_items) / duration, 3) if duration > 0 else 0,
        "trust_boundary": "adjudication_results_are_review_evidence_only",
    }
    summary.update(_operator_runtime_summary(records))
    summary["checkpoint_output_path"] = str(checkpoint_path)
    summary["run_bundle_output_path"] = str(bundle_path)
    _write_json(summary_output_path, summary)
    _write_operator_checkpoint(
        checkpoint_output_path=checkpoint_path,
        stage="adjudication",
        input_path=batch_path,
        output_path=output_path,
        runtime_profile=runtime_profile,
        processed_task_ids=checkpoint_task_ids,
        status_counts=checkpoint_status_counts,
    )
    _write_operator_run_bundle(
        bundle_output_path=bundle_path,
        checkpoint_output_path=checkpoint_path,
        summary_output_path=summary_output_path,
        result_output_path=output_path,
        stage="adjudication",
        runtime_profile=runtime_profile,
        command_metadata={
            "command": "evaluation tg-qa-canonicalization-adjudication-run",
            "resume": resume,
            "max_items": max_items,
            "stop_on_failure": stop_on_failure,
            "stop_after_consecutive_provider_failures": stop_after_consecutive_provider_failures,
        },
        log_path=log_path,
    )
    return {"results": records, "summary": summary}


def run_tg_qa_canonicalization_deepseek_batch(
    *,
    batch_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    endpoint_url: str,
    model_id: str,
    adjudication_run_id: str,
    max_items: int = 0,
    timeout_seconds: int = 180,
    max_tokens: int = 1024,
    structured_output_method: str = "json_mode",
    api_key_env: str = "",
    extra_body: Mapping[str, Any] | None = None,
    stop_on_failure: bool = False,
    runtime_contour: str = "opencode_go_openai_compatible_chat_completion",
    backend: str = "opencode",
    resume: bool = True,
    provider_max_attempts: int = 3,
    provider_retry_delay_seconds: float = 2.0,
    stop_after_consecutive_provider_failures: int = 0,
    progress: bool = False,
    checkpoint_output_path: str | Path | None = None,
    run_bundle_output_path: str | Path | None = None,
    log_path: str = "",
    chain: Any | None = None,
) -> dict[str, Any]:
    """Backward-compatible alias for the generic adjudication runner."""

    return run_tg_qa_canonicalization_adjudication_batch(
        batch_path=batch_path,
        output_path=output_path,
        summary_output_path=summary_output_path,
        endpoint_url=endpoint_url,
        model_id=model_id,
        adjudication_run_id=adjudication_run_id,
        max_items=max_items,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        structured_output_method=structured_output_method,
        api_key_env=api_key_env,
        extra_body=extra_body,
        stop_on_failure=stop_on_failure,
        runtime_contour=runtime_contour,
        backend=backend,
        resume=resume,
        provider_max_attempts=provider_max_attempts,
        provider_retry_delay_seconds=provider_retry_delay_seconds,
        stop_after_consecutive_provider_failures=stop_after_consecutive_provider_failures,
        progress=progress,
        checkpoint_output_path=checkpoint_output_path,
        run_bundle_output_path=run_bundle_output_path,
        log_path=log_path,
        chain=chain,
    )


def canonicalization_prompt_profile() -> dict[str, Any]:
    """Return the canonical LLM prompt profile without per-task provenance."""

    return {
        "prompt_version": CANONICALIZATION_PROMPT_VERSION,
        "prompt_profile_hash": _canonicalization_prompt_profile_hash(CANONICALIZATION_PROMPT_VERSION),
        "prompt_example_set_id": CANONICALIZATION_PROMPT_EXAMPLE_SET_ID,
        "system_instruction": CANONICALIZATION_SYSTEM_INSTRUCTION,
        "few_shot_examples": list(CANONICALIZATION_PROMPT_EXAMPLES),
        "expected_output_schema": dict(EXPECTED_CANONICALIZATION_SCHEMA),
        "pydantic_output_schema": CanonicalizationResultPayload.model_json_schema(),
        "payload_policy": "send_only_task_id_candidate_id_redacted_question_compact_hints_schema_and_examples",
    }


def compact_canonicalization_llm_payload(batch_item: Mapping[str, Any]) -> dict[str, Any]:
    """Return the minimal current-record payload for an operator LLM call."""

    source_input = batch_item.get("input", {}) if isinstance(batch_item.get("input"), Mapping) else {}
    payload = {
        "task_id": str(batch_item.get("task_id", "")),
        "task_scope": str(batch_item.get("task_scope", "question_candidate")),
        "candidate_id": str(batch_item.get("candidate_id", "")),
        "canonicalization_contract_version": str(
            batch_item.get("canonicalization_contract_version", CANONICALIZATION_CONTRACT_VERSION)
        ),
        "prompt_version": str(batch_item.get("prompt_version", CANONICALIZATION_PROMPT_VERSION)),
        "prompt_example_set_id": str(batch_item.get("prompt_example_set_id", CANONICALIZATION_PROMPT_EXAMPLE_SET_ID)),
        "input": {
            "question_text_redacted": str(source_input.get("question_text_redacted", "")),
            "topic_labels": _as_string_list(source_input.get("topic_labels", [])),
            "law_code_candidates": _as_string_list(source_input.get("law_code_candidates", [])),
            "question_date": str(source_input.get("question_date", "")),
            "answer_candidate_status": str(source_input.get("answer_candidate_status", "")),
            "quality_flags": _as_string_list(source_input.get("quality_flags", [])),
        },
        "expected_output_schema": dict(EXPECTED_CANONICALIZATION_SCHEMA),
    }
    retry_context = batch_item.get("retry_context")
    if isinstance(retry_context, Mapping):
        previous_candidate = retry_context.get("previous_candidate")
        if not isinstance(previous_candidate, Mapping):
            previous_candidate = retry_context.get("previous_qwen", {})
        verifier_votes = retry_context.get("verifier_votes")
        if not isinstance(verifier_votes, Sequence) or isinstance(verifier_votes, (str, bytes)):
            legacy_vote = retry_context.get("minimax_verifier", {})
            verifier_votes = [dict(legacy_vote)] if isinstance(legacy_vote, Mapping) and legacy_vote else []
        adjudication_results = retry_context.get("adjudication_results")
        if not isinstance(adjudication_results, Sequence) or isinstance(adjudication_results, (str, bytes)):
            legacy_adjudication = retry_context.get("adjudication", {})
            adjudication_results = (
                [dict(legacy_adjudication)]
                if isinstance(legacy_adjudication, Mapping) and legacy_adjudication
                else []
            )
        payload["retry_context"] = {
            "previous_candidate": dict(previous_candidate)
            if isinstance(previous_candidate, Mapping)
            else {},
            "verifier_votes": [dict(item) for item in verifier_votes if isinstance(item, Mapping)],
            "adjudication_results": [
                dict(item) for item in adjudication_results if isinstance(item, Mapping)
            ],
            "retry_triage": dict(retry_context.get("retry_triage", {}))
            if isinstance(retry_context.get("retry_triage"), Mapping)
            else {},
            "human_triage": dict(retry_context.get("human_triage", {}))
            if isinstance(retry_context.get("human_triage"), Mapping)
            else {},
        }
    _ensure_public_payload(payload)
    return payload


def _atomic_claim_id(
    evidence: Mapping[str, Any],
    *,
    field_name: str,
    field_index: int,
    claim_text: str,
) -> str:
    evidence_hash = str(evidence.get("canonicalization_evidence_hash", ""))
    if not evidence_hash:
        evidence_hash = _canonicalization_evidence_hash(evidence)
    digest = sha256(
        _json_for_prompt(
            {
                "canonicalization_evidence_hash": evidence_hash,
                "field_name": field_name,
                "field_index": field_index,
                "claim_text": claim_text,
            }
        ).encode("utf-8")
    ).hexdigest()[:20]
    return f"atomic-claim:{digest}"


def _atomic_claim_record(
    evidence: Mapping[str, Any],
    *,
    field_name: str,
    field_index: int,
    claim_text: str,
    claim_type: str,
    materiality: str,
) -> dict[str, Any]:
    return {
        "claim_id": _atomic_claim_id(
            evidence,
            field_name=field_name,
            field_index=field_index,
            claim_text=claim_text,
        ),
        "field_name": field_name,
        "field_index": field_index,
        "claim_text": claim_text,
        "claim_type": claim_type,
        "materiality": materiality,
    }


def _atomic_text_segments(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [segment.strip() for segment in re.split(r"\s*;\s*", text) if segment.strip()]


def build_canonicalization_atomic_claim_ledger(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Build deterministic field claims without using generator reasoning."""

    claims: list[dict[str, Any]] = []

    def add(
        field_name: str,
        claim_text: str,
        *,
        claim_type: str,
        materiality: str,
        field_index: int = 0,
    ) -> None:
        normalized = str(claim_text).strip()
        if normalized:
            claims.append(
                _atomic_claim_record(
                    evidence,
                    field_name=field_name,
                    field_index=field_index,
                    claim_text=normalized,
                    claim_type=claim_type,
                    materiality=materiality,
                )
            )

    add(
        "canonical_question",
        str(evidence.get("canonical_question", "")),
        claim_type="canonical_issue",
        materiality="high",
    )
    add(
        "legal_issue_frame",
        str(evidence.get("legal_issue_frame", "")),
        claim_type="canonical_issue",
        materiality="high",
    )
    law_area = str(evidence.get("law_area", "")).strip()
    if law_area:
        add(
            "law_area",
            f"The applicable law area is {law_area}.",
            claim_type="routing",
            materiality="high",
        )
    for index, fact in enumerate(_as_string_list(evidence.get("facts", []))):
        add("facts", fact, claim_type="source_fact", materiality="medium", field_index=index)
    for index, outcome in enumerate(_atomic_text_segments(evidence.get("desired_outcome", ""))):
        add(
            "desired_outcome",
            outcome,
            claim_type="requested_outcome",
            materiality="medium",
            field_index=index,
        )
    for index, authority in enumerate(_as_string_list(evidence.get("authority_context", []))):
        add(
            "authority_context",
            f"The competent authority context includes {authority}.",
            claim_type="authority_context",
            materiality="medium",
            field_index=index,
        )
    for index, issue in enumerate(_as_string_list(evidence.get("hidden_issues", []))):
        add("hidden_issues", issue, claim_type="hidden_issue", materiality="medium", field_index=index)
    exclusion_reason = str(evidence.get("exclusion_reason", "none")).strip() or "none"
    add(
        "exclusion_reason",
        f"The canonicalization exclusion reason is {exclusion_reason}.",
        claim_type="routing",
        materiality="high",
    )
    add(
        "is_legal_answer_required",
        (
            "The source requires a legal answer."
            if _bool_value(evidence.get("is_legal_answer_required", False))
            else "The source does not require a legal answer."
        ),
        claim_type="routing",
        materiality="high",
    )
    add(
        "is_standalone_question",
        (
            "The source is a standalone question."
            if _bool_value(evidence.get("is_standalone_question", False))
            else "The source is not a standalone question."
        ),
        claim_type="routing",
        materiality="high",
    )
    for index, quality_flag in enumerate(_as_string_list(evidence.get("quality_flags", []))):
        add(
            "quality_flags",
            f"The canonicalization quality flag {quality_flag} applies.",
            claim_type="quality_flag",
            materiality="low",
            field_index=index,
        )

    ledger = {
        "policy_version": CANONICALIZATION_ATOMIC_CONTROLLER_POLICY_VERSION,
        "canonicalization_evidence_hash": str(evidence.get("canonicalization_evidence_hash", ""))
        or _canonicalization_evidence_hash(evidence),
        "claims": claims,
    }
    untrusted_law_code_hints = _as_string_list(evidence.get("untrusted_law_code_hints", []))
    if untrusted_law_code_hints:
        ledger["controller_audit"] = {
            "untrusted_law_code_hints": untrusted_law_code_hints,
            "candidate_fields": _atomic_candidate_payload(evidence),
        }
    ledger["claim_ledger_hash"] = _stable_json_hash(ledger)
    return ledger


def _atomic_candidate_payload(evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field_name: evidence.get(field_name)
        for field_name in ATOMIC_CANDIDATE_FIELDS
    }


def compact_canonicalization_atomic_verifier_payload(
    evidence: Mapping[str, Any],
    claim_ledger: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return source, candidate fields, and deterministic claims only."""

    ledger = dict(claim_ledger or build_canonicalization_atomic_claim_ledger(evidence))
    ledger.pop("controller_audit", None)
    payload = {
        "task_id": str(evidence.get("task_id", "")),
        "candidate_id": str(evidence.get("candidate_id", "")),
        "canonicalization_evidence_hash": str(evidence.get("canonicalization_evidence_hash", ""))
        or _canonicalization_evidence_hash(evidence),
        "source_question_text_redacted": str(evidence.get("source_question_text_redacted", "")),
        "candidate": _atomic_candidate_payload(evidence),
        "claim_ledger": ledger,
        "expected_output_schema": AtomicVerificationPayload.model_json_schema(),
    }
    _ensure_public_payload(payload)
    return payload


def compact_canonicalization_atomic_critic_payload(
    evidence: Mapping[str, Any],
    claim_ledger: Mapping[str, Any],
    primary_verification: AtomicVerificationPayload | Mapping[str, Any],
) -> dict[str, Any]:
    """Select semantic and non-explicit claims for an independent critic."""

    primary = (
        primary_verification
        if isinstance(primary_verification, AtomicVerificationPayload)
        else AtomicVerificationPayload.model_validate(primary_verification)
    )
    primary_by_id = {verdict.claim_id: verdict for verdict in primary.claim_verdicts}
    selected_claims = [
        dict(claim)
        for claim in claim_ledger.get("claims", [])
        if isinstance(claim, Mapping)
        and (
            str(claim.get("field_name", "")) in ATOMIC_CRITIC_FIELD_NAMES
            or (
                primary_by_id.get(str(claim.get("claim_id", ""))) is None
                or primary_by_id[str(claim.get("claim_id", ""))].support != "explicit"
            )
        )
    ]
    critic_ledger = {
        "policy_version": CANONICALIZATION_ATOMIC_CONTROLLER_POLICY_VERSION,
        "parent_claim_ledger_hash": str(claim_ledger.get("claim_ledger_hash", "")),
        "canonicalization_evidence_hash": str(claim_ledger.get("canonicalization_evidence_hash", "")),
        "claims": selected_claims,
    }
    critic_ledger["claim_ledger_hash"] = _stable_json_hash(critic_ledger)
    selected_ids = {str(claim.get("claim_id", "")) for claim in selected_claims}
    payload = {
        "task_id": str(evidence.get("task_id", "")),
        "candidate_id": str(evidence.get("candidate_id", "")),
        "canonicalization_evidence_hash": str(evidence.get("canonicalization_evidence_hash", ""))
        or _canonicalization_evidence_hash(evidence),
        "source_question_text_redacted": str(evidence.get("source_question_text_redacted", "")),
        "candidate": _atomic_candidate_payload(evidence),
        "critic_claim_ledger": critic_ledger,
        "prior_verdicts": [
            verdict.model_dump(mode="json")
            for verdict in primary.claim_verdicts
            if verdict.claim_id in selected_ids
        ],
        "expected_output_schema": AtomicVerificationPayload.model_json_schema(),
    }
    _ensure_public_payload(payload)
    return payload


def merge_canonicalization_atomic_verifier_critic(
    primary_verification: AtomicVerificationPayload | Mapping[str, Any],
    critic_verification: AtomicVerificationPayload | Mapping[str, Any],
    claim_ledger: Mapping[str, Any],
    critic_claim_ledger: Mapping[str, Any],
    source_text: str,
) -> dict[str, Any]:
    """Conservatively merge independent verifier and critic claim verdicts."""

    primary = (
        primary_verification
        if isinstance(primary_verification, AtomicVerificationPayload)
        else AtomicVerificationPayload.model_validate(primary_verification)
    )
    critic = (
        critic_verification
        if isinstance(critic_verification, AtomicVerificationPayload)
        else AtomicVerificationPayload.model_validate(critic_verification)
    )
    critic_controller = canonicalization_atomic_verification_controller(
        critic,
        critic_claim_ledger,
        source_text,
    )
    structural_reason_codes = sorted(
        set(critic_controller.get("reason_codes", []))
        & {
            "missing_claim_verdicts",
            "duplicate_claim_verdicts",
            "unknown_claim_verdicts",
            "invalid_or_missing_source_spans",
        }
    )
    expected_claims = {
        str(claim.get("claim_id", "")): dict(claim)
        for claim in claim_ledger.get("claims", [])
        if isinstance(claim, Mapping) and str(claim.get("claim_id", ""))
    }
    critic_by_id = {verdict.claim_id: verdict for verdict in critic.claim_verdicts}
    disagreements: list[dict[str, Any]] = []
    merged_verdicts: list[AtomicClaimVerdictPayload] = []
    for primary_verdict in primary.claim_verdicts:
        critic_verdict = critic_by_id.get(primary_verdict.claim_id)
        if critic_verdict is None:
            merged_verdicts.append(primary_verdict)
            continue
        if (
            primary_verdict.support != critic_verdict.support
            or primary_verdict.relation_kind != critic_verdict.relation_kind
        ):
            disagreements.append(
                {
                    "claim_id": primary_verdict.claim_id,
                    "field_name": str(expected_claims.get(primary_verdict.claim_id, {}).get("field_name", "")),
                    "primary_support": primary_verdict.support,
                    "critic_support": critic_verdict.support,
                    "primary_relation_kind": primary_verdict.relation_kind,
                    "critic_relation_kind": critic_verdict.relation_kind,
                }
            )
        supports = {primary_verdict.support, critic_verdict.support}
        if "unresolved" in supports:
            selected_support = "unresolved"
        elif "unsupported" in supports:
            selected_support = "unsupported"
        elif "necessary_inference" in supports:
            selected_support = "necessary_inference"
        else:
            selected_support = "explicit"
        candidates = [critic_verdict, primary_verdict]
        selected = next(
            verdict for verdict in candidates if verdict.support == selected_support
        )
        expected_materiality = str(
            expected_claims.get(primary_verdict.claim_id, {}).get("materiality", selected.materiality)
        )
        merged_verdicts.append(
            AtomicClaimVerdictPayload(
                claim_id=primary_verdict.claim_id,
                support=selected_support,
                relation_kind=selected.relation_kind,
                materiality=expected_materiality,
                source_spans=selected.source_spans,
                correction=selected.correction,
                short_reason=selected.short_reason,
            )
        )
    merged_supports = {verdict.support for verdict in merged_verdicts}
    if "unresolved" in merged_supports:
        merged_route = "hold"
    elif "unsupported" in merged_supports:
        merged_route = "revise"
    else:
        merged_route = "pass"
    combined = AtomicVerificationPayload(
        route=merged_route,
        claim_verdicts=merged_verdicts,
        short_reason="Deterministic conservative merge of verifier and critic verdicts.",
    )
    return {
        "merge_valid": not structural_reason_codes,
        "structural_reason_codes": structural_reason_codes,
        "critic_controller": critic_controller,
        "disagreements": disagreements,
        "combined_verification": combined.model_dump(mode="json"),
    }


def _resolve_atomic_source_span(
    source_text: str,
    span: AtomicSourceSpanPayload,
) -> dict[str, Any]:
    """Validate an exact quote and normalize only an unambiguous offset error."""

    if span.end <= len(source_text) and source_text[span.start : span.end] == span.quote:
        return {
            "status": "exact",
            "start": span.start,
            "end": span.end,
            "normalization_mode": "none",
        }
    if span.start <= len(source_text) and source_text.startswith(span.quote, span.start):
        return {
            "status": "normalized",
            "start": span.start,
            "end": span.start + len(span.quote),
            "normalization_mode": "end_offset_corrected",
        }
    first_offset = source_text.find(span.quote)
    if first_offset < 0:
        return {
            "status": "invalid",
            "reason": "quote_not_found",
        }
    if source_text.find(span.quote, first_offset + 1) >= 0:
        return {
            "status": "invalid",
            "reason": "quote_occurs_multiple_times_without_valid_anchor",
        }
    return {
        "status": "normalized",
        "start": first_offset,
        "end": first_offset + len(span.quote),
        "normalization_mode": "unique_quote_relocated",
    }


_ATOMIC_NORMALIZED_RELATION_FIELDS = {
    "canonical_question",
    "legal_issue_frame",
    "hidden_issues",
}
_ATOMIC_FOREIGN_REGISTRATION_PATTERN = re.compile(
    r"(?:\b(?:фоп|fop)\b|sole[- ]?proprietor|foreign[- ]registered|"
    r"иностран\w*\s+регистрац|украинск\w*\s+(?:предприним|регистрац))",
    re.IGNORECASE,
)
_ATOMIC_ACTIVITY_ACTION_PATTERN = re.compile(
    r"(?:\bработ\w*|\bпрац\w*|\bwork(?:ing|s|ed)?\b|"
    r"оказыва\w*\s+услуг|предоставля\w*\s+услуг|"
    r"(?:вед|занима|осуществля)\w*\s+(?:бизнес|деятель))",
    re.IGNORECASE,
)
_ATOMIC_GERMAN_CONTEXT_PATTERN = re.compile(
    r"(?:герман\w*|немецк\w*|\bgermany\b|\bdeutschland\b)",
    re.IGNORECASE,
)
_ATOMIC_ACTIVITY_RELATION_PATTERN = re.compile(
    r"(?:регистрац|registration|классификац|classification|gewerbe|freiberuf|"
    r"self[- ]?employ|sole[- ]?proprietor|предпринимательск\w*\s+деятель|"
    r"activity\s+performed|деятельност)",
    re.IGNORECASE,
)
_ATOMIC_CHILD_BENEFIT_PATTERN = re.compile(
    r"(?:kindergeld|child\s+benefit|детск\w*\s+пособ|пособ\w*\s+на\s+реб|"
    r"выплат\w*\s+на\s+реб)",
    re.IGNORECASE,
)
_ATOMIC_JOBCENTER_PATTERN = re.compile(r"(?:jobcenter|\bjc\b)", re.IGNORECASE)
_ATOMIC_DOUBLE_TAX_PATTERN = re.compile(
    r"(?:double\s+taxation|двойн\w*\s+налогооблож)",
    re.IGNORECASE,
)
_ATOMIC_CROSS_BORDER_TAX_MECHANISM_PATTERN = re.compile(
    r"(?:double\s+taxation|двойн\w*\s+налогооблож|doppelbesteuer|tax\s+credit|"
    r"налогов\w*\s+зач[её]т|зач[её]т\w*\s+налог|соглашен\w*\s+об\s+избежан|"
    r"налогов\w*\s+(?:конвенц|соглашен)|tax\s+treaty)",
    re.IGNORECASE,
)
_ATOMIC_IDENTIFIER_PATTERN = re.compile(
    r"(?:steuer[- ]?id|идентификационн\w*\s+(?:налогов\w*\s+)?номер)",
    re.IGNORECASE,
)
_ATOMIC_PREREQUISITE_PATTERN = re.compile(
    r"(?:предварительн\w*\s+услов|prerequisite|"
    r"необходим\w*\s+для\s+(?:налогов\w*\s+)?(?:регистрац|подач|декларац)|"
    r"(?:blocked|required)\s+(?:for|before)|"
    r"без\s+[^.;]{0,40}\s+нельзя\s+[^.;]{0,40}(?:регистрац|подат|декларац))",
    re.IGNORECASE,
)


def _atomic_source_has_foreign_activity_link(source_text: str) -> bool:
    """Return true only for a local action phrase linked to foreign registration."""

    if not _ATOMIC_GERMAN_CONTEXT_PATTERN.search(source_text):
        return False
    for foreign_match in _ATOMIC_FOREIGN_REGISTRATION_PATTERN.finditer(source_text):
        window_start = max(0, foreign_match.start() - 120)
        window_end = min(len(source_text), foreign_match.end() + 120)
        window = source_text[window_start:window_end]
        for action_match in _ATOMIC_ACTIVITY_ACTION_PATTERN.finditer(window):
            prefix = window[max(0, action_match.start() - 16) : action_match.start()]
            if not re.search(r"(?:\bне\s*$|\bnot\s+$)", prefix, re.IGNORECASE):
                return True
    return False


def _atomic_relation_risk_matches(
    *,
    source_text: str,
    expected_claims: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Find narrow source/claim relation risks without making a model verdict."""

    source_has_activity_link = _atomic_source_has_foreign_activity_link(source_text)
    source_has_tax_mechanism = bool(
        _ATOMIC_CROSS_BORDER_TAX_MECHANISM_PATTERN.search(source_text)
    )
    source_has_identifier_prerequisite = bool(
        _ATOMIC_IDENTIFIER_PATTERN.search(source_text)
        and _ATOMIC_PREREQUISITE_PATTERN.search(source_text)
    )
    conflicts: list[dict[str, Any]] = []
    for claim_id, claim in expected_claims.items():
        field_name = str(claim.get("field_name", ""))
        if field_name not in _ATOMIC_NORMALIZED_RELATION_FIELDS:
            continue
        claim_text = str(claim.get("claim_text", ""))
        guard_ids: list[str] = []
        if (
            not source_has_activity_link
            and _ATOMIC_FOREIGN_REGISTRATION_PATTERN.search(claim_text)
            and _ATOMIC_ACTIVITY_RELATION_PATTERN.search(claim_text)
        ):
            guard_ids.append("foreign_activity_actor_action_link_missing")
        if (
            _ATOMIC_CHILD_BENEFIT_PATTERN.search(claim_text)
            and _ATOMIC_JOBCENTER_PATTERN.search(claim_text)
        ):
            guard_ids.append("child_benefit_jobcenter_compound_relation")
        if (
            _ATOMIC_DOUBLE_TAX_PATTERN.search(claim_text)
            and not source_has_tax_mechanism
        ):
            guard_ids.append("cross_border_tax_mechanism_missing")
        if (
            _ATOMIC_IDENTIFIER_PATTERN.search(claim_text)
            and _ATOMIC_PREREQUISITE_PATTERN.search(claim_text)
            and not source_has_identifier_prerequisite
        ):
            guard_ids.append("identifier_prerequisite_missing")
        for guard_id in guard_ids:
            conflicts.append(
                {
                    "guard_id": guard_id,
                    "claim_id": claim_id,
                    "field_name": field_name,
                    "field_index": _safe_int_value(claim.get("field_index")) or 0,
                    "claim_text": claim_text,
                }
            )
    return conflicts


def _atomic_relation_guard_conflicts(
    *,
    source_text: str,
    expected_claims: Mapping[str, Mapping[str, Any]],
    verdicts_by_id: Mapping[str, AtomicClaimVerdictPayload],
) -> list[dict[str, Any]]:
    """Keep only relation risks that a model attempted to support."""

    conflicts: list[dict[str, Any]] = []
    for risk in _atomic_relation_risk_matches(
        source_text=source_text,
        expected_claims=expected_claims,
    ):
        verdict = verdicts_by_id.get(str(risk["claim_id"]))
        if verdict is None or verdict.support not in {"explicit", "necessary_inference"}:
            continue
        conflicts.append({**risk, "model_support": verdict.support})
    return conflicts


def _atomic_untrusted_hint_conflicts(
    *,
    source_text: str,
    expected_claims: Mapping[str, Mapping[str, Any]],
    claim_ledger: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Detect exact weak-hint reuse without exposing hints to the verifier."""

    audit = claim_ledger.get("controller_audit", {})
    if not isinstance(audit, Mapping):
        return []
    candidate_fields = audit.get("candidate_fields", {})
    if not isinstance(candidate_fields, Mapping):
        return []
    source_folded = source_text.casefold()
    conflicts: list[dict[str, Any]] = []
    for hint in _as_string_list(audit.get("untrusted_law_code_hints", [])):
        normalized_hint = hint.strip()
        if not normalized_hint:
            continue
        pattern = re.compile(
            rf"(?<![^\W_]){re.escape(normalized_hint.casefold())}(?![^\W_])"
        )
        if pattern.search(source_folded):
            continue
        for field_name, raw_value in candidate_fields.items():
            values = raw_value if isinstance(raw_value, list) else [raw_value]
            for field_index, value in enumerate(values):
                field_text = str(value)
                if not pattern.search(field_text.casefold()):
                    continue
                claim_id = next(
                    (
                        candidate_claim_id
                        for candidate_claim_id, claim in expected_claims.items()
                        if str(claim.get("field_name", "")) == str(field_name)
                        and (_safe_int_value(claim.get("field_index")) or 0) == field_index
                    ),
                    "",
                )
                conflicts.append(
                    {
                        "hint": normalized_hint,
                        "claim_id": claim_id,
                        "field_name": str(field_name),
                        "field_index": field_index,
                        "claim_text": field_text,
                    }
                )
    return conflicts


def canonicalization_atomic_verification_controller(
    verification: AtomicVerificationPayload | Mapping[str, Any],
    claim_ledger: Mapping[str, Any],
    source_text: str,
) -> dict[str, Any]:
    """Derive pass/revise/hold from claim identity and exact-span invariants."""

    payload = (
        verification
        if isinstance(verification, AtomicVerificationPayload)
        else AtomicVerificationPayload.model_validate(verification)
    )
    claims = claim_ledger.get("claims", [])
    expected_claims = {
        str(claim.get("claim_id", "")): dict(claim)
        for claim in claims
        if isinstance(claim, Mapping) and str(claim.get("claim_id", ""))
    }
    verdicts_by_id: dict[str, AtomicClaimVerdictPayload] = {}
    duplicate_ids: set[str] = set()
    unknown_ids: set[str] = set()
    for verdict in payload.claim_verdicts:
        if verdict.claim_id not in expected_claims:
            unknown_ids.add(verdict.claim_id)
        if verdict.claim_id in verdicts_by_id:
            duplicate_ids.add(verdict.claim_id)
        verdicts_by_id[verdict.claim_id] = verdict
    missing_ids = sorted(set(expected_claims) - set(verdicts_by_id))
    reason_codes: list[str] = []
    feedback: list[dict[str, Any]] = []
    if missing_ids:
        reason_codes.append("missing_claim_verdicts")
    if duplicate_ids:
        reason_codes.append("duplicate_claim_verdicts")
    if unknown_ids:
        reason_codes.append("unknown_claim_verdicts")

    invalid_span_claim_ids: set[str] = set()
    invalid_source_spans: list[dict[str, Any]] = []
    normalized_source_spans: list[dict[str, Any]] = []
    unsupported_claim_ids: list[str] = []
    unresolved_claim_ids: list[str] = []
    for claim_id, verdict in verdicts_by_id.items():
        claim = expected_claims.get(claim_id)
        if claim is None:
            continue
        span_valid = True
        for span_index, span in enumerate(verdict.source_spans):
            span_resolution = _resolve_atomic_source_span(source_text, span)
            if span_resolution["status"] == "invalid":
                span_valid = False
                invalid_source_spans.append(
                    {
                        "claim_id": claim_id,
                        "span_index": span_index,
                        "provided_start": span.start,
                        "provided_end": span.end,
                        "reason": str(span_resolution.get("reason", "invalid_source_span")),
                    }
                )
            elif span_resolution["status"] == "normalized":
                normalized_source_spans.append(
                    {
                        "claim_id": claim_id,
                        "span_index": span_index,
                        "provided_start": span.start,
                        "provided_end": span.end,
                        "normalized_start": span_resolution["start"],
                        "normalized_end": span_resolution["end"],
                        "normalization_mode": span_resolution["normalization_mode"],
                    }
                )
        if verdict.support in {"explicit", "necessary_inference"} and not verdict.source_spans:
            span_valid = False
        if not span_valid:
            invalid_span_claim_ids.add(claim_id)
        if verdict.support == "unsupported":
            unsupported_claim_ids.append(claim_id)
            feedback.append(
                {
                    "claim_id": claim_id,
                    "field_name": str(claim.get("field_name", "")),
                    "field_index": _safe_int_value(claim.get("field_index")) or 0,
                    "claim_text": str(claim.get("claim_text", "")),
                    "support": verdict.support,
                    "relation_kind": verdict.relation_kind,
                    "correction": verdict.correction,
                    "short_reason": verdict.short_reason,
                }
            )
        elif verdict.support == "unresolved":
            unresolved_claim_ids.append(claim_id)
            feedback.append(
                {
                    "claim_id": claim_id,
                    "field_name": str(claim.get("field_name", "")),
                    "field_index": _safe_int_value(claim.get("field_index")) or 0,
                    "claim_text": str(claim.get("claim_text", "")),
                    "support": verdict.support,
                    "relation_kind": verdict.relation_kind,
                    "correction": verdict.correction,
                    "short_reason": verdict.short_reason,
                }
            )
    if invalid_span_claim_ids:
        reason_codes.append("invalid_or_missing_source_spans")
    if unresolved_claim_ids:
        reason_codes.append("unresolved_claims")
    if unsupported_claim_ids:
        reason_codes.append("unsupported_claims")

    relation_guard_conflicts = _atomic_relation_guard_conflicts(
        source_text=source_text,
        expected_claims=expected_claims,
        verdicts_by_id=verdicts_by_id,
    )
    relation_guard_claim_ids = sorted(
        {str(item["claim_id"]) for item in relation_guard_conflicts}
    )
    if relation_guard_conflicts:
        reason_codes.append("deterministic_relation_guard_conflict")

    untrusted_hint_conflicts = _atomic_untrusted_hint_conflicts(
        source_text=source_text,
        expected_claims=expected_claims,
        claim_ledger=claim_ledger,
    )
    untrusted_hint_claim_ids = sorted(
        {str(item["claim_id"]) for item in untrusted_hint_conflicts if item["claim_id"]}
    )
    if untrusted_hint_conflicts:
        reason_codes.append("untrusted_input_hint_reused")

    structural_hold = bool(missing_ids or duplicate_ids or unknown_ids or invalid_span_claim_ids)
    if structural_hold or unresolved_claim_ids:
        route = "hold"
    elif unsupported_claim_ids:
        route = "revise"
    elif relation_guard_conflicts or untrusted_hint_conflicts:
        route = "hold"
    else:
        route = "pass"
    if payload.route != route:
        reason_codes.append("model_controller_route_disagreement")
    return {
        "route": route,
        "model_route": payload.route,
        "reason_codes": sorted(set(reason_codes)),
        "expected_claim_count": len(expected_claims),
        "verdict_count": len(payload.claim_verdicts),
        "missing_claim_ids": missing_ids,
        "duplicate_claim_ids": sorted(duplicate_ids),
        "unknown_claim_ids": sorted(unknown_ids),
        "invalid_span_claim_ids": sorted(invalid_span_claim_ids),
        "invalid_source_spans": invalid_source_spans,
        "normalized_source_spans": normalized_source_spans,
        "normalized_source_span_count": len(normalized_source_spans),
        "unsupported_claim_ids": unsupported_claim_ids,
        "unresolved_claim_ids": unresolved_claim_ids,
        "relation_guard_claim_ids": relation_guard_claim_ids,
        "relation_guard_conflicts": relation_guard_conflicts,
        "untrusted_hint_claim_ids": untrusted_hint_claim_ids,
        "untrusted_hint_conflicts": untrusted_hint_conflicts,
        "feedback": feedback,
    }


def split_tg_qa_canonicalization_atomic_relation_risks(
    *,
    evidence_path: str | Path,
    risk_evidence_output_path: str | Path,
    low_risk_evidence_output_path: str | Path,
    diagnostics_output_path: str | Path,
    summary_output_path: str | Path,
    max_items: int = 0,
) -> dict[str, Any]:
    """Split evidence by narrow deterministic relation risks without changing it."""

    if max_items < 0:
        raise ValueError("max_items_must_be_non_negative")
    available_records = _read_jsonl(evidence_path)
    records = available_records[:max_items] if max_items else available_records
    required_fields = (
        "task_id",
        "candidate_id",
        "canonicalization_evidence_hash",
        "source_question_text_redacted",
    )
    for index, evidence in enumerate(records):
        missing_fields = [
            field_name
            for field_name in required_fields
            if not isinstance(evidence.get(field_name), str)
            or not str(evidence[field_name]).strip()
        ]
        if missing_fields:
            raise ValueError(
                "atomic_relation_risk_split_invalid_evidence:"
                f"index={index}:missing={','.join(missing_fields)}"
            )
        if str(evidence["canonicalization_evidence_hash"]) != (
            _canonicalization_evidence_hash(evidence)
        ):
            raise ValueError(
                "atomic_relation_risk_split_invalid_evidence:"
                f"index={index}:canonicalization_evidence_hash_mismatch"
            )
    risk_records: list[dict[str, Any]] = []
    low_risk_records: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    risk_match_counts: Counter[str] = Counter()
    risk_record_counts: Counter[str] = Counter()

    for evidence in records:
        ledger = build_canonicalization_atomic_claim_ledger(evidence)
        expected_claims = {
            str(claim.get("claim_id", "")): dict(claim)
            for claim in ledger.get("claims", [])
            if isinstance(claim, Mapping) and str(claim.get("claim_id", ""))
        }
        risks = _atomic_relation_risk_matches(
            source_text=str(evidence.get("source_question_text_redacted", "")),
            expected_claims=expected_claims,
        )
        risk_ids = sorted({str(item["guard_id"]) for item in risks})
        risk_match_counts.update(str(item["guard_id"]) for item in risks)
        risk_record_counts.update(risk_ids)
        if risks:
            risk_records.append(dict(evidence))
        else:
            low_risk_records.append(dict(evidence))
        diagnostics.append(
            {
                "artifact_type": "tg_qa_canonicalization_atomic_relation_risk_diagnostic",
                "atomic_controller_policy_version": CANONICALIZATION_ATOMIC_CONTROLLER_POLICY_VERSION,
                "task_id": str(evidence.get("task_id", "")),
                "candidate_id": str(evidence.get("candidate_id", "")),
                "canonicalization_evidence_hash": str(
                    evidence.get("canonicalization_evidence_hash", "")
                ),
                "has_relation_risk": bool(risks),
                "relation_risk_ids": risk_ids,
                "relation_risks": risks,
                "trust_boundary": "relation_risks_are_routing_hints_not_quality_verdicts",
            }
        )

    _write_jsonl(risk_evidence_output_path, risk_records)
    _write_jsonl(low_risk_evidence_output_path, low_risk_records)
    _write_jsonl(diagnostics_output_path, diagnostics)
    summary = {
        "artifact_type": "tg_qa_canonicalization_atomic_relation_risk_split_summary",
        "atomic_controller_policy_version": CANONICALIZATION_ATOMIC_CONTROLLER_POLICY_VERSION,
        "generated_at": _utc_timestamp(),
        "evidence_path": str(evidence_path),
        "available_evidence_count": len(available_records),
        "processed_count": len(records),
        "max_items": max_items,
        "relation_risk_record_count": len(risk_records),
        "low_risk_record_count": len(low_risk_records),
        "relation_risk_match_counts": dict(sorted(risk_match_counts.items())),
        "relation_risk_record_counts": dict(sorted(risk_record_counts.items())),
        "risk_evidence_output_path": str(risk_evidence_output_path),
        "low_risk_evidence_output_path": str(low_risk_evidence_output_path),
        "diagnostics_output_path": str(diagnostics_output_path),
        "trust_boundary": "relation_risks_are_routing_hints_not_quality_verdicts",
    }
    _write_json(summary_output_path, summary)
    return {
        "summary": summary,
        "risk_records": risk_records,
        "low_risk_records": low_risk_records,
        "diagnostics": diagnostics,
    }


def split_tg_qa_canonicalization_foreign_activity_candidates(
    *,
    batch_path: str | Path,
    foreign_activity_output_path: str | Path,
    ordinary_output_path: str | Path,
    diagnostics_output_path: str | Path,
    summary_output_path: str | Path,
    foreign_activity_prompt_version: str,
    max_items: int = 0,
) -> dict[str, Any]:
    """Route explicit foreign-registered work from Germany to a focused prompt."""

    if max_items < 0:
        raise ValueError("max_items_must_be_non_negative")
    batch_items = _read_jsonl(batch_path)
    _canonicalization_batch_identity_index(batch_items)
    profile = load_prompt_profile_data(foreign_activity_prompt_version)
    if str(profile.get("prompt_version", "")) != foreign_activity_prompt_version:
        raise ValueError("foreign activity prompt profile version mismatch")

    considered = batch_items[:max_items] if max_items else batch_items
    selected: list[dict[str, Any]] = []
    ordinary: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for item in considered:
        source_input = item.get("input", {}) if isinstance(item.get("input"), Mapping) else {}
        source_text = str(source_input.get("question_text_redacted", ""))
        is_selected = _atomic_source_has_foreign_activity_link(source_text)
        derived = dict(item)
        derived["canonicalization_source_identity"] = _canonicalization_root_identity(item)
        if is_selected:
            derived["prompt_version"] = foreign_activity_prompt_version
            derived["prompt_example_set_id"] = str(profile["prompt_example_set_id"])
            derived["expected_output_schema"] = dict(profile["expected_output_schema"])
            selected.append(derived)
        else:
            ordinary.append(derived)
        diagnostics.append(
            {
                "artifact_type": "tg_question_canonicalization_foreign_activity_candidate_diagnostic",
                "task_id": str(item.get("task_id", "")),
                "candidate_id": str(item.get("candidate_id", "")),
                "has_foreign_registration": bool(
                    _ATOMIC_FOREIGN_REGISTRATION_PATTERN.search(source_text)
                ),
                "has_activity_action": bool(_ATOMIC_ACTIVITY_ACTION_PATTERN.search(source_text)),
                "has_german_context": bool(_ATOMIC_GERMAN_CONTEXT_PATTERN.search(source_text)),
                "selected_for_foreign_activity_prompt": is_selected,
                "selector_version": "foreign_activity_actor_action_location_v1",
            }
        )

    selected_identity = _bind_canonicalization_batch_identity(selected)
    ordinary_identity = _bind_canonicalization_batch_identity(ordinary)
    _write_jsonl(foreign_activity_output_path, selected)
    _write_jsonl(ordinary_output_path, ordinary)
    _write_jsonl(diagnostics_output_path, diagnostics)
    summary = {
        "artifact_type": "tg_question_canonicalization_foreign_activity_candidate_split_summary",
        "generated_at": _utc_timestamp(),
        "batch_path": str(batch_path),
        "foreign_activity_output_path": str(foreign_activity_output_path),
        "ordinary_output_path": str(ordinary_output_path),
        "diagnostics_output_path": str(diagnostics_output_path),
        "summary_output_path": str(summary_output_path),
        "source_count": len(batch_items),
        "considered_count": len(considered),
        "foreign_activity_count": len(selected),
        "ordinary_count": len(ordinary),
        "foreign_activity_prompt_version": foreign_activity_prompt_version,
        "selector_version": "foreign_activity_actor_action_location_v1",
        "foreign_activity_batch_identity": selected_identity,
        "ordinary_batch_identity": ordinary_identity,
        "trust_boundary": "selector_routes_records_but_does_not_approve_canonicalization",
    }
    _write_json(summary_output_path, summary)
    return {
        "summary": summary,
        "foreign_activity_records": selected,
        "ordinary_records": ordinary,
        "diagnostics": diagnostics,
    }


def compact_canonicalization_atomic_repair_payload(
    evidence: Mapping[str, Any],
    controller: Mapping[str, Any],
) -> dict[str, Any]:
    """Return only source, current candidate, and controller-authorized repairs."""

    payload = {
        "task_id": str(evidence.get("task_id", "")),
        "candidate_id": str(evidence.get("candidate_id", "")),
        "source_question_text_redacted": str(evidence.get("source_question_text_redacted", "")),
        "current_candidate": _atomic_candidate_payload(evidence),
        "controller_route": str(controller.get("route", "hold")),
        "controller_reason_codes": _as_string_list(controller.get("reason_codes", [])),
        "repairs": [
            dict(item)
            for item in controller.get("feedback", [])
            if isinstance(item, Mapping) and str(item.get("support", "")) == "unsupported"
        ],
        "expected_output_schema": AtomicRepairPayload.model_json_schema(),
    }
    _ensure_public_payload(payload)
    return payload


def build_langchain_canonicalization_chain(chat_model: Any, *, method: str = "") -> Any:
    """Build an optional LangChain structured-output chain for Qwen normalization."""

    try:
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError("Install the operator-llm optional dependencies to use LangChain runners.") from exc

    profile = canonicalization_prompt_profile()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "{system_instruction}\n\n"
                "Use the examples as calibration only. Return a structured object matching the schema.",
            ),
            (
                "human",
                "Few-shot examples:\n{few_shot_examples}\n\n"
                "Current compact task payload:\n{task_payload}",
            ),
        ]
    ).partial(
        system_instruction=profile["system_instruction"],
        few_shot_examples=_json_for_prompt(profile["few_shot_examples"]),
    )
    if method:
        return prompt | chat_model.with_structured_output(CanonicalizationResultPayload, method=method, include_raw=True)
    return prompt | chat_model.with_structured_output(CanonicalizationResultPayload, include_raw=True)


def build_langchain_verifier_chain(chat_model: Any, *, method: str = "") -> Any:
    """Build an optional LangChain structured-output chain for verifier verdicts."""

    try:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError("Install the operator-llm optional dependencies to use LangChain runners.") from exc

    user_lines = [str(line) for line in CANONICALIZATION_VERIFIER_PROMPT_PROFILE.get("user_prompt_lines", [])]
    messages: list[Any] = [SystemMessage(content=str(CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]))]
    for example in CANONICALIZATION_VERIFIER_PROMPT_PROFILE.get("few_shot_examples", []):
        if not isinstance(example, Mapping):
            continue
        example_input = example.get("input", {})
        example_output = example.get("output", {})
        if not isinstance(example_input, Mapping) or not isinstance(example_output, Mapping):
            continue
        messages.append(HumanMessage(content="\n".join([*user_lines, _json_for_prompt(example_input)])))
        messages.append(AIMessage(content=_json_for_prompt(example_output)))
    messages.append(("human", "\n".join([*user_lines, "{verifier_payload}"])))
    prompt = ChatPromptTemplate.from_messages(messages)
    if method:
        return prompt | chat_model.with_structured_output(VerifierVerdictPayload, method=method, include_raw=True)
    return prompt | chat_model.with_structured_output(VerifierVerdictPayload, include_raw=True)


def build_langchain_canonicalization_atomic_verifier_chain(
    chat_model: Any,
    *,
    method: str = "",
) -> Any:
    """Build the independent atomic claim verifier chain."""

    try:
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError("Install the operator-llm optional dependencies to use LangChain runners.") from exc

    user_lines = [
        str(line)
        for line in CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_PROFILE.get("user_prompt_lines", [])
    ]
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                str(CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_PROFILE["system_instruction"]),
            ),
            ("human", "\n".join([*user_lines, "{atomic_verifier_payload}"])),
        ]
    )
    if method == "prompt_json":
        return _build_prompt_json_structured_chain(prompt, chat_model, AtomicVerificationPayload)
    if method:
        return prompt | chat_model.with_structured_output(
            AtomicVerificationPayload,
            method=method,
            include_raw=True,
        )
    return prompt | chat_model.with_structured_output(
        AtomicVerificationPayload,
        include_raw=True,
    )


def build_langchain_canonicalization_atomic_critic_chain(
    chat_model: Any,
    *,
    method: str = "",
) -> Any:
    """Build an independent critic over selected structured claim verdicts."""

    try:
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError("Install the operator-llm optional dependencies to use LangChain runners.") from exc

    user_lines = [
        str(line)
        for line in CANONICALIZATION_ATOMIC_CRITIC_PROMPT_PROFILE.get("user_prompt_lines", [])
    ]
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                str(CANONICALIZATION_ATOMIC_CRITIC_PROMPT_PROFILE["system_instruction"]),
            ),
            ("human", "\n".join([*user_lines, "{atomic_critic_payload}"])),
        ]
    )
    if method == "prompt_json":
        return _build_prompt_json_structured_chain(prompt, chat_model, AtomicVerificationPayload)
    if method:
        return prompt | chat_model.with_structured_output(
            AtomicVerificationPayload,
            method=method,
            include_raw=True,
        )
    return prompt | chat_model.with_structured_output(
        AtomicVerificationPayload,
        include_raw=True,
    )


def build_langchain_canonicalization_atomic_repair_chain(
    chat_model: Any,
    *,
    method: str = "",
) -> Any:
    """Build the one-shot minimal repair chain."""

    try:
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError("Install the operator-llm optional dependencies to use LangChain runners.") from exc

    user_lines = [
        str(line)
        for line in CANONICALIZATION_ATOMIC_REPAIR_PROMPT_PROFILE.get("user_prompt_lines", [])
    ]
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                str(CANONICALIZATION_ATOMIC_REPAIR_PROMPT_PROFILE["system_instruction"]),
            ),
            ("human", "\n".join([*user_lines, "{atomic_repair_payload}"])),
        ]
    )
    if method == "prompt_json":
        return _build_prompt_json_structured_chain(prompt, chat_model, AtomicRepairPayload)
    if method:
        return prompt | chat_model.with_structured_output(
            AtomicRepairPayload,
            method=method,
            include_raw=True,
        )
    return prompt | chat_model.with_structured_output(AtomicRepairPayload, include_raw=True)


def _atomic_prompt_profile_and_contract(
    stage: Literal["verifier", "critic", "repair"],
) -> tuple[Mapping[str, Any], str, type[BaseModel]]:
    if stage == "verifier":
        return (
            CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_PROFILE,
            "atomic_verifier_payload",
            AtomicVerificationPayload,
        )
    if stage == "critic":
        return (
            CANONICALIZATION_ATOMIC_CRITIC_PROMPT_PROFILE,
            "atomic_critic_payload",
            AtomicVerificationPayload,
        )
    return (
        CANONICALIZATION_ATOMIC_REPAIR_PROMPT_PROFILE,
        "atomic_repair_payload",
        AtomicRepairPayload,
    )


def build_langchain_canonicalization_atomic_reasoning_chain(
    chat_model: Any,
    *,
    stage: Literal["verifier", "critic", "repair"],
) -> Any:
    """Build the plain-text reasoning half of an atomic two-step stage."""

    try:
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError(
            "Install the operator-llm optional dependencies to use LangChain runners."
        ) from exc

    profile, payload_variable, _schema = _atomic_prompt_profile_and_contract(stage)
    system_instruction = str(profile.get("reasoning_system_instruction", "")).strip()
    if not system_instruction:
        raise ValueError(f"atomic_{stage}_reasoning_system_instruction_missing")
    user_lines = [str(line) for line in profile.get("reasoning_user_prompt_lines", [])]
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_instruction),
            ("human", "\n".join([*user_lines, f"{{{payload_variable}}}"])),
        ]
    )
    return prompt | chat_model


def build_langchain_canonicalization_atomic_formatter_chain(
    chat_model: Any,
    *,
    stage: Literal["verifier", "critic", "repair"],
    method: str = "",
) -> Any:
    """Build the no-reasoning schema half of an atomic two-step stage."""

    try:
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError(
            "Install the operator-llm optional dependencies to use LangChain runners."
        ) from exc

    profile, _payload_variable, schema = _atomic_prompt_profile_and_contract(stage)
    if stage in {"verifier", "critic"}:
        schema = AtomicFormatterVerificationPayload
    system_instruction = str(profile.get("formatter_system_instruction", "")).strip()
    if not system_instruction:
        raise ValueError(f"atomic_{stage}_formatter_system_instruction_missing")
    user_lines = [str(line) for line in profile.get("formatter_user_prompt_lines", [])]
    prompt = ChatPromptTemplate.from_messages(
        [("system", system_instruction), ("human", "\n".join(user_lines))]
    )
    if method == "prompt_json":
        return _build_prompt_json_structured_chain(prompt, chat_model, schema)
    if method:
        return prompt | chat_model.with_structured_output(schema, method=method, include_raw=True)
    return prompt | chat_model.with_structured_output(schema, include_raw=True)


def _build_prompt_json_structured_chain(prompt: Any, chat_model: Any, schema: Any) -> Any:
    """Parse prompt-requested JSON while preserving the raw message and strict schema."""

    try:
        from langchain_core.runnables import RunnableLambda
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError(
            "Install the operator-llm optional dependencies to use LangChain runners."
        ) from exc

    def parse_message(raw_message: Any) -> dict[str, Any]:
        payload = _strict_prompt_json_payload_from_raw_message(raw_message)
        if payload is None:
            return {
                "raw": raw_message,
                "parsed": None,
                "parsing_error": "prompt_json_missing_object",
            }
        try:
            parsed = schema.model_validate(payload)
        except ValidationError as exc:
            return {
                "raw": raw_message,
                "parsed": None,
                "parsing_error": exc,
            }
        return {"raw": raw_message, "parsed": parsed, "parsing_error": None}

    return prompt | chat_model | RunnableLambda(parse_message)


def _strict_prompt_json_payload_from_raw_message(raw_message: Any) -> dict[str, Any] | None:
    """Accept one complete JSON object, optionally inside one JSON fence."""

    text = "\n".join(_raw_message_text_blocks(raw_message)).strip()
    if not text:
        return None
    fenced = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        text = fenced.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return dict(payload) if isinstance(payload, Mapping) else None


def build_langchain_adjudication_chain(chat_model: Any, *, method: str = "") -> Any:
    """Build an optional LangChain structured-output chain for generic adjudication."""

    try:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError("Install the operator-llm optional dependencies to use LangChain runners.") from exc

    user_lines = [
        str(line) for line in CANONICALIZATION_ADJUDICATOR_PROMPT_PROFILE.get("user_prompt_lines", [])
    ]
    messages: list[Any] = [
        SystemMessage(content=str(CANONICALIZATION_ADJUDICATOR_PROMPT_PROFILE["system_instruction"]))
    ]
    for example in CANONICALIZATION_ADJUDICATOR_PROMPT_PROFILE.get("few_shot_examples", []):
        if not isinstance(example, Mapping):
            continue
        example_input = example.get("input", {})
        example_output = example.get("output", {})
        if not isinstance(example_input, Mapping) or not isinstance(example_output, Mapping):
            continue
        messages.append(HumanMessage(content="\n".join([*user_lines, _json_for_prompt(example_input)])))
        messages.append(AIMessage(content=_json_for_prompt(example_output)))
    messages.append(("human", "\n".join([*user_lines, "{adjudication_payload}"])))
    prompt = ChatPromptTemplate.from_messages(messages)
    if method:
        return prompt | chat_model.with_structured_output(AdjudicationPayload, method=method, include_raw=True)
    return prompt | chat_model.with_structured_output(AdjudicationPayload, include_raw=True)


def build_langchain_legal_intent_pair_judge_chain(chat_model: Any, *, method: str = "") -> Any:
    """Build an optional LangChain structured-output chain for legal-intent pair judging."""

    try:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError("Install the operator-llm optional dependencies to use LangChain runners.") from exc

    user_lines = [str(line) for line in LEGAL_INTENT_PAIR_JUDGE_PROMPT_PROFILE.get("user_prompt_lines", [])]
    messages: list[Any] = [
        SystemMessage(content=str(LEGAL_INTENT_PAIR_JUDGE_PROMPT_PROFILE["system_instruction"]))
    ]
    for example in LEGAL_INTENT_PAIR_JUDGE_PROMPT_PROFILE.get("few_shot_examples", []):
        if not isinstance(example, Mapping):
            continue
        example_input = example.get("input", {})
        example_output = example.get("output", {})
        if not isinstance(example_input, Mapping) or not isinstance(example_output, Mapping):
            continue
        messages.append(HumanMessage(content="\n".join([*user_lines, _json_for_prompt(example_input)])))
        messages.append(AIMessage(content=_json_for_prompt(example_output)))
    messages.append(("human", "\n".join([*user_lines, "{pair_payload}"])))
    prompt = ChatPromptTemplate.from_messages(messages)
    if method:
        return prompt | chat_model.with_structured_output(LegalIntentPairDecisionPayload, method=method, include_raw=True)
    return prompt | chat_model.with_structured_output(LegalIntentPairDecisionPayload, include_raw=True)


def build_langchain_legal_intent_extractor_chain(chat_model: Any, *, method: str = "") -> Any:
    """Build an optional LangChain structured-output chain for legal-intent extraction."""

    try:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError("Install the operator-llm optional dependencies to use LangChain runners.") from exc

    user_lines = [str(line) for line in LEGAL_INTENT_EXTRACTOR_PROMPT_PROFILE.get("user_prompt_lines", [])]
    messages: list[Any] = [
        SystemMessage(content=str(LEGAL_INTENT_EXTRACTOR_PROMPT_PROFILE["system_instruction"]))
    ]
    for example in LEGAL_INTENT_EXTRACTOR_PROMPT_PROFILE.get("few_shot_examples", []):
        if not isinstance(example, Mapping):
            continue
        example_input = example.get("input", {})
        example_output = example.get("output", {})
        if not isinstance(example_input, Mapping) or not isinstance(example_output, Mapping):
            continue
        messages.append(HumanMessage(content="\n".join([*user_lines, _json_for_prompt(example_input)])))
        messages.append(AIMessage(content=_json_for_prompt(example_output)))
    messages.append(("human", "\n".join([*user_lines, "{candidate_payload}"])))
    prompt = ChatPromptTemplate.from_messages(messages)
    if method:
        return prompt | chat_model.with_structured_output(LegalIntentCandidatePayload, method=method, include_raw=True)
    return prompt | chat_model.with_structured_output(LegalIntentCandidatePayload, include_raw=True)


def build_langchain_deepseek_adjudication_chain(chat_model: Any, *, method: str = "") -> Any:
    """Backward-compatible alias for the generic adjudication chain."""

    return build_langchain_adjudication_chain(chat_model, method=method)


def import_tg_qa_canonicalization_results(
    *,
    batch_path: str | Path,
    result_path: str | Path,
    output_path: str | Path,
    manifest_output_path: str | Path,
    canonicalization_run_id: str = "",
    runtime_metadata: Mapping[str, Any] | None = None,
    only_results_task_ids: bool = False,
    allow_legacy_identity: bool = False,
) -> dict[str, Any]:
    """Validate canonicalization results and write idempotent evidence records."""

    batch_items = _read_jsonl(batch_path)
    expected_task_identities, batch_identity = _canonicalization_batch_identity_index(
        batch_items,
        allow_legacy_identity=allow_legacy_identity,
    )
    tasks_by_id = {str(item.get("task_id", "")): item for item in batch_items}
    evidence_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    seen_task_ids: set[str] = set()
    result_task_ids: set[str] = set()
    counts = Counter()
    json_valid_count = 0
    schema_valid_count = 0

    for line_number, raw_payload, error in _read_jsonl_tolerant(result_path):
        counts["processed"] += 1
        if error:
            evidence = _failed_canonicalization_evidence(
                task_id=f"invalid-line:{line_number}",
                canonicalization_run_id=canonicalization_run_id,
                failure_reason=error,
            )
            counts["failed"] += 1
        else:
            json_valid_count += 1
            assert raw_payload is not None
            payload = _extract_result_payload(raw_payload)
            payload_task_id = str(payload.get("task_id", raw_payload.get("task_id", "")))
            if payload_task_id and payload_task_id in tasks_by_id:
                result_task_ids.add(payload_task_id)
            evidence, failure_reason = _validate_canonicalization_result(
                payload,
                tasks_by_id,
                default_run_id=canonicalization_run_id,
                expected_task_identities=expected_task_identities,
                strict_identity=not allow_legacy_identity,
            )
            if failure_reason:
                evidence = _failed_canonicalization_evidence(
                    task_id=str(payload.get("task_id", raw_payload.get("task_id", f"invalid-line:{line_number}"))),
                    canonicalization_run_id=str(
                        payload.get(
                            "canonicalization_run_id",
                            raw_payload.get("canonicalization_run_id", canonicalization_run_id),
                        )
                    ),
                    failure_reason=failure_reason,
                    task_scope=str(payload.get("task_scope", "question_candidate")),
                    candidate_id=str(payload.get("candidate_id", "")),
                    source_task=tasks_by_id.get(str(payload.get("task_id", ""))),
                    raw_payload=payload,
                )
                counts["failed"] += 1
            else:
                schema_valid_count += 1
                seen_task_ids.add(str(evidence["task_id"]))
                counts[str(evidence["status"])] += 1
        key = (
            str(evidence.get("canonicalization_run_id", "")),
            str(evidence.get("task_scope", "")),
            str(evidence.get("task_id", "")),
        )
        if key in evidence_by_key:
            counts["duplicate_result"] += 1
            evidence_by_key[key] = _failed_canonicalization_evidence(
                task_id=str(evidence.get("task_id", "")),
                canonicalization_run_id=str(evidence.get("canonicalization_run_id", "")),
                failure_reason="duplicate_result_for_run_task_identity",
                source_task=tasks_by_id.get(str(evidence.get("task_id", ""))),
            )
        else:
            evidence_by_key[key] = evidence

    expected_task_ids = result_task_ids if only_results_task_ids else set(tasks_by_id)
    for task_id in sorted(expected_task_ids - seen_task_ids):
        skipped_key = (
            str(canonicalization_run_id),
            "question_candidate",
            str(task_id),
        )
        if skipped_key in evidence_by_key:
            continue
        skipped = _failed_canonicalization_evidence(
            task_id=task_id,
            canonicalization_run_id=canonicalization_run_id,
            failure_reason="missing_result_for_batch_task",
            status="skipped",
            source_task=tasks_by_id[task_id],
        )
        key = (
            str(skipped.get("canonicalization_run_id", "")),
            str(skipped.get("task_scope", "")),
            str(skipped.get("task_id", "")),
        )
        evidence_by_key[key] = skipped
        counts["skipped"] += 1

    evidence_records = sorted(
        evidence_by_key.values(),
        key=lambda item: (
            str(item.get("canonicalization_run_id", "")),
            str(item.get("task_scope", "")),
            str(item.get("task_id", "")),
        ),
    )
    _ensure_public_payload(evidence_records)
    _write_jsonl(output_path, evidence_records)

    runtime = dict(runtime_metadata or {})
    prompt_versions = sorted({str(item.get("prompt_version", "")) for item in evidence_records if item.get("prompt_version")})
    contract_versions = sorted(
        {
            str(item.get("canonicalization_contract_version", ""))
            for item in evidence_records
            if item.get("canonicalization_contract_version")
        }
    )
    run_ids = sorted({str(item.get("canonicalization_run_id", "")) for item in evidence_records if item.get("canonicalization_run_id")})
    runtime_profile_hashes = sorted(
        {str(item.get("runtime_profile_hash", "")) for item in evidence_records if item.get("runtime_profile_hash")}
    )
    status_counts = Counter(str(item.get("status", "")) for item in evidence_records)
    manifest = {
        "artifact_type": "tg_qa_canonicalization_run_manifest",
        "generated_at": _utc_timestamp(),
        "canonicalization_run_id": canonicalization_run_id
        or (run_ids[0] if len(run_ids) == 1 else "mixed"),
        "canonicalization_run_ids": run_ids,
        "input_artifact_path": _first_non_empty(
            str(item.get("input", {}).get("source_candidate_artifact", "")) for item in batch_items
        ),
        "batch_artifact_path": str(batch_path),
        "result_artifact_path": str(result_path),
        "evidence_output_path": str(output_path),
        "runtime_contour": runtime.get("runtime_contour", "operator_managed_batch_or_fixture"),
        "backend": runtime.get("backend", _first_non_empty(str(item.get("backend", "")) for item in evidence_records)),
        "model_id": runtime.get("model_id", _first_non_empty(str(item.get("model_id", "")) for item in evidence_records)),
        "prompt_version": prompt_versions[0] if len(prompt_versions) == 1 else "mixed",
        "prompt_versions": prompt_versions,
        "canonicalization_contract_version": contract_versions[0] if len(contract_versions) == 1 else "mixed",
        "prompt_profile_hashes": sorted(
            {str(item.get("prompt_profile_hash", "")) for item in evidence_records if item.get("prompt_profile_hash")}
        ),
        "runtime_profile_hashes": runtime_profile_hashes,
        "canonicalization_contract_versions": contract_versions,
        "canonicalization_identity_policy_version": CANONICALIZATION_IDENTITY_POLICY_VERSION,
        **batch_identity,
        "allow_legacy_identity": allow_legacy_identity,
        "input_scope": {
            "task_scope": "question_candidate",
            "batch_task_count": len(batch_items),
            "effective_task_count": len(expected_task_ids),
            "import_scope_mode": "results_task_ids_only" if only_results_task_ids else "full_batch",
        },
        "json_valid_result_count": json_valid_count,
        "schema_valid_result_count": schema_valid_count,
        "processed_count": counts.get("processed", 0),
        "completed_count": status_counts.get("completed", 0),
        "failed_count": status_counts.get("failed", 0),
        "skipped_count": status_counts.get("skipped", 0),
        "excluded_count": sum(1 for item in evidence_records if str(item.get("exclusion_reason", "")) != "none"),
        "uncertain_count": sum(
            1
            for item in evidence_records
            if str(item.get("confidence", "")) == "low" or str(item.get("status", "")) in {"failed", "skipped"}
        ),
        "duplicate_result_count": counts.get("duplicate_result", 0),
        "identity_validation_status_counts": dict(
            sorted(Counter(str(item.get("identity_validation_status", "")) for item in evidence_records).items())
        ),
        "started_at": runtime.get("started_at", ""),
        "completed_at": runtime.get("completed_at", _utc_timestamp()),
        "known_limitations": [
            "canonicalization output is review evidence only",
            "failed and skipped tasks remain backlog and are not trusted legal facts",
        ],
    }
    _write_json(manifest_output_path, manifest)
    return {"evidence": evidence_records, "manifest": manifest}


def _parse_finalization_result_spec(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise ValueError("replacement accepted result spec must be label=path")
    label, raw_path = raw.split("=", 1)
    label = label.strip()
    if not label or not raw_path.strip():
        raise ValueError("replacement accepted result spec must be label=path")
    return label, Path(raw_path.strip())


def _parse_finalization_batch_spec(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise ValueError("replacement batch spec must be label=path")
    label, raw_path = raw.split("=", 1)
    label = label.strip()
    if not label or not raw_path.strip():
        raise ValueError("replacement batch spec must be label=path")
    return label, Path(raw_path.strip())


def _reviewed_acceptance_failure_reason(record: Mapping[str, Any]) -> str:
    review = record.get("review_provenance", {})
    if not isinstance(review, Mapping):
        return "missing_review_provenance"
    if str(review.get("decision", "")) != "accept":
        return "review_decision_is_not_accept"
    if str(review.get("decision_source", "")) != "human_review":
        return "unreviewed_or_nonhuman_acceptance"
    return ""


def finalize_tg_qa_canonicalization_results(
    *,
    batch_path: str | Path,
    base_accepted_results_path: str | Path,
    replacement_accepted_result_specs: Sequence[str] = (),
    replacement_batch_specs: Sequence[str] = (),
    output_path: str | Path,
    manifest_output_path: str | Path,
    backlog_output_path: str | Path,
    allow_legacy_identity: bool = False,
) -> dict[str, Any]:
    """Select reviewed replacement evidence without rewriting its source run identity."""

    batch_items = _read_jsonl(batch_path)
    expected_task_identities, batch_identity = _canonicalization_batch_identity_index(
        batch_items,
        allow_legacy_identity=allow_legacy_identity,
    )
    tasks_by_id = {str(item.get("task_id", "")): item for item in batch_items}
    parsed_replacement_results = [
        _parse_finalization_result_spec(spec) for spec in replacement_accepted_result_specs
    ]
    replacement_result_labels = [label for label, _path in parsed_replacement_results]
    if len(set(replacement_result_labels)) != len(replacement_result_labels):
        raise ValueError("replacement accepted result labels must be unique")
    replacement_batches = dict(_parse_finalization_batch_spec(spec) for spec in replacement_batch_specs)
    if len(replacement_batches) != len(replacement_batch_specs):
        raise ValueError("replacement batch labels must be unique")
    if set(replacement_batches) != set(replacement_result_labels):
        raise ValueError("replacement accepted result and replacement batch labels must match exactly")
    source_specs = [("base", Path(base_accepted_results_path), Path(batch_path))]
    source_specs.extend(
        (label, result_path, replacement_batches[label])
        for label, result_path in parsed_replacement_results
    )
    source_records: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    source_artifacts: list[dict[str, Any]] = []
    backlog: list[dict[str, Any]] = []

    for label, path, source_batch_path in source_specs:
        if label == "base":
            source_batch_items = batch_items
            source_task_identities = expected_task_identities
            source_batch_identity = batch_identity
            source_tasks = tasks_by_id
        else:
            source_batch_items = _read_jsonl(source_batch_path)
            source_task_identities, source_batch_identity = _canonicalization_batch_identity_index(
                source_batch_items,
                allow_legacy_identity=allow_legacy_identity,
            )
            source_tasks = {str(item.get("task_id", "")): item for item in source_batch_items}
        records = _read_jsonl(path)
        source_artifacts.append(
            {
                "label": label,
                "path": str(path),
                "record_count": len(records),
                "batch_path": str(source_batch_path),
                "canonicalization_batch_id": source_batch_identity["canonicalization_batch_id"],
                "canonicalization_batch_hash": source_batch_identity["canonicalization_batch_hash"],
                "batch_task_count": len(source_batch_items),
            }
        )
        grouped, missing_task_id_count = _records_grouped_by_task_id(records)
        if missing_task_id_count:
            backlog.append(
                {
                    "source_label": label,
                    "task_id": "",
                    "validation_status": "blocked",
                    "validation_errors": ["accepted_result_missing_task_id"],
                    "record_count": missing_task_id_count,
                }
            )
        for task_id, raw_records in grouped.items():
            if task_id not in source_tasks:
                backlog.append(
                    {
                        "source_label": label,
                        "task_id": task_id,
                        "validation_status": "blocked",
                        "validation_errors": ["accepted_result_unknown_task_id_for_source_batch"],
                    }
                )
                continue
            if task_id not in tasks_by_id:
                backlog.append(
                    {
                        "source_label": label,
                        "task_id": task_id,
                        "validation_status": "blocked",
                        "validation_errors": ["replacement_task_not_in_base_batch"],
                    }
                )
                continue
            if len(raw_records) != 1:
                backlog.append(
                    {
                        "source_label": label,
                        "task_id": task_id,
                        "validation_status": "blocked",
                        "validation_errors": ["duplicate_accepted_results_for_task_in_source"],
                    }
                )
                continue
            evidence, failure_reason = _validate_canonicalization_result(
                _extract_result_payload(raw_records[0]),
                source_tasks,
                default_run_id="",
                expected_task_identities=source_task_identities,
                strict_identity=not allow_legacy_identity,
            )
            if failure_reason:
                backlog.append(
                    {
                        "source_label": label,
                        "task_id": task_id,
                        "validation_status": "blocked",
                        "validation_errors": [failure_reason],
                    }
                )
                continue
            if label != "base":
                expected_root_identity = _canonicalization_root_identity(tasks_by_id[task_id])
                replacement_root_identity = evidence.get("canonicalization_source_identity", {})
                if not isinstance(replacement_root_identity, Mapping):
                    replacement_root_identity = {}
                if _stable_json_hash(dict(replacement_root_identity)) != _stable_json_hash(
                    expected_root_identity
                ):
                    backlog.append(
                        {
                            "source_label": label,
                            "task_id": task_id,
                            "validation_status": "blocked",
                            "validation_errors": ["replacement_source_identity_mismatch"],
                        }
                    )
                    continue
            review_failure_reason = _reviewed_acceptance_failure_reason(evidence)
            if review_failure_reason:
                backlog.append(
                    {
                        "source_label": label,
                        "task_id": task_id,
                        "validation_status": "blocked",
                        "validation_errors": [review_failure_reason],
                    }
                )
                continue
            source_records[task_id].append((label, evidence))

    finalization_id = _stable_id(
        "tg-question-canonicalization-finalization",
        batch_identity,
        [(label, str(path), str(source_batch_path)) for label, path, source_batch_path in source_specs],
    )
    finalized: list[dict[str, Any]] = []
    for task_id in sorted(tasks_by_id):
        candidates = source_records.get(task_id, [])
        base_candidates = [item for item in candidates if item[0] == "base"]
        replacement_candidates = [item for item in candidates if item[0] != "base"]
        if len(base_candidates) > 1 or len(replacement_candidates) > 1:
            backlog.append(
                {
                    "task_id": task_id,
                    "candidate_id": str(tasks_by_id[task_id].get("candidate_id", "")),
                    "validation_status": "blocked",
                    "validation_errors": ["multiple_reviewed_replacement_results_for_task"],
                }
            )
            continue
        selected: tuple[str, dict[str, Any]] | None = None
        if replacement_candidates:
            selected = replacement_candidates[0]
        elif base_candidates:
            selected = base_candidates[0]
        if selected is None:
            backlog.append(
                {
                    "task_id": task_id,
                    "candidate_id": str(tasks_by_id[task_id].get("candidate_id", "")),
                    "validation_status": "blocked",
                    "validation_errors": ["missing_reviewed_accepted_result_for_batch_task"],
                }
            )
            continue
        source_label, evidence = selected
        final_record = dict(evidence)
        final_record["finalization_provenance"] = {
            "finalization_id": finalization_id,
            "finalization_policy_version": CANONICALIZATION_FINALIZATION_POLICY_VERSION,
            "source_label": source_label,
            "source_run_id": str(evidence.get("canonicalization_run_id", "")),
            "source_evidence_hash": str(evidence.get("canonicalization_evidence_hash", "")),
            "source_batch_id": str(evidence.get("canonicalization_batch_id", "")),
            "source_batch_hash": str(evidence.get("canonicalization_batch_hash", "")),
            "source_root_identity": dict(evidence.get("canonicalization_source_identity", {}))
            if isinstance(evidence.get("canonicalization_source_identity"), Mapping)
            else _canonicalization_root_identity(tasks_by_id[task_id]),
        }
        finalized.append(final_record)

    _ensure_public_payload(finalized)
    _ensure_public_payload(backlog)
    _write_jsonl(output_path, finalized)
    _write_jsonl(backlog_output_path, backlog)
    manifest = {
        "artifact_type": "tg_qa_canonicalization_finalization_manifest",
        "generated_at": _utc_timestamp(),
        "finalization_id": finalization_id,
        "finalization_policy_version": CANONICALIZATION_FINALIZATION_POLICY_VERSION,
        "batch_path": str(batch_path),
        "replacement_batch_specs": {label: str(path) for label, path in sorted(replacement_batches.items())},
        "output_path": str(output_path),
        "backlog_output_path": str(backlog_output_path),
        "input_artifacts": source_artifacts,
        "canonicalization_identity_policy_version": CANONICALIZATION_IDENTITY_POLICY_VERSION,
        **batch_identity,
        "allow_legacy_identity": allow_legacy_identity,
        "processed_batch_task_count": len(batch_items),
        "finalized_record_count": len(finalized),
        "backlog_count": len(backlog),
        "source_run_ids": sorted(
            {str(item.get("canonicalization_run_id", "")) for item in finalized if item.get("canonicalization_run_id")}
        ),
        "source_prompt_versions": sorted(
            {str(item.get("prompt_version", "")) for item in finalized if item.get("prompt_version")}
        ),
        "source_prompt_profile_hashes": sorted(
            {str(item.get("prompt_profile_hash", "")) for item in finalized if item.get("prompt_profile_hash")}
        ),
        "source_runtime_profile_hashes": sorted(
            {str(item.get("runtime_profile_hash", "")) for item in finalized if item.get("runtime_profile_hash")}
        ),
        "known_limitations": [
            "finalized canonicalization remains private review evidence, not legal authority",
            "unreviewed, duplicate, incompatible, and missing records remain in the finalization backlog",
        ],
    }
    _write_json(manifest_output_path, manifest)
    return {"records": finalized, "backlog": backlog, "manifest": manifest}


def _parse_snapshot_evidence_spec(raw: str) -> tuple[str, str, Path]:
    parts = raw.split("=", 2)
    if len(parts) != 3 or not all(part.strip() for part in parts):
        raise ValueError("snapshot evidence spec must be source_label=quality_tier=evidence_path")
    return parts[0].strip(), parts[1].strip(), Path(parts[2].strip())


def _canonicalization_snapshot_validation_errors(
    evidence: Mapping[str, Any],
    *,
    allow_legacy_identity: bool,
) -> list[str]:
    errors: list[str] = []
    if str(evidence.get("status", "")) != "completed":
        errors.append("status_not_completed")
    if str(evidence.get("exclusion_reason", "")) != "none":
        errors.append("exclusion_reason_not_none")
    if not _bool_value(evidence.get("is_legal_answer_required", False)):
        errors.append("legal_answer_not_required")
    if not _bool_value(evidence.get("is_standalone_question", False)):
        errors.append("not_standalone_question")
    if not str(evidence.get("canonical_question", "")).strip():
        errors.append("missing_canonical_question")
    if not str(evidence.get("legal_issue_frame_slug", "")).strip():
        errors.append("missing_legal_issue_frame_slug")
    for field_name in (
        "canonicalization_batch_id",
        "canonicalization_batch_hash",
        "task_input_hash",
        "prompt_profile_hash",
        "runtime_profile_hash",
        "canonicalization_evidence_hash",
    ):
        if not str(evidence.get(field_name, "")):
            errors.append(f"missing_{field_name}")
    if str(evidence.get("identity_validation_status", "")) != "validated" and not allow_legacy_identity:
        errors.append("identity_not_strictly_validated")
    expected_evidence_hash = _canonicalization_evidence_hash(evidence)
    if str(evidence.get("canonicalization_evidence_hash", "")) and (
        str(evidence.get("canonicalization_evidence_hash", "")) != expected_evidence_hash
    ):
        errors.append("canonicalization_evidence_hash_mismatch")
    review_failure_reason = _reviewed_acceptance_failure_reason(evidence)
    if review_failure_reason:
        errors.append(review_failure_reason)
    finalization = evidence.get("finalization_provenance", {})
    if not isinstance(finalization, Mapping) or not str(finalization.get("finalization_id", "")):
        errors.append("missing_finalization_provenance")
    return errors


def build_tg_qa_canonicalization_snapshot(
    *,
    evidence_specs: Sequence[str],
    snapshot_name: str,
    output_path: str | Path,
    manifest_output_path: str | Path,
    quality_output_path: str | Path,
    backlog_output_path: str | Path,
    allow_legacy_identity: bool = False,
) -> dict[str, Any]:
    """Export a private snapshot while retaining review and runtime lineage."""

    if not snapshot_name.strip():
        raise ValueError("snapshot_name is required")
    if not evidence_specs:
        raise ValueError("at least one evidence spec is required")

    parsed_specs = [_parse_snapshot_evidence_spec(spec) for spec in evidence_specs]
    records: list[dict[str, Any]] = []
    backlog: list[dict[str, Any]] = []
    seen_task_ids: set[str] = set()
    seen_evidence_ids: set[str] = set()
    input_artifacts: list[dict[str, Any]] = []
    processed_count = 0

    for source_label, quality_tier, path in parsed_specs:
        evidence_records = _read_jsonl(path)
        input_artifacts.append(
            {
                "source_label": source_label,
                "source_quality_tier": quality_tier,
                "evidence_path": str(path),
                "record_count": len(evidence_records),
            }
        )
        for evidence in evidence_records:
            processed_count += 1
            task_id = str(evidence.get("task_id", ""))
            evidence_id = str(evidence.get("canonicalization_evidence_id", ""))
            errors = _canonicalization_snapshot_validation_errors(
                evidence,
                allow_legacy_identity=allow_legacy_identity,
            )
            if task_id in seen_task_ids:
                errors.append("duplicate_task_id")
            if evidence_id and evidence_id in seen_evidence_ids:
                errors.append("duplicate_canonicalization_evidence_id")
            if errors:
                backlog.append(
                    {
                        "source_label": source_label,
                        "source_quality_tier": quality_tier,
                        "task_id": task_id,
                        "candidate_id": str(evidence.get("candidate_id", "")),
                        "canonicalization_evidence_id": evidence_id,
                        "validation_status": "blocked",
                        "validation_errors": sorted(set(errors)),
                    }
                )
                continue
            seen_task_ids.add(task_id)
            seen_evidence_ids.add(evidence_id)
            records.append(
                {
                    "artifact_type": "tg_qa_canonical_question_snapshot_record",
                    "snapshot_record_id": _stable_id(
                        "tg-qa-canonical-snapshot-record",
                        snapshot_name,
                        evidence_id,
                    ),
                    "snapshot_name": snapshot_name,
                    "source_label": source_label,
                    "source_quality_tier": quality_tier,
                    "task_id": task_id,
                    "candidate_id": str(evidence.get("candidate_id", "")),
                    "canonicalization_evidence_id": evidence_id,
                    "canonicalization_evidence_hash": str(evidence.get("canonicalization_evidence_hash", "")),
                    "canonicalization_run_id": str(evidence.get("canonicalization_run_id", "")),
                    "canonicalization_contract_version": str(evidence.get("canonicalization_contract_version", "")),
                    "canonicalization_batch_id": str(evidence.get("canonicalization_batch_id", "")),
                    "canonicalization_batch_hash": str(evidence.get("canonicalization_batch_hash", "")),
                    "task_input_hash": str(evidence.get("task_input_hash", "")),
                    "canonicalization_source_identity": dict(
                        evidence.get("canonicalization_source_identity", {})
                    )
                    if isinstance(evidence.get("canonicalization_source_identity"), Mapping)
                    else {},
                    "prompt_version": str(evidence.get("prompt_version", "")),
                    "prompt_profile_hash": str(evidence.get("prompt_profile_hash", "")),
                    "runtime_profile": dict(evidence.get("runtime_profile", {}))
                    if isinstance(evidence.get("runtime_profile"), Mapping)
                    else {},
                    "runtime_profile_hash": str(evidence.get("runtime_profile_hash", "")),
                    "model_id": str(evidence.get("model_id", "")),
                    "status": str(evidence.get("status", "")),
                    "canonical_question": str(evidence.get("canonical_question", "")),
                    "canonical_question_language": str(evidence.get("canonical_question_language", "")),
                    "legal_issue_frame": str(evidence.get("legal_issue_frame", "")),
                    "legal_issue_frame_slug": str(evidence.get("legal_issue_frame_slug", "")),
                    "law_area": str(evidence.get("law_area", "")),
                    "facts": _as_string_list(evidence.get("facts", [])),
                    "desired_outcome": str(evidence.get("desired_outcome", "")),
                    "authority_context": _as_string_list(evidence.get("authority_context", [])),
                    "hidden_issues": _as_string_list(evidence.get("hidden_issues", [])),
                    "quality_flags": _as_string_list(evidence.get("quality_flags", [])),
                    "confidence": str(evidence.get("confidence", "")),
                    "question_date": str(evidence.get("question_date", "")),
                    "source_question_text_redacted": str(evidence.get("source_question_text_redacted", "")),
                    "provenance": dict(evidence.get("provenance", {}))
                    if isinstance(evidence.get("provenance"), Mapping)
                    else {},
                    "review_provenance": dict(evidence.get("review_provenance", {})),
                    "finalization_provenance": dict(evidence.get("finalization_provenance", {})),
                    "trust_boundary": "private_reviewed_canonicalization_snapshot_not_legal_authority",
                }
            )

    snapshot_id = _stable_id(
        "tg-qa-canonicalization-snapshot",
        snapshot_name,
        [record["canonicalization_evidence_hash"] for record in records],
    )
    _ensure_public_payload(records)
    _ensure_public_payload(backlog)
    _write_jsonl(output_path, records)
    _write_jsonl(backlog_output_path, backlog)
    quality = {
        "artifact_type": "tg_qa_canonicalization_snapshot_quality",
        "generated_at": _utc_timestamp(),
        "snapshot_id": snapshot_id,
        "processed_input_record_count": processed_count,
        "emitted_record_count": len(records),
        "blocked_backlog_count": len(backlog),
        "validation_error_counts": dict(
            sorted(Counter(error for item in backlog for error in item.get("validation_errors", [])).items())
        ),
    }
    manifest = {
        "artifact_type": "tg_qa_canonicalization_snapshot_manifest",
        "generated_at": _utc_timestamp(),
        "snapshot_id": snapshot_id,
        "snapshot_name": snapshot_name,
        "snapshot_policy_version": CANONICALIZATION_SNAPSHOT_POLICY_VERSION,
        "output_path": str(output_path),
        "quality_output_path": str(quality_output_path),
        "backlog_output_path": str(backlog_output_path),
        "input_artifacts": input_artifacts,
        "record_count": len(records),
        "backlog_count": len(backlog),
        "allow_legacy_identity": allow_legacy_identity,
        "counts_by_quality_tier": dict(sorted(Counter(item["source_quality_tier"] for item in records).items())),
        "counts_by_law_area": dict(sorted(Counter(item["law_area"] for item in records).items())),
        "counts_by_prompt_version": dict(sorted(Counter(item["prompt_version"] for item in records).items())),
        "source_run_ids": sorted({item["canonicalization_run_id"] for item in records if item["canonicalization_run_id"]}),
        "source_prompt_profile_hashes": sorted({item["prompt_profile_hash"] for item in records if item["prompt_profile_hash"]}),
        "source_runtime_profile_hashes": sorted({item["runtime_profile_hash"] for item in records if item["runtime_profile_hash"]}),
        "known_limitations": [
            "snapshot records are private reviewed canonicalization evidence, not legal authority",
            "legacy artifacts require explicit opt-in and remain unsuitable for a strict snapshot unless lineage is reconstructed",
        ],
    }
    _write_json(manifest_output_path, manifest)
    _write_json(quality_output_path, quality)
    return {"records": records, "backlog": backlog, "manifest": manifest, "quality": quality}


def emit_tg_qa_canonical_embedding_batch(
    *,
    canonicalization_evidence_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
) -> dict[str, Any]:
    """Emit query-semantics embedding tasks for canonical questions and issue frames."""

    evidence_records = _read_jsonl(canonicalization_evidence_path)
    batch_items: list[dict[str, Any]] = []
    skipped_count = 0
    for evidence in evidence_records:
        if not _included_canonical_evidence(evidence):
            skipped_count += 1
            continue
        for role in CANONICAL_TEXT_ROLES:
            text = str(evidence.get(role, "")).strip()
            if not text:
                skipped_count += 1
                continue
            batch_items.append(_canonical_embedding_batch_item(evidence, text_role=role, text=text))

    _ensure_public_payload(batch_items)
    _write_jsonl(output_path, batch_items)
    summary = {
        "artifact_type": "tg_qa_canonical_embedding_batch_summary",
        "generated_at": _utc_timestamp(),
        "canonicalization_evidence_path": str(canonicalization_evidence_path),
        "output_path": str(output_path),
        "policy_version": CANONICAL_EMBEDDING_POLICY_VERSION,
        "embedding_prefix": QUERY_PREFIX.strip(),
        "emitted_item_count": len(batch_items),
        "skipped_evidence_or_text_count": skipped_count,
        "counts_by_text_role": _counts(str(item.get("text_role", "")) for item in batch_items),
        "trust_boundary": "canonical_embeddings_are_file_artifacts_not_graph_writes",
    }
    _write_json(summary_output_path, summary)
    return {"records": batch_items, "summary": summary}


def import_tg_qa_canonical_embedding_records(
    *,
    embedding_batch_path: str | Path,
    external_vectors_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    profile_metadata: Mapping[str, Any] | EmbeddingProfile | None = None,
) -> dict[str, Any]:
    """Import externally computed canonical vectors without graph writes."""

    batch_items = _read_jsonl(embedding_batch_path)
    external_records = _read_jsonl(external_vectors_path)
    external_by_item_id = {str(item.get("embedding_item_id", "")): item for item in external_records}
    profile = _embedding_profile_from_metadata(profile_metadata)

    records = [
        _canonical_embedding_record(
            batch_item=item,
            raw_vector_record=external_by_item_id.get(str(item.get("embedding_item_id", ""))),
            profile=profile,
        )
        for item in batch_items
    ]
    _ensure_public_payload(records)
    _write_jsonl(output_path, records)
    summary = {
        "artifact_type": "tg_qa_canonical_embedding_import_summary",
        "generated_at": _utc_timestamp(),
        "embedding_batch_path": str(embedding_batch_path),
        "external_vectors_path": str(external_vectors_path),
        "output_path": str(output_path),
        "embedding_profile": profile.as_record(),
        "processed_count": len(batch_items),
        "completed_count": sum(1 for item in records if item.get("embedding_status") == "completed"),
        "failed_count": sum(1 for item in records if item.get("embedding_status") == "failed"),
        "counts_by_text_role": _counts(str(item.get("text_role", "")) for item in records),
        "trust_boundary": "canonical_embedding_records_are_file_artifacts_not_graph_writes",
    }
    _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def cluster_tg_qa_legal_issues(
    *,
    canonicalization_evidence_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    embedding_records_path: str | Path | None = None,
    manifest_output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build deterministic reviewable clusters from canonical issue frames."""

    evidence_records = _read_jsonl(canonicalization_evidence_path)
    embedding_records = _read_jsonl(embedding_records_path) if embedding_records_path else []
    completed_embedding_ids = {
        str(item.get("canonicalization_evidence_id", ""))
        for item in embedding_records
        if str(item.get("embedding_status", "")) == "completed"
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    excluded_count = 0
    failed_count = 0
    uncertain_count = 0
    for evidence in evidence_records:
        status = str(evidence.get("status", ""))
        if status in {"failed", "skipped"}:
            failed_count += 1
            continue
        if str(evidence.get("exclusion_reason", "none")) != "none":
            excluded_count += 1
            continue
        if str(evidence.get("confidence", "")) == "low":
            uncertain_count += 1
        slug = _slugify(str(evidence.get("legal_issue_frame_slug", "")) or str(evidence.get("legal_issue_frame", "")))
        if not slug:
            slug = _slugify(str(evidence.get("canonical_question", ""))) or "unclassified"
        grouped[slug].append(evidence)

    clusters = [
        _legal_issue_cluster(
            slug,
            records,
            completed_embedding_evidence_ids=completed_embedding_ids,
            embeddings_available=bool(embedding_records_path),
        )
        for slug, records in sorted(grouped.items())
    ]
    _ensure_public_payload(clusters)
    _write_jsonl(output_path, clusters)

    summary = {
        "artifact_type": "tg_qa_legal_issue_cluster_summary",
        "generated_at": _utc_timestamp(),
        "source_canonicalization_evidence_path": str(canonicalization_evidence_path),
        "source_canonical_embedding_record_path": str(embedding_records_path or ""),
        "processed_evidence_count": len(evidence_records),
        "completed_cluster_count": len(clusters),
        "emitted_cluster_count": len(clusters),
        "excluded_evidence_count": excluded_count,
        "uncertain_evidence_count": uncertain_count,
        "failed_evidence_count": failed_count,
        "counts_by_law_area": _counts(str(item.get("law_area", "")) for item in clusters),
        "counts_by_authority_context": _counts(
            value for item in clusters for value in _as_string_list(item.get("authority_context", []))
        ),
        "counts_by_cluster_quality_flag": _counts(
            value for item in clusters for value in _as_string_list(item.get("cluster_quality_flags", []))
        ),
        "counts_by_review_route": _counts(str(item.get("review_route", "")) for item in clusters),
        "merge_policy_version": ISSUE_CLUSTER_POLICY_VERSION,
        "runtime_contour": "deterministic_file_artifact",
        "trust_boundary": "clusters_are_review_candidates_not_approved_legal_issues",
    }
    manifest = {
        "artifact_type": "tg_qa_legal_issue_cluster_manifest",
        "generated_at": summary["generated_at"],
        "input_artifact_paths": {
            "canonicalization_evidence": str(canonicalization_evidence_path),
            "embedding_records": str(embedding_records_path or ""),
        },
        "output_artifact_paths": {
            "clusters": str(output_path),
            "summary": str(summary_output_path),
            "manifest": str(manifest_output_path or ""),
        },
        "policy_versions": {
            "merge_policy_version": ISSUE_CLUSTER_POLICY_VERSION,
            "embedding_policy_version": CANONICAL_EMBEDDING_POLICY_VERSION,
        },
        "embedding_profile_ids": sorted(
            {
                str(item.get("embedding_profile_id", ""))
                for item in embedding_records
                if str(item.get("embedding_profile_id", ""))
            }
        ),
        "runtime_contour": "deterministic_file_artifact",
        "known_limitations": [
            "clustering is by canonical issue frame slug, not by raw question similarity alone",
            "all clusters remain review candidates until human review",
        ],
        "unresolved_backlog_counts": {
            "failed_evidence_count": failed_count,
            "excluded_evidence_count": excluded_count,
            "uncertain_evidence_count": uncertain_count,
        },
    }
    _write_json(summary_output_path, summary)
    if manifest_output_path:
        _write_json(manifest_output_path, manifest)
    return {"clusters": clusters, "summary": summary, "manifest": manifest}


def build_tg_qa_canonical_coverage_report(
    *,
    issue_clusters_path: str | Path,
    reviewed_final_cases_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    question_bank_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compare canonical issue clusters against reviewed cases and optional question bank."""

    clusters = _read_jsonl(issue_clusters_path)
    cases = _read_jsonl(reviewed_final_cases_path)
    question_bank = _read_jsonl(question_bank_path) if question_bank_path else []
    case_index = _slug_index(cases, id_field="case_id")
    question_bank_index = _slug_index(question_bank, id_field="question_bank_entry_id")

    records = [
        _coverage_record(
            cluster,
            reviewed_case_index=case_index,
            question_bank_index=question_bank_index,
        )
        for cluster in clusters
    ]
    _ensure_public_payload(records)
    _write_jsonl(output_path, records)
    summary = {
        "artifact_type": "tg_qa_canonical_coverage_summary",
        "generated_at": _utc_timestamp(),
        "source_issue_cluster_artifact_path": str(issue_clusters_path),
        "source_reviewed_final_cases_path": str(reviewed_final_cases_path),
        "source_question_bank_path": str(question_bank_path or ""),
        "output_path": str(output_path),
        "processed_cluster_count": len(clusters),
        "coverage_record_count": len(records),
        "counts_by_coverage_status": _counts(str(item.get("coverage_status", "")) for item in records),
        "counts_by_law_area": _counts(str(item.get("law_area", "")) for item in records),
        "counts_by_authority_context": _counts(
            value for item in records for value in _as_string_list(item.get("authority_context", []))
        ),
        "counts_by_cluster_quality_flag": _counts(
            value for item in records for value in _as_string_list(item.get("cluster_quality_flags", []))
        ),
        "excluded_count": sum(1 for item in records if item.get("coverage_status") == "excluded"),
        "uncertain_count": sum(1 for item in records if item.get("coverage_status") == "uncertain"),
        "top_uncovered_issue_clusters": [
            {
                "legal_issue_cluster_id": str(item.get("legal_issue_cluster_id", "")),
                "legal_issue_frame_slug": str(item.get("legal_issue_frame_slug", "")),
                "canonical_question_representative": str(item.get("canonical_question_representative", "")),
            }
            for item in records
            if item.get("coverage_status") == "uncovered"
        ][:20],
        "coverage_analysis_version": COVERAGE_ANALYSIS_VERSION,
        "known_limitations": [
            "coverage is measured by canonical issue cluster, not raw Telegram embedding coverage",
            "Telegram answers remain evaluation material and are not legal authority",
        ],
    }
    _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def build_tg_qa_temporal_currentness_review_queue(
    *,
    issue_clusters_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    evaluation_date: str = "",
    legal_corpus_as_of_date: str = "",
) -> dict[str, Any]:
    """Build a review queue for current-default temporal suitability."""

    clusters = _read_jsonl(issue_clusters_path)
    records = [
        _temporal_currentness_review_record(
            cluster,
            evaluation_date=evaluation_date,
            legal_corpus_as_of_date=legal_corpus_as_of_date,
        )
        for cluster in clusters
    ]
    _ensure_public_payload(records)
    _write_jsonl(output_path, records)
    summary = {
        "artifact_type": "tg_qa_temporal_currentness_review_queue_summary",
        "generated_at": _utc_timestamp(),
        "source_issue_cluster_artifact_path": str(issue_clusters_path),
        "output_path": str(output_path),
        "processed_cluster_count": len(clusters),
        "queue_record_count": len(records),
        "counts_by_suggested_temporal_relevance_state": _counts(
            str(item.get("suggested_temporal_relevance_state", "")) for item in records
        ),
        "counts_by_current_default_eligible": _counts(
            str(item.get("current_default_eligible", False)).lower() for item in records
        ),
        "evaluation_date": evaluation_date,
        "legal_corpus_as_of_date": legal_corpus_as_of_date,
        "temporal_currentness_policy_version": TEMPORAL_CURRENTNESS_POLICY_VERSION,
        "runtime_contour": "deterministic_file_artifact",
        "trust_boundary": "temporal_currentness_queue_requires_human_review_before_current_default_promotion",
    }
    _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def import_tg_qa_cluster_review_decisions(
    *,
    issue_clusters_path: str | Path,
    decisions_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
) -> dict[str, Any]:
    """Import human review decisions for canonical issue clusters."""

    clusters = {str(item.get("legal_issue_cluster_id", "")): item for item in _read_jsonl(issue_clusters_path)}
    raw_decisions = _read_decision_records(decisions_path)
    records: list[dict[str, Any]] = []
    seen_cluster_ids: set[str] = set()
    counts = Counter()

    for raw in raw_decisions:
        decision = _review_decision_record(raw, clusters=clusters)
        cluster_id = str(decision.get("legal_issue_cluster_id", ""))
        if cluster_id in seen_cluster_ids and decision.get("status") != "failed":
            decision["status"] = "failed"
            decision["failure_reason"] = "duplicate_decision_for_cluster"
        if decision.get("status") == "failed":
            counts["failed"] += 1
        else:
            seen_cluster_ids.add(cluster_id)
            counts[str(decision.get("decision", ""))] += 1
        records.append(decision)

    _ensure_public_payload(records)
    _write_jsonl(output_path, records)
    summary = {
        "artifact_type": "tg_qa_cluster_review_import_summary",
        "generated_at": _utc_timestamp(),
        "source_issue_cluster_artifact_path": str(issue_clusters_path),
        "source_review_decision_artifact_path": str(decisions_path),
        "output_path": str(output_path),
        "processed_decision_count": len(raw_decisions),
        "imported_count": sum(1 for item in records if item.get("status") != "failed"),
        "failed_count": counts.get("failed", 0),
        "counts_by_decision": _counts(
            str(item.get("decision", "")) for item in records if item.get("status") != "failed"
        ),
        "review_policy_version": CLUSTER_REVIEW_POLICY_VERSION,
    }
    _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def build_tg_qa_question_bank(
    *,
    issue_clusters_path: str | Path,
    review_decisions_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    manifest_output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build reviewed question-bank entries from approved issue clusters."""

    clusters = {str(item.get("legal_issue_cluster_id", "")): item for item in _read_jsonl(issue_clusters_path)}
    decisions = [
        item
        for item in _read_jsonl(review_decisions_path)
        if str(item.get("status", "")) != "failed"
    ]
    decision_by_cluster = {str(item.get("legal_issue_cluster_id", "")): item for item in decisions}
    entries: list[dict[str, Any]] = []
    counts = Counter()

    for cluster_id, cluster in sorted(clusters.items()):
        decision = decision_by_cluster.get(cluster_id)
        if decision is None:
            counts["needs_more_context"] += 1
            continue
        decision_value = str(decision.get("decision", ""))
        if decision_value not in {"approve_question_bank", "approve_final_evaluation"}:
            counts[decision_value or "rejected"] += 1
            continue
        entry = _question_bank_entry(cluster, decision)
        entries.append(entry)
        counts["approved_entry"] += 1
        if entry["reference_answer_status"] == "missing_reference_answer":
            counts["missing_reference_answer"] += 1

    _ensure_public_payload(entries)
    _write_jsonl(output_path, entries)
    summary = {
        "artifact_type": "tg_qa_question_bank_summary",
        "generated_at": _utc_timestamp(),
        "source_issue_cluster_artifact_path": str(issue_clusters_path),
        "source_review_decision_artifact_path": str(review_decisions_path),
        "output_path": str(output_path),
        "processed_cluster_count": len(clusters),
        "completed_entry_count": len(entries),
        "excluded_count": 0,
        "failed_decision_count": sum(1 for item in _read_jsonl(review_decisions_path) if item.get("status") == "failed"),
        "approved_entry_count": counts.get("approved_entry", 0),
        "rejected_entry_count": counts.get("reject", 0),
        "needs_more_context_count": counts.get("needs_more_context", 0),
        "uncertain_count": counts.get("uncertain", 0),
        "missing_reference_answer_count": counts.get("missing_reference_answer", 0),
        "counts_by_law_area": _counts(str(item.get("law_area", "")) for item in entries),
        "counts_by_authority_context": _counts(
            value for item in entries for value in _as_string_list(item.get("authority_context", []))
        ),
        "counts_by_coverage_status": _counts(str(item.get("coverage_status", "")) for item in entries),
        "counts_by_reference_answer_status": _counts(str(item.get("reference_answer_status", "")) for item in entries),
        "counts_by_temporal_relevance_state": _counts(str(item.get("temporal_relevance_state", "")) for item in entries),
        "current_default_eligible_count": sum(1 for item in entries if item.get("current_default_eligible") is True),
        "current_default_blocked_temporal_count": sum(
            1 for item in entries if item.get("current_default_eligible") is not True
        ),
        "review_policy_version": CLUSTER_REVIEW_POLICY_VERSION,
        "question_bank_policy_version": QUESTION_BANK_POLICY_VERSION,
        "temporal_currentness_policy_version": TEMPORAL_CURRENTNESS_POLICY_VERSION,
        "runtime_contour": "deterministic_file_artifact",
    }
    manifest = {
        "artifact_type": "tg_qa_question_bank_manifest",
        "generated_at": summary["generated_at"],
        "input_artifact_paths": {
            "issue_clusters": str(issue_clusters_path),
            "review_decisions": str(review_decisions_path),
        },
        "output_artifact_paths": {
            "question_bank": str(output_path),
            "summary": str(summary_output_path),
            "manifest": str(manifest_output_path or ""),
        },
        "review_policy_version": CLUSTER_REVIEW_POLICY_VERSION,
        "question_bank_policy_version": QUESTION_BANK_POLICY_VERSION,
        "temporal_currentness_policy_version": TEMPORAL_CURRENTNESS_POLICY_VERSION,
        "known_limitations": ["question-bank approval does not imply a final reference answer exists"],
        "unresolved_backlog_counts": {
            "missing_reference_answer_count": summary["missing_reference_answer_count"],
            "needs_more_context_count": summary["needs_more_context_count"],
            "uncertain_count": summary["uncertain_count"],
            "current_default_blocked_temporal_count": summary["current_default_blocked_temporal_count"],
        },
    }
    _write_json(summary_output_path, summary)
    if manifest_output_path:
        _write_json(manifest_output_path, manifest)
    return {"entries": entries, "summary": summary, "manifest": manifest}


def build_tg_qa_issue_final_case_candidates(
    *,
    question_bank_path: str | Path,
    review_decisions_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    manifest_output_path: str | Path | None = None,
    temporal_blocked_output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Gate final evaluation candidates on reviewed reference answer material."""

    entries = _read_jsonl(question_bank_path)
    decisions = {
        str(item.get("legal_issue_cluster_id", "")): item
        for item in _read_jsonl(review_decisions_path)
        if str(item.get("status", "")) != "failed"
    }
    candidates = [_final_case_candidate(entry, decisions.get(str(entry.get("legal_issue_cluster_id", "")))) for entry in entries]
    temporal_blocked_candidates = [
        item for item in candidates if str(item.get("promotion_status", "")) == "blocked_temporal_currentness"
    ]
    _ensure_public_payload(candidates)
    _ensure_public_payload(temporal_blocked_candidates)
    _write_jsonl(output_path, candidates)
    if temporal_blocked_output_path:
        _write_jsonl(temporal_blocked_output_path, temporal_blocked_candidates)
    summary = {
        "artifact_type": "tg_qa_issue_final_case_candidate_summary",
        "generated_at": _utc_timestamp(),
        "source_question_bank_artifact_path": str(question_bank_path),
        "source_review_decision_artifact_path": str(review_decisions_path),
        "output_path": str(output_path),
        "processed_question_bank_entry_count": len(entries),
        "completed_candidate_count": len(candidates),
        "excluded_count": 0,
        "uncertain_count": sum(1 for item in candidates if item.get("review_status") == "uncertain"),
        "failed_count": 0,
        "emitted_candidate_count": len(candidates),
        "eligible_count": sum(1 for item in candidates if item.get("promotion_status") == "eligible"),
        "blocked_missing_reference_answer_count": sum(
            1 for item in candidates if item.get("promotion_status") == "blocked_missing_reference_answer"
        ),
        "blocked_temporal_currentness_count": len(temporal_blocked_candidates),
        "rejected_count": sum(1 for item in candidates if item.get("promotion_status") == "rejected"),
        "llm_only_rejection_count": sum(1 for item in candidates if "llm_only" in item.get("promotion_reasons", [])),
        "manual_reference_answer_count": sum(
            1 for item in candidates if item.get("reference_answer_source") == "manual_review_override"
        ),
        "accepted_telegram_reference_answer_count": sum(
            1 for item in candidates if item.get("reference_answer_source") == "accepted_telegram_answer"
        ),
        "counts_by_law_area": _counts(str(item.get("law_area", "")) for item in candidates),
        "counts_by_authority_context": _counts(
            value for item in candidates for value in _as_string_list(item.get("authority_context", []))
        ),
        "counts_by_temporal_relevance_state": _counts(str(item.get("temporal_relevance_state", "")) for item in candidates),
        "promotion_policy_version": PROMOTION_POLICY_VERSION,
        "reference_answer_policy_version": REFERENCE_ANSWER_POLICY_VERSION,
        "temporal_currentness_policy_version": TEMPORAL_CURRENTNESS_POLICY_VERSION,
        "runtime_contour": "deterministic_file_artifact",
    }
    manifest = {
        "artifact_type": "tg_qa_issue_final_case_candidate_manifest",
        "generated_at": summary["generated_at"],
        "input_artifact_paths": {
            "question_bank": str(question_bank_path),
            "review_decisions": str(review_decisions_path),
        },
        "output_artifact_paths": {
            "case_candidates": str(output_path),
            "temporal_blocked_candidates": str(temporal_blocked_output_path or ""),
            "summary": str(summary_output_path),
            "manifest": str(manifest_output_path or ""),
        },
        "promotion_policy_version": PROMOTION_POLICY_VERSION,
        "reference_answer_policy_version": REFERENCE_ANSWER_POLICY_VERSION,
        "temporal_currentness_policy_version": TEMPORAL_CURRENTNESS_POLICY_VERSION,
        "known_limitations": [
            "only eligible candidates may enter reviewed final dataset artifacts",
            "temporal blocked records are retained for historical evaluation when an output path is provided",
        ],
        "unresolved_backlog_counts": {
            "blocked_missing_reference_answer_count": summary["blocked_missing_reference_answer_count"],
            "blocked_temporal_currentness_count": summary["blocked_temporal_currentness_count"],
            "rejected_count": summary["rejected_count"],
        },
    }
    _write_json(summary_output_path, summary)
    if manifest_output_path:
        _write_json(manifest_output_path, manifest)
    return {
        "candidates": candidates,
        "temporal_blocked_candidates": temporal_blocked_candidates,
        "summary": summary,
        "manifest": manifest,
    }


def build_tg_qa_reviewed_evaluation_dataset(
    *,
    final_case_candidates_path: str | Path,
    output_path: str | Path,
    manifest_output_path: str | Path,
    quality_output_path: str | Path,
) -> dict[str, Any]:
    """Export reviewed final cases from eligible promotion candidates only."""

    candidates = _read_jsonl(final_case_candidates_path)
    cases: list[dict[str, Any]] = []
    seen_cluster_ids: set[str] = set()
    duplicate_rejection_count = 0
    for candidate in candidates:
        if not _eligible_final_candidate(candidate):
            continue
        cluster_id = str(candidate.get("legal_issue_cluster_id", ""))
        if cluster_id in seen_cluster_ids:
            duplicate_rejection_count += 1
            continue
        seen_cluster_ids.add(cluster_id)
        cases.append(_reviewed_final_case(candidate))

    _ensure_public_payload(cases)
    _write_jsonl(output_path, cases)
    manifest = {
        "artifact_type": "tg_qa_reviewed_canonical_evaluation_dataset_manifest",
        "generated_at": _utc_timestamp(),
        "source_final_case_candidate_artifact_path": str(final_case_candidates_path),
        "output_path": str(output_path),
        "case_count": len(cases),
        "counts_by_reference_answer_source": _counts(str(item.get("reference_answer_source", "")) for item in cases),
        "counts_by_law_area": _counts(str(item.get("law_area", "")) for item in cases),
        "counts_by_review_status": _counts(str(item.get("review_status", "")) for item in cases),
        "policy_versions": {
            "reviewed_dataset_policy_version": REVIEWED_DATASET_POLICY_VERSION,
            "promotion_policy_version": PROMOTION_POLICY_VERSION,
            "reference_answer_policy_version": REFERENCE_ANSWER_POLICY_VERSION,
        },
        "known_limitations": ["reviewed cases are evaluation artifacts, not legal authority"],
    }
    quality = {
        "artifact_type": "tg_qa_reviewed_canonical_evaluation_dataset_quality",
        "generated_at": manifest["generated_at"],
        "eligible_input_count": sum(1 for item in candidates if item.get("promotion_status") == "eligible"),
        "exported_case_count": len(cases),
        "blocked_rejected_excluded_count": sum(1 for item in candidates if item.get("promotion_status") != "eligible"),
        "missing_reference_answer_exclusion_count": sum(
            1 for item in candidates if item.get("promotion_status") == "blocked_missing_reference_answer"
        ),
        "llm_only_exclusion_count": sum(1 for item in candidates if "llm_only" in item.get("promotion_reasons", [])),
        "temporal_currentness_exclusion_count": sum(
            1 for item in candidates if item.get("promotion_status") == "blocked_temporal_currentness"
        ),
        "duplicate_cluster_or_case_id_rejection_count": duplicate_rejection_count,
    }
    _write_json(manifest_output_path, manifest)
    _write_json(quality_output_path, quality)
    return {"cases": cases, "manifest": manifest, "quality": quality}


def build_tg_qa_legal_intent_pair_benchmark(
    *,
    canonicalization_evidence_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    similarity_pairs_path: str | Path | None = None,
    max_random_negatives: int = 0,
) -> dict[str, Any]:
    """Build stable legal-intent pair benchmark records from canonical questions."""

    evidence_records = [
        _legal_intent_source_evidence_record(item)
        for item in _read_jsonl(canonicalization_evidence_path)
        if _included_canonical_evidence(item)
    ]
    evidence_by_id = {str(item.get("canonicalization_evidence_id", "")): item for item in evidence_records}
    evidence_by_task_id = {
        str(item.get("task_id", "")): item for item in evidence_records if str(item.get("task_id", ""))
    }
    evidence_by_candidate_id = {
        str(item.get("candidate_id", "")): item for item in evidence_records if str(item.get("candidate_id", ""))
    }
    pairs: dict[str, dict[str, Any]] = {}

    for group in _group_records(evidence_records, key_func=lambda item: str(item.get("legal_issue_frame_slug", ""))):
        for left, right in _all_pairs(group):
            reasons = ["same_law_area"]
            if _normalized_text(left.get("canonical_question", "")) == _normalized_text(right.get("canonical_question", "")):
                reasons.append("strict_duplicate_candidate")
            else:
                reasons.append("preserved_variant_candidate")
            _merge_legal_intent_pair(
                pairs,
                _legal_intent_pair_record(left, right, pair_source_reasons=reasons),
            )

    for group in _group_records(evidence_records, key_func=lambda item: _normalized_text(item.get("canonical_question", ""))):
        if len(group) < 2:
            continue
        for left, right in _all_pairs(group):
            if str(left.get("law_area", "")) != str(right.get("law_area", "")):
                _merge_legal_intent_pair(
                    pairs,
                    _legal_intent_pair_record(left, right, pair_source_reasons=["law_area_conflict"]),
                )

    if similarity_pairs_path:
        for raw_pair in _read_jsonl(similarity_pairs_path):
            left, right = _similarity_pair_evidence(
                raw_pair,
                evidence_by_id=evidence_by_id,
                evidence_by_task_id=evidence_by_task_id,
                evidence_by_candidate_id=evidence_by_candidate_id,
            )
            if not left or not right:
                continue
            reasons = _as_string_list(raw_pair.get("pair_source_reasons", raw_pair.get("reasons", [])))
            if not reasons:
                reasons = ["high_canonical_question_similarity"]
            _merge_legal_intent_pair(
                pairs,
                _legal_intent_pair_record(
                    left,
                    right,
                    pair_source_reasons=reasons,
                    similarity_evidence=_similarity_evidence_from_pair(raw_pair),
                ),
            )

    if max_random_negatives > 0:
        for pair in _balanced_legal_intent_random_negative_pairs(
            evidence_records,
            existing_pair_ids=set(pairs),
            max_pairs=max_random_negatives,
        ):
            _merge_legal_intent_pair(pairs, pair)

    records = sorted(pairs.values(), key=lambda item: str(item.get("pair_id", "")))
    _ensure_public_payload(records)
    _write_jsonl(output_path, records)
    summary = {
        "artifact_type": "tg_qa_legal_intent_pair_benchmark_summary",
        "generated_at": _utc_timestamp(),
        "source_canonicalization_evidence_path": str(canonicalization_evidence_path),
        "source_similarity_pairs_path": str(similarity_pairs_path or ""),
        "output_path": str(output_path),
        "policy_version": LEGAL_INTENT_BENCHMARK_POLICY_VERSION,
        "processed_canonicalization_evidence_count": len(evidence_records),
        "pair_count": len(records),
        "max_random_negatives": max_random_negatives,
        "counts_by_pair_source_reason": _counts(
            reason for item in records for reason in _as_string_list(item.get("pair_source_reasons", []))
        ),
        "random_negative_unique_left_candidate_count": len(
            {
                str(item.get("left_candidate_id", ""))
                for item in records
                if "random_negative" in _as_string_list(item.get("pair_source_reasons", []))
            }
        ),
        "random_negative_unique_right_candidate_count": len(
            {
                str(item.get("right_candidate_id", ""))
                for item in records
                if "random_negative" in _as_string_list(item.get("pair_source_reasons", []))
            }
        ),
        "counts_by_benchmark_status": _counts(str(item.get("benchmark_status", "")) for item in records),
        "artifact_directory": "data/evaluation/tg_qa_legal_intent_equivalence/",
        "trust_boundary": "pair_benchmark_records_are_candidates_not_legal_truth",
    }
    _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def run_tg_qa_legal_intent_candidate_extractor_batch(
    *,
    canonicalization_evidence_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    endpoint_url: str,
    model_id: str,
    extractor_run_id: str,
    pair_benchmark_path: str | Path | None = None,
    provider: str = "openai",
    max_items: int = 0,
    timeout_seconds: int = 180,
    max_tokens: int = 1536,
    structured_output_method: str = "json_mode",
    api_key_env: str = "",
    extra_body: Mapping[str, Any] | None = None,
    stop_on_failure: bool = False,
    runtime_contour: str = "operator_managed_legal_intent_extractor",
    backend: str = "opencode",
    resume: bool = True,
    provider_max_attempts: int = 3,
    provider_retry_delay_seconds: float = 2.0,
    stop_after_consecutive_provider_failures: int = 0,
    progress: bool = False,
    chain: Any | None = None,
) -> dict[str, Any]:
    """Extract structured material slots from included canonicalization evidence."""

    if provider not in {"anthropic", "openai"}:
        raise ValueError("provider must be anthropic or openai")
    if structured_output_method not in {"function_calling", "json_mode", "json_schema"}:
        raise ValueError("structured_output_method must be function_calling, json_mode, or json_schema")
    if provider_max_attempts < 0:
        raise ValueError("provider_max_attempts must be non-negative")
    if provider_retry_delay_seconds < 0:
        raise ValueError("provider_retry_delay_seconds must be non-negative")
    if stop_after_consecutive_provider_failures < 0:
        raise ValueError("stop_after_consecutive_provider_failures must be non-negative")

    all_evidence = [
        _legal_intent_source_evidence_record(item)
        for item in _read_jsonl(canonicalization_evidence_path)
        if _included_canonical_evidence(item)
    ]
    scoped_evidence_ids = _legal_intent_evidence_ids_from_pair_benchmark(pair_benchmark_path)
    available_evidence_ids = {
        str(item.get("canonicalization_evidence_id", "")) for item in all_evidence
    }
    if scoped_evidence_ids is not None:
        if not scoped_evidence_ids:
            raise ValueError("pair benchmark contains no canonicalization evidence ids")
        missing_evidence_ids = scoped_evidence_ids - available_evidence_ids
        if missing_evidence_ids:
            raise ValueError(
                f"pair benchmark references {len(missing_evidence_ids)} canonicalization evidence ids "
                "missing from the source evidence artifact"
            )
    evidence = [
        item
        for item in all_evidence
        if scoped_evidence_ids is None
        or str(item.get("canonicalization_evidence_id", "")) in scoped_evidence_ids
    ]
    run_items = [_legal_intent_candidate_operator_item(item) for item in evidence]
    resume_state = _load_existing_operator_results(output_path, run_items) if resume else _empty_operator_resume_state()
    remaining_evidence = [
        item
        for item in evidence
        if str(item.get("canonicalization_evidence_id", "")) not in resume_state["processed_task_ids"]
    ]
    selected_evidence = remaining_evidence[:max_items] if max_items > 0 else remaining_evidence
    started_at = _utc_timestamp()
    started = perf_counter()
    runner = chain or _build_legal_intent_extractor_chain(
        provider=provider,
        endpoint_url=endpoint_url,
        model_id=model_id,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        structured_output_method=structured_output_method,
        api_key_env=api_key_env,
        extra_body=extra_body,
    )
    counts = Counter()
    records: list[dict[str, Any]] = []
    progress_line = _OperatorProgress(
        enabled=progress,
        label="tg-qa-legal-intent-candidate-extractor-run",
        total=len(selected_evidence),
    )
    output_handle = _open_jsonl_stream(output_path, append=resume and bool(resume_state["processed_task_ids"]))
    consecutive_provider_failure_key = ""
    consecutive_provider_failure_count = 0
    stopped_by_provider_failure_guard = False
    provider_failure_guard_trigger = ""
    try:
        for item_index, source_evidence in enumerate(selected_evidence, start=1):
            operator_item = _legal_intent_candidate_operator_item(source_evidence)
            progress_line.update(
                item_index - 1,
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                skipped=counts.get("skipped", 0),
                last_status="request",
                detail=_operator_progress_detail("request", item_index, len(selected_evidence), operator_item),
            )
            counts["processed"] += 1
            compact_payload = _compact_legal_intent_extractor_payload(source_evidence)
            attempts_used = 0
            item_started = perf_counter()
            last_raw_result: Any = None
            while True:
                attempts_used += 1
                try:
                    raw_result = runner.invoke({"candidate_payload": _json_for_prompt(compact_payload)})
                    last_raw_result = raw_result
                    record = _legal_intent_candidate_record_from_structured_output(
                        raw_result,
                        source_evidence,
                        extractor_run_id=extractor_run_id,
                        runtime_contour=runtime_contour,
                        backend=backend,
                        model_id=model_id,
                    )
                    break
                except Exception as exc:  # pragma: no cover - live endpoint failures vary
                    failure_reason = _operator_error_reason(exc)
                    retry_limit = _operator_retry_limit_for_exception(exc, provider_max_attempts)
                    if _operator_should_retry_exception(exc) and _operator_retry_allowed(attempts_used, retry_limit):
                        counts["provider_retry"] += 1
                        progress_line.update(
                            item_index - 1,
                            completed=counts.get("completed", 0),
                            failed=counts.get("failed", 0),
                            skipped=counts.get("skipped", 0),
                            last_status="retry",
                            detail=_operator_progress_detail(
                                f"retry {attempts_used + 1}/{_operator_retry_limit_label(retry_limit)}",
                                item_index,
                                len(selected_evidence),
                                operator_item,
                                failure_reason=failure_reason,
                            ),
                        )
                        if provider_retry_delay_seconds > 0:
                            sleep(provider_retry_delay_seconds)
                        continue
                    if _operator_should_retry_exception(exc):
                        counts["provider_retry_exhausted"] += 1
                    record = _failed_legal_intent_extractor_record(
                        source_evidence,
                        extractor_run_id=extractor_run_id,
                        failure_reason=_operator_failure_reason_with_attempts(failure_reason, attempts_used),
                        runtime_contour=runtime_contour,
                        backend=backend,
                        model_id=model_id,
                    )
                    break
            record = _attach_runtime_metadata(
                record,
                _operator_record_runtime_metadata(
                    last_raw_result,
                    request_duration_seconds=perf_counter() - item_started,
                    attempts_used=attempts_used,
                ),
            )
            counts[str(record.get("status", "failed"))] += 1
            records.append(record)
            _write_jsonl_stream_record(output_handle, record)
            progress_line.update(
                item_index,
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                skipped=counts.get("skipped", 0),
                last_status=str(record.get("status", "done")),
                detail=_operator_progress_detail(
                    str(record.get("status", "done")),
                    item_index,
                    len(selected_evidence),
                    operator_item,
                    failure_reason=str(record.get("failure_reason", "")),
                ),
            )
            provider_failure_key = _operator_provider_failure_guard_key(record)
            if provider_failure_key:
                if provider_failure_key == consecutive_provider_failure_key:
                    consecutive_provider_failure_count += 1
                else:
                    consecutive_provider_failure_key = provider_failure_key
                    consecutive_provider_failure_count = 1
            else:
                consecutive_provider_failure_key = ""
                consecutive_provider_failure_count = 0
            if (
                stop_after_consecutive_provider_failures > 0
                and consecutive_provider_failure_count >= stop_after_consecutive_provider_failures
            ):
                stopped_by_provider_failure_guard = True
                provider_failure_guard_trigger = consecutive_provider_failure_key
                progress_line.update(
                    item_index,
                    completed=counts.get("completed", 0),
                    failed=counts.get("failed", 0),
                    skipped=counts.get("skipped", 0),
                    last_status="stopped",
                    detail=(
                        "provider_failure_guard "
                        f"{consecutive_provider_failure_count}/"
                        f"{stop_after_consecutive_provider_failures} "
                        f"{provider_failure_guard_trigger}"
                    ),
                )
                break
            if stop_on_failure and str(record.get("status", "")) == "failed":
                break
    finally:
        output_handle.close()
        progress_line.finish(
            counts.get("processed", 0),
            completed=counts.get("completed", 0),
            failed=counts.get("failed", 0),
            skipped=counts.get("skipped", 0),
        )

    completed_at = _utc_timestamp()
    duration = perf_counter() - started
    summary = {
        "artifact_type": "tg_qa_legal_intent_candidate_extractor_run_summary",
        "generated_at": completed_at,
        "canonicalization_evidence_path": str(canonicalization_evidence_path),
        "pair_benchmark_path": str(pair_benchmark_path or ""),
        "output_path": str(output_path),
        "summary_output_path": str(summary_output_path),
        "extractor_run_id": extractor_run_id,
        "endpoint_shape": _redacted_endpoint_shape(endpoint_url),
        "provider": provider,
        "runtime_contour": runtime_contour,
        "backend": backend,
        "model_id": model_id,
        "api_key_env": api_key_env,
        "auth_mode": "bearer_env" if api_key_env else "none",
        "structured_output_method": structured_output_method,
        "extra_body_keys": sorted(extra_body.keys()) if isinstance(extra_body, Mapping) else [],
        "stop_on_failure": stop_on_failure,
        "stop_after_consecutive_provider_failures": stop_after_consecutive_provider_failures,
        "stopped_by_provider_failure_guard": stopped_by_provider_failure_guard,
        "provider_failure_guard_trigger": provider_failure_guard_trigger,
        "consecutive_provider_failure_count": consecutive_provider_failure_count,
        "unprocessed_count_due_to_provider_failure_guard": (
            len(selected_evidence) - counts.get("processed", 0) if stopped_by_provider_failure_guard else 0
        ),
        "resume": resume,
        "progress": progress,
        "provider_max_attempts": provider_max_attempts,
        "provider_retry_forever": provider_max_attempts == 0,
        "provider_retry_delay_seconds": provider_retry_delay_seconds,
        "max_items": max_items,
        "max_tokens": max_tokens,
        "timeout_seconds": timeout_seconds,
        "requested_item_count": len(selected_evidence),
        "remaining_evidence_count_before_run": len(remaining_evidence),
        "available_included_evidence_count": len(all_evidence),
        "scoped_evidence_count": len(evidence),
        "pair_benchmark_requested_evidence_count": len(scoped_evidence_ids or set()),
        "pair_benchmark_missing_evidence_count": len((scoped_evidence_ids or set()) - available_evidence_ids),
        "processed_count": counts.get("processed", 0),
        "completed_count": counts.get("completed", 0),
        "failed_count": counts.get("failed", 0),
        "skipped_count": counts.get("skipped", 0),
        "provider_retry_count": counts.get("provider_retry", 0),
        "provider_retry_exhausted_count": counts.get("provider_retry_exhausted", 0),
        "resumed_existing_count": len(resume_state["processed_task_ids"]),
        "existing_status_counts": dict(sorted(resume_state["status_counts"].items())),
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": round(duration, 3),
        "items_per_second": round(len(selected_evidence) / duration, 3) if duration > 0 else 0,
        "policy_version": LEGAL_INTENT_EXTRACTOR_RUN_POLICY_VERSION,
        "prompt_version": LEGAL_INTENT_EXTRACTOR_PROMPT_VERSION,
        "trust_boundary": "llm_legal_intent_candidates_are_review_evidence_only",
    }
    summary.update(_operator_runtime_summary(records))
    _write_json(summary_output_path, summary)
    return {"results": records, "summary": summary}


def import_tg_qa_legal_intent_candidates(
    *,
    canonicalization_evidence_path: str | Path,
    candidates_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
) -> dict[str, Any]:
    """Import structured legal-intent candidates for canonical questions."""

    evidence_records = [
        _legal_intent_source_evidence_record(item)
        for item in _read_jsonl(canonicalization_evidence_path)
        if _included_canonical_evidence(item)
    ]
    by_evidence_id = {str(item.get("canonicalization_evidence_id", "")): item for item in evidence_records}
    by_candidate_id = {str(item.get("candidate_id", "")): item for item in evidence_records}
    raw_records = _read_jsonl(candidates_path)
    records: list[dict[str, Any]] = []
    seen_evidence_ids: set[str] = set()
    counts = Counter()

    for raw in raw_records:
        record = _legal_intent_candidate_record(
            raw,
            evidence_by_id=by_evidence_id,
            evidence_by_candidate_id=by_candidate_id,
        )
        evidence_id = str(record.get("canonicalization_evidence_id", ""))
        if record.get("status") != "failed" and evidence_id in seen_evidence_ids:
            record["status"] = "failed"
            record["failure_reason"] = "duplicate_legal_intent_candidate_for_evidence"
        if record.get("status") == "failed":
            counts["failed"] += 1
        else:
            seen_evidence_ids.add(evidence_id)
            counts["completed"] += 1
        records.append(record)

    _ensure_public_payload(records)
    _write_jsonl(output_path, records)
    summary = {
        "artifact_type": "tg_qa_legal_intent_candidate_import_summary",
        "generated_at": _utc_timestamp(),
        "source_canonicalization_evidence_path": str(canonicalization_evidence_path),
        "source_legal_intent_candidate_path": str(candidates_path),
        "output_path": str(output_path),
        "policy_version": LEGAL_INTENT_CANDIDATE_POLICY_VERSION,
        "processed_count": len(raw_records),
        "completed_count": counts.get("completed", 0),
        "failed_count": counts.get("failed", 0),
        "counts_by_law_area": _counts(str(item.get("law_area", "")) for item in records if item.get("status") != "failed"),
        "counts_by_validation_flag": _counts(
            flag for item in records for flag in _as_string_list(item.get("validation_flags", []))
        ),
        "trust_boundary": "legal_intent_candidates_are_review_evidence_only",
    }
    _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def import_tg_qa_legal_intent_pair_decisions(
    *,
    pair_benchmark_path: str | Path,
    decisions_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
) -> dict[str, Any]:
    """Import structured legal-intent pair decisions."""

    benchmark = {str(item.get("pair_id", "")): item for item in _read_jsonl(pair_benchmark_path)}
    raw_decisions = _read_decision_records(decisions_path)
    records: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    counts = Counter()

    for raw in raw_decisions:
        record = _legal_intent_pair_decision_record(raw, benchmark=benchmark)
        key = (str(record.get("pair_id", "")), str(record.get("decision_source", "")))
        if record.get("status") != "failed" and key in seen_keys:
            record["status"] = "failed"
            record["failure_reason"] = "duplicate_pair_decision_for_source"
        if record.get("status") == "failed":
            counts["failed"] += 1
        else:
            seen_keys.add(key)
            counts["completed"] += 1
            counts[str(record.get("pair_class", ""))] += 1
        records.append(record)

    _ensure_public_payload(records)
    _write_jsonl(output_path, records)
    summary = {
        "artifact_type": "tg_qa_legal_intent_pair_decision_import_summary",
        "generated_at": _utc_timestamp(),
        "source_pair_benchmark_path": str(pair_benchmark_path),
        "source_pair_decisions_path": str(decisions_path),
        "output_path": str(output_path),
        "policy_version": LEGAL_INTENT_PAIR_POLICY_VERSION,
        "processed_count": len(raw_decisions),
        "completed_count": counts.get("completed", 0),
        "failed_count": counts.get("failed", 0),
        "counts_by_pair_class": _counts(
            str(item.get("pair_class", "")) for item in records if item.get("status") != "failed"
        ),
        "counts_by_decision_source": _counts(
            str(item.get("decision_source", "")) for item in records if item.get("status") != "failed"
        ),
        "counts_by_validation_flag": _counts(
            flag for item in records for flag in _as_string_list(item.get("validation_flags", []))
        ),
        "trust_boundary": "legal_intent_pair_decisions_are_review_evidence_only",
    }
    _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def build_tg_qa_legal_intent_similarity_baseline(
    *,
    pair_benchmark_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    embedding_records_path: str | Path | None = None,
    decision_source: str = "similarity_baseline_cosine_recos_v1",
    exact_duplicate_threshold: float = 0.97,
    same_intent_threshold: float = 0.90,
    related_threshold: float = 0.80,
) -> dict[str, Any]:
    """Emit a deliberately simple cosine+recos pair decision baseline."""

    pairs = _read_jsonl(pair_benchmark_path)
    embedding_vectors = _legal_intent_embedding_vectors_by_evidence_role(embedding_records_path)
    records: list[dict[str, Any]] = []
    recos_available_count = 0
    for pair in pairs:
        record = _legal_intent_similarity_baseline_record(
            pair,
            embedding_vectors=embedding_vectors,
            decision_source=decision_source,
            exact_duplicate_threshold=exact_duplicate_threshold,
            same_intent_threshold=same_intent_threshold,
            related_threshold=related_threshold,
        )
        if _float_value(record.get("runtime_metadata", {}).get("recos_canonical_question_score", 0.0)):
            recos_available_count += 1
        records.append(record)

    _ensure_public_payload(records)
    _write_jsonl(output_path, records)
    summary = {
        "artifact_type": "tg_qa_legal_intent_similarity_baseline_summary",
        "generated_at": _utc_timestamp(),
        "pair_benchmark_path": str(pair_benchmark_path),
        "embedding_records_path": str(embedding_records_path or ""),
        "output_path": str(output_path),
        "summary_output_path": str(summary_output_path),
        "decision_source": decision_source,
        "policy_version": LEGAL_INTENT_SIMILARITY_BASELINE_POLICY_VERSION,
        "exact_duplicate_threshold": exact_duplicate_threshold,
        "same_intent_threshold": same_intent_threshold,
        "related_threshold": related_threshold,
        "processed_count": len(records),
        "completed_count": sum(1 for item in records if item.get("status") == "completed"),
        "recos_available_count": recos_available_count,
        "counts_by_pair_class": _counts(str(item.get("pair_class", "")) for item in records),
        "trust_boundary": "similarity_baseline_is_diagnostic_only_not_legal_truth",
    }
    _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def build_tg_qa_legal_intent_slot_comparator_decisions(
    *,
    pair_benchmark_path: str | Path,
    legal_intent_candidates_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    decision_source: str = "legal_slot_comparator_v1",
) -> dict[str, Any]:
    """Emit deterministic pair decisions from structured legal-intent slots."""

    pairs = _read_jsonl(pair_benchmark_path)
    candidates = [
        item for item in _read_jsonl(legal_intent_candidates_path) if str(item.get("status", "")) == "completed"
    ]
    candidates_by_evidence_id = {
        str(item.get("canonicalization_evidence_id", "")): item
        for item in candidates
        if str(item.get("canonicalization_evidence_id", ""))
    }
    records = [
        _legal_intent_slot_comparator_record(
            pair,
            candidates_by_evidence_id=candidates_by_evidence_id,
            decision_source=decision_source,
        )
        for pair in pairs
    ]

    _ensure_public_payload(records)
    _write_jsonl(output_path, records)
    summary = {
        "artifact_type": "tg_qa_legal_intent_slot_comparator_summary",
        "generated_at": _utc_timestamp(),
        "pair_benchmark_path": str(pair_benchmark_path),
        "legal_intent_candidates_path": str(legal_intent_candidates_path),
        "output_path": str(output_path),
        "summary_output_path": str(summary_output_path),
        "decision_source": decision_source,
        "policy_version": LEGAL_INTENT_SLOT_COMPARATOR_POLICY_VERSION,
        "processed_count": len(records),
        "completed_count": sum(1 for item in records if item.get("status") == "completed"),
        "counts_by_pair_class": _counts(str(item.get("pair_class", "")) for item in records),
        "counts_by_validation_flag": _counts(
            flag for item in records for flag in _as_string_list(item.get("validation_flags", []))
        ),
        "trust_boundary": "slot_comparator_decisions_are_diagnostic_review_evidence_only",
    }
    _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def run_tg_qa_legal_intent_pair_judge_batch(
    *,
    pair_benchmark_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    endpoint_url: str,
    model_id: str,
    judge_run_id: str,
    legal_intent_candidates_path: str | Path | None = None,
    provider: str = "openai",
    max_items: int = 0,
    timeout_seconds: int = 180,
    max_tokens: int = 1536,
    structured_output_method: str = "json_mode",
    api_key_env: str = "",
    extra_body: Mapping[str, Any] | None = None,
    stop_on_failure: bool = False,
    runtime_contour: str = "operator_managed_pair_judge",
    backend: str = "opencode",
    resume: bool = True,
    provider_max_attempts: int = 3,
    provider_retry_delay_seconds: float = 2.0,
    stop_after_consecutive_provider_failures: int = 0,
    progress: bool = False,
    chain: Any | None = None,
) -> dict[str, Any]:
    """Run a structured LLM judge over legal-intent pair benchmark records."""

    if provider not in {"anthropic", "openai"}:
        raise ValueError("provider must be anthropic or openai")
    if structured_output_method not in {"function_calling", "json_mode", "json_schema"}:
        raise ValueError("structured_output_method must be function_calling, json_mode, or json_schema")
    if provider_max_attempts < 0:
        raise ValueError("provider_max_attempts must be non-negative")
    if provider_retry_delay_seconds < 0:
        raise ValueError("provider_retry_delay_seconds must be non-negative")
    if stop_after_consecutive_provider_failures < 0:
        raise ValueError("stop_after_consecutive_provider_failures must be non-negative")

    pairs = _read_jsonl(pair_benchmark_path)
    candidates_by_evidence_id = _legal_intent_candidates_by_evidence_id(legal_intent_candidates_path)
    run_items = [_legal_intent_pair_operator_item(pair) for pair in pairs]
    resume_state = _load_existing_operator_results(output_path, run_items) if resume else _empty_operator_resume_state()
    remaining_pairs = [
        pair for pair in pairs if str(pair.get("pair_id", "")) not in resume_state["processed_task_ids"]
    ]
    selected_pairs = remaining_pairs[:max_items] if max_items > 0 else remaining_pairs
    started_at = _utc_timestamp()
    started = perf_counter()
    runner = chain or _build_legal_intent_pair_judge_chain(
        provider=provider,
        endpoint_url=endpoint_url,
        model_id=model_id,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        structured_output_method=structured_output_method,
        api_key_env=api_key_env,
        extra_body=extra_body,
    )
    counts = Counter()
    records: list[dict[str, Any]] = []
    progress_line = _OperatorProgress(
        enabled=progress,
        label="tg-qa-legal-intent-pair-judge-run",
        total=len(selected_pairs),
    )
    output_handle = _open_jsonl_stream(output_path, append=resume and bool(resume_state["processed_task_ids"]))
    consecutive_provider_failure_key = ""
    consecutive_provider_failure_count = 0
    stopped_by_provider_failure_guard = False
    provider_failure_guard_trigger = ""
    try:
        for item_index, pair in enumerate(selected_pairs, start=1):
            operator_item = _legal_intent_pair_operator_item(pair)
            progress_line.update(
                item_index - 1,
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                skipped=counts.get("skipped", 0),
                last_status="request",
                detail=_operator_progress_detail("request", item_index, len(selected_pairs), operator_item),
            )
            counts["processed"] += 1
            compact_payload = _compact_legal_intent_pair_judge_payload(
                pair,
                candidates_by_evidence_id=candidates_by_evidence_id,
            )
            attempts_used = 0
            item_started = perf_counter()
            last_raw_result: Any = None
            while True:
                attempts_used += 1
                try:
                    raw_result = runner.invoke({"pair_payload": _json_for_prompt(compact_payload)})
                    last_raw_result = raw_result
                    record = _legal_intent_pair_judge_record_from_structured_output(
                        raw_result,
                        pair,
                        judge_run_id=judge_run_id,
                        runtime_contour=runtime_contour,
                        backend=backend,
                        model_id=model_id,
                    )
                    break
                except Exception as exc:  # pragma: no cover - live endpoint failures vary
                    failure_reason = _operator_error_reason(exc)
                    if _operator_should_retry_exception(exc) and _operator_retry_allowed(
                        attempts_used,
                        provider_max_attempts,
                    ):
                        counts["provider_retry"] += 1
                        progress_line.update(
                            item_index - 1,
                            completed=counts.get("completed", 0),
                            failed=counts.get("failed", 0),
                            skipped=counts.get("skipped", 0),
                            last_status="retry",
                            detail=_operator_progress_detail(
                                f"retry {attempts_used + 1}/{_operator_retry_limit_label(provider_max_attempts)}",
                                item_index,
                                len(selected_pairs),
                                operator_item,
                                failure_reason=failure_reason,
                            ),
                        )
                        if provider_retry_delay_seconds > 0:
                            sleep(provider_retry_delay_seconds)
                        continue
                    if _operator_should_retry_exception(exc):
                        counts["provider_retry_exhausted"] += 1
                    record = _failed_legal_intent_pair_judge_record(
                        pair,
                        judge_run_id=judge_run_id,
                        failure_reason=_operator_failure_reason_with_attempts(failure_reason, attempts_used),
                        runtime_contour=runtime_contour,
                        backend=backend,
                        model_id=model_id,
                    )
                    break
            record = _attach_runtime_metadata(
                record,
                _operator_record_runtime_metadata(
                    last_raw_result,
                    request_duration_seconds=perf_counter() - item_started,
                    attempts_used=attempts_used,
                ),
            )
            counts[str(record.get("status", "failed"))] += 1
            records.append(record)
            _write_jsonl_stream_record(output_handle, record)
            progress_line.update(
                item_index,
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                skipped=counts.get("skipped", 0),
                last_status=str(record.get("status", "done")),
                detail=_operator_progress_detail(
                    str(record.get("status", "done")),
                    item_index,
                    len(selected_pairs),
                    operator_item,
                    failure_reason=str(record.get("failure_reason", "")),
                ),
            )
            provider_failure_key = _operator_provider_failure_guard_key(record)
            if provider_failure_key:
                if provider_failure_key == consecutive_provider_failure_key:
                    consecutive_provider_failure_count += 1
                else:
                    consecutive_provider_failure_key = provider_failure_key
                    consecutive_provider_failure_count = 1
            else:
                consecutive_provider_failure_key = ""
                consecutive_provider_failure_count = 0
            if (
                stop_after_consecutive_provider_failures > 0
                and consecutive_provider_failure_count >= stop_after_consecutive_provider_failures
            ):
                stopped_by_provider_failure_guard = True
                provider_failure_guard_trigger = consecutive_provider_failure_key
                progress_line.update(
                    item_index,
                    completed=counts.get("completed", 0),
                    failed=counts.get("failed", 0),
                    skipped=counts.get("skipped", 0),
                    last_status="stopped",
                    detail=(
                        "provider_failure_guard "
                        f"{consecutive_provider_failure_count}/"
                        f"{stop_after_consecutive_provider_failures} "
                        f"{provider_failure_guard_trigger}"
                    ),
                )
                break
            if stop_on_failure and str(record.get("status", "")) == "failed":
                break
    finally:
        output_handle.close()
        progress_line.finish(
            counts.get("processed", 0),
            completed=counts.get("completed", 0),
            failed=counts.get("failed", 0),
            skipped=counts.get("skipped", 0),
        )

    completed_at = _utc_timestamp()
    duration = perf_counter() - started
    summary = {
        "artifact_type": "tg_qa_legal_intent_pair_judge_run_summary",
        "generated_at": completed_at,
        "pair_benchmark_path": str(pair_benchmark_path),
        "legal_intent_candidates_path": str(legal_intent_candidates_path or ""),
        "output_path": str(output_path),
        "summary_output_path": str(summary_output_path),
        "judge_run_id": judge_run_id,
        "endpoint_shape": _redacted_endpoint_shape(endpoint_url),
        "provider": provider,
        "runtime_contour": runtime_contour,
        "backend": backend,
        "model_id": model_id,
        "api_key_env": api_key_env,
        "auth_mode": "bearer_env" if api_key_env else "none",
        "structured_output_method": structured_output_method,
        "extra_body_keys": sorted(extra_body.keys()) if isinstance(extra_body, Mapping) else [],
        "stop_on_failure": stop_on_failure,
        "stop_after_consecutive_provider_failures": stop_after_consecutive_provider_failures,
        "stopped_by_provider_failure_guard": stopped_by_provider_failure_guard,
        "provider_failure_guard_trigger": provider_failure_guard_trigger,
        "consecutive_provider_failure_count": consecutive_provider_failure_count,
        "unprocessed_count_due_to_provider_failure_guard": (
            len(selected_pairs) - counts.get("processed", 0) if stopped_by_provider_failure_guard else 0
        ),
        "resume": resume,
        "progress": progress,
        "provider_max_attempts": provider_max_attempts,
        "provider_retry_forever": provider_max_attempts == 0,
        "provider_retry_delay_seconds": provider_retry_delay_seconds,
        "max_items": max_items,
        "max_tokens": max_tokens,
        "timeout_seconds": timeout_seconds,
        "requested_item_count": len(selected_pairs),
        "remaining_pair_count_before_run": len(remaining_pairs),
        "available_pair_count": len(pairs),
        "processed_count": counts.get("processed", 0),
        "completed_count": counts.get("completed", 0),
        "failed_count": counts.get("failed", 0),
        "skipped_count": counts.get("skipped", 0),
        "provider_retry_count": counts.get("provider_retry", 0),
        "provider_retry_exhausted_count": counts.get("provider_retry_exhausted", 0),
        "resumed_existing_count": len(resume_state["processed_task_ids"]),
        "existing_status_counts": dict(sorted(resume_state["status_counts"].items())),
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": round(duration, 3),
        "items_per_second": round(len(selected_pairs) / duration, 3) if duration > 0 else 0,
        "policy_version": LEGAL_INTENT_PAIR_JUDGE_RUN_POLICY_VERSION,
        "prompt_version": LEGAL_INTENT_PAIR_JUDGE_PROMPT_VERSION,
        "trust_boundary": "llm_pair_judge_results_are_review_evidence_only",
    }
    summary.update(_operator_runtime_summary(records))
    _write_json(summary_output_path, summary)
    return {"results": records, "summary": summary}


def export_tg_qa_legal_intent_pair_review_html(
    *,
    pair_benchmark_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    pair_decisions_path: str | Path | None = None,
    review_labels_path: str | Path | None = None,
    review_filter: str = "all",
) -> dict[str, Any]:
    """Export dependency-free HTML for manual pair review."""

    if review_filter not in {"all", "unreviewed", "reviewed"}:
        raise ValueError(f"invalid_review_filter:{review_filter}")

    pairs = _read_jsonl(pair_benchmark_path)
    decisions = _read_jsonl(pair_decisions_path) if pair_decisions_path else []
    review_labels = _read_jsonl(review_labels_path) if review_labels_path else []
    labels_by_pair: dict[str, dict[str, Any]] = {}
    for label in review_labels:
        if str(label.get("status", "")) != "completed":
            continue
        pair_id = str(label.get("pair_id", ""))
        if pair_id and pair_id not in labels_by_pair:
            labels_by_pair[pair_id] = label

    decisions_by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for decision in decisions:
        if str(decision.get("status", "")) == "failed":
            continue
        decisions_by_pair[str(decision.get("pair_id", ""))].append(decision)
    selected_pairs = []
    for pair in pairs:
        pair_id = str(pair.get("pair_id", ""))
        is_reviewed = pair_id in labels_by_pair
        if review_filter == "unreviewed" and is_reviewed:
            continue
        if review_filter == "reviewed" and not is_reviewed:
            continue
        selected_pairs.append(pair)

    cards = [
        _legal_intent_review_card(
            pair,
            decisions_by_pair.get(str(pair.get("pair_id", "")), []),
            review_label=labels_by_pair.get(str(pair.get("pair_id", ""))),
        )
        for pair in selected_pairs
    ]
    _write_text(output_path, _legal_intent_review_html(cards))
    summary = {
        "artifact_type": "tg_qa_legal_intent_pair_review_html_summary",
        "generated_at": _utc_timestamp(),
        "pair_benchmark_path": str(pair_benchmark_path),
        "pair_decisions_path": str(pair_decisions_path or ""),
        "review_labels_path": str(review_labels_path or ""),
        "review_filter": review_filter,
        "html_output_path": str(output_path),
        "card_count": len(cards),
        "available_pair_count": len(pairs),
        "available_reviewed_label_count": len(labels_by_pair),
        "included_reviewed_label_count": sum(1 for item in cards if item.get("review_label")),
        "excluded_reviewed_label_count": sum(
            1 for item in pairs if str(item.get("pair_id", "")) in labels_by_pair
        )
        - sum(1 for item in cards if item.get("review_label")),
        "cards_with_decisions_count": sum(1 for item in cards if item.get("decisions")),
        "review_ui_mode": "static_html_with_client_side_jsonl_export",
        "trust_boundary": "pair_review_labels_require_human_export_and_import",
    }
    _write_json(summary_output_path, summary)
    return {"cards": cards, "summary": summary}


def import_tg_qa_legal_intent_pair_review_labels(
    *,
    pair_benchmark_path: str | Path,
    labels_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
) -> dict[str, Any]:
    """Import human labels for legal-intent pair benchmark records."""

    benchmark = {str(item.get("pair_id", "")): item for item in _read_jsonl(pair_benchmark_path)}
    raw_labels = _read_decision_records(labels_path)
    records: list[dict[str, Any]] = []
    seen_by_pair: dict[str, str] = {}
    counts = Counter()

    for raw in raw_labels:
        record = _legal_intent_pair_review_label_record(raw, benchmark=benchmark)
        pair_id = str(record.get("pair_id", ""))
        fingerprint = _legal_intent_label_fingerprint(record)
        if record.get("status") != "failed" and pair_id in seen_by_pair:
            if seen_by_pair[pair_id] == fingerprint:
                record["status"] = "skipped"
                record["failure_reason"] = "duplicate_identical_pair_review_label"
                counts["skipped"] += 1
            else:
                record["status"] = "failed"
                record["failure_reason"] = "conflicting_pair_review_label"
                counts["failed"] += 1
        elif record.get("status") == "failed":
            counts["failed"] += 1
        else:
            seen_by_pair[pair_id] = fingerprint
            counts["completed"] += 1
        records.append(record)

    _ensure_public_payload(records)
    _write_jsonl(output_path, records)
    summary = {
        "artifact_type": "tg_qa_legal_intent_pair_review_label_import_summary",
        "generated_at": _utc_timestamp(),
        "source_pair_benchmark_path": str(pair_benchmark_path),
        "source_review_labels_path": str(labels_path),
        "output_path": str(output_path),
        "review_policy_version": LEGAL_INTENT_REVIEW_POLICY_VERSION,
        "processed_count": len(raw_labels),
        "completed_count": counts.get("completed", 0),
        "failed_count": counts.get("failed", 0),
        "skipped_count": counts.get("skipped", 0),
        "counts_by_pair_class": _counts(
            str(item.get("pair_class", "")) for item in records if item.get("status") == "completed"
        ),
        "trust_boundary": "pair_review_labels_are_human_review_artifacts",
    }
    _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def build_tg_qa_legal_intent_equivalence_report(
    *,
    pair_benchmark_path: str | Path,
    pair_decisions_path: str | Path,
    review_labels_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
) -> dict[str, Any]:
    """Evaluate legal-intent pair decisions against reviewed labels."""

    benchmark = {str(item.get("pair_id", "")): item for item in _read_jsonl(pair_benchmark_path)}
    decisions = [item for item in _read_jsonl(pair_decisions_path) if str(item.get("status", "")) != "failed"]
    labels = [item for item in _read_jsonl(review_labels_path) if str(item.get("status", "")) == "completed"]
    labels_by_pair = {str(item.get("pair_id", "")): item for item in labels}
    decision_pair_ids = {str(item.get("pair_id", "")) for item in decisions}
    evaluated_labels_by_pair = {
        pair_id: label for pair_id, label in labels_by_pair.items() if pair_id in decision_pair_ids
    }
    comparison_records = [
        _legal_intent_evaluation_record(decision, labels_by_pair.get(str(decision.get("pair_id", ""))), benchmark)
        for decision in decisions
    ]
    _ensure_public_payload(comparison_records)
    _write_jsonl(output_path, comparison_records)

    label_count = len(labels_by_pair)
    false_duplicate_risks = [
        item for item in comparison_records if _bool_value(item.get("false_duplicate_risk", False))
    ][:25]
    false_separation_risks = [
        item for item in comparison_records if _bool_value(item.get("false_separation_risk", False))
    ][:25]
    hard_negatives = [
        _hard_negative_summary(pair_id, benchmark[pair_id], labels_by_pair[pair_id])
        for pair_id in sorted(evaluated_labels_by_pair)
        if pair_id in benchmark
        and _legal_intent_hard_negative(benchmark[pair_id], evaluated_labels_by_pair[pair_id])
    ][:25]
    evaluated_label_count = len(evaluated_labels_by_pair)
    method_suitability = _legal_intent_method_suitability(comparison_records, evaluated_label_count)
    summary = {
        "artifact_type": "tg_qa_legal_intent_equivalence_evaluation_summary",
        "generated_at": _utc_timestamp(),
        "pair_benchmark_path": str(pair_benchmark_path),
        "pair_decisions_path": str(pair_decisions_path),
        "review_labels_path": str(review_labels_path),
        "output_path": str(output_path),
        "summary_output_path": str(summary_output_path),
        "evaluation_policy_version": LEGAL_INTENT_EVALUATION_POLICY_VERSION,
        "pair_count": len(benchmark),
        "decision_count": len(decisions),
        "available_reviewed_label_count": label_count,
        "reviewed_label_count": evaluated_label_count,
        "comparison_count": len(comparison_records),
        "counts_by_label_pair_class": _counts(
            str(item.get("pair_class", "")) for item in evaluated_labels_by_pair.values()
        ),
        "counts_by_decision_pair_class": _counts(str(item.get("pair_class", "")) for item in decisions),
        "counts_by_decision_source": _counts(str(item.get("decision_source", "")) for item in decisions),
        "counts_by_match_status": _counts(str(item.get("match_status", "")) for item in comparison_records),
        "counts_by_question_equivalence_match_status": _counts(
            str(item.get("question_equivalence_match_status", "")) for item in comparison_records
        ),
        "counts_by_answer_equivalence_match_status": _counts(
            str(item.get("answer_equivalence_match_status", "")) for item in comparison_records
        ),
        "counts_by_question_reuse_safety_match_status": _counts(
            str(item.get("question_reuse_safety_match_status", "")) for item in comparison_records
        ),
        "counts_by_answer_reuse_safety_match_status": _counts(
            str(item.get("answer_reuse_safety_match_status", "")) for item in comparison_records
        ),
        "hard_negative_count": len(hard_negatives),
        "false_duplicate_risk_count": len(false_duplicate_risks),
        "false_separation_risk_count": len(false_separation_risks),
        "high_similarity_hard_negatives": hard_negatives,
        "false_duplicate_risk_examples": false_duplicate_risks,
        "false_separation_risk_examples": false_separation_risks,
        "insufficient_label_warnings": _legal_intent_insufficient_label_warnings(
            list(evaluated_labels_by_pair.values())
        ),
        "method_suitability": method_suitability,
        "trust_boundary": "equivalence_evaluation_does_not_approve_automatic_answer_reuse",
    }
    _write_json(summary_output_path, summary)
    return {"records": comparison_records, "summary": summary}


def verify_tg_question_canonicalization_boundaries(
    *,
    source_path: str | Path = "src/evaluation/tg_question_canonicalization.py",
    gitignore_path: str | Path = ".gitignore",
) -> dict[str, Any]:
    """Verify 007 remains a file-artifact evaluation workflow."""

    source = Path(source_path).read_text(encoding="utf-8")
    gitignore = Path(gitignore_path).read_text(encoding="utf-8")
    source_to_scan = "\n".join(
        line
        for line in source.splitlines()
        if "forbidden_source_patterns" not in line
        and "graph_mutation_import" not in line
        and "neo4j_import" not in line
        and "chatbot_or_answer_synthesis" not in line
        and "raw_tg_input_path" not in line
        and line.strip() != '"data/tg/",'
        and '"data/tg/" in lowered' not in line
        and "agent_or_orchestration_framework_dependency" not in line
    )
    forbidden_source_patterns = {
        "graph_mutation_import": r"^\s*from\s+graph\.|^\s*import\s+graph\.",
        "neo4j_import": r"^\s*from\s+neo4j|^\s*import\s+neo4j",
        "chatbot_or_answer_synthesis": r"chatbot|answer_generation|generated_answer",
        "raw_tg_input_path": r"(?<!\")data/tg/(?!\")",
        "agent_or_orchestration_framework_dependency": (
            r"^\s*from\s+langgraph|^\s*import\s+langgraph"
            r"|^\s*from\s+langchain\.(?:agents|chains|experimental)"
            r"|^\s*import\s+langchain(?:\s|$)"
        ),
    }
    failed = [
        name
        for name, pattern in forbidden_source_patterns.items()
        if re.search(pattern, source_to_scan, flags=re.IGNORECASE | re.MULTILINE)
    ]
    required_ignore_patterns = [
        "data/tg/",
        "data/evaluation/",
        "data/evaluation/tg_qa_canonicalization/*.json",
        "data/evaluation/tg_qa_canonicalization/*.jsonl",
        "data/evaluation/tg_qa_canonical_embeddings/*.json",
        "data/evaluation/tg_qa_canonical_embeddings/*.jsonl",
        "data/evaluation/tg_qa_issue_clusters/*.json",
        "data/evaluation/tg_qa_issue_clusters/*.jsonl",
        "data/evaluation/tg_qa_question_bank/*.json",
        "data/evaluation/tg_qa_question_bank/*.jsonl",
        "data/evaluation/tg_qa_question_bank/*.md",
        "data/evaluation/tg_qa_question_bank/*.tsv",
        "data/evaluation/tg_qa_canonical_coverage/*.json",
        "data/evaluation/tg_qa_canonical_coverage/*.jsonl",
        "data/evaluation/tg_qa_legal_intent_equivalence/*.json",
        "data/evaluation/tg_qa_legal_intent_equivalence/*.jsonl",
        "data/evaluation/tg_qa_legal_intent_equivalence/*.html",
    ]
    missing_ignore_patterns = [pattern for pattern in required_ignore_patterns if pattern not in gitignore]
    status = "passed" if not failed and not missing_ignore_patterns else "failed"
    return {
        "artifact_type": "tg_question_canonicalization_boundary_verification",
        "generated_at": _utc_timestamp(),
        "status": status,
        "failed_source_checks": failed,
        "missing_ignore_patterns": missing_ignore_patterns,
        "source_path": str(source_path),
        "gitignore_path": str(gitignore_path),
    }


def _group_records(
    records: Sequence[Mapping[str, Any]],
    *,
    key_func,
) -> list[list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = str(key_func(record))
        if key:
            grouped[key].append(dict(record))
    return [items for _, items in sorted(grouped.items()) if len(items) > 1]


def _all_pairs(records: Sequence[Mapping[str, Any]]) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    items = [dict(item) for item in records]
    for left_index in range(len(items)):
        for right_index in range(left_index + 1, len(items)):
            yield items[left_index], items[right_index]


def _balanced_legal_intent_random_negative_pairs(
    records: Sequence[Mapping[str, Any]],
    *,
    existing_pair_ids: set[str],
    max_pairs: int,
) -> list[dict[str, Any]]:
    """Select deterministic negative controls without pinning one anchor record."""

    if max_pairs <= 0:
        return []
    items = sorted(
        [dict(item) for item in records],
        key=lambda item: str(item.get("canonicalization_evidence_id", "")),
    )
    if len(items) < 2:
        return []

    emitted: list[dict[str, Any]] = []
    emitted_pair_ids: set[str] = set()
    degree_by_evidence_id: Counter[str] = Counter()
    item_count = len(items)
    degree_cap = max(1, (max_pairs * 2 + item_count - 1) // item_count)

    while len(emitted) < max_pairs and degree_cap <= max(max_pairs, item_count):
        added_this_round = False
        for offset in range(1, item_count):
            for left_index, left in enumerate(items):
                if len(emitted) >= max_pairs:
                    return emitted
                right = items[(left_index + offset) % item_count]
                left_id = str(left.get("canonicalization_evidence_id", ""))
                right_id = str(right.get("canonicalization_evidence_id", ""))
                if not left_id or not right_id or left_id == right_id:
                    continue
                if degree_by_evidence_id[left_id] >= degree_cap:
                    continue
                if degree_by_evidence_id[right_id] >= degree_cap:
                    continue
                if str(left.get("legal_issue_frame_slug", "")) == str(right.get("legal_issue_frame_slug", "")):
                    continue
                if str(left.get("law_area", "")) == str(right.get("law_area", "")):
                    continue
                pair = _legal_intent_pair_record(left, right, pair_source_reasons=["random_negative"])
                pair_id = str(pair.get("pair_id", ""))
                if pair_id in existing_pair_ids or pair_id in emitted_pair_ids:
                    continue
                emitted.append(pair)
                emitted_pair_ids.add(pair_id)
                degree_by_evidence_id[left_id] += 1
                degree_by_evidence_id[right_id] += 1
                added_this_round = True
            if len(emitted) >= max_pairs:
                return emitted
        if not added_this_round and degree_cap >= max(max_pairs, item_count):
            break
        degree_cap += 1
    return emitted


def _legal_intent_pair_id(left_evidence_id: str, right_evidence_id: str) -> str:
    left, right = sorted([left_evidence_id, right_evidence_id])
    return _stable_id("tg-legal-intent-pair", left, right)


def _legal_intent_source_evidence_record(evidence: Mapping[str, Any]) -> dict[str, Any]:
    record = dict(evidence)
    evidence_id = str(record.get("canonicalization_evidence_id", ""))
    if not evidence_id:
        evidence_id = str(record.get("dataset_record_id", ""))
    if not evidence_id:
        evidence_id = _stable_id(
            "tg-question-canonicalization-evidence",
            str(record.get("canonicalization_run_id", "")),
            str(record.get("task_id", "")),
            str(record.get("candidate_id", "")),
        )
    record["canonicalization_evidence_id"] = evidence_id
    return record


def _ordered_pair_evidence(left: Mapping[str, Any], right: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    left_id = str(left.get("canonicalization_evidence_id", ""))
    right_id = str(right.get("canonicalization_evidence_id", ""))
    return (left, right) if left_id <= right_id else (right, left)


def _legal_intent_pair_record(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    pair_source_reasons: Sequence[str],
    similarity_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    left, right = _ordered_pair_evidence(left, right)
    left_id = str(left.get("canonicalization_evidence_id", ""))
    right_id = str(right.get("canonicalization_evidence_id", ""))
    if not left_id or not right_id or left_id == right_id:
        raise ValueError("pair_requires_two_distinct_canonicalization_evidence_ids")
    canonical_score = 1.0 if _normalized_text(left.get("canonical_question", "")) == _normalized_text(right.get("canonical_question", "")) else 0.0
    issue_score = 1.0 if str(left.get("legal_issue_frame_slug", "")) == str(right.get("legal_issue_frame_slug", "")) else 0.0
    evidence = {
        "canonical_question_score": canonical_score,
        "legal_issue_frame_score": issue_score,
        "embedding_profile_id": "",
    }
    evidence.update(dict(similarity_evidence or {}))
    return {
        "pair_id": _legal_intent_pair_id(left_id, right_id),
        "left_canonicalization_evidence_id": left_id,
        "right_canonicalization_evidence_id": right_id,
        "left_candidate_id": str(left.get("candidate_id", "")),
        "right_candidate_id": str(right.get("candidate_id", "")),
        "pair_source_reasons": sorted(set(_as_string_list(pair_source_reasons))),
        "similarity_evidence": evidence,
        "benchmark_status": "needs_pair_review",
        "left": _legal_intent_pair_side(left),
        "right": _legal_intent_pair_side(right),
        "policy_version": LEGAL_INTENT_BENCHMARK_POLICY_VERSION,
        "provenance": {
            "source_canonicalization_run_ids": sorted(
                {
                    str(left.get("canonicalization_run_id", "")),
                    str(right.get("canonicalization_run_id", "")),
                }
            ),
            "trust_boundary": "pair_is_candidate_not_legal_truth",
        },
    }


def _legal_intent_pair_side(evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "canonicalization_evidence_id": str(evidence.get("canonicalization_evidence_id", "")),
        "candidate_id": str(evidence.get("candidate_id", "")),
        "canonical_question": _redact_private_text(str(evidence.get("canonical_question", ""))),
        "legal_issue_frame": str(evidence.get("legal_issue_frame", "")),
        "legal_issue_frame_slug": str(evidence.get("legal_issue_frame_slug", "")),
        "law_area": str(evidence.get("law_area", "")),
        "authority_context": _as_string_list(evidence.get("authority_context", [])),
        "quality_flags": _as_string_list(evidence.get("quality_flags", [])),
        "question_date": str(evidence.get("question_date", "")),
        "confidence": str(evidence.get("confidence", "")),
    }


def _merge_legal_intent_pair(pairs: dict[str, dict[str, Any]], pair: Mapping[str, Any]) -> None:
    pair_id = str(pair.get("pair_id", ""))
    if not pair_id:
        return
    if pair_id not in pairs:
        pairs[pair_id] = dict(pair)
        return
    existing = pairs[pair_id]
    existing["pair_source_reasons"] = sorted(
        set(_as_string_list(existing.get("pair_source_reasons", []))) | set(_as_string_list(pair.get("pair_source_reasons", [])))
    )
    existing_evidence = dict(existing.get("similarity_evidence", {})) if isinstance(existing.get("similarity_evidence"), Mapping) else {}
    incoming_evidence = dict(pair.get("similarity_evidence", {})) if isinstance(pair.get("similarity_evidence"), Mapping) else {}
    for key, value in incoming_evidence.items():
        if isinstance(value, int | float) and isinstance(existing_evidence.get(key), int | float):
            existing_evidence[key] = max(float(existing_evidence[key]), float(value))
        elif value and not existing_evidence.get(key):
            existing_evidence[key] = value
    existing["similarity_evidence"] = existing_evidence


def _similarity_pair_evidence(
    raw_pair: Mapping[str, Any],
    *,
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    evidence_by_task_id: Mapping[str, Mapping[str, Any]],
    evidence_by_candidate_id: Mapping[str, Mapping[str, Any]],
) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    left_raw = raw_pair.get("left", {})
    right_raw = raw_pair.get("right", {})
    left = _similarity_pair_side_evidence(
        raw_pair,
        left_raw if isinstance(left_raw, Mapping) else {},
        side="left",
        evidence_by_id=evidence_by_id,
        evidence_by_task_id=evidence_by_task_id,
        evidence_by_candidate_id=evidence_by_candidate_id,
    )
    right = _similarity_pair_side_evidence(
        raw_pair,
        right_raw if isinstance(right_raw, Mapping) else {},
        side="right",
        evidence_by_id=evidence_by_id,
        evidence_by_task_id=evidence_by_task_id,
        evidence_by_candidate_id=evidence_by_candidate_id,
    )
    return left, right


def _similarity_pair_side_evidence(
    raw_pair: Mapping[str, Any],
    side_payload: Mapping[str, Any],
    *,
    side: str,
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    evidence_by_task_id: Mapping[str, Mapping[str, Any]],
    evidence_by_candidate_id: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    opposite = "target" if side == "right" else "source"
    evidence_id = str(
        raw_pair.get(
            f"{side}_canonicalization_evidence_id",
            raw_pair.get(
                f"{side}_id",
                raw_pair.get(f"{opposite}_canonicalization_evidence_id", side_payload.get("canonicalization_evidence_id", "")),
            ),
        )
    )
    if evidence_id and evidence_id in evidence_by_id:
        return evidence_by_id[evidence_id]
    task_id = str(side_payload.get("task_id", raw_pair.get(f"{side}_task_id", "")))
    if task_id and task_id in evidence_by_task_id:
        return evidence_by_task_id[task_id]
    candidate_id = str(side_payload.get("candidate_id", raw_pair.get(f"{side}_candidate_id", "")))
    if candidate_id and candidate_id in evidence_by_candidate_id:
        return evidence_by_candidate_id[candidate_id]
    return None


def _similarity_evidence_from_pair(raw_pair: Mapping[str, Any]) -> dict[str, Any]:
    evidence = raw_pair.get("similarity_evidence", {})
    result = dict(evidence) if isinstance(evidence, Mapping) else {}
    for source_key, target_key in (
        ("canonical_question_score", "canonical_question_score"),
        ("question_similarity_score", "canonical_question_score"),
        ("legal_issue_frame_score", "legal_issue_frame_score"),
        ("issue_frame_similarity_score", "legal_issue_frame_score"),
        ("embedding_profile_id", "embedding_profile_id"),
    ):
        if source_key in raw_pair and target_key not in result:
            result[target_key] = raw_pair[source_key]
    return result


def _legal_intent_embedding_vectors_by_evidence_role(
    embedding_records_path: str | Path | None,
) -> dict[tuple[str, str], list[float]]:
    if not embedding_records_path:
        return {}
    vectors: dict[tuple[str, str], list[float]] = {}
    for record in _read_jsonl(embedding_records_path):
        if str(record.get("embedding_status", "")) != "completed":
            continue
        evidence_id = str(record.get("canonicalization_evidence_id", ""))
        candidate_id = str(record.get("candidate_id", ""))
        text_role = str(record.get("text_role", ""))
        vector = record.get("vector", [])
        if not text_role or not isinstance(vector, Sequence) or isinstance(vector, (str, bytes)):
            continue
        try:
            normalized_vector = [float(value) for value in vector]
        except (TypeError, ValueError):
            continue
        if evidence_id:
            vectors[(evidence_id, text_role)] = normalized_vector
        if candidate_id:
            vectors[(f"candidate:{candidate_id}", text_role)] = normalized_vector
    return vectors


def _recos_for_pair_role(
    pair: Mapping[str, Any],
    embedding_vectors: Mapping[tuple[str, str], Sequence[float]],
    text_role: str,
) -> float | None:
    left_id = str(pair.get("left_canonicalization_evidence_id", ""))
    right_id = str(pair.get("right_canonicalization_evidence_id", ""))
    left_candidate_id = str(pair.get("left_candidate_id", ""))
    right_candidate_id = str(pair.get("right_candidate_id", ""))
    left = embedding_vectors.get((left_id, text_role)) or embedding_vectors.get((f"candidate:{left_candidate_id}", text_role))
    right = embedding_vectors.get((right_id, text_role)) or embedding_vectors.get((f"candidate:{right_candidate_id}", text_role))
    if left is None or right is None:
        return None
    return _recos_score(left, right)


def _recos_score(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_abs = sorted((abs(float(value)) for value in left), reverse=True)
    right_abs = sorted((abs(float(value)) for value in right), reverse=True)
    upper = sum(a * b for a, b in zip(left_abs, right_abs))
    if upper <= 0:
        return 0.0
    return max(-1.0, min(1.0, dot / upper))


def _high_similarity_non_equivalent_source(pair: Mapping[str, Any]) -> bool:
    reasons = set(_as_string_list(pair.get("pair_source_reasons", [])))
    evidence = pair.get("similarity_evidence", {}) if isinstance(pair.get("similarity_evidence"), Mapping) else {}
    score = max(
        _float_value(evidence.get("canonical_question_score", 0.0)),
        _float_value(evidence.get("legal_issue_frame_score", 0.0)),
        _float_value(evidence.get("recos_canonical_question_score", 0.0)),
        _float_value(evidence.get("recos_legal_issue_frame_score", 0.0)),
    )
    return score >= 0.85 or any("similarity" in reason or "negative" in reason for reason in reasons)


def _similarity_shared_facts(
    pair: Mapping[str, Any],
    canonical_score: float,
    issue_score: float,
    recos_canonical: float,
    recos_issue: float,
) -> list[str]:
    facts = []
    if canonical_score:
        facts.append(f"canonical_question_cosine:{canonical_score:.3f}")
    if issue_score:
        facts.append(f"legal_issue_frame_cosine:{issue_score:.3f}")
    if recos_canonical:
        facts.append(f"canonical_question_recos:{recos_canonical:.3f}")
    if recos_issue:
        facts.append(f"legal_issue_frame_recos:{recos_issue:.3f}")
    for reason in _as_string_list(pair.get("pair_source_reasons", [])):
        facts.append(f"pair_source:{reason}")
    return facts


def _legal_intent_evidence_ids_from_pair_benchmark(
    pair_benchmark_path: str | Path | None,
) -> set[str] | None:
    if not pair_benchmark_path:
        return None
    evidence_ids: set[str] = set()
    for pair in _read_jsonl(pair_benchmark_path):
        for field_name in (
            "left_canonicalization_evidence_id",
            "right_canonicalization_evidence_id",
        ):
            evidence_id = str(pair.get(field_name, ""))
            if evidence_id:
                evidence_ids.add(evidence_id)
    return evidence_ids


def _legal_intent_candidate_operator_item(evidence: Mapping[str, Any]) -> dict[str, Any]:
    evidence_id = str(evidence.get("canonicalization_evidence_id", ""))
    return {
        "task_id": evidence_id,
        "canonicalization_evidence_id": evidence_id,
        "candidate_id": str(evidence.get("candidate_id", "")),
    }


def _compact_legal_intent_extractor_payload(evidence: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "canonicalization_evidence_id": str(evidence.get("canonicalization_evidence_id", "")),
        "candidate_id": str(evidence.get("candidate_id", "")),
        "canonical_question": _redact_private_text(str(evidence.get("canonical_question", ""))),
        "legal_issue_frame": str(evidence.get("legal_issue_frame", "")),
        "law_area": str(evidence.get("law_area", "")),
        "facts": _as_string_list(evidence.get("facts", [])),
        "desired_outcome": str(evidence.get("desired_outcome", "")),
        "authority_context": _as_string_list(evidence.get("authority_context", [])),
        "hidden_issues": _as_string_list(evidence.get("hidden_issues", [])),
        "quality_flags": _as_string_list(evidence.get("quality_flags", [])),
        "expected_output_schema": {
            "legal_domain": "string",
            "actor": "string",
            "subject": "string",
            "current_status": "string",
            "target_status": "string",
            "desired_action": "string",
            "legal_object": "string",
            "authority_context": "array[string]",
            "third_party_context": "array[string]",
            "location_scope": "string",
            "temporal_condition": "string",
            "operational_boundary": "string",
            "material_slots_unknown": "array[string]",
            "ambiguities": "array[string]",
            "evidence_refs": "array[{field,source_field,support_text}]",
            "validation_flags": "array[string]",
            "confidence": "low|medium|high",
            "review_status": "candidate|needs_more_context|uncertain",
        },
    }
    _ensure_public_payload(payload)
    return payload


def _legal_intent_candidate_record_from_structured_output(
    raw_result: Any,
    source_evidence: Mapping[str, Any],
    *,
    extractor_run_id: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
) -> dict[str, Any]:
    payload = _extract_result_payload(_structured_output_payload(raw_result))
    evidence_id = str(source_evidence.get("canonicalization_evidence_id", ""))
    payload.update(
        {
            "legal_intent_candidate_id": _stable_id(
                "tg-legal-intent-candidate",
                evidence_id,
                LEGAL_INTENT_CANDIDATE_POLICY_VERSION,
            ),
            "candidate_id": str(source_evidence.get("candidate_id", "")),
            "canonicalization_evidence_id": evidence_id,
            "source_canonical_question": str(source_evidence.get("canonical_question", "")),
            "source_legal_issue_frame": str(source_evidence.get("legal_issue_frame", "")),
            "law_area": str(source_evidence.get("law_area", "")),
            "policy_version": LEGAL_INTENT_CANDIDATE_POLICY_VERSION,
        }
    )
    record = _legal_intent_candidate_record(
        payload,
        evidence_by_id={evidence_id: source_evidence},
        evidence_by_candidate_id={str(source_evidence.get("candidate_id", "")): source_evidence},
    )
    record["task_id"] = evidence_id
    record["extractor_run_id"] = extractor_run_id
    record["runtime_metadata"] = {
        "extractor_run_id": extractor_run_id,
        "runtime_contour": runtime_contour,
        "backend": backend,
        "model_id": model_id,
        "prompt_version": LEGAL_INTENT_EXTRACTOR_PROMPT_VERSION,
        "policy_version": LEGAL_INTENT_EXTRACTOR_RUN_POLICY_VERSION,
    }
    return record


def _failed_legal_intent_extractor_record(
    source_evidence: Mapping[str, Any],
    *,
    extractor_run_id: str,
    failure_reason: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
) -> dict[str, Any]:
    evidence_id = str(source_evidence.get("canonicalization_evidence_id", ""))
    record = _failed_legal_intent_candidate(
        {
            "canonicalization_evidence_id": evidence_id,
            "candidate_id": str(source_evidence.get("candidate_id", "")),
        },
        failure_reason,
    )
    record["task_id"] = evidence_id
    record["extractor_run_id"] = extractor_run_id
    record["runtime_metadata"] = {
        "extractor_run_id": extractor_run_id,
        "runtime_contour": runtime_contour,
        "backend": backend,
        "model_id": model_id,
        "prompt_version": LEGAL_INTENT_EXTRACTOR_PROMPT_VERSION,
        "policy_version": LEGAL_INTENT_EXTRACTOR_RUN_POLICY_VERSION,
    }
    return record


def _legal_intent_candidates_by_evidence_id(
    legal_intent_candidates_path: str | Path | None,
) -> dict[str, dict[str, Any]]:
    if not legal_intent_candidates_path:
        return {}
    return {
        str(item.get("canonicalization_evidence_id", "")): item
        for item in _read_jsonl(legal_intent_candidates_path)
        if str(item.get("status", "")) == "completed" and str(item.get("canonicalization_evidence_id", ""))
    }


def _legal_intent_pair_operator_item(pair: Mapping[str, Any]) -> dict[str, Any]:
    pair_id = str(pair.get("pair_id", ""))
    return {
        "task_id": pair_id,
        "pair_id": pair_id,
        "candidate_id": f"{pair.get('left_candidate_id', '')}|{pair.get('right_candidate_id', '')}",
    }


def _compact_legal_intent_pair_judge_payload(
    pair: Mapping[str, Any],
    *,
    candidates_by_evidence_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    left_id = str(pair.get("left_canonicalization_evidence_id", ""))
    right_id = str(pair.get("right_canonicalization_evidence_id", ""))
    payload = {
        "pair_id": str(pair.get("pair_id", "")),
        "pair_source_reasons": _as_string_list(pair.get("pair_source_reasons", [])),
        "similarity_evidence": dict(pair.get("similarity_evidence", {}))
        if isinstance(pair.get("similarity_evidence"), Mapping)
        else {},
        "left": _compact_legal_intent_pair_side(pair.get("left", {})),
        "right": _compact_legal_intent_pair_side(pair.get("right", {})),
        "left_legal_intent_candidate": _compact_legal_intent_candidate(candidates_by_evidence_id.get(left_id, {})),
        "right_legal_intent_candidate": _compact_legal_intent_candidate(candidates_by_evidence_id.get(right_id, {})),
        "expected_output_schema": {
            "pair_class": "exact_duplicate|same_legal_intent|same_topic_different_issue|related_context|different|uncertain",
            "answer_equivalence": "safe_to_share_answer|not_safe_to_share_answer|uncertain",
            "canonical_question_equivalence": "safe_to_share_question|not_safe_to_share_question|uncertain",
            "allowed_downstream_actions": list(LEGAL_INTENT_DOWNSTREAM_ACTIONS),
            "material_differences": "array[{field,left,right,why_material}]",
            "shared_material_facts": "array[string]",
            "unknowns": "array[string]",
            "ambiguities": "array[string]",
            "short_reason": "string",
            "confidence": "low|medium|high",
            "risk": "none|low|medium|high",
        },
    }
    _ensure_public_payload(payload)
    return payload


def _compact_legal_intent_pair_side(raw: Any) -> dict[str, Any]:
    side = raw if isinstance(raw, Mapping) else {}
    return {
        "canonicalization_evidence_id": str(side.get("canonicalization_evidence_id", "")),
        "candidate_id": str(side.get("candidate_id", "")),
        "canonical_question": _redact_private_text(str(side.get("canonical_question", ""))),
        "legal_issue_frame": str(side.get("legal_issue_frame", "")),
        "legal_issue_frame_slug": str(side.get("legal_issue_frame_slug", "")),
        "law_area": str(side.get("law_area", "")),
        "authority_context": _as_string_list(side.get("authority_context", [])),
        "quality_flags": _as_string_list(side.get("quality_flags", [])),
    }


def _compact_legal_intent_candidate(raw: Any) -> dict[str, Any]:
    candidate = raw if isinstance(raw, Mapping) else {}
    if not candidate:
        return {}
    return {
        "legal_domain": str(candidate.get("legal_domain", "")),
        "actor": str(candidate.get("actor", "")),
        "subject": str(candidate.get("subject", "")),
        "current_status": str(candidate.get("current_status", "")),
        "target_status": str(candidate.get("target_status", "")),
        "desired_action": str(candidate.get("desired_action", "")),
        "legal_object": str(candidate.get("legal_object", "")),
        "authority_context": _as_string_list(candidate.get("authority_context", [])),
        "third_party_context": _as_string_list(candidate.get("third_party_context", [])),
        "location_scope": str(candidate.get("location_scope", "")),
        "temporal_condition": str(candidate.get("temporal_condition", "")),
        "operational_boundary": str(candidate.get("operational_boundary", "")),
        "material_slots_unknown": _as_string_list(candidate.get("material_slots_unknown", [])),
        "ambiguities": _as_string_list(candidate.get("ambiguities", [])),
        "confidence": str(candidate.get("confidence", "")),
    }


def _legal_intent_slot_differences(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> list[dict[str, str]]:
    differences: list[dict[str, str]] = []
    for field_name in LEGAL_INTENT_MATERIAL_SCALAR_SLOTS:
        left_value = _normalized_slot_value(left.get(field_name, ""))
        right_value = _normalized_slot_value(right.get(field_name, ""))
        if left_value and right_value and left_value != right_value:
            differences.append(
                {
                    "field": field_name,
                    "left": str(left.get(field_name, "")),
                    "right": str(right.get(field_name, "")),
                    "why_material": f"Different {field_name} can change legal intent or answer reuse.",
                }
            )
    for field_name in LEGAL_INTENT_MATERIAL_LIST_SLOTS:
        left_values = {_normalized_slot_value(value) for value in _as_string_list(left.get(field_name, []))}
        right_values = {_normalized_slot_value(value) for value in _as_string_list(right.get(field_name, []))}
        left_values.discard("")
        right_values.discard("")
        if left_values and right_values and left_values.isdisjoint(right_values):
            differences.append(
                {
                    "field": field_name,
                    "left": "; ".join(_as_string_list(left.get(field_name, []))),
                    "right": "; ".join(_as_string_list(right.get(field_name, []))),
                    "why_material": f"Different {field_name} can route the question to different actors or procedures.",
                }
            )
    return differences


def _legal_intent_shared_slot_facts(left: Mapping[str, Any], right: Mapping[str, Any]) -> list[str]:
    shared: list[str] = []
    for field_name in LEGAL_INTENT_MATERIAL_SCALAR_SLOTS:
        left_value = _normalized_slot_value(left.get(field_name, ""))
        right_value = _normalized_slot_value(right.get(field_name, ""))
        if left_value and left_value == right_value:
            shared.append(f"{field_name}:{left.get(field_name, '')}")
    for field_name in LEGAL_INTENT_MATERIAL_LIST_SLOTS:
        left_values = {_normalized_slot_value(value) for value in _as_string_list(left.get(field_name, []))}
        right_values = {_normalized_slot_value(value) for value in _as_string_list(right.get(field_name, []))}
        shared_values = sorted((left_values & right_values) - {""})
        for value in shared_values:
            shared.append(f"{field_name}:{value}")
    return shared


def _legal_intent_slot_unknowns(left: Mapping[str, Any], right: Mapping[str, Any]) -> list[str]:
    unknowns = set(_as_string_list(left.get("material_slots_unknown", [])) + _as_string_list(right.get("material_slots_unknown", [])))
    for field_name in ("desired_action", "legal_object"):
        if not _normalized_slot_value(left.get(field_name, "")):
            unknowns.add(f"left_missing_{field_name}")
        if not _normalized_slot_value(right.get(field_name, "")):
            unknowns.add(f"right_missing_{field_name}")
    return sorted(unknowns)


def _normalized_slot_value(value: Any) -> str:
    return _slugify(str(value).strip())


def _legal_intent_candidate_record(
    raw: Mapping[str, Any],
    *,
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    evidence_by_candidate_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    raw_payload = dict(raw)
    evidence_id = str(raw_payload.get("canonicalization_evidence_id", ""))
    source_evidence = evidence_by_id.get(evidence_id)
    if source_evidence is None:
        source_evidence = evidence_by_candidate_id.get(str(raw_payload.get("candidate_id", "")))
        if source_evidence is not None:
            raw_payload["canonicalization_evidence_id"] = str(source_evidence.get("canonicalization_evidence_id", ""))
    if source_evidence is None:
        return _failed_legal_intent_candidate(raw_payload, "unknown_canonicalization_evidence_id")
    raw_payload.setdefault("candidate_id", str(source_evidence.get("candidate_id", "")))
    raw_payload.setdefault("source_canonical_question", str(source_evidence.get("canonical_question", "")))
    raw_payload.setdefault("source_legal_issue_frame", str(source_evidence.get("legal_issue_frame", "")))
    raw_payload.setdefault("law_area", str(source_evidence.get("law_area", "")))
    try:
        payload = LegalIntentCandidatePayload.model_validate(raw_payload)
    except ValidationError as exc:
        return _failed_legal_intent_candidate(raw_payload, _pydantic_failure_reason(exc))
    flags = list(payload.validation_flags)
    if payload.confidence == "high" and (payload.material_slots_unknown or payload.ambiguities):
        flags.append("high_confidence_with_unresolved_material_slots")
    if not payload.evidence_refs:
        flags.append("missing_evidence_refs")
    record = payload.model_dump()
    record["legal_intent_candidate_id"] = record["legal_intent_candidate_id"] or _stable_id(
        "tg-legal-intent-candidate",
        record["canonicalization_evidence_id"],
        record["policy_version"],
    )
    record["validation_flags"] = sorted(set(flags))
    record["status"] = "completed"
    record["failure_reason"] = ""
    record["provenance"] = {
        "source_canonicalization_artifact": str(source_evidence.get("provenance", {}).get("source_candidate_artifact", ""))
        if isinstance(source_evidence.get("provenance"), Mapping)
        else "",
        "canonicalization_run_id": str(source_evidence.get("canonicalization_run_id", "")),
        "trust_boundary": "legal_intent_candidate_is_review_evidence_only",
    }
    return record


def _failed_legal_intent_candidate(raw: Mapping[str, Any], failure_reason: str) -> dict[str, Any]:
    evidence_id = str(raw.get("canonicalization_evidence_id", ""))
    return {
        "legal_intent_candidate_id": str(raw.get("legal_intent_candidate_id", ""))
        or _stable_id("tg-legal-intent-candidate", evidence_id, failure_reason, raw),
        "candidate_id": str(raw.get("candidate_id", "")),
        "canonicalization_evidence_id": evidence_id,
        "source_canonical_question": "",
        "source_legal_issue_frame": "",
        "law_area": "",
        "legal_domain": "",
        "actor": "",
        "subject": "",
        "current_status": "",
        "target_status": "",
        "desired_action": "",
        "legal_object": "",
        "authority_context": [],
        "third_party_context": [],
        "location_scope": "",
        "temporal_condition": "",
        "operational_boundary": "",
        "material_slots_unknown": [],
        "ambiguities": [],
        "evidence_refs": [],
        "validation_flags": ["legal_intent_candidate_import_failed"],
        "confidence": "low",
        "review_status": "uncertain",
        "policy_version": LEGAL_INTENT_CANDIDATE_POLICY_VERSION,
        "status": "failed",
        "failure_reason": failure_reason,
        "provenance": {"trust_boundary": "failed_candidate_not_usable"},
    }


def _legal_intent_pair_decision_record(
    raw: Mapping[str, Any],
    *,
    benchmark: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    raw_payload = dict(raw)
    pair_id = str(raw_payload.get("pair_id", ""))
    if pair_id not in benchmark:
        return _failed_legal_intent_pair_decision(raw_payload, "unknown_pair_id")
    try:
        payload = LegalIntentPairDecisionPayload.model_validate(raw_payload)
    except ValidationError as exc:
        return _failed_legal_intent_pair_decision(raw_payload, _pydantic_failure_reason(exc))
    flags = set(payload.validation_flags)
    if payload.pair_class == "exact_duplicate" and (
        payload.answer_equivalence != "safe_to_share_answer"
        or payload.canonical_question_equivalence != "safe_to_share_question"
    ):
        flags.add("exact_duplicate_without_safe_sharing")
    if payload.pair_class == "same_topic_different_issue" and (
        "allow_duplicate_removal" in payload.allowed_downstream_actions
        or "allow_reference_answer_sharing" in payload.allowed_downstream_actions
    ):
        flags.add("non_equivalent_pair_allows_strict_sharing")
    if payload.pair_class in {"different", "same_topic_different_issue"} and not payload.material_differences:
        flags.add("missing_material_differences_for_non_equivalent_pair")
    record = payload.model_dump()
    record["pair_decision_id"] = record["pair_decision_id"] or _stable_id(
        "tg-legal-intent-pair-decision",
        record["pair_id"],
        record["decision_source"],
        record["policy_version"],
    )
    record["validation_flags"] = sorted(flags)
    record["status"] = "completed"
    record["failure_reason"] = ""
    record["provenance"] = {
        "source_pair_benchmark_id": pair_id,
        "trust_boundary": "pair_decision_is_review_evidence_only",
    }
    return record


def _failed_legal_intent_pair_decision(raw: Mapping[str, Any], failure_reason: str) -> dict[str, Any]:
    pair_id = str(raw.get("pair_id", ""))
    return {
        "pair_decision_id": str(raw.get("pair_decision_id", "")) or _stable_id("tg-legal-intent-pair-decision", pair_id, failure_reason, raw),
        "pair_id": pair_id,
        "decision_source": str(raw.get("decision_source", "")),
        "pair_class": "uncertain",
        "answer_equivalence": "uncertain",
        "canonical_question_equivalence": "uncertain",
        "allowed_downstream_actions": ["route_human_review"],
        "material_differences": [],
        "shared_material_facts": [],
        "unknowns": [],
        "ambiguities": [],
        "short_reason": "",
        "confidence": "low",
        "risk": "high",
        "validation_flags": ["pair_decision_import_failed"],
        "policy_version": LEGAL_INTENT_PAIR_POLICY_VERSION,
        "runtime_metadata": {},
        "status": "failed",
        "failure_reason": failure_reason,
        "provenance": {"trust_boundary": "failed_pair_decision_not_usable"},
    }


def _legal_intent_similarity_baseline_record(
    pair: Mapping[str, Any],
    *,
    embedding_vectors: Mapping[tuple[str, str], Sequence[float]],
    decision_source: str,
    exact_duplicate_threshold: float,
    same_intent_threshold: float,
    related_threshold: float,
) -> dict[str, Any]:
    pair_id = str(pair.get("pair_id", ""))
    evidence = dict(pair.get("similarity_evidence", {})) if isinstance(pair.get("similarity_evidence"), Mapping) else {}
    recos_canonical = _recos_for_pair_role(pair, embedding_vectors, "canonical_question")
    recos_issue = _recos_for_pair_role(pair, embedding_vectors, "legal_issue_frame")
    canonical_score = _float_value(evidence.get("canonical_question_score", 0.0))
    issue_score = _float_value(evidence.get("legal_issue_frame_score", 0.0))
    if recos_canonical is None:
        recos_canonical = _float_value(evidence.get("recos_canonical_question_score", 0.0))
    if recos_issue is None:
        recos_issue = _float_value(evidence.get("recos_legal_issue_frame_score", 0.0))
    combined_score = max(canonical_score, issue_score, recos_canonical, recos_issue)
    left = pair.get("left", {}) if isinstance(pair.get("left"), Mapping) else {}
    right = pair.get("right", {}) if isinstance(pair.get("right"), Mapping) else {}
    same_normalized_question = _normalized_text(left.get("canonical_question", "")) == _normalized_text(
        right.get("canonical_question", "")
    )
    recos_canonical_available = bool(recos_canonical)
    exact = same_normalized_question or (
        canonical_score >= exact_duplicate_threshold
        and (
            recos_canonical >= exact_duplicate_threshold
            if recos_canonical_available
            else max(issue_score, recos_issue) >= same_intent_threshold
        )
    )
    if exact:
        pair_class = "exact_duplicate"
        answer_equivalence = "safe_to_share_answer"
        question_equivalence = "safe_to_share_question"
        actions = [
            "allow_duplicate_removal",
            "allow_canonical_question_sharing",
            "allow_reference_answer_sharing",
            "allow_faq_pattern_grouping",
            "allow_retrieval_cluster_grouping",
        ]
        confidence = "medium" if same_normalized_question else "low"
        risk = "medium"
        material_differences: list[dict[str, str]] = []
        short_reason = "Similarity-only baseline classified this pair as duplicate; requires review before any trusted action."
    elif combined_score >= same_intent_threshold:
        pair_class = "same_legal_intent"
        answer_equivalence = "uncertain"
        question_equivalence = "uncertain"
        actions = ["route_human_review", "allow_retrieval_cluster_grouping"]
        confidence = "low"
        risk = "high"
        material_differences = []
        short_reason = "High cosine/recos similarity suggests possible same legal intent but does not prove safe reuse."
    elif combined_score >= related_threshold:
        pair_class = "related_context"
        answer_equivalence = "not_safe_to_share_answer"
        question_equivalence = "not_safe_to_share_question"
        actions = ["route_human_review"]
        confidence = "low"
        risk = "medium"
        material_differences = []
        short_reason = "Medium cosine/recos similarity suggests related context only."
    else:
        pair_class = "different"
        answer_equivalence = "not_safe_to_share_answer"
        question_equivalence = "not_safe_to_share_question"
        actions = []
        confidence = "low"
        risk = "low"
        material_differences = [
            {
                "field": "similarity_score",
                "left": f"{combined_score:.6f}",
                "right": f"threshold:{related_threshold:.6f}",
                "why_material": "Similarity-only baseline found no close pair evidence.",
            }
        ]
        short_reason = "Similarity-only baseline found no close pair evidence."
    if pair_class in {"same_legal_intent", "exact_duplicate"} and _high_similarity_non_equivalent_source(pair):
        actions = sorted(set(actions + ["route_human_review"]))
    payload = {
        "pair_id": pair_id,
        "decision_source": decision_source,
        "pair_class": pair_class,
        "answer_equivalence": answer_equivalence,
        "canonical_question_equivalence": question_equivalence,
        "allowed_downstream_actions": actions,
        "material_differences": material_differences,
        "shared_material_facts": _similarity_shared_facts(pair, canonical_score, issue_score, recos_canonical, recos_issue),
        "unknowns": [] if recos_canonical or recos_issue else ["recos_scores_missing_without_embedding_records"],
        "ambiguities": ["similarity_does_not_encode_material_legal_slots"],
        "short_reason": short_reason,
        "confidence": confidence,
        "risk": risk,
        "validation_flags": ["similarity_only_baseline_not_safe_for_automatic_action"],
        "runtime_metadata": {
            "policy_version": LEGAL_INTENT_SIMILARITY_BASELINE_POLICY_VERSION,
            "canonical_question_score": f"{canonical_score:.6f}",
            "legal_issue_frame_score": f"{issue_score:.6f}",
            "recos_canonical_question_score": f"{recos_canonical:.6f}",
            "recos_legal_issue_frame_score": f"{recos_issue:.6f}",
            "combined_similarity_score": f"{combined_score:.6f}",
            "exact_duplicate_threshold": f"{exact_duplicate_threshold:.6f}",
            "same_intent_threshold": f"{same_intent_threshold:.6f}",
            "related_threshold": f"{related_threshold:.6f}",
        },
    }
    record = _legal_intent_pair_decision_record(payload, benchmark={pair_id: pair})
    record["task_id"] = pair_id
    return record


def _legal_intent_slot_comparator_record(
    pair: Mapping[str, Any],
    *,
    candidates_by_evidence_id: Mapping[str, Mapping[str, Any]],
    decision_source: str,
) -> dict[str, Any]:
    pair_id = str(pair.get("pair_id", ""))
    left_id = str(pair.get("left_canonicalization_evidence_id", ""))
    right_id = str(pair.get("right_canonicalization_evidence_id", ""))
    left_candidate = candidates_by_evidence_id.get(left_id)
    right_candidate = candidates_by_evidence_id.get(right_id)
    if left_candidate is None or right_candidate is None:
        payload = {
            "pair_id": pair_id,
            "decision_source": decision_source,
            "pair_class": "uncertain",
            "answer_equivalence": "uncertain",
            "canonical_question_equivalence": "uncertain",
            "allowed_downstream_actions": ["route_human_review"],
            "material_differences": [],
            "shared_material_facts": [],
            "unknowns": ["missing_left_legal_intent_candidate" if left_candidate is None else "", "missing_right_legal_intent_candidate" if right_candidate is None else ""],
            "ambiguities": [],
            "short_reason": "Structured legal-intent slots are missing for at least one side.",
            "confidence": "low",
            "risk": "medium",
            "validation_flags": ["slot_comparator_missing_candidate"],
            "runtime_metadata": {"policy_version": LEGAL_INTENT_SLOT_COMPARATOR_POLICY_VERSION},
        }
        payload["unknowns"] = [item for item in payload["unknowns"] if item]
        record = _legal_intent_pair_decision_record(payload, benchmark={pair_id: pair})
        record["task_id"] = pair_id
        return record

    differences = _legal_intent_slot_differences(left_candidate, right_candidate)
    shared = _legal_intent_shared_slot_facts(left_candidate, right_candidate)
    unresolved = _legal_intent_slot_unknowns(left_candidate, right_candidate)
    exact_question = _normalized_text(pair.get("left", {}).get("canonical_question", "") if isinstance(pair.get("left"), Mapping) else "") == _normalized_text(
        pair.get("right", {}).get("canonical_question", "") if isinstance(pair.get("right"), Mapping) else ""
    )
    if differences:
        pair_class = "same_topic_different_issue" if shared or _high_similarity_non_equivalent_source(pair) else "different"
        answer_equivalence = "not_safe_to_share_answer"
        question_equivalence = "not_safe_to_share_question"
        actions = ["route_human_review"]
        if _high_similarity_non_equivalent_source(pair):
            actions.append("preserve_hard_negative")
        confidence = "medium"
        risk = "high" if _high_similarity_non_equivalent_source(pair) else "medium"
        short_reason = "Material legal-intent slots differ, so the pair is not safe for duplicate or answer reuse."
    elif unresolved:
        pair_class = "uncertain"
        answer_equivalence = "uncertain"
        question_equivalence = "uncertain"
        actions = ["route_human_review"]
        confidence = "low"
        risk = "medium"
        short_reason = "No explicit slot conflict was found, but unresolved material slots prevent safe equivalence."
    elif exact_question:
        pair_class = "exact_duplicate"
        answer_equivalence = "safe_to_share_answer"
        question_equivalence = "safe_to_share_question"
        actions = [
            "allow_duplicate_removal",
            "allow_canonical_question_sharing",
            "allow_reference_answer_sharing",
            "allow_faq_pattern_grouping",
            "allow_retrieval_cluster_grouping",
        ]
        confidence = "high"
        risk = "low"
        short_reason = "Canonical question text and structured legal-intent slots match."
    else:
        pair_class = "same_legal_intent"
        answer_equivalence = "safe_to_share_answer"
        question_equivalence = "safe_to_share_question"
        actions = [
            "allow_canonical_question_sharing",
            "allow_reference_answer_sharing",
            "allow_faq_pattern_grouping",
            "allow_retrieval_cluster_grouping",
        ]
        confidence = "medium"
        risk = "low"
        short_reason = "Structured legal-intent slots match without unresolved material differences."
    payload = {
        "pair_id": pair_id,
        "decision_source": decision_source,
        "pair_class": pair_class,
        "answer_equivalence": answer_equivalence,
        "canonical_question_equivalence": question_equivalence,
        "allowed_downstream_actions": actions,
        "material_differences": differences,
        "shared_material_facts": shared,
        "unknowns": unresolved,
        "ambiguities": sorted(
            set(_as_string_list(left_candidate.get("ambiguities", [])) + _as_string_list(right_candidate.get("ambiguities", [])))
        ),
        "short_reason": short_reason,
        "confidence": confidence,
        "risk": risk,
        "validation_flags": [],
        "runtime_metadata": {"policy_version": LEGAL_INTENT_SLOT_COMPARATOR_POLICY_VERSION},
    }
    record = _legal_intent_pair_decision_record(payload, benchmark={pair_id: pair})
    record["task_id"] = pair_id
    return record


def _legal_intent_pair_judge_record_from_structured_output(
    raw_result: Any,
    pair: Mapping[str, Any],
    *,
    judge_run_id: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
) -> dict[str, Any]:
    payload = _extract_result_payload(_structured_output_payload(raw_result))
    pair_id = str(pair.get("pair_id", ""))
    payload["pair_id"] = str(payload.get("pair_id", "")) or pair_id
    payload["decision_source"] = str(payload.get("decision_source", "")) or judge_run_id
    runtime_metadata = dict(payload.get("runtime_metadata", {})) if isinstance(payload.get("runtime_metadata"), Mapping) else {}
    runtime_metadata.update(
        {
            "judge_run_id": judge_run_id,
            "runtime_contour": runtime_contour,
            "backend": backend,
            "model_id": model_id,
            "prompt_version": LEGAL_INTENT_PAIR_JUDGE_PROMPT_VERSION,
            "policy_version": LEGAL_INTENT_PAIR_JUDGE_RUN_POLICY_VERSION,
        }
    )
    payload["runtime_metadata"] = runtime_metadata
    record = _legal_intent_pair_decision_record(payload, benchmark={pair_id: pair})
    record["task_id"] = pair_id
    record["judge_run_id"] = judge_run_id
    return record


def _failed_legal_intent_pair_judge_record(
    pair: Mapping[str, Any],
    *,
    judge_run_id: str,
    failure_reason: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
) -> dict[str, Any]:
    pair_id = str(pair.get("pair_id", ""))
    record = _failed_legal_intent_pair_decision(
        {
            "pair_id": pair_id,
            "decision_source": judge_run_id,
            "runtime_metadata": {
                "judge_run_id": judge_run_id,
                "runtime_contour": runtime_contour,
                "backend": backend,
                "model_id": model_id,
                "prompt_version": LEGAL_INTENT_PAIR_JUDGE_PROMPT_VERSION,
            },
        },
        failure_reason,
    )
    record["task_id"] = pair_id
    record["judge_run_id"] = judge_run_id
    return record


def _legal_intent_review_card(
    pair: Mapping[str, Any],
    decisions: Sequence[Mapping[str, Any]],
    *,
    review_label: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    label_payload: dict[str, Any] = {}
    if review_label:
        label_payload = {
            "pair_class": str(review_label.get("pair_class", "")),
            "answer_equivalence": str(review_label.get("answer_equivalence", "")),
            "canonical_question_equivalence": str(review_label.get("canonical_question_equivalence", "")),
            "allowed_downstream_actions": _as_string_list(review_label.get("allowed_downstream_actions", [])),
            "decision_reason": str(review_label.get("decision_reason", "")),
            "reviewed_at": str(review_label.get("reviewed_at", "")),
        }
    return {
        "pair_id": str(pair.get("pair_id", "")),
        "pair_source_reasons": _as_string_list(pair.get("pair_source_reasons", [])),
        "benchmark_status": str(pair.get("benchmark_status", "")),
        "similarity_evidence": dict(pair.get("similarity_evidence", {})) if isinstance(pair.get("similarity_evidence"), Mapping) else {},
        "left": dict(pair.get("left", {})) if isinstance(pair.get("left"), Mapping) else {},
        "right": dict(pair.get("right", {})) if isinstance(pair.get("right"), Mapping) else {},
        "review_label": label_payload,
        "decisions": [
            {
                "decision_source": str(item.get("decision_source", "")),
                "pair_class": str(item.get("pair_class", "")),
                "answer_equivalence": str(item.get("answer_equivalence", "")),
                "canonical_question_equivalence": str(item.get("canonical_question_equivalence", "")),
                "allowed_downstream_actions": _as_string_list(item.get("allowed_downstream_actions", [])),
                "material_differences": item.get("material_differences", []),
                "short_reason": str(item.get("short_reason", "")),
                "confidence": str(item.get("confidence", "")),
                "risk": str(item.get("risk", "")),
                "validation_flags": _as_string_list(item.get("validation_flags", [])),
            }
            for item in decisions
        ],
    }


def _legal_intent_review_html(cards: Sequence[Mapping[str, Any]]) -> str:
    data = json.dumps(list(cards), ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>007 Legal Intent Pair Review</title>
  <style>
    :root {{ --bg:#f7f7f4; --panel:#fff; --line:#d6d9d2; --text:#1f2328; --muted:#697179; --accent:#0f766e; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: ui-sans-serif, system-ui, sans-serif; background:var(--bg); color:var(--text); }}
    header {{ position:sticky; top:0; z-index:2; padding:12px 18px; border-bottom:1px solid var(--line); background:#eef1ea; display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
    main {{ max-width:1240px; margin:0 auto; padding:16px; display:grid; gap:12px; }}
    button, select, input, textarea {{ font:inherit; }}
    button {{ border:1px solid var(--line); background:var(--panel); border-radius:6px; padding:7px 10px; cursor:pointer; }}
    button.primary {{ background:var(--accent); border-color:var(--accent); color:#fff; }}
    select, textarea {{ border:1px solid var(--line); border-radius:6px; background:#fff; padding:7px 8px; }}
    textarea {{ min-height:64px; resize:vertical; width:100%; }}
    .card {{ border:1px solid var(--line); border-radius:8px; background:var(--panel); padding:14px; display:grid; gap:12px; }}
    .grid {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:12px; }}
    .box {{ border-top:1px solid var(--line); padding-top:10px; }}
    .label {{ color:var(--muted); font-size:12px; text-transform:uppercase; }}
    .value {{ white-space:pre-wrap; overflow-wrap:anywhere; }}
    .chips {{ display:flex; gap:5px; flex-wrap:wrap; }}
    .chip {{ border:1px solid var(--line); border-radius:999px; padding:2px 7px; font-size:12px; background:#fafaf8; }}
    .decision {{ display:grid; grid-template-columns:180px 210px 210px minmax(0,1fr); gap:8px; align-items:start; }}
    .muted {{ color:var(--muted); font-size:12px; }}
    @media (max-width: 820px) {{ .grid,.decision {{ grid-template-columns:1fr; }} main {{ padding:12px; }} }}
  </style>
</head>
<body>
<header>
  <strong>007 legal intent pair review</strong>
  <span id="counter" class="muted"></span>
  <button id="prev">Prev</button>
  <button id="next">Next</button>
  <select id="filter">
    <option value="all">all</option>
    <option value="undecided">undecided</option>
    <option value="unreviewed">unreviewed</option>
    <option value="reviewed">reviewed</option>
    <option value="source-hard">source hard pairs</option>
    <option value="not-different">not different</option>
    <option value="same-or-duplicate">same/duplicate</option>
    <option value="related-or-uncertain">related/uncertain</option>
    <option value="random-control">random control</option>
  </select>
  <button id="export" class="primary">Export JSONL</button>
</header>
<main id="app"></main>
<script>
const cards = {data};
const decisions = new Map();
let index = 0;
let filter = 'all';
function chips(values) {{
  return `<div class="chips">${{(values || []).map(v => `<span class="chip">${{String(v)}}</span>`).join('')}}</div>`;
}}
function filtered() {{
  return cards.filter(card => {{
    const current = decisions.get(card.pair_id);
    const reviewed = Boolean(card.review_label && card.review_label.pair_class);
    const reasons = (card.pair_source_reasons || []).map(v => String(v));
    const modelClasses = (card.decisions || []).map(d => String(d.pair_class || '')).filter(Boolean);
    const visibleClasses = current && current.pair_class ? [current.pair_class] : modelClasses;
    if (filter === 'undecided') return (!current || !current.pair_class) && !reviewed;
    if (filter === 'unreviewed') return !reviewed;
    if (filter === 'reviewed') return reviewed;
    if (filter === 'source-hard') return reasons.some(v => v !== 'random_negative');
    if (filter === 'not-different') return visibleClasses.some(v => v && v !== 'different');
    if (filter === 'same-or-duplicate') return visibleClasses.some(v => ['exact_duplicate', 'same_legal_intent'].includes(v));
    if (filter === 'related-or-uncertain') return visibleClasses.some(v => ['same_topic_different_issue', 'related_context', 'uncertain'].includes(v));
    if (filter === 'random-control') return reasons.includes('random_negative');
    return true;
  }});
}}
function renderSide(title, side) {{
  return `<section class="box"><div class="label">${{title}}</div><h3>${{side.candidate_id || ''}}</h3><div class="value">${{side.canonical_question || ''}}</div><div class="muted">${{side.legal_issue_frame_slug || ''}} · ${{side.law_area || ''}}</div>${{chips(side.quality_flags || [])}}</section>`;
}}
function render() {{
  const list = filtered();
  if (!list.length) {{
    document.getElementById('app').innerHTML = '<div class="card">No cards</div>';
    document.getElementById('counter').textContent = '0/0';
    return;
  }}
  index = Math.max(0, Math.min(index, list.length - 1));
  const card = list[index];
  const existing = decisions.get(card.pair_id) || {{}};
  const label = card.review_label || {{}};
  document.getElementById('counter').textContent = `${{index + 1}}/${{list.length}}`;
  document.getElementById('app').innerHTML = `<article class="card">
    <div><strong>${{card.pair_id}}</strong><div class="muted">${{(card.pair_source_reasons || []).join(', ')}}</div></div>
    <div class="grid">${{renderSide('left', card.left || {{}})}}${{renderSide('right', card.right || {{}})}}</div>
    <section class="box"><div class="label">similarity</div><pre>${{JSON.stringify(card.similarity_evidence || {{}}, null, 2)}}</pre></section>
    ${{label.pair_class ? `<section class="box"><div class="label">existing human label</div><p><strong>${{label.pair_class}}</strong>: ${{label.answer_equivalence || ''}} / ${{label.canonical_question_equivalence || ''}}</p><div class="value">${{label.decision_reason || ''}}</div><div class="muted">${{label.reviewed_at || ''}}</div></section>` : ''}}
    <section class="box"><div class="label">model decisions</div>${{(card.decisions || []).map(d => `<p><strong>${{d.decision_source}}</strong>: ${{d.pair_class}} / ${{d.answer_equivalence}} / ${{d.canonical_question_equivalence}}<br>${{d.short_reason || ''}}</p>`).join('') || '<span class="muted">none</span>'}}</section>
    <section class="decision">
      <select id="pairClass">
        ${{['','exact_duplicate','same_legal_intent','same_topic_different_issue','related_context','different','uncertain'].map(v => `<option value="${{v}}" ${{existing.pair_class===v?'selected':''}}>${{v || 'decision'}}</option>`).join('')}}
      </select>
      <select id="answerEq">
        ${{['','safe_to_share_answer','not_safe_to_share_answer','uncertain'].map(v => `<option value="${{v}}" ${{existing.answer_equivalence===v?'selected':''}}>${{v || 'answer equivalence'}}</option>`).join('')}}
      </select>
      <select id="questionEq">
        ${{['','safe_to_share_question','not_safe_to_share_question','uncertain'].map(v => `<option value="${{v}}" ${{existing.canonical_question_equivalence===v?'selected':''}}>${{v || 'question equivalence'}}</option>`).join('')}}
      </select>
      <textarea id="reason" placeholder="decision_reason">${{existing.decision_reason || ''}}</textarea>
    </section>
  </article>`;
  document.getElementById('pairClass').oninput = () => {{
    applyPairClassDefaults();
    save();
  }};
  for (const id of ['answerEq','questionEq','reason']) {{
    document.getElementById(id).oninput = save;
  }}
  function applyPairClassDefaults() {{
    if (document.getElementById('pairClass').value === 'different') {{
      document.getElementById('answerEq').value = 'not_safe_to_share_answer';
      document.getElementById('questionEq').value = 'not_safe_to_share_question';
    }}
  }}
  function save() {{
    decisions.set(card.pair_id, {{
      pair_id: card.pair_id,
      pair_class: document.getElementById('pairClass').value,
      answer_equivalence: document.getElementById('answerEq').value,
      canonical_question_equivalence: document.getElementById('questionEq').value,
      allowed_downstream_actions: [],
      decision_reason: document.getElementById('reason').value,
      reviewer_hash: '',
      reviewed_at: new Date().toISOString()
    }});
  }}
}}
document.getElementById('prev').onclick = () => {{ index--; render(); }};
document.getElementById('next').onclick = () => {{ index++; render(); }};
document.getElementById('filter').onchange = event => {{ filter = event.target.value; index = 0; render(); }};
document.getElementById('export').onclick = () => {{
  const exported = Array.from(decisions.values()).filter(item => item.pair_class);
  const lines = exported.map(item => JSON.stringify(item));
  const blob = new Blob([lines.join('\\n') + (lines.length ? '\\n' : '')], {{type: 'application/x-ndjson'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'tg_007_legal_intent_pair_review_labels.jsonl';
  a.click();
  URL.revokeObjectURL(url);
}};
render();
</script>
</body>
</html>
"""


def _legal_intent_pair_review_label_record(
    raw: Mapping[str, Any],
    *,
    benchmark: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    pair_id = str(raw.get("pair_id", ""))
    pair_class = str(raw.get("pair_class", ""))
    answer_equivalence = str(raw.get("answer_equivalence", "uncertain") or "uncertain")
    canonical_question_equivalence = str(raw.get("canonical_question_equivalence", "uncertain") or "uncertain")
    actions = _as_string_list(raw.get("allowed_downstream_actions", []))
    failure_reason = ""
    if pair_id not in benchmark:
        failure_reason = "unknown_pair_id"
    elif pair_class not in LEGAL_INTENT_PAIR_CLASSES:
        failure_reason = f"invalid_pair_class:{pair_class}"
    elif answer_equivalence not in LEGAL_INTENT_ANSWER_EQUIVALENCE_VALUES:
        failure_reason = f"invalid_answer_equivalence:{answer_equivalence}"
    elif canonical_question_equivalence not in LEGAL_INTENT_QUESTION_EQUIVALENCE_VALUES:
        failure_reason = f"invalid_canonical_question_equivalence:{canonical_question_equivalence}"
    else:
        invalid_actions = sorted({item for item in actions if item not in LEGAL_INTENT_DOWNSTREAM_ACTIONS})
        if invalid_actions:
            failure_reason = f"invalid_allowed_downstream_actions:{','.join(invalid_actions)}"
    return {
        "pair_review_label_id": str(raw.get("pair_review_label_id", "")) or _stable_id(
            "tg-legal-intent-pair-review",
            pair_id,
            pair_class,
            answer_equivalence,
            canonical_question_equivalence,
        ),
        "pair_id": pair_id,
        "pair_class": pair_class if pair_class in LEGAL_INTENT_PAIR_CLASSES else "uncertain",
        "answer_equivalence": answer_equivalence
        if answer_equivalence in LEGAL_INTENT_ANSWER_EQUIVALENCE_VALUES
        else "uncertain",
        "canonical_question_equivalence": canonical_question_equivalence
        if canonical_question_equivalence in LEGAL_INTENT_QUESTION_EQUIVALENCE_VALUES
        else "uncertain",
        "allowed_downstream_actions": actions,
        "decision_reason": str(raw.get("decision_reason", "")),
        "reviewer_hash": str(raw.get("reviewer_hash", "")),
        "reviewed_at": str(raw.get("reviewed_at", "")) or _utc_timestamp(),
        "status": "failed" if failure_reason else "completed",
        "failure_reason": failure_reason,
        "review_policy_version": LEGAL_INTENT_REVIEW_POLICY_VERSION,
    }


def _legal_intent_label_fingerprint(record: Mapping[str, Any]) -> str:
    return json.dumps(
        {
            "pair_class": record.get("pair_class", ""),
            "answer_equivalence": record.get("answer_equivalence", ""),
            "canonical_question_equivalence": record.get("canonical_question_equivalence", ""),
            "allowed_downstream_actions": sorted(_as_string_list(record.get("allowed_downstream_actions", []))),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _legal_intent_evaluation_record(
    decision: Mapping[str, Any],
    label: Mapping[str, Any] | None,
    benchmark: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    pair_id = str(decision.get("pair_id", ""))
    label_pair_class = str((label or {}).get("pair_class", ""))
    label_answer_equivalence = str((label or {}).get("answer_equivalence", ""))
    label_question_equivalence = str((label or {}).get("canonical_question_equivalence", ""))
    decision_pair_class = str(decision.get("pair_class", ""))
    decision_answer_equivalence = str(decision.get("answer_equivalence", ""))
    decision_question_equivalence = str(decision.get("canonical_question_equivalence", ""))
    match_status = "unreviewed"
    question_equivalence_match_status = "unreviewed"
    answer_equivalence_match_status = "unreviewed"
    question_reuse_safety_match_status = "unreviewed"
    answer_reuse_safety_match_status = "unreviewed"
    if label:
        match_status = "match" if decision_pair_class == label_pair_class else "mismatch"
        question_equivalence_match_status = (
            "match" if decision_question_equivalence == label_question_equivalence else "mismatch"
        )
        answer_equivalence_match_status = (
            "match" if decision_answer_equivalence == label_answer_equivalence else "mismatch"
        )
        question_reuse_safety_match_status = (
            "match"
            if (decision_question_equivalence == "safe_to_share_question")
            == (label_question_equivalence == "safe_to_share_question")
            else "mismatch"
        )
        answer_reuse_safety_match_status = (
            "match"
            if (decision_answer_equivalence == "safe_to_share_answer")
            == (label_answer_equivalence == "safe_to_share_answer")
            else "mismatch"
        )
    false_duplicate_risk = bool(
        label
        and label_pair_class in {"same_topic_different_issue", "related_context", "different"}
        and (
            decision_pair_class in {"exact_duplicate", "same_legal_intent"}
            or decision_answer_equivalence == "safe_to_share_answer"
            or "allow_duplicate_removal" in _as_string_list(decision.get("allowed_downstream_actions", []))
        )
    )
    false_separation_risk = bool(
        label
        and label_pair_class in {"exact_duplicate", "same_legal_intent"}
        and decision_pair_class in {"different", "same_topic_different_issue"}
    )
    pair = benchmark.get(pair_id, {})
    return {
        "pair_id": pair_id,
        "decision_source": str(decision.get("decision_source", "")),
        "decision_pair_class": decision_pair_class,
        "label_pair_class": label_pair_class,
        "decision_answer_equivalence": decision_answer_equivalence,
        "label_answer_equivalence": label_answer_equivalence,
        "decision_question_equivalence": decision_question_equivalence,
        "label_question_equivalence": label_question_equivalence,
        "match_status": match_status,
        "question_equivalence_match_status": question_equivalence_match_status,
        "answer_equivalence_match_status": answer_equivalence_match_status,
        "question_reuse_safety_match_status": question_reuse_safety_match_status,
        "answer_reuse_safety_match_status": answer_reuse_safety_match_status,
        "false_duplicate_risk": false_duplicate_risk,
        "false_separation_risk": false_separation_risk,
        "canonical_question_score": _float_value(
            (pair.get("similarity_evidence", {}) if isinstance(pair.get("similarity_evidence"), Mapping) else {}).get(
                "canonical_question_score", 0.0
            )
        ),
        "legal_issue_frame_score": _float_value(
            (pair.get("similarity_evidence", {}) if isinstance(pair.get("similarity_evidence"), Mapping) else {}).get(
                "legal_issue_frame_score", 0.0
            )
        ),
        "material_differences": decision.get("material_differences", []),
        "short_reason": str(decision.get("short_reason", "")),
    }


def _legal_intent_hard_negative(pair: Mapping[str, Any], label: Mapping[str, Any]) -> bool:
    pair_class = str(label.get("pair_class", ""))
    if pair_class not in {"same_topic_different_issue", "related_context", "different"}:
        return False
    evidence = pair.get("similarity_evidence", {}) if isinstance(pair.get("similarity_evidence"), Mapping) else {}
    return max(_float_value(evidence.get("canonical_question_score", 0.0)), _float_value(evidence.get("legal_issue_frame_score", 0.0))) >= 0.85


def _hard_negative_summary(pair_id: str, pair: Mapping[str, Any], label: Mapping[str, Any]) -> dict[str, Any]:
    evidence = pair.get("similarity_evidence", {}) if isinstance(pair.get("similarity_evidence"), Mapping) else {}
    return {
        "pair_id": pair_id,
        "label_pair_class": str(label.get("pair_class", "")),
        "canonical_question_score": _float_value(evidence.get("canonical_question_score", 0.0)),
        "legal_issue_frame_score": _float_value(evidence.get("legal_issue_frame_score", 0.0)),
        "pair_source_reasons": _as_string_list(pair.get("pair_source_reasons", [])),
        "decision_reason": str(label.get("decision_reason", "")),
    }


def _legal_intent_insufficient_label_warnings(labels: Sequence[Mapping[str, Any]]) -> list[str]:
    warnings: list[str] = []
    if len(labels) < 100:
        warnings.append("reviewed_pair_label_count_below_100")
    class_counts = _counts(str(item.get("pair_class", "")) for item in labels)
    if len(class_counts) < 2:
        warnings.append("reviewed_pair_labels_not_class_diverse")
    return warnings


def _legal_intent_method_suitability(records: Sequence[Mapping[str, Any]], label_count: int) -> str:
    if label_count < 100:
        return "insufficient_reviewed_labels"
    if any(_bool_value(item.get("false_duplicate_risk", False)) for item in records):
        return "unsafe_for_automatic_action"
    if any(str(item.get("match_status", "")) == "mismatch" for item in records):
        return "safe_only_for_candidate_generation"
    return "safe_for_narrow_reviewed_downstream_action"


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _canonicalization_batch_item(candidate: Mapping[str, Any], *, candidates_path: str | Path) -> dict[str, Any]:
    candidate_id = str(candidate.get("candidate_id", "")) or _stable_id("tg-qa-candidate", candidate)
    source_message_ids = _source_message_ids(candidate)
    question_text = _redact_private_text(
        str(candidate.get("question_text_redacted", candidate.get("question_text", ""))).strip()
    )
    return {
        "task_id": _stable_id("tg-question-canonicalization-task", candidate_id, question_text),
        "task_scope": "question_candidate",
        "candidate_id": candidate_id,
        "canonicalization_contract_version": CANONICALIZATION_CONTRACT_VERSION,
        "prompt_version": CANONICALIZATION_PROMPT_VERSION,
        "prompt_example_set_id": CANONICALIZATION_PROMPT_EXAMPLE_SET_ID,
        "runtime_hint": "operator_managed_llm_or_deterministic_fixture",
        "input": {
            "question_text_redacted": question_text,
            "topic_labels": _as_string_list(candidate.get("topic_labels", [])),
            "law_code_candidates": _as_string_list(candidate.get("law_code_candidates", [])),
            "question_date": str(candidate.get("question_date", candidate.get("date", ""))),
            "answer_candidate_status": str(candidate.get("answer_candidate_status", "")),
            "quality_flags": _as_string_list(candidate.get("quality_flags", [])),
            "source_candidate_artifact": str(candidates_path),
            "source_message_ids": source_message_ids,
            "selected_answer_metadata": _selected_answer_metadata(candidate),
        },
        "expected_output_schema": dict(EXPECTED_CANONICALIZATION_SCHEMA),
    }


def _stable_json_hash(payload: Any) -> str:
    """Return a stable full SHA-256 digest for a JSON-compatible value."""

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _canonicalization_prompt_profile_hash(prompt_version: str) -> str:
    profile = load_prompt_profile_data(prompt_version)
    if str(profile.get("prompt_version", "")) != prompt_version:
        raise ValueError(f"prompt profile version mismatch: {prompt_version}")
    return _stable_json_hash(profile)


def _canonicalization_task_identity_payload(task: Mapping[str, Any]) -> dict[str, Any]:
    """Return the immutable, non-runtime portion of a canonicalization task."""

    source_input = task.get("input", {}) if isinstance(task.get("input"), Mapping) else {}
    expected_schema = (
        task.get("expected_output_schema", {})
        if isinstance(task.get("expected_output_schema"), Mapping)
        else {}
    )
    retry_context = task.get("retry_context", {}) if isinstance(task.get("retry_context"), Mapping) else {}
    source_identity = (
        task.get("canonicalization_source_identity", {})
        if isinstance(task.get("canonicalization_source_identity"), Mapping)
        else {}
    )
    payload = {
        "task_id": str(task.get("task_id", "")),
        "task_scope": str(task.get("task_scope", "question_candidate")),
        "candidate_id": str(task.get("candidate_id", "")),
        "canonicalization_contract_version": str(
            task.get("canonicalization_contract_version", CANONICALIZATION_CONTRACT_VERSION)
        ),
        "prompt_version": str(task.get("prompt_version", CANONICALIZATION_PROMPT_VERSION)),
        "prompt_example_set_id": str(task.get("prompt_example_set_id", "")),
        "input": dict(source_input),
        "expected_output_schema": dict(expected_schema),
        "retry_context": dict(retry_context),
    }
    if source_identity:
        payload["canonicalization_source_identity"] = dict(source_identity)
    return payload


def _canonicalization_root_identity(task: Mapping[str, Any]) -> dict[str, str]:
    """Return the original task identity that a derived retry is allowed to replace."""

    existing = task.get("canonicalization_source_identity", {})
    if isinstance(existing, Mapping) and existing:
        return {str(key): str(value) for key, value in existing.items()}
    return {
        "task_id": str(task.get("task_id", "")),
        "candidate_id": str(task.get("candidate_id", "")),
        "canonicalization_contract_version": str(
            task.get("canonicalization_contract_version", CANONICALIZATION_CONTRACT_VERSION)
        ),
        "canonicalization_batch_id": str(task.get("canonicalization_batch_id", "")),
        "canonicalization_batch_hash": str(task.get("canonicalization_batch_hash", "")),
        "task_input_hash": str(task.get("task_input_hash", "")),
        "prompt_version": str(task.get("prompt_version", CANONICALIZATION_PROMPT_VERSION)),
        "prompt_profile_hash": str(task.get("prompt_profile_hash", "")),
    }


def _canonicalization_task_input_hash(task: Mapping[str, Any]) -> str:
    return _stable_json_hash(_canonicalization_task_identity_payload(task))


def _canonicalization_batch_identity_values(
    batch_items: Sequence[Mapping[str, Any]],
) -> tuple[str, str, dict[str, dict[str, str]]]:
    """Derive deterministic task and batch identities without trusting stored hashes."""

    task_identities: dict[str, dict[str, str]] = {}
    for item in batch_items:
        task_id = str(item.get("task_id", ""))
        if not task_id:
            raise ValueError("canonicalization batch contains task without task_id")
        if task_id in task_identities:
            raise ValueError(f"canonicalization batch contains duplicate task_id: {task_id}")
        prompt_version = str(item.get("prompt_version", CANONICALIZATION_PROMPT_VERSION))
        task_identities[task_id] = {
            "task_id": task_id,
            "task_input_hash": _canonicalization_task_input_hash(item),
            "prompt_profile_hash": _canonicalization_prompt_profile_hash(prompt_version),
        }

    batch_hash = _stable_json_hash(
        [task_identities[task_id] for task_id in sorted(task_identities)]
    )
    batch_id = f"tg-question-canonicalization-batch:{batch_hash[:20]}"
    return batch_id, batch_hash, task_identities


def _bind_canonicalization_batch_identity(records: Sequence[dict[str, Any]]) -> dict[str, str]:
    """Attach authoritative identity fields to every emitted task in one batch."""

    batch_id, batch_hash, task_identities = _canonicalization_batch_identity_values(records)
    for record in records:
        identity = task_identities[str(record.get("task_id", ""))]
        record.update(
            {
                "canonicalization_identity_policy_version": CANONICALIZATION_IDENTITY_POLICY_VERSION,
                "canonicalization_batch_id": batch_id,
                "canonicalization_batch_hash": batch_hash,
                "task_input_hash": identity["task_input_hash"],
                "prompt_profile_hash": identity["prompt_profile_hash"],
            }
        )
    return {
        "canonicalization_batch_id": batch_id,
        "canonicalization_batch_hash": batch_hash,
    }


def _canonicalization_batch_identity_index(
    batch_items: Sequence[Mapping[str, Any]],
    *,
    allow_legacy_identity: bool = False,
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """Validate stored task identities and return recomputed expected values."""

    batch_id, batch_hash, task_identities = _canonicalization_batch_identity_values(batch_items)
    required_fields = (
        "canonicalization_batch_id",
        "canonicalization_batch_hash",
        "task_input_hash",
        "prompt_profile_hash",
    )
    for item in batch_items:
        task_id = str(item.get("task_id", ""))
        expected = {
            "canonicalization_batch_id": batch_id,
            "canonicalization_batch_hash": batch_hash,
            "task_input_hash": task_identities[task_id]["task_input_hash"],
            "prompt_profile_hash": task_identities[task_id]["prompt_profile_hash"],
        }
        for field_name in required_fields:
            actual = str(item.get(field_name, ""))
            if not actual and allow_legacy_identity:
                continue
            if not actual:
                raise ValueError(f"canonicalization batch missing {field_name} for task_id: {task_id}")
            if actual != expected[field_name]:
                raise ValueError(f"canonicalization batch identity mismatch: {field_name} for task_id: {task_id}")
        task_identities[task_id].update(expected)
    return task_identities, {
        "canonicalization_batch_id": batch_id,
        "canonicalization_batch_hash": batch_hash,
    }


def _candidate_matches_filter(candidate: Mapping[str, Any], filter_mode: str) -> bool:
    if filter_mode == "all":
        return True
    has_law_or_topic = bool(_as_string_list(candidate.get("topic_labels", []))) or bool(
        _as_string_list(candidate.get("law_code_candidates", []))
    )
    if filter_mode == "law_or_topic":
        return has_law_or_topic
    return has_law_or_topic and str(candidate.get("answer_candidate_status", "")) != "missing"


def _selected_answer_metadata(candidate: Mapping[str, Any]) -> dict[str, Any]:
    answer_candidates = candidate.get("answer_candidates", [])
    selected_answer = {}
    if isinstance(answer_candidates, list) and answer_candidates:
        preferred = [
            item
            for item in answer_candidates
            if isinstance(item, Mapping) and str(item.get("answer_candidate_priority", "")) != "low"
        ]
        selected_answer = dict((preferred or [answer_candidates[0]])[0])
    return {
        "answer_candidate_status": str(candidate.get("answer_candidate_status", "")),
        "answer_source_type": str(selected_answer.get("answer_source_type", "")),
        "answer_link_type": str(selected_answer.get("answer_link_type", "")),
        "answer_candidate_priority": str(selected_answer.get("answer_candidate_priority", "")),
    }


def _source_message_ids(candidate: Mapping[str, Any]) -> list[str]:
    values = []
    for key in ("source_message_id", "question_message_id", "message_id"):
        value = str(candidate.get(key, ""))
        if value:
            values.append(value)
    for key in ("source_message_ids", "message_ids"):
        values.extend(_as_string_list(candidate.get(key, [])))
    return sorted(set(values))


CANONICALIZATION_RESULT_IDENTITY_FIELDS = (
    "canonicalization_identity_policy_version",
    "canonicalization_batch_id",
    "canonicalization_batch_hash",
    "task_input_hash",
    "prompt_profile_hash",
    "runtime_profile_hash",
    "canonicalization_evidence_hash",
)
CANONICALIZATION_RESULT_AUXILIARY_FIELDS = {
    "canonicalization_evidence_id",
    "canonicalization_identity_policy_version",
    "canonicalization_batch_id",
    "canonicalization_batch_hash",
    "task_input_hash",
    "prompt_profile_hash",
    "runtime_profile",
    "runtime_profile_hash",
    "runtime_metadata",
    "canonicalization_evidence_hash",
    "source_question_text_redacted",
    "question_date",
    "provenance",
    "review_provenance",
    "adjudication_provenance",
    "finalization_provenance",
    "canonicalization_source_identity",
    "identity_validation_status",
    "operator_stage",
    "untrusted_law_code_hints",
    "custom_id",
}


def _canonicalization_result_model_payload(raw_payload: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    allowed_fields = set(CanonicalizationResultPayload.model_fields) | CANONICALIZATION_RESULT_AUXILIARY_FIELDS
    unknown_fields = sorted(str(field_name) for field_name in raw_payload if field_name not in allowed_fields)
    if unknown_fields:
        return {}, f"unexpected_result_fields:{','.join(unknown_fields)}"
    return {
        field_name: raw_payload[field_name]
        for field_name in CanonicalizationResultPayload.model_fields
        if field_name in raw_payload
    }, ""


def _extract_result_payload(raw_payload: Mapping[str, Any]) -> dict[str, Any]:
    if "canonical_question" in raw_payload or "status" in raw_payload:
        return dict(raw_payload)
    for key in ("result", "output", "response_json"):
        nested = raw_payload.get(key)
        if isinstance(nested, Mapping):
            merged = dict(nested)
            for passthrough in (
                "task_id",
                "custom_id",
                "canonicalization_run_id",
                "task_scope",
                "candidate_id",
                *CANONICALIZATION_RESULT_AUXILIARY_FIELDS,
            ):
                if passthrough in raw_payload and passthrough not in merged:
                    merged[passthrough] = raw_payload[passthrough]
            return merged
    content = _response_content(raw_payload)
    if content:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return dict(raw_payload)
        if isinstance(parsed, Mapping):
            merged = dict(parsed)
            for passthrough in (
                "task_id",
                "custom_id",
                "canonicalization_run_id",
                "task_scope",
                "candidate_id",
                *CANONICALIZATION_RESULT_AUXILIARY_FIELDS,
            ):
                if passthrough in raw_payload and passthrough not in merged:
                    merged[passthrough] = raw_payload[passthrough]
            return merged
    return dict(raw_payload)


def _response_content(raw_payload: Mapping[str, Any]) -> str:
    content = raw_payload.get("content")
    if isinstance(content, str):
        return content
    response = raw_payload.get("response")
    if isinstance(response, Mapping):
        body = response.get("body")
        if isinstance(body, Mapping):
            choices = body.get("choices")
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, Mapping):
                    message = first.get("message")
                    if isinstance(message, Mapping) and isinstance(message.get("content"), str):
                        return str(message["content"])
    return ""


def _validate_canonicalization_result(
    payload: Mapping[str, Any],
    tasks_by_id: Mapping[str, Mapping[str, Any]],
    *,
    default_run_id: str,
    expected_task_identities: Mapping[str, Mapping[str, str]],
    strict_identity: bool = True,
) -> tuple[dict[str, Any], str]:
    raw_payload = dict(payload)
    if not raw_payload.get("task_id") and raw_payload.get("custom_id"):
        raw_payload["task_id"] = raw_payload["custom_id"]
    task_id = str(raw_payload.get("task_id", ""))
    if not task_id:
        return {}, "missing_task_id"
    source_task = tasks_by_id.get(task_id)
    if source_task is None:
        return {}, "unknown_task_id"
    model_payload, schema_failure_reason = _canonicalization_result_model_payload(raw_payload)
    if schema_failure_reason:
        return {}, schema_failure_reason
    try:
        result = CanonicalizationResultPayload.model_validate(model_payload)
    except ValidationError as exc:
        return {}, _pydantic_failure_reason(exc)
    cjk_failure_reason = _canonicalization_cjk_failure_reason(result)
    if cjk_failure_reason:
        return {}, cjk_failure_reason

    expected_identity = expected_task_identities.get(task_id)
    if expected_identity is None:
        return {}, "missing_expected_task_identity"
    identity_failure_reason, run_id, runtime_profile = _canonicalization_result_identity_failure_reason(
        raw_payload,
        result=result,
        source_task=source_task,
        expected_identity=expected_identity,
        default_run_id=default_run_id,
        strict_identity=strict_identity,
    )
    if identity_failure_reason:
        return {}, identity_failure_reason

    failure_reason = result.failure_reason
    if result.status in {"failed", "skipped"} and not failure_reason:
        failure_reason = result.status

    legal_issue_frame_slug = _slugify(result.legal_issue_frame_slug or result.legal_issue_frame)
    evidence = {
        "canonicalization_evidence_id": _stable_id("tg-question-canonicalization-evidence", run_id, task_id),
        "task_id": task_id,
        "task_scope": str(source_task.get("task_scope", "question_candidate")),
        "candidate_id": str(source_task.get("candidate_id", "")),
        "canonicalization_run_id": run_id,
        "canonicalization_contract_version": str(source_task.get("canonicalization_contract_version", "")),
        "canonicalization_identity_policy_version": CANONICALIZATION_IDENTITY_POLICY_VERSION,
        "canonicalization_batch_id": expected_identity["canonicalization_batch_id"],
        "canonicalization_batch_hash": expected_identity["canonicalization_batch_hash"],
        "task_input_hash": expected_identity["task_input_hash"],
        "prompt_version": str(source_task.get("prompt_version", CANONICALIZATION_PROMPT_VERSION)),
        "prompt_profile_hash": expected_identity["prompt_profile_hash"],
        "runtime_profile": runtime_profile,
        "runtime_profile_hash": str(raw_payload.get("runtime_profile_hash", "")),
        "runtime_contour": result.runtime_contour,
        "backend": result.backend,
        "model_id": result.model_id,
        "status": result.status,
        "failure_reason": failure_reason,
        "canonical_question": result.canonical_question,
        "canonical_question_language": result.canonical_question_language,
        "legal_issue_frame": result.legal_issue_frame,
        "legal_issue_frame_slug": legal_issue_frame_slug,
        "law_area": result.law_area,
        "facts": result.facts,
        "desired_outcome": result.desired_outcome,
        "authority_context": result.authority_context,
        "hidden_issues": result.hidden_issues,
        "is_legal_answer_required": result.is_legal_answer_required,
        "is_standalone_question": result.is_standalone_question,
        "exclusion_reason": result.exclusion_reason,
        "confidence": result.confidence,
        "quality_flags": result.quality_flags,
        "question_date": str(source_task.get("input", {}).get("question_date", "")),
        "source_question_text_redacted": str(source_task.get("input", {}).get("question_text_redacted", "")),
        "identity_validation_status": "validated" if strict_identity else "legacy_identity_unverified",
        "provenance": _canonicalization_provenance(
            source_task,
            raw_payload,
            expected_identity=expected_identity,
            identity_validation_status="validated" if strict_identity else "legacy_identity_unverified",
        ),
    }
    untrusted_law_code_hints = _as_string_list(
        source_task.get("input", {}).get("law_code_candidates", [])
    )
    if untrusted_law_code_hints:
        evidence["untrusted_law_code_hints"] = untrusted_law_code_hints
    source_identity = source_task.get("canonicalization_source_identity", {})
    if isinstance(source_identity, Mapping) and source_identity:
        evidence["canonicalization_source_identity"] = dict(source_identity)
    if isinstance(raw_payload.get("runtime_metadata"), Mapping):
        evidence["runtime_metadata"] = dict(raw_payload["runtime_metadata"])
    if isinstance(raw_payload.get("review_provenance"), Mapping):
        evidence["review_provenance"] = dict(raw_payload["review_provenance"])
    if isinstance(raw_payload.get("adjudication_provenance"), Mapping):
        evidence["adjudication_provenance"] = dict(raw_payload["adjudication_provenance"])
    if isinstance(raw_payload.get("finalization_provenance"), Mapping):
        evidence["finalization_provenance"] = dict(raw_payload["finalization_provenance"])
    evidence_hash = _canonicalization_evidence_hash(evidence)
    supplied_evidence_hash = str(raw_payload.get("canonicalization_evidence_hash", ""))
    if strict_identity and not supplied_evidence_hash:
        return {}, "identity_missing:canonicalization_evidence_hash"
    if supplied_evidence_hash and supplied_evidence_hash != evidence_hash:
        return {}, "identity_mismatch:canonicalization_evidence_hash"
    evidence["canonicalization_evidence_hash"] = evidence_hash
    _ensure_public_payload(evidence)
    return evidence, ""


def _canonicalization_result_identity_failure_reason(
    raw_payload: Mapping[str, Any],
    *,
    result: CanonicalizationResultPayload,
    source_task: Mapping[str, Any],
    expected_identity: Mapping[str, str],
    default_run_id: str,
    strict_identity: bool,
) -> tuple[str, str, dict[str, Any]]:
    expected_values = {
        "task_id": str(source_task.get("task_id", "")),
        "task_scope": str(source_task.get("task_scope", "question_candidate")),
        "candidate_id": str(source_task.get("candidate_id", "")),
        "canonicalization_contract_version": str(
            source_task.get("canonicalization_contract_version", CANONICALIZATION_CONTRACT_VERSION)
        ),
        "prompt_version": str(source_task.get("prompt_version", CANONICALIZATION_PROMPT_VERSION)),
        "canonicalization_identity_policy_version": CANONICALIZATION_IDENTITY_POLICY_VERSION,
        "canonicalization_batch_id": str(expected_identity["canonicalization_batch_id"]),
        "canonicalization_batch_hash": str(expected_identity["canonicalization_batch_hash"]),
        "task_input_hash": str(expected_identity["task_input_hash"]),
        "prompt_profile_hash": str(expected_identity["prompt_profile_hash"]),
    }
    for field_name, expected_value in expected_values.items():
        actual_value = str(raw_payload.get(field_name, ""))
        if not actual_value:
            if strict_identity:
                return f"identity_missing:{field_name}", "", {}
            continue
        if actual_value != expected_value:
            return f"identity_mismatch:{field_name}", "", {}

    source_identity = source_task.get("canonicalization_source_identity", {})
    if isinstance(source_identity, Mapping) and source_identity:
        actual_source_identity = raw_payload.get("canonicalization_source_identity", {})
        if not isinstance(actual_source_identity, Mapping):
            if strict_identity:
                return "identity_missing:canonicalization_source_identity", "", {}
        elif _stable_json_hash(dict(actual_source_identity)) != _stable_json_hash(dict(source_identity)):
            return "identity_mismatch:canonicalization_source_identity", "", {}

    run_id = str(raw_payload.get("canonicalization_run_id", "")) or default_run_id
    if not run_id:
        return "identity_missing:canonicalization_run_id", "", {}
    if default_run_id and str(raw_payload.get("canonicalization_run_id", "")) not in {"", default_run_id}:
        return "identity_mismatch:canonicalization_run_id", "", {}
    if result.task_id and result.task_id != expected_values["task_id"]:
        return "identity_mismatch:task_id", "", {}
    if result.task_scope and result.task_scope != expected_values["task_scope"]:
        return "identity_mismatch:task_scope", "", {}
    if result.candidate_id and result.candidate_id != expected_values["candidate_id"]:
        return "identity_mismatch:candidate_id", "", {}
    if (
        result.canonicalization_contract_version
        and result.canonicalization_contract_version != expected_values["canonicalization_contract_version"]
    ):
        return "identity_mismatch:canonicalization_contract_version", "", {}
    if result.prompt_version and result.prompt_version != expected_values["prompt_version"]:
        return "identity_mismatch:prompt_version", "", {}

    raw_runtime_profile = raw_payload.get("runtime_profile", {})
    runtime_profile = dict(raw_runtime_profile) if isinstance(raw_runtime_profile, Mapping) else {}
    runtime_profile_hash = str(raw_payload.get("runtime_profile_hash", ""))
    if strict_identity and not runtime_profile:
        return "identity_missing:runtime_profile", "", {}
    if strict_identity and not runtime_profile_hash:
        return "identity_missing:runtime_profile_hash", "", {}
    if runtime_profile and runtime_profile_hash and runtime_profile_hash != _stable_json_hash(runtime_profile):
        return "identity_mismatch:runtime_profile_hash", "", {}
    if runtime_profile and str(runtime_profile.get("stage", "")) not in {"canonicalization", "manual_review"}:
        return "identity_mismatch:runtime_profile.stage", "", {}
    return "", run_id, runtime_profile


def _canonicalization_evidence_hash(record: Mapping[str, Any]) -> str:
    fields = (
        "task_id",
        "task_scope",
        "candidate_id",
        "canonicalization_run_id",
        "canonicalization_contract_version",
        "canonicalization_batch_id",
        "canonicalization_batch_hash",
        "task_input_hash",
        "prompt_version",
        "prompt_profile_hash",
        "runtime_profile_hash",
        "status",
        "failure_reason",
        "canonical_question",
        "canonical_question_language",
        "legal_issue_frame",
        "legal_issue_frame_slug",
        "law_area",
        "facts",
        "desired_outcome",
        "authority_context",
        "hidden_issues",
        "is_legal_answer_required",
        "is_standalone_question",
        "exclusion_reason",
        "confidence",
        "quality_flags",
    )
    payload = {field_name: record.get(field_name) for field_name in fields}
    source_identity = record.get("canonicalization_source_identity", {})
    if isinstance(source_identity, Mapping) and source_identity:
        payload["canonicalization_source_identity"] = dict(source_identity)
    return _stable_json_hash(payload)


def _canonicalization_cjk_failure_reason(result: CanonicalizationResultPayload) -> str:
    checks = (
        ("canonical_question", result.canonical_question),
        ("legal_issue_frame", result.legal_issue_frame),
        ("desired_outcome", result.desired_outcome),
    )
    for field_name, value in checks:
        if value and CJK_RE.search(value):
            return f"contract_invalid:cjk_characters_detected:{field_name}"
    list_checks = (
        ("facts", result.facts),
        ("authority_context", result.authority_context),
        ("hidden_issues", result.hidden_issues),
    )
    for field_name, values in list_checks:
        for index, value in enumerate(values):
            if value and CJK_RE.search(value):
                return f"contract_invalid:cjk_characters_detected:{field_name}[{index}]"
    return ""


def _failed_canonicalization_evidence(
    *,
    task_id: str,
    canonicalization_run_id: str,
    failure_reason: str,
    status: str = "failed",
    task_scope: str = "question_candidate",
    candidate_id: str = "",
    source_task: Mapping[str, Any] | None = None,
    raw_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source = dict(source_task or {})
    raw = dict(raw_payload or {})
    run_id = canonicalization_run_id or "tg-question-canonicalization-run:unspecified"
    evidence = {
        "canonicalization_evidence_id": _stable_id("tg-question-canonicalization-evidence", run_id, task_id),
        "task_id": task_id,
        "task_scope": str(source.get("task_scope", task_scope)),
        "candidate_id": str(source.get("candidate_id", candidate_id)),
        "canonicalization_run_id": run_id,
        "canonicalization_contract_version": str(
            source.get("canonicalization_contract_version", CANONICALIZATION_CONTRACT_VERSION)
        ),
        "canonicalization_identity_policy_version": CANONICALIZATION_IDENTITY_POLICY_VERSION,
        "canonicalization_batch_id": str(source.get("canonicalization_batch_id", "")),
        "canonicalization_batch_hash": str(source.get("canonicalization_batch_hash", "")),
        "task_input_hash": str(source.get("task_input_hash", "")),
        "prompt_version": str(source.get("prompt_version", CANONICALIZATION_PROMPT_VERSION)),
        "prompt_profile_hash": str(source.get("prompt_profile_hash", "")),
        "runtime_profile": dict(raw.get("runtime_profile", {})) if isinstance(raw.get("runtime_profile"), Mapping) else {},
        "runtime_profile_hash": str(raw.get("runtime_profile_hash", "")),
        "runtime_contour": "operator_managed_batch_or_fixture",
        "backend": "",
        "model_id": "",
        "status": status,
        "failure_reason": failure_reason,
        "canonical_question": "",
        "canonical_question_language": "",
        "legal_issue_frame": "",
        "legal_issue_frame_slug": "",
        "law_area": "",
        "facts": [],
        "desired_outcome": "",
        "authority_context": [],
        "hidden_issues": [],
        "is_legal_answer_required": False,
        "is_standalone_question": False,
        "exclusion_reason": "llm_failed" if status == "failed" else "malformed_input",
        "confidence": "low",
        "quality_flags": ["canonicalization_backlog"],
        "question_date": str(source.get("input", {}).get("question_date", "")),
        "source_question_text_redacted": str(source.get("input", {}).get("question_text_redacted", "")),
        "identity_validation_status": "failed",
        "provenance": _canonicalization_provenance(
            source,
            raw,
            expected_identity={
                "canonicalization_batch_id": str(source.get("canonicalization_batch_id", "")),
                "canonicalization_batch_hash": str(source.get("canonicalization_batch_hash", "")),
                "task_input_hash": str(source.get("task_input_hash", "")),
                "prompt_profile_hash": str(source.get("prompt_profile_hash", "")),
            },
            identity_validation_status="failed",
        ),
    }
    source_identity = source.get("canonicalization_source_identity", {})
    if isinstance(source_identity, Mapping) and source_identity:
        evidence["canonicalization_source_identity"] = dict(source_identity)
    evidence["canonicalization_evidence_hash"] = _canonicalization_evidence_hash(evidence)
    return evidence


def _canonicalization_provenance(
    source_task: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    expected_identity: Mapping[str, str] | None = None,
    identity_validation_status: str = "",
) -> dict[str, Any]:
    source_input = source_task.get("input", {}) if isinstance(source_task.get("input"), Mapping) else {}
    raw_provenance = payload.get("provenance", {}) if isinstance(payload.get("provenance"), Mapping) else {}
    identity = dict(expected_identity or {})
    return {
        "source_candidate_artifact": str(
            raw_provenance.get("source_candidate_artifact", source_input.get("source_candidate_artifact", ""))
        ),
        "source_message_ids": _as_string_list(
            raw_provenance.get("source_message_ids", source_input.get("source_message_ids", []))
        ),
        "source_candidate_id": str(source_task.get("candidate_id", payload.get("candidate_id", ""))),
        "canonicalization_identity": {
            "policy_version": CANONICALIZATION_IDENTITY_POLICY_VERSION,
            **identity,
            "validation_status": identity_validation_status,
        },
    }


def _canonical_embedding_batch_item(evidence: Mapping[str, Any], *, text_role: str, text: str) -> dict[str, Any]:
    evidence_id = str(evidence.get("canonicalization_evidence_id", ""))
    embedding_item_id = _stable_id("tg-canonical-embedding", evidence_id, text_role, text)
    return {
        "embedding_item_id": embedding_item_id,
        "candidate_id": str(evidence.get("candidate_id", "")),
        "canonicalization_evidence_id": evidence_id,
        "text_role": text_role,
        "embedding_input_text": QUERY_PREFIX + text,
        "embedding_prefix": QUERY_PREFIX.strip(),
        "cluster_usage": ["canonical_legal_issue_cluster"],
        "canonicalization_run_id": str(evidence.get("canonicalization_run_id", "")),
        "legal_issue_frame_slug": str(evidence.get("legal_issue_frame_slug", "")),
        "law_area": str(evidence.get("law_area", "")),
        "authority_context": _as_string_list(evidence.get("authority_context", [])),
        "embedding_profile_expected": {
            "query_prefix": QUERY_PREFIX,
            "document_prefix": DOCUMENT_PREFIX,
            "routing_mode": "local_only",
            "task_semantics": "retrieval.query",
        },
        "policy_version": CANONICAL_EMBEDDING_POLICY_VERSION,
    }


def _canonical_embedding_record(
    *,
    batch_item: Mapping[str, Any],
    raw_vector_record: Mapping[str, Any] | None,
    profile: EmbeddingProfile,
) -> dict[str, Any]:
    failure_reason = ""
    vector: list[float] = []
    if raw_vector_record is None:
        failure_reason = "missing_external_vector_record"
    else:
        try:
            vector = _extract_vector(raw_vector_record)
            validate_vector(vector, profile)
        except (TypeError, ValueError) as exc:
            failure_reason = str(exc)
    return {
        "embedding_item_id": str(batch_item.get("embedding_item_id", "")),
        "candidate_id": str(batch_item.get("candidate_id", "")),
        "canonicalization_evidence_id": str(batch_item.get("canonicalization_evidence_id", "")),
        "text_role": str(batch_item.get("text_role", "")),
        "embedding_profile_id": profile.embedding_profile_id,
        "provider": profile.provider,
        "model": profile.model_id,
        "variant": profile.variant,
        "dimensions": profile.dimensions,
        "normalized": profile.normalized,
        "query_prefix": profile.query_prefix,
        "document_prefix": profile.document_prefix,
        "routing_mode": profile.routing_mode,
        "task_semantics": "retrieval.query",
        "backend_name": str((raw_vector_record or {}).get("backend_name", "external_jsonl_import")),
        "vector": vector if not failure_reason else [],
        "embedding_status": "failed" if failure_reason else "completed",
        "failure_reason": failure_reason,
        "legal_issue_frame_slug": str(batch_item.get("legal_issue_frame_slug", "")),
        "law_area": str(batch_item.get("law_area", "")),
        "cluster_usage": _as_string_list(batch_item.get("cluster_usage", [])),
        "policy_version": str(batch_item.get("policy_version", CANONICAL_EMBEDDING_POLICY_VERSION)),
    }


def _legal_issue_cluster(
    slug: str,
    records: list[dict[str, Any]],
    *,
    completed_embedding_evidence_ids: set[str],
    embeddings_available: bool,
) -> dict[str, Any]:
    sorted_records = sorted(records, key=lambda item: str(item.get("canonicalization_evidence_id", "")))
    representative = _representative_evidence(sorted_records)
    law_areas = sorted({str(item.get("law_area", "")) for item in sorted_records if str(item.get("law_area", ""))})
    authority_context = sorted(
        {
            value
            for item in sorted_records
            for value in _as_string_list(item.get("authority_context", []))
            if value
        }
    )
    confidences = [str(item.get("confidence", "low")) for item in sorted_records]
    cluster_confidence = _cluster_confidence(confidences)
    quality_flags = _cluster_quality_flags(
        sorted_records,
        law_areas=law_areas,
        authority_context=authority_context,
        completed_embedding_evidence_ids=completed_embedding_evidence_ids,
        embeddings_available=embeddings_available,
    )
    return {
        "legal_issue_cluster_id": _stable_id("tg-legal-issue-cluster", slug, [item.get("candidate_id", "") for item in sorted_records]),
        "legal_issue_frame_slug": slug,
        "canonical_question_representative": str(representative.get("canonical_question", "")),
        "legal_issue_frame_representative": str(representative.get("legal_issue_frame", "")),
        "law_area": law_areas[0] if len(law_areas) == 1 else ("mixed" if law_areas else ""),
        "authority_context": authority_context,
        "candidate_ids": [str(item.get("candidate_id", "")) for item in sorted_records],
        "canonicalization_evidence_ids": [str(item.get("canonicalization_evidence_id", "")) for item in sorted_records],
        "source_question_dates": sorted(
            {str(item.get("question_date", "")) for item in sorted_records if str(item.get("question_date", ""))}
        ),
        "representative_raw_questions": _representative_raw_questions(sorted_records),
        "cluster_size": len(sorted_records),
        "cluster_confidence": cluster_confidence,
        "cluster_quality_flags": quality_flags,
        "merge_policy_version": ISSUE_CLUSTER_POLICY_VERSION,
        "review_route": "needs_cluster_review",
        "coverage_status": "unmeasured",
        "provenance": {
            "source_canonicalization_run_ids": sorted({str(item.get("canonicalization_run_id", "")) for item in sorted_records}),
            "trust_boundary": "cluster_is_review_candidate_not_approved_legal_issue",
        },
    }


def _cluster_quality_flags(
    records: list[dict[str, Any]],
    *,
    law_areas: list[str],
    authority_context: list[str],
    completed_embedding_evidence_ids: set[str],
    embeddings_available: bool,
) -> list[str]:
    flags: list[str] = []
    if any(str(item.get("confidence", "")) == "low" for item in records):
        flags.append("low_confidence_present")
    if len(records) > 25:
        flags.append("broad_cluster")
    if len(law_areas) > 1:
        flags.append("mixed_law_area")
    if len(authority_context) > 4:
        flags.append("broad_authority_context")
    if embeddings_available:
        missing = [
            item
            for item in records
            if str(item.get("canonicalization_evidence_id", "")) not in completed_embedding_evidence_ids
        ]
        if missing:
            flags.append("missing_embedding_evidence")
    return flags


def _coverage_record(
    cluster: Mapping[str, Any],
    *,
    reviewed_case_index: Mapping[str, list[dict[str, str]]],
    question_bank_index: Mapping[str, list[dict[str, str]]],
) -> dict[str, Any]:
    cluster_id = str(cluster.get("legal_issue_cluster_id", ""))
    slug = str(cluster.get("legal_issue_frame_slug", ""))
    quality_flags = _as_string_list(cluster.get("cluster_quality_flags", []))
    best_case = reviewed_case_index.get(slug, [None])[0]
    best_bank = question_bank_index.get(slug, [None])[0]
    coverage_status = "uncovered"
    case_score = 0.0
    frame_score = 0.0
    flags: list[str] = []

    if str(cluster.get("coverage_status", "")) == "excluded":
        coverage_status = "excluded"
    elif "low_confidence_present" in quality_flags or str(cluster.get("cluster_confidence", "")) == "low":
        coverage_status = "uncertain"
    elif best_case:
        coverage_status = "covered"
        case_score = 1.0
        frame_score = 1.0
    elif best_bank:
        coverage_status = "partial"
        frame_score = 1.0
        flags.append("question_bank_only_no_reviewed_final_case")
    else:
        partial_match = _best_partial_match(slug, reviewed_case_index)
        if partial_match:
            coverage_status = "partial"
            best_case = partial_match
            frame_score = float(partial_match.get("score", 0.0))
            flags.append("canonical_frame_token_overlap_only")
        else:
            flags.append("no_reviewed_case_or_question_bank_match")

    return {
        "coverage_record_id": _stable_id("tg-canonical-coverage", cluster_id, slug),
        "legal_issue_cluster_id": cluster_id,
        "legal_issue_frame_slug": slug,
        "canonical_question_representative": str(cluster.get("canonical_question_representative", "")),
        "law_area": str(cluster.get("law_area", "")),
        "authority_context": _as_string_list(cluster.get("authority_context", [])),
        "cluster_quality_flags": quality_flags,
        "coverage_analysis_version": COVERAGE_ANALYSIS_VERSION,
        "coverage_status": coverage_status,
        "best_reviewed_case_id": str((best_case or {}).get("id", "")),
        "best_question_bank_entry_id": str((best_bank or {}).get("id", "")),
        "question_similarity_score": case_score,
        "issue_frame_similarity_score": frame_score,
        "supporting_candidate_ids": _as_string_list(cluster.get("candidate_ids", [])),
        "coverage_gap_flags": flags,
        "known_limitations": [
            "coverage decision does not validate legal correctness",
            "raw question embedding coverage is not reused as legal question-space coverage",
        ],
    }


def _temporal_currentness_review_record(
    cluster: Mapping[str, Any],
    *,
    evaluation_date: str,
    legal_corpus_as_of_date: str,
) -> dict[str, Any]:
    cluster_id = str(cluster.get("legal_issue_cluster_id", ""))
    source_dates = _source_question_dates(cluster)
    suggested_state = _temporal_relevance_state(cluster)
    return {
        "temporal_currentness_review_id": _stable_id(
            "tg-temporal-currentness-review", cluster_id, source_dates, evaluation_date, legal_corpus_as_of_date
        ),
        "legal_issue_cluster_id": cluster_id,
        "legal_issue_frame_slug": str(cluster.get("legal_issue_frame_slug", "")),
        "canonical_question_representative": _redact_private_text(
            str(cluster.get("canonical_question_representative", ""))
        ),
        "law_area": str(cluster.get("law_area", "")),
        "authority_context": _as_string_list(cluster.get("authority_context", [])),
        "source_question_dates": source_dates,
        "evaluation_date": evaluation_date,
        "legal_corpus_as_of_date": legal_corpus_as_of_date,
        "suggested_temporal_relevance_state": suggested_state,
        "allowed_temporal_relevance_states": list(TEMPORAL_RELEVANCE_STATES),
        "current_default_eligible": suggested_state in CURRENT_DEFAULT_TEMPORAL_STATES,
        "review_instruction": (
            "Set temporal_relevance_state before current-default question-bank or final evaluation promotion."
        ),
        "review_decision_template": {
            "legal_issue_cluster_id": cluster_id,
            "temporal_relevance_state": suggested_state,
            "source_question_date": source_dates[0] if source_dates else "",
            "evaluation_date": evaluation_date,
            "legal_corpus_as_of_date": legal_corpus_as_of_date,
            "temporal_review_date": "",
            "temporal_review_reason": "",
        },
        "policy_version": TEMPORAL_CURRENTNESS_POLICY_VERSION,
        "trust_boundary": "temporal_currentness_record_requires_human_review_before_current_default_promotion",
    }


def _review_decision_record(raw: Mapping[str, Any], *, clusters: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    cluster_id = str(raw.get("legal_issue_cluster_id", raw.get("cluster_id", "")))
    decision = str(raw.get("decision", ""))
    action = str(raw.get("reference_answer_action", "none") or "none")
    failure_reason = ""
    if cluster_id not in clusters:
        failure_reason = "unknown_legal_issue_cluster_id"
    elif decision not in CLUSTER_REVIEW_DECISIONS:
        failure_reason = f"invalid_decision:{decision}"
    elif action not in REFERENCE_ANSWER_ACTIONS:
        failure_reason = f"invalid_reference_answer_action:{action}"
    cluster = clusters.get(cluster_id, {})
    manual_answer = _redact_private_text(str(raw.get("manual_reference_answer_text_redacted", "")))
    selected_answer = _redact_private_text(
        str(raw.get("selected_reference_answer_text_redacted", raw.get("reference_answer_text_redacted", "")))
    )
    record = {
        "cluster_review_decision_id": _stable_id("tg-cluster-review-decision", cluster_id, decision, raw),
        "legal_issue_cluster_id": cluster_id,
        "decision": decision,
        "decision_scope": str(raw.get("decision_scope", "cluster")),
        "reviewed_canonical_question": _redact_private_text(
            str(raw.get("reviewed_canonical_question", cluster.get("canonical_question_representative", "")))
        ),
        "reviewed_legal_issue_frame_slug": _slugify(
            str(raw.get("reviewed_legal_issue_frame_slug", cluster.get("legal_issue_frame_slug", "")))
        ),
        "reference_answer_action": action,
        "reference_answer_source": _reference_answer_source(action, raw),
        "manual_reference_answer_text_redacted": manual_answer,
        "selected_reference_answer_text_redacted": selected_answer,
        "reviewer_hash": str(raw.get("reviewer_hash", "")),
        "reviewed_at": str(raw.get("reviewed_at", "")) or _utc_timestamp(),
        "decision_reason": str(raw.get("decision_reason", "")),
        "temporal_relevance_state": _temporal_relevance_state(raw, clusters.get(cluster_id, {})),
        "source_question_date": str(raw.get("source_question_date", "")),
        "legal_corpus_as_of_date": str(raw.get("legal_corpus_as_of_date", "")),
        "temporal_review_date": str(raw.get("temporal_review_date", "")) or _utc_timestamp(),
        "temporal_review_reason": str(raw.get("temporal_review_reason", "")),
        "status": "failed" if failure_reason else "completed",
        "failure_reason": failure_reason,
        "review_policy_version": CLUSTER_REVIEW_POLICY_VERSION,
    }
    return record


def _question_bank_entry(cluster: Mapping[str, Any], decision: Mapping[str, Any]) -> dict[str, Any]:
    cluster_id = str(cluster.get("legal_issue_cluster_id", ""))
    temporal_state = _temporal_relevance_state(decision, cluster)
    reference_status = (
        "reviewed_reference_available"
        if _decision_reference_answer_text(decision) and _reference_answer_source(str(decision.get("reference_answer_action", "")), decision)
        else "missing_reference_answer"
    )
    return {
        "question_bank_entry_id": _stable_id("tg-question-bank-entry", cluster_id, decision.get("cluster_review_decision_id", "")),
        "legal_issue_cluster_id": cluster_id,
        "canonical_question": _redact_private_text(
            str(decision.get("reviewed_canonical_question", cluster.get("canonical_question_representative", "")))
        ),
        "legal_issue_frame_slug": str(
            decision.get("reviewed_legal_issue_frame_slug", cluster.get("legal_issue_frame_slug", ""))
        ),
        "law_area": str(cluster.get("law_area", "")),
        "authority_context": _as_string_list(cluster.get("authority_context", [])),
        "representative_raw_questions": _as_string_list(cluster.get("representative_raw_questions", [])),
        "source_question_dates": _source_question_dates(cluster),
        "temporal_relevance_state": temporal_state,
        "current_default_eligible": temporal_state in CURRENT_DEFAULT_TEMPORAL_STATES,
        "temporal_currentness": _temporal_currentness_payload(decision, cluster, temporal_state=temporal_state),
        "coverage_status": str(cluster.get("coverage_status", "unmeasured")),
        "review_status": "approved_final_evaluation"
        if str(decision.get("decision", "")) == "approve_final_evaluation"
        else "approved_question_bank",
        "reference_answer_status": reference_status,
        "provenance": {
            "cluster_review_decision_id": str(decision.get("cluster_review_decision_id", "")),
            "canonicalization_evidence_ids": _as_string_list(cluster.get("canonicalization_evidence_ids", [])),
            "candidate_ids": _as_string_list(cluster.get("candidate_ids", [])),
        },
        "question_bank_policy_version": QUESTION_BANK_POLICY_VERSION,
    }


def _final_case_candidate(entry: Mapping[str, Any], decision: Mapping[str, Any] | None) -> dict[str, Any]:
    cluster_id = str(entry.get("legal_issue_cluster_id", ""))
    reasons: list[str] = []
    reference_text = ""
    reference_source = ""
    promotion_status = "rejected"
    review_status = str(entry.get("review_status", ""))
    temporal_state = _temporal_relevance_state(entry, decision or {})

    if decision is None or str(decision.get("decision", "")) != "approve_final_evaluation":
        reasons.append("not_approved_for_final_evaluation")
    else:
        reference_text = _decision_reference_answer_text(decision)
        reference_source = _reference_answer_source(str(decision.get("reference_answer_action", "")), decision)
        if reference_source in {"llm", "llm_canonicalization_only"}:
            promotion_status = "rejected"
            reasons.append("llm_only")
        elif not reference_text:
            promotion_status = "blocked_missing_reference_answer"
            reasons.append("missing_reference_answer")
        elif reference_source:
            promotion_status = "eligible"
            reasons.append("reviewed_reference_answer_available")
        else:
            promotion_status = "blocked_missing_reference_answer"
            reasons.append("missing_reference_answer")

    if promotion_status == "eligible" and temporal_state not in CURRENT_DEFAULT_TEMPORAL_STATES:
        promotion_status = "blocked_temporal_currentness"
        reasons.append(f"temporal_currentness:{temporal_state}")

    return {
        "case_candidate_id": _stable_id("tg-reviewed-case-candidate", cluster_id, entry.get("question_bank_entry_id", "")),
        "legal_issue_cluster_id": cluster_id,
        "source_006_case_id": str(entry.get("source_006_case_id", "")),
        "canonical_question": _redact_private_text(str(entry.get("canonical_question", ""))),
        "question_text_redacted": _redact_private_text(str(entry.get("canonical_question", ""))),
        "reference_answer_text_redacted": reference_text,
        "reference_answer_source": reference_source,
        "reference_answer_role": "reviewed_reference_answer" if reference_text and reference_source else "",
        "review_status": review_status,
        "promotion_status": promotion_status,
        "promotion_reasons": reasons,
        "law_area": str(entry.get("law_area", "")),
        "authority_context": _as_string_list(entry.get("authority_context", [])),
        "source_question_dates": _source_question_dates(entry),
        "temporal_relevance_state": temporal_state,
        "current_default_eligible": temporal_state in CURRENT_DEFAULT_TEMPORAL_STATES,
        "temporal_currentness": _temporal_currentness_payload(entry, decision or {}, temporal_state=temporal_state),
        "legal_issue_frame_slug": str(entry.get("legal_issue_frame_slug", "")),
        "provenance": {
            "question_bank_entry_id": str(entry.get("question_bank_entry_id", "")),
            "cluster_review_decision_id": str((decision or {}).get("cluster_review_decision_id", "")),
            "canonicalization_evidence_ids": _as_string_list(entry.get("provenance", {}).get("canonicalization_evidence_ids", []))
            if isinstance(entry.get("provenance"), Mapping)
            else [],
        },
        "promotion_policy_version": PROMOTION_POLICY_VERSION,
        "reference_answer_policy_version": REFERENCE_ANSWER_POLICY_VERSION,
    }


def _reviewed_final_case(candidate: Mapping[str, Any]) -> dict[str, Any]:
    cluster_id = str(candidate.get("legal_issue_cluster_id", ""))
    return {
        "case_id": _stable_id("tg-reviewed-canonical-case", cluster_id, candidate.get("case_candidate_id", "")),
        "case_candidate_id": str(candidate.get("case_candidate_id", "")),
        "legal_issue_cluster_id": cluster_id,
        "canonical_question": _redact_private_text(str(candidate.get("canonical_question", ""))),
        "question_text_redacted": _redact_private_text(str(candidate.get("question_text_redacted", ""))),
        "reference_answer_text_redacted": _redact_private_text(str(candidate.get("reference_answer_text_redacted", ""))),
        "reference_answer_source": str(candidate.get("reference_answer_source", "")),
        "reference_answer_role": str(candidate.get("reference_answer_role", "")),
        "review_status": str(candidate.get("review_status", "")),
        "law_area": str(candidate.get("law_area", "")),
        "authority_context": _as_string_list(candidate.get("authority_context", [])),
        "source_question_dates": _source_question_dates(candidate),
        "temporal_relevance_state": str(candidate.get("temporal_relevance_state", "")),
        "temporal_currentness": dict(candidate.get("temporal_currentness", {}))
        if isinstance(candidate.get("temporal_currentness"), Mapping)
        else {},
        "legal_issue_frame_slug": str(candidate.get("legal_issue_frame_slug", "")),
        "provenance": dict(candidate.get("provenance", {})) if isinstance(candidate.get("provenance"), Mapping) else {},
        "dataset_policy_version": REVIEWED_DATASET_POLICY_VERSION,
    }


def _temporal_relevance_state(*sources: Mapping[str, Any] | None) -> str:
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        value = str(source.get("temporal_relevance_state", "")).strip()
        if value in TEMPORAL_RELEVANCE_STATES:
            return value
        currentness = source.get("temporal_currentness", {})
        if isinstance(currentness, Mapping):
            value = str(currentness.get("temporal_relevance_state", "")).strip()
            if value in TEMPORAL_RELEVANCE_STATES:
                return value
    return "unresolved_currentness"


def _source_question_dates(source: Mapping[str, Any]) -> list[str]:
    dates = _as_string_list(source.get("source_question_dates", []))
    for key in ("source_question_date", "question_date"):
        value = str(source.get(key, ""))
        if value:
            dates.append(value)
    return sorted({value for value in dates if value})


def _temporal_currentness_payload(
    primary: Mapping[str, Any],
    fallback: Mapping[str, Any],
    *,
    temporal_state: str,
) -> dict[str, Any]:
    source_dates = _source_question_dates(primary) or _source_question_dates(fallback)
    source_currentness = primary.get("temporal_currentness", {})
    fallback_currentness = fallback.get("temporal_currentness", {})
    if not isinstance(source_currentness, Mapping):
        source_currentness = {}
    if not isinstance(fallback_currentness, Mapping):
        fallback_currentness = {}
    source_question_date = str(
        primary.get(
            "source_question_date",
            source_currentness.get(
                "source_question_date",
                fallback.get("source_question_date", fallback_currentness.get("source_question_date", "")),
            ),
        )
    )
    if not source_question_date and source_dates:
        source_question_date = source_dates[0]
    return {
        "temporal_relevance_state": temporal_state,
        "source_question_dates": source_dates,
        "source_question_date": source_question_date,
        "evaluation_date": str(
            primary.get(
                "evaluation_date",
                source_currentness.get("evaluation_date", fallback_currentness.get("evaluation_date", "")),
            )
        ),
        "legal_corpus_as_of_date": str(
            primary.get(
                "legal_corpus_as_of_date",
                source_currentness.get(
                    "legal_corpus_as_of_date",
                    fallback.get("legal_corpus_as_of_date", fallback_currentness.get("legal_corpus_as_of_date", "")),
                ),
            )
        ),
        "temporal_review_date": str(
            primary.get(
                "temporal_review_date",
                source_currentness.get(
                    "temporal_review_date",
                    fallback.get("temporal_review_date", fallback_currentness.get("temporal_review_date", "")),
                ),
            )
        ),
        "temporal_review_reason": str(
            primary.get(
                "temporal_review_reason",
                source_currentness.get(
                    "temporal_review_reason",
                    fallback.get("temporal_review_reason", fallback_currentness.get("temporal_review_reason", "")),
                ),
            )
        ),
        "current_default_eligible": temporal_state in CURRENT_DEFAULT_TEMPORAL_STATES,
        "policy_version": TEMPORAL_CURRENTNESS_POLICY_VERSION,
    }


def _decision_reference_answer_text(decision: Mapping[str, Any]) -> str:
    action = str(decision.get("reference_answer_action", "none"))
    if action == "replace_manual":
        return _redact_private_text(str(decision.get("manual_reference_answer_text_redacted", "")))
    if action == "keep_selected_telegram_answer":
        return _redact_private_text(
            str(
                decision.get(
                    "selected_reference_answer_text_redacted",
                    decision.get("manual_reference_answer_text_redacted", ""),
                )
            )
        )
    return ""


def _reference_answer_source(action: str, raw: Mapping[str, Any]) -> str:
    explicit = str(raw.get("reference_answer_source", ""))
    if explicit:
        return explicit
    if action == "replace_manual":
        return "manual_review_override"
    if action == "keep_selected_telegram_answer":
        return "accepted_telegram_answer"
    return ""


def _eligible_final_candidate(candidate: Mapping[str, Any]) -> bool:
    if str(candidate.get("promotion_status", "")) != "eligible":
        return False
    if not str(candidate.get("reference_answer_text_redacted", "")).strip():
        return False
    if str(candidate.get("reference_answer_source", "")) in {"llm", "llm_canonicalization_only", ""}:
        return False
    return True


def _representative_evidence(records: list[dict[str, Any]]) -> dict[str, Any]:
    high = [item for item in records if str(item.get("confidence", "")) == "high"]
    medium = [item for item in records if str(item.get("confidence", "")) == "medium"]
    return (high or medium or records)[0]


def _representative_raw_questions(records: list[dict[str, Any]], *, limit: int = 5) -> list[str]:
    values = []
    for record in records:
        text = _redact_private_text(
            str(record.get("source_question_text_redacted", record.get("canonical_question", ""))).strip()
        )
        if text and text not in values:
            values.append(text)
    return values[:limit]


def _cluster_confidence(confidences: list[str]) -> str:
    if not confidences:
        return "low"
    if all(value == "high" for value in confidences):
        return "high"
    if any(value == "low" for value in confidences):
        return "low"
    return "medium"


def _slug_index(records: list[dict[str, Any]], *, id_field: str) -> dict[str, list[dict[str, str]]]:
    index: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in records:
        slug = _record_issue_slug(item)
        if not slug:
            continue
        index[slug].append({"id": str(item.get(id_field, "")), "slug": slug, "score": "1.0"})
    return index


def _record_issue_slug(item: Mapping[str, Any]) -> str:
    for key in (
        "legal_issue_frame_slug",
        "canonical_legal_issue_frame_slug",
        "canonical_issue_slug",
        "issue_frame_slug",
    ):
        value = str(item.get(key, ""))
        if value:
            return _slugify(value)
    provenance = item.get("provenance", {})
    if isinstance(provenance, Mapping):
        return _slugify(str(provenance.get("legal_issue_frame_slug", "")))
    return ""


def _best_partial_match(slug: str, reviewed_case_index: Mapping[str, list[dict[str, str]]]) -> dict[str, str] | None:
    best: dict[str, str] | None = None
    best_score = 0.0
    for case_slug, records in reviewed_case_index.items():
        score = _token_jaccard(slug, case_slug)
        if score > best_score:
            best_score = score
            best = dict(records[0])
            best["score"] = f"{score:.3f}"
    return best if best is not None and best_score >= 0.35 else None


def _token_jaccard(left: str, right: str) -> float:
    left_tokens = {token for token in left.split("_") if token}
    right_tokens = {token for token in right.split("_") if token}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _read_decision_records(path: str | Path) -> list[dict[str, Any]]:
    decision_path = Path(path)
    if decision_path.suffix.lower() == ".tsv":
        with decision_path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle, delimiter="\t")]
    return _read_jsonl(path)


def _canonicalization_review_decision_record(
    raw: Mapping[str, Any],
    *,
    tasks_by_id: Mapping[str, Mapping[str, Any]],
    qwen_by_task: Mapping[str, Mapping[str, Any]],
    verifier_by_task: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    task_id = str(raw.get("task_id", ""))
    candidate_id = str(raw.get("candidate_id", ""))
    decision = str(raw.get("decision", ""))
    failure_reason = ""
    source_task = tasks_by_id.get(task_id)
    qwen_payload = _extract_result_payload(qwen_by_task.get(task_id, {})) if task_id in qwen_by_task else {}
    verifier_payload = _extract_result_payload(verifier_by_task.get(task_id, {})) if task_id in verifier_by_task else {}
    supplied_review_payload_version = str(raw.get("review_payload_version", ""))
    supplied_review_payload_hash = str(raw.get("review_payload_hash", ""))
    expected_review_payload_hash = ""
    review_evidence_binding_status = "legacy_unverified"
    if source_task is not None:
        review_card = _review_card_record(
            source_task,
            qwen_result=qwen_by_task.get(task_id),
            verifier_result=verifier_by_task.get(task_id),
        )
        expected_review_payload_hash = str(review_card.get("review_payload_hash", ""))
        if supplied_review_payload_hash:
            if not supplied_review_payload_version:
                review_evidence_binding_status = "missing_version"
            elif supplied_review_payload_version != CANONICALIZATION_REVIEW_PAYLOAD_VERSION:
                review_evidence_binding_status = "unsupported_version"
            elif supplied_review_payload_hash != expected_review_payload_hash:
                review_evidence_binding_status = "mismatch"
            elif str(qwen_payload.get("canonicalization_evidence_hash", "")):
                review_evidence_binding_status = "validated"
            else:
                review_evidence_binding_status = "legacy_identity_unverified"
    manual_canonicalization, manual_failure_reason = _coerce_manual_canonicalization(
        raw.get(
            "manual_canonicalization",
            raw.get("manual_canonicalization_json", raw.get("manual_canonicalization_text", "")),
        )
    )
    if not task_id:
        failure_reason = "missing_task_id"
    elif source_task is None:
        failure_reason = "unknown_task_id"
    elif decision not in CANONICALIZATION_REVIEW_DECISIONS:
        failure_reason = f"invalid_decision:{decision}"
    elif candidate_id and source_task and candidate_id != str(source_task.get("candidate_id", "")):
        failure_reason = "candidate_id_mismatch_for_task"
    elif review_evidence_binding_status == "missing_version":
        failure_reason = "review_payload_version_missing"
    elif review_evidence_binding_status == "unsupported_version":
        failure_reason = (
            f"unsupported_review_payload_version:{supplied_review_payload_version}"
        )
    elif review_evidence_binding_status == "mismatch":
        failure_reason = "review_payload_hash_mismatch"
    elif manual_failure_reason:
        failure_reason = manual_failure_reason
    record = {
        "canonicalization_review_decision_id": _stable_id("tg-canonicalization-review-decision", task_id, decision, raw),
        "task_id": task_id,
        "candidate_id": candidate_id or str((source_task or {}).get("candidate_id", "")),
        "decision": decision,
        "reviewer_hash": str(raw.get("reviewer_hash", "")),
        "reviewed_at": str(raw.get("reviewed_at", "")) or _utc_timestamp(),
        "decision_reason": str(raw.get("decision_reason", "")),
        "review_payload_version": supplied_review_payload_version,
        "expected_review_payload_version": CANONICALIZATION_REVIEW_PAYLOAD_VERSION,
        "review_payload_hash": supplied_review_payload_hash,
        "expected_review_payload_hash": expected_review_payload_hash,
        "review_evidence_binding_status": review_evidence_binding_status,
        "canonicalization_batch_id": str((source_task or {}).get("canonicalization_batch_id", "")),
        "canonicalization_batch_hash": str((source_task or {}).get("canonicalization_batch_hash", "")),
        "task_input_hash": str((source_task or {}).get("task_input_hash", "")),
        "prompt_profile_hash": str((source_task or {}).get("prompt_profile_hash", "")),
        "qwen_status": str(qwen_payload.get("status", "")),
        "qwen_exclusion_reason": str(qwen_payload.get("exclusion_reason", "")),
        "verifier_verdict": str(verifier_payload.get("verdict", "")),
        "verifier_suggested_action": str(verifier_payload.get("suggested_action", "")),
        "qwen_canonicalization_evidence_hash": str(qwen_payload.get("canonicalization_evidence_hash", "")),
        "verifier_canonicalization_evidence_hash": str(verifier_payload.get("canonicalization_evidence_hash", "")),
        "verifier_prompt_version": str(verifier_payload.get("verifier_prompt_version", "")),
        "verifier_prompt_profile_hash": str(verifier_payload.get("verifier_prompt_profile_hash", "")),
        "status": "failed" if failure_reason else "completed",
        "failure_reason": failure_reason,
        "decision_policy_version": CANONICALIZATION_ROUTING_POLICY_VERSION,
    }
    if manual_canonicalization:
        record["manual_canonicalization"] = manual_canonicalization
    return record


def _coerce_manual_canonicalization(raw: Any) -> tuple[dict[str, Any], str]:
    if raw is None:
        return {}, ""
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}, ""
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            return {}, f"invalid_manual_canonicalization_json:{exc.msg}"
    if not isinstance(raw, Mapping):
        return {}, "invalid_manual_canonicalization:not_json_object"
    payload = dict(raw)
    return (payload, "") if payload else ({}, "")


def _manual_canonicalization_payload_from_decision(
    decision: Mapping[str, Any] | None,
    *,
    source_task: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    if not decision or str(decision.get("decision", "")) != "accept":
        return {}, ""
    manual_raw = decision.get("manual_canonicalization", {})
    if not isinstance(manual_raw, Mapping) or not manual_raw:
        return {}, ""

    payload = dict(manual_raw)
    source_input = source_task.get("input", {}) if isinstance(source_task.get("input"), Mapping) else {}
    payload["task_id"] = str(source_task.get("task_id", "")) or str(decision.get("task_id", ""))
    payload["task_scope"] = str(source_task.get("task_scope", "question_candidate"))
    payload["candidate_id"] = str(source_task.get("candidate_id", "")) or str(decision.get("candidate_id", ""))
    payload["canonicalization_run_id"] = str(payload.get("canonicalization_run_id", "")) or "tg-question-canonicalization-run:manual-review"
    payload["canonicalization_contract_version"] = str(
        source_task.get("canonicalization_contract_version", CANONICALIZATION_CONTRACT_VERSION)
    )
    payload["prompt_version"] = str(source_task.get("prompt_version", CANONICALIZATION_PROMPT_VERSION))
    payload["runtime_contour"] = "human_manual_review"
    payload["backend"] = "human_review"
    payload["model_id"] = "manual_override"
    payload["status"] = "completed"
    payload["failure_reason"] = ""
    payload["canonical_question_language"] = str(payload.get("canonical_question_language", "")) or "ru"
    payload["legal_issue_frame_slug"] = _slugify(
        str(payload.get("legal_issue_frame_slug", "")) or str(payload.get("legal_issue_frame", ""))
    )
    payload["exclusion_reason"] = str(payload.get("exclusion_reason", "")) or "none"
    payload["confidence"] = str(payload.get("confidence", "")) or "high"
    payload["is_legal_answer_required"] = payload.get("is_legal_answer_required", True)
    payload["is_standalone_question"] = payload.get("is_standalone_question", True)
    payload["facts"] = _as_string_list(payload.get("facts", []))
    payload["authority_context"] = _as_string_list(payload.get("authority_context", []))
    payload["hidden_issues"] = _as_string_list(payload.get("hidden_issues", []))
    quality_flags = _as_string_list(payload.get("quality_flags", []))
    if "manual_canonicalization_override" not in quality_flags:
        quality_flags.append("manual_canonicalization_override")
    payload["quality_flags"] = quality_flags

    required_text_fields = ("canonical_question", "legal_issue_frame", "law_area")
    for field_name in required_text_fields:
        if not str(payload.get(field_name, "")).strip():
            return {}, f"manual_canonicalization_missing_{field_name}"
    if str(payload.get("exclusion_reason", "")) != "none":
        return {}, "manual_canonicalization_accept_requires_exclusion_reason_none"

    try:
        result = CanonicalizationResultPayload.model_validate(
            {
                field_name: payload[field_name]
                for field_name in CanonicalizationResultPayload.model_fields
                if field_name in payload
            }
        )
    except ValidationError as exc:
        return {}, _pydantic_failure_reason(exc)
    cjk_failure_reason = _canonicalization_cjk_failure_reason(result)
    if cjk_failure_reason:
        return {}, cjk_failure_reason
    runtime_profile = _operator_runtime_profile(
        stage="manual_review",
        prompt_version=str(source_task.get("prompt_version", CANONICALIZATION_PROMPT_VERSION)),
        prompt_profile_hash=str(source_task.get("prompt_profile_hash", ""))
        or _canonicalization_prompt_profile_hash(str(source_task.get("prompt_version", CANONICALIZATION_PROMPT_VERSION))),
        provider="human_review",
        runtime_contour="human_manual_review",
        backend="human_review",
        model_id="manual_override",
        structured_output_method="manual_json",
        max_tokens=0,
        timeout_seconds=0,
        extra_body=None,
        input_batch_hash=str(source_task.get("canonicalization_batch_hash", "")),
    )
    record = _attach_operator_record_identity(
        result.model_dump(),
        stage="canonicalization",
        input_item=source_task,
        runtime_profile=runtime_profile,
    )
    record["source_question_text_redacted"] = str(source_input.get("question_text_redacted", ""))
    record["provenance"] = {
        "source": "human_review_manual_canonicalization",
        "reviewed_at": str(decision.get("reviewed_at", "")),
        "reviewer_hash": str(decision.get("reviewer_hash", "")),
    }
    _ensure_public_payload(record)
    return record, ""


def _effective_canonicalization_decision(
    qwen_payload: Mapping[str, Any],
    decision: Mapping[str, Any] | None,
    *,
    unreviewed_policy: str,
) -> str:
    if decision is not None and str(decision.get("decision", "")) in CANONICALIZATION_REVIEW_DECISIONS:
        return str(decision.get("decision", ""))
    if unreviewed_policy == "hold":
        return "hold"
    if str(qwen_payload.get("status", "")) != "completed":
        return "hold"
    if str(qwen_payload.get("exclusion_reason", "")) != "none":
        return "reject"
    return "accept"


def _effective_canonicalization_decision_source(
    qwen_payload: Mapping[str, Any],
    decision: Mapping[str, Any] | None,
    *,
    unreviewed_policy: str,
) -> str:
    if decision is not None and str(decision.get("decision", "")) in CANONICALIZATION_REVIEW_DECISIONS:
        return "human_review"
    if unreviewed_policy == "hold":
        return "unreviewed_hold"
    if str(qwen_payload.get("status", "")) != "completed":
        return "explicit_first_pass_hold_non_completed_qwen"
    if str(qwen_payload.get("exclusion_reason", "")) != "none":
        return "explicit_first_pass_reject_qwen_exclusion"
    return "explicit_first_pass_accept_qwen_included"


def _adjudication_candidate_entry(candidate_key: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    entry = {
        "candidate_key": candidate_key,
        "candidate_id": str(payload.get("candidate_id", "")),
        "canonicalization_run_id": str(payload.get("canonicalization_run_id", "")),
        "canonicalization_evidence_id": str(payload.get("canonicalization_evidence_id", "")),
        "canonicalization_batch_id": str(payload.get("canonicalization_batch_id", "")),
        "canonicalization_batch_hash": str(payload.get("canonicalization_batch_hash", "")),
        "task_input_hash": str(payload.get("task_input_hash", "")),
        "prompt_version": str(payload.get("prompt_version", "")),
        "prompt_profile_hash": str(payload.get("prompt_profile_hash", "")),
        "model_id": str(payload.get("model_id", "")),
        "status": str(payload.get("status", "")),
        "canonical_question": str(payload.get("canonical_question", "")),
        "canonical_question_language": str(payload.get("canonical_question_language", "")),
        "legal_issue_frame": str(payload.get("legal_issue_frame", "")),
        "legal_issue_frame_slug": str(payload.get("legal_issue_frame_slug", "")),
        "law_area": str(payload.get("law_area", "")),
        "facts": _as_string_list(payload.get("facts", [])),
        "desired_outcome": str(payload.get("desired_outcome", "")),
        "authority_context": _as_string_list(payload.get("authority_context", [])),
        "hidden_issues": _as_string_list(payload.get("hidden_issues", [])),
        "is_legal_answer_required": _bool_value(payload.get("is_legal_answer_required", False)),
        "is_standalone_question": _bool_value(payload.get("is_standalone_question", False)),
        "exclusion_reason": str(payload.get("exclusion_reason", "")),
        "confidence": str(payload.get("confidence", "")),
        "quality_flags": _as_string_list(payload.get("quality_flags", [])),
        "question_date": str(payload.get("question_date", "")),
    }
    entry["canonicalization_evidence_hash"] = str(payload.get("canonicalization_evidence_hash", "")) or _canonicalization_evidence_hash(
        {**payload, **entry}
    )
    return entry


def _adjudication_verifier_vote_entry(
    candidate_key: str,
    verifier_key: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "candidate_key": candidate_key,
        "verifier_key": verifier_key,
        "model_id": str(payload.get("model_id", "")),
        "canonicalization_evidence_id": str(payload.get("canonicalization_evidence_id", "")),
        "canonicalization_evidence_hash": str(payload.get("canonicalization_evidence_hash", "")),
        "verifier_prompt_version": str(payload.get("verifier_prompt_version", "")),
        "verifier_prompt_profile_hash": str(payload.get("verifier_prompt_profile_hash", "")),
        "runtime_profile_hash": str(payload.get("runtime_profile_hash", "")),
        "status": str(payload.get("status", "")) or "completed",
        "verdict": str(payload.get("verdict", "")),
        "confidence": payload.get("confidence", ""),
        "risk": str(payload.get("risk", "")),
        "bad_fields": _as_string_list(payload.get("bad_fields", [])),
        "short_reason": str(payload.get("short_reason", "")),
        "suggested_action": str(payload.get("suggested_action", "")),
    }


def _adjudication_verifier_vote_identity_status(
    vote: Mapping[str, Any],
    candidate: Mapping[str, Any] | None,
) -> tuple[str, str]:
    if candidate is None:
        return "invalid", "missing_candidate_for_verifier_vote"
    vote_hash = str(vote.get("canonicalization_evidence_hash", ""))
    candidate_hash = str(candidate.get("canonicalization_evidence_hash", ""))
    vote_evidence_id = str(vote.get("canonicalization_evidence_id", ""))
    candidate_evidence_id = str(candidate.get("canonicalization_evidence_id", ""))
    if not vote_hash or not candidate_hash:
        return "legacy_unverified", "missing_canonicalization_evidence_hash"
    if vote_hash != candidate_hash:
        return "invalid", "canonicalization_evidence_hash_mismatch"
    if vote_evidence_id and candidate_evidence_id and vote_evidence_id != candidate_evidence_id:
        return "invalid", "canonicalization_evidence_id_mismatch"
    return "compatible", ""


def _field_scope_review_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Repeat only the candidate fields that models often confuse with source text."""

    return {
        "candidate_key": str(candidate.get("candidate_key", "")),
        "status": str(candidate.get("status", "")),
        "exclusion_reason": str(candidate.get("exclusion_reason", "")),
        "canonical_question_under_review": str(candidate.get("canonical_question", "")),
        "legal_issue_frame_under_review": str(candidate.get("legal_issue_frame", "")),
        "facts_under_review": _as_string_list(candidate.get("facts", [])),
        "hidden_issues_under_review": _as_string_list(candidate.get("hidden_issues", [])),
        "quality_flags_under_review": _as_string_list(candidate.get("quality_flags", [])),
    }


def _candidate_signature_for_adjudication(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    status = str(candidate.get("status", ""))
    if status != "completed":
        return ("status", status)
    exclusion_reason = str(candidate.get("exclusion_reason", ""))
    law_area = str(candidate.get("law_area", ""))
    is_standalone = _bool_value(candidate.get("is_standalone_question", False))
    if exclusion_reason and exclusion_reason != "none":
        return ("excluded", exclusion_reason, law_area, is_standalone)
    canonical_question = _signature_text(str(candidate.get("canonical_question", "")))
    legal_issue_frame_slug = _slugify(
        str(candidate.get("legal_issue_frame_slug", "")) or str(candidate.get("legal_issue_frame", ""))
    )
    is_legal = _bool_value(candidate.get("is_legal_answer_required", False))
    return ("included", canonical_question, legal_issue_frame_slug, law_area, is_standalone, is_legal)


def _adjudication_consensus_summary(
    *,
    expected_candidate_keys: Sequence[str],
    candidates: Sequence[Mapping[str, Any]],
    verifier_votes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    candidate_by_key = {str(candidate.get("candidate_key", "")): candidate for candidate in candidates}
    votes_by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for vote in verifier_votes:
        votes_by_candidate[str(vote.get("candidate_key", ""))].append(dict(vote))

    reasons: set[str] = set()
    missing_candidate_keys = [key for key in expected_candidate_keys if key not in candidate_by_key]
    if missing_candidate_keys:
        reasons.add("candidate_missing")

    signatures = {
        _candidate_signature_for_adjudication(candidate)
        for candidate in candidate_by_key.values()
        if str(candidate.get("status", "")) == "completed"
    }
    if len(candidate_by_key) != len(expected_candidate_keys):
        pass
    elif any(str(candidate.get("status", "")) != "completed" for candidate in candidate_by_key.values()):
        reasons.add("candidate_not_completed")
    elif len(signatures) > 1:
        reasons.add("candidate_signature_disagreement")

    if not verifier_votes:
        reasons.add("no_verifier_votes")
    for vote in verifier_votes:
        candidate = candidate_by_key.get(str(vote.get("candidate_key", "")))
        identity_status, identity_reason = _adjudication_verifier_vote_identity_status(vote, candidate)
        if identity_status == "invalid":
            reasons.add("verifier_evidence_identity_mismatch")
        elif identity_status == "legacy_unverified":
            reasons.add("verifier_evidence_identity_unverified")

    candidate_summaries: list[dict[str, Any]] = []
    for candidate_key in expected_candidate_keys:
        candidate = candidate_by_key.get(candidate_key)
        votes = votes_by_candidate.get(candidate_key, [])
        status_counts = Counter(str(vote.get("status", "")) or "completed" for vote in votes)
        verdict_counts = Counter(
            str(vote.get("verdict", ""))
            for vote in votes
            if str(vote.get("status", "")) in {"", "completed"}
        )
        if candidate is not None and not votes:
            reasons.add("candidate_without_verifier_votes")
        if any(str(vote.get("status", "")) not in {"", "completed"} for vote in votes):
            reasons.add("verifier_not_completed")
        if any(str(vote.get("verdict", "")) == "fail" for vote in votes):
            reasons.add("verifier_fail")
        if any(str(vote.get("verdict", "")) == "uncertain" for vote in votes):
            reasons.add("verifier_uncertain")
        candidate_summaries.append(
            {
                "candidate_key": candidate_key,
                "status": "" if candidate is None else str(candidate.get("status", "")),
                "vote_count": len(votes),
                "pass_count": verdict_counts.get("pass", 0),
                "fail_count": verdict_counts.get("fail", 0),
                "uncertain_count": verdict_counts.get("uncertain", 0),
                "status_counts": dict(sorted(status_counts.items())),
                "all_verifier_votes_pass": bool(votes) and verdict_counts.get("pass", 0) == len(votes),
                "candidate_signature": [] if candidate is None else list(_candidate_signature_for_adjudication(candidate)),
            }
        )

    unanimous = not reasons and bool(expected_candidate_keys) and bool(verifier_votes)
    return {
        "expected_candidate_keys": list(expected_candidate_keys),
        "present_candidate_keys": sorted(candidate_by_key),
        "candidate_count": len(candidates),
        "verifier_vote_count": len(verifier_votes),
        "candidate_signatures_match": len(signatures) <= 1 and len(candidate_by_key) == len(expected_candidate_keys),
        "all_verifier_votes_pass": bool(verifier_votes)
        and all(str(vote.get("status", "")) in {"", "completed"} and str(vote.get("verdict", "")) == "pass" for vote in verifier_votes),
        "unanimous": unanimous,
        "escalation_reason_codes": sorted(reasons),
        "candidate_summaries": candidate_summaries,
    }


def _deepseek_adjudication_batch_item(
    *,
    source_task: Mapping[str, Any],
    qwen_payload: Mapping[str, Any],
    verifier_payload: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_entry = _adjudication_candidate_entry("primary", qwen_payload)
    verifier_votes = []
    if verifier_payload:
        verifier_votes.append(_adjudication_verifier_vote_entry("primary", "reviewer_1", verifier_payload))
    return {
        "task_id": str(qwen_payload.get("task_id", "")),
        "candidate_id": str(qwen_payload.get("candidate_id", "")) or str(source_task.get("candidate_id", "")),
        "canonicalization_batch_id": str(source_task.get("canonicalization_batch_id", "")),
        "canonicalization_batch_hash": str(source_task.get("canonicalization_batch_hash", "")),
        "task_input_hash": str(source_task.get("task_input_hash", "")),
        "canonicalization_contract_version": str(
            source_task.get("canonicalization_contract_version", "")
        ),
        "canonicalization_prompt_version": str(source_task.get("prompt_version", "")),
        "canonicalization_prompt_profile_hash": str(source_task.get("prompt_profile_hash", "")),
        "adjudication_prompt_version": CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION,
        "source_question_text_redacted": str(source_task.get("input", {}).get("question_text_redacted", "")),
        "question_date": str(source_task.get("input", {}).get("question_date", "")),
        "candidates": [candidate_entry],
        "verifier_votes": verifier_votes,
        "consensus_summary": _adjudication_consensus_summary(
            expected_candidate_keys=["primary"],
            candidates=[candidate_entry],
            verifier_votes=verifier_votes,
        ),
        "human_triage": {
            "decision": str(decision.get("decision", "")),
            "decision_reason": str(decision.get("decision_reason", "")),
            "reviewer_hash": str(decision.get("reviewer_hash", "")),
        },
        "expected_output_schema": {
            "verdict": "pass|fail|uncertain",
            "confidence": "0-100 integer",
            "risk": "none|low|medium|high",
            "bad_fields": "array[string]",
            "short_reason": "string",
            "final_recommendation": "accept|reject|retry_generator|human_review",
            "selected_candidate_key": "string",
        },
    }


def _retry_qwen_batch_item(
    *,
    source_task: Mapping[str, Any],
    qwen_payload: Mapping[str, Any],
    verifier_payload: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    record = dict(source_task)
    record["canonicalization_source_identity"] = _canonicalization_root_identity(source_task)
    record["retry_context"] = {
        "previous_candidate": {
            "candidate_key": "primary",
            "model_id": str(qwen_payload.get("model_id", "")),
            "canonical_question": str(qwen_payload.get("canonical_question", "")),
            "legal_issue_frame": str(qwen_payload.get("legal_issue_frame", "")),
            "legal_issue_frame_slug": str(qwen_payload.get("legal_issue_frame_slug", "")),
            "law_area": str(qwen_payload.get("law_area", "")),
            "facts": _as_string_list(qwen_payload.get("facts", [])),
            "desired_outcome": str(qwen_payload.get("desired_outcome", "")),
            "authority_context": _as_string_list(qwen_payload.get("authority_context", [])),
            "hidden_issues": _as_string_list(qwen_payload.get("hidden_issues", [])),
            "is_legal_answer_required": _bool_value(qwen_payload.get("is_legal_answer_required", False)),
            "is_standalone_question": _bool_value(qwen_payload.get("is_standalone_question", False)),
            "exclusion_reason": str(qwen_payload.get("exclusion_reason", "")),
            "confidence": str(qwen_payload.get("confidence", "")),
            "quality_flags": _as_string_list(qwen_payload.get("quality_flags", [])),
            "question_date": str(qwen_payload.get("question_date", source_task.get("input", {}).get("question_date", ""))),
        },
        "verifier_votes": [
            _adjudication_verifier_vote_entry("primary", "reviewer_1", verifier_payload)
        ]
        if verifier_payload
        else [],
        "human_triage": {
            "decision": str(decision.get("decision", "")),
            "decision_reason": str(decision.get("decision_reason", "")),
            "reviewer_hash": str(decision.get("reviewer_hash", "")),
        },
    }
    return record


def _selected_adjudication_candidate_key(
    adjudication_result: Mapping[str, Any],
    adjudication_item: Mapping[str, Any],
) -> str:
    selected = str(adjudication_result.get("selected_candidate_key", "")).strip()
    if selected:
        return selected
    candidates = adjudication_item.get("candidates", [])
    if isinstance(candidates, Sequence) and not isinstance(candidates, (str, bytes)) and len(candidates) == 1:
        only_candidate = candidates[0]
        if isinstance(only_candidate, Mapping):
            return str(only_candidate.get("candidate_key", "")).strip()
    return ""


def _adjudication_results_key(result_path: str | Path, index: int) -> str:
    raw = str(result_path)
    if "=" in raw and not Path(raw).exists():
        key, _path = raw.split("=", 1)
        key = key.strip()
        if key:
            return key
    path = Path(raw.split("=", 1)[1] if "=" in raw and not Path(raw).exists() else raw)
    stem = path.name
    for suffix in ("_adjudication_results.jsonl", "_results.jsonl", ".jsonl"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem or f"judge_{index}"


def _adjudication_results_path(result_path: str | Path) -> Path:
    raw = str(result_path)
    if "=" in raw and not Path(raw).exists():
        _key, path = raw.split("=", 1)
        return Path(path.strip())
    return Path(result_path)


def _adjudication_result_retry_entry(result_key: str, result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "result_key": result_key,
        "task_id": str(result.get("task_id", "")),
        "candidate_id": str(result.get("candidate_id", "")),
        "status": str(result.get("status", "")),
        "model_id": str(result.get("model_id", "")),
        "adjudication_run_id": str(result.get("adjudication_run_id", "")),
        "adjudication_batch_id": str(result.get("adjudication_batch_id", "")),
        "adjudication_batch_hash": str(result.get("adjudication_batch_hash", "")),
        "adjudication_input_hash": str(result.get("adjudication_input_hash", "")),
        "adjudication_prompt_version": str(result.get("adjudication_prompt_version", "")),
        "adjudication_prompt_profile_hash": str(result.get("adjudication_prompt_profile_hash", "")),
        "runtime_profile_hash": str(result.get("runtime_profile_hash", "")),
        "verdict": str(result.get("verdict", "")),
        "confidence": result.get("confidence", ""),
        "risk": str(result.get("risk", "")),
        "bad_fields": _as_string_list(result.get("bad_fields", [])),
        "short_reason": str(result.get("short_reason", "")),
        "failure_reason": str(result.get("failure_reason", "")),
        "final_recommendation": str(result.get("final_recommendation", "")),
        "selected_candidate_key": str(result.get("selected_candidate_key", "")),
    }


def _retry_reason_signature(result: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(_as_string_list(result.get("bad_fields", [])))) or ("no_bad_fields",)


def _is_manual_adjudication_result(result: Mapping[str, Any]) -> bool:
    return (
        str(result.get("model_id", "")) == "human-reviewer"
        or str(result.get("adjudication_run_id", "")) == "manual-adjudication-review"
        or str(result.get("result_key", "")) == "manual"
    )


def _retry_consensus_triage(
    *,
    adjudication_results: Sequence[Mapping[str, Any]],
    adjudication_item: Mapping[str, Any],
    selected_candidate_key: str,
) -> dict[str, Any]:
    if adjudication_results and all(_is_manual_adjudication_result(result) for result in adjudication_results):
        return {
            "route": "auto_retry",
            "reason_code": "manual_review_retry",
            "bad_fields": sorted(
                {
                    field
                    for result in adjudication_results
                    for field in _as_string_list(result.get("bad_fields", []))
                }
            ),
        }

    bad_fields = sorted(
        {
            field
            for result in adjudication_results
            for field in _as_string_list(result.get("bad_fields", []))
        }
    )
    signatures = {_retry_reason_signature(result) for result in adjudication_results}
    blocking_fields = [field for field in bad_fields if field in AUTO_RETRY_BLOCKING_BAD_FIELDS]
    verifier_bad_fields = sorted(
        {
            field
            for vote in adjudication_item.get("verifier_votes", [])
            if isinstance(vote, Mapping) and str(vote.get("candidate_key", "")) == selected_candidate_key
            for field in _as_string_list(vote.get("bad_fields", []))
        }
    )
    verifier_blocking_fields = [
        field for field in verifier_bad_fields if field in AUTO_RETRY_BLOCKING_BAD_FIELDS
    ]
    if len(signatures) > 1 or blocking_fields or verifier_blocking_fields:
        return {
            "route": "human_review",
            "reason_code": "material_retry_disagreement_requires_human_review",
            "bad_fields": bad_fields,
            "reason_signatures": [list(signature) for signature in sorted(signatures)],
            "blocking_bad_fields": blocking_fields,
            "verifier_blocking_bad_fields": verifier_blocking_fields,
        }

    return {
        "route": "auto_retry",
        "reason_code": "retry_consensus_low_risk",
        "bad_fields": bad_fields,
    }


def _adjudication_candidate_by_key(
    adjudication_item: Mapping[str, Any],
    candidate_key: str,
) -> dict[str, Any]:
    candidates = adjudication_item.get("candidates", [])
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        return {}
    for candidate in candidates:
        if isinstance(candidate, Mapping) and str(candidate.get("candidate_key", "")) == candidate_key:
            return dict(candidate)
    return {}


def _retry_generator_batch_item(
    *,
    source_task: Mapping[str, Any],
    adjudication_item: Mapping[str, Any],
    selected_candidate: Mapping[str, Any],
    adjudication_result: Mapping[str, Any],
    adjudication_results: Sequence[Mapping[str, Any]] | None = None,
    retry_triage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selected_candidate_key = str(selected_candidate.get("candidate_key", ""))
    verifier_votes = [
        dict(vote)
        for vote in adjudication_item.get("verifier_votes", [])
        if isinstance(vote, Mapping) and str(vote.get("candidate_key", "")) == selected_candidate_key
    ]
    record = dict(source_task)
    record["canonicalization_source_identity"] = _canonicalization_root_identity(source_task)
    record["retry_context"] = {
        "previous_candidate": dict(selected_candidate),
        "verifier_votes": verifier_votes,
        "adjudication": {
            "adjudication_run_id": str(adjudication_result.get("adjudication_run_id", "")),
            "model_id": str(adjudication_result.get("model_id", "")),
            "verdict": str(adjudication_result.get("verdict", "")),
            "confidence": adjudication_result.get("confidence", ""),
            "risk": str(adjudication_result.get("risk", "")),
            "bad_fields": _as_string_list(adjudication_result.get("bad_fields", [])),
            "short_reason": str(adjudication_result.get("short_reason", "")),
            "final_recommendation": str(adjudication_result.get("final_recommendation", "")),
            "selected_candidate_key": str(adjudication_result.get("selected_candidate_key", "")),
        },
        "adjudication_results": [
            dict(result) for result in (adjudication_results or []) if isinstance(result, Mapping)
        ],
        "retry_triage": dict(retry_triage or {}),
        "human_triage": dict(adjudication_item.get("human_triage", {}))
        if isinstance(adjudication_item.get("human_triage"), Mapping)
        else {},
    }
    return record


def _records_by_task_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_task: dict[str, dict[str, Any]] = {}
    for record in records:
        task_id = str(record.get("task_id", record.get("custom_id", "")))
        if task_id:
            by_task[task_id] = record
    return by_task


def _records_grouped_by_task_id(
    records: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], int]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    missing_task_id_count = 0
    for raw_record in records:
        payload = _extract_result_payload(raw_record)
        task_id = str(payload.get("task_id", payload.get("custom_id", "")))
        if not task_id:
            missing_task_id_count += 1
            continue
        grouped[task_id].append(dict(raw_record))
    return dict(grouped), missing_task_id_count


def _review_card_record(
    batch_item: Mapping[str, Any],
    *,
    qwen_result: Mapping[str, Any] | None,
    verifier_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source_input = batch_item.get("input", {}) if isinstance(batch_item.get("input"), Mapping) else {}
    qwen_payload = _extract_result_payload(qwen_result or {}) if qwen_result else {}
    verifier_payload = _extract_result_payload(verifier_result or {}) if verifier_result else {}
    verifier_view = _verifier_payload_for_review(verifier_payload)
    retry_context = batch_item.get("retry_context", {})
    if not isinstance(retry_context, Mapping):
        retry_context = {}
    previous_candidate = retry_context.get("previous_candidate", {})
    if not isinstance(previous_candidate, Mapping):
        previous_candidate = {}
    adjudication = retry_context.get("adjudication", {})
    if not isinstance(adjudication, Mapping):
        adjudication = {}
    retry_triage = retry_context.get("retry_triage", {})
    if not isinstance(retry_triage, Mapping):
        retry_triage = {}
    human_triage = retry_context.get("human_triage", {})
    if not isinstance(human_triage, Mapping):
        human_triage = {}
    retry_decision_reason = str(
        human_triage.get("decision_reason", "") or adjudication.get("short_reason", "")
    )
    record = {
        "review_payload_version": CANONICALIZATION_REVIEW_PAYLOAD_VERSION,
        "task_id": str(batch_item.get("task_id", "")),
        "candidate_id": str(batch_item.get("candidate_id", "")),
        "input": {
            "question_date": str(source_input.get("question_date", "")),
            "question_text_redacted": str(source_input.get("question_text_redacted", "")),
            "topic_labels": _as_string_list(source_input.get("topic_labels", [])),
            "law_code_candidates": _as_string_list(source_input.get("law_code_candidates", [])),
            "answer_candidate_status": str(source_input.get("answer_candidate_status", "")),
            "quality_flags": _as_string_list(source_input.get("quality_flags", [])),
        },
        "qwen": {
            "status": str(qwen_payload.get("status", "")),
            "failure_reason": str(qwen_payload.get("failure_reason", "")),
            "canonical_question": str(qwen_payload.get("canonical_question", "")),
            "canonical_question_language": str(qwen_payload.get("canonical_question_language", "")),
            "legal_issue_frame": str(qwen_payload.get("legal_issue_frame", "")),
            "legal_issue_frame_slug": str(qwen_payload.get("legal_issue_frame_slug", "")),
            "law_area": str(qwen_payload.get("law_area", "")),
            "facts": _as_string_list(qwen_payload.get("facts", [])),
            "desired_outcome": str(qwen_payload.get("desired_outcome", "")),
            "authority_context": _as_string_list(qwen_payload.get("authority_context", [])),
            "hidden_issues": _as_string_list(qwen_payload.get("hidden_issues", [])),
            "is_legal_answer_required": _bool_value(qwen_payload.get("is_legal_answer_required", False)),
            "is_standalone_question": _bool_value(qwen_payload.get("is_standalone_question", False)),
            "exclusion_reason": str(qwen_payload.get("exclusion_reason", "")),
            "confidence": str(qwen_payload.get("confidence", "")),
            "quality_flags": _as_string_list(qwen_payload.get("quality_flags", [])),
        },
        "verifier": {
            "verdict": str(verifier_view.get("verdict", "")),
            "confidence": verifier_view.get("confidence", ""),
            "risk": str(verifier_view.get("risk", "")),
            "bad_fields": _as_string_list(verifier_view.get("bad_fields", [])),
            "short_reason": str(verifier_view.get("short_reason", "")),
            "suggested_action": str(verifier_view.get("suggested_action", "")),
        },
        "retry_context": {
            "previous_canonical_question": str(previous_candidate.get("canonical_question", "")),
            "previous_legal_issue_frame": str(previous_candidate.get("legal_issue_frame", "")),
            "previous_law_area": str(previous_candidate.get("law_area", "")),
            "previous_quality_flags": _as_string_list(previous_candidate.get("quality_flags", [])),
            "adjudication_reason": str(adjudication.get("short_reason", "")),
            "adjudication_recommendation": str(adjudication.get("final_recommendation", "")),
            "retry_triage_reason": str(retry_triage.get("reason_code", "")),
            "human_decision": str(human_triage.get("decision", "")),
            "human_decision_reason": str(human_triage.get("decision_reason", "")),
            "retry_decision_reason": retry_decision_reason,
        },
        "review_binding": {
            "qwen_canonicalization_evidence_hash": str(
                qwen_payload.get("canonicalization_evidence_hash", "")
            ),
            "verifier_payload_hash": (
                _stable_json_hash(verifier_payload) if verifier_payload else ""
            ),
        },
    }
    record["review_payload_hash"] = _stable_json_hash(record)
    return record


def _review_cards_html(
    cards: list[dict[str, Any]],
    *,
    download_name: str = "tg_007_review_decisions.jsonl",
    storage_key: str = "tg007ReviewDecisions",
) -> str:
    data = json.dumps(cards, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>007 Canonicalization Review</title>
  <style>
    :root {{
      --bg: #f6f7f4;
      --text: #1b1f23;
      --muted: #687076;
      --line: #d6d9d2;
      --panel: #ffffff;
      --accent: #0f766e;
      --warn: #a16207;
      --bad: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: ui-sans-serif, system-ui, sans-serif; background: var(--bg); color: var(--text); }}
    header {{ position: sticky; top: 0; z-index: 2; padding: 12px 18px; border-bottom: 1px solid var(--line); background: #eef1ea; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
    header strong {{ font-size: 15px; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 18px; display: grid; gap: 14px; }}
    button, select, input, textarea {{ font: inherit; }}
    button {{ border: 1px solid var(--line); background: var(--panel); padding: 7px 10px; border-radius: 6px; cursor: pointer; }}
    button.primary {{ background: var(--accent); border-color: var(--accent); color: white; }}
    input, select, textarea {{ border: 1px solid var(--line); border-radius: 6px; background: white; padding: 7px 8px; }}
    textarea {{ min-height: 72px; resize: vertical; width: 100%; }}
    .toolbar {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
    .card {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 14px; display: grid; gap: 12px; }}
    .card h2 {{ font-size: 15px; margin: 0; }}
    .meta {{ color: var(--muted); font-size: 12px; display: flex; gap: 10px; flex-wrap: wrap; }}
    .grid {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; }}
    .section {{ border-top: 1px solid var(--line); padding-top: 10px; }}
    .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0; }}
    .value {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 5px; }}
    .chip {{ border: 1px solid var(--line); border-radius: 999px; padding: 2px 7px; font-size: 12px; background: #f9faf7; }}
    .warn {{ color: var(--warn); }}
    .bad {{ color: var(--bad); }}
    .decision {{ display: grid; grid-template-columns: 160px 180px minmax(0, 1fr); gap: 8px; align-items: start; }}
    .manual-json {{ display: grid; gap: 8px; }}
    .manual-json textarea {{ min-height: 220px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; }}
    @media (max-width: 820px) {{
      .grid, .decision {{ grid-template-columns: 1fr; }}
      main {{ padding: 12px; }}
    }}
  </style>
</head>
<body>
<header>
  <strong>007 canonicalization review</strong>
  <span id="counter" class="meta"></span>
  <div class="toolbar">
    <button id="prev">Prev</button>
    <button id="next">Next</button>
    <select id="filter">
      <option value="all">all</option>
      <option value="undecided">undecided</option>
      <option value="fail">verifier fail</option>
      <option value="uncertain">verifier uncertain</option>
    </select>
    <button id="export" class="primary">Export JSONL</button>
  </div>
</header>
<main id="app"></main>
<script id="cards-data" type="application/json">{data}</script>
<script>
const cards = JSON.parse(document.getElementById('cards-data').textContent);
const storageKey = {json.dumps(storage_key, ensure_ascii=False)};
const decisions = new Map(JSON.parse(localStorage.getItem(storageKey) || '[]'));
let index = 0;
let filter = 'all';

function text(value) {{
  if (Array.isArray(value)) return value.join(', ');
  if (value === null || value === undefined) return '';
  return String(value);
}}

function unique(values) {{
  return Array.from(new Set((values || []).filter(value => value !== null && value !== undefined && String(value).trim())));
}}

function manualTemplate(card) {{
  const payload = {{
    canonical_question: card.qwen.canonical_question || card.input.question_text_redacted || '',
    canonical_question_language: card.qwen.canonical_question_language || 'ru',
    legal_issue_frame: card.qwen.legal_issue_frame || '',
    legal_issue_frame_slug: card.qwen.legal_issue_frame_slug || '',
    law_area: card.qwen.law_area || '',
    facts: card.qwen.facts || [],
    desired_outcome: card.qwen.desired_outcome || '',
    authority_context: card.qwen.authority_context || [],
    hidden_issues: card.qwen.hidden_issues || [],
    is_legal_answer_required: true,
    is_standalone_question: true,
    exclusion_reason: 'none',
    confidence: card.qwen.confidence || 'high',
    quality_flags: unique([...(card.qwen.quality_flags || []), 'manual_canonicalization_override'])
  }};
  return JSON.stringify(payload, null, 2);
}}

function currentCards() {{
  return cards.filter(card => {{
    const decision = decisions.get(card.task_id);
    if (filter === 'undecided') return !decision || !decision.decision;
    if (filter === 'fail') return card.verifier.verdict === 'fail';
    if (filter === 'uncertain') return card.verifier.verdict === 'uncertain';
    return true;
  }});
}}

function field(label, value) {{
  const wrap = document.createElement('div');
  const l = document.createElement('div');
  l.className = 'label';
  l.textContent = label;
  const v = document.createElement('div');
  v.className = 'value';
  v.textContent = text(value);
  wrap.append(l, v);
  return wrap;
}}

function render() {{
  const visible = currentCards();
  if (index >= visible.length) index = Math.max(0, visible.length - 1);
  const card = visible[index];
  document.getElementById('counter').textContent = `${{visible.length ? index + 1 : 0}} / ${{visible.length}} visible, ${{cards.length}} total`;
  const app = document.getElementById('app');
  app.textContent = '';
  if (!card) {{
    app.append(field('status', 'No cards for current filter'));
    return;
  }}
  const saved = decisions.get(card.task_id) || {{}};
  const root = document.createElement('section');
  root.className = 'card';
  const title = document.createElement('h2');
  title.textContent = card.task_id;
  const meta = document.createElement('div');
  meta.className = 'meta';
  meta.textContent = `${{card.candidate_id}} | date=${{card.input.question_date || 'unknown'}} | status=${{card.input.answer_candidate_status}} | topics=${{text(card.input.topic_labels)}}`;
  root.append(title, meta);

  const grid = document.createElement('div');
  grid.className = 'grid';
  const left = document.createElement('div');
  left.append(field('source question', card.input.question_text_redacted), field('law candidates', card.input.law_code_candidates), field('quality flags', card.input.quality_flags));
  const right = document.createElement('div');
  right.append(
    field('qwen status', `${{card.qwen.status}} ${{card.qwen.failure_reason || ''}}`),
    field('qwen canonical question', card.qwen.canonical_question),
    field('legal issue frame', card.qwen.legal_issue_frame),
    field('slug', card.qwen.legal_issue_frame_slug),
    field('law area', card.qwen.law_area)
  );
  grid.append(left, right);
  root.append(grid);

  const details = document.createElement('div');
  details.className = 'grid section';
  details.append(
    field('facts', card.qwen.facts),
    field('desired outcome', card.qwen.desired_outcome),
    field('authority context', card.qwen.authority_context),
    field('hidden issues', card.qwen.hidden_issues),
    field('legal/standalone', `${{card.qwen.is_legal_answer_required}} / ${{card.qwen.is_standalone_question}}`),
    field('exclusion/confidence', `${{card.qwen.exclusion_reason}} / ${{card.qwen.confidence}}`),
    field('retry previous question', card.retry_context.previous_canonical_question),
    field('retry previous law/flags', `${{card.retry_context.previous_law_area || ''}} / ${{text(card.retry_context.previous_quality_flags)}}`),
    field('retry decision reason', card.retry_context.retry_decision_reason),
    field('adjudication retry reason', card.retry_context.adjudication_reason),
    field('retry triage', `${{card.retry_context.adjudication_recommendation || ''}} / ${{card.retry_context.retry_triage_reason || ''}}`),
    field('verifier', `${{card.verifier.verdict}} confidence=${{card.verifier.confidence}} risk=${{card.verifier.risk}}`),
    field('bad fields', card.verifier.bad_fields),
    field('verifier reason', card.verifier.short_reason)
  );
  root.append(details);

  const decision = document.createElement('div');
  decision.className = 'decision section';
  const select = document.createElement('select');
  for (const value of ['', 'accept', 'reject', 'retry_qwen', 'send_deepseek', 'hold']) {{
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value || 'decision';
    if ((saved.decision || '') === value) option.selected = true;
    select.append(option);
  }}
  const reason = document.createElement('textarea');
  reason.placeholder = 'decision_reason';
  reason.value = saved.decision_reason || '';
  const manualWrap = document.createElement('div');
  manualWrap.className = 'manual-json section';
  const manualLabel = document.createElement('div');
  manualLabel.className = 'label';
  manualLabel.textContent = 'manual canonicalization JSON';
  const manualToolbar = document.createElement('div');
  manualToolbar.className = 'toolbar';
  const useTemplate = document.createElement('button');
  useTemplate.type = 'button';
  useTemplate.textContent = 'Use Template';
  const clearManual = document.createElement('button');
  clearManual.type = 'button';
  clearManual.textContent = 'Clear';
  manualToolbar.append(useTemplate, clearManual);
  const manual = document.createElement('textarea');
  manual.placeholder = manualTemplate(card);
  manual.value = saved.manual_canonicalization_text || (saved.manual_canonicalization ? JSON.stringify(saved.manual_canonicalization, null, 2) : '');
  const persist = () => {{
    decisions.set(card.task_id, {{
      task_id: card.task_id,
      candidate_id: card.candidate_id,
      decision: select.value,
      decision_reason: reason.value,
      review_payload_version: card.review_payload_version,
      review_payload_hash: card.review_payload_hash,
      manual_canonicalization_text: manual.value,
      reviewed_at: new Date().toISOString()
    }});
    localStorage.setItem(storageKey, JSON.stringify(Array.from(decisions.entries())));
  }};
  select.addEventListener('change', persist);
  reason.addEventListener('input', persist);
  manual.addEventListener('input', persist);
  useTemplate.addEventListener('click', () => {{
    manual.value = manualTemplate(card);
    persist();
  }});
  clearManual.addEventListener('click', () => {{
    manual.value = '';
    persist();
  }});
  decision.append(select, reason);
  root.append(decision);
  manualWrap.append(manualLabel, manualToolbar, manual);
  root.append(manualWrap);
  app.append(root);
}}

document.getElementById('prev').onclick = () => {{ index = Math.max(0, index - 1); render(); }};
document.getElementById('next').onclick = () => {{ index = Math.min(currentCards().length - 1, index + 1); render(); }};
document.getElementById('filter').onchange = event => {{ filter = event.target.value; index = 0; render(); }};
document.getElementById('export').onclick = () => {{
  const exported = [];
  for (const item of Array.from(decisions.values()).filter(item => item.decision)) {{
    const copy = {{...item}};
    const manualText = (copy.manual_canonicalization_text || '').trim();
    delete copy.manual_canonicalization_text;
    if (manualText) {{
      try {{
        const parsed = JSON.parse(manualText);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {{
          throw new Error('manual canonicalization must be a JSON object');
        }}
        copy.manual_canonicalization = parsed;
      }} catch (error) {{
        alert(`Invalid manual canonicalization JSON for ${{copy.task_id}}: ${{error.message}}`);
        return;
      }}
    }}
    exported.push(copy);
  }}
  const lines = exported.map(item => JSON.stringify(item));
  const blob = new Blob([lines.join('\\n') + (lines.length ? '\\n' : '')], {{type: 'application/x-ndjson'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = {json.dumps(download_name, ensure_ascii=False)};
  a.click();
  URL.revokeObjectURL(url);
}};
render();
</script>
</body>
</html>
"""


def _included_canonical_evidence(evidence: Mapping[str, Any]) -> bool:
    return str(evidence.get("status", "")) == "completed" and str(evidence.get("exclusion_reason", "")) == "none"


def _embedding_profile_from_metadata(metadata: Mapping[str, Any] | EmbeddingProfile | None) -> EmbeddingProfile:
    if isinstance(metadata, EmbeddingProfile):
        return metadata.validate()
    source = dict(metadata or {})
    return EmbeddingProfile(
        embedding_profile_id=str(source.get("embedding_profile_id", "jina_v5_q8_1024_norm_v1")),
        provider=str(source.get("provider", "jina")),
        model_id=str(source.get("model_id", source.get("model", "jina-embeddings-v5-text-small-retrieval-GGUF"))),
        variant=str(source.get("variant", "Q8")),
        dimensions=int(source.get("dimensions", source.get("vector_dimensions", 1024))),
        normalized=_bool_value(source.get("normalized", True)),
        query_prefix=str(source.get("query_prefix", QUERY_PREFIX)),
        document_prefix=str(source.get("document_prefix", DOCUMENT_PREFIX)),
        routing_mode=str(source.get("routing_mode", "local_only")),
    ).validate()


def _extract_vector(raw: Mapping[str, Any]) -> list[float]:
    value = raw.get("vector", raw.get("embedding"))
    if value is None and isinstance(raw.get("data"), list) and raw["data"]:
        first = raw["data"][0]
        if isinstance(first, Mapping):
            value = first.get("embedding")
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("vector is missing or not a sequence")
    return [float(item) for item in value]


def _write_jsonl(path: str | Path, records: Iterable[Mapping[str, Any]]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return output


def _write_json(path: str | Path, record: Mapping[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _open_jsonl_stream(path: str | Path, *, append: bool = False):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    return output.open("a" if append else "w", encoding="utf-8")


def _write_jsonl_stream_record(handle: Any, record: Mapping[str, Any]) -> None:
    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    handle.flush()


def _write_text(path: str | Path, text: str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def _json_for_prompt(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _review_payload_for_prompt(payload: Mapping[str, Any]) -> str:
    """Place candidate field scope after all source text and review reasons."""

    field_scope = payload.get("field_scope_review", {})
    if not isinstance(field_scope, Mapping) or not field_scope:
        return _json_for_prompt(payload)
    return (
        f"{_json_for_prompt(payload)}\n\n"
        "FINAL FIELD-SCOPE REVIEW: use this block to verify what text is actually inside candidate fields.\n"
        f"{json.dumps(field_scope, ensure_ascii=False, indent=2, sort_keys=False)}"
    )


def _raw_message_text_blocks(raw_message: Any) -> list[str]:
    content = getattr(raw_message, "content", None)
    if isinstance(content, str):
        return [content]
    if not isinstance(content, Sequence) or isinstance(content, (str, bytes)):
        return []
    blocks: list[str] = []
    for block in content:
        if isinstance(block, str):
            blocks.append(block)
            continue
        if not isinstance(block, Mapping):
            continue
        if block.get("type") != "text":
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            blocks.append(text)
    return blocks


def _extract_json_object_from_text(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()
    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, Mapping):
            return dict(value)
    return None


def _structured_output_payload_from_raw_message(raw_message: Any) -> dict[str, Any] | None:
    for text in _raw_message_text_blocks(raw_message):
        payload = _extract_json_object_from_text(text)
        if payload is not None:
            return payload
    return None


def _structured_output_payload(raw_result: Any) -> dict[str, Any]:
    if isinstance(raw_result, Mapping) and "parsed" in raw_result:
        parsing_error = raw_result.get("parsing_error")
        if parsing_error:
            raise ValueError(f"structured_output_parsing_error:{_sanitize_operator_error_text(str(parsing_error))}")
        parsed = raw_result.get("parsed")
        if parsed is None:
            fallback_payload = _structured_output_payload_from_raw_message(raw_result.get("raw"))
            if fallback_payload is not None:
                return fallback_payload
            raise ValueError("structured_output_missing_parsed_payload")
        if isinstance(parsed, BaseModel):
            return parsed.model_dump()
        if isinstance(parsed, Mapping):
            return dict(parsed)
        raise ValueError(f"structured_output_unsupported_parsed_type:{type(parsed).__name__}")
    if isinstance(raw_result, BaseModel):
        return raw_result.model_dump()
    if isinstance(raw_result, Mapping):
        return dict(raw_result)
    raise ValueError(f"structured_output_unsupported_type:{type(raw_result).__name__}")


def _langchain_raw_message(raw_result: Any) -> Any:
    if isinstance(raw_result, Mapping):
        return raw_result.get("raw")
    return raw_result


def _safe_int_value(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value))
    except ValueError:
        return None


def _first_int_value(*values: Any) -> int | None:
    for value in values:
        parsed = _safe_int_value(value)
        if parsed is not None:
            return parsed
    return None


def _llm_usage_metadata_from_structured_output(raw_result: Any) -> dict[str, Any]:
    raw_message = _langchain_raw_message(raw_result)
    if raw_message is None:
        return {}
    usage_metadata = getattr(raw_message, "usage_metadata", None)
    response_metadata = getattr(raw_message, "response_metadata", None)
    usage = usage_metadata if isinstance(usage_metadata, Mapping) else {}
    response = response_metadata if isinstance(response_metadata, Mapping) else {}
    token_usage = response.get("token_usage", {})
    if not isinstance(token_usage, Mapping):
        token_usage = response.get("usage", {})
    if not isinstance(token_usage, Mapping):
        token_usage = {}
    completion_details = token_usage.get("completion_tokens_details", {})
    if not isinstance(completion_details, Mapping):
        completion_details = {}
    output_details = usage.get("output_token_details", {})
    if not isinstance(output_details, Mapping):
        output_details = {}

    normalized: dict[str, Any] = {}
    input_tokens = _first_int_value(usage.get("input_tokens"), token_usage.get("prompt_tokens"))
    output_tokens = _first_int_value(usage.get("output_tokens"), token_usage.get("completion_tokens"))
    total_tokens = _first_int_value(usage.get("total_tokens"), token_usage.get("total_tokens"))
    reasoning_tokens = _first_int_value(
        output_details.get("reasoning"),
        output_details.get("reasoning_tokens"),
        completion_details.get("reasoning_tokens"),
    )
    if input_tokens is not None:
        normalized["input_tokens"] = input_tokens
    if output_tokens is not None:
        normalized["output_tokens"] = output_tokens
    if total_tokens is not None:
        normalized["total_tokens"] = total_tokens
    if reasoning_tokens is not None:
        normalized["reasoning_tokens"] = reasoning_tokens
    if normalized:
        sources: list[str] = []
        if usage:
            sources.append("langchain_usage_metadata")
        if token_usage:
            sources.append("response_metadata_token_usage")
        normalized["usage_source"] = "+".join(sources) if sources else "unknown"
    return normalized


def _operator_runtime_profile(
    *,
    stage: str,
    prompt_version: str,
    prompt_profile_hash: str,
    provider: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
    structured_output_method: str,
    max_tokens: int,
    timeout_seconds: int,
    extra_body: Mapping[str, Any] | None,
    input_batch_hash: str,
) -> dict[str, Any]:
    """Build a secret-free profile that must match before a run can resume."""

    return {
        "stage": stage,
        "prompt_version": prompt_version,
        "prompt_profile_hash": prompt_profile_hash,
        "provider": provider,
        "runtime_contour": runtime_contour,
        "backend": backend,
        "model_id": model_id,
        "structured_output_method": structured_output_method,
        "max_tokens": max_tokens,
        "timeout_seconds": timeout_seconds,
        "extra_body_hash": _stable_json_hash(dict(extra_body or {})),
        "input_batch_hash": input_batch_hash,
    }


def _operator_input_batch_hash(
    input_items: Sequence[Mapping[str, Any]],
    *,
    identity_field: str,
) -> str:
    identities: list[dict[str, str]] = []
    for item in input_items:
        task_id = str(item.get("task_id", ""))
        identity = str(item.get(identity_field, ""))
        if not task_id or not identity:
            raise ValueError(f"operator input missing {identity_field} or task_id")
        identities.append({"task_id": task_id, identity_field: identity})
    return _stable_json_hash(sorted(identities, key=lambda item: item["task_id"]))


def _attach_operator_record_identity(
    record: dict[str, Any],
    *,
    stage: str,
    input_item: Mapping[str, Any],
    runtime_profile: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach authoritative task and runtime identity after model output is parsed."""

    profile = dict(runtime_profile)
    record["operator_stage"] = stage
    record["runtime_profile"] = profile
    record["runtime_profile_hash"] = _stable_json_hash(profile)

    if stage == "canonicalization":
        for field_name in (
            "canonicalization_batch_id",
            "canonicalization_batch_hash",
            "task_input_hash",
            "prompt_profile_hash",
        ):
            record[field_name] = str(input_item.get(field_name, ""))
        record["canonicalization_identity_policy_version"] = CANONICALIZATION_IDENTITY_POLICY_VERSION
        source_identity = input_item.get("canonicalization_source_identity", {})
        if isinstance(source_identity, Mapping) and source_identity:
            record["canonicalization_source_identity"] = dict(source_identity)
        record["canonicalization_evidence_hash"] = _canonicalization_evidence_hash(record)
        return record

    if stage == "verifier":
        for field_name in (
            "canonicalization_batch_id",
            "canonicalization_batch_hash",
            "task_input_hash",
            "prompt_version",
            "prompt_profile_hash",
            "canonicalization_contract_version",
            "canonicalization_evidence_id",
        ):
            record[field_name] = str(input_item.get(field_name, ""))
        evidence_hash = str(input_item.get("canonicalization_evidence_hash", "")) or _canonicalization_evidence_hash(input_item)
        record["canonicalization_evidence_hash"] = evidence_hash
        record["verifier_prompt_version"] = str(profile.get("prompt_version", ""))
        record["verifier_prompt_profile_hash"] = str(profile.get("prompt_profile_hash", ""))
        record["verifier_input_hash"] = _stable_json_hash(
            {
                "canonicalization_evidence_hash": evidence_hash,
                "verifier_prompt_profile_hash": record["verifier_prompt_profile_hash"],
            }
        )
        return record

    if stage == "atomic_verify_repair":
        for field_name in (
            "canonicalization_batch_id",
            "canonicalization_batch_hash",
            "task_input_hash",
            "prompt_version",
            "prompt_profile_hash",
            "canonicalization_contract_version",
            "canonicalization_evidence_id",
        ):
            record[field_name] = str(input_item.get(field_name, ""))
        evidence_hash = str(input_item.get("canonicalization_evidence_hash", "")) or _canonicalization_evidence_hash(
            input_item
        )
        record["canonicalization_evidence_hash"] = evidence_hash
        record["atomic_input_hash"] = _stable_json_hash(
            {
                "canonicalization_evidence_hash": evidence_hash,
                "atomic_runtime_profile_hash": record["runtime_profile_hash"],
            }
        )
        return record

    if stage == "adjudication":
        record["adjudication_batch_id"] = str(input_item.get("adjudication_batch_id", ""))
        record["adjudication_batch_hash"] = str(input_item.get("adjudication_batch_hash", ""))
        record["adjudication_input_hash"] = str(input_item.get("adjudication_input_hash", ""))
        record["adjudication_prompt_version"] = str(profile.get("prompt_version", ""))
        record["adjudication_prompt_profile_hash"] = str(profile.get("prompt_profile_hash", ""))
        record["canonicalization_batch_id"] = str(input_item.get("canonicalization_batch_id", ""))
        record["canonicalization_batch_hash"] = str(input_item.get("canonicalization_batch_hash", ""))
        return record

    raise ValueError(f"unsupported operator stage: {stage}")


def _operator_checkpoint_payload(
    *,
    stage: str,
    input_path: str | Path,
    output_path: str | Path,
    runtime_profile: Mapping[str, Any],
    processed_task_ids: Iterable[str],
    status_counts: Mapping[str, int],
) -> dict[str, Any]:
    return {
        "artifact_type": "tg_qa_canonicalization_operator_checkpoint",
        "generated_at": _utc_timestamp(),
        "stage": stage,
        "input_path": str(input_path),
        "output_path": str(output_path),
        "runtime_profile": dict(runtime_profile),
        "runtime_profile_hash": _stable_json_hash(dict(runtime_profile)),
        "processed_task_ids": sorted({str(task_id) for task_id in processed_task_ids if task_id}),
        "status_counts": dict(sorted((str(key), int(value)) for key, value in status_counts.items())),
    }


def _operator_artifact_path(summary_output_path: str | Path, suffix: str) -> Path:
    summary_path = Path(summary_output_path)
    return summary_path.with_name(f"{summary_path.stem}_{suffix}.json")


def _write_operator_checkpoint(
    *,
    checkpoint_output_path: str | Path,
    stage: str,
    input_path: str | Path,
    output_path: str | Path,
    runtime_profile: Mapping[str, Any],
    processed_task_ids: Iterable[str],
    status_counts: Mapping[str, int],
) -> dict[str, Any]:
    checkpoint = _operator_checkpoint_payload(
        stage=stage,
        input_path=input_path,
        output_path=output_path,
        runtime_profile=runtime_profile,
        processed_task_ids=processed_task_ids,
        status_counts=status_counts,
    )
    _write_json(checkpoint_output_path, checkpoint)
    return checkpoint


def _write_operator_run_bundle(
    *,
    bundle_output_path: str | Path,
    checkpoint_output_path: str | Path,
    summary_output_path: str | Path,
    result_output_path: str | Path,
    stage: str,
    runtime_profile: Mapping[str, Any],
    command_metadata: Mapping[str, Any],
    log_path: str,
) -> dict[str, Any]:
    bundle = {
        "artifact_type": "tg_qa_canonicalization_operator_run_bundle",
        "generated_at": _utc_timestamp(),
        "stage": stage,
        "result_output_path": str(result_output_path),
        "summary_output_path": str(summary_output_path),
        "checkpoint_output_path": str(checkpoint_output_path),
        "log_path": log_path,
        "runtime_profile": dict(runtime_profile),
        "runtime_profile_hash": _stable_json_hash(dict(runtime_profile)),
        "command_metadata": dict(command_metadata),
        "trust_boundary": "operator_run_artifacts_are_private_review_evidence_only",
    }
    _write_json(bundle_output_path, bundle)
    return bundle


def _operator_record_runtime_metadata(
    raw_result: Any,
    *,
    request_duration_seconds: float,
    attempts_used: int,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "request_duration_seconds": round(max(request_duration_seconds, 0.0), 3),
        "attempts_used": attempts_used,
    }
    usage = _llm_usage_metadata_from_structured_output(raw_result)
    if usage:
        metadata.update(usage)
        metadata["llm_usage_available"] = True
    else:
        metadata["llm_usage_available"] = False
    return metadata


def _attach_runtime_metadata(record: dict[str, Any], metadata: Mapping[str, Any]) -> dict[str, Any]:
    existing = record.get("runtime_metadata", {})
    merged = dict(existing) if isinstance(existing, Mapping) else {}
    merged.update(dict(metadata))
    record["runtime_metadata"] = merged
    return record


def _operator_runtime_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    metadata_items = [
        item.get("runtime_metadata", {})
        for item in records
        if isinstance(item.get("runtime_metadata", {}), Mapping)
    ]
    durations = [
        float(metadata.get("request_duration_seconds", 0.0))
        for metadata in metadata_items
        if _safe_int_value(metadata.get("request_duration_seconds")) is not None or metadata.get("request_duration_seconds") not in {None, ""}
    ]
    usage_items = [metadata for metadata in metadata_items if _bool_value(metadata.get("llm_usage_available", False))]
    summary: dict[str, Any] = {
        "runtime_metadata_record_count": len(metadata_items),
        "usage_metadata_record_count": len(usage_items),
    }
    if durations:
        summary.update(
            {
                "request_duration_seconds_total": round(sum(durations), 3),
                "request_duration_seconds_avg": round(sum(durations) / len(durations), 3),
                "request_duration_seconds_max": round(max(durations), 3),
            }
        )
    for field_name in ("input_tokens", "output_tokens", "total_tokens", "reasoning_tokens"):
        values = [
            _safe_int_value(metadata.get(field_name))
            for metadata in usage_items
            if _safe_int_value(metadata.get(field_name)) is not None
        ]
        if values:
            summary[f"{field_name}_total"] = sum(value for value in values if value is not None)
            summary[f"{field_name}_avg"] = round(
                sum(value for value in values if value is not None) / len(values),
                3,
            )
            summary[f"{field_name}_record_count"] = len(values)
    return summary


def _build_openai_canonicalization_chain(
    *,
    endpoint_url: str,
    model_id: str,
    timeout_seconds: int,
    max_tokens: int,
    structured_output_method: str,
    api_key_env: str,
    extra_body: Mapping[str, Any] | None,
) -> Any:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError("Install the operator-llm optional dependencies to run live canonicalization.") from exc

    model = ChatOpenAI(
        model=model_id,
        base_url=_openai_base_url_from_endpoint(endpoint_url),
        api_key=_api_key_from_env(api_key_env) or "not-needed",
        timeout=timeout_seconds,
        max_completion_tokens=max_tokens,
        temperature=0,
        extra_body=extra_body,
    )
    return build_langchain_canonicalization_chain(model, method=structured_output_method)


def _build_canonicalization_chain(
    *,
    provider: str,
    endpoint_url: str,
    model_id: str,
    timeout_seconds: int,
    max_tokens: int,
    structured_output_method: str,
    api_key_env: str,
    extra_body: Mapping[str, Any] | None,
) -> Any:
    api_key = _api_key_from_env(api_key_env) or "not-needed"
    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:  # pragma: no cover - optional operator dependency
            raise RuntimeError("Install the operator-llm optional dependencies to run live canonicalization.") from exc
        normalized_base_url = endpoint_url.rstrip("/")
        if normalized_base_url.endswith("/v1/messages"):
            normalized_base_url = normalized_base_url[: -len("/v1/messages")]
        elif normalized_base_url.endswith("/messages"):
            normalized_base_url = normalized_base_url[: -len("/messages")]
        model_kwargs: dict[str, Any] = {}
        if isinstance(extra_body, Mapping) and isinstance(extra_body.get("thinking"), Mapping):
            model_kwargs["thinking"] = dict(extra_body["thinking"])
        model = ChatAnthropic(
            model=model_id,
            base_url=normalized_base_url,
            api_key=api_key,
            timeout=timeout_seconds,
            max_tokens=max_tokens,
            **model_kwargs,
        )
        return build_langchain_canonicalization_chain(model, method=structured_output_method)
    return _build_openai_canonicalization_chain(
        endpoint_url=endpoint_url,
        model_id=model_id,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        structured_output_method=structured_output_method,
        api_key_env=api_key_env,
        extra_body=extra_body,
    )


def _build_verifier_chain(
    *,
    provider: str,
    endpoint_url: str,
    model_id: str,
    timeout_seconds: int,
    max_tokens: int,
    structured_output_method: str,
    api_key_env: str,
    extra_body: Mapping[str, Any] | None,
) -> Any:
    api_key = _api_key_from_env(api_key_env) or "not-needed"
    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:  # pragma: no cover - optional operator dependency
            raise RuntimeError("Install the operator-llm optional dependencies to run live verification.") from exc
        normalized_base_url = endpoint_url.rstrip("/")
        if normalized_base_url.endswith("/v1/messages"):
            normalized_base_url = normalized_base_url[: -len("/v1/messages")]
        elif normalized_base_url.endswith("/messages"):
            normalized_base_url = normalized_base_url[: -len("/messages")]
        model_kwargs: dict[str, Any] = {}
        if isinstance(extra_body, Mapping) and isinstance(extra_body.get("thinking"), Mapping):
            model_kwargs["thinking"] = dict(extra_body["thinking"])
        model = ChatAnthropic(
            model=model_id,
            base_url=normalized_base_url,
            api_key=api_key,
            timeout=timeout_seconds,
            max_tokens=max_tokens,
            **model_kwargs,
        )
        return build_langchain_verifier_chain(model, method=structured_output_method)
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError("Install the operator-llm optional dependencies to run live verification.") from exc
    model = ChatOpenAI(
        model=model_id,
        base_url=_openai_base_url_from_endpoint(endpoint_url),
        api_key=api_key,
        timeout=timeout_seconds,
        max_tokens=max_tokens,
        temperature=0,
        extra_body=extra_body,
    )
    return build_langchain_verifier_chain(model, method=structured_output_method)


def _build_atomic_operator_chat_model(
    *,
    provider: str,
    endpoint_url: str,
    model_id: str,
    timeout_seconds: int,
    max_tokens: int,
    api_key_env: str,
    extra_body: Mapping[str, Any] | None,
    temperature: float | None = None,
    parameter_transport: str = "",
) -> Any:
    api_key = _api_key_from_env(api_key_env) or "not-needed"
    if provider == "anthropic":
        if parameter_transport and parameter_transport != "anthropic_constructor":
            raise ValueError("anthropic atomic profile requires anthropic_constructor transport")
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:  # pragma: no cover - optional operator dependency
            raise RuntimeError("Install the operator-llm optional dependencies to run atomic verification.") from exc
        normalized_base_url = endpoint_url.rstrip("/")
        if normalized_base_url.endswith("/v1/messages"):
            normalized_base_url = normalized_base_url[: -len("/v1/messages")]
        elif normalized_base_url.endswith("/messages"):
            normalized_base_url = normalized_base_url[: -len("/messages")]
        model_kwargs = _anthropic_atomic_constructor_kwargs(extra_body)
        return ChatAnthropic(
            model=model_id,
            base_url=normalized_base_url,
            api_key=api_key,
            timeout=timeout_seconds,
            max_tokens=max_tokens,
            max_retries=0,
            temperature=temperature,
            **model_kwargs,
        )
    if parameter_transport and parameter_transport != "openai_extra_body":
        raise ValueError("openai atomic profile requires openai_extra_body transport")
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError("Install the operator-llm optional dependencies to run atomic verification.") from exc
    model_kwargs: dict[str, Any] = {}
    if temperature is not None:
        model_kwargs["temperature"] = temperature
    return ChatOpenAI(
        model=model_id,
        base_url=_openai_base_url_from_endpoint(endpoint_url),
        api_key=api_key,
        timeout=timeout_seconds,
        max_completion_tokens=max_tokens,
        max_retries=0,
        extra_body=extra_body,
        **model_kwargs,
    )


def _anthropic_atomic_constructor_kwargs(
    request_parameters: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Map an explicit allowlist to ChatAnthropic without silently dropping keys."""

    if not request_parameters:
        return {}
    allowed = {
        "betas",
        "disable_streaming",
        "effort",
        "model_kwargs",
        "output_config",
        "thinking",
        "top_k",
        "top_p",
    }
    unknown = sorted(set(request_parameters) - allowed)
    if unknown:
        raise ValueError(f"unsupported anthropic atomic request parameters: {unknown}")
    model_kwargs = dict(request_parameters)
    if isinstance(model_kwargs.get("thinking"), Mapping):
        model_kwargs["thinking"] = dict(model_kwargs["thinking"])
    if isinstance(model_kwargs.get("model_kwargs"), Mapping):
        model_kwargs["model_kwargs"] = dict(model_kwargs["model_kwargs"])
    return model_kwargs


def _build_atomic_runner_for_stage(
    *,
    stage: Literal["verifier", "critic", "repair"],
    stage_runtime: Mapping[str, Any],
    api_key_env: str,
) -> Any:
    reasoning_model = _build_atomic_operator_chat_model(
        provider=str(stage_runtime["provider"]),
        endpoint_url=str(stage_runtime["endpoint_url"]),
        model_id=str(stage_runtime["model_id"]),
        timeout_seconds=int(stage_runtime["timeout_seconds"]),
        max_tokens=int(stage_runtime["max_tokens"]),
        api_key_env=api_key_env,
        extra_body=stage_runtime.get("request_parameters"),
        temperature=stage_runtime.get("temperature"),
        parameter_transport=str(stage_runtime["parameter_transport"]),
    )
    formatter_runtime = stage_runtime.get("formatter_runtime")
    if not isinstance(formatter_runtime, Mapping):
        if stage == "verifier":
            return build_langchain_canonicalization_atomic_verifier_chain(
                reasoning_model,
                method=str(stage_runtime["structured_output_method"]),
            )
        if stage == "critic":
            return build_langchain_canonicalization_atomic_critic_chain(
                reasoning_model,
                method=str(stage_runtime["structured_output_method"]),
            )
        return build_langchain_canonicalization_atomic_repair_chain(
            reasoning_model,
            method=str(stage_runtime["structured_output_method"]),
        )

    formatter_model = _build_atomic_operator_chat_model(
        provider=str(formatter_runtime["provider"]),
        endpoint_url=str(formatter_runtime["endpoint_url"]),
        model_id=str(formatter_runtime["model_id"]),
        timeout_seconds=int(formatter_runtime["timeout_seconds"]),
        max_tokens=int(formatter_runtime["max_tokens"]),
        api_key_env=api_key_env,
        extra_body=formatter_runtime.get("request_parameters"),
        temperature=formatter_runtime.get("temperature"),
        parameter_transport=str(formatter_runtime["parameter_transport"]),
    )
    return AtomicTwoStepRunner(
        reasoning_runner=build_langchain_canonicalization_atomic_reasoning_chain(
            reasoning_model,
            stage=stage,
        ),
        formatter_runner=build_langchain_canonicalization_atomic_formatter_chain(
            formatter_model,
            stage=stage,
            method=str(formatter_runtime["structured_output_method"]),
        ),
        reasoning_runtime_profile=_atomic_component_runtime_identity(
            stage_runtime,
            component_role="reasoning",
        ),
        formatter_runtime_profile=_atomic_component_runtime_identity(
            formatter_runtime,
            component_role="formatter",
        ),
        formatter_output_contract=str(
            stage_runtime.get("formatter_output_contract", "final_schema")
        ),
    )


def _build_atomic_verifier_chain(
    *,
    provider: str,
    endpoint_url: str,
    model_id: str,
    timeout_seconds: int,
    max_tokens: int,
    structured_output_method: str,
    api_key_env: str,
    extra_body: Mapping[str, Any] | None,
    temperature: float | None = None,
    parameter_transport: str = "",
) -> Any:
    model = _build_atomic_operator_chat_model(
        provider=provider,
        endpoint_url=endpoint_url,
        model_id=model_id,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        api_key_env=api_key_env,
        extra_body=extra_body,
        temperature=temperature,
        parameter_transport=parameter_transport,
    )
    return build_langchain_canonicalization_atomic_verifier_chain(
        model,
        method=structured_output_method,
    )


def _build_atomic_critic_chain(
    *,
    provider: str,
    endpoint_url: str,
    model_id: str,
    timeout_seconds: int,
    max_tokens: int,
    structured_output_method: str,
    api_key_env: str,
    extra_body: Mapping[str, Any] | None,
    temperature: float | None = None,
    parameter_transport: str = "",
) -> Any:
    model = _build_atomic_operator_chat_model(
        provider=provider,
        endpoint_url=endpoint_url,
        model_id=model_id,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        api_key_env=api_key_env,
        extra_body=extra_body,
        temperature=temperature,
        parameter_transport=parameter_transport,
    )
    return build_langchain_canonicalization_atomic_critic_chain(
        model,
        method=structured_output_method,
    )


def _build_atomic_repair_chain(
    *,
    provider: str,
    endpoint_url: str,
    model_id: str,
    timeout_seconds: int,
    max_tokens: int,
    structured_output_method: str,
    api_key_env: str,
    extra_body: Mapping[str, Any] | None,
    temperature: float | None = None,
    parameter_transport: str = "",
) -> Any:
    model = _build_atomic_operator_chat_model(
        provider=provider,
        endpoint_url=endpoint_url,
        model_id=model_id,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        api_key_env=api_key_env,
        extra_body=extra_body,
        temperature=temperature,
        parameter_transport=parameter_transport,
    )
    return build_langchain_canonicalization_atomic_repair_chain(
        model,
        method=structured_output_method,
    )


def _build_openai_adjudication_chain(
    *,
    endpoint_url: str,
    model_id: str,
    timeout_seconds: int,
    max_tokens: int,
    structured_output_method: str,
    api_key_env: str,
    extra_body: Mapping[str, Any] | None,
) -> Any:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError("Install the operator-llm optional dependencies to run live adjudication.") from exc

    model = ChatOpenAI(
        model=model_id,
        base_url=_openai_base_url_from_endpoint(endpoint_url),
        api_key=_api_key_from_env(api_key_env) or "not-needed",
        timeout=timeout_seconds,
        max_completion_tokens=max_tokens,
        temperature=0,
        extra_body=extra_body,
    )
    return build_langchain_adjudication_chain(model, method=structured_output_method)


def _build_adjudication_chain(
    *,
    provider: str,
    endpoint_url: str,
    model_id: str,
    timeout_seconds: int,
    max_tokens: int,
    structured_output_method: str,
    api_key_env: str,
    extra_body: Mapping[str, Any] | None,
) -> Any:
    api_key = _api_key_from_env(api_key_env) or "not-needed"
    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:  # pragma: no cover - optional operator dependency
            raise RuntimeError("Install the operator-llm optional dependencies to run live adjudication.") from exc
        normalized_base_url = endpoint_url.rstrip("/")
        if normalized_base_url.endswith("/v1/messages"):
            normalized_base_url = normalized_base_url[: -len("/v1/messages")]
        elif normalized_base_url.endswith("/messages"):
            normalized_base_url = normalized_base_url[: -len("/messages")]
        model_kwargs: dict[str, Any] = {}
        if isinstance(extra_body, Mapping) and isinstance(extra_body.get("thinking"), Mapping):
            model_kwargs["thinking"] = dict(extra_body["thinking"])
        model = ChatAnthropic(
            model=model_id,
            base_url=normalized_base_url,
            api_key=api_key,
            timeout=timeout_seconds,
            max_tokens=max_tokens,
            **model_kwargs,
        )
        return build_langchain_adjudication_chain(model, method=structured_output_method)
    return _build_openai_adjudication_chain(
        endpoint_url=endpoint_url,
        model_id=model_id,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        structured_output_method=structured_output_method,
        api_key_env=api_key_env,
        extra_body=extra_body,
    )


def _build_legal_intent_extractor_chain(
    *,
    provider: str,
    endpoint_url: str,
    model_id: str,
    timeout_seconds: int,
    max_tokens: int,
    structured_output_method: str,
    api_key_env: str,
    extra_body: Mapping[str, Any] | None,
) -> Any:
    api_key = _api_key_from_env(api_key_env) or "not-needed"
    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:  # pragma: no cover - optional operator dependency
            raise RuntimeError("Install the operator-llm optional dependencies to run live legal-intent extraction.") from exc
        normalized_base_url = endpoint_url.rstrip("/")
        if normalized_base_url.endswith("/v1/messages"):
            normalized_base_url = normalized_base_url[: -len("/v1/messages")]
        elif normalized_base_url.endswith("/messages"):
            normalized_base_url = normalized_base_url[: -len("/messages")]
        model_kwargs: dict[str, Any] = {}
        if isinstance(extra_body, Mapping) and isinstance(extra_body.get("thinking"), Mapping):
            model_kwargs["thinking"] = dict(extra_body["thinking"])
        model = ChatAnthropic(
            model=model_id,
            base_url=normalized_base_url,
            api_key=api_key,
            timeout=timeout_seconds,
            max_tokens=max_tokens,
            **model_kwargs,
        )
        return build_langchain_legal_intent_extractor_chain(model, method=structured_output_method)
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError("Install the operator-llm optional dependencies to run live legal-intent extraction.") from exc
    model = ChatOpenAI(
        model=model_id,
        base_url=_openai_base_url_from_endpoint(endpoint_url),
        api_key=api_key,
        timeout=timeout_seconds,
        max_tokens=max_tokens,
        temperature=0,
        extra_body=extra_body,
    )
    return build_langchain_legal_intent_extractor_chain(model, method=structured_output_method)


def _build_legal_intent_pair_judge_chain(
    *,
    provider: str,
    endpoint_url: str,
    model_id: str,
    timeout_seconds: int,
    max_tokens: int,
    structured_output_method: str,
    api_key_env: str,
    extra_body: Mapping[str, Any] | None,
) -> Any:
    api_key = _api_key_from_env(api_key_env) or "not-needed"
    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:  # pragma: no cover - optional operator dependency
            raise RuntimeError("Install the operator-llm optional dependencies to run live legal-intent pair judging.") from exc
        normalized_base_url = endpoint_url.rstrip("/")
        if normalized_base_url.endswith("/v1/messages"):
            normalized_base_url = normalized_base_url[: -len("/v1/messages")]
        elif normalized_base_url.endswith("/messages"):
            normalized_base_url = normalized_base_url[: -len("/messages")]
        model_kwargs: dict[str, Any] = {}
        if isinstance(extra_body, Mapping) and isinstance(extra_body.get("thinking"), Mapping):
            model_kwargs["thinking"] = dict(extra_body["thinking"])
        model = ChatAnthropic(
            model=model_id,
            base_url=normalized_base_url,
            api_key=api_key,
            timeout=timeout_seconds,
            max_tokens=max_tokens,
            **model_kwargs,
        )
        return build_langchain_legal_intent_pair_judge_chain(model, method=structured_output_method)
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover - optional operator dependency
        raise RuntimeError("Install the operator-llm optional dependencies to run live legal-intent pair judging.") from exc
    model = ChatOpenAI(
        model=model_id,
        base_url=_openai_base_url_from_endpoint(endpoint_url),
        api_key=api_key,
        timeout=timeout_seconds,
        max_tokens=max_tokens,
        temperature=0,
        extra_body=extra_body,
    )
    return build_langchain_legal_intent_pair_judge_chain(model, method=structured_output_method)


def _build_openai_deepseek_adjudication_chain(
    *,
    endpoint_url: str,
    model_id: str,
    timeout_seconds: int,
    max_tokens: int,
    structured_output_method: str,
    api_key_env: str,
    extra_body: Mapping[str, Any] | None,
) -> Any:
    """Backward-compatible alias for the generic adjudication chain builder."""

    return _build_openai_adjudication_chain(
        endpoint_url=endpoint_url,
        model_id=model_id,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        structured_output_method=structured_output_method,
        api_key_env=api_key_env,
        extra_body=extra_body,
    )


def _canonicalization_record_from_structured_output(
    raw_result: Any,
    batch_item: Mapping[str, Any],
    *,
    canonicalization_run_id: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
) -> dict[str, Any]:
    payload = _structured_output_payload(raw_result)
    payload["task_id"] = str(payload.get("task_id", "")) or str(batch_item.get("task_id", ""))
    payload["task_scope"] = str(payload.get("task_scope", "")) or str(batch_item.get("task_scope", "question_candidate"))
    payload["candidate_id"] = str(payload.get("candidate_id", "")) or str(batch_item.get("candidate_id", ""))
    payload["canonicalization_run_id"] = canonicalization_run_id
    payload["canonicalization_contract_version"] = str(
        batch_item.get("canonicalization_contract_version", CANONICALIZATION_CONTRACT_VERSION)
    )
    payload["prompt_version"] = CANONICALIZATION_PROMPT_VERSION
    payload["runtime_contour"] = runtime_contour
    payload["backend"] = backend
    payload["model_id"] = model_id
    payload["status"] = str(payload.get("status", "")) or "completed"
    payload["legal_issue_frame_slug"] = _slugify(str(payload.get("legal_issue_frame_slug", "")) or str(payload.get("legal_issue_frame", "")))
    result = CanonicalizationResultPayload.model_validate(payload)
    cjk_failure_reason = _canonicalization_cjk_failure_reason(result)
    if cjk_failure_reason:
        raise RetryableOperatorOutputError(cjk_failure_reason)
    record = result.model_dump()
    _ensure_public_payload(record)
    return record


def _operator_failed_canonicalization_record(
    batch_item: Mapping[str, Any],
    *,
    canonicalization_run_id: str,
    failure_reason: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
) -> dict[str, Any]:
    return {
        "task_id": str(batch_item.get("task_id", "")),
        "task_scope": str(batch_item.get("task_scope", "question_candidate")),
        "candidate_id": str(batch_item.get("candidate_id", "")),
        "canonicalization_run_id": canonicalization_run_id,
        "canonicalization_contract_version": str(
            batch_item.get("canonicalization_contract_version", CANONICALIZATION_CONTRACT_VERSION)
        ),
        "prompt_version": CANONICALIZATION_PROMPT_VERSION,
        "runtime_contour": runtime_contour,
        "backend": backend,
        "model_id": model_id,
        "status": "failed",
        "failure_reason": failure_reason,
        "canonical_question": "",
        "canonical_question_language": "",
        "legal_issue_frame": "",
        "legal_issue_frame_slug": "",
        "law_area": "",
        "facts": [],
        "desired_outcome": "",
        "authority_context": [],
        "hidden_issues": [],
        "is_legal_answer_required": False,
        "is_standalone_question": False,
        "exclusion_reason": "llm_failed",
        "confidence": "low",
        "quality_flags": ["canonicalization_live_runner_failed"],
    }


def _compact_verifier_llm_payload(evidence: Mapping[str, Any]) -> dict[str, Any]:
    qwen_payload = {
        "candidate_key": "qwen",
        "status": str(evidence.get("status", "")),
        "canonical_question": str(evidence.get("canonical_question", "")),
        "legal_issue_frame": str(evidence.get("legal_issue_frame", "")),
        "facts": _as_string_list(evidence.get("facts", [])),
        "hidden_issues": _as_string_list(evidence.get("hidden_issues", [])),
        "quality_flags": _as_string_list(evidence.get("quality_flags", [])),
        "exclusion_reason": str(evidence.get("exclusion_reason", "")),
    }
    payload = {
        "task_id": str(evidence.get("task_id", "")),
        "candidate_id": str(evidence.get("candidate_id", "")),
        "source_question_text_redacted": str(evidence.get("source_question_text_redacted", "")),
        "question_date": str(evidence.get("question_date", "")),
        "qwen": {
            "canonical_question": qwen_payload["canonical_question"],
            "canonical_question_language": str(evidence.get("canonical_question_language", "")),
            "legal_issue_frame": qwen_payload["legal_issue_frame"],
            "legal_issue_frame_slug": str(evidence.get("legal_issue_frame_slug", "")),
            "law_area": str(evidence.get("law_area", "")),
            "facts": qwen_payload["facts"],
            "desired_outcome": str(evidence.get("desired_outcome", "")),
            "authority_context": _as_string_list(evidence.get("authority_context", [])),
            "hidden_issues": qwen_payload["hidden_issues"],
            "is_legal_answer_required": _bool_value(evidence.get("is_legal_answer_required", False)),
            "is_standalone_question": _bool_value(evidence.get("is_standalone_question", False)),
            "exclusion_reason": qwen_payload["exclusion_reason"],
            "confidence": str(evidence.get("confidence", "")),
            "quality_flags": qwen_payload["quality_flags"],
        },
        "field_scope_review": {
            "instruction": "Before marking canonical_question or legal_issue_frame as bad, check these candidate fields only; source text and verifier reasons are context, not the field text.",
            "qwen": _field_scope_review_candidate(qwen_payload),
        },
        "local_validation": {"status": str(evidence.get("status", "")), "failure_reason": str(evidence.get("failure_reason", ""))},
    }
    _ensure_public_payload(payload)
    return payload


def _compact_adjudication_payload(batch_item: Mapping[str, Any]) -> dict[str, Any]:
    candidates = batch_item.get("candidates")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        legacy_qwen = batch_item.get("qwen", {})
        candidates = [
            {
                "candidate_key": "primary",
                **dict(legacy_qwen),
            }
        ] if isinstance(legacy_qwen, Mapping) and legacy_qwen else []
    verifier_votes = batch_item.get("verifier_votes")
    if not isinstance(verifier_votes, Sequence) or isinstance(verifier_votes, (str, bytes)):
        legacy_verifier = batch_item.get("minimax_verifier", {})
        verifier_votes = [
            {
                "candidate_key": "primary",
                "verifier_key": "reviewer_1",
                **dict(legacy_verifier),
            }
        ] if isinstance(legacy_verifier, Mapping) and legacy_verifier else []
    payload = {
        "task_id": str(batch_item.get("task_id", "")),
        "candidate_id": str(batch_item.get("candidate_id", "")),
        "adjudication_prompt_version": str(batch_item.get("adjudication_prompt_version", "")),
        "source_question_text_redacted": str(batch_item.get("source_question_text_redacted", "")),
        "question_date": str(batch_item.get("question_date", "")),
        "candidates": [dict(item) for item in candidates if isinstance(item, Mapping)],
        "verifier_votes": [dict(item) for item in verifier_votes if isinstance(item, Mapping)],
        "field_scope_review": {
            "instruction": "Before repeating a verifier claim that canonical_question or legal_issue_frame merged source details, inspect these candidate fields only. Source text, facts, hidden_issues, quality_flags, and verifier reasons may mention intentionally omitted source details.",
            "candidates": [
                _field_scope_review_candidate(item)
                for item in candidates
                if isinstance(item, Mapping)
            ],
        },
        "consensus_summary": (
            dict(batch_item.get("consensus_summary", {}))
            if isinstance(batch_item.get("consensus_summary"), Mapping)
            else {}
        ),
        "human_triage": dict(batch_item.get("human_triage", {})) if isinstance(batch_item.get("human_triage"), Mapping) else {},
        "expected_output_schema": (
            dict(batch_item.get("expected_output_schema", {}))
            if isinstance(batch_item.get("expected_output_schema"), Mapping)
            else {}
        ),
    }
    _ensure_public_payload(payload)
    return payload


def _compact_deepseek_adjudication_payload(batch_item: Mapping[str, Any]) -> dict[str, Any]:
    """Backward-compatible alias for the generic compact adjudication payload."""

    return _compact_adjudication_payload(batch_item)


def _verifier_record_from_structured_output(
    raw_result: Any,
    evidence: Mapping[str, Any],
    *,
    verifier_run_id: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
) -> dict[str, Any]:
    payload = _structured_output_payload(raw_result) if raw_result is not None else {}
    payload = _unwrap_structured_output_mapping(payload)
    verdict = VerifierVerdictPayload.model_validate(payload)
    record = verdict.model_dump()
    record.update(
        {
            "task_id": str(evidence.get("task_id", "")),
            "candidate_id": str(evidence.get("candidate_id", "")),
            "canonicalization_evidence_id": str(evidence.get("canonicalization_evidence_id", "")),
            "verifier_run_id": verifier_run_id,
            "runtime_contour": runtime_contour,
            "backend": backend,
            "model_id": model_id,
            "status": "completed",
            "failure_reason": "",
        }
    )
    _ensure_public_payload(record)
    return record


def _adjudication_record_from_structured_output(
    raw_result: Any,
    batch_item: Mapping[str, Any],
    *,
    adjudication_run_id: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
) -> dict[str, Any]:
    payload = _structured_output_payload(raw_result) if raw_result is not None else {}
    payload = _unwrap_structured_output_mapping(payload)
    if not str(payload.get("selected_candidate_key", "")).strip():
        candidates = batch_item.get("candidates", [])
        if isinstance(candidates, Sequence) and not isinstance(candidates, (str, bytes)) and len(candidates) == 1:
            only_candidate = candidates[0]
            if isinstance(only_candidate, Mapping):
                recommendation = _strip_matching_quotes(payload.get("final_recommendation", ""))
                recommendation = {"retry_qwen": "retry_generator"}.get(recommendation, recommendation)
                if recommendation in {"accept", "retry_generator"}:
                    payload["selected_candidate_key"] = str(only_candidate.get("candidate_key", "")) or "primary"
    verdict = AdjudicationPayload.model_validate(payload)
    record = verdict.model_dump()
    if (
        str(record.get("final_recommendation", "")) in {"accept", "retry_generator"}
        and not str(record.get("selected_candidate_key", "")).strip()
    ):
        raise ValueError("missing_selected_candidate_key")
    record.update(
        {
            "task_id": str(batch_item.get("task_id", "")),
            "candidate_id": str(batch_item.get("candidate_id", "")),
            "adjudication_run_id": adjudication_run_id,
            "runtime_contour": runtime_contour,
            "backend": backend,
            "model_id": model_id,
            "status": "completed",
            "failure_reason": "",
        }
    )
    _ensure_public_payload(record)
    return record


def _deepseek_record_from_structured_output(
    raw_result: Any,
    batch_item: Mapping[str, Any],
    *,
    adjudication_run_id: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
) -> dict[str, Any]:
    """Backward-compatible alias for the generic adjudication record parser."""

    return _adjudication_record_from_structured_output(
        raw_result,
        batch_item,
        adjudication_run_id=adjudication_run_id,
        runtime_contour=runtime_contour,
        backend=backend,
        model_id=model_id,
    )


def _skipped_verifier_record(
    evidence: Mapping[str, Any],
    *,
    verifier_run_id: str,
    failure_reason: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
) -> dict[str, Any]:
    record = _failed_verifier_record(
        evidence,
        verifier_run_id=verifier_run_id,
        failure_reason=failure_reason or "non_completed_canonicalization_evidence",
        runtime_contour=runtime_contour,
        backend=backend,
        model_id=model_id,
    )
    record["status"] = "skipped"
    return record


def _failed_verifier_record(
    evidence: Mapping[str, Any],
    *,
    verifier_run_id: str,
    failure_reason: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
) -> dict[str, Any]:
    return {
        "task_id": str(evidence.get("task_id", "")),
        "candidate_id": str(evidence.get("candidate_id", "")),
        "canonicalization_evidence_id": str(evidence.get("canonicalization_evidence_id", "")),
        "verifier_run_id": verifier_run_id,
        "runtime_contour": runtime_contour,
        "backend": backend,
        "model_id": model_id,
        "status": "failed",
        "failure_reason": failure_reason,
        "verdict": "uncertain",
        "confidence": 0,
        "risk": "high",
        "bad_fields": [],
        "short_reason": failure_reason,
        "suggested_action": "human_review",
    }


def _failed_adjudication_record(
    batch_item: Mapping[str, Any],
    *,
    adjudication_run_id: str,
    failure_reason: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
) -> dict[str, Any]:
    return {
        "task_id": str(batch_item.get("task_id", "")),
        "candidate_id": str(batch_item.get("candidate_id", "")),
        "adjudication_run_id": adjudication_run_id,
        "runtime_contour": runtime_contour,
        "backend": backend,
        "model_id": model_id,
        "status": "failed",
        "failure_reason": failure_reason,
        "verdict": "uncertain",
        "confidence": 0,
        "risk": "high",
        "bad_fields": [],
        "short_reason": failure_reason,
        "final_recommendation": "human_review",
        "selected_candidate_key": "",
    }


def _failed_deepseek_record(
    batch_item: Mapping[str, Any],
    *,
    adjudication_run_id: str,
    failure_reason: str,
    runtime_contour: str,
    backend: str,
    model_id: str,
) -> dict[str, Any]:
    """Backward-compatible alias for the generic adjudication failure record."""

    return _failed_adjudication_record(
        batch_item,
        adjudication_run_id=adjudication_run_id,
        failure_reason=failure_reason,
        runtime_contour=runtime_contour,
        backend=backend,
        model_id=model_id,
    )


def _api_key_from_env(api_key_env: str) -> str:
    if not api_key_env:
        return ""
    value = os.environ.get(api_key_env, "")
    if not value:
        raise ValueError(f"environment variable {api_key_env} is not set")
    return value


def _openai_base_url_from_endpoint(endpoint_url: str) -> str:
    stripped = endpoint_url.rstrip("/")
    if stripped.endswith("/chat/completions"):
        return stripped.removesuffix("/chat/completions")
    return stripped


def _redacted_endpoint_shape(endpoint_url: str) -> str:
    stripped = endpoint_url.rstrip("/")
    if stripped.endswith("/chat/completions"):
        return "redacted_openai_compatible_chat_completion"
    if "/anthropic" in stripped:
        return "redacted_anthropic_compatible_messages"
    return "redacted_llm_endpoint"


def _operator_error_reason(exc: Exception) -> str:
    detail_parts: list[str] = []
    base_message = _stringify_operator_error_value(str(exc))
    if base_message:
        detail_parts.append(base_message)
    for attr_name in ("observation", "llm_output"):
        if not hasattr(exc, attr_name):
            continue
        attr_value = getattr(exc, attr_name)
        attr_text = _stringify_operator_error_value(attr_value)
        if attr_text and attr_text not in detail_parts:
            detail_parts.append(f"{attr_name} {attr_text}")
    detail = _sanitize_operator_error_text(" | ".join(detail_parts))
    prefix = f"endpoint_error:{type(exc).__name__}"
    if not detail:
        return prefix
    return f"{prefix}:{_truncate_text(detail, OPERATOR_ERROR_REASON_LIMIT)}"


def _operator_should_retry_exception(exc: Exception) -> bool:
    if isinstance(exc, RetryableOperatorOutputError):
        return True
    type_name = type(exc).__name__
    if type_name == "OutputParserException":
        return False
    if type_name in TRANSIENT_PROVIDER_ERROR_TYPE_NAMES:
        return True
    message = _sanitize_operator_error_text(_stringify_operator_error_value(exc)).lower()
    if any(token in message for token in ("output parser", "invalid json", "validationerror", "schema")):
        return False
    return any(token in message for token in TRANSIENT_PROVIDER_ERROR_PATTERNS)


def _operator_failure_reason_with_attempts(failure_reason: str, attempts_used: int) -> str:
    if attempts_used <= 1:
        return failure_reason
    return f"{failure_reason} retry_attempts={attempts_used}"


def _operator_retry_allowed(attempts_used: int, provider_max_attempts: int) -> bool:
    if provider_max_attempts == 0:
        return True
    return attempts_used < provider_max_attempts


def _operator_retry_limit_for_exception(exc: Exception, provider_max_attempts: int) -> int:
    if not isinstance(exc, RetryableOperatorOutputError):
        return provider_max_attempts
    if provider_max_attempts == 0:
        return OPERATOR_OUTPUT_RETRY_MAX_ATTEMPTS
    return min(provider_max_attempts, OPERATOR_OUTPUT_RETRY_MAX_ATTEMPTS)


def _operator_retry_limit_label(provider_max_attempts: int) -> str:
    return "inf" if provider_max_attempts == 0 else str(provider_max_attempts)


def _operator_provider_failure_guard_key(record: Mapping[str, Any]) -> str:
    """Return a stable outage key for exhausted provider failures, or empty."""

    if str(record.get("status", "")) != "failed":
        return ""
    failure_reason = str(record.get("failure_reason", ""))
    if not failure_reason.startswith("endpoint_error:"):
        return ""
    lowered = failure_reason.lower()
    if any(
        token in lowered
        for token in (
            "outputparserexception",
            "retryableoperatoroutputerror",
            "validationerror",
            "invalid json",
            "output parser",
            "schema",
        )
    ):
        return ""
    parts = failure_reason.split(":", 2)
    error_type = parts[1] if len(parts) > 1 and parts[1] else "unknown"
    code_match = PROVIDER_ERROR_CODE_RE.search(failure_reason)
    if code_match:
        return f"endpoint_error:{error_type}:{code_match.group(1)}"
    return f"endpoint_error:{error_type}"


def _empty_operator_resume_state() -> dict[str, Any]:
    return {
        "processed_task_ids": set(),
        "status_counts": Counter(),
    }


def _load_existing_operator_results(
    output_path: str | Path,
    batch_items: Sequence[Mapping[str, Any]],
    *,
    stage: str = "",
    runtime_profile: Mapping[str, Any] | None = None,
    input_identity_field: str = "",
) -> dict[str, Any]:
    path = Path(output_path)
    if not path.exists():
        return _empty_operator_resume_state()
    expected_by_task = {
        str(item.get("task_id", "")): str(item.get(input_identity_field, ""))
        for item in batch_items
        if item.get("task_id")
    }
    strict_profile = bool(stage and runtime_profile is not None and input_identity_field)
    if not expected_by_task or (strict_profile and any(not identity for identity in expected_by_task.values())):
        raise ValueError(f"resume input is missing {input_identity_field}")
    expected_runtime_profile_hash = _stable_json_hash(dict(runtime_profile or {}))
    processed_task_ids: set[str] = set()
    status_counts: Counter[str] = Counter()
    foreign_task_ids: set[str] = set()
    for line_number, payload, error in _read_jsonl_tolerant(path):
        if error:
            raise ValueError(f"existing output path contains invalid jsonl at line {line_number}: {error}")
        assert payload is not None
        task_id = str(payload.get("task_id", ""))
        if not task_id:
            continue
        if task_id not in expected_by_task:
            foreign_task_ids.add(task_id)
            continue
        if task_id in processed_task_ids:
            raise ValueError(f"existing output path contains duplicate task_id: {task_id}")
        if strict_profile:
            if str(payload.get("operator_stage", "")) != stage:
                raise ValueError(f"existing output path has incompatible operator stage for task_id: {task_id}")
            if str(payload.get("runtime_profile_hash", "")) != expected_runtime_profile_hash:
                raise ValueError(f"existing output path has incompatible runtime profile for task_id: {task_id}")
            if str(payload.get(input_identity_field, "")) != expected_by_task[task_id]:
                raise ValueError(f"existing output path has incompatible {input_identity_field} for task_id: {task_id}")
        processed_task_ids.add(task_id)
        status_counts[str(payload.get("status", ""))] += 1
    if foreign_task_ids:
        raise ValueError(
            f"existing output path does not match batch task ids; found {len(foreign_task_ids)} foreign task ids"
        )
    return {
        "processed_task_ids": processed_task_ids,
        "status_counts": status_counts,
    }


def _stringify_operator_error_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Mapping) or isinstance(value, list | tuple):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except TypeError:
            return str(value)
    return str(value)


def _sanitize_operator_error_text(value: str) -> str:
    text = URL_RE.sub("[url]", value)
    text = EMAIL_RE.sub("[email]", text)
    text = BEARER_TOKEN_RE.sub("bearer [redacted]", text)
    text = CREDENTIAL_ASSIGNMENT_RE.sub("credential [redacted]", text)
    text = API_KEY_VALUE_RE.sub("[api-key-redacted]", text)
    return SPACE_RE.sub(" ", text).strip()


def _truncate_text(value: str, limit: int) -> str:
    if limit <= 0 or len(value) <= limit:
        return value
    return value[: max(limit - 3, 0)].rstrip() + "..."


def _operator_progress_detail(
    event: str,
    index: int,
    total: int,
    item: Mapping[str, Any],
    *,
    failure_reason: str = "",
) -> str:
    details = [
        f"{event} {index}/{total}",
        f"task={item.get('task_id', '')}",
        f"candidate={item.get('candidate_id', '')}",
    ]
    if failure_reason:
        details.append(
            f"failure={_truncate_text(_sanitize_operator_error_text(failure_reason), OPERATOR_PROGRESS_DETAIL_LIMIT)}"
        )
    return " ".join(details)


class _OperatorProgress:
    def __init__(self, *, enabled: bool, label: str, total: int) -> None:
        self.enabled = enabled
        self.label = label
        self.total = max(total, 0)
        self.started = perf_counter()
        self.last_len = 0
        self.is_tty = sys.stderr.isatty()

    def update(
        self,
        processed: int,
        *,
        completed: int,
        failed: int,
        skipped: int,
        last_status: str = "",
        detail: str = "",
    ) -> None:
        if not self.enabled:
            return
        elapsed = max(perf_counter() - self.started, 0.001)
        rate = processed / elapsed if processed > 0 else 0.0
        remaining = max(self.total - processed, 0)
        eta = remaining / rate if rate > 0 else 0.0
        percent = (processed / self.total * 100) if self.total else 100.0
        text = (
            f"{self.label}: {processed}/{self.total} ({percent:5.1f}%) "
            f"ok={completed} failed={failed} skipped={skipped} elapsed={_format_duration(elapsed)}"
        )
        if rate > 0:
            text += f" rate={rate:.3f}/s eta={_format_duration(eta)}"
        if last_status:
            text += f" last_status={last_status}"
        if detail:
            text += f" | {detail}"
        self._write(_truncate_text(text, 1200))

    def finish(self, processed: int, *, completed: int, failed: int, skipped: int) -> None:
        if not self.enabled:
            return
        elapsed = max(perf_counter() - self.started, 0.001)
        text = (
            f"{self.label}: {processed}/{self.total} (100.0%) "
            f"ok={completed} failed={failed} skipped={skipped} elapsed={_format_duration(elapsed)}"
        )
        self._write(text)
        if self.is_tty:
            sys.stderr.write("\n")
            sys.stderr.flush()

    def _write(self, text: str) -> None:
        if self.is_tty:
            padding = " " * max(0, self.last_len - len(text))
            sys.stderr.write("\r" + text + padding)
            sys.stderr.flush()
            self.last_len = len(text)
            return
        print(text, file=sys.stderr, flush=True)


def _format_duration(seconds: float) -> str:
    total_seconds = int(max(seconds, 0))
    minutes, remaining_seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}h{minutes:02d}m{remaining_seconds:02d}s"
    if minutes:
        return f"{minutes:d}m{remaining_seconds:02d}s"
    return f"{remaining_seconds:d}s"


def _read_jsonl(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    items: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _read_jsonl_tolerant(path: str | Path) -> Iterable[tuple[int, dict[str, Any] | None, str]]:
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            yield line_number, None, f"invalid_json:{exc.msg}"
            continue
        if not isinstance(payload, dict):
            yield line_number, None, "not_json_object"
            continue
        yield line_number, payload, ""


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return f"{prefix}:{sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _pydantic_failure_reason(exc: ValidationError) -> str:
    for error in exc.errors():
        message = str(error.get("msg", ""))
        if message.startswith("Value error, "):
            return message.removeprefix("Value error, ")
        location = ".".join(str(part) for part in error.get("loc", []) if str(part))
        error_type = str(error.get("type", "validation_error"))
        return f"schema_invalid:{location}:{error_type}" if location else f"schema_invalid:{error_type}"
    return "schema_invalid"


def _unwrap_structured_output_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(payload)
    for key in ("answer", "output", "result", "data"):
        nested = raw.get(key)
        if isinstance(nested, Mapping):
            nested_dict = dict(nested)
            if any(
                field in nested_dict
                for field in (
                    "verdict",
                    "confidence",
                    "risk",
                    "bad_fields",
                    "short_reason",
                    "suggested_action",
                    "final_recommendation",
                    "selected_candidate_key",
                )
            ):
                return nested_dict
    return raw


def _verifier_payload_for_review(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not payload:
        return {}
    atomic_view = _atomic_verifier_payload_for_review(payload)
    if atomic_view is not None:
        return atomic_view
    raw = _unwrap_structured_output_mapping(payload)
    if "short_reason" not in raw and "reason" in raw:
        raw["short_reason"] = raw["reason"]
    try:
        verdict = VerifierVerdictPayload.model_validate(raw)
    except ValidationError as exc:
        return {
            "verdict": "uncertain",
            "confidence": 0,
            "risk": "high",
            "bad_fields": [],
            "short_reason": _pydantic_failure_reason(exc),
            "suggested_action": "human_review",
        }
    return verdict.model_dump()


def _atomic_verifier_payload_for_review(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if (
        str(payload.get("artifact_type", ""))
        != "tg_qa_canonicalization_atomic_verify_repair_record"
        and str(payload.get("operator_stage", "")) != "atomic_verify_repair"
    ):
        return None

    route = str(payload.get("route", "hold"))
    status = str(payload.get("status", ""))
    repair_attempted = bool(payload.get("repair_attempted", False))
    changed_fields = _as_string_list(payload.get("changed_fields", []))
    controller = payload.get("initial_controller", {})
    if not isinstance(controller, Mapping):
        controller = {}
    feedback = controller.get("feedback", [])
    if not isinstance(feedback, list):
        feedback = []

    bad_fields = set(changed_fields)
    findings: list[str] = []
    for item in feedback:
        if not isinstance(item, Mapping):
            continue
        field_name = str(item.get("field_name", ""))
        if field_name:
            bad_fields.add(field_name)
        reason = str(item.get("short_reason", "")).strip()
        correction = str(item.get("correction", "")).strip()
        detail = ": ".join(part for part in (field_name, reason) if part)
        if correction:
            detail = f"{detail}; correction: {correction}" if detail else correction
        if detail:
            findings.append(detail)

    reason_parts = [f"Atomic route: {route}."]
    initial_verification = payload.get("initial_verification", {})
    if isinstance(initial_verification, Mapping):
        initial_reason = str(initial_verification.get("short_reason", "")).strip()
        if initial_reason:
            reason_parts.append(initial_reason)
    reason_parts.extend(findings)

    if repair_attempted:
        repaired_candidate = payload.get("repaired_candidate", {})
        if not isinstance(repaired_candidate, Mapping):
            repaired_candidate = {}
        repaired_values = {
            field_name: repaired_candidate.get(field_name)
            for field_name in changed_fields
            if field_name in repaired_candidate
        }
        reason_parts.append(
            "Repaired fields: "
            + json.dumps(repaired_values, ensure_ascii=False, sort_keys=True)
        )

    failure_reason = str(payload.get("failure_reason", "")).strip()
    if status != "completed" and failure_reason:
        reason_parts.append(f"Failure: {failure_reason}")

    if route in {"pass", "pass_repaired"} and status == "completed":
        verdict = "pass"
        risk = "medium" if route == "pass_repaired" else "low"
    else:
        verdict = "uncertain"
        risk = "high"
    return {
        "verdict": verdict,
        "confidence": 0,
        "risk": risk,
        "bad_fields": sorted(bad_fields),
        "short_reason": " ".join(reason_parts),
        "suggested_action": "human_review",
    }


def _slugify(value: str) -> str:
    text = value.strip().lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = SLUG_RE.sub("_", text).strip("_")
    return re.sub(r"_+", "_", text)


def _signature_text(value: str) -> str:
    return SPACE_RE.sub(" ", value.strip().lower())


def _redact_private_text(value: str) -> str:
    text = URL_RE.sub("[url]", value)
    text = EMAIL_RE.sub("[email]", text)
    text = PHONE_RE.sub("[phone]", text)
    text = USERNAME_RE.sub("[username]", text)
    return SPACE_RE.sub(" ", text).strip()


def _normalized_text(value: Any) -> str:
    return SPACE_RE.sub(" ", str(value).casefold()).strip()


def _ensure_public_payload(payload: Any) -> None:
    violations: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for item in value.values():
                walk(item)
        elif isinstance(value, list | tuple | set):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            lowered = value.lower()
            if "data/tg/" in lowered or "telegram export" in lowered:
                violations.append("raw_telegram_input_reference")
            if ".env" in lowered or "neo4j_password" in lowered or "password=" in lowered or "api_key=" in lowered:
                violations.append("secret_or_env_reference")
            if re.search(r"\bsk-[A-Za-z0-9_-]{10,}", value):
                violations.append("api_key_like_value")
            if re.search(r"https?://", value, flags=re.IGNORECASE):
                violations.append("endpoint_or_url")

    walk(payload)
    if violations:
        raise ValueError(f"private or unsafe payload value detected: {sorted(set(violations))}")


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, Sequence):
        return [str(item) for item in value if str(item)]
    return [str(value)] if str(value) else []


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _strip_matching_quotes(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1].strip()
    return text


def _counts(values: Iterable[str]) -> dict[str, int]:
    counter = Counter(value for value in values if value)
    return dict(sorted(counter.items()))


def _parse_keyed_path_spec(spec: str, *, label: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise ValueError(f"Invalid {label} spec: {spec!r}. Expected key=path.")
    key, path = spec.split("=", 1)
    key = key.strip()
    path = path.strip()
    if not key or not path:
        raise ValueError(f"Invalid {label} spec: {spec!r}. Expected key=path.")
    return key, Path(path)


def _parse_candidate_verifier_path_spec(spec: str) -> tuple[str, str, Path]:
    if "=" not in spec or ":" not in spec.split("=", 1)[0]:
        raise ValueError(f"Invalid verifier result spec: {spec!r}. Expected candidate:verifier=path.")
    left, path = spec.split("=", 1)
    candidate_key, verifier_key = left.split(":", 1)
    candidate_key = candidate_key.strip()
    verifier_key = verifier_key.strip()
    path = path.strip()
    if not candidate_key or not verifier_key or not path:
        raise ValueError(f"Invalid verifier result spec: {spec!r}. Expected candidate:verifier=path.")
    return candidate_key, verifier_key, Path(path)


def _first_non_empty(values: Iterable[str]) -> str:
    for value in values:
        if value:
            return value
    return ""


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
