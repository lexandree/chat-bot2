"""Private dataset snapshots and corpus-bounded exact-reference benchmarks."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import log2, sqrt
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ingestion.legal_reference_parser import parse_explicit_legal_references
from ingestion.legal_structure_builder import build_structural_legal_graph, legal_section_id
from retrieval.embedding_profile import DOCUMENT_PREFIX, QUERY_PREFIX
from retrieval.legal_reference_resolver import ReferenceQuery, resolve_from_section_records


PRIVATE_SNAPSHOT_POLICY_VERSION = "private_artifact_snapshot_v1"
CORPUS_BOUNDED_REFERENCE_BENCHMARK_POLICY_VERSION = "tg_qa_corpus_bounded_explicit_reference_v1"
CORPUS_BOUNDED_SEMANTIC_BATCH_POLICY_VERSION = "tg_qa_corpus_bounded_semantic_embedding_batch_v1"
CORPUS_BOUNDED_SEMANTIC_BENCHMARK_POLICY_VERSION = "tg_qa_corpus_bounded_semantic_retrieval_v1"
RETRIEVAL_RELEVANCE_REVIEW_POLICY_VERSION = "tg_qa_retrieval_relevance_review_v1"
REFERENCE_REVIEW_DECISIONS = {"accept", "exclude", "uncertain"}
RELEVANCE_REVIEW_STATUSES = {"reviewed", "uncertain", "skip"}
EXPLICIT_REFERENCE_ROLES = {"answer_support", "status_context", "incorrect", "uncertain"}


def build_private_artifact_snapshot_manifest(
    *,
    snapshot_name: str,
    artifact_paths: Iterable[str | Path],
    output_path: str | Path,
) -> dict[str, Any]:
    """Write a content-free manifest that identifies a private artifact bundle."""

    normalized_name = snapshot_name.strip()
    if not normalized_name:
        raise ValueError("snapshot_name is required")
    output = Path(output_path)
    paths = sorted({Path(path) for path in artifact_paths}, key=lambda path: str(path))
    if not paths:
        raise ValueError("at least one artifact path is required")
    if output in paths:
        raise ValueError("snapshot output cannot also be an input artifact")

    artifacts = [_private_artifact_identity(path) for path in paths]
    stable_payload = {
        "snapshot_name": normalized_name,
        "policy_version": PRIVATE_SNAPSHOT_POLICY_VERSION,
        "privacy_classification": "private_project_artifact",
        "publication_status": "private_not_for_publication",
        "artifacts": artifacts,
    }
    snapshot_id = _stable_id("private-artifact-snapshot", stable_payload)
    manifest = {
        "artifact_type": "private_artifact_snapshot_manifest",
        "snapshot_id": snapshot_id,
        "generated_at": _utc_timestamp(),
        **stable_payload,
        "artifact_count": len(artifacts),
        "total_byte_count": sum(int(item["byte_count"]) for item in artifacts),
        "contains_record_content": False,
        "known_limitations": [
            "manifest proves local artifact identity but does not contain or publish private records",
            "reproduction requires access to the separately stored private artifacts",
        ],
    }
    _write_json(output, manifest)
    return manifest


def build_tg_qa_corpus_bounded_reference_benchmark(
    *,
    dataset_path: str | Path,
    legal_preview_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    dataset_snapshot_manifest_path: str | Path | None = None,
    law_codes: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Evaluate exact-reference retrieval on private canonical questions.

    Only explicit law-code references in ``canonical_question`` are eligible.
    This makes the expected target query-explicit and avoids pretending that
    semantic retrieval or legal-reference correctness has been labeled.
    """

    dataset_records = _read_jsonl(dataset_path)
    preview = _read_json(legal_preview_path)
    graph = build_structural_legal_graph(preview)
    available_law_codes = sorted({str(item.get("law_code", "")) for item in graph["legal_sections"] if item.get("law_code")})
    selected_law_codes = sorted(set(str(item) for item in (law_codes or available_law_codes) if str(item)))
    unsupported = sorted(set(selected_law_codes).difference(available_law_codes))
    if unsupported:
        raise ValueError(f"selected law codes are absent from legal preview: {unsupported}")
    selected_sections = [
        item for item in graph["legal_sections"] if str(item.get("law_code", "")) in selected_law_codes
    ]
    snapshot_id = _private_snapshot_id(dataset_snapshot_manifest_path)

    cases: list[dict[str, Any]] = []
    excluded_counts: Counter[str] = Counter()
    referenced_query_ids: set[str] = set()
    queries_with_any_explicit_law_reference: set[str] = set()
    seen_case_keys: set[tuple[str, str, str]] = set()
    for record in dataset_records:
        dataset_record_id = str(record.get("dataset_record_id", ""))
        canonical_question = str(record.get("canonical_question", "")).strip()
        if not dataset_record_id or not canonical_question:
            excluded_counts["missing_dataset_record_id_or_canonical_question"] += 1
            continue
        references = parse_explicit_legal_references(canonical_question)
        if not references:
            excluded_counts["no_explicit_section_reference"] += 1
            continue
        for reference in references:
            if not reference.target_law_code_explicit:
                excluded_counts["reference_without_explicit_law_code"] += 1
                continue
            queries_with_any_explicit_law_reference.add(dataset_record_id)
            target_law_code = str(reference.target_law_code)
            target_section_reference = str(reference.target_section_reference)
            if target_law_code not in selected_law_codes:
                excluded_counts["explicit_reference_outside_selected_corpus"] += 1
                continue
            case_key = (dataset_record_id, target_law_code, target_section_reference)
            if case_key in seen_case_keys:
                excluded_counts["duplicate_reference_within_query"] += 1
                continue
            seen_case_keys.add(case_key)
            referenced_query_ids.add(dataset_record_id)
            expected_section_id = legal_section_id(target_law_code, target_section_reference)
            result = resolve_from_section_records(
                ReferenceQuery(law_code=target_law_code, section_reference=target_section_reference),
                selected_sections,
            )
            observed_section_id = result.matched_legal_section_id
            if observed_section_id == expected_section_id:
                outcome = "mechanically_resolved"
            elif not observed_section_id:
                outcome = "missing_target_in_selected_corpus"
            else:
                outcome = "mismatched_target"
            cases.append(
                {
                    "artifact_type": "tg_qa_corpus_bounded_explicit_reference_case",
                    "benchmark_case_id": _stable_id(
                        "tg-qa-explicit-reference-case",
                        {
                            "dataset_record_id": dataset_record_id,
                            "target_law_code": target_law_code,
                            "target_section_reference": target_section_reference,
                        },
                    ),
                    "dataset_snapshot_id": snapshot_id,
                    "dataset_record_id": dataset_record_id,
                    "task_id": str(record.get("task_id", "")),
                    "canonical_question": canonical_question,
                    "raw_reference_text": reference.raw_reference_text,
                    "normalized_reference_text": reference.normalized_reference_text,
                    "target_law_code": target_law_code,
                    "target_section_reference": target_section_reference,
                    "expected_legal_section_id": expected_section_id,
                    "observed_legal_section_id": observed_section_id,
                    "outcome": outcome,
                    "policy_version": CORPUS_BOUNDED_REFERENCE_BENCHMARK_POLICY_VERSION,
                    "trust_boundary": "private_retrieval_evaluation_case_not_legal_authority",
                }
            )

    cases.sort(key=lambda item: str(item["benchmark_case_id"]))
    _write_jsonl(Path(output_path), cases)
    counts_by_outcome = _counts(str(item["outcome"]) for item in cases)
    resolved_count = counts_by_outcome.get("mechanically_resolved", 0)
    reference_case_count = len(cases)
    summary = {
        "artifact_type": "tg_qa_corpus_bounded_explicit_reference_benchmark_summary",
        "benchmark_id": _stable_id(
            "tg-qa-explicit-reference-benchmark",
            {
                "dataset_snapshot_id": snapshot_id,
                "preview_id": str(preview.get("preview_id", "")),
                "selected_law_codes": selected_law_codes,
                "benchmark_case_ids": [item["benchmark_case_id"] for item in cases],
            },
        ),
        "generated_at": _utc_timestamp(),
        "policy_version": CORPUS_BOUNDED_REFERENCE_BENCHMARK_POLICY_VERSION,
        "dataset_snapshot_id": snapshot_id,
        "source_dataset_path": str(dataset_path),
        "source_legal_preview_path": str(legal_preview_path),
        "legal_preview_id": str(preview.get("preview_id", "")),
        "selected_law_codes": selected_law_codes,
        "dataset_record_count": len(dataset_records),
        "query_with_any_explicit_law_reference_count": len(queries_with_any_explicit_law_reference),
        "query_with_in_scope_explicit_reference_count": len(referenced_query_ids),
        "reference_case_count": reference_case_count,
        "counts_by_law_code": _counts(str(item["target_law_code"]) for item in cases),
        "counts_by_outcome": counts_by_outcome,
        "excluded_reference_counts": dict(sorted(excluded_counts.items())),
        "exact_reference_recall_at_1": round(resolved_count / reference_case_count, 6) if reference_case_count else 0.0,
        "metric_scope": "query_explicit_reference_resolution_not_legal_reference_correctness",
        "reference_correctness_review_status": "unreviewed",
        "output_path": str(output_path),
        "privacy_classification": "private_project_artifact",
        "known_limitations": [
            "benchmark covers explicit law-code references only",
            "benchmark does not measure semantic retrieval, reranking, or answer quality",
            "benchmark does not validate whether an LLM-produced legal reference is legally correct",
            "canonical questions and benchmark cases remain private generated artifacts",
        ],
        "trust_boundary": "retrieval_benchmark_does_not_create_trusted_answer_support",
    }
    _write_json(Path(summary_output_path), summary)
    return {"cases": cases, "summary": summary}


