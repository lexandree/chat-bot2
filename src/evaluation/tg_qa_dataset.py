"""Telegram export question/answer candidate extraction for evaluation datasets."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import csv
import json
from math import sqrt
import os
from pathlib import Path
import re
import sys
from time import perf_counter
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib import error, request
from urllib.parse import urlparse

from evaluation.prompts import (
    TG_QA_CANDIDATE_PROMPT_PROFILE,
    TG_QA_CANDIDATE_PROMPT_VERSION,
    TG_QA_CLUSTER_COMPACT_PROMPT_PROFILE,
    TG_QA_CLUSTER_COMPACT_PROMPT_VERSION,
    TG_QA_CLUSTER_PROMPT_PROFILE,
    TG_QA_CLUSTER_PROMPT_VERSION,
)
from retrieval.embedding_endpoint_client import EmbeddingEndpointClient
from retrieval.embedding_profile import EmbeddingProfile, validate_vector


QUESTION_MARKERS = (
    "?",
    "подскажите",
    "скажите",
    "как",
    "какие",
    "какой",
    "какая",
    "куда",
    "где",
    "когда",
    "можно ли",
    "нужно ли",
    "есть ли",
    "имею ли",
    "что делать",
    "кто знает",
    "wie",
    "was",
    "wo",
    "wann",
    "kann ich",
    "muss ich",
    "brauche ich",
)
TOPIC_KEYWORDS = {
    "migration_status": (
        "aufenthg",
        "aufenthalt",
        "aufenthaltstitel",
        "aufenthaltserlaubnis",
        "niederlassungserlaubnis",
        "fiktion",
        "fiktionsbescheinigung",
        "ausländerbehörde",
        "abh",
        "внж",
        "пмж",
        "вид на жительство",
        "карта",
        "blue card",
        "blaue karte",
        "виза",
        "visum",
        "familiennachzug",
    ),
    "asylum": (
        "asyl",
        "asylg",
        "bamf",
        "dublin",
        "flüchtling",
        "бежен",
        "убежище",
        "азил",
    ),
    "employment": (
        "beschäftigung",
        "beschv",
        "arbeit",
        "arbeitserlaubnis",
        "работа",
        "работать",
        "работодатель",
        "job",
        "zustimmung ba",
        "bundesagentur",
        "ausbildung",
        "anerkennung",
        "16d",
    ),
}
LAW_CODE_KEYWORDS = {
    "AufenthG": (
        "aufenthg",
        "aufenthalt",
        "aufenthaltstitel",
        "aufenthaltserlaubnis",
        "niederlassung",
        "fiktion",
        "familiennachzug",
        "blue card",
        "blaue karte",
        "внж",
        "пмж",
        "виза",
    ),
    "AsylG": ("asylg", "asyl", "bamf", "dublin", "бежен", "убежище", "азил"),
    "BeschV": (
        "beschv",
        "beschäftigung",
        "arbeitserlaubnis",
        "zustimmung ba",
        "bundesagentur",
        "работа",
        "работать",
        "ausbildung",
        "anerkennung",
        "16d",
    ),
}
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
USERNAME_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{4,32}\b")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{6,}\d)(?!\w)")
SPACE_RE = re.compile(r"\s+")
SELECTION_POLICY = "semantic_qa_cluster_latest_usable_answer"
QUESTION_EMBEDDING_PREFIX = "Query: "
ANSWER_EMBEDDING_PREFIX = "Document: "
BOT_ANSWER_MARKING_POLICY = "all_reply_answers_kept_with_bot_source_markers"
QUESTION_TRIGGER_WINDOW_MESSAGES = 10
QUESTION_TRIGGER_WINDOW_SECONDS = 600
TRIGGER_BOT_WINDOW_SECONDS = 120
TRIGGER_TEXT_MAX_CHARS = 80
TRIGGER_TEXT_MAX_WORDS = 8
MAX_ANSWER_CANDIDATES_PER_QUESTION = 8
CLUSTERING_POLICY_VERSION = "tg_qa_cluster_policy_v1"
LLM_CONTRACT_VERSION = "tg_qa_llm_analysis_v1"
LLM_CANDIDATE_PROMPT_VERSION = TG_QA_CANDIDATE_PROMPT_VERSION
LLM_CLUSTER_PROMPT_VERSION = TG_QA_CLUSTER_PROMPT_VERSION
LLM_CLUSTER_COMPACT_PROMPT_VERSION = TG_QA_CLUSTER_COMPACT_PROMPT_VERSION

COVERAGE_ANALYSIS_VERSION = "tg_qa_dataset_corpus_coverage_v1"
CORPUS_COVERAGE_FILTER_MODES = ("all", "law_or_topic", "legalish")
QUESTION_COVERAGE_THRESHOLDS = {
    "high": 0.90,
    "medium": 0.82,
    "low": 0.74,
}
ANSWER_SUPPORT_THRESHOLDS = {
    "strong": 0.90,
    "medium": 0.86,
    "weak": 0.78,
}
LLM_COMPACT_INPUT_CHAR_BUDGET = 3600
ISSUE_SPOTTING_LEVELS = ("none", "low", "medium", "high", "unclassified")
ISSUE_SPOTTING_CONFIDENCE_LEVELS = ("low", "medium", "high", "unclassified")
HIDDEN_LEGAL_ISSUE_CATEGORY_TAXONOMY = (
    "residence_status",
    "asylum_or_temporary_protection",
    "work_authorization",
    "self_employment",
    "tax_income_reporting",
    "social_benefits",
    "health_insurance",
    "family_or_children",
    "housing_registration",
    "education_language",
    "authority_procedure",
    "deadline_or_proof",
    "travel_cross_border",
    "criminal_or_fraud_risk",
    "other",
)
HIDDEN_LEGAL_ISSUE_CATEGORY_ALIASES = {
    "tax": "tax_income_reporting",
    "tax_duty": "tax_income_reporting",
    "tax_duties": "tax_income_reporting",
    "tax_obligation": "tax_income_reporting",
    "income_reporting": "tax_income_reporting",
    "benefit_reporting": "social_benefits",
    "benefits_reporting": "social_benefits",
    "jobcenter": "social_benefits",
    "insurance": "health_insurance",
    "healthcare": "health_insurance",
    "freelance": "self_employment",
    "self_employed": "self_employment",
    "business_registration": "self_employment",
    "visa": "residence_status",
    "residence_permit": "residence_status",
    "temporary_protection": "asylum_or_temporary_protection",
    "asylum": "asylum_or_temporary_protection",
    "work_permit": "work_authorization",
    "employment": "work_authorization",
    "authority": "authority_procedure",
    "deadline": "deadline_or_proof",
    "proof": "deadline_or_proof",
    "travel": "travel_cross_border",
    "criminal": "criminal_or_fraud_risk",
    "fraud": "criminal_or_fraud_risk",
}
DEFAULT_CLUSTERING_POLICY = {
    "clustering_policy_version": CLUSTERING_POLICY_VERSION,
    "question_similarity_threshold": 0.82,
    "answer_similarity_threshold": 0.86,
    "qa_pair_similarity_threshold": 0.84,
    "top_k": 20,
    "max_component_size": 50,
    "topic_overlap_required": True,
    "law_overlap_required": False,
    "answer_conflict_similarity_ceiling": 0.72,
    "answer_changed_similarity_floor": 0.72,
    "stable_cluster_min_answer_count": 1,
    "auto_select_allowed_answer_statuses": ["strong", "partial"],
    "auto_select_allowed_link_confidences": ["high", "medium"],
    "auto_select_excluded_answer_priorities": ["low"],
}
ALLOWED_LLM_STATUSES = {"completed", "failed", "skipped"}
ALLOWED_LLM_TASK_SCOPES = {"candidate", "qa_cluster"}
ALLOWED_LLM_RECOMMENDATIONS = {"needs_llm_review", "needs_manual_review", "uncertain", "rejected"}
ALLOWED_REVIEW_DECISIONS = {"approve", "reject", "merge", "split", "needs_more_context", "uncertain"}
HUMAN_REVIEW_DECISION_SCOPE = "question_dataset_inclusion"
REFERENCE_ANSWER_ROLE = "community_answer_for_graph_db_comparison_not_legal_truth"
REFERENCE_ANSWER_ACTIONS = {"keep_selected", "replace_manual", "needs_manual_answer"}
LLM_REQUIRED_OUTPUT_FIELDS = (
    "is_real_user_question",
    "current_topic_relevance",
    "answer_candidate_quality",
    "normalized_question",
    "short_answer_summary",
    "drift_or_conflict_assessment",
    "recommended_selection_status",
    "needs_human_review",
)
LLM_OPTIONAL_OUTPUT_DEFAULTS: dict[str, Any] = {
    "question_intent": "unclassified",
    "legal_answer_requirement": "unclassified",
    "graph_db_evaluation_fit": "unclassified",
    "issue_spotting_required": False,
    "issue_spotting_level": "unclassified",
    "issue_spotting_confidence": "unclassified",
    "issue_spotting_reason": "",
    "hidden_legal_issue_categories": [],
    "answer_must_expand_beyond_user_wording": False,
    "exclusion_reason": "none",
}
LlmTransport = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class BotCatalogEntry:
    name: str
    usernames: tuple[str, ...]
    city: str
    scope_type: str
    responsible_usernames: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True, slots=True)
class TelegramMessage:
    export_id: str
    message_id: str
    date: str
    author_hash: str
    text: str
    text_redacted: str
    reply_to_message_id: str = ""
    bot_mentions: tuple[str, ...] = ()
    author_bot_kind: str = "none"
    author_bot_usernames: tuple[str, ...] = ()


@dataclass(slots=True)
class TgQaExtractionResult:
    candidates: list[dict[str, Any]]
    summary: dict[str, Any]
    embedding_batch_items: list[dict[str, Any]] = field(default_factory=list)
    llm_batch_items: list[dict[str, Any]] = field(default_factory=list)


def extract_tg_qa_dataset(
    *,
    input_paths: list[str | Path],
    bot_catalog_path: str | Path | None = None,
    output_path: str | Path | None = None,
    summary_output_path: str | Path | None = None,
    embedding_batch_output_path: str | Path | None = None,
    llm_batch_output_path: str | Path | None = None,
    max_messages_per_export: int = 0,
    max_candidates: int = 500,
    candidate_offset: int = 0,
    min_attention_score: int = 6,
) -> TgQaExtractionResult:
    export_paths = resolve_export_paths(input_paths)
    bot_catalog = load_bot_catalog(bot_catalog_path) if bot_catalog_path else []
    messages_by_export: dict[str, list[TelegramMessage]] = {}
    processed_message_count = 0
    raw_text_message_count = 0
    for export_path in export_paths:
        export_id = export_path.parent.name
        raw_messages = _load_export_messages(export_path, limit=max_messages_per_export)
        processed_message_count += len(raw_messages)
        normalized = [
            message
            for raw in raw_messages
            if (message := _normalize_message(raw, export_id=export_id, bot_catalog=bot_catalog)) is not None
        ]
        raw_text_message_count += len(normalized)
        messages_by_export[export_id] = normalized
    candidates: list[dict[str, Any]] = []
    for export_path in export_paths:
        export_id = export_path.parent.name
        candidates.extend(
            _extract_candidates_for_export(
                export_id=export_id,
                messages=messages_by_export.get(export_id, []),
                min_attention_score=min_attention_score,
            )
        )
    candidates = _deduplicate_candidates(candidates)
    candidate_pool_count = len(candidates)
    sorted_candidates = sorted(candidates, key=_candidate_sort_key)
    start = max(0, candidate_offset)
    stop = start + max_candidates if max_candidates > 0 else None
    candidates = sorted_candidates[start:stop]
    orphan_trigger_chain_summary = _orphan_trigger_chain_summary(messages_by_export, candidates)
    embedding_batch_items = [
        item
        for candidate in candidates
        for item in _embedding_batch_items(candidate)
    ]
    llm_batch_items = [_llm_batch_item(candidate) for candidate in candidates]
    summary = _build_summary(
        export_paths=export_paths,
        bot_catalog_path=bot_catalog_path,
        processed_message_count=processed_message_count,
        text_message_count=raw_text_message_count,
        candidates=candidates,
        output_path=output_path,
        summary_output_path=summary_output_path,
        embedding_batch_output_path=embedding_batch_output_path,
        llm_batch_output_path=llm_batch_output_path,
        orphan_trigger_chain_summary=orphan_trigger_chain_summary,
        candidate_pool_count=candidate_pool_count,
        candidate_offset=start,
        max_candidates=max_candidates,
    )
    if output_path:
        _write_jsonl(output_path, candidates)
    if summary_output_path:
        _write_json(summary_output_path, summary)
    if embedding_batch_output_path:
        _write_jsonl(embedding_batch_output_path, embedding_batch_items)
    if llm_batch_output_path:
        _write_jsonl(llm_batch_output_path, llm_batch_items)
    return TgQaExtractionResult(
        candidates=candidates,
        summary=summary,
        embedding_batch_items=embedding_batch_items,
        llm_batch_items=llm_batch_items,
    )


def resolve_export_paths(input_paths: list[str | Path]) -> list[Path]:
    resolved: list[Path] = []
    for raw_path in input_paths:
        path = Path(raw_path)
        if path.is_file() and path.name == "result.json":
            resolved.append(path)
            continue
        if path.is_dir() and (path / "result.json").exists():
            resolved.append(path / "result.json")
            continue
        if path.is_dir():
            resolved.extend(sorted(path.glob("**/result.json")))
    unique = sorted({path.resolve(): path for path in resolved}.values())
    if not unique:
        raise ValueError("no Telegram result.json exports found")
    return unique


def load_bot_catalog(path: str | Path | None) -> list[BotCatalogEntry]:
    if not path:
        return []
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = []
    for item in payload.get("bots", []) if isinstance(payload, Mapping) else []:
        if not isinstance(item, Mapping):
            continue
        usernames = tuple(str(username).lower() for username in item.get("usernames", []) if username)
        entries.append(
            BotCatalogEntry(
                name=str(item.get("name", "")),
                usernames=usernames,
                city=str(item.get("city", "")),
                scope_type=str(item.get("scope_type", "")),
                responsible_usernames=tuple(
                    str(username) for username in item.get("responsible_usernames", []) if username
                ),
                notes=str(item.get("notes", "")),
            )
        )
    return entries


def normalize_telegram_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, Mapping):
                parts.append(str(item.get("text", "")))
        return _clean_text("".join(parts))
    return _clean_text(str(value))


def redact_text(text: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    redacted = text
    for pattern, replacement, flag in (
        (URL_RE, "[URL]", "url_redacted"),
        (EMAIL_RE, "[EMAIL]", "email_redacted"),
        (PHONE_RE, "[PHONE]", "phone_redacted"),
        (USERNAME_RE, "[USERNAME]", "username_redacted"),
    ):
        redacted, count = pattern.subn(replacement, redacted)
        if count:
            flags.append(flag)
    return _clean_text(redacted), sorted(set(flags)) or ["none"]


def _load_export_messages(path: Path, *, limit: int) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    messages = payload.get("messages", []) if isinstance(payload, Mapping) else []
    messages = [item for item in messages if isinstance(item, dict)]
    return messages[:limit] if limit > 0 else messages


def _normalize_message(
    raw: Mapping[str, Any],
    *,
    export_id: str,
    bot_catalog: list[BotCatalogEntry],
) -> TelegramMessage | None:
    if raw.get("type") != "message":
        return None
    text = normalize_telegram_text(raw.get("text", ""))
    if not text:
        return None
    text_redacted, _flags = redact_text(text)
    author = str(raw.get("from_id") or raw.get("from") or raw.get("actor") or "unknown")
    bot_mentions = _detect_bot_mentions(text, bot_catalog)
    author_bot_usernames = _detect_known_bot_author(raw, bot_catalog)
    author_bot_kind = "known_wiki_bot" if author_bot_usernames else _detect_other_bot_author(raw)
    return TelegramMessage(
        export_id=export_id,
        message_id=str(raw.get("id", "")),
        date=str(raw.get("date", "")),
        author_hash=_stable_hash(f"tg-author:{author}"),
        text=text,
        text_redacted=text_redacted,
        reply_to_message_id=str(raw.get("reply_to_message_id") or ""),
        bot_mentions=tuple(bot_mentions),
        author_bot_kind=author_bot_kind,
        author_bot_usernames=tuple(author_bot_usernames),
    )


def _extract_candidates_for_export(
    *,
    export_id: str,
    messages: list[TelegramMessage],
    min_attention_score: int,
) -> list[dict[str, Any]]:
    replies_by_parent: dict[str, list[TelegramMessage]] = defaultdict(list)
    for message in messages:
        if message.reply_to_message_id:
            replies_by_parent[message.reply_to_message_id].append(message)
    message_index_by_id = {message.message_id: index for index, message in enumerate(messages)}
    candidates = []
    for message in messages:
        topic_labels, law_codes, topic_score = _topic_signals(message.text)
        is_question = _is_question(message.text)
        replies = sorted(replies_by_parent.get(message.message_id, []), key=lambda item: (item.date, item.message_id))
        attention_score = _attention_score(
            message=message,
            is_question=is_question,
            topic_score=topic_score,
            reply_count=len(replies),
        )
        if not is_question or attention_score < min_attention_score:
            continue
        redaction_flags = redact_text(message.text)[1]
        answer_candidates, trigger_evidence = _collect_answer_candidates(
            export_id=export_id,
            question=message,
            messages=messages,
            message_index_by_id=message_index_by_id,
            replies_by_parent=replies_by_parent,
        )
        answer_source_counts = _answer_source_counts(answer_candidates)
        source_message_ids = [
            message.message_id,
            *[str(trigger["trigger_message_id"]) for trigger in trigger_evidence],
            *[str(answer["message_id"]) for answer in answer_candidates],
        ]
        answer_status = _answer_candidate_status(answer_candidates)
        confidence_tier = _confidence_tier(
            attention_score=attention_score,
            topic_score=topic_score,
            answer_status=answer_status,
            answer_source_counts=answer_source_counts,
            bot_mentions=message.bot_mentions,
        )
        selection_status = _initial_selection_status(
            confidence_tier=confidence_tier,
            answer_status=answer_status,
        )
        review_route = _review_route(
            confidence_tier=confidence_tier,
            selection_status=selection_status,
            answer_status=answer_status,
            answer_source_counts=answer_source_counts,
        )
        candidate = {
            "candidate_id": _candidate_id(export_id, message.message_id, message.text),
            "export_id": export_id,
            "pipeline_stage": "candidate_extraction",
            "question_message_id": message.message_id,
            "question_reply_to_message_id": message.reply_to_message_id,
            "question_is_reply": bool(message.reply_to_message_id),
            "question_date": message.date,
            "author_hash": message.author_hash,
            "question_text_redacted": message.text_redacted,
            "is_question": is_question,
            "attention_score": attention_score,
            "topic_relevance_score": topic_score,
            "topic_labels": topic_labels,
            "law_code_candidates": law_codes,
            "bot_mentions": list(message.bot_mentions),
            "reply_count": len(replies),
            "answer_candidate_status": answer_status,
            "answer_candidates": answer_candidates,
            "trigger_evidence": trigger_evidence,
            "trigger_evidence_count": len(trigger_evidence),
            "answer_link_counts": _answer_link_counts(answer_candidates),
            "answer_source_counts": answer_source_counts,
            "known_wiki_bot_answer_candidate_count": answer_source_counts.get("known_wiki_bot", 0),
            "other_bot_answer_candidate_count": answer_source_counts.get("other_bot", 0),
            "known_bot_answer_via_trigger_count": _known_bot_answer_via_trigger_count(answer_candidates),
            "trigger_linking_policy": _trigger_linking_policy(),
            "bot_answer_marking_policy": BOT_ANSWER_MARKING_POLICY,
            "source_message_ids": source_message_ids,
            "pii_redaction_status": redaction_flags,
            "confidence_tier": confidence_tier,
            "selection_policy": SELECTION_POLICY,
            "selection_status": selection_status,
            "review_route": review_route,
            "embedding_processing_status": "not_run",
            "clustering_status": "not_run",
            "question_cluster_id": "",
            "answer_cluster_id": "",
            "qa_cluster_id": "",
            "selected_answer_candidate_id": "",
            "selected_answer_date": "",
            "historical_answer_variant_count": 0,
            "answer_drift_status": "not_evaluated",
            "review_status": "pending",
            "llm_processing_status": "not_run",
            "quality_flags": _quality_flags(
                topic_labels=topic_labels,
                answer_status=answer_status,
                answer_source_counts=answer_source_counts,
                bot_mentions=message.bot_mentions,
            ),
        }
        candidates.append(candidate)
    return candidates


def _collect_answer_candidates(
    *,
    export_id: str,
    question: TelegramMessage,
    messages: list[TelegramMessage],
    message_index_by_id: Mapping[str, int],
    replies_by_parent: Mapping[str, list[TelegramMessage]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    answer_candidates: list[dict[str, Any]] = []
    trigger_evidence_by_id: dict[str, dict[str, Any]] = {}
    seen_answer_message_ids: set[str] = set()

    def add_answer(
        answer: TelegramMessage,
        *,
        answer_link_type: str,
        link_confidence: str,
        trigger: TelegramMessage | None = None,
    ) -> None:
        if answer.message_id in seen_answer_message_ids:
            return
        payload = _answer_payload(
            answer,
            export_id=export_id,
            answer_link_type=answer_link_type,
            link_confidence=link_confidence,
            trigger=trigger,
            question=question,
        )
        answer_candidates.append(payload)
        seen_answer_message_ids.add(answer.message_id)

    def add_trigger(
        trigger: TelegramMessage,
        *,
        trigger_link_type: str,
        link_confidence: str,
        linked_bot_message_id: str = "",
    ) -> None:
        current = trigger_evidence_by_id.get(trigger.message_id)
        if current is not None and current["link_confidence"] == "high":
            return
        trigger_evidence_by_id[trigger.message_id] = _trigger_evidence_payload(
            trigger,
            question=question,
            trigger_link_type=trigger_link_type,
            link_confidence=link_confidence,
            linked_bot_message_id=linked_bot_message_id,
        )

    direct_replies = sorted(
        replies_by_parent.get(question.message_id, []),
        key=lambda item: (item.date, item.message_id),
    )
    for reply in direct_replies:
        bot_replies_to_trigger = [
            child
            for child in sorted(replies_by_parent.get(reply.message_id, []), key=lambda item: (item.date, item.message_id))
            if child.author_bot_kind == "known_wiki_bot"
        ]
        if _is_trigger_message(reply) and bot_replies_to_trigger:
            for bot_reply in bot_replies_to_trigger:
                add_trigger(
                    reply,
                    trigger_link_type="direct_reply_trigger",
                    link_confidence="high",
                    linked_bot_message_id=bot_reply.message_id,
                )
                add_answer(
                    bot_reply,
                    answer_link_type="bot_reply_to_trigger",
                    link_confidence="high",
                    trigger=reply,
                )
            continue
        add_answer(reply, answer_link_type="direct_reply_to_question", link_confidence="high")

    question_index = message_index_by_id.get(question.message_id)
    question_timestamp = _message_timestamp(question)
    if question_index is not None and question_timestamp is not None:
        upper_index = min(len(messages), question_index + QUESTION_TRIGGER_WINDOW_MESSAGES + 1)
        for trigger in messages[question_index + 1 : upper_index]:
            if trigger.message_id == question.message_id:
                continue
            if trigger.author_bot_kind == "known_wiki_bot":
                continue
            if _is_question(trigger.text) and trigger.message_id != question.message_id:
                break
            if not _is_trigger_message(trigger):
                continue
            if trigger.reply_to_message_id and trigger.reply_to_message_id != question.message_id:
                continue
            question_to_trigger_seconds = _seconds_between(question, trigger)
            if question_to_trigger_seconds is None or question_to_trigger_seconds > QUESTION_TRIGGER_WINDOW_SECONDS:
                continue
            linked_bot_answers = _known_bot_answers_for_trigger(
                trigger=trigger,
                messages=messages,
                message_index_by_id=message_index_by_id,
                replies_by_parent=replies_by_parent,
            )
            for bot_answer, answer_link_type in linked_bot_answers:
                add_trigger(
                    trigger,
                    trigger_link_type="nearby_trigger",
                    link_confidence="medium",
                    linked_bot_message_id=bot_answer.message_id,
                )
                add_answer(
                    bot_answer,
                    answer_link_type=answer_link_type,
                    link_confidence="medium",
                    trigger=trigger,
                )

    return (
        answer_candidates[:MAX_ANSWER_CANDIDATES_PER_QUESTION],
        sorted(trigger_evidence_by_id.values(), key=lambda item: (item["trigger_date"], item["trigger_message_id"])),
    )


def _answer_payload(
    message: TelegramMessage,
    *,
    export_id: str,
    answer_link_type: str,
    link_confidence: str,
    trigger: TelegramMessage | None = None,
    question: TelegramMessage | None = None,
) -> dict[str, Any]:
    if message.author_bot_kind == "known_wiki_bot":
        answer_source_type = "known_wiki_bot"
        answer_source_markers = ["known_wiki_bot_answer"]
        answer_candidate_priority = "normal"
        marking_reason = "known_wiki_bot_author_match"
    elif message.author_bot_kind == "other_bot":
        answer_source_type = "other_bot"
        answer_source_markers = ["other_bot_answer"]
        answer_candidate_priority = "low"
        marking_reason = "bot_like_author_outside_known_catalog"
    else:
        answer_source_type = "human_reply"
        answer_source_markers = ["human_reply"]
        answer_candidate_priority = "normal"
        marking_reason = ""
    if answer_link_type in {"bot_reply_to_trigger", "bot_after_trigger"}:
        answer_source_markers = sorted(set(answer_source_markers) | {"via_trigger"})
    answer_candidate_status = _single_answer_candidate_status(message.text_redacted)
    return {
        "answer_candidate_id": _answer_candidate_id(export_id, message.message_id, message.text),
        "message_id": message.message_id,
        "date": message.date,
        "author_hash": message.author_hash,
        "text_redacted": message.text_redacted,
        "answer_candidate_status": answer_candidate_status,
        "answer_candidate_usable": (
            answer_candidate_status in {"strong", "partial"}
            and answer_candidate_priority != "low"
            and link_confidence in {"high", "medium"}
        ),
        "bot_mentions": list(message.bot_mentions),
        "answer_source_type": answer_source_type,
        "answer_source_markers": answer_source_markers,
        "answer_candidate_priority": answer_candidate_priority,
        "author_bot_kind": message.author_bot_kind,
        "known_bot_usernames": list(message.author_bot_usernames),
        "marking_reason": marking_reason,
        "answer_link_type": answer_link_type,
        "link_confidence": link_confidence,
        "trigger_message_id": trigger.message_id if trigger else "",
        "trigger_author_hash": trigger.author_hash if trigger else "",
        "trigger_date": trigger.date if trigger else "",
        "question_to_trigger_seconds": _seconds_between(question, trigger) if question and trigger else None,
        "trigger_to_bot_seconds": _seconds_between(trigger, message) if trigger else None,
        "pii_redaction_status": redact_text(message.text)[1],
    }


def _is_question(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in QUESTION_MARKERS)


def _is_trigger_message(message: TelegramMessage) -> bool:
    if message.author_bot_kind != "none":
        return False
    text = message.text.strip()
    if not text or _is_question(text):
        return False
    words = [word for word in text.split() if word]
    return len(text) <= TRIGGER_TEXT_MAX_CHARS and len(words) <= TRIGGER_TEXT_MAX_WORDS


def _known_bot_answers_for_trigger(
    *,
    trigger: TelegramMessage,
    messages: list[TelegramMessage],
    message_index_by_id: Mapping[str, int],
    replies_by_parent: Mapping[str, list[TelegramMessage]],
) -> list[tuple[TelegramMessage, str]]:
    answers: list[tuple[TelegramMessage, str]] = []
    seen: set[str] = set()
    for reply in sorted(replies_by_parent.get(trigger.message_id, []), key=lambda item: (item.date, item.message_id)):
        if reply.author_bot_kind == "known_wiki_bot":
            answers.append((reply, "bot_reply_to_trigger"))
            seen.add(reply.message_id)

    trigger_index = message_index_by_id.get(trigger.message_id)
    if trigger_index is None:
        return answers
    for message in messages[trigger_index + 1 : trigger_index + QUESTION_TRIGGER_WINDOW_MESSAGES + 1]:
        if message.message_id in seen:
            continue
        if message.author_bot_kind != "known_wiki_bot":
            if _is_question(message.text) or _is_trigger_message(message):
                break
            continue
        trigger_to_bot_seconds = _seconds_between(trigger, message)
        if trigger_to_bot_seconds is None:
            continue
        if trigger_to_bot_seconds > TRIGGER_BOT_WINDOW_SECONDS:
            break
        if message.reply_to_message_id and message.reply_to_message_id != trigger.message_id:
            continue
        answers.append((message, "bot_after_trigger"))
        seen.add(message.message_id)
    return answers


def _orphan_trigger_chain_summary(
    messages_by_export: Mapping[str, list[TelegramMessage]],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    linked_trigger_ids = {
        (str(candidate.get("export_id", "")), str(trigger.get("trigger_message_id", "")))
        for candidate in candidates
        for trigger in candidate.get("trigger_evidence", [])
        if isinstance(trigger, Mapping)
    }
    linked_bot_answer_ids = {
        (str(candidate.get("export_id", "")), str(answer.get("message_id", "")))
        for candidate in candidates
        for answer in candidate.get("answer_candidates", [])
        if isinstance(answer, Mapping)
        and answer.get("answer_source_type") == "known_wiki_bot"
        and answer.get("answer_link_type") in {"bot_reply_to_trigger", "bot_after_trigger"}
    }
    orphan_triggers: set[tuple[str, str]] = set()
    orphan_bot_answers: set[tuple[str, str]] = set()
    samples: list[dict[str, Any]] = []
    for export_id, messages in messages_by_export.items():
        replies_by_parent: dict[str, list[TelegramMessage]] = defaultdict(list)
        message_index_by_id = {message.message_id: index for index, message in enumerate(messages)}
        for message in messages:
            if message.reply_to_message_id:
                replies_by_parent[message.reply_to_message_id].append(message)
        for message in messages:
            if not _is_trigger_message(message):
                continue
            answers = _known_bot_answers_for_trigger(
                trigger=message,
                messages=messages,
                message_index_by_id=message_index_by_id,
                replies_by_parent=replies_by_parent,
            )
            if not answers:
                continue
            trigger_key = (export_id, message.message_id)
            answer_keys = {(export_id, answer.message_id) for answer, _link_type in answers}
            if trigger_key in linked_trigger_ids and answer_keys & linked_bot_answer_ids:
                continue
            orphan_triggers.add(trigger_key)
            orphan_bot_answers.update(answer_keys - linked_bot_answer_ids)
            if len(samples) < 10:
                samples.append(
                    {
                        "export_id": export_id,
                        "trigger_message_id": message.message_id,
                        "trigger_date": message.date,
                        "linked_bot_message_ids": sorted(answer_id for _export_id, answer_id in answer_keys),
                        "reason": "known_wiki_bot_trigger_chain_not_linked_to_emitted_question_candidate",
                    }
                )
    return {
        "orphan_trigger_chain_count": len(orphan_triggers),
        "orphan_trigger_message_count": len(orphan_triggers),
        "orphan_known_bot_answer_count": len(orphan_bot_answers),
        "samples": samples,
    }


def _trigger_evidence_payload(
    trigger: TelegramMessage,
    *,
    question: TelegramMessage,
    trigger_link_type: str,
    link_confidence: str,
    linked_bot_message_id: str,
) -> dict[str, Any]:
    return {
        "trigger_message_id": trigger.message_id,
        "trigger_date": trigger.date,
        "trigger_author_hash": trigger.author_hash,
        "trigger_text_redacted": trigger.text_redacted,
        "trigger_link_type": trigger_link_type,
        "link_confidence": link_confidence,
        "linked_bot_message_id": linked_bot_message_id,
        "question_to_trigger_seconds": _seconds_between(question, trigger),
        "pii_redaction_status": redact_text(trigger.text)[1],
    }


def _topic_signals(text: str) -> tuple[list[str], list[str], int]:
    lowered = text.lower()
    topic_labels = [
        label
        for label, keywords in TOPIC_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ]
    law_codes = [
        law_code
        for law_code, keywords in LAW_CODE_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ]
    score = min(6, len(topic_labels) * 2 + len(law_codes))
    return sorted(topic_labels), sorted(law_codes), score


def _attention_score(
    *,
    message: TelegramMessage,
    is_question: bool,
    topic_score: int,
    reply_count: int,
) -> int:
    score = 0
    if is_question:
        score += 4
    if "?" in message.text:
        score += 2
    text_length = len(message.text)
    if 40 <= text_length <= 1500:
        score += 1
    score += topic_score
    if message.bot_mentions:
        score += 3
    score += min(3, reply_count)
    return score


def _answer_candidate_status(answer_candidates: list[dict[str, Any]]) -> str:
    if not answer_candidates:
        return "no_answer"
    if any(len(item.get("text_redacted", "")) >= 80 for item in answer_candidates):
        return "strong"
    return "partial"


def _single_answer_candidate_status(text: str) -> str:
    if not text:
        return "no_answer"
    if len(text) >= 80:
        return "strong"
    return "partial"


def _answer_source_counts(answer_candidates: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item.get("answer_source_type", "unknown")) for item in answer_candidates)
    return dict(sorted(counts.items()))


def _answer_link_counts(answer_candidates: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item.get("answer_link_type", "unknown")) for item in answer_candidates)
    return dict(sorted(counts.items()))


def _known_bot_answer_via_trigger_count(answer_candidates: list[dict[str, Any]]) -> int:
    return sum(
        1
        for item in answer_candidates
        if item.get("answer_source_type") == "known_wiki_bot"
        and item.get("answer_link_type") in {"bot_reply_to_trigger", "bot_after_trigger"}
    )


def _trigger_linking_policy() -> dict[str, Any]:
    return {
        "question_trigger_window_messages": QUESTION_TRIGGER_WINDOW_MESSAGES,
        "question_trigger_window_seconds": QUESTION_TRIGGER_WINDOW_SECONDS,
        "trigger_bot_window_seconds": TRIGGER_BOT_WINDOW_SECONDS,
        "trigger_text_max_chars": TRIGGER_TEXT_MAX_CHARS,
        "trigger_text_max_words": TRIGGER_TEXT_MAX_WORDS,
    }


def _confidence_tier(
    *,
    attention_score: int,
    topic_score: int,
    answer_status: str,
    answer_source_counts: Mapping[str, int],
    bot_mentions: tuple[str, ...],
) -> str:
    if answer_status == "strong" and topic_score >= 3 and attention_score >= 10:
        return "high"
    if answer_status in {"strong", "partial"} and attention_score >= 7 and (topic_score > 0 or bot_mentions):
        return "medium"
    if answer_source_counts.get("known_wiki_bot", 0) and attention_score >= 7:
        return "medium"
    if answer_status != "no_answer" or topic_score > 0 or bot_mentions:
        return "low"
    return "low"


def _initial_selection_status(*, confidence_tier: str, answer_status: str) -> str:
    if answer_status == "no_answer":
        return "uncertain"
    if confidence_tier in {"high", "medium"}:
        return "pending_embedding_cluster"
    return "needs_manual_review"


def _review_route(
    *,
    confidence_tier: str,
    selection_status: str,
    answer_status: str,
    answer_source_counts: Mapping[str, int],
) -> str:
    if selection_status == "pending_embedding_cluster" and answer_status == "no_answer":
        return "embedding_cluster_then_llm_review"
    if (
        selection_status == "pending_embedding_cluster"
        and answer_source_counts.get("known_wiki_bot", 0)
        and answer_source_counts.get("human_reply", 0) == 0
    ):
        return "embedding_cluster_then_llm_review"
    if selection_status == "pending_embedding_cluster" and confidence_tier == "high":
        return "embedding_cluster_selection"
    if selection_status == "pending_embedding_cluster":
        return "embedding_cluster_then_llm_review"
    if selection_status == "uncertain":
        return "manual_or_uncertain"
    return "manual_review"


def _quality_flags(
    *,
    topic_labels: list[str],
    answer_status: str,
    answer_source_counts: Mapping[str, int],
    bot_mentions: tuple[str, ...],
) -> list[str]:
    flags = []
    if not topic_labels:
        flags.append("low_topic_relevance")
    if answer_status == "no_answer":
        flags.append("missing_answer_candidate")
    if answer_source_counts.get("known_wiki_bot", 0):
        flags.append("known_bot_answer_marked")
    if answer_source_counts.get("other_bot", 0):
        flags.append("other_bot_answer_marked_low_priority")
    if bot_mentions:
        flags.append("bot_mention_context")
    return flags or ["none"]


def _detect_bot_mentions(text: str, bot_catalog: list[BotCatalogEntry]) -> list[str]:
    lowered = text.lower()
    mentions = []
    for entry in bot_catalog:
        for username in entry.usernames:
            if username and username.lower() in lowered:
                mentions.append(username)
    return sorted(set(mentions))


def _detect_known_bot_author(raw: Mapping[str, Any], bot_catalog: list[BotCatalogEntry]) -> list[str]:
    raw_values = [
        str(raw.get("from", "") or ""),
        str(raw.get("from_id", "") or ""),
        str(raw.get("actor", "") or ""),
    ]
    normalized_values = {_normalize_author_identity(value) for value in raw_values if value}
    combined = " ".join(sorted(normalized_values))
    matches: list[str] = []
    for entry in bot_catalog:
        entry_name = _normalize_author_identity(entry.name)
        name_matched = entry_name and entry_name in normalized_values
        username_matched = any(
            username and (
                _normalize_author_identity(username) in normalized_values
                or _normalize_author_identity(username).lstrip("@") in combined
            )
            for username in entry.usernames
        )
        if name_matched or username_matched:
            matches.extend(entry.usernames)
    return sorted(set(matches))


def _detect_other_bot_author(raw: Mapping[str, Any]) -> str:
    raw_values = [
        str(raw.get("from", "") or ""),
        str(raw.get("from_id", "") or ""),
        str(raw.get("actor", "") or ""),
    ]
    combined = " ".join(_normalize_author_identity(value) for value in raw_values if value)
    if "bot" in combined or "бот" in combined:
        return "other_bot"
    return "none"


def _normalize_author_identity(value: str) -> str:
    return SPACE_RE.sub(" ", value.lower()).strip()


def _message_timestamp(message: TelegramMessage | None) -> datetime | None:
    if message is None or not message.date:
        return None
    try:
        return datetime.fromisoformat(message.date.replace("Z", "+00:00"))
    except ValueError:
        return None


def _seconds_between(start: TelegramMessage | None, end: TelegramMessage | None) -> int | None:
    start_timestamp = _message_timestamp(start)
    end_timestamp = _message_timestamp(end)
    if start_timestamp is None or end_timestamp is None:
        return None
    return int((end_timestamp - start_timestamp).total_seconds())


def _deduplicate_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        key = _dedupe_key(str(candidate.get("question_text_redacted", "")))
        current = by_key.get(key)
        if current is None or _candidate_sort_key(candidate) < _candidate_sort_key(current):
            by_key[key] = candidate
    return list(by_key.values())


def _candidate_sort_key(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        -int(candidate.get("attention_score", 0) or 0),
        -int(candidate.get("topic_relevance_score", 0) or 0),
        str(candidate.get("export_id", "")),
        str(candidate.get("question_message_id", "")),
    )


def _dedupe_key(text: str) -> str:
    normalized = re.sub(r"[^a-zа-яё0-9 ]+", " ", text.lower(), flags=re.IGNORECASE)
    normalized = SPACE_RE.sub(" ", normalized).strip()
    return _stable_hash(normalized)


def _candidate_id(export_id: str, message_id: str, text: str) -> str:
    return f"tg-qa-candidate:{_stable_hash(f'{export_id}:{message_id}:{text}')}"


def _answer_candidate_id(export_id: str, message_id: str, text: str) -> str:
    return f"tg-answer-candidate:{_stable_hash(f'{export_id}:{message_id}:{text}')}"


def _embedding_batch_items(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidate_id = str(candidate.get("candidate_id", ""))
    items = [
        {
            "embedding_item_id": f"tg-embedding:{_stable_hash(candidate_id + ':question')}",
            "candidate_id": candidate_id,
            "source_message_id": str(candidate.get("question_message_id", "")),
            "text_role": "question",
            "date": str(candidate.get("question_date", "")),
            "embedding_prefix": QUESTION_EMBEDDING_PREFIX.strip(),
            "embedding_input_text": QUESTION_EMBEDDING_PREFIX + str(candidate.get("question_text_redacted", "")),
            "cluster_usage": ["question_cluster", "qa_cluster"],
            "selection_policy": SELECTION_POLICY,
        }
    ]
    for answer in candidate.get("answer_candidates", []):
        if not isinstance(answer, Mapping):
            continue
        answer_id = str(answer.get("answer_candidate_id", ""))
        text = str(answer.get("text_redacted", ""))
        if not text:
            continue
        items.append(
            {
                "embedding_item_id": f"tg-embedding:{_stable_hash(candidate_id + ':' + answer_id)}",
                "candidate_id": candidate_id,
                "answer_candidate_id": answer_id,
                "source_message_id": str(answer.get("message_id", "")),
                "text_role": "answer",
                "answer_source_type": str(answer.get("answer_source_type", "")),
                "answer_link_type": str(answer.get("answer_link_type", "")),
                "link_confidence": str(answer.get("link_confidence", "")),
                "trigger_message_id": str(answer.get("trigger_message_id", "")),
                "date": str(answer.get("date", "")),
                "embedding_prefix": ANSWER_EMBEDDING_PREFIX.strip(),
                "embedding_input_text": ANSWER_EMBEDDING_PREFIX + text,
                "cluster_usage": ["answer_cluster", "qa_cluster", "temporal_answer_selection"],
                "selection_policy": SELECTION_POLICY,
            }
        )
        question_text = str(candidate.get("question_text_redacted", ""))
        if question_text:
            items.append(
                {
                    "embedding_item_id": f"tg-embedding:{_stable_hash(candidate_id + ':' + answer_id + ':qa_pair')}",
                    "candidate_id": candidate_id,
                    "answer_candidate_id": answer_id,
                    "source_message_id": str(answer.get("message_id", "")),
                    "source_message_ids": [
                        str(candidate.get("question_message_id", "")),
                        str(answer.get("message_id", "")),
                    ],
                    "text_role": "qa_pair",
                    "answer_source_type": str(answer.get("answer_source_type", "")),
                    "answer_link_type": str(answer.get("answer_link_type", "")),
                    "link_confidence": str(answer.get("link_confidence", "")),
                    "trigger_message_id": str(answer.get("trigger_message_id", "")),
                    "date": str(answer.get("date", "")),
                    "embedding_prefix": ANSWER_EMBEDDING_PREFIX.strip(),
                    "embedding_input_text": (
                        ANSWER_EMBEDDING_PREFIX
                        + "Question: "
                        + question_text
                        + "\nAnswer: "
                        + text
                    ),
                    "cluster_usage": ["qa_cluster"],
                    "selection_policy": SELECTION_POLICY,
                }
            )
    return items


def _llm_batch_item(candidate: Mapping[str, Any]) -> dict[str, Any]:
    prompt_profile = _active_tg_qa_prompt_profile(LLM_CANDIDATE_PROMPT_VERSION)
    return {
        "task_id": candidate["candidate_id"],
        "task_type": "tg_qa_candidate_classification",
        "task_scope": "candidate",
        "runtime_hint": "operator_managed_llama_server_openai_compatible",
        "llm_contract_version": "tg_qa_llm_analysis_v1",
        "prompt_version": LLM_CANDIDATE_PROMPT_VERSION,
        "system_instruction": str(prompt_profile["system_instruction"]),
        "input": {
            "question_text_redacted": candidate.get("question_text_redacted", ""),
            "answer_candidates": candidate.get("answer_candidates", []),
            "trigger_evidence": candidate.get("trigger_evidence", []),
            "answer_link_counts": candidate.get("answer_link_counts", {}),
            "answer_source_counts": candidate.get("answer_source_counts", {}),
            "known_wiki_bot_answer_candidate_count": candidate.get("known_wiki_bot_answer_candidate_count", 0),
            "other_bot_answer_candidate_count": candidate.get("other_bot_answer_candidate_count", 0),
            "known_bot_answer_via_trigger_count": candidate.get("known_bot_answer_via_trigger_count", 0),
            "topic_labels": candidate.get("topic_labels", []),
            "law_code_candidates": candidate.get("law_code_candidates", []),
            "bot_mentions": candidate.get("bot_mentions", []),
            "confidence_tier": candidate.get("confidence_tier", ""),
            "selection_status": candidate.get("selection_status", ""),
            "review_route": candidate.get("review_route", ""),
            "answer_drift_status": candidate.get("answer_drift_status", ""),
        },
        "expected_output_schema": _llm_expected_output_schema(),
    }


def _build_summary(
    *,
    export_paths: list[Path],
    bot_catalog_path: str | Path | None,
    processed_message_count: int,
    text_message_count: int,
    candidates: list[dict[str, Any]],
    output_path: str | Path | None,
    summary_output_path: str | Path | None,
    embedding_batch_output_path: str | Path | None,
    llm_batch_output_path: str | Path | None,
    orphan_trigger_chain_summary: Mapping[str, Any],
    candidate_pool_count: int,
    candidate_offset: int,
    max_candidates: int,
) -> dict[str, Any]:
    status_counts = Counter(str(candidate.get("answer_candidate_status", "")) for candidate in candidates)
    confidence_counts = Counter(str(candidate.get("confidence_tier", "")) for candidate in candidates)
    selection_counts = Counter(str(candidate.get("selection_status", "")) for candidate in candidates)
    route_counts = Counter(str(candidate.get("review_route", "")) for candidate in candidates)
    topic_counts = Counter(
        label for candidate in candidates for label in candidate.get("topic_labels", [])
    )
    law_counts = Counter(
        law_code for candidate in candidates for law_code in candidate.get("law_code_candidates", [])
    )
    bot_mention_count = sum(1 for candidate in candidates if candidate.get("bot_mentions"))
    answer_source_counts = Counter(
        str(answer.get("answer_source_type", "unknown"))
        for candidate in candidates
        for answer in candidate.get("answer_candidates", [])
        if isinstance(answer, Mapping)
    )
    answer_link_counts = Counter(
        str(answer.get("answer_link_type", "unknown"))
        for candidate in candidates
        for answer in candidate.get("answer_candidates", [])
        if isinstance(answer, Mapping)
    )
    answer_candidate_count = sum(len(candidate.get("answer_candidates", [])) for candidate in candidates)
    trigger_evidence_count = sum(len(candidate.get("trigger_evidence", [])) for candidate in candidates)
    known_wiki_bot_answer_count = answer_source_counts.get("known_wiki_bot", 0)
    other_bot_answer_count = answer_source_counts.get("other_bot", 0)
    known_bot_answer_via_trigger_count = sum(
        int(candidate.get("known_bot_answer_via_trigger_count", 0) or 0)
        for candidate in candidates
    )
    return {
        "artifact_type": "tg_qa_extraction_summary",
        "generated_at": _utc_timestamp(),
        "input_exports": [str(path) for path in export_paths],
        "bot_catalog_path": str(bot_catalog_path or ""),
        "processed_message_count": processed_message_count,
        "text_message_count": text_message_count,
        "candidate_pool_count": candidate_pool_count,
        "candidate_offset": candidate_offset,
        "max_candidates": max_candidates,
        "question_candidate_count": len(candidates),
        "emitted_candidate_count": len(candidates),
        "counts_by_answer_candidate_status": dict(sorted(status_counts.items())),
        "counts_by_confidence_tier": dict(sorted(confidence_counts.items())),
        "counts_by_selection_status": dict(sorted(selection_counts.items())),
        "counts_by_review_route": dict(sorted(route_counts.items())),
        "counts_by_topic_label": dict(sorted(topic_counts.items())),
        "counts_by_law_code_candidate": dict(sorted(law_counts.items())),
        "bot_mention_candidate_count": bot_mention_count,
        "answer_candidate_count": answer_candidate_count,
        "answer_source_counts": dict(sorted(answer_source_counts.items())),
        "answer_link_counts": dict(sorted(answer_link_counts.items())),
        "trigger_evidence_count": trigger_evidence_count,
        "known_wiki_bot_answer_candidate_count": known_wiki_bot_answer_count,
        "other_bot_answer_candidate_count": other_bot_answer_count,
        "known_bot_answer_via_trigger_count": known_bot_answer_via_trigger_count,
        "orphan_trigger_chain_count": orphan_trigger_chain_summary.get("orphan_trigger_chain_count", 0),
        "orphan_trigger_message_count": orphan_trigger_chain_summary.get("orphan_trigger_message_count", 0),
        "orphan_known_bot_answer_count": orphan_trigger_chain_summary.get("orphan_known_bot_answer_count", 0),
        "orphan_trigger_chain_samples": orphan_trigger_chain_summary.get("samples", []),
        "trigger_linking_policy": _trigger_linking_policy(),
        "bot_answer_marking_policy": BOT_ANSWER_MARKING_POLICY,
        "candidate_output_path": str(output_path or ""),
        "summary_output_path": str(summary_output_path or ""),
        "embedding_batch_output_path": str(embedding_batch_output_path or ""),
        "llm_batch_output_path": str(llm_batch_output_path or ""),
        "trust_boundary": "telegram_answers_are_evaluation_material_not_legal_truth",
        "selection_policy": SELECTION_POLICY,
        "embedding_processing_status": "not_run",
        "clustering_status": "not_run",
        "llm_processing_status": "not_run",
    }


def import_tg_qa_embedding_records(
    *,
    embedding_batch_path: str | Path,
    external_vectors_path: str | Path,
    output_path: str | Path | None = None,
    summary_output_path: str | Path | None = None,
    profile_metadata: Mapping[str, Any] | EmbeddingProfile | None = None,
) -> dict[str, Any]:
    """Import external vector records while preserving the project embedding profile."""

    batch_items = _read_jsonl(embedding_batch_path)
    external_items = _read_jsonl(external_vectors_path)
    profile = _embedding_profile_from_metadata(profile_metadata)
    external_by_key = {
        _embedding_external_key(item): item
        for item in external_items
        if isinstance(item, Mapping)
    }
    records: list[dict[str, Any]] = []
    counts = Counter()
    for item in batch_items:
        if not isinstance(item, Mapping):
            continue
        raw_vector_record = external_by_key.get(_embedding_external_key(item))
        record = _embedding_record_from_external_item(
            batch_item=item,
            raw_vector_record=raw_vector_record,
            profile=profile,
        )
        records.append(record)
        counts[str(record["embedding_status"])] += 1
    summary = {
        "artifact_type": "tg_qa_embedding_import_summary",
        "generated_at": _utc_timestamp(),
        "embedding_batch_path": str(embedding_batch_path),
        "external_vectors_path": str(external_vectors_path),
        "embedding_records_path": str(output_path or ""),
        "summary_output_path": str(summary_output_path or ""),
        "processed_count": len(batch_items),
        "completed_count": counts.get("completed", 0),
        "failed_count": counts.get("failed", 0),
        "counts_by_text_role": dict(
            sorted(Counter(str(record.get("text_role", "")) for record in records).items())
        ),
        "counts_by_embedding_status": dict(sorted(counts.items())),
        "embedding_profile": profile.as_record(),
        "trust_boundary": "embedding_records_are_evaluation_artifacts_not_graph_writes",
    }
    if output_path:
        _write_jsonl(output_path, records)
    if summary_output_path:
        _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def vectorize_tg_qa_embedding_batch(
    *,
    embedding_batch_path: str | Path,
    output_path: str | Path | None = None,
    summary_output_path: str | Path | None = None,
    endpoint_url: str,
    model_id: str,
    batch_size: int = 16,
    timeout_seconds: int = 60,
    transport: Any = None,
    progress: bool = False,
) -> dict[str, Any]:
    """Vectorize a 006 embedding batch against an OpenAI-compatible endpoint."""

    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    started_at = _utc_timestamp()
    started = perf_counter()
    batch_items = [item for item in _read_jsonl(embedding_batch_path) if isinstance(item, Mapping)]
    client = EmbeddingEndpointClient(
        endpoint_url,
        model_id=model_id,
        timeout_seconds=timeout_seconds,
        transport=transport,
    )
    vector_records: list[dict[str, Any]] = []
    counts = Counter()
    progress_line = _ProgressLine(enabled=progress, label="tg-qa-embed-batch", total=len(batch_items))
    processed_count = 0
    for chunk_index, chunk in enumerate(_chunks(batch_items, batch_size), start=1):
        progress_line.update(
            processed_count,
            completed=counts.get("completed", 0),
            failed=counts.get("failed", 0),
            detail=f"chunk {chunk_index}/{(len(batch_items) + batch_size - 1) // batch_size}",
        )
        inputs = [str(item.get("embedding_input_text", "")) for item in chunk]
        try:
            vectors = client.embed(inputs)
        except Exception as exc:
            failure_reason = str(exc)
            for item in chunk:
                vector_records.append(_external_vector_record(item, vector=[], failure_reason=failure_reason))
                counts["failed"] += 1
            processed_count += len(chunk)
            progress_line.update(
                processed_count,
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                detail=f"chunk {chunk_index} failed",
            )
            continue
        for item, vector in zip(chunk, vectors, strict=True):
            vector_records.append(_external_vector_record(item, vector=vector, failure_reason=""))
            counts["completed"] += 1
        processed_count += len(chunk)
        progress_line.update(
            processed_count,
            completed=counts.get("completed", 0),
            failed=counts.get("failed", 0),
            detail=f"chunk {chunk_index} done",
        )
    progress_line.finish(
        processed_count,
        completed=counts.get("completed", 0),
        failed=counts.get("failed", 0),
    )
    duration_seconds = round(perf_counter() - started, 3)
    summary = {
        "artifact_type": "tg_qa_embedding_batch_vectorization_summary",
        "generated_at": _utc_timestamp(),
        "started_at": started_at,
        "completed_at": _utc_timestamp(),
        "duration_seconds": duration_seconds,
        "items_per_second": round(len(batch_items) / duration_seconds, 3) if duration_seconds else 0,
        "embedding_batch_path": str(embedding_batch_path),
        "external_vectors_path": str(output_path or ""),
        "summary_output_path": str(summary_output_path or ""),
        "endpoint_shape": _redacted_endpoint_shape(endpoint_url),
        "model_id": model_id,
        "batch_size": batch_size,
        "batch_count": (len(batch_items) + batch_size - 1) // batch_size,
        "timeout_seconds": timeout_seconds,
        "processed_count": len(batch_items),
        "completed_count": counts.get("completed", 0),
        "failed_count": counts.get("failed", 0),
        "counts_by_text_role": dict(
            sorted(Counter(str(item.get("text_role", "")) for item in batch_items).items())
        ),
        "embedding_input_text_stats": _text_length_stats(
            str(item.get("embedding_input_text", "")) for item in batch_items
        ),
        "trust_boundary": "embedding_vectors_are_generated_evaluation_artifacts_not_trusted_legal_facts",
    }
    if output_path:
        _write_jsonl(output_path, vector_records)
    if summary_output_path:
        _write_json(summary_output_path, summary)
    return {"vectors": vector_records, "summary": summary}


def run_tg_qa_similarity(
    *,
    embedding_records_path: str | Path,
    output_path: str | Path | None = None,
    summary_output_path: str | Path | None = None,
    clustering_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    records = [
        item
        for item in _read_jsonl(embedding_records_path)
        if isinstance(item, Mapping) and item.get("embedding_status") == "completed"
    ]
    policy = _clustering_policy(clustering_policy)
    neighbors: list[dict[str, Any]] = []
    records_by_space: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        role = str(record.get("text_role", ""))
        if role in {"question", "answer", "qa_pair"}:
            records_by_space[role].append(record)
    for space, space_records in sorted(records_by_space.items()):
        threshold = _threshold_for_space(space, policy)
        for source in sorted(space_records, key=lambda item: str(item.get("embedding_item_id", ""))):
            scored: list[tuple[float, Mapping[str, Any]]] = []
            for neighbor in space_records:
                if neighbor.get("embedding_item_id") == source.get("embedding_item_id"):
                    continue
                score = _cosine_similarity(source.get("vector", []), neighbor.get("vector", []))
                if score >= threshold:
                    scored.append((score, neighbor))
            scored.sort(key=lambda item: (-item[0], str(item[1].get("embedding_item_id", ""))))
            for rank, (score, neighbor) in enumerate(scored[: int(policy["top_k"])], start=1):
                neighbors.append(
                    {
                        "source_embedding_item_id": str(source.get("embedding_item_id", "")),
                        "neighbor_embedding_item_id": str(neighbor.get("embedding_item_id", "")),
                        "candidate_id": str(source.get("candidate_id", "")),
                        "neighbor_candidate_id": str(neighbor.get("candidate_id", "")),
                        "answer_candidate_id": str(source.get("answer_candidate_id", "")),
                        "neighbor_answer_candidate_id": str(neighbor.get("answer_candidate_id", "")),
                        "similarity_space": space,
                        "similarity_score": round(score, 6),
                        "rank": rank,
                        "threshold": threshold,
                        "threshold_version": str(policy["clustering_policy_version"]),
                        "embedding_profile_id": str(source.get("embedding_profile_id", "")),
                        "index_implementation": "in_memory_cosine_index",
                    }
                )
    summary = {
        "artifact_type": "tg_qa_similarity_summary",
        "generated_at": _utc_timestamp(),
        "embedding_records_path": str(embedding_records_path),
        "neighbors_path": str(output_path or ""),
        "summary_output_path": str(summary_output_path or ""),
        "processed_embedding_count": len(records),
        "neighbor_count": len(neighbors),
        "neighbor_count_by_space": dict(
            sorted(Counter(str(item["similarity_space"]) for item in neighbors).items())
        ),
        "embedding_profile_ids": sorted(
            {str(record.get("embedding_profile_id", "")) for record in records if record.get("embedding_profile_id")}
        ),
        "clustering_policy": policy,
        "index_implementation": "in_memory_cosine_index",
        "approval_side_effect": "none_similarity_does_not_merge_or_approve",
    }
    if output_path:
        _write_jsonl(output_path, neighbors)
    if summary_output_path:
        _write_json(summary_output_path, summary)
    return {"neighbors": neighbors, "summary": summary}


def cluster_tg_qa_candidates(
    *,
    candidates_path: str | Path,
    neighbors_path: str | Path,
    question_clusters_output_path: str | Path | None = None,
    answer_clusters_output_path: str | Path | None = None,
    qa_clusters_output_path: str | Path | None = None,
    summary_output_path: str | Path | None = None,
    clustering_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    candidates = [item for item in _read_jsonl(candidates_path) if isinstance(item, Mapping)]
    neighbors = [item for item in _read_jsonl(neighbors_path) if isinstance(item, Mapping)]
    policy = _clustering_policy(clustering_policy)
    candidate_ids = [str(candidate.get("candidate_id", "")) for candidate in candidates]
    candidate_by_id = {str(candidate.get("candidate_id", "")): candidate for candidate in candidates}
    answer_owner = _answer_owner_map(candidates)

    question_union = _UnionFind(candidate_ids)
    answer_union = _UnionFind(answer_owner.keys())
    qa_union = _UnionFind(candidate_ids)
    for neighbor in neighbors:
        space = str(neighbor.get("similarity_space", ""))
        source_candidate_id = str(neighbor.get("candidate_id", ""))
        neighbor_candidate_id = str(neighbor.get("neighbor_candidate_id", ""))
        if space == "question":
            question_union.union(source_candidate_id, neighbor_candidate_id)
            if _cluster_metadata_compatible(candidate_by_id, source_candidate_id, neighbor_candidate_id, policy):
                qa_union.union(source_candidate_id, neighbor_candidate_id)
        elif space == "answer":
            answer_id = str(neighbor.get("answer_candidate_id", ""))
            neighbor_answer_id = str(neighbor.get("neighbor_answer_candidate_id", ""))
            answer_union.union(answer_id, neighbor_answer_id)
            source_owner = answer_owner.get(answer_id, "")
            neighbor_owner = answer_owner.get(neighbor_answer_id, "")
            if _cluster_metadata_compatible(candidate_by_id, source_owner, neighbor_owner, policy):
                qa_union.union(source_owner, neighbor_owner)
        elif space == "qa_pair":
            if _cluster_metadata_compatible(candidate_by_id, source_candidate_id, neighbor_candidate_id, policy):
                qa_union.union(source_candidate_id, neighbor_candidate_id)

    question_clusters = _cluster_records_from_components(
        components=question_union.components(),
        cluster_type="question",
        candidates_by_id=candidate_by_id,
        answer_owner=answer_owner,
        policy=policy,
    )
    answer_clusters = _cluster_records_from_components(
        components=answer_union.components(),
        cluster_type="answer",
        candidates_by_id=candidate_by_id,
        answer_owner=answer_owner,
        policy=policy,
    )
    qa_clusters = _cluster_records_from_components(
        components=qa_union.components(),
        cluster_type="qa_pair",
        candidates_by_id=candidate_by_id,
        answer_owner=answer_owner,
        policy=policy,
    )
    answer_cluster_by_answer_id = {
        answer_id: cluster["cluster_id"]
        for cluster in answer_clusters
        for answer_id in cluster.get("answer_candidate_ids", [])
    }
    for cluster in qa_clusters:
        cluster["answer_cluster_ids"] = sorted(
            {
                answer_cluster_by_answer_id.get(answer_id, "")
                for answer_id in cluster.get("answer_candidate_ids", [])
                if answer_cluster_by_answer_id.get(answer_id, "")
            }
        )
        cluster["combination_policy"] = (
            "question_answer_qa_pair_similarity_with_topic_law_source_link_metadata"
        )
    summary = {
        "artifact_type": "tg_qa_clustering_summary",
        "generated_at": _utc_timestamp(),
        "candidates_path": str(candidates_path),
        "neighbors_path": str(neighbors_path),
        "question_clusters_path": str(question_clusters_output_path or ""),
        "answer_clusters_path": str(answer_clusters_output_path or ""),
        "qa_clusters_path": str(qa_clusters_output_path or ""),
        "summary_output_path": str(summary_output_path or ""),
        "question_cluster_count": len(question_clusters),
        "answer_cluster_count": len(answer_clusters),
        "qa_cluster_count": len(qa_clusters),
        "max_component_size": policy["max_component_size"],
        "clustering_policy": policy,
    }
    if question_clusters_output_path:
        _write_jsonl(question_clusters_output_path, question_clusters)
    if answer_clusters_output_path:
        _write_jsonl(answer_clusters_output_path, answer_clusters)
    if qa_clusters_output_path:
        _write_jsonl(qa_clusters_output_path, qa_clusters)
    if summary_output_path:
        _write_json(summary_output_path, summary)
    return {
        "question_clusters": question_clusters,
        "answer_clusters": answer_clusters,
        "qa_clusters": qa_clusters,
        "summary": summary,
    }


def select_tg_qa_clusters(
    *,
    candidates_path: str | Path,
    qa_clusters_path: str | Path,
    answer_clusters_path: str | Path | None = None,
    output_path: str | Path | None = None,
    summary_output_path: str | Path | None = None,
    clustering_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    candidates = [item for item in _read_jsonl(candidates_path) if isinstance(item, Mapping)]
    qa_clusters = [item for item in _read_jsonl(qa_clusters_path) if isinstance(item, Mapping)]
    answer_clusters = (
        [item for item in _read_jsonl(answer_clusters_path) if isinstance(item, Mapping)]
        if answer_clusters_path
        else []
    )
    policy = _clustering_policy(clustering_policy)
    candidate_by_id = {str(candidate.get("candidate_id", "")): candidate for candidate in candidates}
    answer_cluster_by_answer_id = {
        str(answer_id): str(cluster.get("cluster_id", ""))
        for cluster in answer_clusters
        for answer_id in cluster.get("answer_candidate_ids", [])
    }
    selections: list[dict[str, Any]] = []
    for cluster in qa_clusters:
        candidate_ids = [str(item) for item in cluster.get("candidate_ids", [])]
        usable = [
            _answer_variant_payload(candidate, answer, answer_cluster_by_answer_id)
            for candidate_id in candidate_ids
            if (candidate := candidate_by_id.get(candidate_id)) is not None
            for answer in candidate.get("answer_candidates", [])
            if isinstance(answer, Mapping) and _is_usable_answer_candidate(answer, policy)
        ]
        usable.sort(key=lambda item: (_date_sort_value(str(item["answer_date"])), str(item["answer_candidate_id"])), reverse=True)
        selected = usable[0] if usable else {}
        historical = usable[1:]
        drift_status = _answer_drift_status(usable, answer_cluster_by_answer_id, policy)
        selected_candidate = candidate_by_id.get(str(selected.get("candidate_id", "")), {}) if selected else {}
        selection_status = _cluster_selection_status(
            selected_candidate=selected_candidate,
            usable_answers=usable,
            drift_status=drift_status,
        )
        selection = {
            "qa_cluster_id": str(cluster.get("cluster_id", "")),
            "selection_status": selection_status,
            "selected_candidate_id": str(selected.get("candidate_id", "")),
            "selected_answer_candidate_id": str(selected.get("answer_candidate_id", "")),
            "selected_answer_date": str(selected.get("answer_date", "")),
            "historical_answer_variants": historical,
            "historical_answer_variant_count": len(historical),
            "answer_drift_status": drift_status,
            "selection_reasons": _selection_reasons(selection_status, drift_status, usable),
            "review_route": _selection_review_route(selection_status, drift_status),
            "candidate_ids": candidate_ids,
            "answer_candidate_ids": list(cluster.get("answer_candidate_ids", [])),
            "cluster_quality_flags": list(cluster.get("cluster_quality_flags", [])),
            "clustering_policy_version": str(policy["clustering_policy_version"]),
        }
        selections.append(selection)
    summary = {
        "artifact_type": "tg_qa_cluster_selection_summary",
        "generated_at": _utc_timestamp(),
        "candidates_path": str(candidates_path),
        "qa_clusters_path": str(qa_clusters_path),
        "answer_clusters_path": str(answer_clusters_path or ""),
        "selection_path": str(output_path or ""),
        "summary_output_path": str(summary_output_path or ""),
        "selection_count": len(selections),
        "counts_by_selection_status": dict(
            sorted(Counter(str(item["selection_status"]) for item in selections).items())
        ),
        "counts_by_answer_drift_status": dict(
            sorted(Counter(str(item["answer_drift_status"]) for item in selections).items())
        ),
        "clustering_policy": policy,
    }
    if output_path:
        _write_jsonl(output_path, selections)
    if summary_output_path:
        _write_json(summary_output_path, summary)
    return {"selections": selections, "summary": summary}


def emit_tg_qa_cluster_llm_batch(
    *,
    candidates_path: str | Path,
    selection_path: str | Path,
    output_path: str | Path | None = None,
    prompt_profile: str = "full",
    input_char_budget: int = 0,
    overflow_output_path: str | Path | None = None,
    skip_over_budget: bool = False,
    manual_review_path: str | Path | None = None,
) -> dict[str, Any]:
    if prompt_profile not in {"full", "compact"}:
        raise ValueError("prompt_profile must be full or compact")
    candidates = [item for item in _read_jsonl(candidates_path) if isinstance(item, Mapping)]
    selections = [item for item in _read_jsonl(selection_path) if isinstance(item, Mapping)]
    manual_overlays = _manual_review_overlays_by_cluster(manual_review_path) if manual_review_path else {}
    candidate_by_id = {str(candidate.get("candidate_id", "")): candidate for candidate in candidates}
    batch_items: list[dict[str, Any]] = []
    overflow_items: list[dict[str, Any]] = []
    skipped_items: list[dict[str, Any]] = []
    for selection in selections:
        if not _selection_needs_llm(selection):
            continue
        qa_cluster_id = str(selection.get("qa_cluster_id", ""))
        cluster_candidates = [
            candidate_by_id[candidate_id]
            for candidate_id in selection.get("candidate_ids", [])
            if candidate_id in candidate_by_id
        ]
        full_item = _cluster_llm_batch_item(
            qa_cluster_id=qa_cluster_id,
            selection=selection,
            candidates=cluster_candidates,
            prompt_profile="full",
            input_char_budget=0,
            manual_overlay=manual_overlays.get(qa_cluster_id, {}),
        )
        if input_char_budget > 0 and _serialized_input_chars(full_item) > input_char_budget:
            overflow_items.append(full_item)
        batch_item = (
            _cluster_llm_batch_item(
                qa_cluster_id=qa_cluster_id,
                selection=selection,
                candidates=cluster_candidates,
                prompt_profile="compact",
                input_char_budget=input_char_budget,
                manual_overlay=manual_overlays.get(qa_cluster_id, {}),
            )
            if prompt_profile == "compact"
            else full_item
        )
        if skip_over_budget and input_char_budget > 0 and _serialized_input_chars(batch_item) > input_char_budget:
            skipped_items.append(batch_item)
            continue
        batch_items.append(batch_item)
    summary = {
        "artifact_type": "tg_qa_cluster_llm_batch_summary",
        "generated_at": _utc_timestamp(),
        "selection_path": str(selection_path),
        "manual_review_overlay_path": str(manual_review_path or ""),
        "llm_batch_output_path": str(output_path or ""),
        "overflow_output_path": str(overflow_output_path or ""),
        "batch_item_count": len(batch_items),
        "overflow_item_count": len(overflow_items),
        "skipped_over_budget_count": len(skipped_items),
        "manual_review_overlay_count": sum(1 for item in batch_items if item.get("input", {}).get("review_overlay")),
        "prompt_profile": prompt_profile,
        "input_char_budget": input_char_budget,
        "llm_contract_version": LLM_CONTRACT_VERSION,
        "prompt_version": (
            LLM_CLUSTER_COMPACT_PROMPT_VERSION if prompt_profile == "compact" else LLM_CLUSTER_PROMPT_VERSION
        ),
        "input_text_stats": _text_length_stats(
            json.dumps(item.get("input", {}), ensure_ascii=False, sort_keys=True) for item in batch_items
        ),
        "overflow_policy": (
            "full_items_whose_full_input_exceeds_input_char_budget"
            if overflow_output_path and input_char_budget > 0
            else "not_requested"
        ),
    }
    if output_path:
        _write_jsonl(output_path, batch_items)
    if overflow_output_path:
        _write_jsonl(overflow_output_path, overflow_items)
    return {"batch_items": batch_items, "summary": summary}


def run_tg_qa_llm_batch(
    *,
    batch_path: str | Path,
    output_path: str | Path | None = None,
    summary_output_path: str | Path | None = None,
    endpoint_url: str,
    model_id: str,
    llm_run_id: str,
    max_items: int = 0,
    timeout_seconds: int = 120,
    max_tokens: int = 512,
    response_format_json: bool = True,
    reasoning_effort: str = "",
    thinking_type: str = "",
    omit_temperature: bool = False,
    extra_body: Mapping[str, Any] | None = None,
    runtime_contour: str = "operator_managed_llama_server_openai_compatible",
    backend: str = "llama-server",
    model_file: str = "",
    quantization: str = "",
    api_key_env: str = "",
    http_user_agent: str = "chat_bot2-evaluation-runner/006",
    transport: LlmTransport | None = None,
    progress: bool = False,
) -> dict[str, Any]:
    if not endpoint_url:
        raise ValueError("endpoint_url is required")
    if not model_id:
        raise ValueError("model_id is required")
    if not llm_run_id:
        raise ValueError("llm_run_id is required")
    batch_items = [item for item in _read_jsonl(batch_path) if isinstance(item, Mapping)]
    selected_items = batch_items[:max_items] if max_items > 0 else batch_items
    started_at = _utc_timestamp()
    started = perf_counter()
    chat_url = _chat_completion_url(endpoint_url)
    api_key = _api_key_from_env(api_key_env)
    client = transport or _openai_chat_completion_transport(
        chat_url,
        timeout_seconds=timeout_seconds,
        api_key=api_key,
        user_agent=http_user_agent,
    )
    result_records: list[dict[str, Any]] = []
    counts = Counter()
    progress_line = _ProgressLine(enabled=progress, label="tg-qa-llm-run", total=len(selected_items))
    output_handle = _open_jsonl_stream(output_path) if output_path else None
    try:
        for item_index, task in enumerate(selected_items, start=1):
            progress_line.update(
                item_index - 1,
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                detail=f"request {item_index}/{len(selected_items)}",
            )
            counts["processed"] += 1
            payload = _llm_chat_payload(
                task,
                model_id=model_id,
                max_tokens=max_tokens,
                response_format_json=response_format_json,
                reasoning_effort=reasoning_effort,
                thinking_type=thinking_type,
                omit_temperature=omit_temperature,
                extra_body=extra_body,
            )
            try:
                response = client(payload)
                raw_text = _llm_response_text(response)
                parsed, parse_error = _extract_first_json_object(raw_text)
                if parse_error:
                    failure_reason = parse_error + ":" + _llm_response_diagnostics(response)
                    record = _failed_llm_result_record(
                        task,
                        llm_run_id=llm_run_id,
                        failure_reason=failure_reason,
                        runtime_contour=runtime_contour,
                        backend=backend,
                        model_file=model_file or model_id,
                        model_id=model_id,
                        quantization=quantization,
                    )
                else:
                    record = _llm_result_record_from_model_output(
                        task,
                        parsed,
                        llm_run_id=llm_run_id,
                        runtime_contour=runtime_contour,
                        backend=backend,
                        model_file=model_file or model_id,
                        model_id=model_id,
                        quantization=quantization,
                    )
            except Exception as exc:  # pragma: no cover - network failures are environment-dependent
                record = _failed_llm_result_record(
                    task,
                    llm_run_id=llm_run_id,
                    failure_reason=_llm_endpoint_error_reason(exc),
                    runtime_contour=runtime_contour,
                    backend=backend,
                    model_file=model_file or model_id,
                    model_id=model_id,
                    quantization=quantization,
                )
            counts[str(record.get("status", "failed"))] += 1
            result_records.append(record)
            _write_jsonl_stream_record(output_handle, record)
            progress_line.update(
                item_index,
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                detail=f"last={record.get('status', '')}",
            )
    finally:
        if output_handle:
            output_handle.close()
        progress_line.finish(
            counts.get("processed", 0),
            completed=counts.get("completed", 0),
            failed=counts.get("failed", 0),
        )
    completed_at = _utc_timestamp()
    duration = perf_counter() - started
    summary = {
        "artifact_type": "tg_qa_llm_batch_run_summary",
        "generated_at": completed_at,
        "input_batch_path": str(batch_path),
        "result_output_path": str(output_path or ""),
        "summary_output_path": str(summary_output_path or ""),
        "endpoint_shape": _redacted_endpoint_shape(chat_url),
        "runtime_contour": runtime_contour,
        "backend": backend,
        "model_file": model_file or model_id,
        "model_id": model_id,
        "quantization": quantization,
        "api_key_env": api_key_env,
        "auth_mode": "bearer_env" if api_key_env else "none",
        "http_user_agent": http_user_agent,
        "llm_run_id": llm_run_id,
        "response_format_json": response_format_json,
        "reasoning_effort": reasoning_effort,
        "thinking_type": thinking_type,
        "omit_temperature": omit_temperature,
        "extra_body_keys": sorted(extra_body.keys()) if isinstance(extra_body, Mapping) else [],
        "max_tokens": max_tokens,
        "timeout_seconds": timeout_seconds,
        "requested_item_count": len(selected_items),
        "available_batch_item_count": len(batch_items),
        "completed_count": counts.get("completed", 0),
        "failed_count": counts.get("failed", 0),
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": round(duration, 3),
        "items_per_second": round(len(selected_items) / duration, 3) if duration > 0 else 0,
        "trust_boundary": "llm_results_are_review_evidence_only",
    }
    if summary_output_path:
        _write_json(summary_output_path, summary)
    return {"results": result_records, "summary": summary}


def import_tg_qa_llm_results(
    *,
    batch_path: str | Path,
    result_path: str | Path,
    evidence_output_path: str | Path | None = None,
    manifest_output_path: str | Path | None = None,
    llm_run_id: str = "",
    runtime_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    batch_items = [item for item in _read_jsonl(batch_path) if isinstance(item, Mapping)]
    tasks_by_id = {str(item.get("task_id", "")): item for item in batch_items}
    evidence_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    counts = Counter()
    json_valid_count = 0
    schema_valid_count = 0
    seen_task_ids: set[str] = set()
    for line_number, payload, error in _read_jsonl_tolerant(result_path):
        counts["processed"] += 1
        if error:
            counts["failed"] += 1
            continue
        json_valid_count += 1
        assert payload is not None
        evidence, failure_reason = _validate_llm_result(payload, tasks_by_id, default_run_id=llm_run_id)
        if failure_reason:
            counts["failed"] += 1
            evidence = {
                "task_id": str(payload.get("task_id", f"invalid-line:{line_number}")),
                "task_scope": str(payload.get("task_scope", "")),
                "llm_run_id": str(payload.get("llm_run_id", llm_run_id)),
                "status": "failed",
                "failure_reason": failure_reason,
                "review_evidence_type": "llm_analysis_import_failure",
            }
        else:
            schema_valid_count += 1
            seen_task_ids.add(str(evidence["task_id"]))
            counts[str(evidence["status"])] += 1
        key = (
            str(evidence.get("llm_run_id", "")),
            str(evidence.get("task_scope", "")),
            str(evidence.get("task_id", "")),
        )
        if key in evidence_by_key:
            counts["duplicate_result"] += 1
        evidence_by_key[key] = evidence
    evidence_records = sorted(
        evidence_by_key.values(),
        key=lambda item: (str(item.get("llm_run_id", "")), str(item.get("task_scope", "")), str(item.get("task_id", ""))),
    )
    unprocessed_count = len(set(tasks_by_id) - seen_task_ids)
    runtime = dict(runtime_metadata or {})
    completed_count = counts.get("completed", 0)
    manifest = {
        "artifact_type": "tg_qa_llm_run_manifest",
        "generated_at": _utc_timestamp(),
        "llm_run_id": llm_run_id or _first_non_empty([str(item.get("llm_run_id", "")) for item in evidence_records]),
        "input_batch_path": str(batch_path),
        "result_output_path": str(result_path),
        "evidence_output_path": str(evidence_output_path or ""),
        "runtime_contour": runtime.get("runtime_contour", "operator_managed_llama_server_openai_compatible"),
        "backend": runtime.get("backend", "llama-server"),
        "model_file": runtime.get("model_file", ""),
        "model_id": runtime.get("model_id", ""),
        "quantization": runtime.get("quantization", ""),
        "prompt_version": _first_non_empty([str(item.get("prompt_version", "")) for item in batch_items]),
        "llm_contract_version": _first_non_empty([str(item.get("llm_contract_version", "")) for item in batch_items]),
        "server_parameters": runtime.get("server_parameters", {}),
        "endpoint_shape": runtime.get("endpoint_shape", "redacted_openai_compatible_chat_completion"),
        "json_valid_result_count": json_valid_count,
        "schema_valid_result_count": schema_valid_count,
        "manual_spot_check_sample_size": min(20, completed_count),
        "manual_spot_check_outcome": runtime.get("manual_spot_check_outcome", "pending"),
        "processed_count": counts.get("processed", 0),
        "completed_count": completed_count,
        "failed_count": counts.get("failed", 0),
        "skipped_count": counts.get("skipped", 0),
        "unprocessed_count": unprocessed_count,
        "duplicate_result_count": counts.get("duplicate_result", 0),
        "started_at": runtime.get("started_at", ""),
        "completed_at": runtime.get("completed_at", _utc_timestamp()),
        "operator_notes_path": runtime.get("operator_notes_path", ""),
        "trust_boundary": "llm_results_are_review_evidence_only",
    }
    if evidence_output_path:
        _write_jsonl(evidence_output_path, evidence_records)
    if manifest_output_path:
        _write_json(manifest_output_path, manifest)
    return {"evidence": evidence_records, "manifest": manifest}


def filter_tg_qa_llm_batch_by_results(
    *,
    batch_path: str | Path,
    results_path: str | Path,
    output_path: str | Path | None = None,
    status: str = "failed",
) -> dict[str, Any]:
    batch_items = [item for item in _read_jsonl(batch_path) if isinstance(item, Mapping)]
    result_items = [item for item in _read_jsonl(results_path) if isinstance(item, Mapping)]
    selected_task_ids = {
        str(item.get("task_id", ""))
        for item in result_items
        if str(item.get("status", "")) == status and item.get("task_id")
    }
    filtered = [item for item in batch_items if str(item.get("task_id", "")) in selected_task_ids]
    summary = {
        "artifact_type": "tg_qa_llm_retry_batch_summary",
        "generated_at": _utc_timestamp(),
        "batch_path": str(batch_path),
        "results_path": str(results_path),
        "output_path": str(output_path or ""),
        "status_filter": status,
        "source_batch_item_count": len(batch_items),
        "source_result_item_count": len(result_items),
        "selected_task_count": len(selected_task_ids),
        "retry_batch_item_count": len(filtered),
    }
    if output_path:
        _write_jsonl(output_path, filtered)
    return {"batch_items": filtered, "summary": summary}


def merge_tg_qa_llm_results(
    *,
    primary_results_path: str | Path,
    retry_results_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    primary_results = [item for item in _read_jsonl(primary_results_path) if isinstance(item, Mapping)]
    retry_results = [item for item in _read_jsonl(retry_results_path) if isinstance(item, Mapping)]
    merged_by_task_id: dict[str, dict[str, Any]] = {
        str(item.get("task_id", "")): dict(item)
        for item in primary_results
        if item.get("task_id")
    }
    replaced_count = 0
    ignored_retry_count = 0
    for retry in retry_results:
        task_id = str(retry.get("task_id", ""))
        if not task_id:
            ignored_retry_count += 1
            continue
        current = merged_by_task_id.get(task_id)
        if current is None:
            merged_by_task_id[task_id] = dict(retry)
            replaced_count += 1
            continue
        if str(current.get("status", "")) != "completed" and str(retry.get("status", "")) == "completed":
            merged_by_task_id[task_id] = dict(retry)
            replaced_count += 1
        else:
            ignored_retry_count += 1
    primary_order = [str(item.get("task_id", "")) for item in primary_results if item.get("task_id")]
    extra_retry_order = [
        str(item.get("task_id", ""))
        for item in retry_results
        if item.get("task_id") and str(item.get("task_id", "")) not in set(primary_order)
    ]
    merged = [merged_by_task_id[task_id] for task_id in [*primary_order, *extra_retry_order] if task_id in merged_by_task_id]
    summary = {
        "artifact_type": "tg_qa_llm_merged_results_summary",
        "generated_at": _utc_timestamp(),
        "primary_results_path": str(primary_results_path),
        "retry_results_path": str(retry_results_path),
        "output_path": str(output_path or ""),
        "primary_result_count": len(primary_results),
        "retry_result_count": len(retry_results),
        "merged_result_count": len(merged),
        "replaced_count": replaced_count,
        "ignored_retry_count": ignored_retry_count,
        "counts_by_status": dict(sorted(Counter(str(item.get("status", "")) for item in merged).items())),
        "merge_policy": "retry_completed_replaces_primary_non_completed_by_task_id",
    }
    if output_path:
        _write_jsonl(output_path, merged)
    return {"results": merged, "summary": summary}


def build_tg_qa_manual_review_queue(
    *,
    candidates_path: str | Path,
    selection_path: str | Path,
    llm_evidence_path: str | Path | None = None,
    output_path: str | Path | None = None,
    summary_output_path: str | Path | None = None,
) -> dict[str, Any]:
    candidates = [item for item in _read_jsonl(candidates_path) if isinstance(item, Mapping)]
    selections = [item for item in _read_jsonl(selection_path) if isinstance(item, Mapping)]
    llm_evidence = (
        [item for item in _read_jsonl(llm_evidence_path) if isinstance(item, Mapping)]
        if llm_evidence_path
        else []
    )
    candidate_by_id = {str(candidate.get("candidate_id", "")): candidate for candidate in candidates}
    llm_by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for evidence in llm_evidence:
        qa_cluster_id = str(evidence.get("qa_cluster_id", ""))
        if qa_cluster_id:
            llm_by_cluster[qa_cluster_id].append(dict(evidence))
    queue: list[dict[str, Any]] = []
    for selection in selections:
        if not _selection_needs_manual_review(selection):
            continue
        qa_cluster_id = str(selection.get("qa_cluster_id", ""))
        selected_candidate = candidate_by_id.get(str(selection.get("selected_candidate_id", "")), {})
        selected_answer = _find_answer_candidate(
            selected_candidate,
            str(selection.get("selected_answer_candidate_id", "")),
        )
        queue.append(
            {
                "review_queue_id": f"tg-review-queue:{_stable_hash(qa_cluster_id)}",
                "qa_cluster_id": qa_cluster_id,
                "selection_status": str(selection.get("selection_status", "")),
                "answer_drift_status": str(selection.get("answer_drift_status", "")),
                "redacted_question": str(selected_candidate.get("question_text_redacted", "")),
                "selected_answer_candidate": selected_answer,
                "historical_answer_variants": selection.get("historical_answer_variants", []),
                "trigger_evidence": selected_candidate.get("trigger_evidence", []),
                "candidate_ids": selection.get("candidate_ids", []),
                "similarity_evidence": {
                    "cluster_quality_flags": selection.get("cluster_quality_flags", []),
                    "selection_reasons": selection.get("selection_reasons", []),
                },
                "llm_notes": llm_by_cluster.get(qa_cluster_id, []),
                "allowed_decisions": sorted(ALLOWED_REVIEW_DECISIONS),
                "trust_boundary": "manual_review_decisions_are_evaluation_metadata_not_legal_truth",
            }
        )
    summary = {
        "artifact_type": "tg_qa_manual_review_queue_summary",
        "generated_at": _utc_timestamp(),
        "selection_path": str(selection_path),
        "llm_evidence_path": str(llm_evidence_path or ""),
        "review_queue_path": str(output_path or ""),
        "summary_output_path": str(summary_output_path or ""),
        "queue_count": len(queue),
        "counts_by_selection_status": dict(sorted(Counter(str(item["selection_status"]) for item in queue).items())),
        "counts_by_answer_drift_status": dict(sorted(Counter(str(item["answer_drift_status"]) for item in queue).items())),
    }
    if output_path:
        _write_jsonl(output_path, queue)
    if summary_output_path:
        _write_json(summary_output_path, summary)
    return {"queue": queue, "summary": summary}


def export_tg_qa_human_review(
    *,
    review_queue_path: str | Path,
    markdown_output_path: str | Path | None = None,
    tsv_output_path: str | Path | None = None,
    summary_output_path: str | Path | None = None,
    max_text_chars: int = 900,
) -> dict[str, Any]:
    queue = [item for item in _read_jsonl(review_queue_path) if isinstance(item, Mapping)]
    records = [_human_review_record(item, index=index, max_text_chars=max_text_chars) for index, item in enumerate(queue, start=1)]
    records.sort(key=lambda item: (-int(item["interest_score"]), str(item["bucket"]), int(item["source_index"])))
    for rank, record in enumerate(records, start=1):
        record["rank"] = rank
    summary = {
        "artifact_type": "tg_qa_human_review_export_summary",
        "generated_at": _utc_timestamp(),
        "review_queue_path": str(review_queue_path),
        "markdown_output_path": str(markdown_output_path or ""),
        "tsv_output_path": str(tsv_output_path or ""),
        "summary_output_path": str(summary_output_path or ""),
        "review_item_count": len(records),
        "decision_scope": HUMAN_REVIEW_DECISION_SCOPE,
        "reference_answer_role": REFERENCE_ANSWER_ROLE,
        "counts_by_bucket": dict(sorted(Counter(str(item["bucket"]) for item in records).items())),
        "counts_by_suggested_decision": dict(sorted(Counter(str(item["suggested_decision"]) for item in records).items())),
        "counts_by_reference_answer_status": dict(
            sorted(Counter(str(item["reference_answer_status"]) for item in records).items())
        ),
        "trust_boundary": "human_review_export_is_triage_metadata_not_approval",
    }
    if markdown_output_path:
        _write_markdown(markdown_output_path, _human_review_markdown(records, summary))
    if tsv_output_path:
        _write_text(tsv_output_path, _human_review_tsv(records))
    if summary_output_path:
        _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def _read_manual_review_decision_rows(decisions_path: str | Path) -> list[Mapping[str, Any]]:
    path = Path(decisions_path)
    if path.suffix.lower() == ".tsv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle, delimiter="\t")]
    return [item for item in _read_jsonl(path) if isinstance(item, Mapping)]


def _ensure_unique_manual_review_clusters(
    rows: Sequence[Mapping[str, Any]],
    *,
    purpose: str,
) -> None:
    duplicate_cluster_ids = sorted(
        cluster_id
        for cluster_id, count in Counter(
            str(item.get("qa_cluster_id", ""))
            for item in rows
            if str(item.get("qa_cluster_id", ""))
        ).items()
        if count > 1
    )
    if not duplicate_cluster_ids:
        return
    duplicate_preview = ", ".join(duplicate_cluster_ids[:5])
    extra_count = len(duplicate_cluster_ids) - min(len(duplicate_cluster_ids), 5)
    if extra_count > 0:
        duplicate_preview = f"{duplicate_preview}, ... (+{extra_count} more)"
    raise ValueError(
        f"Duplicate qa_cluster_id rows are not supported for {purpose}. "
        "Current 006 review import/build emits at most one final case per qa_cluster_id; "
        "do not duplicate TSV rows to emulate split. "
        f"Duplicate qa_cluster_id values: {duplicate_preview}"
    )


def _manual_review_overlays_by_cluster(manual_review_path: str | Path | None) -> dict[str, dict[str, Any]]:
    if not manual_review_path:
        return {}
    rows = _read_manual_review_decision_rows(manual_review_path)
    _ensure_unique_manual_review_clusters(rows, purpose="manual review overlay")
    overlays: dict[str, dict[str, Any]] = {}
    for item in rows:
        qa_cluster_id = str(item.get("qa_cluster_id", ""))
        if not qa_cluster_id:
            continue
        manual_question_raw = str(
            item.get("manual_question_text_redacted")
            or item.get("manual_question_text")
            or ""
        )
        manual_answer_raw = str(
            item.get("manual_reference_answer_text_redacted")
            or item.get("manual_reference_answer_text")
            or ""
        )
        question_redacted, _question_flags = redact_text(manual_question_raw) if manual_question_raw else ("", [])
        answer_redacted, _answer_flags = redact_text(manual_answer_raw) if manual_answer_raw else ("", [])
        overlay = {
            "purpose": (
                "manual_corrected_text_for_prompt_ab_test_only; "
                "do_not_use_any_prior_human_decision_as_label"
            ),
            "question_text_redacted": question_redacted
            or str(item.get("original_redacted_question", ""))
            or str(item.get("normalized_question", "")),
            "question_text_source": "manual_question_text" if question_redacted else "review_export_question_text",
            "reference_answer_text_redacted": answer_redacted or str(item.get("reference_answer", "")),
            "reference_answer_source": "manual_reference_answer_text" if answer_redacted else "review_export_reference_answer",
        }
        if overlay["question_text_redacted"] or overlay["reference_answer_text_redacted"]:
            overlays[qa_cluster_id] = overlay
    return overlays


def import_tg_qa_manual_review_decisions(
    *,
    review_queue_path: str | Path,
    decisions_path: str | Path,
    output_path: str | Path | None = None,
    summary_output_path: str | Path | None = None,
) -> dict[str, Any]:
    queue = [item for item in _read_jsonl(review_queue_path) if isinstance(item, Mapping)]
    raw_decisions = _read_manual_review_decision_rows(decisions_path)
    _ensure_unique_manual_review_clusters(raw_decisions, purpose="manual review import")
    known_clusters = {str(item.get("qa_cluster_id", "")) for item in queue}
    decisions: list[dict[str, Any]] = []
    counts = Counter()
    for item in raw_decisions:
        qa_cluster_id = str(item.get("qa_cluster_id", ""))
        decision = str(item.get("decision", ""))
        if qa_cluster_id not in known_clusters or decision not in ALLOWED_REVIEW_DECISIONS:
            counts["failed"] += 1
            continue
        manual_answer_raw = str(
            item.get("manual_reference_answer_text_redacted")
            or item.get("manual_reference_answer_text")
            or ""
        )
        manual_answer_redacted, manual_answer_flags = redact_text(manual_answer_raw) if manual_answer_raw else ("", [])
        manual_question_raw = str(
            item.get("manual_question_text_redacted")
            or item.get("manual_question_text")
            or ""
        )
        manual_question_redacted, manual_question_flags = (
            redact_text(manual_question_raw) if manual_question_raw else ("", [])
        )
        question_intent = _clean_text(str(item.get("question_intent", "")))
        legal_answer_requirement = _clean_text(str(item.get("legal_answer_requirement", "")))
        graph_db_evaluation_fit = _clean_text(str(item.get("graph_db_evaluation_fit", "")))
        issue_spotting_required = _parse_boolish(item.get("issue_spotting_required", ""))
        issue_spotting_level = _normalize_enum_value(
            item.get("issue_spotting_level", ""),
            allowed=ISSUE_SPOTTING_LEVELS,
            default="unclassified",
        )
        issue_spotting_confidence = _normalize_enum_value(
            item.get("issue_spotting_confidence", ""),
            allowed=ISSUE_SPOTTING_CONFIDENCE_LEVELS,
            default="unclassified",
        )
        issue_spotting_reason_raw = _clean_text(str(item.get("issue_spotting_reason", "")))
        issue_spotting_reason = redact_text(issue_spotting_reason_raw)[0] if issue_spotting_reason_raw else ""
        hidden_legal_issue_categories = _string_list(item.get("hidden_legal_issue_categories", ""))
        answer_must_expand_beyond_user_wording = _parse_boolish(item.get("answer_must_expand_beyond_user_wording", ""))
        exclusion_reason = _clean_text(str(item.get("exclusion_reason", ""))) or "none"
        requested_reference_answer_action = str(item.get("reference_answer_action", ""))
        reference_answer_action = requested_reference_answer_action
        if manual_answer_redacted:
            if reference_answer_action and reference_answer_action != "replace_manual":
                counts["manual_answer_overrode_reference_action"] += 1
            reference_answer_action = "replace_manual"
        elif not reference_answer_action:
            reference_answer_action = "keep_selected"
        if reference_answer_action not in REFERENCE_ANSWER_ACTIONS:
            counts["failed"] += 1
            continue
        if decision == "approve" and reference_answer_action == "replace_manual" and not manual_answer_redacted:
            counts["failed"] += 1
            counts["missing_manual_reference_answer"] += 1
            continue
        record = {
            "review_decision_id": str(item.get("review_decision_id", f"tg-review-decision:{_stable_hash(qa_cluster_id + decision)}")),
            "qa_cluster_id": qa_cluster_id,
            "decision": decision,
            "decision_scope": str(item.get("decision_scope", HUMAN_REVIEW_DECISION_SCOPE)),
            "selected_candidate_id": str(item.get("selected_candidate_id", "")),
            "selected_answer_candidate_id": str(item.get("selected_answer_candidate_id", "")),
            "reference_answer_action": reference_answer_action,
            "requested_reference_answer_action": requested_reference_answer_action,
            "reference_answer_role": str(item.get("reference_answer_role", REFERENCE_ANSWER_ROLE)),
            "reference_answer_status": str(item.get("reference_answer_status", "")),
            "manual_reference_answer_text_redacted": manual_answer_redacted,
            "manual_reference_answer_redaction_flags": manual_answer_flags,
            "manual_question_text_redacted": manual_question_redacted,
            "manual_question_redaction_flags": manual_question_flags,
            "question_intent": question_intent,
            "legal_answer_requirement": legal_answer_requirement,
            "graph_db_evaluation_fit": graph_db_evaluation_fit,
            "issue_spotting_required": issue_spotting_required,
            "issue_spotting_level": issue_spotting_level,
            "issue_spotting_confidence": issue_spotting_confidence,
            "issue_spotting_reason": issue_spotting_reason,
            "hidden_legal_issue_categories": hidden_legal_issue_categories,
            "answer_must_expand_beyond_user_wording": answer_must_expand_beyond_user_wording,
            "exclusion_reason": exclusion_reason,
            "reviewer_hash": str(item.get("reviewer_hash", "")),
            "reviewed_at": str(item.get("reviewed_at", _utc_timestamp())),
            "decision_reason": str(item.get("decision_reason", "")),
            "review_status": "review_approved" if decision == "approve" else decision,
            "trust_boundary": "manual_review_decision_is_evaluation_metadata_not_legal_truth",
        }
        decisions.append(record)
        counts["imported"] += 1
        counts[decision] += 1
        counts[reference_answer_action] += 1
        if manual_question_redacted:
            counts["manual_question_override"] += 1
        if graph_db_evaluation_fit:
            counts[f"graph_db_evaluation_fit:{graph_db_evaluation_fit}"] += 1
        if legal_answer_requirement:
            counts[f"legal_answer_requirement:{legal_answer_requirement}"] += 1
        if question_intent:
            counts[f"question_intent:{question_intent}"] += 1
        if issue_spotting_required:
            counts["issue_spotting_required"] += 1
        if issue_spotting_level:
            counts[f"issue_spotting_level:{issue_spotting_level}"] += 1
        if issue_spotting_confidence:
            counts[f"issue_spotting_confidence:{issue_spotting_confidence}"] += 1
        for issue in hidden_legal_issue_categories:
            counts[f"hidden_legal_issue:{issue}"] += 1
    summary = {
        "artifact_type": "tg_qa_manual_review_decision_summary",
        "generated_at": _utc_timestamp(),
        "review_queue_path": str(review_queue_path),
        "decisions_path": str(decisions_path),
        "imported_decisions_path": str(output_path or ""),
        "summary_output_path": str(summary_output_path or ""),
        "processed_count": len(raw_decisions),
        "imported_count": counts.get("imported", 0),
        "failed_count": counts.get("failed", 0),
        "counts_by_decision": {
            key: value for key, value in sorted(counts.items()) if key in ALLOWED_REVIEW_DECISIONS
        },
        "counts_by_reference_answer_action": {
            key: value for key, value in sorted(counts.items()) if key in REFERENCE_ANSWER_ACTIONS
        },
        "missing_manual_reference_answer_count": counts.get("missing_manual_reference_answer", 0),
        "manual_answer_overrode_reference_action_count": counts.get("manual_answer_overrode_reference_action", 0),
        "manual_question_override_count": counts.get("manual_question_override", 0),
        "issue_spotting_required_count": counts.get("issue_spotting_required", 0),
        "counts_by_issue_spotting_level": _prefixed_counter(counts, "issue_spotting_level:"),
        "counts_by_issue_spotting_confidence": _prefixed_counter(counts, "issue_spotting_confidence:"),
        "counts_by_graph_db_evaluation_fit": _prefixed_counter(counts, "graph_db_evaluation_fit:"),
        "counts_by_legal_answer_requirement": _prefixed_counter(counts, "legal_answer_requirement:"),
        "counts_by_question_intent": _prefixed_counter(counts, "question_intent:"),
        "counts_by_hidden_legal_issue_category": _prefixed_counter(counts, "hidden_legal_issue:"),
    }
    if output_path:
        _write_jsonl(output_path, decisions)
    if summary_output_path:
        _write_json(summary_output_path, summary)
    return {"decisions": decisions, "summary": summary}


def build_final_tg_qa_dataset(
    *,
    candidates_path: str | Path,
    selection_path: str | Path,
    review_decisions_path: str | Path | None = None,
    output_path: str | Path | None = None,
    manifest_output_path: str | Path | None = None,
    quality_output_path: str | Path | None = None,
) -> dict[str, Any]:
    candidates = [item for item in _read_jsonl(candidates_path) if isinstance(item, Mapping)]
    selections = [item for item in _read_jsonl(selection_path) if isinstance(item, Mapping)]
    decisions = (
        [item for item in _read_jsonl(review_decisions_path) if isinstance(item, Mapping)]
        if review_decisions_path
        else []
    )
    candidate_by_id = {str(candidate.get("candidate_id", "")): candidate for candidate in candidates}
    decisions_by_cluster = {
        str(decision.get("qa_cluster_id", "")): decision
        for decision in decisions
        if decision.get("decision") == "approve"
    }
    cases: list[dict[str, Any]] = []
    for selection in selections:
        qa_cluster_id = str(selection.get("qa_cluster_id", ""))
        status = ""
        decision = decisions_by_cluster.get(qa_cluster_id)
        selected_candidate_id = str(selection.get("selected_candidate_id", ""))
        selected_answer_candidate_id = str(selection.get("selected_answer_candidate_id", ""))
        if selection.get("selection_status") == "auto_selected":
            status = "auto_selected"
        elif decision:
            status = "review_approved"
            selected_candidate_id = str(decision.get("selected_candidate_id") or selected_candidate_id)
            selected_answer_candidate_id = str(decision.get("selected_answer_candidate_id") or selected_answer_candidate_id)
        if status not in {"auto_selected", "review_approved"}:
            continue
        candidate = candidate_by_id.get(selected_candidate_id, {})
        answer = _find_answer_candidate(candidate, selected_answer_candidate_id)
        manual_reference_answer = str(decision.get("manual_reference_answer_text_redacted", "")) if decision else ""
        manual_question = str(decision.get("manual_question_text_redacted", "")) if decision else ""
        reference_answer_action = str(decision.get("reference_answer_action", "")) if decision else "keep_selected"
        if not reference_answer_action:
            reference_answer_action = "replace_manual" if manual_reference_answer else "keep_selected"
        use_manual_reference_answer = reference_answer_action == "replace_manual" and bool(manual_reference_answer.strip())
        if not candidate or (not answer and not use_manual_reference_answer):
            continue
        original_question_text = str(candidate.get("question_text_redacted", ""))
        use_manual_question = bool(manual_question.strip())
        question_text = manual_question if use_manual_question else original_question_text
        question_text_source = "manual_review_override" if use_manual_question else "selected_telegram_question"
        original_selected_answer_text = str(answer.get("text_redacted", "")) if answer else ""
        reference_answer_text = manual_reference_answer if use_manual_reference_answer else original_selected_answer_text
        reference_answer_source = "manual_review_override" if use_manual_reference_answer else "selected_telegram_answer"
        reference_answer_status = (
            "manual_reference_answer"
            if use_manual_reference_answer
            else str(decision.get("reference_answer_status", ""))
            if decision
            else "auto_selected"
        )
        question_intent = str(decision.get("question_intent", "")) if decision else ""
        legal_answer_requirement = str(decision.get("legal_answer_requirement", "")) if decision else ""
        graph_db_evaluation_fit = str(decision.get("graph_db_evaluation_fit", "")) if decision else ""
        issue_spotting_required = bool(decision.get("issue_spotting_required", False)) if decision else False
        issue_spotting_level = str(decision.get("issue_spotting_level", "unclassified")) if decision else "unclassified"
        issue_spotting_confidence = (
            str(decision.get("issue_spotting_confidence", "unclassified")) if decision else "unclassified"
        )
        issue_spotting_reason = str(decision.get("issue_spotting_reason", "")) if decision else ""
        hidden_legal_issue_categories = list(decision.get("hidden_legal_issue_categories", [])) if decision else []
        answer_must_expand_beyond_user_wording = (
            bool(decision.get("answer_must_expand_beyond_user_wording", False)) if decision else False
        )
        exclusion_reason = str(decision.get("exclusion_reason", "")) if decision else ""
        case_id_question_part = _stable_hash(question_text) if use_manual_question else selected_candidate_id
        case_id_answer_part = _stable_hash(reference_answer_text) if use_manual_reference_answer else selected_answer_candidate_id
        cases.append(
            {
                "case_id": f"tg-eval-case:{_stable_hash(qa_cluster_id + case_id_question_part + case_id_answer_part)}",
                "qa_cluster_id": qa_cluster_id,
                "normalized_question": question_text,
                "question_text_redacted": question_text,
                "original_question_text_redacted": original_question_text,
                "question_text_source": question_text_source,
                "selected_answer_text_redacted": reference_answer_text,
                "reference_answer_text_redacted": reference_answer_text,
                "original_selected_answer_text_redacted": original_selected_answer_text,
                "selected_candidate_id": selected_candidate_id,
                "selected_answer_candidate_id": selected_answer_candidate_id,
                "reference_answer_candidate_id": selected_answer_candidate_id,
                "reference_answer_source": reference_answer_source,
                "reference_answer_action": reference_answer_action,
                "reference_answer_role": str(decision.get("reference_answer_role", "")) if decision else REFERENCE_ANSWER_ROLE,
                "reference_answer_status": reference_answer_status,
                "question_intent": question_intent,
                "legal_answer_requirement": legal_answer_requirement,
                "graph_db_evaluation_fit": graph_db_evaluation_fit,
                "issue_spotting_required": issue_spotting_required,
                "issue_spotting_level": issue_spotting_level,
                "issue_spotting_confidence": issue_spotting_confidence,
                "issue_spotting_reason": issue_spotting_reason,
                "hidden_legal_issue_categories": hidden_legal_issue_categories,
                "answer_must_expand_beyond_user_wording": answer_must_expand_beyond_user_wording,
                "exclusion_reason": exclusion_reason,
                "manual_reference_answer_redaction_flags": list(decision.get("manual_reference_answer_redaction_flags", []))
                if decision
                else [],
                "manual_question_redaction_flags": list(decision.get("manual_question_redaction_flags", []))
                if decision
                else [],
                "question_inclusion_status": status,
                "answer_source_type": reference_answer_source if use_manual_reference_answer else str(answer.get("answer_source_type", "")),
                "answer_link_type": "manual_review_override" if use_manual_reference_answer else str(answer.get("answer_link_type", "")),
                "selected_telegram_answer_source_type": str(answer.get("answer_source_type", "")) if answer else "",
                "selected_telegram_answer_link_type": str(answer.get("answer_link_type", "")) if answer else "",
                "topic_labels": list(candidate.get("topic_labels", [])),
                "law_code_candidates": list(candidate.get("law_code_candidates", [])),
                "status": status,
                "answer_drift_status": str(selection.get("answer_drift_status", "")),
                "historical_answer_variant_count": int(selection.get("historical_answer_variant_count", 0) or 0),
                "review_status": status,
                "provenance": {
                    "export_id": str(candidate.get("export_id", "")),
                    "question_message_id": str(candidate.get("question_message_id", "")),
                    "answer_message_id": str(answer.get("message_id", "")) if answer else "",
                    "trigger_message_id": str(answer.get("trigger_message_id", "")) if answer else "",
                    "reference_answer_source": reference_answer_source,
                    "source_candidate_artifact": str(candidates_path),
                    "source_cluster_artifact": str(selection_path),
                    "source_review_artifact": str(review_decisions_path or ""),
                },
            }
        )
    manifest = {
        "artifact_type": "tg_qa_dataset_manifest",
        "dataset_id": f"tg-eval-dataset:{_stable_hash(str(output_path or '') + str(len(cases)))}",
        "generated_at": _utc_timestamp(),
        "source_candidate_artifact": str(candidates_path),
        "source_cluster_artifact": str(selection_path),
        "source_review_artifact": str(review_decisions_path or ""),
        "run_ids_by_stage": {},
        "case_count": len(cases),
        "counts_by_status": dict(sorted(Counter(str(item["status"]) for item in cases).items())),
        "counts_by_topic_label": dict(sorted(Counter(label for item in cases for label in item["topic_labels"]).items())),
        "counts_by_law_code_candidate": dict(
            sorted(Counter(law for item in cases for law in item["law_code_candidates"]).items())
        ),
        "counts_by_answer_source_type": dict(sorted(Counter(str(item["answer_source_type"]) for item in cases).items())),
        "counts_by_answer_link_type": dict(sorted(Counter(str(item["answer_link_type"]) for item in cases).items())),
        "counts_by_reference_answer_source": dict(
            sorted(Counter(str(item["reference_answer_source"]) for item in cases).items())
        ),
        "counts_by_reference_answer_action": dict(
            sorted(Counter(str(item["reference_answer_action"]) for item in cases).items())
        ),
        "counts_by_reference_answer_status": dict(
            sorted(Counter(str(item["reference_answer_status"]) for item in cases).items())
        ),
        "counts_by_graph_db_evaluation_fit": dict(
            sorted(Counter(str(item.get("graph_db_evaluation_fit", "") or "unclassified") for item in cases).items())
        ),
        "counts_by_legal_answer_requirement": dict(
            sorted(Counter(str(item.get("legal_answer_requirement", "") or "unclassified") for item in cases).items())
        ),
        "counts_by_question_intent": dict(
            sorted(Counter(str(item.get("question_intent", "") or "unclassified") for item in cases).items())
        ),
        "issue_spotting_required_count": sum(1 for item in cases if item.get("issue_spotting_required")),
        "counts_by_issue_spotting_level": dict(
            sorted(Counter(str(item.get("issue_spotting_level", "") or "unclassified") for item in cases).items())
        ),
        "counts_by_issue_spotting_confidence": dict(
            sorted(Counter(str(item.get("issue_spotting_confidence", "") or "unclassified") for item in cases).items())
        ),
        "answer_must_expand_beyond_user_wording_count": sum(
            1 for item in cases if item.get("answer_must_expand_beyond_user_wording")
        ),
        "counts_by_hidden_legal_issue_category": dict(
            sorted(
                Counter(
                    issue
                    for item in cases
                    for issue in item.get("hidden_legal_issue_categories", [])
                ).items()
            )
        ),
        "drift_conflict_counts": dict(
            sorted(Counter(str(item.get("answer_drift_status", "")) for item in selections).items())
        ),
        "known_limitations": [
            "telegram_answers_are_evaluation_material_not_legal_truth",
            REFERENCE_ANSWER_ROLE,
            "llm_output_alone_cannot_create_final_cases",
        ],
        "unresolved_backlog_counts": dict(
            sorted(
                Counter(
                    str(item.get("selection_status", ""))
                    for item in selections
                    if item.get("selection_status") not in {"auto_selected"}
                    and str(item.get("qa_cluster_id", "")) not in decisions_by_cluster
                ).items()
            )
        ),
        "quality_report_path": str(quality_output_path or ""),
    }
    quality = {
        "artifact_type": "tg_qa_dataset_quality_report",
        "generated_at": _utc_timestamp(),
        "case_count": len(cases),
        "source_selection_count": len(selections),
        "rejected_or_uncertain_count": sum(
            1
            for item in selections
            if item.get("selection_status") in {"rejected", "uncertain", "needs_manual_review", "needs_llm_review"}
            and str(item.get("qa_cluster_id", "")) not in decisions_by_cluster
        ),
        "counts_by_answer_source_type": manifest["counts_by_answer_source_type"],
        "counts_by_answer_link_type": manifest["counts_by_answer_link_type"],
        "counts_by_reference_answer_source": manifest["counts_by_reference_answer_source"],
        "counts_by_reference_answer_action": manifest["counts_by_reference_answer_action"],
        "counts_by_reference_answer_status": manifest["counts_by_reference_answer_status"],
        "counts_by_graph_db_evaluation_fit": manifest["counts_by_graph_db_evaluation_fit"],
        "counts_by_legal_answer_requirement": manifest["counts_by_legal_answer_requirement"],
        "counts_by_question_intent": manifest["counts_by_question_intent"],
        "issue_spotting_required_count": manifest["issue_spotting_required_count"],
        "counts_by_issue_spotting_level": manifest["counts_by_issue_spotting_level"],
        "counts_by_issue_spotting_confidence": manifest["counts_by_issue_spotting_confidence"],
        "answer_must_expand_beyond_user_wording_count": manifest["answer_must_expand_beyond_user_wording_count"],
        "counts_by_hidden_legal_issue_category": manifest["counts_by_hidden_legal_issue_category"],
        "drift_conflict_counts": manifest["drift_conflict_counts"],
        "llm_reviewed_count": 0,
        "manual_reviewed_count": len(decisions_by_cluster),
        "trust_boundary": "final_dataset_is_evaluation_artifact_not_legal_authority",
    }
    if output_path:
        _write_jsonl(output_path, cases)
    if manifest_output_path:
        _write_json(manifest_output_path, manifest)
    if quality_output_path:
        _write_json(quality_output_path, quality)
    return {"cases": cases, "manifest": manifest, "quality": quality}


def _canonicalize_merged_final_case(
    case: Mapping[str, Any],
    *,
    source_case_artifact: str,
    source_manifest_artifact: str,
    source_dataset_batch: str,
) -> dict[str, Any]:
    record = dict(case)
    record["question_intent"] = str(record.get("question_intent", "") or "unclassified")
    record["legal_answer_requirement"] = str(record.get("legal_answer_requirement", "") or "unclassified")
    record["graph_db_evaluation_fit"] = str(record.get("graph_db_evaluation_fit", "") or "unclassified")
    record["issue_spotting_required"] = bool(record.get("issue_spotting_required", False))
    record["issue_spotting_level"] = _normalize_enum_value(
        record.get("issue_spotting_level", ""),
        allowed=ISSUE_SPOTTING_LEVELS,
        default="unclassified",
    )
    record["issue_spotting_confidence"] = _normalize_enum_value(
        record.get("issue_spotting_confidence", ""),
        allowed=ISSUE_SPOTTING_CONFIDENCE_LEVELS,
        default="unclassified",
    )
    record["issue_spotting_reason"] = str(record.get("issue_spotting_reason", "") or "")
    record["hidden_legal_issue_categories"] = _normalize_hidden_legal_issue_categories(
        record.get("hidden_legal_issue_categories", [])
    )
    record["answer_must_expand_beyond_user_wording"] = bool(
        record.get("answer_must_expand_beyond_user_wording", False)
    )
    record["exclusion_reason"] = str(record.get("exclusion_reason", "") or "none")
    record["topic_labels"] = list(record.get("topic_labels", []))
    record["law_code_candidates"] = list(record.get("law_code_candidates", []))
    record["manual_reference_answer_redaction_flags"] = list(record.get("manual_reference_answer_redaction_flags", []))
    record["manual_question_redaction_flags"] = list(record.get("manual_question_redaction_flags", []))
    provenance = dict(record.get("provenance", {})) if isinstance(record.get("provenance"), Mapping) else {}
    provenance["source_final_case_artifact"] = source_case_artifact
    provenance["source_final_manifest_artifact"] = source_manifest_artifact
    record["provenance"] = provenance
    record["source_dataset_batch"] = source_dataset_batch
    return record


def merge_final_tg_qa_datasets(
    *,
    case_paths: Sequence[str | Path],
    manifest_paths: Sequence[str | Path] | None = None,
    output_path: str | Path | None = None,
    manifest_output_path: str | Path | None = None,
    quality_output_path: str | Path | None = None,
) -> dict[str, Any]:
    if not case_paths:
        raise ValueError("At least one final dataset case path is required")
    manifest_paths = manifest_paths or []
    if manifest_paths and len(manifest_paths) != len(case_paths):
        raise ValueError("When provided, manifest_paths must match case_paths length")

    merged_cases: list[dict[str, Any]] = []
    source_case_artifacts = [str(path) for path in case_paths]
    source_manifest_artifacts = [str(path) for path in manifest_paths]
    source_batch_case_counts: Counter[str] = Counter()
    known_limitations: list[str] = []
    case_ids_seen: set[str] = set()
    qa_cluster_ids_seen: set[str] = set()

    for index, case_path in enumerate(case_paths):
        case_artifact = str(case_path)
        manifest_artifact = str(manifest_paths[index]) if manifest_paths else ""
        source_dataset_batch = Path(case_artifact).stem
        if manifest_artifact:
            manifest = json.loads(Path(manifest_artifact).read_text(encoding="utf-8"))
            for limitation in manifest.get("known_limitations", []):
                limitation_text = str(limitation)
                if limitation_text not in known_limitations:
                    known_limitations.append(limitation_text)
        for item in _read_jsonl(case_path):
            if not isinstance(item, Mapping):
                continue
            record = _canonicalize_merged_final_case(
                item,
                source_case_artifact=case_artifact,
                source_manifest_artifact=manifest_artifact,
                source_dataset_batch=source_dataset_batch,
            )
            case_id = str(record.get("case_id", ""))
            qa_cluster_id = str(record.get("qa_cluster_id", ""))
            if case_id in case_ids_seen:
                raise ValueError(f"Duplicate case_id across merged datasets: {case_id}")
            if qa_cluster_id in qa_cluster_ids_seen:
                raise ValueError(f"Duplicate qa_cluster_id across merged datasets: {qa_cluster_id}")
            case_ids_seen.add(case_id)
            qa_cluster_ids_seen.add(qa_cluster_id)
            merged_cases.append(record)
            source_batch_case_counts[source_dataset_batch] += 1

    for limitation in (
        "telegram_answers_are_evaluation_material_not_legal_truth",
        REFERENCE_ANSWER_ROLE,
        "llm_output_alone_cannot_create_final_cases",
    ):
        if limitation not in known_limitations:
            known_limitations.append(limitation)

    manifest = {
        "artifact_type": "tg_qa_dataset_merged_manifest",
        "dataset_id": f"tg-eval-dataset-merged:{_stable_hash(''.join(source_case_artifacts) + str(len(merged_cases)))}",
        "generated_at": _utc_timestamp(),
        "source_case_artifacts": source_case_artifacts,
        "source_manifest_artifacts": source_manifest_artifacts,
        "source_dataset_count": len(source_case_artifacts),
        "source_batch_case_counts": dict(sorted(source_batch_case_counts.items())),
        "case_count": len(merged_cases),
        "counts_by_status": dict(sorted(Counter(str(item["status"]) for item in merged_cases).items())),
        "counts_by_topic_label": dict(sorted(Counter(label for item in merged_cases for label in item["topic_labels"]).items())),
        "counts_by_law_code_candidate": dict(
            sorted(Counter(law for item in merged_cases for law in item["law_code_candidates"]).items())
        ),
        "counts_by_answer_source_type": dict(
            sorted(Counter(str(item["answer_source_type"]) for item in merged_cases).items())
        ),
        "counts_by_answer_link_type": dict(
            sorted(Counter(str(item["answer_link_type"]) for item in merged_cases).items())
        ),
        "counts_by_reference_answer_source": dict(
            sorted(Counter(str(item["reference_answer_source"]) for item in merged_cases).items())
        ),
        "counts_by_reference_answer_action": dict(
            sorted(Counter(str(item["reference_answer_action"]) for item in merged_cases).items())
        ),
        "counts_by_reference_answer_status": dict(
            sorted(Counter(str(item["reference_answer_status"]) for item in merged_cases).items())
        ),
        "counts_by_graph_db_evaluation_fit": dict(
            sorted(Counter(str(item.get("graph_db_evaluation_fit", "") or "unclassified") for item in merged_cases).items())
        ),
        "counts_by_legal_answer_requirement": dict(
            sorted(Counter(str(item.get("legal_answer_requirement", "") or "unclassified") for item in merged_cases).items())
        ),
        "counts_by_question_intent": dict(
            sorted(Counter(str(item.get("question_intent", "") or "unclassified") for item in merged_cases).items())
        ),
        "issue_spotting_required_count": sum(1 for item in merged_cases if item.get("issue_spotting_required")),
        "counts_by_issue_spotting_level": dict(
            sorted(Counter(str(item.get("issue_spotting_level", "") or "unclassified") for item in merged_cases).items())
        ),
        "counts_by_issue_spotting_confidence": dict(
            sorted(Counter(str(item.get("issue_spotting_confidence", "") or "unclassified") for item in merged_cases).items())
        ),
        "answer_must_expand_beyond_user_wording_count": sum(
            1 for item in merged_cases if item.get("answer_must_expand_beyond_user_wording")
        ),
        "counts_by_hidden_legal_issue_category": dict(
            sorted(
                Counter(
                    issue
                    for item in merged_cases
                    for issue in item.get("hidden_legal_issue_categories", [])
                ).items()
            )
        ),
        "known_limitations": known_limitations,
        "quality_report_path": str(quality_output_path or ""),
    }
    quality = {
        "artifact_type": "tg_qa_dataset_merged_quality_report",
        "generated_at": _utc_timestamp(),
        "case_count": len(merged_cases),
        "source_dataset_count": len(source_case_artifacts),
        "source_batch_case_counts": manifest["source_batch_case_counts"],
        "counts_by_answer_source_type": manifest["counts_by_answer_source_type"],
        "counts_by_answer_link_type": manifest["counts_by_answer_link_type"],
        "counts_by_reference_answer_source": manifest["counts_by_reference_answer_source"],
        "counts_by_reference_answer_action": manifest["counts_by_reference_answer_action"],
        "counts_by_reference_answer_status": manifest["counts_by_reference_answer_status"],
        "counts_by_graph_db_evaluation_fit": manifest["counts_by_graph_db_evaluation_fit"],
        "counts_by_legal_answer_requirement": manifest["counts_by_legal_answer_requirement"],
        "counts_by_question_intent": manifest["counts_by_question_intent"],
        "issue_spotting_required_count": manifest["issue_spotting_required_count"],
        "counts_by_issue_spotting_level": manifest["counts_by_issue_spotting_level"],
        "counts_by_issue_spotting_confidence": manifest["counts_by_issue_spotting_confidence"],
        "answer_must_expand_beyond_user_wording_count": manifest["answer_must_expand_beyond_user_wording_count"],
        "counts_by_hidden_legal_issue_category": manifest["counts_by_hidden_legal_issue_category"],
        "manual_reviewed_count": sum(1 for item in merged_cases if str(item.get("status", "")) == "review_approved"),
        "auto_selected_count": sum(1 for item in merged_cases if str(item.get("status", "")) == "auto_selected"),
        "trust_boundary": "final_dataset_is_evaluation_artifact_not_legal_authority",
    }
    if output_path:
        _write_jsonl(output_path, merged_cases)
    if manifest_output_path:
        _write_json(manifest_output_path, manifest)
    if quality_output_path:
        _write_json(quality_output_path, quality)
    return {"cases": merged_cases, "manifest": manifest, "quality": quality}


def _coverage_dataset_question_batch_item(case: Mapping[str, Any]) -> dict[str, Any]:
    case_id = str(case.get("case_id", ""))
    question_text = str(case.get("question_text_redacted", ""))
    return {
        "embedding_item_id": f"tg-coverage-embedding:{_stable_hash(case_id + ':question')}",
        "candidate_id": case_id,
        "answer_candidate_id": "",
        "source_message_id": str(case.get("provenance", {}).get("question_message_id", "")),
        "text_role": "question",
        "coverage_scope": "dataset",
        "coverage_subject_id": case_id,
        "coverage_subject_kind": "final_case",
        "coverage_text_source": "question_text",
        "qa_cluster_id": str(case.get("qa_cluster_id", "")),
        "case_id": case_id,
        "text_redacted": question_text,
        "reference_answer_source": str(case.get("reference_answer_source", "")),
        "topic_labels": list(case.get("topic_labels", [])),
        "law_code_candidates": list(case.get("law_code_candidates", [])),
        "graph_db_evaluation_fit": str(case.get("graph_db_evaluation_fit", "")),
        "question_intent": str(case.get("question_intent", "")),
        "issue_spotting_level": str(case.get("issue_spotting_level", "")),
        "issue_spotting_required": bool(case.get("issue_spotting_required", False)),
        "answer_candidate_status": str(case.get("reference_answer_status", "")),
        "confidence_tier": "reviewed_dataset_case",
        "embedding_prefix": QUESTION_EMBEDDING_PREFIX.strip(),
        "embedding_input_text": QUESTION_EMBEDDING_PREFIX + question_text,
        "cluster_usage": ["dataset_corpus_coverage"],
        "selection_policy": COVERAGE_ANALYSIS_VERSION,
    }


def _coverage_dataset_answer_batch_item(case: Mapping[str, Any]) -> dict[str, Any] | None:
    case_id = str(case.get("case_id", ""))
    answer_text = str(case.get("reference_answer_text_redacted", ""))
    if not answer_text.strip():
        return None
    return {
        "embedding_item_id": f"tg-coverage-embedding:{_stable_hash(case_id + ':answer')}",
        "candidate_id": case_id,
        "answer_candidate_id": str(case.get("reference_answer_candidate_id", "")),
        "source_message_id": str(case.get("provenance", {}).get("answer_message_id", "")),
        "text_role": "answer",
        "coverage_scope": "dataset",
        "coverage_subject_id": case_id,
        "coverage_subject_kind": "final_case",
        "coverage_text_source": "reference_answer",
        "qa_cluster_id": str(case.get("qa_cluster_id", "")),
        "case_id": case_id,
        "text_redacted": answer_text,
        "reference_answer_source": str(case.get("reference_answer_source", "")),
        "topic_labels": list(case.get("topic_labels", [])),
        "law_code_candidates": list(case.get("law_code_candidates", [])),
        "graph_db_evaluation_fit": str(case.get("graph_db_evaluation_fit", "")),
        "question_intent": str(case.get("question_intent", "")),
        "issue_spotting_level": str(case.get("issue_spotting_level", "")),
        "issue_spotting_required": bool(case.get("issue_spotting_required", False)),
        "answer_candidate_status": str(case.get("reference_answer_status", "")),
        "confidence_tier": "reviewed_dataset_case",
        "embedding_prefix": ANSWER_EMBEDDING_PREFIX.strip(),
        "embedding_input_text": ANSWER_EMBEDDING_PREFIX + answer_text,
        "cluster_usage": ["dataset_corpus_coverage"],
        "selection_policy": COVERAGE_ANALYSIS_VERSION,
    }


def _representative_answer_sort_key(answer: Mapping[str, Any], policy: Mapping[str, Any]) -> tuple[int, int, int, int, int, str, str]:
    status_rank = {"strong": 2, "partial": 1}.get(str(answer.get("answer_candidate_status", "")), 0)
    confidence_rank = {"high": 2, "medium": 1, "low": 0}.get(str(answer.get("link_confidence", "")), 0)
    priority_rank = {"normal": 1, "low": 0}.get(str(answer.get("answer_candidate_priority", "")), 1)
    usable_rank = 1 if _is_usable_answer_candidate(answer, policy) else 0
    text_rank = 1 if str(answer.get("text_redacted", "")).strip() else 0
    return (
        usable_rank,
        status_rank,
        confidence_rank,
        priority_rank,
        text_rank,
        _date_sort_value(str(answer.get("date", ""))),
        str(answer.get("answer_candidate_id", "")),
    )


def _representative_answer_candidate(candidate: Mapping[str, Any], policy: Mapping[str, Any]) -> Mapping[str, Any] | None:
    answers = [
        answer
        for answer in candidate.get("answer_candidates", [])
        if isinstance(answer, Mapping) and str(answer.get("text_redacted", "")).strip()
    ]
    if not answers:
        return None
    answers.sort(key=lambda item: _representative_answer_sort_key(item, policy), reverse=True)
    return answers[0]


def _coverage_corpus_question_batch_item(candidate: Mapping[str, Any]) -> dict[str, Any]:
    candidate_id = str(candidate.get("candidate_id", ""))
    question_text = str(candidate.get("question_text_redacted", ""))
    return {
        "embedding_item_id": f"tg-coverage-embedding:{_stable_hash(candidate_id + ':question')}",
        "candidate_id": candidate_id,
        "answer_candidate_id": "",
        "source_message_id": str(candidate.get("question_message_id", "")),
        "text_role": "question",
        "coverage_scope": "corpus",
        "coverage_subject_id": candidate_id,
        "coverage_subject_kind": "candidate",
        "coverage_text_source": "question_text",
        "qa_cluster_id": "",
        "case_id": "",
        "text_redacted": question_text,
        "reference_answer_source": "",
        "topic_labels": list(candidate.get("topic_labels", [])),
        "law_code_candidates": list(candidate.get("law_code_candidates", [])),
        "graph_db_evaluation_fit": "",
        "question_intent": "",
        "issue_spotting_level": "",
        "issue_spotting_required": False,
        "answer_candidate_status": str(candidate.get("answer_candidate_status", "")),
        "confidence_tier": str(candidate.get("confidence_tier", "")),
        "embedding_prefix": QUESTION_EMBEDDING_PREFIX.strip(),
        "embedding_input_text": QUESTION_EMBEDDING_PREFIX + question_text,
        "cluster_usage": ["dataset_corpus_coverage"],
        "selection_policy": COVERAGE_ANALYSIS_VERSION,
    }


def _coverage_corpus_answer_batch_item(
    candidate: Mapping[str, Any],
    representative_answer: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_id = str(candidate.get("candidate_id", ""))
    answer_id = str(representative_answer.get("answer_candidate_id", ""))
    answer_text = str(representative_answer.get("text_redacted", ""))
    return {
        "embedding_item_id": f"tg-coverage-embedding:{_stable_hash(candidate_id + ':' + answer_id)}",
        "candidate_id": candidate_id,
        "answer_candidate_id": answer_id,
        "source_message_id": str(representative_answer.get("message_id", "")),
        "text_role": "answer",
        "coverage_scope": "corpus",
        "coverage_subject_id": candidate_id,
        "coverage_subject_kind": "candidate",
        "coverage_text_source": "representative_answer",
        "qa_cluster_id": "",
        "case_id": "",
        "text_redacted": answer_text,
        "reference_answer_source": str(representative_answer.get("answer_source_type", "")),
        "topic_labels": list(candidate.get("topic_labels", [])),
        "law_code_candidates": list(candidate.get("law_code_candidates", [])),
        "graph_db_evaluation_fit": "",
        "question_intent": "",
        "issue_spotting_level": "",
        "issue_spotting_required": False,
        "answer_candidate_status": str(representative_answer.get("answer_candidate_status", "")),
        "confidence_tier": str(candidate.get("confidence_tier", "")),
        "embedding_prefix": ANSWER_EMBEDDING_PREFIX.strip(),
        "embedding_input_text": ANSWER_EMBEDDING_PREFIX + answer_text,
        "cluster_usage": ["dataset_corpus_coverage"],
        "selection_policy": COVERAGE_ANALYSIS_VERSION,
        "answer_source_type": str(representative_answer.get("answer_source_type", "")),
        "answer_link_type": str(representative_answer.get("answer_link_type", "")),
        "link_confidence": str(representative_answer.get("link_confidence", "")),
    }


def _corpus_coverage_filter_matches(candidate: Mapping[str, Any], mode: str) -> bool:
    if mode == "all":
        return True
    has_law_or_topic = bool(candidate.get("law_code_candidates")) or bool(candidate.get("topic_labels"))
    if mode == "law_or_topic":
        return has_law_or_topic
    if mode == "legalish":
        has_trigger_signal = bool(candidate.get("trigger_evidence"))
        has_known_bot_signal = (
            int(candidate.get("known_wiki_bot_answer_candidate_count", 0) or 0) > 0
            or int(candidate.get("known_bot_answer_via_trigger_count", 0) or 0) > 0
        )
        needs_embedding_cluster = str(candidate.get("selection_status", "")) == "pending_embedding_cluster"
        return has_law_or_topic or has_trigger_signal or has_known_bot_signal or needs_embedding_cluster
    raise ValueError(f"unsupported corpus coverage filter mode: {mode}")


def emit_tg_qa_dataset_corpus_coverage_embedding_batch(
    *,
    final_cases_path: str | Path,
    candidates_path: str | Path,
    output_path: str | Path | None = None,
    summary_output_path: str | Path | None = None,
    clustering_policy: Mapping[str, Any] | None = None,
    corpus_filter_mode: str = "all",
    include_corpus_answers: bool = True,
) -> dict[str, Any]:
    cases = [item for item in _read_jsonl(final_cases_path) if isinstance(item, Mapping)]
    candidates = [item for item in _read_jsonl(candidates_path) if isinstance(item, Mapping)]
    if corpus_filter_mode not in CORPUS_COVERAGE_FILTER_MODES:
        raise ValueError(
            f"unsupported corpus_filter_mode={corpus_filter_mode!r}; "
            f"expected one of {CORPUS_COVERAGE_FILTER_MODES}"
        )
    filtered_candidates = [
        candidate for candidate in candidates if _corpus_coverage_filter_matches(candidate, corpus_filter_mode)
    ]
    policy = _clustering_policy(clustering_policy)
    batch_items: list[dict[str, Any]] = []
    for case in cases:
        batch_items.append(_coverage_dataset_question_batch_item(case))
        answer_item = _coverage_dataset_answer_batch_item(case)
        if answer_item:
            batch_items.append(answer_item)
    representative_answer_count = 0
    for candidate in filtered_candidates:
        batch_items.append(_coverage_corpus_question_batch_item(candidate))
        if include_corpus_answers:
            representative_answer = _representative_answer_candidate(candidate, policy)
            if representative_answer:
                representative_answer_count += 1
                batch_items.append(_coverage_corpus_answer_batch_item(candidate, representative_answer))
    summary = {
        "artifact_type": "tg_qa_dataset_corpus_coverage_embedding_batch_summary",
        "generated_at": _utc_timestamp(),
        "final_cases_path": str(final_cases_path),
        "candidates_path": str(candidates_path),
        "embedding_batch_output_path": str(output_path or ""),
        "summary_output_path": str(summary_output_path or ""),
        "analysis_version": COVERAGE_ANALYSIS_VERSION,
        "corpus_filter_mode": corpus_filter_mode,
        "include_corpus_answers": include_corpus_answers,
        "dataset_case_count": len(cases),
        "corpus_candidate_count": len(filtered_candidates),
        "corpus_candidate_count_before_filter": len(candidates),
        "corpus_candidate_filtered_out_count": len(candidates) - len(filtered_candidates),
        "corpus_candidate_with_representative_answer_count": representative_answer_count,
        "batch_item_count": len(batch_items),
        "counts_by_scope_role": dict(
            sorted(
                Counter(
                    f"{str(item.get('coverage_scope', ''))}:{str(item.get('text_role', ''))}"
                    for item in batch_items
                ).items()
            )
        ),
        "embedding_input_text_stats": _text_length_stats(
            str(item.get("embedding_input_text", "")) for item in batch_items
        ),
        "trust_boundary": "coverage_embedding_batch_is_evaluation_analysis_input_not_graph_write",
    }
    if output_path:
        _write_jsonl(output_path, batch_items)
    if summary_output_path:
        _write_json(summary_output_path, summary)
    return {"batch_items": batch_items, "summary": summary}


def _coverage_embedding_record_from_external_item(
    *,
    batch_item: Mapping[str, Any],
    raw_vector_record: Mapping[str, Any] | None,
    profile: EmbeddingProfile,
) -> dict[str, Any]:
    base = _embedding_record_from_external_item(
        batch_item=batch_item,
        raw_vector_record=raw_vector_record,
        profile=profile,
    )
    base.update(
        {
            "coverage_scope": str(batch_item.get("coverage_scope", "")),
            "coverage_subject_id": str(batch_item.get("coverage_subject_id", "")),
            "coverage_subject_kind": str(batch_item.get("coverage_subject_kind", "")),
            "coverage_text_source": str(batch_item.get("coverage_text_source", "")),
            "qa_cluster_id": str(batch_item.get("qa_cluster_id", "")),
            "case_id": str(batch_item.get("case_id", "")),
            "text_redacted": str(batch_item.get("text_redacted", "")),
            "reference_answer_source": str(batch_item.get("reference_answer_source", "")),
            "topic_labels": list(batch_item.get("topic_labels", [])),
            "law_code_candidates": list(batch_item.get("law_code_candidates", [])),
            "graph_db_evaluation_fit": str(batch_item.get("graph_db_evaluation_fit", "")),
            "question_intent": str(batch_item.get("question_intent", "")),
            "issue_spotting_level": str(batch_item.get("issue_spotting_level", "")),
            "issue_spotting_required": bool(batch_item.get("issue_spotting_required", False)),
            "confidence_tier": str(batch_item.get("confidence_tier", "")),
        }
    )
    return base


def import_tg_qa_dataset_corpus_coverage_embeddings(
    *,
    embedding_batch_path: str | Path,
    external_vectors_path: str | Path,
    output_path: str | Path | None = None,
    summary_output_path: str | Path | None = None,
    profile_metadata: Mapping[str, Any] | EmbeddingProfile | None = None,
) -> dict[str, Any]:
    batch_items = [item for item in _read_jsonl(embedding_batch_path) if isinstance(item, Mapping)]
    external_items = _read_jsonl(external_vectors_path)
    profile = _embedding_profile_from_metadata(profile_metadata)
    external_by_key = {
        _embedding_external_key(item): item
        for item in external_items
        if isinstance(item, Mapping)
    }
    records: list[dict[str, Any]] = []
    counts = Counter()
    for item in batch_items:
        raw_vector_record = external_by_key.get(_embedding_external_key(item))
        record = _coverage_embedding_record_from_external_item(
            batch_item=item,
            raw_vector_record=raw_vector_record,
            profile=profile,
        )
        records.append(record)
        counts[str(record["embedding_status"])] += 1
    summary = {
        "artifact_type": "tg_qa_dataset_corpus_coverage_embedding_import_summary",
        "generated_at": _utc_timestamp(),
        "embedding_batch_path": str(embedding_batch_path),
        "external_vectors_path": str(external_vectors_path),
        "embedding_records_path": str(output_path or ""),
        "summary_output_path": str(summary_output_path or ""),
        "analysis_version": COVERAGE_ANALYSIS_VERSION,
        "processed_count": len(batch_items),
        "completed_count": counts.get("completed", 0),
        "failed_count": counts.get("failed", 0),
        "counts_by_scope_role": dict(
            sorted(
                Counter(
                    f"{str(record.get('coverage_scope', ''))}:{str(record.get('text_role', ''))}"
                    for record in records
                ).items()
            )
        ),
        "embedding_profile": profile.as_record(),
        "trust_boundary": "coverage_embedding_records_are_evaluation_analysis_artifacts_not_graph_writes",
    }
    if output_path:
        _write_jsonl(output_path, records)
    if summary_output_path:
        _write_json(summary_output_path, summary)
    return {"records": records, "summary": summary}


def _question_coverage_band(score: float) -> str:
    if score >= QUESTION_COVERAGE_THRESHOLDS["high"]:
        return "high"
    if score >= QUESTION_COVERAGE_THRESHOLDS["medium"]:
        return "medium"
    if score >= QUESTION_COVERAGE_THRESHOLDS["low"]:
        return "low"
    return "uncovered"


def _answer_support_band(score: float | None) -> str:
    if score is None:
        return "unavailable"
    if score >= ANSWER_SUPPORT_THRESHOLDS["strong"]:
        return "strong"
    if score >= ANSWER_SUPPORT_THRESHOLDS["medium"]:
        return "medium"
    if score >= ANSWER_SUPPORT_THRESHOLDS["weak"]:
        return "weak"
    return "unavailable"


def _coverage_status_from_question_band(question_band: str) -> str:
    if question_band in {"high", "medium"}:
        return "covered"
    if question_band == "low":
        return "partial"
    return "uncovered"


def _coverage_gap_flag(*, coverage_status: str, answer_support_band: str) -> str:
    if coverage_status == "uncovered":
        return "question_uncovered"
    if coverage_status == "partial":
        return "question_partial"
    if answer_support_band in {"strong", "medium"}:
        return "covered_with_answer_support"
    return "covered_question_only"


def _similarity_stats(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "min": 0,
            "avg": 0,
            "p50": 0,
            "p95": 0,
            "max": 0,
        }
    ordered = sorted(float(value) for value in values)
    index_p50 = min(len(ordered) - 1, int((len(ordered) - 1) * 0.50))
    index_p95 = min(len(ordered) - 1, int((len(ordered) - 1) * 0.95))
    return {
        "count": len(ordered),
        "min": round(ordered[0], 6),
        "avg": round(sum(ordered) / len(ordered), 6),
        "p50": round(ordered[index_p50], 6),
        "p95": round(ordered[index_p95], 6),
        "max": round(ordered[-1], 6),
    }


def _coverage_best_matches(
    corpus_records: Sequence[Mapping[str, Any]],
    dataset_records: Sequence[Mapping[str, Any]],
    *,
    chunk_size: int,
) -> dict[str, dict[str, Any]]:
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "numpy is required for tg-qa dataset coverage analysis; run in the chbot environment"
        ) from exc
    if not corpus_records or not dataset_records:
        return {}
    dataset_matrix = np.asarray([record.get("vector", []) for record in dataset_records], dtype=np.float32)
    dataset_subject_ids = [str(record.get("coverage_subject_id", "")) for record in dataset_records]
    results: dict[str, dict[str, Any]] = {}
    for chunk in _chunks(list(corpus_records), chunk_size):
        corpus_matrix = np.asarray([record.get("vector", []) for record in chunk], dtype=np.float32)
        scores = corpus_matrix @ dataset_matrix.T
        best_indices = scores.argmax(axis=1)
        best_scores = scores.max(axis=1)
        for record, best_index, best_score in zip(chunk, best_indices.tolist(), best_scores.tolist(), strict=True):
            results[str(record.get("coverage_subject_id", ""))] = {
                "dataset_subject_id": dataset_subject_ids[int(best_index)],
                "similarity_score": round(float(best_score), 6),
            }
    return results


def build_tg_qa_dataset_corpus_coverage_report(
    *,
    embedding_records_path: str | Path,
    output_path: str | Path | None = None,
    summary_output_path: str | Path | None = None,
    chunk_size: int = 4096,
    max_samples_per_bucket: int = 20,
) -> dict[str, Any]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    records = [
        item
        for item in _read_jsonl(embedding_records_path)
        if isinstance(item, Mapping) and item.get("embedding_status") == "completed"
    ]
    dataset_question_records = [
        item for item in records if item.get("coverage_scope") == "dataset" and item.get("text_role") == "question"
    ]
    dataset_answer_records = [
        item for item in records if item.get("coverage_scope") == "dataset" and item.get("text_role") == "answer"
    ]
    corpus_question_records = [
        item for item in records if item.get("coverage_scope") == "corpus" and item.get("text_role") == "question"
    ]
    corpus_answer_records = [
        item for item in records if item.get("coverage_scope") == "corpus" and item.get("text_role") == "answer"
    ]
    if not dataset_question_records or not corpus_question_records:
        raise ValueError("Coverage analysis requires completed dataset question embeddings and corpus question embeddings")

    dataset_question_by_subject = {
        str(item.get("coverage_subject_id", "")): item for item in dataset_question_records
    }
    dataset_answer_by_subject = {
        str(item.get("coverage_subject_id", "")): item for item in dataset_answer_records
    }
    question_matches = _coverage_best_matches(
        corpus_question_records,
        dataset_question_records,
        chunk_size=chunk_size,
    )
    answer_matches = _coverage_best_matches(
        corpus_answer_records,
        dataset_answer_records,
        chunk_size=chunk_size,
    ) if dataset_answer_records and corpus_answer_records else {}

    corpus_by_subject: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for record in corpus_question_records:
        corpus_by_subject[str(record.get("coverage_subject_id", ""))]["question"] = record
    for record in corpus_answer_records:
        corpus_by_subject[str(record.get("coverage_subject_id", ""))]["answer"] = record

    report_rows: list[dict[str, Any]] = []
    dataset_case_reuse_counts = Counter()
    question_scores: list[float] = []
    answer_scores: list[float] = []

    for subject_id, bundle in corpus_by_subject.items():
        question_record = bundle.get("question", {})
        answer_record = bundle.get("answer", {})
        question_match = question_matches.get(subject_id, {})
        answer_match = answer_matches.get(subject_id, {})
        question_score = float(question_match.get("similarity_score", 0.0))
        answer_score = float(answer_match.get("similarity_score", 0.0)) if answer_match else None
        question_band = _question_coverage_band(question_score)
        answer_band = _answer_support_band(answer_score)
        coverage_status = _coverage_status_from_question_band(question_band)
        coverage_gap_flag = _coverage_gap_flag(
            coverage_status=coverage_status,
            answer_support_band=answer_band,
        )
        question_case_id = str(question_match.get("dataset_subject_id", ""))
        answer_case_id = str(answer_match.get("dataset_subject_id", "")) if answer_match else ""
        matched_question_case = dataset_question_by_subject.get(question_case_id, {})
        matched_answer_case = dataset_answer_by_subject.get(answer_case_id, {})
        dataset_case_reuse_counts[question_case_id] += 1
        question_scores.append(question_score)
        if answer_score is not None:
            answer_scores.append(answer_score)
        report_rows.append(
            {
                "candidate_id": subject_id,
                "coverage_status": coverage_status,
                "question_coverage_band": question_band,
                "answer_support_band": answer_band,
                "coverage_gap_flag": coverage_gap_flag,
                "question_similarity_score": round(question_score, 6),
                "answer_similarity_score": round(answer_score, 6) if answer_score is not None else None,
                "question_best_case_id": question_case_id,
                "answer_best_case_id": answer_case_id,
                "question_best_case_question_text_redacted": str(matched_question_case.get("text_redacted", "")),
                "answer_best_case_reference_answer_text_redacted": str(matched_answer_case.get("text_redacted", "")),
                "question_text_redacted": str(question_record.get("text_redacted", "")),
                "representative_answer_text_redacted": str(answer_record.get("text_redacted", "")),
                "representative_answer_candidate_id": str(answer_record.get("answer_candidate_id", "")),
                "law_code_candidates": list(question_record.get("law_code_candidates", [])),
                "topic_labels": list(question_record.get("topic_labels", [])),
                "confidence_tier": str(question_record.get("confidence_tier", "")),
                "answer_candidate_status": str(question_record.get("answer_candidate_status", "")),
                "source_message_id": str(question_record.get("source_message_id", "")),
            }
        )

    report_rows.sort(
        key=lambda item: (
            {"uncovered": 0, "partial": 1, "covered": 2}.get(str(item.get("coverage_status", "")), 9),
            float(item.get("question_similarity_score", 0.0)),
            str(item.get("candidate_id", "")),
        )
    )

    uncovered_rows = [item for item in report_rows if item["coverage_status"] == "uncovered"]
    partial_rows = [item for item in report_rows if item["coverage_status"] == "partial"]
    summary = {
        "artifact_type": "tg_qa_dataset_corpus_coverage_summary",
        "generated_at": _utc_timestamp(),
        "embedding_records_path": str(embedding_records_path),
        "coverage_report_path": str(output_path or ""),
        "summary_output_path": str(summary_output_path or ""),
        "analysis_version": COVERAGE_ANALYSIS_VERSION,
        "dataset_case_count": len(dataset_question_records),
        "corpus_candidate_count": len(corpus_question_records),
        "corpus_candidate_with_representative_answer_count": len(corpus_answer_records),
        "counts_by_coverage_status": dict(
            sorted(Counter(str(item["coverage_status"]) for item in report_rows).items())
        ),
        "counts_by_question_coverage_band": dict(
            sorted(Counter(str(item["question_coverage_band"]) for item in report_rows).items())
        ),
        "counts_by_answer_support_band": dict(
            sorted(Counter(str(item["answer_support_band"]) for item in report_rows).items())
        ),
        "counts_by_coverage_gap_flag": dict(
            sorted(Counter(str(item["coverage_gap_flag"]) for item in report_rows).items())
        ),
        "question_similarity_stats": _similarity_stats(question_scores),
        "answer_similarity_stats": _similarity_stats(answer_scores),
        "dataset_case_reuse_counts": dict(sorted(dataset_case_reuse_counts.items())),
        "uncovered_counts_by_law_code_candidate": dict(
            sorted(
                Counter(
                    law
                    for item in uncovered_rows
                    for law in item.get("law_code_candidates", [])
                ).items()
            )
        ),
        "partial_counts_by_law_code_candidate": dict(
            sorted(
                Counter(
                    law
                    for item in partial_rows
                    for law in item.get("law_code_candidates", [])
                ).items()
            )
        ),
        "uncovered_counts_by_topic_label": dict(
            sorted(
                Counter(
                    label
                    for item in uncovered_rows
                    for label in item.get("topic_labels", [])
                ).items()
            )
        ),
        "partial_counts_by_topic_label": dict(
            sorted(
                Counter(
                    label
                    for item in partial_rows
                    for label in item.get("topic_labels", [])
                ).items()
            )
        ),
        "uncovered_sample_candidates": uncovered_rows[:max_samples_per_bucket],
        "partial_sample_candidates": partial_rows[:max_samples_per_bucket],
        "trust_boundary": "coverage_report_is_evaluation_analysis_not_legal_truth",
    }
    if output_path:
        _write_jsonl(output_path, report_rows)
    if summary_output_path:
        _write_json(summary_output_path, summary)
    return {"rows": report_rows, "summary": summary}


def verify_tg_qa_boundaries(
    *,
    source_path: str | Path = "src/evaluation/tg_qa_dataset.py",
    gitignore_path: str | Path = ".gitignore",
) -> dict[str, Any]:
    source = Path(source_path).read_text(encoding="utf-8")
    gitignore = Path(gitignore_path).read_text(encoding="utf-8")
    source_to_scan = "\n".join(
        line
        for line in source.splitlines()
        if "forbidden_source_patterns" not in line
        and "graph_writer_import" not in line
        and "neo4j_import" not in line
        and "chatbot_path" not in line
        and "live_framework_dependency" not in line
    )
    forbidden_source_patterns = {
        "graph_writer_import": r"^\s*from\s+graph\.writer|^\s*import\s+graph\.writer",
        "neo4j_import": r"^\s*from\s+neo4j|^\s*import\s+neo4j",
        "chatbot_path": r"chatbot|answer_generation",
        "live_framework_dependency": r"^\s*from\s+langchain|^\s*import\s+langchain|^\s*from\s+langgraph|^\s*import\s+langgraph",
    }
    failed = [
        name
        for name, pattern in forbidden_source_patterns.items()
        if re.search(pattern, source_to_scan, flags=re.IGNORECASE | re.MULTILINE)
    ]
    required_ignore_patterns = [
        "data/tg/",
        "data/evaluation/tg_qa_candidates/*.jsonl",
        "data/evaluation/tg_qa_embeddings/*.json",
        "data/evaluation/tg_qa_embeddings/*.jsonl",
        "data/evaluation/tg_qa_similarity/*.json",
        "data/evaluation/tg_qa_clusters/*.json",
        "data/evaluation/tg_qa_selection/*.json",
        "data/evaluation/tg_qa_review/*.json",
        "data/evaluation/tg_qa_review/*.jsonl",
        "data/evaluation/tg_qa_review/*.md",
        "data/evaluation/tg_qa_review/*.tsv",
        "data/evaluation/tg_qa_llm_results/*.json",
        "data/evaluation/tg_qa_llm_results/*.jsonl",
        "data/evaluation/tg_qa_dataset/*.json",
        "data/evaluation/tg_qa_dataset/*.jsonl",
    ]
    missing_ignore_patterns = [pattern for pattern in required_ignore_patterns if pattern not in gitignore]
    status = "passed" if not failed and not missing_ignore_patterns else "failed"
    return {
        "artifact_type": "tg_qa_boundary_verification",
        "generated_at": _utc_timestamp(),
        "status": status,
        "failed_source_checks": failed,
        "missing_ignore_patterns": missing_ignore_patterns,
        "source_path": str(source_path),
        "gitignore_path": str(gitignore_path),
    }


def _write_jsonl(path: str | Path, records: Iterable[Mapping[str, Any]]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return output


def _write_text(path: str | Path, text: str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def _write_markdown(path: str | Path, text: str) -> Path:
    return _write_text(path, text)


def _open_jsonl_stream(path: str | Path):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    return output.open("w", encoding="utf-8")


def _write_jsonl_stream_record(handle: Any, record: Mapping[str, Any]) -> None:
    if handle is None:
        return
    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def _write_json(path: str | Path, record: Mapping[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


class _ProgressLine:
    def __init__(self, *, enabled: bool, label: str, total: int) -> None:
        self.enabled = enabled and sys.stderr.isatty()
        self.label = label
        self.total = max(total, 0)
        self.started = perf_counter()
        self.last_len = 0

    def update(self, processed: int, *, completed: int, failed: int, detail: str = "") -> None:
        if not self.enabled:
            return
        elapsed = max(perf_counter() - self.started, 0.001)
        rate = processed / elapsed if processed > 0 else 0.0
        remaining = max(self.total - processed, 0)
        eta = remaining / rate if rate > 0 else 0.0
        percent = (processed / self.total * 100) if self.total else 100.0
        text = (
            f"{self.label}: {processed}/{self.total} ({percent:5.1f}%) "
            f"ok={completed} failed={failed} elapsed={_format_duration(elapsed)}"
        )
        if rate > 0:
            text += f" rate={rate:.3f}/s eta={_format_duration(eta)}"
        if detail:
            text += f" | {detail}"
        self._write(text)

    def finish(self, processed: int, *, completed: int, failed: int) -> None:
        if not self.enabled:
            return
        elapsed = max(perf_counter() - self.started, 0.001)
        text = (
            f"{self.label}: {processed}/{self.total} (100.0%) "
            f"ok={completed} failed={failed} elapsed={_format_duration(elapsed)}"
        )
        self._write(text)
        sys.stderr.write("\n")
        sys.stderr.flush()

    def _write(self, text: str) -> None:
        padding = " " * max(0, self.last_len - len(text))
        sys.stderr.write("\r" + text + padding)
        sys.stderr.flush()
        self.last_len = len(text)


def _format_duration(seconds: float) -> str:
    total_seconds = int(max(seconds, 0))
    minutes, remaining_seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}h{minutes:02d}m{remaining_seconds:02d}s"
    if minutes:
        return f"{minutes:d}m{remaining_seconds:02d}s"
    return f"{remaining_seconds:d}s"


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
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


def _chunks(items: list[Mapping[str, Any]], chunk_size: int) -> Iterable[list[Mapping[str, Any]]]:
    for offset in range(0, len(items), chunk_size):
        yield items[offset : offset + chunk_size]


def _external_vector_record(
    batch_item: Mapping[str, Any],
    *,
    vector: Sequence[float],
    failure_reason: str,
) -> dict[str, Any]:
    return {
        "embedding_item_id": str(batch_item.get("embedding_item_id", "")),
        "candidate_id": str(batch_item.get("candidate_id", "")),
        "answer_candidate_id": str(batch_item.get("answer_candidate_id", "")),
        "text_role": str(batch_item.get("text_role", "")),
        "backend_name": "local_embedding_endpoint",
        "vector": [float(value) for value in vector] if not failure_reason else [],
        "embedding_status": "failed" if failure_reason else "completed",
        "failure_reason": failure_reason,
    }


def _redacted_endpoint_shape(endpoint_url: str) -> str:
    parsed = urlparse(endpoint_url)
    if parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        return endpoint_url
    scheme = parsed.scheme or "http"
    path = parsed.path or ""
    return f"{scheme}://<redacted-host>{path}"


def _text_length_stats(texts: Iterable[str]) -> dict[str, Any]:
    values = list(texts)
    char_lengths = sorted(len(text) for text in values)
    word_lengths = sorted(len(text.split()) for text in values)
    if not values:
        return {
            "count": 0,
            "max_chars": 0,
            "avg_chars": 0,
            "p95_chars": 0,
            "max_words": 0,
            "avg_words": 0,
            "p95_words": 0,
            "tokenizer": "not_measured_whitespace_words_only",
        }
    return {
        "count": len(values),
        "max_chars": max(char_lengths),
        "avg_chars": round(sum(char_lengths) / len(values), 1),
        "p95_chars": _percentile(char_lengths, 0.95),
        "max_words": max(word_lengths),
        "avg_words": round(sum(word_lengths) / len(values), 1),
        "p95_words": _percentile(word_lengths, 0.95),
        "tokenizer": "not_measured_whitespace_words_only",
    }


def _percentile(values: list[int], quantile: float) -> int:
    if not values:
        return 0
    index = min(len(values) - 1, max(0, int(round((len(values) - 1) * quantile))))
    return values[index]


def _embedding_profile_from_metadata(
    metadata: Mapping[str, Any] | EmbeddingProfile | None,
) -> EmbeddingProfile:
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
        query_prefix=str(source.get("query_prefix", QUESTION_EMBEDDING_PREFIX)),
        document_prefix=str(source.get("document_prefix", ANSWER_EMBEDDING_PREFIX)),
        routing_mode=str(source.get("routing_mode", "local_only")),
    ).validate()


def _embedding_external_key(item: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(item.get("embedding_item_id", "")),
        str(item.get("candidate_id", "")),
        str(item.get("text_role", "")),
        str(item.get("answer_candidate_id", "")),
    )


def _embedding_record_from_external_item(
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
    status = "failed" if failure_reason else "completed"
    return {
        "embedding_item_id": str(batch_item.get("embedding_item_id", "")),
        "candidate_id": str(batch_item.get("candidate_id", "")),
        "answer_candidate_id": str(batch_item.get("answer_candidate_id", "")),
        "source_message_id": str(batch_item.get("source_message_id", "")),
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
        "backend_name": str((raw_vector_record or {}).get("backend_name", "external_jsonl_import")),
        "vector": vector if not failure_reason else [],
        "embedding_status": status,
        "failure_reason": failure_reason,
        "answer_source_type": str(batch_item.get("answer_source_type", "")),
        "answer_link_type": str(batch_item.get("answer_link_type", "")),
        "cluster_usage": list(batch_item.get("cluster_usage", [])),
        "selection_policy": str(batch_item.get("selection_policy", "")),
    }


def _extract_vector(raw: Mapping[str, Any]) -> list[float]:
    value = raw.get("vector", raw.get("embedding"))
    if value is None and isinstance(raw.get("data"), list) and raw["data"]:
        first = raw["data"][0]
        if isinstance(first, Mapping):
            value = first.get("embedding")
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("vector is missing or not a sequence")
    return [float(item) for item in value]


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _clustering_policy(policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    merged = dict(DEFAULT_CLUSTERING_POLICY)
    merged.update(dict(policy or {}))
    return merged


def _threshold_for_space(space: str, policy: Mapping[str, Any]) -> float:
    if space == "question":
        return float(policy["question_similarity_threshold"])
    if space == "answer":
        return float(policy["answer_similarity_threshold"])
    return float(policy["qa_pair_similarity_threshold"])


def _cosine_similarity(left: Any, right: Any) -> float:
    if not isinstance(left, Sequence) or not isinstance(right, Sequence):
        return 0.0
    if len(left) != len(right) or not left:
        return 0.0
    left_values = [float(item) for item in left]
    right_values = [float(item) for item in right]
    left_norm = sqrt(sum(item * item for item in left_values))
    right_norm = sqrt(sum(item * item for item in right_values))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left_values, right_values, strict=True)) / (left_norm * right_norm)


class _UnionFind:
    def __init__(self, items: Iterable[str]) -> None:
        self.parent = {item: item for item in items if item}

    def find(self, item: str) -> str:
        if not item:
            return ""
        self.parent.setdefault(item, item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: str, right: str) -> None:
        if not left or not right:
            return
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if right_root < left_root:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root

    def components(self) -> list[list[str]]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for item in list(self.parent):
            grouped[self.find(item)].append(item)
        return [sorted(items) for items in sorted(grouped.values(), key=lambda values: values[0])]


def _answer_owner_map(candidates: list[Mapping[str, Any]]) -> dict[str, str]:
    owners: dict[str, str] = {}
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id", ""))
        for answer in candidate.get("answer_candidates", []):
            if isinstance(answer, Mapping):
                owners[str(answer.get("answer_candidate_id", ""))] = candidate_id
    return owners


def _cluster_metadata_compatible(
    candidate_by_id: Mapping[str, Mapping[str, Any]],
    left_candidate_id: str,
    right_candidate_id: str,
    policy: Mapping[str, Any],
) -> bool:
    if not left_candidate_id or not right_candidate_id:
        return False
    left = candidate_by_id.get(left_candidate_id, {})
    right = candidate_by_id.get(right_candidate_id, {})
    if policy.get("topic_overlap_required"):
        left_topics = set(left.get("topic_labels", []))
        right_topics = set(right.get("topic_labels", []))
        if (left_topics or right_topics) and left_topics.isdisjoint(right_topics):
            return False
    if policy.get("law_overlap_required"):
        left_laws = set(left.get("law_code_candidates", []))
        right_laws = set(right.get("law_code_candidates", []))
        if left_laws and right_laws and left_laws.isdisjoint(right_laws):
            return False
    return True


def _cluster_records_from_components(
    *,
    components: list[list[str]],
    cluster_type: str,
    candidates_by_id: Mapping[str, Mapping[str, Any]],
    answer_owner: Mapping[str, str],
    policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for members in components:
        if cluster_type == "answer":
            answer_ids = members
            candidate_ids = sorted({answer_owner.get(answer_id, "") for answer_id in answer_ids if answer_owner.get(answer_id, "")})
        else:
            candidate_ids = members
            answer_ids = sorted(
                str(answer.get("answer_candidate_id", ""))
                for candidate_id in candidate_ids
                for answer in candidates_by_id.get(candidate_id, {}).get("answer_candidates", [])
                if isinstance(answer, Mapping)
            )
        flags = _cluster_quality_flags(candidate_ids, answer_ids, candidates_by_id, policy)
        records.append(
            {
                "cluster_id": f"tg-{cluster_type.replace('_', '-')}-cluster:{_stable_hash(cluster_type + ':' + '|'.join(members))}",
                "cluster_type": cluster_type,
                "candidate_ids": candidate_ids,
                "answer_candidate_ids": answer_ids,
                "representative_candidate_id": candidate_ids[0] if candidate_ids else "",
                "cluster_size": len(members),
                "cluster_confidence": _cluster_confidence(members, flags),
                "cluster_quality_flags": flags,
                "similarity_thresholds": {
                    "question": policy["question_similarity_threshold"],
                    "answer": policy["answer_similarity_threshold"],
                    "qa_pair": policy["qa_pair_similarity_threshold"],
                },
                "clustering_policy_version": policy["clustering_policy_version"],
                "answer_source_counts": dict(
                    sorted(
                        Counter(
                            str(answer.get("answer_source_type", "unknown"))
                            for candidate_id in candidate_ids
                            for answer in candidates_by_id.get(candidate_id, {}).get("answer_candidates", [])
                            if isinstance(answer, Mapping)
                        ).items()
                    )
                ),
                "answer_link_counts": dict(
                    sorted(
                        Counter(
                            str(answer.get("answer_link_type", "unknown"))
                            for candidate_id in candidate_ids
                            for answer in candidates_by_id.get(candidate_id, {}).get("answer_candidates", [])
                            if isinstance(answer, Mapping)
                        ).items()
                    )
                ),
            }
        )
    return records


def _cluster_quality_flags(
    candidate_ids: list[str],
    answer_ids: list[str],
    candidates_by_id: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> list[str]:
    flags: list[str] = []
    if len(candidate_ids) > int(policy["max_component_size"]):
        flags.append("component_size_exceeds_limit")
    if not answer_ids:
        flags.append("no_answer_candidates")
    topics = [set(candidates_by_id.get(candidate_id, {}).get("topic_labels", [])) for candidate_id in candidate_ids]
    non_empty_topics = [topic for topic in topics if topic]
    if len(non_empty_topics) > 1 and set.intersection(*non_empty_topics) == set():
        flags.append("topic_overlap_missing")
    return flags or ["none"]


def _cluster_confidence(members: list[str], flags: list[str]) -> str:
    if "component_size_exceeds_limit" in flags or "topic_overlap_missing" in flags:
        return "low"
    if len(members) > 1:
        return "high"
    return "medium"


def _is_usable_answer_candidate(answer: Mapping[str, Any], policy: Mapping[str, Any]) -> bool:
    return (
        str(answer.get("answer_candidate_status", "")) in set(policy["auto_select_allowed_answer_statuses"])
        and bool(answer.get("answer_candidate_usable", False))
        and str(answer.get("link_confidence", "")) in set(policy["auto_select_allowed_link_confidences"])
        and str(answer.get("answer_candidate_priority", "")) not in set(policy["auto_select_excluded_answer_priorities"])
        and bool(str(answer.get("text_redacted", "")).strip())
    )


def _answer_variant_payload(
    candidate: Mapping[str, Any],
    answer: Mapping[str, Any],
    answer_cluster_by_answer_id: Mapping[str, str],
) -> dict[str, Any]:
    answer_id = str(answer.get("answer_candidate_id", ""))
    return {
        "candidate_id": str(candidate.get("candidate_id", "")),
        "answer_candidate_id": answer_id,
        "answer_date": str(answer.get("date", "")),
        "answer_cluster_id": answer_cluster_by_answer_id.get(answer_id, ""),
        "answer_source_type": str(answer.get("answer_source_type", "")),
        "answer_link_type": str(answer.get("answer_link_type", "")),
        "link_confidence": str(answer.get("link_confidence", "")),
        "answer_candidate_priority": str(answer.get("answer_candidate_priority", "")),
    }


def _date_sort_value(value: str) -> str:
    return value or ""


def _answer_drift_status(
    usable_answers: list[Mapping[str, Any]],
    answer_cluster_by_answer_id: Mapping[str, str],
    policy: Mapping[str, Any],
) -> str:
    if not usable_answers:
        return "insufficient_history"
    if len(usable_answers) == 1:
        return "stable"
    answer_cluster_ids = {
        answer_cluster_by_answer_id.get(str(answer.get("answer_candidate_id", "")), "")
        for answer in usable_answers
    }
    answer_cluster_ids.discard("")
    if not answer_cluster_ids:
        return "insufficient_history"
    if len(answer_cluster_ids) == 1:
        return "stable"
    if len(usable_answers) <= int(policy["max_component_size"]):
        return "changed"
    return "conflicting"


def _cluster_selection_status(
    *,
    selected_candidate: Mapping[str, Any],
    usable_answers: list[Mapping[str, Any]],
    drift_status: str,
) -> str:
    if not usable_answers:
        return "uncertain"
    confidence = str(selected_candidate.get("confidence_tier", ""))
    if drift_status == "stable" and confidence == "high":
        return "auto_selected"
    if drift_status in {"stable", "changed"}:
        return "needs_llm_review"
    if drift_status == "conflicting":
        return "needs_manual_review"
    return "needs_manual_review"


def _selection_reasons(selection_status: str, drift_status: str, usable: list[Mapping[str, Any]]) -> list[str]:
    reasons = [f"answer_drift_status:{drift_status}"]
    if usable:
        reasons.append("latest_usable_answer_selected_inside_qa_cluster")
    else:
        reasons.append("no_usable_answer_candidate")
    if selection_status == "auto_selected":
        reasons.append("high_confidence_stable_cluster")
    if selection_status == "needs_llm_review":
        reasons.append("requires_classifier_or_review_evidence")
    if selection_status == "needs_manual_review":
        reasons.append("requires_human_review")
    return reasons


def _selection_review_route(selection_status: str, drift_status: str) -> str:
    if selection_status == "auto_selected":
        return "final_dataset_candidate"
    if selection_status == "needs_llm_review":
        return "llm_review_then_manual_if_needed"
    if drift_status == "conflicting":
        return "manual_review"
    return "manual_or_uncertain"


def _selection_needs_llm(selection: Mapping[str, Any]) -> bool:
    return (
        str(selection.get("selection_status", "")) == "needs_llm_review"
        or str(selection.get("answer_drift_status", "")) in {"changed", "conflicting", "insufficient_history"}
    )


def _selection_needs_manual_review(selection: Mapping[str, Any]) -> bool:
    return str(selection.get("selection_status", "")) in {"needs_manual_review", "needs_llm_review", "uncertain"} or str(
        selection.get("answer_drift_status", "")
    ) == "conflicting"


def _candidate_llm_input(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": str(candidate.get("candidate_id", "")),
        "question_text_redacted": str(candidate.get("question_text_redacted", "")),
        "topic_labels": list(candidate.get("topic_labels", [])),
        "law_code_candidates": list(candidate.get("law_code_candidates", [])),
        "answer_candidates": candidate.get("answer_candidates", []),
        "trigger_evidence": candidate.get("trigger_evidence", []),
        "confidence_tier": str(candidate.get("confidence_tier", "")),
        "quality_flags": list(candidate.get("quality_flags", [])),
    }


def _active_tg_qa_prompt_profile(prompt_version: str) -> Mapping[str, Any]:
    if prompt_version == LLM_CANDIDATE_PROMPT_VERSION:
        return TG_QA_CANDIDATE_PROMPT_PROFILE
    if prompt_version == LLM_CLUSTER_PROMPT_VERSION:
        return TG_QA_CLUSTER_PROMPT_PROFILE
    if prompt_version == LLM_CLUSTER_COMPACT_PROMPT_VERSION:
        return TG_QA_CLUSTER_COMPACT_PROMPT_PROFILE
    return {}


def _active_tg_qa_user_prompt_lines(prompt_version: str) -> list[str]:
    profile = _active_tg_qa_prompt_profile(prompt_version)
    raw_lines = profile.get("user_prompt_lines", [])
    if isinstance(raw_lines, list) and raw_lines:
        return [str(line) for line in raw_lines]
    return [
        "You classify redacted Telegram Q/A evidence for an evaluation dataset.",
        "Do not treat answers as legal truth. Do not approve final records.",
        "If Input.review_overlay exists, use that corrected question/reference answer as primary evidence for this prompt comparison. Do not infer the human label from the overlay.",
        "For normalized_question, keep the source user's language; do not translate Russian/Ukrainian/German questions into English.",
        "Keep German legal names and section references as terms inside the preserved-language question.",
        "Do not classify by topic words alone. Ask whether a correct answer requires legally precise analysis.",
        "Approve only if the question is useful for comparing a future graph-backed answer with a reference answer.",
        "Reject cases where the main intent is rhetoric, grievance, small talk, emotional support, local logistics, or general discussion, even when the text mentions legal-adjacent entities.",
        "Set issue_spotting_required=true only when an answer that follows the user's surface wording would be materially incomplete, misleading, or legally risky unless hidden duties, risks, status conditions, or reporting obligations are identified.",
        "Do not set issue_spotting_required=true for every ordinary legal question; use it only for concealed cross-domain legal implications.",
        "Return issue_spotting_level with this scale: none means no hidden expansion; low means useful surrounding legal context but the direct answer still works; medium means hidden issues noticeably change answer completeness; high means omitting hidden issues would be materially misleading or legally risky.",
        "Return issue_spotting_confidence as low, medium, or high. Keep issue_spotting_reason short and factual.",
        "Use hidden_legal_issue_categories as broad taxonomy labels only. Return at most five labels from the schema list; use other only when no listed category fits.",
        "Calibration examples: health insurance with foreign income may require hidden issue spotting for self-employment, tax duties, and income reporting; a complaint asking why Germany or an authority behaves unfairly is rhetorical unless it asks a concrete entitlement, deadline, remedy, or procedure; a question only about where to pick up a card is practical logistics.",
        "Return exactly one JSON object. No markdown. No prose.",
    ]


def _cluster_llm_batch_item(
    *,
    qa_cluster_id: str,
    selection: Mapping[str, Any],
    candidates: list[Mapping[str, Any]],
    prompt_profile: str,
    input_char_budget: int,
    manual_overlay: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if prompt_profile == "compact":
        prompt_version = LLM_CLUSTER_COMPACT_PROMPT_VERSION
        prompt_profile_data = _active_tg_qa_prompt_profile(prompt_version)
        input_payload = _compact_cluster_llm_input(
            qa_cluster_id=qa_cluster_id,
            selection=selection,
            candidates=candidates,
            input_char_budget=input_char_budget or LLM_COMPACT_INPUT_CHAR_BUDGET,
            manual_overlay=manual_overlay,
        )
    else:
        prompt_version = LLM_CLUSTER_PROMPT_VERSION
        prompt_profile_data = _active_tg_qa_prompt_profile(prompt_version)
        input_payload = {
            "qa_cluster_id": qa_cluster_id,
            "selection": selection,
            "candidates": [_candidate_llm_input(candidate) for candidate in candidates],
        }
        if manual_overlay:
            input_payload["review_overlay"] = dict(manual_overlay)
    return {
        "task_id": qa_cluster_id,
        "task_type": "tg_qa_cluster_review",
        "task_scope": "qa_cluster",
        "runtime_hint": "operator_managed_llama_server_openai_compatible",
        "llm_contract_version": LLM_CONTRACT_VERSION,
        "prompt_version": prompt_version,
        "prompt_profile": prompt_profile,
        "input_char_budget": input_char_budget,
        "system_instruction": str(prompt_profile_data["system_instruction"]),
        "input": input_payload,
        "expected_output_schema": _llm_expected_output_schema(),
    }


def _llm_expected_output_schema() -> dict[str, str]:
    return dict(TG_QA_CANDIDATE_PROMPT_PROFILE["expected_output_schema"])


def _compact_cluster_llm_input(
    *,
    qa_cluster_id: str,
    selection: Mapping[str, Any],
    candidates: list[Mapping[str, Any]],
    input_char_budget: int,
    manual_overlay: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    candidate_order = _ordered_cluster_candidates(selection, candidates)
    profiles = [
        {"candidate_limit": 4, "answer_limit": 3, "question_chars": 420, "answer_chars": 700, "trigger_chars": 160},
        {"candidate_limit": 3, "answer_limit": 2, "question_chars": 320, "answer_chars": 420, "trigger_chars": 120},
        {"candidate_limit": 2, "answer_limit": 2, "question_chars": 260, "answer_chars": 260, "trigger_chars": 80},
        {"candidate_limit": 1, "answer_limit": 1, "question_chars": 220, "answer_chars": 180, "trigger_chars": 0},
    ]
    selected_profile = profiles[-1]
    payload = {}
    for profile in profiles:
        selected_profile = profile
        payload = _compact_cluster_llm_input_with_profile(
            qa_cluster_id=qa_cluster_id,
            selection=selection,
            candidates=candidate_order[: int(profile["candidate_limit"])],
            answer_limit=int(profile["answer_limit"]),
            question_chars=int(profile["question_chars"]),
            answer_chars=int(profile["answer_chars"]),
            trigger_chars=int(profile["trigger_chars"]),
            input_char_budget=input_char_budget,
            manual_overlay=manual_overlay,
        )
        if input_char_budget <= 0 or _serialized_chars(payload) <= input_char_budget:
            break
    payload["budget"] = {
        "input_char_budget": input_char_budget,
        "serialized_input_chars": _serialized_chars(payload),
        "profile_candidate_limit": selected_profile["candidate_limit"],
        "profile_answer_limit": selected_profile["answer_limit"],
        "profile_question_chars": selected_profile["question_chars"],
        "profile_answer_chars": selected_profile["answer_chars"],
        "profile_trigger_chars": selected_profile["trigger_chars"],
        "full_candidate_count": len(candidates),
        "included_candidate_count": len(payload.get("candidates", [])),
        "truncation_policy": "latest_and_selected_evidence_first_text_truncated_for_small_context_llm",
    }
    return payload


def _compact_cluster_llm_input_with_profile(
    *,
    qa_cluster_id: str,
    selection: Mapping[str, Any],
    candidates: list[Mapping[str, Any]],
    answer_limit: int,
    question_chars: int,
    answer_chars: int,
    trigger_chars: int,
    input_char_budget: int,
    manual_overlay: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selected_answer_id = str(selection.get("selected_answer_candidate_id", ""))
    payload = {
        "qa_cluster_id": qa_cluster_id,
        "task": (
            "Classify whether this redacted chat cluster is usable evaluation evidence. "
            "Prefer uncertain or manual review when evidence is thin. Do not approve final records."
        ),
        "selection": {
            "selection_status": str(selection.get("selection_status", "")),
            "selected_candidate_id": str(selection.get("selected_candidate_id", "")),
            "selected_answer_candidate_id": selected_answer_id,
            "selected_answer_date": str(selection.get("selected_answer_date", "")),
            "historical_answer_variant_count": int(selection.get("historical_answer_variant_count", 0) or 0),
            "answer_drift_status": str(selection.get("answer_drift_status", "")),
            "selection_reasons": list(selection.get("selection_reasons", [])),
            "cluster_quality_flags": list(selection.get("cluster_quality_flags", [])),
        },
        "candidates": [
            _compact_candidate_llm_input(
                candidate,
                selected_answer_id=selected_answer_id,
                answer_limit=answer_limit,
                question_chars=question_chars,
                answer_chars=answer_chars,
                trigger_chars=trigger_chars,
            )
            for candidate in candidates
        ],
        "expected_output_keys": list(_llm_expected_output_schema().keys()),
        "context_note": {
            "profile": "compact_small_context",
            "input_char_budget": input_char_budget,
            "full_cluster_context_available_in_companion_batch": True,
        },
    }
    if manual_overlay:
        payload["review_overlay"] = dict(manual_overlay)
    return payload


def _ordered_cluster_candidates(
    selection: Mapping[str, Any],
    candidates: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    selected_candidate_id = str(selection.get("selected_candidate_id", ""))

    def sort_key(candidate: Mapping[str, Any]) -> tuple[int, str, str]:
        return (
            0 if str(candidate.get("candidate_id", "")) == selected_candidate_id else 1,
            str(candidate.get("question_date", "")),
            str(candidate.get("candidate_id", "")),
        )

    return sorted(candidates, key=sort_key)


def _compact_candidate_llm_input(
    candidate: Mapping[str, Any],
    *,
    selected_answer_id: str,
    answer_limit: int,
    question_chars: int,
    answer_chars: int,
    trigger_chars: int,
) -> dict[str, Any]:
    answers = [
        answer
        for answer in candidate.get("answer_candidates", [])
        if isinstance(answer, Mapping)
    ]
    answers = sorted(
        answers,
        key=lambda answer: (
            0 if str(answer.get("answer_candidate_id", "")) == selected_answer_id else 1,
            str(answer.get("date", "")),
            str(answer.get("answer_candidate_id", "")),
        ),
    )
    triggers = [
        trigger
        for trigger in candidate.get("trigger_evidence", [])
        if isinstance(trigger, Mapping)
    ]
    return {
        "candidate_id": str(candidate.get("candidate_id", "")),
        "question_date": str(candidate.get("question_date", "")),
        "question_text_redacted": _truncate_text(str(candidate.get("question_text_redacted", "")), question_chars),
        "topic_labels": list(candidate.get("topic_labels", [])),
        "law_code_candidates": list(candidate.get("law_code_candidates", [])),
        "confidence_tier": str(candidate.get("confidence_tier", "")),
        "quality_flags": list(candidate.get("quality_flags", [])),
        "answer_source_counts": dict(candidate.get("answer_source_counts", {})),
        "answer_link_counts": dict(candidate.get("answer_link_counts", {})),
        "known_bot_answer_via_trigger_count": int(candidate.get("known_bot_answer_via_trigger_count", 0) or 0),
        "answers": [
            {
                "answer_candidate_id": str(answer.get("answer_candidate_id", "")),
                "date": str(answer.get("date", "")),
                "answer_source_type": str(answer.get("answer_source_type", "")),
                "answer_link_type": str(answer.get("answer_link_type", "")),
                "link_confidence": str(answer.get("link_confidence", "")),
                "answer_candidate_status": str(answer.get("answer_candidate_status", "")),
                "answer_candidate_priority": str(answer.get("answer_candidate_priority", "")),
                "text_redacted": _truncate_text(str(answer.get("text_redacted", "")), answer_chars),
            }
            for answer in answers[:answer_limit]
        ],
        "trigger_samples": [
            {
                "trigger_link_type": str(trigger.get("trigger_link_type", "")),
                "link_confidence": str(trigger.get("link_confidence", "")),
                "trigger_text_redacted": _truncate_text(str(trigger.get("trigger_text_redacted", "")), trigger_chars),
            }
            for trigger in triggers[:2]
            if trigger_chars > 0
        ],
    }


def _serialized_input_chars(item: Mapping[str, Any]) -> int:
    return _serialized_chars(item.get("input", {}))


def _serialized_chars(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _truncate_text(value: str, max_chars: int) -> str:
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    return value[: max(0, max_chars)].rstrip() + " [truncated]"


def _llm_chat_payload(
    task: Mapping[str, Any],
    *,
    model_id: str,
    max_tokens: int,
    response_format_json: bool,
    reasoning_effort: str = "",
    thinking_type: str = "",
    omit_temperature: bool = False,
    extra_body: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": _llm_user_prompt(task),
            }
        ],
        "max_tokens": max_tokens,
    }
    if not omit_temperature:
        payload["temperature"] = 0
    if response_format_json:
        payload["response_format"] = {"type": "json_object"}
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    if thinking_type:
        payload["thinking"] = {"type": thinking_type}
    if extra_body:
        payload.update(dict(extra_body))
    return payload


def _llm_user_prompt(task: Mapping[str, Any]) -> str:
    expected_schema = json.dumps(task.get("expected_output_schema", {}), ensure_ascii=False, sort_keys=True)
    task_input = json.dumps(task.get("input", {}), ensure_ascii=False, sort_keys=True)
    prompt_lines = _active_tg_qa_user_prompt_lines(str(task.get("prompt_version", "")))
    return "\n".join(
        [
            *prompt_lines,
            f"Required JSON schema hints: {expected_schema}",
            f"Task scope: {task.get('task_scope', '')}",
            f"Task id: {task.get('task_id', '')}",
            f"Input: {task_input}",
        ]
    )


def _chat_completion_url(endpoint_url: str) -> str:
    stripped = endpoint_url.rstrip("/")
    if stripped.endswith("/v1/chat/completions"):
        return stripped
    if stripped.endswith("/v1"):
        return stripped + "/chat/completions"
    return stripped + "/v1/chat/completions"


def _openai_chat_completion_transport(
    endpoint_url: str,
    *,
    timeout_seconds: int,
    api_key: str = "",
    user_agent: str = "chat_bot2-evaluation-runner/006",
) -> LlmTransport:
    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = request.Request(
            endpoint_url,
            data=body,
            headers=headers,
            method="POST",
        )
        with request.urlopen(req, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    return transport


def _api_key_from_env(api_key_env: str) -> str:
    if not api_key_env:
        return ""
    value = os.environ.get(api_key_env, "")
    if not value:
        raise ValueError(f"environment variable {api_key_env} is not set")
    return value


def _llm_endpoint_error_reason(exc: Exception) -> str:
    if isinstance(exc, error.HTTPError):
        body = _clean_text(exc.read().decode("utf-8", errors="replace"))[:500]
        return f"http_error:{exc.code}:{body}"
    return f"endpoint_error:{type(exc).__name__}"


def _llm_response_text(response: Mapping[str, Any]) -> str:
    choices = response.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, Mapping):
        return ""
    message = first.get("message", {})
    if isinstance(message, Mapping) and isinstance(message.get("content"), str):
        return str(message.get("content", ""))
    if isinstance(first.get("text"), str):
        return str(first.get("text", ""))
    return ""


def _llm_response_diagnostics(response: Mapping[str, Any]) -> str:
    choices = response.get("choices", [])
    first = choices[0] if isinstance(choices, list) and choices else {}
    finish_reason = str(first.get("finish_reason", "")) if isinstance(first, Mapping) else ""
    message = first.get("message", {}) if isinstance(first, Mapping) else {}
    content = str(message.get("content", "")) if isinstance(message, Mapping) else ""
    reasoning = str(message.get("reasoning_content", "")) if isinstance(message, Mapping) else ""
    usage = response.get("usage", {})
    total_tokens = usage.get("total_tokens", "") if isinstance(usage, Mapping) else ""
    completion_tokens = usage.get("completion_tokens", "") if isinstance(usage, Mapping) else ""
    reasoning_tokens = ""
    if isinstance(usage, Mapping):
        details = usage.get("completion_tokens_details", {})
        if isinstance(details, Mapping):
            reasoning_tokens = str(details.get("reasoning_tokens", ""))
    return (
        f"finish_reason={finish_reason};content_chars={len(content)};"
        f"reasoning_chars={len(reasoning)};completion_tokens={completion_tokens};"
        f"reasoning_tokens={reasoning_tokens};total_tokens={total_tokens}"
    )


def _extract_first_json_object(text: str) -> tuple[dict[str, Any], str]:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            payload, _offset = decoder.raw_decode(text[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload, ""
    return {}, "missing_json_object"


def _llm_result_record_from_model_output(
    task: Mapping[str, Any],
    model_output: Mapping[str, Any],
    *,
    llm_run_id: str,
    runtime_contour: str,
    backend: str,
    model_file: str,
    model_id: str,
    quantization: str,
) -> dict[str, Any]:
    required_fields = set(LLM_REQUIRED_OUTPUT_FIELDS)
    missing_fields = sorted(field for field in required_fields if field not in model_output)
    recommendation = str(model_output.get("recommended_selection_status", ""))
    if missing_fields:
        return _failed_llm_result_record(
            task,
            llm_run_id=llm_run_id,
            failure_reason="missing_required_fields:" + ",".join(missing_fields),
            runtime_contour=runtime_contour,
            backend=backend,
            model_file=model_file,
            model_id=model_id,
            quantization=quantization,
        )
    if recommendation not in ALLOWED_LLM_RECOMMENDATIONS:
        return _failed_llm_result_record(
            task,
            llm_run_id=llm_run_id,
            failure_reason="invalid_recommended_selection_status",
            runtime_contour=runtime_contour,
            backend=backend,
            model_file=model_file,
            model_id=model_id,
            quantization=quantization,
        )
    record = _llm_result_record_base(
        task,
        llm_run_id=llm_run_id,
        runtime_contour=runtime_contour,
        backend=backend,
        model_file=model_file,
        model_id=model_id,
        quantization=quantization,
    )
    record.update({key: model_output[key] for key in LLM_REQUIRED_OUTPUT_FIELDS})
    for key, default in LLM_OPTIONAL_OUTPUT_DEFAULTS.items():
        record[key] = _normalize_llm_optional_field(key, model_output.get(key, default))
    record["status"] = "completed"
    record["failure_reason"] = ""
    return record


def _normalize_llm_optional_field(key: str, value: Any) -> Any:
    if key in {"issue_spotting_required", "answer_must_expand_beyond_user_wording"}:
        return _parse_boolish(value)
    if key == "issue_spotting_level":
        return _normalize_enum_value(value, allowed=ISSUE_SPOTTING_LEVELS, default="unclassified")
    if key == "issue_spotting_confidence":
        return _normalize_enum_value(value, allowed=ISSUE_SPOTTING_CONFIDENCE_LEVELS, default="unclassified")
    if key == "hidden_legal_issue_categories":
        return _normalize_hidden_legal_issue_categories(value)
    if value is None or value == "":
        return LLM_OPTIONAL_OUTPUT_DEFAULTS.get(key, "")
    return str(value)


def _normalize_enum_value(value: Any, *, allowed: tuple[str, ...], default: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    return normalized if normalized in set(allowed) else default


def _normalize_hidden_legal_issue_categories(value: Any) -> list[str]:
    allowed = set(HIDDEN_LEGAL_ISSUE_CATEGORY_TAXONOMY)
    normalized: list[str] = []
    for raw_item in _string_list(value):
        item = re.sub(r"[^a-z0-9]+", "_", raw_item.lower()).strip("_")
        item = HIDDEN_LEGAL_ISSUE_CATEGORY_ALIASES.get(item, item)
        if item not in allowed:
            item = "other"
        if item not in normalized:
            normalized.append(item)
        if len(normalized) >= 5:
            break
    return normalized


def _failed_llm_result_record(
    task: Mapping[str, Any],
    *,
    llm_run_id: str,
    failure_reason: str,
    runtime_contour: str,
    backend: str,
    model_file: str,
    model_id: str,
    quantization: str,
) -> dict[str, Any]:
    record = _llm_result_record_base(
        task,
        llm_run_id=llm_run_id,
        runtime_contour=runtime_contour,
        backend=backend,
        model_file=model_file,
        model_id=model_id,
        quantization=quantization,
    )
    record["status"] = "failed"
    record["failure_reason"] = failure_reason
    return record


def _llm_result_record_base(
    task: Mapping[str, Any],
    *,
    llm_run_id: str,
    runtime_contour: str,
    backend: str,
    model_file: str,
    model_id: str,
    quantization: str,
) -> dict[str, Any]:
    task_scope = str(task.get("task_scope", ""))
    task_id = str(task.get("task_id", ""))
    return {
        "task_id": task_id,
        "task_scope": task_scope,
        "candidate_id": task_id if task_scope == "candidate" else "",
        "qa_cluster_id": task_id if task_scope == "qa_cluster" else "",
        "llm_run_id": llm_run_id,
        "llm_contract_version": str(task.get("llm_contract_version", LLM_CONTRACT_VERSION)),
        "prompt_version": str(task.get("prompt_version", "")),
        "runtime_contour": runtime_contour,
        "backend": backend,
        "model_file": model_file,
        "model_id": model_id,
        "quantization": quantization,
    }


def _validate_llm_result(
    payload: Mapping[str, Any],
    tasks_by_id: Mapping[str, Mapping[str, Any]],
    *,
    default_run_id: str,
) -> tuple[dict[str, Any], str]:
    task_id = str(payload.get("task_id", ""))
    task_scope = str(payload.get("task_scope", ""))
    status = str(payload.get("status", ""))
    run_id = str(payload.get("llm_run_id", default_run_id))
    if not task_id or task_id not in tasks_by_id:
        return {}, "unknown_or_missing_task_id"
    expected_task = tasks_by_id[task_id]
    if task_scope not in ALLOWED_LLM_TASK_SCOPES or task_scope != expected_task.get("task_scope"):
        return {}, "invalid_task_scope"
    if not run_id:
        return {}, "missing_llm_run_id"
    if status not in ALLOWED_LLM_STATUSES:
        return {}, "invalid_status"
    if not payload.get("llm_contract_version") or not payload.get("prompt_version"):
        return {}, "missing_contract_or_prompt_version"
    recommendation = str(payload.get("recommended_selection_status", ""))
    if recommendation and recommendation not in ALLOWED_LLM_RECOMMENDATIONS:
        return {}, "invalid_or_direct_approval_recommendation"
    evidence = dict(payload)
    evidence["llm_run_id"] = run_id
    evidence["review_evidence_type"] = "llm_analysis"
    evidence["selection_status_effect"] = "review_evidence_only"
    evidence["can_create_final_record"] = False
    if task_scope == "candidate":
        evidence.setdefault("candidate_id", task_id)
        evidence.setdefault("qa_cluster_id", "")
    else:
        evidence.setdefault("qa_cluster_id", task_id)
    return evidence, ""


def _first_non_empty(values: Iterable[str]) -> str:
    for value in values:
        if value:
            return value
    return ""


def _find_answer_candidate(candidate: Mapping[str, Any], answer_candidate_id: str) -> dict[str, Any]:
    for answer in candidate.get("answer_candidates", []):
        if isinstance(answer, Mapping) and str(answer.get("answer_candidate_id", "")) == answer_candidate_id:
            return dict(answer)
    return {}


def _human_review_record(item: Mapping[str, Any], *, index: int, max_text_chars: int) -> dict[str, Any]:
    llm_note = _primary_llm_note(item)
    selected_answer = item.get("selected_answer_candidate", {})
    answer_text = str(selected_answer.get("text_redacted", "")) if isinstance(selected_answer, Mapping) else ""
    candidate_ids = [str(value) for value in item.get("candidate_ids", []) if value]
    selected_candidate_id = str(item.get("selected_candidate_id", "")) or (candidate_ids[0] if candidate_ids else "")
    selected_answer_candidate_id = str(item.get("selected_answer_candidate_id", ""))
    if not selected_answer_candidate_id and isinstance(selected_answer, Mapping):
        selected_answer_candidate_id = str(selected_answer.get("answer_candidate_id", ""))
    question_text = str(item.get("redacted_question", ""))
    normalized_question = str(llm_note.get("normalized_question", "")) or question_text
    summary = str(llm_note.get("short_answer_summary", ""))
    question_dialogue_role, dialogue_issue_signals = _question_dialogue_role(
        original_question=question_text,
        normalized_question=normalized_question,
        reference_answer=answer_text,
    )
    score, signals = _human_review_interest_score(
        item=item,
        llm_note=llm_note,
        normalized_question=normalized_question,
        selected_answer_text=answer_text,
        extra_signals=dialogue_issue_signals,
    )
    bucket = _human_review_bucket(llm_note=llm_note, score=score, signals=signals)
    suggested_decision = _human_review_suggested_decision(llm_note=llm_note, signals=signals, bucket=bucket)
    answer_status = _human_review_reference_answer_status(llm_note=llm_note, answer_text=answer_text, signals=signals)
    suggested_reference_answer_action = _suggested_reference_answer_action(answer_status)
    answer_issue_signals = [
        signal
        for signal in signals
        if signal.startswith("answer_") or signal in {"meta_or_non_answer", "conflicting_history", "changed_history"}
    ]
    return {
        "source_index": index,
        "rank": index,
        "review_queue_id": str(item.get("review_queue_id", "")),
        "qa_cluster_id": str(item.get("qa_cluster_id", "")),
        "selected_candidate_id": selected_candidate_id,
        "selected_answer_candidate_id": selected_answer_candidate_id,
        "bucket": bucket,
        "suggested_decision": suggested_decision,
        "decision_scope": HUMAN_REVIEW_DECISION_SCOPE,
        "interest_score": score,
        "signals": signals,
        "question_dialogue_role": question_dialogue_role,
        "dialogue_issue_signals": dialogue_issue_signals,
        "answer_issue_signals": answer_issue_signals,
        "topic_relevance": str(llm_note.get("current_topic_relevance", "")),
        "question_intent": str(llm_note.get("question_intent", "")),
        "legal_answer_requirement": str(llm_note.get("legal_answer_requirement", "")),
        "graph_db_evaluation_fit": str(llm_note.get("graph_db_evaluation_fit", "")),
        "issue_spotting_required": _parse_boolish(llm_note.get("issue_spotting_required", False)),
        "issue_spotting_level": str(llm_note.get("issue_spotting_level", "unclassified")),
        "issue_spotting_confidence": str(llm_note.get("issue_spotting_confidence", "unclassified")),
        "issue_spotting_reason": str(llm_note.get("issue_spotting_reason", "")),
        "hidden_legal_issue_categories": _string_list(llm_note.get("hidden_legal_issue_categories", [])),
        "answer_must_expand_beyond_user_wording": _parse_boolish(
            llm_note.get("answer_must_expand_beyond_user_wording", False)
        ),
        "exclusion_reason": str(llm_note.get("exclusion_reason", "")),
        "answer_quality": str(llm_note.get("answer_candidate_quality", "")),
        "reference_answer_status": answer_status,
        "suggested_reference_answer_action": suggested_reference_answer_action,
        "reference_answer_action": "",
        "manual_reference_answer_text": "",
        "manual_question_text": "",
        "reference_answer_role": REFERENCE_ANSWER_ROLE,
        "llm_recommendation": str(llm_note.get("recommended_selection_status", "")),
        "needs_human_review": bool(llm_note.get("needs_human_review", False)),
        "drift_or_conflict": str(llm_note.get("drift_or_conflict_assessment", "")),
        "answer_drift_status": str(item.get("answer_drift_status", "")),
        "original_redacted_question": _truncate_text(question_text, max_text_chars),
        "normalized_question": _truncate_text(normalized_question, max_text_chars),
        "reference_answer": _truncate_text(answer_text, max_text_chars),
        "selected_answer": _truncate_text(answer_text, max_text_chars),
        "llm_summary": _truncate_text(summary, max_text_chars),
        "selected_answer_date": str(selected_answer.get("date", "")) if isinstance(selected_answer, Mapping) else "",
        "selected_answer_source_type": str(selected_answer.get("answer_source_type", "")) if isinstance(selected_answer, Mapping) else "",
        "selected_answer_link_type": str(selected_answer.get("answer_link_type", "")) if isinstance(selected_answer, Mapping) else "",
        "decision": "",
        "decision_reason": "",
    }


def _primary_llm_note(item: Mapping[str, Any]) -> dict[str, Any]:
    for note in item.get("llm_notes", []):
        if isinstance(note, Mapping) and str(note.get("status", "")) == "completed":
            return dict(note)
    for note in item.get("llm_notes", []):
        if isinstance(note, Mapping):
            return dict(note)
    return {}


def _human_review_interest_score(
    *,
    item: Mapping[str, Any],
    llm_note: Mapping[str, Any],
    normalized_question: str,
    selected_answer_text: str,
    extra_signals: list[str] | None = None,
) -> tuple[int, list[str]]:
    score = 0
    signals: list[str] = list(extra_signals or [])
    if "dialogue_clarification_question" in signals or "dialogue_context_fragment" in signals:
        score -= 80
    if bool(llm_note.get("is_real_user_question", False)):
        score += 35
        signals.append("real_question")
    elif llm_note:
        score -= 30
        signals.append("not_real_question")
    else:
        signals.append("question_not_llm_reviewed")
    relevance = str(llm_note.get("current_topic_relevance", ""))
    if relevance == "high":
        score += 45
        signals.append("topic_high")
    elif relevance == "medium":
        score += 25
        signals.append("topic_medium")
    elif relevance == "low":
        score -= 35
        signals.append("topic_low")
    else:
        signals.append("topic_unknown")
    graph_fit = str(llm_note.get("graph_db_evaluation_fit", ""))
    if graph_fit == "legal_core":
        score += 45
        signals.append("graph_fit_legal_core")
    elif graph_fit == "legal_adjacent":
        score += 25
        signals.append("graph_fit_legal_adjacent")
    elif graph_fit == "not_fit":
        score -= 60
        signals.append("graph_fit_not_fit")
    elif graph_fit:
        signals.append(f"graph_fit_{graph_fit}")
    question_intent = str(llm_note.get("question_intent", ""))
    if question_intent in {"rhetorical_or_discussion", "announcement_or_resource"}:
        score -= 50
        signals.append(f"intent_{question_intent}")
    elif question_intent:
        signals.append(f"intent_{question_intent}")
    legal_requirement = str(llm_note.get("legal_answer_requirement", ""))
    if legal_requirement == "requires_hidden_issue_spotting":
        score += 30
        signals.append("requires_hidden_issue_spotting")
    elif legal_requirement == "requires_legal_rule_or_status_analysis":
        score += 25
        signals.append("requires_legal_rule_or_status_analysis")
    elif legal_requirement in {"practical_only", "nonlegal"}:
        score -= 40
        signals.append(f"legal_requirement_{legal_requirement}")
    elif legal_requirement:
        signals.append(f"legal_requirement_{legal_requirement}")
    if _parse_boolish(llm_note.get("issue_spotting_required", False)):
        score += 20
        signals.append("issue_spotting_required")
    if _parse_boolish(llm_note.get("answer_must_expand_beyond_user_wording", False)):
        signals.append("answer_must_expand_beyond_user_wording")
    exclusion_reason = str(llm_note.get("exclusion_reason", ""))
    if exclusion_reason and exclusion_reason != "none":
        score -= 35
        signals.append(f"exclusion_{exclusion_reason}")
    question_len = len(normalized_question)
    if question_len >= 30:
        score += 10
        signals.append("question_has_context")
    elif question_len < 12:
        score -= 15
        signals.append("question_too_short")
    if item.get("topic_labels"):
        score += 5
        signals.append("topic_label_present")
    if item.get("law_code_candidates"):
        score += 5
        signals.append("law_candidate_present")
    recommendation = str(llm_note.get("recommended_selection_status", ""))
    if recommendation == "rejected":
        score -= 15
        signals.append("llm_rejected_question")
    elif recommendation == "needs_manual_review":
        signals.append("llm_manual_review")
    if bool(llm_note.get("needs_human_review", False)):
        signals.append("llm_human_needed")
    elif llm_note:
        signals.append("llm_no_human_needed")

    quality = str(llm_note.get("answer_candidate_quality", ""))
    if quality == "strong":
        signals.append("answer_strong")
    elif quality == "partial":
        signals.append("answer_partial")
    elif quality == "conflicting":
        signals.append("answer_conflicting")
    elif quality == "none":
        signals.append("answer_none")
    if str(llm_note.get("drift_or_conflict_assessment", "")) == "conflicting":
        signals.append("conflicting_history")
    if str(item.get("answer_drift_status", "")) == "changed":
        signals.append("changed_history")
    answer_len = len(selected_answer_text)
    if answer_len < 50:
        signals.append("answer_too_short")
    elif answer_len <= 900:
        signals.append("answer_readable_length")
    if _looks_like_meta_or_non_answer(selected_answer_text, str(llm_note.get("short_answer_summary", ""))):
        signals.append("meta_or_non_answer")
    return max(0, min(100, score)), signals


def _human_review_bucket(*, llm_note: Mapping[str, Any], score: int, signals: list[str]) -> str:
    relevance = str(llm_note.get("current_topic_relevance", ""))
    if "dialogue_clarification_question" in signals or "dialogue_context_fragment" in signals:
        return "question_reject_dialogue_fragment"
    if (
        "graph_fit_not_fit" in signals
        or "intent_rhetorical_or_discussion" in signals
        or "intent_announcement_or_resource" in signals
        or "legal_requirement_nonlegal" in signals
        or "legal_requirement_practical_only" in signals
    ):
        return "question_reject_low_value"
    if "not_real_question" in signals or relevance == "low":
        return "question_reject_low_value"
    if score >= 75 and bool(llm_note.get("is_real_user_question", False)):
        return "question_inclusion_candidate"
    if score >= 55 or relevance in {"high", "medium"}:
        return "question_manual_review"
    return "question_uncertain_review"


def _human_review_suggested_decision(*, llm_note: Mapping[str, Any], signals: list[str], bucket: str) -> str:
    if bucket == "question_inclusion_candidate":
        return "approve"
    if bucket in {"question_reject_low_value", "question_reject_dialogue_fragment"}:
        return "reject"
    if "question_too_short" in signals or str(llm_note.get("recommended_selection_status", "")) == "needs_manual_review":
        return "needs_more_context"
    return "uncertain"


def _human_review_reference_answer_status(
    *,
    llm_note: Mapping[str, Any],
    answer_text: str,
    signals: list[str],
) -> str:
    if not answer_text.strip() or "answer_none" in signals:
        return "missing_reference_answer"
    if _looks_like_clarifying_question(answer_text):
        return "reference_answer_is_clarifying_question"
    if "meta_or_non_answer" in signals:
        return "reference_answer_probably_not_answer"
    if "answer_conflicting" in signals or str(llm_note.get("drift_or_conflict_assessment", "")) == "conflicting":
        return "reference_answer_conflicting"
    if "answer_partial" in signals:
        return "partial_reference_answer"
    if "answer_strong" in signals:
        return "usable_reference_answer"
    return "unreviewed_reference_answer"


def _suggested_reference_answer_action(reference_answer_status: str) -> str:
    if reference_answer_status in {"usable_reference_answer", "partial_reference_answer", "unreviewed_reference_answer"}:
        return "keep_selected"
    return "replace_manual"


def _question_dialogue_role(
    *,
    original_question: str,
    normalized_question: str,
    reference_answer: str,
) -> tuple[str, list[str]]:
    original_lower = original_question.lower().strip()
    normalized_lower = normalized_question.lower().strip()
    signals: list[str] = []
    if _looks_like_dialogue_context_fragment(original_lower):
        signals.append("dialogue_context_fragment")
    if _looks_like_clarifying_question(normalized_question) or _looks_like_clarifying_question(original_question):
        signals.append("dialogue_clarification_question")
    if _looks_like_short_context_reply(reference_answer):
        signals.append("selected_answer_short_context_reply")
    if _looks_like_clarifying_question(reference_answer):
        signals.append("selected_answer_is_clarifying_question")
    if (
        "dialogue_clarification_question" in signals
        and ("selected_answer_short_context_reply" in signals or "dialogue_context_fragment" in signals)
    ):
        return "dialogue_clarification_question", signals
    if "dialogue_context_fragment" in signals:
        return "dialogue_context_fragment", signals
    if "selected_answer_is_clarifying_question" in signals:
        return "standalone_question_with_clarifying_answer", signals
    return "standalone_question", signals


def _looks_like_dialogue_context_fragment(lowered_text: str) -> bool:
    prefixes = (
        "о, это новость",
        "это большая разница",
        "по-моему",
        "как пишут выше",
        "пока вы",
        "ну а если",
    )
    return any(lowered_text.startswith(prefix) for prefix in prefixes)


def _looks_like_clarifying_question(text: str) -> bool:
    lowered = text.lower().strip()
    prefixes_requiring_question_mark = (
        "у вас",
        "а у вас",
        "вы уже",
        "вам ",
        "вам не",
        "а на ",
        "на мужа",
        "о какой",
        "а в какой",
        "в какой",
        "какой у вас",
        "какая у вас",
        "какие у вас",
    )
    prefixes_without_question_mark = (
        "что значит",
        "подскажите пожалуйста, что значит",
    )
    if any(lowered.startswith(prefix) for prefix in prefixes_without_question_mark):
        return True
    return "?" in lowered and any(lowered.startswith(prefix) for prefix in prefixes_requiring_question_mark)


def _looks_like_short_context_reply(text: str) -> bool:
    lowered = text.lower().strip()
    if len(lowered) > 180:
        return False
    prefixes = (
        "да",
        "нет",
        "на мужа нет",
        "поняла",
        "спасибо",
        "уже",
        "не знаю",
    )
    return any(lowered.startswith(prefix) for prefix in prefixes)


def _looks_like_meta_or_non_answer(answer_text: str, summary: str) -> bool:
    text = f"{answer_text} {summary}".lower()
    markers = (
        "не даёт прямого ответа",
        "не дает прямого ответа",
        "not a legal response",
        "does not answer",
        "irrelevant",
        "accusatory",
        "confrontational",
        "зачем",
        "заняться нечем",
        "в чем у вас проблема",
        "цель вашего сообщения",
        "коллаборант",
        "погугл",
        "гугл",
        "не знаю",
        "спасибо",
    )
    return any(marker in text for marker in markers)


def _human_review_markdown(records: list[dict[str, Any]], summary: Mapping[str, Any]) -> str:
    lines = [
        "# Telegram Q/A Human Review - Question Inclusion",
        "",
        f"Generated at: {summary.get('generated_at', '')}",
        f"Items: {summary.get('review_item_count', 0)}",
        f"Decision scope: `{HUMAN_REVIEW_DECISION_SCOPE}`",
        f"Reference answer role: `{REFERENCE_ANSWER_ROLE}`",
        "",
        "## Summary",
        "",
        f"- Buckets: `{summary.get('counts_by_bucket', {})}`",
        f"- Suggested decisions: `{summary.get('counts_by_suggested_decision', {})}`",
        "- `approve`/`reject` classify whether the question is useful for the evaluation dataset.",
        "- Legal fit is not based on topic words alone. A case fits when the answer requires legal rule/status analysis or hidden issue spotting.",
        "- The reference answer is kept for later comparison with graph DB output. It is not approved as legal truth here.",
        "- If the LLM normalized question is useful but the original Telegram fragment is not, fill `manual_question_text`; it becomes the final dataset question.",
        "- If the question is useful but the selected answer is bad or too verbose, fill `manual_reference_answer_text`; it automatically overrides `keep_selected`.",
        "",
        "## Short Table",
        "",
        "| # | Bucket | Suggested | Score | Relevance | Dialogue Role | Answer Status | Answer Action | Human | Question | Reference Answer | LLM Summary |",
        "|---:|---|---|---:|---|---|---|---|---|---|---|---|",
    ]
    for record in records:
        lines.append(
            "| {rank} | {bucket} | {suggested} | {score} | {relevance} | {dialogue_role} | {answer_status} | {answer_action} | {human} | {question} | {answer} | {summary} |".format(
                rank=record["rank"],
                bucket=_md_cell(str(record["bucket"])),
                suggested=_md_cell(str(record["suggested_decision"])),
                score=record["interest_score"],
                relevance=_md_cell(str(record["topic_relevance"])),
                dialogue_role=_md_cell(str(record["question_dialogue_role"])),
                answer_status=_md_cell(str(record["reference_answer_status"])),
                answer_action=_md_cell(str(record["suggested_reference_answer_action"])),
                human="yes" if record["needs_human_review"] else "no",
                question=_md_cell(_truncate_text(str(record["normalized_question"]), 180)),
                answer=_md_cell(_truncate_text(str(record["reference_answer"]), 220)),
                summary=_md_cell(_truncate_text(str(record["llm_summary"]), 180)),
            )
        )
    lines.extend(["", "## Review Cards", ""])
    for record in records:
        lines.extend(
            [
                f"### {record['rank']}. {record['bucket']} / suggested: {record['suggested_decision']} / score: {record['interest_score']}",
                "",
                f"- `qa_cluster_id`: `{record['qa_cluster_id']}`",
                f"- decision scope: `{record['decision_scope']}`",
                f"- question relevance: `{record['topic_relevance']}`",
                f"- graph DB evaluation fit: `{record['graph_db_evaluation_fit']}`",
                f"- legal answer requirement: `{record['legal_answer_requirement']}`",
                f"- question intent: `{record['question_intent']}`",
                f"- issue spotting required: `{record['issue_spotting_required']}`",
                f"- issue spotting level: `{record['issue_spotting_level']}`",
                f"- issue spotting confidence: `{record['issue_spotting_confidence']}`",
                f"- issue spotting reason: `{record['issue_spotting_reason']}`",
                f"- hidden legal issue categories: `{', '.join(record['hidden_legal_issue_categories'])}`",
                f"- exclusion reason: `{record['exclusion_reason']}`",
                f"- question dialogue role: `{record['question_dialogue_role']}`",
                f"- dialogue issue signals: `{', '.join(record['dialogue_issue_signals'])}`",
                f"- reference answer status: `{record['reference_answer_status']}`",
                f"- suggested reference answer action: `{record['suggested_reference_answer_action']}`",
                f"- reference answer quality label: `{record['answer_quality']}`",
                f"- LLM recommendation: `{record['llm_recommendation']}`, human review: `{record['needs_human_review']}`",
                f"- signals: `{', '.join(record['signals'])}`",
                f"- answer issue signals: `{', '.join(record['answer_issue_signals'])}`",
                "",
                "**Question To Classify**",
                "",
                str(record["normalized_question"]),
                "",
                "**Original Redacted Question**",
                "",
                str(record["original_redacted_question"]),
                "",
                "**Reference Answer For Later Graph DB Comparison**",
                "",
                str(record["reference_answer"]),
                "",
                f"`{REFERENCE_ANSWER_ROLE}`",
                "",
                "**Manual Reference Answer Override**",
                "",
                "Use this when the question should enter the dataset but the selected Telegram answer should not be the reference answer.",
                "Fill `manual_reference_answer_text`; it automatically overrides `keep_selected` during import.",
                "Fill `manual_question_text` when the source Telegram fragment is not the standalone question to evaluate.",
                "",
                "**LLM Summary**",
                "",
                str(record["llm_summary"]),
                "",
                "**Decision JSONL Template**",
                "",
                "```json",
                json.dumps(
                    {
                        "qa_cluster_id": record["qa_cluster_id"],
                        "decision": record["suggested_decision"],
                        "decision_scope": record["decision_scope"],
                        "selected_candidate_id": record["selected_candidate_id"],
                        "selected_answer_candidate_id": record["selected_answer_candidate_id"],
                        "question_intent": record["question_intent"],
                        "legal_answer_requirement": record["legal_answer_requirement"],
                        "graph_db_evaluation_fit": record["graph_db_evaluation_fit"],
                        "issue_spotting_required": record["issue_spotting_required"],
                        "issue_spotting_level": record["issue_spotting_level"],
                        "issue_spotting_confidence": record["issue_spotting_confidence"],
                        "issue_spotting_reason": record["issue_spotting_reason"],
                        "hidden_legal_issue_categories": record["hidden_legal_issue_categories"],
                        "answer_must_expand_beyond_user_wording": record["answer_must_expand_beyond_user_wording"],
                        "exclusion_reason": record["exclusion_reason"],
                        "reference_answer_action": record["suggested_reference_answer_action"],
                        "reference_answer_role": record["reference_answer_role"],
                        "reference_answer_status": record["reference_answer_status"],
                        "manual_question_text": "",
                        "manual_reference_answer_text": "",
                        "decision_reason": "",
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def _human_review_tsv(records: list[dict[str, Any]]) -> str:
    columns = [
        "rank",
        "bucket",
        "suggested_decision",
        "decision_scope",
        "decision",
        "decision_reason",
        "interest_score",
        "topic_relevance",
        "question_intent",
        "legal_answer_requirement",
        "graph_db_evaluation_fit",
        "issue_spotting_required",
        "issue_spotting_level",
        "issue_spotting_confidence",
        "issue_spotting_reason",
        "hidden_legal_issue_categories",
        "answer_must_expand_beyond_user_wording",
        "exclusion_reason",
        "needs_human_review",
        "qa_cluster_id",
        "selected_candidate_id",
        "selected_answer_candidate_id",
        "question_dialogue_role",
        "dialogue_issue_signals",
        "normalized_question",
        "original_redacted_question",
        "reference_answer",
        "reference_answer_status",
        "suggested_reference_answer_action",
        "reference_answer_action",
        "manual_reference_answer_text",
        "manual_question_text",
        "reference_answer_role",
        "answer_quality",
        "selected_answer_source_type",
        "selected_answer_link_type",
        "llm_summary",
        "answer_issue_signals",
        "signals",
    ]
    lines = ["\t".join(columns)]
    for record in records:
        values = []
        for column in columns:
            value = record.get(column, "")
            if column == "signals":
                value = ",".join(record.get("signals", []))
            elif column == "dialogue_issue_signals":
                value = ",".join(record.get("dialogue_issue_signals", []))
            elif column == "answer_issue_signals":
                value = ",".join(record.get("answer_issue_signals", []))
            elif column == "hidden_legal_issue_categories":
                value = ",".join(record.get("hidden_legal_issue_categories", []))
            values.append(_tsv_cell(str(value)))
        lines.append("\t".join(values))
    return "\n".join(lines) + "\n"


def _md_cell(value: str) -> str:
    return _clean_text(value).replace("|", "\\|").replace("\n", " ")


def _tsv_cell(value: str) -> str:
    return _clean_text(value).replace("\t", " ").replace("\n", " ")


def _clean_text(text: str) -> str:
    return SPACE_RE.sub(" ", text).strip()


def _parse_boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "y", "да"}


def _string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = re.split(r"[,;]", str(value))
    items = []
    for item in raw_items:
        text = _clean_text(str(item))
        if text:
            items.append(text)
    return items


def _prefixed_counter(counter: Counter, prefix: str) -> dict[str, int]:
    return {
        key.removeprefix(prefix): value
        for key, value in sorted(counter.items())
        if isinstance(key, str) and key.startswith(prefix)
    }


def _stable_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:16]


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_plain_dict(result: TgQaExtractionResult) -> dict[str, Any]:
    return {
        "candidates": result.candidates,
        "summary": result.summary,
        "embedding_batch_items": result.embedding_batch_items,
        "llm_batch_items": result.llm_batch_items,
    }
