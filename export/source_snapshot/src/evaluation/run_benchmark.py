"""Minimal benchmark runner for the MVP."""

from __future__ import annotations

from bot.handlers.chat import handle_chat_message


def run_structural_legal_validation(
    validation_set: dict[str, object],
    *,
    resolver,
    traversal,
    run_id: str = "structural-baseline",
) -> dict[str, object]:
    cases = list(validation_set.get("cases", []))
    results = []
    for case in cases:
        resolved = resolver(str(case["prompt_text"]), as_of=case.get("as_of_date") or None)
        observed_refs = []
        outcome = "unresolved"
        if resolved is not None:
            observed_refs.append(str(resolved["section_id"]))
            related = traversal(str(resolved["section_id"]))
            observed_refs.extend(str(node["section_id"]) for node in related)
            expected = {str(ref) for ref in case.get("expected_support_refs", [])}
            outcome = "matched" if expected.intersection(observed_refs) else "resolved"
        results.append(
            {
                "validation_result_id": f"{run_id}:{case['case_id']}",
                "run_id": run_id,
                "case_id": case["case_id"],
                "mode": "structural_baseline",
                "observed_support_refs": observed_refs,
                "outcome_label": outcome,
                "review_notes": f"structural refs={len(observed_refs)}",
            }
        )
    return {
        "validation_set_id": validation_set["validation_set_id"],
        "mode": "structural_baseline",
        "result_count": len(results),
        "results": results,
    }


def run_semantic_legal_validation(
    validation_set: dict[str, object],
    *,
    resolver,
    traversal,
    proposition_candidates: list[dict[str, object]],
    run_id: str = "semantic-enriched",
) -> dict[str, object]:
    cases = list(validation_set.get("cases", []))
    results = []
    for case in cases:
        resolved = resolver(str(case["prompt_text"]), as_of=case.get("as_of_date") or None)
        observed_refs = []
        outcome = "unresolved"
        if resolved is not None:
            observed_refs.append(str(resolved["section_id"]))
            related = traversal(str(resolved["section_id"]))
            related_refs = [str(node["section_id"]) for node in related]
            observed_refs.extend(related_refs)
            structural_refs = {str(resolved["section_id"]), *related_refs}
            semantic_refs = []
            for candidate in proposition_candidates:
                parent_refs = {str(ref) for ref in candidate.get("structural_parent_refs", [])}
                if structural_refs.intersection(parent_refs):
                    semantic_refs.extend(sorted(parent_refs))
            observed_refs.extend(semantic_refs)
            expected = {str(ref) for ref in case.get("expected_support_refs", [])}
            outcome = "matched" if expected.intersection(observed_refs) else "resolved"
        results.append(
            {
                "validation_result_id": f"{run_id}:{case['case_id']}",
                "run_id": run_id,
                "case_id": case["case_id"],
                "mode": "semantic_enriched",
                "observed_support_refs": sorted(dict.fromkeys(observed_refs)),
                "outcome_label": outcome,
                "review_notes": f"semantic candidates={len(proposition_candidates)}",
            }
        )
    return {
        "validation_set_id": validation_set["validation_set_id"],
        "mode": "semantic_enriched",
        "result_count": len(results),
        "results": results,
    }


def build_managed_smoke_validation_set(
    validation_set: dict[str, object],
    *,
    smoke_limit: int,
) -> dict[str, object]:
    cases = list(validation_set.get("cases", []))
    return {
        **validation_set,
        "cases": cases[:smoke_limit],
    }


def run_benchmark(cases: list[dict[str, object]], services: dict[str, object]) -> list[dict[str, object]]:
    results = []
    for case in cases:
        response = handle_chat_message({"text": case["prompt_text"], "language_tags": [case["language"]]}, services)
        results.append({"case_id": case["case_id"], "kind": response["kind"], "citations": len(response["citations"])})
    return results


def run_validation_benchmark(
    question_set: dict[str, object],
    services: dict[str, object],
    *,
    mode: str,
) -> dict[str, object]:
    questions = list(question_set.get("questions", []))
    results = []
    for question in questions:
        response = handle_chat_message(
            {"text": question["prompt_text"], "language_tags": [question["language"]]},
            services,
        )
        results.append(
            {
                "question_id": question["question_id"],
                "mode": mode,
                "outcome_label": "grounded" if response["citations"] else "ungrounded",
                "observed_support_refs": [citation["citation_id"] for citation in response["citations"]],
                "review_notes": f"{mode} mode citations={len(response['citations'])}",
            }
        )
    return {
        "question_set_id": question_set["question_set_id"],
        "mode": mode,
        "result_count": len(results),
        "results": results,
    }


def compare_validation_modes(
    question_set: dict[str, object],
    services: dict[str, object],
) -> dict[str, object]:
    baseline = run_validation_benchmark(question_set, services, mode="baseline")
    enriched = run_validation_benchmark(question_set, services, mode="enriched")
    return {
        "question_set_id": question_set["question_set_id"],
        "baseline_run_ref": "baseline",
        "enriched_run_ref": "enriched",
        "baseline": baseline,
        "enriched": enriched,
        "go_no_go": "go" if enriched["result_count"] >= baseline["result_count"] else "no-go",
    }
