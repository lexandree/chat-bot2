"""Legal reference parsing for structural graph construction."""

from __future__ import annotations

from dataclasses import dataclass
import re

from ingestion.legal_xml_import import normalize_section_reference


REFERENCE_PATTERN = re.compile(
    r"(?P<prefix>§{1,2})\s*(?P<section>[0-9]+[a-zA-Z]?)"
    r"(?:\s*Abs\.\s*(?P<subsection>[0-9]+[a-zA-Z]?))?"
    r"(?:\s*Satz\s*(?P<sentence>[0-9]+))?"
    r"(?:\s*Nr\.\s*(?P<number>[0-9]+[a-zA-Z]?))?"
    r"(?:\s*(?P<law>[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9]+))?"
)


@dataclass(frozen=True, slots=True)
class ParsedLegalReference:
    raw_reference_text: str
    normalized_reference_text: str
    target_law_code: str
    target_section_reference: str
    relation_type: str = "CITES"


def parse_explicit_legal_references(
    text: str,
    *,
    default_law_code: str = "",
) -> list[ParsedLegalReference]:
    references: list[ParsedLegalReference] = []
    for match in REFERENCE_PATTERN.finditer(text):
        section_reference = normalize_section_reference(f"§ {match.group('section')}")
        suffix_parts = []
        if match.group("subsection"):
            suffix_parts.append(f"Abs. {match.group('subsection')}")
        if match.group("sentence"):
            suffix_parts.append(f"Satz {match.group('sentence')}")
        if match.group("number"):
            suffix_parts.append(f"Nr. {match.group('number')}")
        normalized = " ".join([section_reference, *suffix_parts]).strip()
        law_code = match.group("law") or default_law_code
        relation_type = _infer_relation_type(match.group(0))
        references.append(
            ParsedLegalReference(
                raw_reference_text=match.group(0).strip(),
                normalized_reference_text=normalized,
                target_law_code=law_code,
                target_section_reference=section_reference,
                relation_type=relation_type,
            )
        )
    return references


def _infer_relation_type(raw_reference_text: str) -> str:
    lowered = raw_reference_text.lower()
    if "ausnahme" in lowered or "abweichend" in lowered:
        return "EXCEPTION_TO"
    if "begriff" in lowered or "im sinne" in lowered:
        return "DEFINES"
    return "CITES"
