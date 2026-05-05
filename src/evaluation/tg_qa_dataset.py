"""Telegram export question/answer candidate extraction for evaluation datasets."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping


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
    candidates = sorted(candidates, key=_candidate_sort_key)[:max_candidates]
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
        answer_candidates = [
            _answer_payload(reply, export_id=export_id)
            for reply in replies[:5]
        ]
        answer_source_counts = _answer_source_counts(answer_candidates)
        source_message_ids = [
            message.message_id,
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
            "answer_source_counts": answer_source_counts,
            "known_wiki_bot_answer_candidate_count": answer_source_counts.get("known_wiki_bot", 0),
            "other_bot_answer_candidate_count": answer_source_counts.get("other_bot", 0),
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


def _answer_payload(
    message: TelegramMessage,
    *,
    export_id: str,
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
    return {
        "answer_candidate_id": _answer_candidate_id(export_id, message.message_id, message.text),
        "message_id": message.message_id,
        "date": message.date,
        "author_hash": message.author_hash,
        "text_redacted": message.text_redacted,
        "bot_mentions": list(message.bot_mentions),
        "answer_source_type": answer_source_type,
        "answer_source_markers": answer_source_markers,
        "answer_candidate_priority": answer_candidate_priority,
        "author_bot_kind": message.author_bot_kind,
        "known_bot_usernames": list(message.author_bot_usernames),
        "marking_reason": marking_reason,
        "pii_redaction_status": redact_text(message.text)[1],
    }


def _is_question(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in QUESTION_MARKERS)


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


def _answer_source_counts(answer_candidates: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item.get("answer_source_type", "unknown")) for item in answer_candidates)
    return dict(sorted(counts.items()))


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
                "date": str(answer.get("date", "")),
                "embedding_prefix": ANSWER_EMBEDDING_PREFIX.strip(),
                "embedding_input_text": ANSWER_EMBEDDING_PREFIX + text,
                "cluster_usage": ["answer_cluster", "qa_cluster", "temporal_answer_selection"],
                "selection_policy": SELECTION_POLICY,
            }
        )
    return items


def _llm_batch_item(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_id": candidate["candidate_id"],
        "task_type": "tg_qa_candidate_classification",
        "runtime_hint": "openai_compatible_or_langchain_optional",
        "system_instruction": (
            "Classify the redacted Telegram Q/A candidate for evaluation dataset use. "
            "Do not treat the answer as legal truth. Return JSON only."
        ),
        "input": {
            "question_text_redacted": candidate.get("question_text_redacted", ""),
            "answer_candidates": candidate.get("answer_candidates", []),
            "answer_source_counts": candidate.get("answer_source_counts", {}),
            "known_wiki_bot_answer_candidate_count": candidate.get("known_wiki_bot_answer_candidate_count", 0),
            "other_bot_answer_candidate_count": candidate.get("other_bot_answer_candidate_count", 0),
            "topic_labels": candidate.get("topic_labels", []),
            "law_code_candidates": candidate.get("law_code_candidates", []),
            "bot_mentions": candidate.get("bot_mentions", []),
            "confidence_tier": candidate.get("confidence_tier", ""),
            "selection_status": candidate.get("selection_status", ""),
            "review_route": candidate.get("review_route", ""),
            "answer_drift_status": candidate.get("answer_drift_status", ""),
        },
        "expected_output_schema": {
            "is_real_user_question": "boolean",
            "current_topic_relevance": "none|low|medium|high",
            "answer_candidate_quality": "none|partial|strong|conflicting",
            "normalized_question": "string",
            "short_answer_summary": "string",
            "recommended_selection_status": "needs_llm_review|needs_manual_review|uncertain|rejected",
            "needs_human_review": "boolean",
        },
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
    answer_candidate_count = sum(len(candidate.get("answer_candidates", [])) for candidate in candidates)
    known_wiki_bot_answer_count = answer_source_counts.get("known_wiki_bot", 0)
    other_bot_answer_count = answer_source_counts.get("other_bot", 0)
    return {
        "artifact_type": "tg_qa_extraction_summary",
        "generated_at": _utc_timestamp(),
        "input_exports": [str(path) for path in export_paths],
        "bot_catalog_path": str(bot_catalog_path or ""),
        "processed_message_count": processed_message_count,
        "text_message_count": text_message_count,
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
        "known_wiki_bot_answer_candidate_count": known_wiki_bot_answer_count,
        "other_bot_answer_candidate_count": other_bot_answer_count,
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
    output.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def _clean_text(text: str) -> str:
    return SPACE_RE.sub(" ", text).strip()


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
