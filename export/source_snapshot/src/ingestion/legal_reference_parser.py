"""Explicit legal reference parsing for structural baseline construction."""

from __future__ import annotations

from dataclasses import dataclass
import re


REFERENCE_PATTERN = re.compile(
    r"(?P<prefix>§{1,2})\s*(?P<section>\d+[a-z]?)"
    r"(?:\s*Abs\.\s*(?P<subsection>\d+[a-z]?))?"
    r"(?:\s*Satz\s*(?P<sentence>\d+))?"
    r"(?:\s*Nr\.\s*(?P<number>\d+[a-z]?))?"
    r"(?:\s*(?P<law>[A-Z][A-Za-z0-9]+))?"
)


@dataclass(slots=True)
class ParsedLegalReference:
    raw_reference_text: str
    normalized_reference_text: str
    target_law_code: str
    target_section_ref: str
    reference_type: str
    resolution_state: str = "resolved"


def _normalize_reference(match: re.Match[str], default_law_code: str | None = None) -> ParsedLegalReference:
    section_ref = f"§ {match.group('section')}"
    suffix_parts: list[str] = []
    if match.group("subsection"):
        suffix_parts.append(f"Abs. {match.group('subsection')}")
    if match.group("sentence"):
        suffix_parts.append(f"Satz {match.group('sentence')}")
    if match.group("number"):
        suffix_parts.append(f"Nr. {match.group('number')}")
    normalized = " ".join([section_ref, *suffix_parts]).strip()
    law_code = (match.group("law") or default_law_code or "").strip()
    raw_text = match.group(0).strip()
    context = raw_text.lower()
    reference_type = "CITES"
    if "im sinne" in context or "begriff" in context:
        reference_type = "DEFINES"
    if "abweichend" in context or "ausnahme" in context:
        reference_type = "EXCEPTION_TO"
    return ParsedLegalReference(
        raw_reference_text=raw_text,
        normalized_reference_text=normalized,
        target_law_code=law_code,
        target_section_ref=section_ref,
        reference_type=reference_type,
        resolution_state="resolved" if law_code or default_law_code else "ambiguous",
    )


def parse_explicit_legal_references(
    text: str,
    *,
    default_law_code: str | None = None,
) -> list[ParsedLegalReference]:
    references: list[ParsedLegalReference] = []
    for match in REFERENCE_PATTERN.finditer(text):
        parsed = _normalize_reference(match, default_law_code=default_law_code)
        references.append(parsed)
    return references