def emit_tg_qa_corpus_bounded_semantic_embedding_batch(
    *,
    reference_cases_path: str | Path,
    legal_preview_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    law_codes: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Emit query and legal-section document inputs for a semantic benchmark."""

    reference_cases = _read_jsonl(reference_cases_path)
    preview = _read_json(legal_preview_path)
    graph = build_structural_legal_graph(preview)
    available_law_codes = sorted(
        {str(item.get("law_code", "")) for item in graph["legal_sections"] if item.get("law_code")}
    )
    case_law_codes = {
        str(item.get("target_law_code", ""))
        for item in reference_cases
        if item.get("target_law_code")
    }
    selected_law_codes = sorted(set(str(item) for item in (law_codes or case_law_codes) if str(item)))
    unsupported = sorted(set(selected_law_codes).difference(available_law_codes))
    if unsupported:
        raise ValueError(f"selected law codes are absent from legal preview: {unsupported}")

    selected_sections = sorted(
        [
            item
            for item in graph["legal_sections"]
            if str(item.get("law_code", "")) in selected_law_codes
        ],
        key=lambda item: str(item.get("legal_section_id", "")),
    )
    source_fragments = {
        str(item.get("source_fragment_id", "")): item
        for item in preview.get("source_fragments", [])
        if isinstance(item, Mapping) and item.get("source_fragment_id")
    }
    available_section_ids = {
        str(item.get("legal_section_id", ""))
        for item in selected_sections
        if item.get("legal_section_id")
    }

    query_items: list[dict[str, Any]] = []
    excluded_counts: Counter[str] = Counter()
    for case in sorted(reference_cases, key=lambda item: str(item.get("benchmark_case_id", ""))):
        benchmark_case_id = str(case.get("benchmark_case_id", ""))
        canonical_question = str(case.get("canonical_question", "")).strip()
        expected_section_id = str(case.get("expected_legal_section_id", ""))
        if str(case.get("outcome", "")) != "mechanically_resolved":
            excluded_counts["reference_case_not_mechanically_resolved"] += 1
            continue
        if str(case.get("target_law_code", "")) not in selected_law_codes:
            excluded_counts["reference_case_outside_selected_law_codes"] += 1
            continue
        if expected_section_id not in available_section_ids:
            excluded_counts["expected_section_absent_from_selected_preview"] += 1
            continue
        if not benchmark_case_id or not canonical_question:
            excluded_counts["missing_benchmark_case_id_or_canonical_question"] += 1
            continue
        query_items.append(
            {
                "artifact_type": "tg_qa_corpus_bounded_semantic_embedding_item",
                "embedding_item_id": _stable_id(
                    "tg-qa-semantic-query-embedding",
                    {"benchmark_case_id": benchmark_case_id, "canonical_question": canonical_question},
                ),
                "candidate_id": benchmark_case_id,
                "benchmark_case_id": benchmark_case_id,
                "dataset_record_id": str(case.get("dataset_record_id", "")),
                "expected_legal_section_id": expected_section_id,
                "text_role": "semantic_query",
                "embedding_input_text": QUERY_PREFIX + canonical_question,
                "task_semantics": "retrieval.query",
                "policy_version": CORPUS_BOUNDED_SEMANTIC_BATCH_POLICY_VERSION,
                "trust_boundary": "private_semantic_retrieval_evaluation_input_not_legal_authority",
            }
        )

    document_items: list[dict[str, Any]] = []
    for section in selected_sections:
        source_fragment_id = str(section.get("source_fragment_id", ""))
        source_fragment = source_fragments.get(source_fragment_id, {})
        body_text = str(source_fragment.get("body_text", "")).strip()
        if not body_text:
            excluded_counts["selected_section_missing_source_fragment_body_text"] += 1
            continue
        legal_section_id_value = str(section.get("legal_section_id", ""))
        document_items.append(
            {
                "artifact_type": "tg_qa_corpus_bounded_semantic_embedding_item",
                "embedding_item_id": _stable_id(
                    "tg-qa-semantic-document-embedding",
                    {
                        "legal_section_id": legal_section_id_value,
                        "content_checksum": str(section.get("content_checksum", "")),
                    },
                ),
                "candidate_id": legal_section_id_value,
                "legal_section_id": legal_section_id_value,
                "source_fragment_id": source_fragment_id,
                "law_code": str(section.get("law_code", "")),
                "section_reference": str(section.get("section_reference", "")),
                "title": str(section.get("title", "")),
                "content_checksum": str(section.get("content_checksum", "")),
                "text_role": "legal_section_document",
                "embedding_input_text": DOCUMENT_PREFIX + body_text,
                "task_semantics": "retrieval.passage",
                "policy_version": CORPUS_BOUNDED_SEMANTIC_BATCH_POLICY_VERSION,
                "trust_boundary": "legal_source_embedding_input_for_private_retrieval_evaluation",
            }
        )

    batch_items = [*query_items, *document_items]
    _write_jsonl(Path(output_path), batch_items)
    summary = {
        "artifact_type": "tg_qa_corpus_bounded_semantic_embedding_batch_summary",
        "generated_at": _utc_timestamp(),
        "policy_version": CORPUS_BOUNDED_SEMANTIC_BATCH_POLICY_VERSION,
        "reference_cases_path": str(reference_cases_path),
        "source_legal_preview_path": str(legal_preview_path),
        "legal_preview_id": str(preview.get("preview_id", "")),
        "selected_law_codes": selected_law_codes,
        "reference_case_count": len(reference_cases),
        "query_embedding_item_count": len(query_items),
        "document_embedding_item_count": len(document_items),
        "embedding_item_count": len(batch_items),
        "excluded_counts": dict(sorted(excluded_counts.items())),
        "query_prefix": QUERY_PREFIX,
        "document_prefix": DOCUMENT_PREFIX,
        "document_text_contract": "source_fragment_body_text_only_matches_current_graph_write_embedding_contract",
        "output_path": str(output_path),
        "privacy_classification": "private_project_artifact",
        "trust_boundary": "semantic_embedding_batch_does_not_create_trusted_answer_support",
    }
    _write_json(Path(summary_output_path), summary)
    return {"items": batch_items, "summary": summary}


def build_tg_qa_corpus_bounded_semantic_benchmark(
    *,
    reference_cases_path: str | Path,
    embedding_batch_path: str | Path,
    external_vectors_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    vectorization_summary_path: str | Path | None = None,
    reference_review_decisions_path: str | Path | None = None,
    top_ks: Sequence[int] = (1, 5, 10),
) -> dict[str, Any]:
    """Rank legal sections for query-explicit silver reference cases."""

    ks = sorted({int(value) for value in top_ks if int(value) > 0})
    if not ks:
        raise ValueError("at least one positive top-k value is required")
    reference_cases = _read_jsonl(reference_cases_path)
    batch_items = _read_jsonl(embedding_batch_path)
    external_vectors = _read_jsonl(external_vectors_path)
    vectorization_summary = _read_json(vectorization_summary_path) if vectorization_summary_path else {}
    review_decisions = _reference_review_decisions(reference_review_decisions_path)

    vector_by_item_id = {
        str(item.get("embedding_item_id", "")): [float(value) for value in item.get("vector", [])]
        for item in external_vectors
        if item.get("embedding_item_id")
        and item.get("embedding_status") == "completed"
        and isinstance(item.get("vector"), list)
        and item.get("vector")
    }
    query_item_by_case_id = {
        str(item.get("benchmark_case_id", "")): item
        for item in batch_items
        if item.get("text_role") == "semantic_query" and item.get("benchmark_case_id")
    }
    document_items = sorted(
        [
            item
            for item in batch_items
            if item.get("text_role") == "legal_section_document" and item.get("legal_section_id")
        ],
        key=lambda item: str(item.get("legal_section_id", "")),
    )
    document_vectors: list[tuple[dict[str, Any], list[float]]] = []
    for item in document_items:
        vector = vector_by_item_id.get(str(item.get("embedding_item_id", "")))
        if vector:
            document_vectors.append((item, vector))

    results: list[dict[str, Any]] = []
    excluded_counts: Counter[str] = Counter()
    for case in sorted(reference_cases, key=lambda item: str(item.get("benchmark_case_id", ""))):
        if str(case.get("outcome", "")) != "mechanically_resolved":
            excluded_counts["reference_case_not_mechanically_resolved"] += 1
            continue
        benchmark_case_id = str(case.get("benchmark_case_id", ""))
        expected_section_id = str(case.get("expected_legal_section_id", ""))
        query_item = query_item_by_case_id.get(benchmark_case_id)
        query_vector = (
            vector_by_item_id.get(str(query_item.get("embedding_item_id", "")))
            if query_item
            else None
        )
        reference_review = review_decisions.get(
            benchmark_case_id,
            {"reference_correctness_decision": "unreviewed", "decision_reason": ""},
        )
        ranked: list[tuple[dict[str, Any], float]] = []
        if query_vector:
            ranked = sorted(
                (
                    (document_item, _cosine_similarity(query_vector, document_vector))
                    for document_item, document_vector in document_vectors
                ),
                key=lambda item: (-item[1], str(item[0].get("legal_section_id", ""))),
            )
        expected_rank = next(
            (
                index
                for index, (document_item, _score) in enumerate(ranked, start=1)
                if str(document_item.get("legal_section_id", "")) == expected_section_id
            ),
            0,
        )
        expected_score = next(
            (
                score
                for document_item, score in ranked
                if str(document_item.get("legal_section_id", "")) == expected_section_id
            ),
            0.0,
        )
        results.append(
            {
                "artifact_type": "tg_qa_corpus_bounded_semantic_retrieval_case",
                "benchmark_case_id": benchmark_case_id,
                "dataset_snapshot_id": str(case.get("dataset_snapshot_id", "")),
                "dataset_record_id": str(case.get("dataset_record_id", "")),
                "canonical_question": str(case.get("canonical_question", "")),
                "expected_legal_section_id": expected_section_id,
                "target_evidence_type": str(
                    case.get("target_evidence_type", "query_explicit_silver")
                ),
                "target_law_code": str(case.get("target_law_code", "")),
                "target_section_reference": str(case.get("target_section_reference", "")),
                "reference_correctness_decision": reference_review["reference_correctness_decision"],
                "reference_correctness_decision_reason": reference_review["decision_reason"],
                "query_vector_available": bool(query_vector),
                "candidate_document_vector_count": len(document_vectors),
                "expected_rank": expected_rank,
                "expected_score": round(expected_score, 8),
                "top_candidates": [
                    {
                        "legal_section_id": str(document_item.get("legal_section_id", "")),
                        "law_code": str(document_item.get("law_code", "")),
                        "section_reference": str(document_item.get("section_reference", "")),
                        "title": str(document_item.get("title", "")),
                        "score": round(score, 8),
                    }
                    for document_item, score in ranked[: max(ks)]
                ],
                "policy_version": CORPUS_BOUNDED_SEMANTIC_BENCHMARK_POLICY_VERSION,
                "trust_boundary": "private_semantic_retrieval_evaluation_case_not_legal_authority",
            }
        )

    all_expected_metrics = _ranking_metrics(results, ks)
    query_explicit_results = [
        item for item in results if item["target_evidence_type"] == "query_explicit_silver"
    ]
    curated_checked_results = [
        item for item in results if item["target_evidence_type"] == "curated_checked"
    ]
    reviewed_accepted_results = [
        item for item in results if item["reference_correctness_decision"] == "accept"
    ]
    summary = {
        "artifact_type": "tg_qa_corpus_bounded_semantic_retrieval_benchmark_summary",
        "benchmark_id": _stable_id(
            "tg-qa-semantic-retrieval-benchmark",
            {
                "reference_case_ids": [item["benchmark_case_id"] for item in results],
                "embedding_batch_path": str(embedding_batch_path),
                "external_vectors_path": str(external_vectors_path),
                "top_ks": ks,
            },
        ),
        "generated_at": _utc_timestamp(),
        "policy_version": CORPUS_BOUNDED_SEMANTIC_BENCHMARK_POLICY_VERSION,
        "reference_cases_path": str(reference_cases_path),
        "embedding_batch_path": str(embedding_batch_path),
        "external_vectors_path": str(external_vectors_path),
        "vectorization_summary_path": str(vectorization_summary_path or ""),
        "reference_review_decisions_path": str(reference_review_decisions_path or ""),
        "vectorization_model_id": str(vectorization_summary.get("model_id", "")),
        "top_ks": ks,
        "reference_case_count": len(reference_cases),
        "evaluated_case_count": len(results),
        "query_vector_available_count": sum(bool(item["query_vector_available"]) for item in results),
        "candidate_document_item_count": len(document_items),
        "candidate_document_vector_count": len(document_vectors),
        "counts_by_reference_correctness_decision": _counts(
            str(item["reference_correctness_decision"]) for item in results
        ),
        "counts_by_target_evidence_type": _counts(
            str(item["target_evidence_type"]) for item in results
        ),
        "counts_by_expected_legal_section_id": _counts(
            str(item["expected_legal_section_id"]) for item in results
        ),
        "excluded_counts": dict(sorted(excluded_counts.items())),
        "metric_scopes": {
            "all_expected_targets": all_expected_metrics,
            "query_explicit_silver_targets": _ranking_metrics(query_explicit_results, ks),
            "silver_all_query_explicit_targets": _ranking_metrics(query_explicit_results, ks),
            "curated_checked_targets": _ranking_metrics(curated_checked_results, ks),
            "reviewed_accepted_targets": _ranking_metrics(reviewed_accepted_results, ks),
        },
        "metric_interpretation": "expected_target_recovery_by_evidence_type_not_legal_answer_quality",
        "metric_scope_note": (
            "query-explicit silver targets may be legally incorrect or describe status context; "
            "curated checked targets are independently selected primary relevant sections; "
            "reviewed_accepted metrics are authoritative only for decisions made under the separate review file"
        ),
        "output_path": str(output_path),
        "privacy_classification": "private_project_artifact",
        "known_limitations": [
            "semantic retrieval metrics do not measure answer correctness or completeness",
            "a single expected target does not prove that no other legal section is relevant",
            "unreviewed query-explicit silver references may penalize legally better retrieval",
            "an explicit law reference may identify the user's status or premise rather than relevant answer support",
            "document vectors use source fragment body text only to match the current graph-write embedding contract",
            "the benchmark evaluates the selected bounded legal preview rather than the full German legal corpus",
        ],
        "trust_boundary": "semantic_retrieval_benchmark_does_not_create_trusted_answer_support",
    }
    _write_jsonl(Path(output_path), results)
    _write_json(Path(summary_output_path), summary)
    return {"cases": results, "summary": summary}


def build_tg_qa_retrieval_relevance_review_batch(
    *,
    semantic_cases_path: str | Path,
    embedding_batch_path: str | Path,
    dataset_path: str | Path | None = None,
    output_path: str | Path,
    summary_output_path: str | Path,
    max_cases: int = 30,
    top_k: int = 10,
) -> dict[str, Any]:
    """Build a diverse, bounded batch for human legal-section relevance review."""

    if max_cases <= 0:
        raise ValueError("max_cases must be positive")
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    semantic_cases = _read_jsonl(semantic_cases_path)
    embedding_items = _read_jsonl(embedding_batch_path)
    documents_by_section_id = {
        str(item.get("legal_section_id", "")): item
        for item in embedding_items
        if item.get("text_role") == "legal_section_document" and item.get("legal_section_id")
    }
    legal_section_catalog = [
        {
            "legal_section_id": section_id,
            "law_code": str(item.get("law_code", "")),
            "section_reference": str(item.get("section_reference", "")),
            "title": str(item.get("title", "")),
        }
        for section_id, item in sorted(documents_by_section_id.items())
    ]
    dataset_by_record_id = {
        str(item.get("dataset_record_id", "")): item
        for item in (_read_jsonl(dataset_path) if dataset_path else [])
        if item.get("dataset_record_id")
    }
    selected_cases = _diverse_relevance_review_sample(semantic_cases, max_cases=max_cases)
    cards: list[dict[str, Any]] = []
    missing_document_counts: Counter[str] = Counter()
    source_diagnostic_counts: Counter[str] = Counter()
    for case in selected_cases:
        expected_section_id = str(case.get("expected_legal_section_id", ""))
        target_evidence_type = str(case.get("target_evidence_type", "query_explicit_silver"))
        canonical_question = str(case.get("canonical_question", ""))
        dataset_record = dataset_by_record_id.get(str(case.get("dataset_record_id", "")), {})
        source_question = str(dataset_record.get("source_question_text_redacted", ""))
        source_reference_diagnostics = _source_reference_diagnostics(
            source_question,
            expected_section_id=expected_section_id,
        )
        source_diagnostic_counts.update(source_reference_diagnostics)
        ranked_candidates = [
            item for item in case.get("top_candidates", []) if isinstance(item, Mapping)
        ][:top_k]
        candidate_section_ids = [
            str(item.get("legal_section_id", "")) for item in ranked_candidates if item.get("legal_section_id")
        ]
        if expected_section_id and expected_section_id not in candidate_section_ids:
            candidate_section_ids.append(expected_section_id)
        same_question_reference_ids = _same_question_reference_section_ids(canonical_question)
        for section_id in same_question_reference_ids:
            if section_id not in candidate_section_ids:
                candidate_section_ids.append(section_id)
        rank_by_section_id = {
            str(item.get("legal_section_id", "")): index
            for index, item in enumerate(ranked_candidates, start=1)
            if item.get("legal_section_id")
        }
        score_by_section_id = {
            str(item.get("legal_section_id", "")): float(item.get("score", 0.0) or 0.0)
            for item in ranked_candidates
            if item.get("legal_section_id")
        }
        candidates: list[dict[str, Any]] = []
        for section_id in candidate_section_ids:
            document = documents_by_section_id.get(section_id)
            if not document:
                missing_document_counts["candidate_missing_document_embedding_item"] += 1
                continue
            if section_id in rank_by_section_id:
                candidate_rank = rank_by_section_id[section_id]
                candidate_score = score_by_section_id.get(section_id, 0.0)
            elif section_id == expected_section_id:
                candidate_rank = int(case.get("expected_rank", 0) or 0)
                candidate_score = float(case.get("expected_score", 0.0) or 0.0)
            else:
                candidate_rank = 0
                candidate_score = 0.0
            candidates.append(
                {
                    "legal_section_id": section_id,
                    "law_code": str(document.get("law_code", "")),
                    "section_reference": str(document.get("section_reference", "")),
                    "title": str(document.get("title", "")),
                    "body_text": _strip_embedding_prefix(
                        str(document.get("embedding_input_text", "")),
                        DOCUMENT_PREFIX,
                    ),
                    "rank": candidate_rank,
                    "score": round(candidate_score, 8),
                    "is_expected_target": section_id == expected_section_id,
                    "is_explicit_reference_target": (
                        section_id == expected_section_id
                        and target_evidence_type == "query_explicit_silver"
                    ),
                    "is_same_question_reference": section_id in same_question_reference_ids,
                    "candidate_source": (
                        "top_semantic_candidate"
                        if section_id in rank_by_section_id
                        else "same_question_inferred_law_reference"
                        if section_id in same_question_reference_ids and section_id != expected_section_id
                        else "curated_expected_target_added_for_review"
                        if target_evidence_type == "curated_checked"
                        else "explicit_reference_target_added_for_review"
                    ),
                }
            )
        cards.append(
            {
                "artifact_type": "tg_qa_retrieval_relevance_review_card",
                "benchmark_case_id": str(case.get("benchmark_case_id", "")),
                "dataset_record_id": str(case.get("dataset_record_id", "")),
                "canonical_question": canonical_question,
                "source_question_text_redacted": source_question,
                "source_reference_diagnostics": source_reference_diagnostics,
                "expected_legal_section_id": expected_section_id,
                "target_evidence_type": target_evidence_type,
                "expected_rank": int(case.get("expected_rank", 0) or 0),
                "candidates": candidates,
                "legal_section_catalog": legal_section_catalog,
                "review_contract": {
                    "review_statuses": sorted(RELEVANCE_REVIEW_STATUSES),
                    "explicit_reference_roles": sorted(EXPLICIT_REFERENCE_ROLES),
                    "multiple_relevant_sections_allowed": True,
                    "no_relevant_candidate_shown_allowed": True,
                    "additional_relevant_sections_allowed": True,
                    "rerun_after_corpus_expansion_allowed": True,
                },
                "policy_version": RETRIEVAL_RELEVANCE_REVIEW_POLICY_VERSION,
                "trust_boundary": "private_human_relevance_review_card_not_legal_authority",
            }
        )

    _write_jsonl(Path(output_path), cards)
    summary = {
        "artifact_type": "tg_qa_retrieval_relevance_review_batch_summary",
        "generated_at": _utc_timestamp(),
        "policy_version": RETRIEVAL_RELEVANCE_REVIEW_POLICY_VERSION,
        "semantic_cases_path": str(semantic_cases_path),
        "embedding_batch_path": str(embedding_batch_path),
        "dataset_path": str(dataset_path or ""),
        "output_path": str(output_path),
        "source_case_count": len(semantic_cases),
        "max_cases": max_cases,
        "top_k": top_k,
        "card_count": len(cards),
        "legal_section_catalog_count": len(legal_section_catalog),
        "counts_by_expected_legal_section_id": _counts(
            str(item.get("expected_legal_section_id", "")) for item in cards
        ),
        "missing_document_counts": dict(sorted(missing_document_counts.items())),
        "source_reference_diagnostic_counts": dict(sorted(source_diagnostic_counts.items())),
        "sample_policy": "stable_round_robin_rarest_expected_section_first",
        "privacy_classification": "private_project_artifact",
        "trust_boundary": "review_batch_requires_human_labels_before_relevance_metrics",
    }
    _write_json(Path(summary_output_path), summary)
    return {"cards": cards, "summary": summary}


def export_tg_qa_retrieval_relevance_review_html(
    *,
    review_batch_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
) -> dict[str, Any]:
    """Export a dependency-free relevance review UI with JSONL download."""

    cards = _read_jsonl(review_batch_path)
    _write_text(Path(output_path), _retrieval_relevance_review_html(cards))
    summary = {
        "artifact_type": "tg_qa_retrieval_relevance_review_html_summary",
        "generated_at": _utc_timestamp(),
        "policy_version": RETRIEVAL_RELEVANCE_REVIEW_POLICY_VERSION,
        "review_batch_path": str(review_batch_path),
        "html_output_path": str(output_path),
        "card_count": len(cards),
        "review_ui_mode": "static_html_with_local_storage_and_client_side_jsonl_export",
        "privacy_classification": "private_project_artifact",
        "trust_boundary": "relevance_review_labels_require_human_export_and_import",
    }
    _write_json(Path(summary_output_path), summary)
    return {"cards": cards, "summary": summary}


def import_tg_qa_retrieval_relevance_review_labels(
    *,
    review_batch_path: str | Path,
    labels_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
) -> dict[str, Any]:
    """Validate human legal-section relevance labels."""

    cards = {
        str(item.get("benchmark_case_id", "")): item
        for item in _read_jsonl(review_batch_path)
        if item.get("benchmark_case_id")
    }
    raw_labels = _read_jsonl(labels_path)
    records: list[dict[str, Any]] = []
    seen_case_ids: set[str] = set()
    counts: Counter[str] = Counter()
    for raw in raw_labels:
        case_id = str(raw.get("benchmark_case_id", ""))
        card = cards.get(case_id)
        review_status = str(raw.get("review_status", ""))
        explicit_reference_role = str(raw.get("explicit_reference_role", "uncertain") or "uncertain")
        shown_relevant_ids = sorted(
            set(str(item) for item in raw.get("relevant_legal_section_ids", []) if str(item))
        )
        additional_relevant_ids = sorted(
            set(
                str(item)
                for item in raw.get("additional_relevant_legal_section_ids", [])
                if str(item)
            )
        )
        raw_rerun_after_corpus_expansion = raw.get("rerun_after_corpus_expansion", [])
        rerun_after_corpus_expansion_valid = isinstance(raw_rerun_after_corpus_expansion, list) and all(
            isinstance(item, str) for item in raw_rerun_after_corpus_expansion
        )
        rerun_after_corpus_expansion = sorted(
            set(
                str(item).strip()
                for item in raw_rerun_after_corpus_expansion
                if str(item).strip()
            )
        ) if rerun_after_corpus_expansion_valid else []
        relevant_ids = sorted(set(shown_relevant_ids + additional_relevant_ids))
        no_relevant_shown = bool(raw.get("no_relevant_candidate_shown", False))
        candidate_ids = {
            str(item.get("legal_section_id", ""))
            for item in (card or {}).get("candidates", [])
            if isinstance(item, Mapping) and item.get("legal_section_id")
        }
        catalog_ids = {
            str(item.get("legal_section_id", ""))
            for item in (card or {}).get("legal_section_catalog", [])
            if isinstance(item, Mapping) and item.get("legal_section_id")
        }
        failure_reason = ""
        if not card:
            failure_reason = "unknown_benchmark_case_id"
        elif case_id in seen_case_ids:
            failure_reason = "duplicate_relevance_review_label"
        elif review_status not in RELEVANCE_REVIEW_STATUSES:
            failure_reason = f"invalid_review_status:{review_status}"
        elif explicit_reference_role not in EXPLICIT_REFERENCE_ROLES:
            failure_reason = f"invalid_explicit_reference_role:{explicit_reference_role}"
        elif not rerun_after_corpus_expansion_valid:
            failure_reason = "rerun_after_corpus_expansion_must_be_string_list"
        elif set(shown_relevant_ids).difference(candidate_ids):
            failure_reason = "shown_relevant_section_not_in_review_candidates"
        elif set(additional_relevant_ids).difference(catalog_ids):
            failure_reason = "additional_relevant_section_not_in_selected_corpus"
        elif set(shown_relevant_ids).intersection(additional_relevant_ids):
            failure_reason = "relevant_section_present_in_shown_and_additional_sets"
        elif review_status == "reviewed" and bool(shown_relevant_ids) == no_relevant_shown:
            failure_reason = "reviewed_label_requires_shown_relevant_sections_xor_no_relevant_candidate_shown"
        if not failure_reason:
            seen_case_ids.add(case_id)
            counts[review_status] += 1
            counts[f"explicit_reference_role:{explicit_reference_role}"] += 1
            for law_code in rerun_after_corpus_expansion:
                counts[f"rerun_after_corpus_expansion:{law_code}"] += 1
        else:
            counts["failed"] += 1
        records.append(
            {
                "artifact_type": "tg_qa_retrieval_relevance_review_label",
                "relevance_review_label_id": _stable_id(
                    "tg-qa-relevance-review-label",
                    {
                        "benchmark_case_id": case_id,
                        "relevant_legal_section_ids": relevant_ids,
                        "shown_relevant_legal_section_ids": shown_relevant_ids,
                        "additional_relevant_legal_section_ids": additional_relevant_ids,
                        "no_relevant_candidate_shown": no_relevant_shown,
                        "review_status": review_status,
                        "explicit_reference_role": explicit_reference_role,
                        "rerun_after_corpus_expansion": rerun_after_corpus_expansion,
                    },
                ),
                "benchmark_case_id": case_id,
                "relevant_legal_section_ids": relevant_ids,
                "shown_relevant_legal_section_ids": shown_relevant_ids,
                "additional_relevant_legal_section_ids": additional_relevant_ids,
                "no_relevant_candidate_shown": no_relevant_shown,
                "review_status": review_status,
                "explicit_reference_role": explicit_reference_role,
                "rerun_after_corpus_expansion": rerun_after_corpus_expansion,
                "decision_reason": str(raw.get("decision_reason", "")),
                "reviewed_at": str(raw.get("reviewed_at", "")) or _utc_timestamp(),
                "status": "failed" if failure_reason else "completed",
                "failure_reason": failure_reason,
                "policy_version": RETRIEVAL_RELEVANCE_REVIEW_POLICY_VERSION,
                "trust_boundary": "human_relevance_label_for_private_evaluation_not_legal_authority",
            }
        )

    _write_jsonl(Path(output_path), records)
    summary = {
        "artifact_type": "tg_qa_retrieval_relevance_review_label_import_summary",
        "generated_at": _utc_timestamp(),
        "policy_version": RETRIEVAL_RELEVANCE_REVIEW_POLICY_VERSION,
        "review_batch_path": str(review_batch_path),
        "labels_path": str(labels_path),
        "output_path": str(output_path),
        "processed_count": len(raw_labels),
        "completed_count": sum(item["status"] == "completed" for item in records),
        "failed_count": counts.get("failed", 0),
        "counts_by_review_status": _counts(
            str(item.get("review_status", "")) for item in records if item["status"] == "completed"
        ),
        "counts_by_explicit_reference_role": _counts(
            str(item.get("explicit_reference_role", "")) for item in records if item["status"] == "completed"
        ),
        "counts_by_rerun_after_corpus_expansion_law_code": _counts(
            law_code
            for item in records
            if item["status"] == "completed"
            for law_code in item.get("rerun_after_corpus_expansion", [])
        ),
        "trust_boundary": "reviewed_relevance_labels_remain_private_evaluation_artifacts",
    }
    _write_json(Path(summary_output_path), summary)
    return {"labels": records, "summary": summary}


def build_tg_qa_reviewed_relevance_report(
    *,
    semantic_cases_path: str | Path,
    review_labels_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    top_ks: Sequence[int] = (1, 5, 10),
) -> dict[str, Any]:
    """Evaluate semantic rankings against reviewed positive relevance labels."""

    ks = sorted({int(value) for value in top_ks if int(value) > 0})
    if not ks:
        raise ValueError("at least one positive top-k value is required")
    semantic_cases = {
        str(item.get("benchmark_case_id", "")): item
        for item in _read_jsonl(semantic_cases_path)
        if item.get("benchmark_case_id")
    }
    labels = [
        item
        for item in _read_jsonl(review_labels_path)
        if item.get("status") == "completed" and item.get("review_status") == "reviewed"
    ]
    records: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for label in labels:
        case_id = str(label.get("benchmark_case_id", ""))
        case = semantic_cases.get(case_id)
        relevant_ids = set(str(item) for item in label.get("relevant_legal_section_ids", []) if str(item))
        if label.get("no_relevant_candidate_shown"):
            counts["reviewed_no_relevant_candidate_shown"] += 1
        if not case:
            counts["missing_semantic_case"] += 1
            continue
        if not relevant_ids:
            counts["reviewed_without_positive_relevance_label"] += 1
            continue
        rank_by_id = {
            str(item.get("legal_section_id", "")): index
            for index, item in enumerate(case.get("top_candidates", []), start=1)
            if isinstance(item, Mapping) and item.get("legal_section_id")
        }
        expected_id = str(case.get("expected_legal_section_id", ""))
        expected_rank = int(case.get("expected_rank", 0) or 0)
        if expected_id and expected_rank:
            rank_by_id.setdefault(expected_id, expected_rank)
        relevant_ranks = sorted(rank_by_id[item] for item in relevant_ids if item in rank_by_id)
        unranked_relevant_ids = sorted(relevant_ids.difference(rank_by_id))
        if unranked_relevant_ids:
            counts["positive_label_with_unranked_relevant_sections"] += 1
        records.append(
            {
                "artifact_type": "tg_qa_reviewed_relevance_evaluation_case",
                "benchmark_case_id": case_id,
                "relevant_legal_section_ids": sorted(relevant_ids),
                "relevant_ranks": relevant_ranks,
                "unranked_relevant_legal_section_ids": unranked_relevant_ids,
                "first_relevant_rank": relevant_ranks[0] if relevant_ranks else 0,
                "additional_relevant_legal_section_ids": list(
                    label.get("additional_relevant_legal_section_ids", [])
                ),
                "explicit_reference_role": str(label.get("explicit_reference_role", "")),
                "rerun_after_corpus_expansion": list(label.get("rerun_after_corpus_expansion", [])),
                "policy_version": RETRIEVAL_RELEVANCE_REVIEW_POLICY_VERSION,
                "trust_boundary": "reviewed_relevance_evaluation_not_trusted_answer_support",
            }
        )

    metrics = _multi_relevance_ranking_metrics(records, ks)
    _write_jsonl(Path(output_path), records)
    summary = {
        "artifact_type": "tg_qa_reviewed_relevance_report_summary",
        "generated_at": _utc_timestamp(),
        "policy_version": RETRIEVAL_RELEVANCE_REVIEW_POLICY_VERSION,
        "semantic_cases_path": str(semantic_cases_path),
        "review_labels_path": str(review_labels_path),
        "output_path": str(output_path),
        "reviewed_label_count": len(labels),
        "evaluated_positive_label_count": len(records),
        "positive_label_coverage_rate": (
            round(len(records) / len(labels), 6) if labels else 0.0
        ),
        "bounded_candidate_failure_rate": (
            round(counts.get("reviewed_no_relevant_candidate_shown", 0) / len(labels), 6)
            if labels
            else 0.0
        ),
        "excluded_counts": dict(sorted(counts.items())),
        "counts_by_explicit_reference_role": _counts(
            str(item.get("explicit_reference_role", "")) for item in records
        ),
        "counts_by_rerun_after_corpus_expansion_law_code": _counts(
            law_code
            for item in records
            for law_code in item.get("rerun_after_corpus_expansion", [])
        ),
        "metrics": metrics,
        "known_limitations": [
            "metrics cover only human-reviewed cards with at least one positive relevance label",
            "review candidates are bounded to semantic top candidates plus the explicit-reference target",
            "reviewer-added relevant sections outside the recorded ranking count as retrieval misses",
            "the report cannot recover the exact rank of reviewer-added sections outside recorded candidates",
        ],
        "trust_boundary": "reviewed_relevance_metrics_do_not_create_trusted_answer_support",
    }
    _write_json(Path(summary_output_path), summary)
    return {"cases": records, "summary": summary}


def _reference_review_decisions(path: str | Path | None) -> dict[str, dict[str, str]]:
    if not path:
        return {}
    decisions: dict[str, dict[str, str]] = {}
    for item in _read_jsonl(path):
        benchmark_case_id = str(item.get("benchmark_case_id", ""))
        decision = str(item.get("reference_correctness_decision", ""))
        if not benchmark_case_id:
            raise ValueError("reference review decision is missing benchmark_case_id")
        if decision not in REFERENCE_REVIEW_DECISIONS:
            raise ValueError(
                f"reference review decision for {benchmark_case_id} must be one of "
                f"{sorted(REFERENCE_REVIEW_DECISIONS)}"
            )
        decisions[benchmark_case_id] = {
            "reference_correctness_decision": decision,
            "decision_reason": str(item.get("decision_reason", "")),
        }
    return decisions


def _diverse_relevance_review_sample(
    semantic_cases: Sequence[Mapping[str, Any]],
    *,
    max_cases: int,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in semantic_cases:
        key = str(item.get("expected_legal_section_id", "")) or "missing_expected_section"
        groups.setdefault(key, []).append(dict(item))
    for items in groups.values():
        items.sort(key=lambda item: str(item.get("benchmark_case_id", "")))
    ordered_groups = sorted(groups.items(), key=lambda pair: (len(pair[1]), pair[0]))
    selected: list[dict[str, Any]] = []
    offset = 0
    while len(selected) < max_cases:
        added = False
        for _key, items in ordered_groups:
            if offset < len(items):
                selected.append(items[offset])
                added = True
                if len(selected) >= max_cases:
                    break
        if not added:
            break
        offset += 1
    return selected


def _strip_embedding_prefix(text: str, prefix: str) -> str:
    return text[len(prefix) :] if text.startswith(prefix) else text


def _source_reference_diagnostics(
    source_question: str,
    *,
    expected_section_id: str,
) -> list[str]:
    if not source_question or not expected_section_id:
        return []
    parts = expected_section_id.split(":")
    if len(parts) < 3:
        return []
    law_code = parts[1]
    diagnostics: list[str] = []
    if law_code.casefold() not in source_question.casefold():
        diagnostics.append("explicit_target_law_code_absent_from_source")
    return diagnostics


def _same_question_reference_section_ids(canonical_question: str) -> list[str]:
    references = parse_explicit_legal_references(canonical_question)
    explicit_law_codes = {
        str(item.target_law_code)
        for item in references
        if item.target_law_code_explicit and item.target_law_code
    }
    if len(explicit_law_codes) != 1:
        return []
    inherited_law_code = next(iter(explicit_law_codes))
    section_ids = {
        legal_section_id(
            str(item.target_law_code) if item.target_law_code_explicit else inherited_law_code,
            str(item.target_section_reference),
        )
        for item in references
        if item.target_section_reference
    }
    return sorted(section_ids)


def _retrieval_relevance_review_html(cards: Sequence[Mapping[str, Any]]) -> str:
    data = json.dumps(list(cards), ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>007 Retrieval Relevance Review</title>
  <style>
    :root {{ --bg:#f5f6f3; --panel:#fff; --line:#d7dad4; --text:#202428; --muted:#687078; --accent:#166534; --target:#fff7d6; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:ui-sans-serif,system-ui,sans-serif; background:var(--bg); color:var(--text); }}
    header {{ position:sticky; top:0; z-index:2; padding:11px 16px; background:#edf1eb; border-bottom:1px solid var(--line); display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
    main {{ max-width:1320px; margin:0 auto; padding:14px; }}
    button,select,textarea,input {{ font:inherit; }}
    button,select {{ border:1px solid var(--line); background:#fff; border-radius:6px; padding:7px 10px; }}
    button {{ cursor:pointer; }}
    button.primary {{ color:#fff; background:var(--accent); border-color:var(--accent); }}
    textarea {{ width:100%; min-height:72px; resize:vertical; border:1px solid var(--line); border-radius:6px; padding:8px; }}
    .card {{ display:grid; gap:12px; }}
    .question,.candidate,.decision {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:12px; }}
    .warning {{ color:#9a3412; font-weight:600; }}
    .candidate {{ display:grid; grid-template-columns:26px minmax(0,1fr); gap:8px; }}
    .candidate.target {{ background:var(--target); }}
    .meta,.muted {{ color:var(--muted); font-size:12px; }}
    .body {{ white-space:pre-wrap; overflow-wrap:anywhere; max-height:240px; overflow:auto; margin-top:7px; border-top:1px solid var(--line); padding-top:7px; }}
    .decision-grid {{ display:grid; grid-template-columns:220px 240px 220px minmax(0,1fr); gap:8px; align-items:start; }}
    .field {{ display:grid; gap:4px; }}
    .field > span {{ color:var(--muted); font-size:12px; }}
    .additional {{ display:flex; gap:6px; flex-wrap:wrap; margin-top:6px; }}
    .additional button {{ padding:4px 7px; }}
    @media (max-width:900px) {{ .decision-grid {{ grid-template-columns:1fr; }} main {{ padding:10px; }} }}
  </style>
</head>
<body>
<header>
  <strong>007 retrieval relevance review</strong>
  <span id="counter" class="muted"></span>
  <button id="prev">Prev</button>
  <button id="next">Next</button>
  <select id="filter"><option value="all">all</option><option value="undecided">undecided</option><option value="reviewed">reviewed</option><option value="uncertain">uncertain</option><option value="corpus-rerun">corpus rerun</option></select>
  <button id="export" class="primary">Export JSONL</button>
</header>
<main id="app"></main>
<script>
const cards = {data};
const storageKey = 'tg_007_retrieval_relevance_review_v1';
const decisions = new Map(JSON.parse(localStorage.getItem(storageKey) || '[]'));
let index = 0;
let filter = 'all';
let additionalSections = [];
const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
function filtered() {{
  return cards.filter(card => {{
    const d = decisions.get(card.benchmark_case_id);
    if (filter === 'undecided') return !d || !d.review_status;
    if (filter === 'reviewed') return d && d.review_status === 'reviewed';
    if (filter === 'uncertain') return d && d.review_status === 'uncertain';
    if (filter === 'corpus-rerun') return d && (d.rerun_after_corpus_expansion || []).length;
    return true;
  }});
}}
function save(card) {{
  const relevant = Array.from(document.querySelectorAll('input[data-section]:checked')).map(x => x.dataset.section);
  const rerunLawCodes = document.getElementById('rerunLawCodes').value.split(',').map(x => x.trim()).filter(Boolean);
  if (document.getElementById('rerunVwvfg').checked && !rerunLawCodes.includes('VwVfG')) rerunLawCodes.push('VwVfG');
  const record = {{
    benchmark_case_id: card.benchmark_case_id,
    relevant_legal_section_ids: relevant,
    additional_relevant_legal_section_ids: additionalSections,
    no_relevant_candidate_shown: document.getElementById('noneShown').checked,
    review_status: document.getElementById('reviewStatus').value,
    explicit_reference_role: document.getElementById('referenceRole').value,
    rerun_after_corpus_expansion: [...new Set(rerunLawCodes)].sort(),
    decision_reason: document.getElementById('reason').value,
    reviewed_at: new Date().toISOString()
  }};
  decisions.set(card.benchmark_case_id, record);
  localStorage.setItem(storageKey, JSON.stringify(Array.from(decisions.entries())));
}}
function render() {{
  const list = filtered();
  if (!list.length) {{ document.getElementById('app').innerHTML='<div class="question">No cards</div>'; document.getElementById('counter').textContent='0/0'; return; }}
  index = Math.max(0, Math.min(index, list.length - 1));
  const card = list[index];
  const saved = decisions.get(card.benchmark_case_id) || {{}};
  additionalSections = [...(saved.additional_relevant_legal_section_ids || [])];
  const savedRerunLawCodes = [...(saved.rerun_after_corpus_expansion || [])];
  const savedOtherRerunLawCodes = savedRerunLawCodes.filter(lawCode => lawCode !== 'VwVfG');
  document.getElementById('counter').textContent = `${{index + 1}}/${{list.length}}`;
  const candidateIds = new Set((card.candidates || []).map(c => c.legal_section_id));
  const catalog = (card.legal_section_catalog || []).filter(c => !candidateIds.has(c.legal_section_id));
  const catalogOptions = catalog.map(c => `<option value="${{esc(c.legal_section_id)}}">${{esc(c.section_reference)}} ${{esc(c.law_code)}} · ${{esc(c.title)}}</option>`).join('');
  const candidates = (card.candidates || []).map(c => `<label class="candidate ${{c.is_expected_target ? 'target' : ''}}">
    <input type="checkbox" data-section="${{esc(c.legal_section_id)}}" ${{(saved.relevant_legal_section_ids || []).includes(c.legal_section_id) ? 'checked' : ''}}>
    <div><strong>${{esc(c.legal_section_id)}}</strong> · rank=${{esc(c.rank)}} · score=${{esc(c.score)}}${{c.is_expected_target ? ' · ' + esc(card.target_evidence_type || 'expected target') : ''}}${{c.is_same_question_reference && !c.is_expected_target ? ' · same-question reference' : ''}}
    <div class="meta">${{esc(c.title)}} · ${{esc(c.candidate_source)}}</div><div class="body">${{esc(c.body_text)}}</div></div>
  </label>`).join('');
  document.getElementById('app').innerHTML = `<article class="card">
    <section class="question"><strong>${{esc(card.benchmark_case_id)}}</strong><h2>${{esc(card.canonical_question)}}</h2>
      <div class="meta">source question</div><div>${{esc(card.source_question_text_redacted || 'not supplied')}}</div>
      <div class="meta">${{esc(card.target_evidence_type || 'expected target')}}: ${{esc(card.expected_legal_section_id)}} · rank=${{esc(card.expected_rank)}}</div>
      <div class="warning">${{esc((card.source_reference_diagnostics || []).join('; '))}}</div>
    </section>
    ${{candidates}}
    <section class="decision"><div class="decision-grid">
      <label class="field"><span>review status</span><select id="reviewStatus">${{['','reviewed','uncertain','skip'].map(v => `<option value="${{v}}" ${{saved.review_status===v?'selected':''}}>${{v || 'select'}}</option>`).join('')}}</select></label>
      <label class="field"><span>expected-target role</span><select id="referenceRole">${{['uncertain','answer_support','status_context','incorrect'].map(v => `<option value="${{v}}" ${{saved.explicit_reference_role===v?'selected':''}}>${{v}}</option>`).join('')}}</select></label>
      <label class="field"><span>bounded candidate result</span><span><input id="noneShown" type="checkbox" ${{saved.no_relevant_candidate_shown?'checked':''}}> no relevant candidate shown</span></label>
      <label class="field"><span>decision reason</span><textarea id="reason" placeholder="optional">${{esc(saved.decision_reason || '')}}</textarea></label>
      <label class="field"><span>rerun after corpus expansion</span><span><input id="rerunVwvfg" type="checkbox" ${{savedRerunLawCodes.includes('VwVfG')?'checked':''}}> VwVfG</span><input id="rerunLawCodes" value="${{esc(savedOtherRerunLawCodes.join(', '))}}" placeholder="other law codes, comma-separated"></label>
    </div>
    <div class="field"><span>additional relevant section outside shown candidates</span>
      <span><input id="additionalSectionInput" list="sectionCatalog" placeholder="Choose a legal section"><button id="addSection" type="button">Add section</button></span>
      <datalist id="sectionCatalog">${{catalogOptions}}</datalist>
      <div id="additionalSections" class="additional"></div>
    </div></section>
  </article>`;
  function renderAdditional() {{
    document.getElementById('additionalSections').innerHTML = additionalSections.map(sectionId =>
      `<button type="button" data-remove-section="${{esc(sectionId)}}">${{esc(sectionId)}} ×</button>`
    ).join('');
    document.querySelectorAll('[data-remove-section]').forEach(node => node.onclick = () => {{
      additionalSections = additionalSections.filter(sectionId => sectionId !== node.dataset.removeSection);
      renderAdditional();
      save(card);
    }});
  }}
  renderAdditional();
  document.getElementById('addSection').onclick = () => {{
    const input = document.getElementById('additionalSectionInput');
    const sectionId = input.value.trim();
    const catalogIds = new Set(catalog.map(item => item.legal_section_id));
    if (catalogIds.has(sectionId) && !additionalSections.includes(sectionId)) {{
      additionalSections.push(sectionId);
      additionalSections.sort();
      input.value = '';
      renderAdditional();
      save(card);
    }}
  }};
  document.querySelectorAll('input[data-section]').forEach(node => node.onchange = () => {{
    if (node.checked) document.getElementById('noneShown').checked = false;
    save(card);
  }});
  document.getElementById('noneShown').onchange = event => {{
    if (event.target.checked) document.querySelectorAll('input[data-section]').forEach(node => node.checked = false);
    save(card);
  }};
  document.querySelectorAll('select,textarea,input').forEach(node => node.oninput = () => save(card));
}}
document.getElementById('prev').onclick=()=>{{index--;render();}};
document.getElementById('next').onclick=()=>{{index++;render();}};
document.getElementById('filter').onchange=e=>{{filter=e.target.value;index=0;render();}};
document.getElementById('export').onclick=()=>{{
  const rows=Array.from(decisions.values()).filter(x=>x.review_status);
  const blob=new Blob([rows.map(x=>JSON.stringify(x)).join('\\n')+(rows.length?'\\n':'')],{{type:'application/x-ndjson'}});
  const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download='tg_007_retrieval_relevance_review_labels.jsonl'; a.click(); URL.revokeObjectURL(url);
}};
render();
</script>
</body>
</html>
"""


def _ranking_metrics(records: Sequence[Mapping[str, Any]], ks: Sequence[int]) -> dict[str, Any]:
    count = len(records)
    ranks = [int(item.get("expected_rank", 0) or 0) for item in records]
    metrics: dict[str, Any] = {
        "case_count": count,
        "mean_reciprocal_rank": round(
            sum(1.0 / rank for rank in ranks if rank > 0) / count,
            6,
        )
        if count
        else 0.0,
    }
    for k in ks:
        metrics[f"recall_at_{k}"] = (
            round(sum(0 < rank <= k for rank in ranks) / count, 6) if count else 0.0
        )
        metrics[f"ndcg_at_{k}"] = (
            round(
                sum((1.0 / log2(rank + 1)) if 0 < rank <= k else 0.0 for rank in ranks)
                / count,
                6,
            )
            if count
            else 0.0
        )
    return metrics


def _multi_relevance_ranking_metrics(records: Sequence[Mapping[str, Any]], ks: Sequence[int]) -> dict[str, Any]:
    count = len(records)
    metrics: dict[str, Any] = {
        "case_count": count,
        "mean_reciprocal_rank": round(
            sum(1.0 / int(item["first_relevant_rank"]) for item in records if item.get("first_relevant_rank"))
            / count,
            6,
        )
        if count
        else 0.0,
    }
    for k in ks:
        recalls: list[float] = []
        ndcgs: list[float] = []
        hits = 0
        for item in records:
            relevant_ids = item.get("relevant_legal_section_ids", [])
            ranks = [int(rank) for rank in item.get("relevant_ranks", []) if int(rank) > 0]
            retrieved = sum(rank <= k for rank in ranks)
            recalls.append(retrieved / len(relevant_ids) if relevant_ids else 0.0)
            hits += bool(retrieved)
            dcg = sum(1.0 / log2(rank + 1) for rank in ranks if rank <= k)
            ideal_count = min(k, len(relevant_ids))
            ideal_dcg = sum(1.0 / log2(rank + 1) for rank in range(1, ideal_count + 1))
            ndcgs.append(dcg / ideal_dcg if ideal_dcg else 0.0)
        metrics[f"hit_rate_at_{k}"] = round(hits / count, 6) if count else 0.0
        metrics[f"recall_at_{k}"] = round(sum(recalls) / count, 6) if count else 0.0
        metrics[f"ndcg_at_{k}"] = round(sum(ndcgs) / count, 6) if count else 0.0
    return metrics


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = sqrt(sum(float(value) * float(value) for value in left))
    right_norm = sqrt(sum(float(value) * float(value) for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(float(a) * float(b) for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _private_artifact_identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    digest = sha256()
    byte_count = 0
    line_count = 0
    last_byte = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            byte_count += len(chunk)
            line_count += chunk.count(b"\n")
            last_byte = chunk[-1:]
    if byte_count and last_byte != b"\n":
        line_count += 1
    return {
        "artifact_path": str(path),
        "sha256": digest.hexdigest(),
        "byte_count": byte_count,
        "line_count": line_count,
        "suffix": path.suffix.lower(),
    }


def _private_snapshot_id(path: str | Path | None) -> str:
    if not path:
        return ""
    manifest = _read_json(path)
    snapshot_id = str(manifest.get("snapshot_id", ""))
    if not snapshot_id:
        raise ValueError("dataset snapshot manifest is missing snapshot_id")
    if manifest.get("publication_status") != "private_not_for_publication":
        raise ValueError("dataset snapshot manifest must be classified private_not_for_publication")
    return snapshot_id


def _read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise TypeError(f"expected JSONL object: {path}")
        records.append(payload)
    return records


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:{sha256(normalized.encode('utf-8')).hexdigest()[:20]}"


def _counts(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(value for value in values if value).items()))


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
