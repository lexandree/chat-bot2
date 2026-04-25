"""Resolve exact legal references against structural legal sections."""

from __future__ import annotations

from typing import Iterable

from ingestion.legal_reference_parser import parse_explicit_legal_references


def resolve_exact_reference(
    sections: Iterable[dict[str, object]],
    reference_text: str,
    *,
    as_of: str | None = None,
    default_law_code: str | None = None,
) -> dict[str, object] | None:
    parsed = parse_explicit_legal_references(reference_text, default_law_code=default_law_code)
    if not parsed:
        return None
    target = parsed[0]
    candidates = [
        section
        for section in sections
        if str(section.get("law_code", "")) == target.target_law_code
        and str(section.get("section_ref", "")) == target.target_section_ref
    ]
    if not candidates:
        return None
    if as_of:
        dated = [
            section
            for section in candidates
            if (not section.get("valid_from") or str(section.get("valid_from")) <= as_of)
            and (not section.get("valid_to") or str(section.get("valid_to")) >= as_of)
        ]
        if dated:
            return dated[0]
    for section in candidates:
        if bool(section.get("is_current", False)):
            return section
    return candidates[0]
