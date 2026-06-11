"""Private dataset snapshots and corpus-bounded exact-reference benchmarks."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from ingestion.legal_reference_parser import parse_explicit_legal_references
from ingestion.legal_structure_builder import build_structural_legal_graph, legal_section_id
from retrieval.legal_reference_resolver import ReferenceQuery, resolve_from_section_records


PRIVATE_SNAPSHOT_POLICY_VERSION = "private_artifact_snapshot_v1"
CORPUS_BOUNDED_REFERENCE_BENCHMARK_POLICY_VERSION = "tg_qa_corpus_bounded_explicit_reference_v1"


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
