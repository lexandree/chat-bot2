from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any


CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
SEMANTIC_FIELDS = (
    "canonical_question",
    "legal_issue_frame",
    "law_area",
    "exclusion_reason",
    "facts",
    "desired_outcome",
    "authority_context",
    "hidden_issues",
    "quality_flags",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _by_task(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(record.get("task_id", "")): record for record in records if str(record.get("task_id", ""))}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _routing(record: Mapping[str, Any]) -> str:
    if str(record.get("status", "")) != "completed":
        return str(record.get("status", "missing"))
    exclusion_reason = str(record.get("exclusion_reason", ""))
    return "included" if exclusion_reason == "none" else f"excluded:{exclusion_reason}"


def _string_set(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value} if value else set()
    if isinstance(value, list):
        return {str(item) for item in value if str(item)}
    return set()


def _normalized_text(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return str(value).casefold()


def _evidence_text(record: Mapping[str, Any]) -> str:
    return " ".join(
        _normalized_text(record.get(field, ""))
        for field in ("canonical_question", "legal_issue_frame", "facts", "desired_outcome", "hidden_issues")
    )


def _check_record(record: Mapping[str, Any], checks: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    expected_status = str(checks.get("status", ""))
    if expected_status and str(record.get("status", "missing")) != expected_status:
        failures.append(f"status expected {expected_status}, got {record.get('status', 'missing')}")
    expected_routing = str(checks.get("routing", ""))
    if expected_routing and _routing(record) != expected_routing:
        failures.append(f"routing expected {expected_routing}, got {_routing(record)}")
    canonical_question = str(record.get("canonical_question", ""))
    if checks.get("forbid_cjk") and CJK_RE.search(canonical_question):
        failures.append("canonical_question contains CJK characters")
    if "max_canonical_question_marks" in checks:
        maximum = int(checks["max_canonical_question_marks"])
        if canonical_question.count("?") > maximum:
            failures.append(f"canonical_question contains more than {maximum} question marks")
    flags = _string_set(record.get("quality_flags", []))
    required_all = _string_set(checks.get("required_all_quality_flags", []))
    missing_all = sorted(required_all - flags)
    if missing_all:
        failures.append(f"missing required quality flags: {', '.join(missing_all)}")
    required_any = _string_set(checks.get("required_any_quality_flags", []))
    if required_any and not (required_any & flags):
        failures.append(f"none of required quality flags present: {', '.join(sorted(required_any))}")
    forbidden = sorted(_string_set(checks.get("forbidden_quality_flags", [])) & flags)
    if forbidden:
        failures.append(f"forbidden quality flags present: {', '.join(forbidden)}")
    allowed_law_areas = _string_set(checks.get("allowed_law_areas", []))
    if allowed_law_areas and str(record.get("law_area", "")) not in allowed_law_areas:
        failures.append(
            f"law_area expected one of {', '.join(sorted(allowed_law_areas))}, got {record.get('law_area', '')}"
        )
    canonical_question_text = _normalized_text(record.get("canonical_question", ""))
    evidence_text = _evidence_text(record)
    required_all_evidence_terms = _string_set(checks.get("required_all_evidence_terms", []))
    missing_evidence_terms = sorted(
        term for term in required_all_evidence_terms if term.casefold() not in evidence_text
    )
    if missing_evidence_terms:
        failures.append(f"missing required evidence terms: {', '.join(missing_evidence_terms)}")
    forbidden_evidence_terms = sorted(
        term
        for term in _string_set(checks.get("forbidden_evidence_terms", []))
        if term.casefold() in evidence_text
    )
    if forbidden_evidence_terms:
        failures.append(f"forbidden evidence terms present: {', '.join(forbidden_evidence_terms)}")
    required_any_canonical_terms = _string_set(checks.get("required_any_canonical_question_terms", []))
    if required_any_canonical_terms and not any(
        term.casefold() in canonical_question_text for term in required_any_canonical_terms
    ):
        failures.append(
            "none of required canonical_question terms present: "
            f"{', '.join(sorted(required_any_canonical_terms))}"
        )
    forbidden_canonical_terms = sorted(
        term
        for term in _string_set(checks.get("forbidden_canonical_question_terms", []))
        if term.casefold() in canonical_question_text
    )
    if forbidden_canonical_terms:
        failures.append(
            f"forbidden canonical_question terms present: {', '.join(forbidden_canonical_terms)}"
        )
    return failures


def _warn_record(record: Mapping[str, Any], checks: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    flags = _string_set(record.get("quality_flags", []))
    recommended_any = _string_set(checks.get("recommended_any_quality_flags", []))
    if recommended_any and not (recommended_any & flags):
        warnings.append(f"none of recommended quality flags present: {', '.join(sorted(recommended_any))}")
    return warnings


def _changed_fields(current: Mapping[str, Any], baseline: Mapping[str, Any]) -> list[str]:
    return [field for field in SEMANTIC_FIELDS if current.get(field) != baseline.get(field)]


def _row(item: Mapping[str, Any], current: Mapping[str, Any], baseline: Mapping[str, Any] | None) -> dict[str, Any]:
    checks = item.get("automatic_checks", {})
    failures = _check_record(current, checks if isinstance(checks, Mapping) else {})
    warnings = _warn_record(current, checks if isinstance(checks, Mapping) else {})
    changed_fields = _changed_fields(current, baseline) if baseline else []
    manual_on_change = bool(item.get("manual_review_required_on_change", True))
    manual_review_required = bool(failures) or bool(warnings) or baseline is None or (
        manual_on_change and bool(changed_fields)
    )
    if failures:
        status = "automatic_fail"
    elif warnings:
        status = "semantic_warning"
    elif baseline is None:
        status = "baseline_required"
    elif changed_fields:
        status = "manual_review"
    else:
        status = "stable_pass"
    return {
        "case_id": item.get("case_id", ""),
        "lesson_ids": item.get("lesson_ids", []),
        "task_id": item.get("task_id", ""),
        "expected_focus": item.get("expected_focus", ""),
        "source_question_text_redacted": item.get("source_question_text_redacted", ""),
        "source_batch_path": item.get("source_batch_path", ""),
        "automatic_checks": checks,
        "automatic_failures": failures,
        "semantic_warnings": warnings,
        "status": status,
        "manual_review_required": manual_review_required,
        "baseline_present": baseline is not None,
        "changed_fields": changed_fields,
        "current_routing": _routing(current),
        "baseline_routing": _routing(baseline) if baseline else "",
        "current": {field: current.get(field, [] if field in {"facts", "hidden_issues", "quality_flags"} else "") for field in SEMANTIC_FIELDS},
        "baseline": (
            {field: baseline.get(field, [] if field in {"facts", "hidden_issues", "quality_flags"} else "") for field in SEMANTIC_FIELDS}
            if baseline
            else {}
        ),
    }


def _render_value(value: Any) -> str:
    if isinstance(value, list):
        return "<br>".join(html.escape(str(item)) for item in value) or "<span class=\"empty\">empty</span>"
    text = str(value)
    return html.escape(text) if text else "<span class=\"empty\">empty</span>"


def _render_html(rows: list[dict[str, Any]], summary: Mapping[str, Any]) -> str:
    cards = []
    for row in rows:
        changed = ", ".join(row["changed_fields"]) or "none"
        failures = "<br>".join(html.escape(value) for value in row["automatic_failures"]) or "none"
        warnings = "<br>".join(html.escape(value) for value in row["semantic_warnings"]) or "none"
        field_rows = []
        for field in SEMANTIC_FIELDS:
            field_rows.append(
                "<tr>"
                f"<th>{html.escape(field)}</th>"
                f"<td>{_render_value(row['baseline'].get(field, ''))}</td>"
                f"<td>{_render_value(row['current'].get(field, ''))}</td>"
                "</tr>"
            )
        cards.append(
            f"""
<article class="card {html.escape(row['status'])}">
  <h2>{html.escape(row['case_id'])} <code>{html.escape(row['task_id'])}</code></h2>
  <p><strong>lessons:</strong> {html.escape(', '.join(row['lesson_ids']))}</p>
  <p><strong>expected:</strong> {html.escape(row['expected_focus'])}</p>
  <p><strong>source:</strong> {html.escape(row['source_question_text_redacted'])}</p>
  <p><strong>status:</strong> {html.escape(row['status'])}; <strong>changed:</strong> {html.escape(changed)}</p>
  <p><strong>automatic failures:</strong> {failures}</p>
  <p><strong>semantic warnings:</strong> {warnings}</p>
  <table><thead><tr><th>field</th><th>accepted baseline</th><th>current</th></tr></thead>
  <tbody>{''.join(field_rows)}</tbody></table>
</article>
"""
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>007 cumulative prompt regression</title>
<style>
body {{ font: 14px/1.45 system-ui, sans-serif; margin: 0; background: #f4f5f7; color: #202124; }}
header {{ position: sticky; top: 0; padding: 12px 20px; background: #fff; border-bottom: 1px solid #ccd0d5; z-index: 1; }}
main {{ max-width: 1500px; margin: 0 auto; padding: 16px; }}
.card {{ background: #fff; border: 1px solid #ccd0d5; border-left: 5px solid #5f6368; margin: 0 0 14px; padding: 12px; border-radius: 6px; }}
.automatic_fail {{ border-left-color: #b3261e; }} .manual_review,.baseline_required,.semantic_warning {{ border-left-color: #e37400; }}
.stable_pass {{ border-left-color: #137333; }}
h2 {{ font-size: 16px; margin: 0 0 8px; }} p {{ margin: 5px 0; }} code {{ font-size: 12px; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 10px; table-layout: fixed; }}
th, td {{ border: 1px solid #d7dce1; padding: 6px; text-align: left; vertical-align: top; overflow-wrap: anywhere; }}
th:first-child {{ width: 14%; }} .empty {{ color: #777; font-style: italic; }}
</style>
</head>
<body>
<header><strong>007 cumulative prompt regression</strong> | {html.escape(json.dumps(summary['counts'], sort_keys=True))}</header>
<main>{''.join(cards)}</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare a cumulative 007 prompt-regression run to accepted baseline.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--baseline-results", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tsv-output", type=Path, required=True)
    parser.add_argument("--html-output", type=Path, required=True)
    args = parser.parse_args()

    manifest = _read_json(args.manifest)
    current_by_task = _by_task(_read_jsonl(args.results))
    baseline_by_task = _by_task(_read_jsonl(args.baseline_results))
    selected_items = [item for item in manifest.get("items", []) if item.get("status") == "selected"]
    rows = [
        _row(item, current_by_task.get(str(item["task_id"]), {}), baseline_by_task.get(str(item["task_id"])))
        for item in selected_items
    ]
    counts = Counter(row["status"] for row in rows)
    counts["records"] = len(rows)
    counts["manual_review_required"] = sum(1 for row in rows if row["manual_review_required"])
    report = {
        "artifact_type": "tg_question_canonicalization_prompt_regression_report",
        "manifest_path": str(args.manifest),
        "results_path": str(args.results),
        "baseline_results_path": str(args.baseline_results) if args.baseline_results else "",
        "baseline_available": bool(baseline_by_task),
        "counts": dict(sorted(counts.items())),
        "rows": rows,
    }
    _write_json(args.output, report)
    args.tsv_output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "status\tcase_id\tlessons\ttask_id\tcurrent_routing\tbaseline_routing\tchanged_fields"
        "\tautomatic_failures\tsemantic_warnings"
    ]
    for row in rows:
        lines.append(
            "\t".join(
                [
                    row["status"],
                    row["case_id"],
                    ";".join(row["lesson_ids"]),
                    row["task_id"],
                    row["current_routing"],
                    row["baseline_routing"],
                    ";".join(row["changed_fields"]),
                    " | ".join(row["automatic_failures"]),
                    " | ".join(row["semantic_warnings"]),
                ]
            )
        )
    args.tsv_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(_render_html(rows, report), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "html": str(args.html_output), "counts": report["counts"]}, ensure_ascii=False))
    return 1 if counts.get("automatic_fail", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
