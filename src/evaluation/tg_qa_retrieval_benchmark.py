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
REFERENCE_REVIEW_DECISIONS = {"accept", "exclude", "uncertain"}


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

    silver_metrics = _ranking_metrics(results, ks)
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
        "counts_by_expected_legal_section_id": _counts(
            str(item["expected_legal_section_id"]) for item in results
        ),
        "excluded_counts": dict(sorted(excluded_counts.items())),
        "metric_scopes": {
            "silver_all_query_explicit_targets": silver_metrics,
            "reviewed_accepted_targets": _ranking_metrics(reviewed_accepted_results, ks),
        },
        "metric_interpretation": "query_explicit_citation_recovery_silver_not_legal_relevance",
        "metric_scope_note": (
            "silver targets are explicit references in canonical questions and may be legally incorrect; "
            "an explicit reference may describe status context rather than the section that answers the question; "
            "reviewed_accepted metrics are authoritative only for decisions made under the separate review file"
        ),
        "output_path": str(output_path),
        "privacy_classification": "private_project_artifact",
        "known_limitations": [
            "semantic retrieval metrics do not measure answer correctness or completeness",
            "unreviewed query-explicit references are silver labels and may penalize legally better retrieval",
            "an explicit law reference may identify the user's status or premise rather than relevant answer support",
            "document vectors use source fragment body text only to match the current graph-write embedding contract",
            "the benchmark evaluates a bounded three-law preview rather than the full German legal corpus",
        ],
        "trust_boundary": "semantic_retrieval_benchmark_does_not_create_trusted_answer_support",
    }
    _write_jsonl(Path(output_path), results)
    _write_json(Path(summary_output_path), summary)
    return {"cases": results, "summary": summary}


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


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:{sha256(normalized.encode('utf-8')).hexdigest()[:20]}"


def _counts(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(value for value in values if value).items()))


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
