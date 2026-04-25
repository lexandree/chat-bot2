"""Prompt and parsing helpers for LLM-backed legal proposition extraction."""

from __future__ import annotations

import json
from typing import Any


REQUIRED_PROPOSITION_FIELDS = (
    "proposition_text",
    "proposition_type",
    "supporting_source_citations",
    "structural_parent_references",
)


def build_proposition_prompt(
    *,
    fragment: dict[str, object],
    section: dict[str, object],
    prompt_or_policy_version: str,
) -> str:
    return (
        "Extract grounded legal propositions from the provided fragment.\n"
        "Return JSON with a top-level 'propositions' array.\n"
        "Each proposition must include:\n"
        "- proposition_text\n"
        "- proposition_type\n"
        "- supporting_source_citations\n"
        "- structural_parent_references\n"
        f"Policy version: {prompt_or_policy_version}\n"
        f"Law code: {section.get('law_code', '')}\n"
        f"Section ref: {section.get('section_ref', '')}\n"
        f"Fragment id: {fragment.get('fragment_id', '')}\n"
        "Fragment text:\n"
        f"{fragment.get('text', '')}\n"
    )


def parse_proposition_output(raw_output: str | dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload: Any = raw_output
    if isinstance(raw_output, str):
        payload = json.loads(raw_output)
    if isinstance(payload, dict):
        propositions = payload.get("propositions", [])
    else:
        propositions = payload
    if not isinstance(propositions, list):
        raise ValueError("Proposition output must be a list or a dict with 'propositions'")
    normalized: list[dict[str, Any]] = []
    for proposition in propositions:
        if not isinstance(proposition, dict):
            raise ValueError("Each proposition output must be an object")
        for field in REQUIRED_PROPOSITION_FIELDS:
            if field not in proposition:
                raise ValueError(f"Missing required proposition field: {field}")
        normalized.append(
            {
                "proposition_text": str(proposition["proposition_text"]).strip(),
                "proposition_type": str(proposition["proposition_type"]).strip(),
                "supporting_source_citations": [str(item) for item in proposition["supporting_source_citations"]],
                "structural_parent_references": [str(item) for item in proposition["structural_parent_references"]],
            }
        )
    return normalized
