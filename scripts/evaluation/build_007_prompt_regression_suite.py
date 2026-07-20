from __future__ import annotations

import argparse
from hashlib import sha256
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY = Path("specs/007-legal-question-canonicalization/prompt-regression-cases.json")
DEFAULT_DATA_DIR = Path("data/evaluation/tg_qa_canonicalization")
PROMPT_PROFILE_DIR = Path("src/evaluation/prompt_profiles")
PRIMARY_BATCH_NAMES = [
    "real_data_007_bulk_1_1000_v6_batch.jsonl",
    "real_data_007_bulk_1001_2000_batch.jsonl",
    "real_data_007_bulk_2001_3000_batch.jsonl",
    "real_data_007_bulk_3001_4000_batch.jsonl",
    "real_data_007_bulk_4001_5000_batch.jsonl",
    "real_data_007_canonicalization_batch.jsonl",
]
DERIVED_NAME_MARKERS = (
    "adjudication",
    "current",
    "failed",
    "partial",
    "retry",
    "review",
    "routed",
    "smoke",
    "verify",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _stable_json_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _task_identity_payload(task: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "task_id": str(task.get("task_id", "")),
        "task_scope": str(task.get("task_scope", "question_candidate")),
        "candidate_id": str(task.get("candidate_id", "")),
        "canonicalization_contract_version": str(task.get("canonicalization_contract_version", "")),
        "prompt_version": str(task.get("prompt_version", "")),
        "prompt_example_set_id": str(task.get("prompt_example_set_id", "")),
        "input": dict(task.get("input", {})),
        "expected_output_schema": dict(task.get("expected_output_schema", {})),
        "retry_context": dict(task.get("retry_context", {})),
    }
    source_identity = task.get("canonicalization_source_identity", {})
    if isinstance(source_identity, Mapping) and source_identity:
        payload["canonicalization_source_identity"] = dict(source_identity)
    return payload


def _bind_prompt_profile(records: list[dict[str, Any]], prompt_version: str) -> dict[str, str]:
    profile_path = PROMPT_PROFILE_DIR / f"{prompt_version}.json"
    profile = _read_json(profile_path)
    if str(profile.get("prompt_version", "")) != prompt_version:
        raise ValueError(f"prompt profile version mismatch: {profile_path}")
    profile_hash = _stable_json_hash(profile)
    task_identities: dict[str, dict[str, str]] = {}
    for record in records:
        record["canonicalization_contract_version"] = "tg_question_canonicalization_v2"
        record["prompt_version"] = prompt_version
        record["prompt_example_set_id"] = str(profile["prompt_example_set_id"])
        record["expected_output_schema"] = dict(profile["expected_output_schema"])
        task_id = str(record.get("task_id", ""))
        task_identities[task_id] = {
            "task_id": task_id,
            "task_input_hash": _stable_json_hash(_task_identity_payload(record)),
            "prompt_profile_hash": profile_hash,
        }
    batch_hash = _stable_json_hash([task_identities[key] for key in sorted(task_identities)])
    batch_id = f"tg-question-canonicalization-batch:{batch_hash[:20]}"
    for record in records:
        identity = task_identities[str(record["task_id"])]
        record.update(
            {
                "canonicalization_identity_policy_version": "tg_question_canonicalization_identity_v1",
                "canonicalization_batch_id": batch_id,
                "canonicalization_batch_hash": batch_hash,
                "task_input_hash": identity["task_input_hash"],
                "prompt_profile_hash": profile_hash,
            }
        )
    return {
        "prompt_version": prompt_version,
        "prompt_profile_hash": profile_hash,
        "canonicalization_batch_id": batch_id,
        "canonicalization_batch_hash": batch_hash,
    }


def _batch_paths(data_dir: Path) -> list[Path]:
    primary = [data_dir / name for name in PRIMARY_BATCH_NAMES if (data_dir / name).exists()]
    primary_set = set(primary)
    remaining = [path for path in data_dir.glob("*_batch.jsonl") if path not in primary_set]
    remaining.sort(key=lambda path: (any(marker in path.name for marker in DERIVED_NAME_MARKERS), path.name))
    return [*primary, *remaining]


def _selected_cases(registry: Mapping[str, Any], stage: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen_case_ids: set[str] = set()
    seen_task_ids: set[str] = set()
    for raw_case in registry.get("cases", []):
        if not isinstance(raw_case, Mapping):
            continue
        case = dict(raw_case)
        case_id = str(case.get("case_id", ""))
        if not case_id or case_id in seen_case_ids:
            raise ValueError(f"missing or duplicate case_id: {case_id!r}")
        seen_case_ids.add(case_id)
        prompt_families = {str(value) for value in case.get("prompt_families", [])}
        if stage not in prompt_families or str(case.get("source_kind", "")) != "real_task":
            continue
        task_id = str(case.get("task_id", ""))
        if not task_id or task_id in seen_task_ids:
            raise ValueError(f"missing or duplicate real task_id for {stage}: {task_id!r}")
        seen_task_ids.add(task_id)
        cases.append(case)
    return cases


def _registered_real_task_ids(registry: Mapping[str, Any]) -> set[str]:
    return {
        str(case.get("task_id", ""))
        for case in registry.get("cases", [])
        if isinstance(case, Mapping) and str(case.get("source_kind", "")) == "real_task" and str(case.get("task_id", ""))
    }


def _historical_smoke_task_ids(data_dir: Path) -> set[str]:
    task_ids: set[str] = set()
    for path in sorted(data_dir.glob("*smoke*batch.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                task_id = str(json.loads(line).get("task_id", ""))
                if task_id.startswith("tg-question-canonicalization-task:"):
                    task_ids.add(task_id)
    return task_ids


def _index_tasks(paths: list[Path], wanted_task_ids: set[str]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    records: dict[str, dict[str, Any]] = {}
    sources: dict[str, str] = {}
    for path in paths:
        if len(records) == len(wanted_task_ids):
            break
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                task_id = str(record.get("task_id", ""))
                if task_id in wanted_task_ids and task_id not in records:
                    records[task_id] = record
                    sources[task_id] = str(path)
    return records, sources


def _source_text(record: Mapping[str, Any]) -> str:
    input_payload = record.get("input", {})
    if isinstance(input_payload, Mapping):
        return str(input_payload.get("question_text_redacted", input_payload.get("question_text", "")))
    return str(record.get("question_text_redacted", record.get("question_text", "")))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build cumulative 007 prompt-regression batches from tracked task ids.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--stage", default="canonicalizer")
    parser.add_argument("--prompt-version", default="")
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    registry = _read_json(args.registry)
    cases = _selected_cases(registry, args.stage)
    if args.case_id:
        selected_case_ids = set(args.case_id)
        cases = [case for case in cases if str(case.get("case_id", "")) in selected_case_ids]
        found_case_ids = {str(case.get("case_id", "")) for case in cases}
        missing_case_ids = sorted(selected_case_ids - found_case_ids)
        if missing_case_ids:
            raise ValueError(f"unknown case ids for {args.stage}: {', '.join(missing_case_ids)}")
    task_ids = {str(case["task_id"]) for case in cases}
    registered_real_task_ids = _registered_real_task_ids(registry)
    historical_smoke_task_ids = _historical_smoke_task_ids(args.data_dir)
    unregistered_historical_smoke_task_ids = sorted(historical_smoke_task_ids - registered_real_task_ids)
    batch_paths = _batch_paths(args.data_dir)
    records_by_task, source_by_task = _index_tasks(batch_paths, task_ids)
    defaults = registry.get("case_defaults", {})
    default_checks = defaults.get("automatic_checks", {}) if isinstance(defaults, Mapping) else {}

    selected_records: list[dict[str, Any]] = []
    manifest_items: list[dict[str, Any]] = []
    for case in cases:
        task_id = str(case["task_id"])
        record = records_by_task.get(task_id)
        checks = dict(default_checks) if isinstance(default_checks, Mapping) else {}
        case_checks = case.get("automatic_checks", {})
        if isinstance(case_checks, Mapping):
            checks.update(case_checks)
        item = {
            "case_id": case["case_id"],
            "lesson_ids": case.get("lesson_ids", []),
            "task_id": task_id,
            "expected_focus": case.get("expected_focus", ""),
            "automatic_checks": checks,
            "manual_review_required_on_change": case.get(
                "manual_review_required_on_change",
                defaults.get("manual_review_required_on_change", True) if isinstance(defaults, Mapping) else True,
            ),
        }
        if record is None:
            manifest_items.append({**item, "status": "missing"})
            continue
        selected_records.append(record)
        manifest_items.append(
            {
                **item,
                "status": "selected",
                "candidate_id": str(record.get("candidate_id", "")),
                "source_batch_path": source_by_task[task_id],
                "source_question_text_redacted": _source_text(record),
            }
        )

    missing = [item for item in manifest_items if item["status"] == "missing"]
    manifest = {
        "artifact_type": "tg_question_canonicalization_prompt_regression_manifest",
        "registry_path": str(args.registry),
        "registry_version": registry.get("registry_version", ""),
        "stage": args.stage,
        "output_batch": str(args.output),
        "selected_count": len(selected_records),
        "missing_count": len(missing),
        "historical_smoke_task_count": len(historical_smoke_task_ids),
        "unregistered_historical_smoke_task_count": len(unregistered_historical_smoke_task_ids),
        "unregistered_historical_smoke_task_ids": unregistered_historical_smoke_task_ids,
        "searched_batch_paths": [str(path) for path in batch_paths],
        "items": manifest_items,
    }
    prompt_identity = _bind_prompt_profile(selected_records, args.prompt_version) if args.prompt_version else {}
    manifest.update(prompt_identity)
    _write_jsonl(args.output, selected_records)
    _write_json(args.manifest_output, manifest)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "manifest": str(args.manifest_output),
                "selected_count": len(selected_records),
                "missing_count": len(missing),
                "missing_task_ids": [item["task_id"] for item in missing],
                "unregistered_historical_smoke_task_count": len(unregistered_historical_smoke_task_ids),
                "unregistered_historical_smoke_task_ids": unregistered_historical_smoke_task_ids,
            },
            ensure_ascii=False,
        )
    )
    return 0 if args.allow_missing or (not missing and not unregistered_historical_smoke_task_ids) else 1


if __name__ == "__main__":
    raise SystemExit(main())
