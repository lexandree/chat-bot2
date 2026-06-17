"""Context-aware legal reference parsing for relationship evidence."""

from __future__ import annotations

from hashlib import sha256
import re

from graph.types import (
    CLASSIFIER_POLICY_VERSION,
    DEFERRED_RELATION_TYPES,
    MANDATORY_CLASSIFIER_RELATION_TYPES,
    ParsedReferenceCandidate,
)
from ingestion.legal_xml_import import normalize_section_reference


REFERENCE_PATTERN = re.compile(
    r"(?P<prefix>§{1,2})\s*(?P<section>[0-9]+[a-zA-Z]?)"
    r"(?:\s*(?:Abs\.|Absatz)\s*(?P<subsection>[0-9]+[a-zA-Z]?))?"
    r"(?:\s*Satz\s*(?P<sentence>[0-9]+))?"
    r"(?:\s*(?:Nr\.|Nummer)\s*(?P<number>[0-9]+[a-zA-Z]?))?"
    r"(?:\s*(?!(?:Absatz|Abs\.|Satz|Nr\.|Nummer)\b)"
    r"(?P<law>[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9/]*[A-Z][A-Za-zÄÖÜäöüß0-9/]*))?"
)

LAW_NAME_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bVerwaltungsverfahrensgesetz(?:es)?\b", re.IGNORECASE), "VwVfG"),
    (re.compile(r"\bAufenthaltsgesetz(?:es)?\b", re.IGNORECASE), "AufenthG"),
    (re.compile(r"\bAsylgesetz(?:es)?\b", re.IGNORECASE), "AsylG"),
    (re.compile(r"\bAsylbewerberleistungsgesetz(?:es)?\b", re.IGNORECASE), "AsylbLG"),
    (re.compile(r"\bBeschäftigungsverordnung\b", re.IGNORECASE), "BeschV"),
    (re.compile(r"\bAufenthaltsverordnung\b", re.IGNORECASE), "AufenthV"),
    (re.compile(r"\bStaatsangehörigkeitsgesetz(?:es)?\b", re.IGNORECASE), "StAG"),
    (re.compile(r"\bIntegrationskursverordnung\b", re.IGNORECASE), "IntV"),
    (re.compile(r"\bVerwaltungsgerichtsordnung\b", re.IGNORECASE), "VwGO"),
    (re.compile(r"\bZivilprozessordnung\b", re.IGNORECASE), "ZPO"),
    (re.compile(r"\bStrafgesetzbuch(?:es)?\b", re.IGNORECASE), "StGB"),
    (re.compile(r"\bBürgerlich(?:es|en)\s+Gesetzbuch(?:es|s)?\b", re.IGNORECASE), "BGB"),
    (re.compile(r"\bZweit(?:es|en)\s+Buch(?:es)?\s+Sozialgesetzbuch\b", re.IGNORECASE), "SGB_2"),
    (re.compile(r"\bDritt(?:es|en)\s+Buch(?:es)?\s+Sozialgesetzbuch\b", re.IGNORECASE), "SGB_3"),
    (re.compile(r"\bF(?:ü|ue)nft(?:es|en)\s+Buch(?:es)?\s+Sozialgesetzbuch\b", re.IGNORECASE), "SGB_5"),
    (re.compile(r"\bAcht(?:es|en)\s+Buch(?:es)?\s+Sozialgesetzbuch\b", re.IGNORECASE), "SGB_8"),
    (re.compile(r"\bZehnt(?:es|en)\s+Buch(?:es)?\s+Sozialgesetzbuch\b", re.IGNORECASE), "SGB_10"),
    (re.compile(r"\bZw(?:ö|oe)lft(?:es|en)\s+Buch(?:es)?\s+Sozialgesetzbuch\b", re.IGNORECASE), "SGB_12"),
)

SENTENCE_BOUNDARY_PATTERN = re.compile(r"[.!?]\s+|\n+")
TEMPORAL_HINT_PATTERN = re.compile(
    r"\b(ab|bis|seit|fassung|geändert|änderung|aufgehoben|ersetzt|tritt|inkraft|"
    r"außerkraft|uebergang|übergang)\b",
    re.IGNORECASE,
)
CONTEXT_WINDOW_CHARS = 160

_SIGNAL_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "EXCEPTION_TO",
        (
            r"\babweichend\b",
            r"\bausnahme\b",
            r"\bausgenommen\b",
            r"\bunbeschadet\b",
        ),
    ),
    (
        "EXCLUDES_IF",
        (
            r"\bgilt\s+nicht\b",
            r"\bnicht\s+anzuwenden\b",
            r"\bausgeschlossen\b",
        ),
    ),
    (
        "APPLIES_IF",
        (
            r"\bgilt\b[^.?!;\n]{0,80}\bwenn\b",
            r"\bsofern\b",
            r"\bsoweit\b",
            r"\banwendbar\b",
            r"\banzuwenden\b[^.?!;\n]{0,80}\bwenn\b",
        ),
    ),
    (
        "REQUIRES",
        (
            r"\bsetzt\s+voraus\b",
            r"\bvoraussetzung(?:en)?\b",
            r"\berforderlich\b",
            r"\bmuss\b",
            r"\bbedarf\b",
            r"\banforderung(?:en)?\b",
        ),
    ),
    (
        "DEFINES",
        (
            r"\bim\s+sinne\b",
            r"\bbegriff(?:e)?\b",
            r"\bbedeutet\b",
            r"\bdefinition\b",
            r"\bdefiniert\b",
        ),
    ),
    (
        "AMENDS",
        (
            r"\bändert\b",
            r"\bgeändert\b",
            r"\bergänzt\b",
            r"\baufgehoben\b",
        ),
    ),
    (
        "SUPERSEDED_BY",
        (
            r"\bersetzt\b",
            r"\bersetzte\b",
            r"\btritt\s+an\s+die\s+stelle\b",
        ),
    ),
)


def parse_explicit_legal_references(
    text: str,
    *,
    default_law_code: str = "",
    source_legal_section_id: str = "",
    source_legal_fragment_id: str = "",
    source_fragment_id: str = "",
    law_code: str = "",
    section_reference: str = "",
    title: str = "",
    classifier_policy_version: str = CLASSIFIER_POLICY_VERSION,
    effective_from: str = "",
    effective_until: str = "",
    publication_date: str = "",
    source_version_id: str = "",
    source_revision_marker: str = "",
    build_date: str = "",
    temporal_metadata_expected: bool = False,
    context_window_chars: int = CONTEXT_WINDOW_CHARS,
) -> list[ParsedReferenceCandidate]:
    """Parse explicit section references and emit pre-resolution evidence."""
    references: list[ParsedReferenceCandidate] = []
    source_law_code = law_code or default_law_code
    for ordinal, match in enumerate(REFERENCE_PATTERN.finditer(text), start=1):
        raw_reference_text = match.group(0).strip()
        target_section_reference = normalize_section_reference(f"§ {match.group('section')}")
        normalized_reference_text = _normalized_reference_text(match, target_section_reference)
        explicit_law = _explicit_law_code(text, match)
        target_law_code = explicit_law or default_law_code or law_code
        context_before, context_text, context_after = _context_window(
            text,
            match.start(),
            match.end(),
            context_window_chars=context_window_chars,
        )
        context_checksum = _checksum_context(context_before, context_text, context_after)
        primary, secondary = _classify_relation(
            title=title,
            context_before=context_before,
            context_text=context_text,
            context_after=context_after,
        )
        temporal_context_text = _temporal_context(title=title, context_text=context_text)
        temporal_context_checksum = (
            _checksum_text(_normalize_whitespace(temporal_context_text)) if temporal_context_text else ""
        )
        temporal_evidence_status = _temporal_evidence_status(
            structured_values=[
                effective_from,
                effective_until,
                publication_date,
                source_version_id,
                source_revision_marker,
            ],
            temporal_context_text=temporal_context_text,
            temporal_metadata_expected=temporal_metadata_expected,
        )
        parsed_reference_id = _parsed_reference_id(
            source_legal_section_id=source_legal_section_id,
            source_fragment_id=source_fragment_id,
            source_law_code=source_law_code,
            section_reference=section_reference,
            ordinal=ordinal,
            raw_reference_text=raw_reference_text,
            context_checksum=context_checksum,
        )
        references.append(
            ParsedReferenceCandidate(
                parsed_reference_id=parsed_reference_id,
                source_legal_section_id=source_legal_section_id,
                source_legal_fragment_id=source_legal_fragment_id,
                source_fragment_id=source_fragment_id,
                law_code=source_law_code,
                raw_reference_text=raw_reference_text,
                normalized_reference_text=normalized_reference_text,
                target_law_code=target_law_code,
                target_section_reference=target_section_reference,
                target_law_code_explicit=bool(explicit_law),
                subsection_anchor=_subsection_anchor(match, target_section_reference),
                context_before=context_before,
                context_text=context_text,
                context_after=context_after,
                context_checksum=context_checksum,
                primary_relation_type=primary,
                secondary_relation_signals=secondary,
                classifier_policy_version=classifier_policy_version,
                effective_from=effective_from,
                effective_until=effective_until,
                publication_date=publication_date,
                source_version_id=source_version_id,
                source_revision_marker=source_revision_marker,
                build_date=build_date,
                temporal_context_text=temporal_context_text,
                temporal_context_checksum=temporal_context_checksum,
                temporal_evidence_status=temporal_evidence_status,
            )
        )
    return references


def _explicit_law_code(text: str, match: re.Match[str]) -> str:
    explicit_law = match.group("law")
    if explicit_law:
        return _canonical_law_code(explicit_law)

    sentence_tail = _same_sentence_tail(text, match.end())
    for pattern, law_code in LAW_NAME_ALIASES:
        alias_match = pattern.search(sentence_tail)
        if alias_match and "§" not in sentence_tail[: alias_match.start()]:
            return law_code
    return ""


def _canonical_law_code(value: str) -> str:
    for pattern, law_code in LAW_NAME_ALIASES:
        if pattern.fullmatch(value):
            return law_code
    return value


def _same_sentence_tail(text: str, start: int) -> str:
    next_boundary = SENTENCE_BOUNDARY_PATTERN.search(text[start:])
    end = len(text) if next_boundary is None else start + next_boundary.start()
    return text[start:end]


def _normalized_reference_text(match: re.Match[str], section_reference: str) -> str:
    suffix_parts = []
    if match.group("subsection"):
        suffix_parts.append(f"Abs. {match.group('subsection')}")
    if match.group("sentence"):
        suffix_parts.append(f"Satz {match.group('sentence')}")
    if match.group("number"):
        suffix_parts.append(f"Nr. {match.group('number')}")
    return " ".join([section_reference, *suffix_parts]).strip()


def _subsection_anchor(match: re.Match[str], section_reference: str) -> dict[str, str | bool]:
    anchor: dict[str, str | bool] = {"section_reference": section_reference}
    if match.group("prefix") == "§§":
        anchor["range_reference"] = True
    if match.group("subsection"):
        anchor["subsection"] = match.group("subsection")
    if match.group("sentence"):
        anchor["sentence"] = match.group("sentence")
    if match.group("number"):
        anchor["number"] = match.group("number")
    return anchor


def _context_window(
    text: str,
    start: int,
    end: int,
    *,
    context_window_chars: int,
) -> tuple[str, str, str]:
    sentence_start, sentence_end = _sentence_bounds(text, start, end)
    context_text = text[sentence_start:sentence_end].strip()
    before_start = max(0, sentence_start - context_window_chars)
    after_end = min(len(text), sentence_end + context_window_chars)
    context_before = text[before_start:sentence_start].strip()
    context_after = text[sentence_end:after_end].strip()
    return (
        _normalize_whitespace(context_before),
        _normalize_whitespace(context_text),
        _normalize_whitespace(context_after),
    )


def _sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    sentence_start = 0
    for boundary in SENTENCE_BOUNDARY_PATTERN.finditer(text[:start]):
        sentence_start = boundary.end()
    next_match = SENTENCE_BOUNDARY_PATTERN.search(text[end:])
    sentence_end = len(text) if next_match is None else end + next_match.start() + 1
    return sentence_start, sentence_end


def _classify_relation(
    *,
    title: str,
    context_before: str,
    context_text: str,
    context_after: str,
) -> tuple[str, list[str]]:
    evidence_text = " ".join(
        part for part in (title, context_before, context_text, context_after) if part
    ).lower()
    matched: list[str] = []
    for relation_type, patterns in _SIGNAL_PATTERNS:
        if any(re.search(pattern, evidence_text, flags=re.IGNORECASE) for pattern in patterns):
            matched.append(relation_type)
    if not matched:
        return "CITES", []
    primary = matched[0]
    secondary = [relation_type for relation_type in matched[1:] if relation_type != primary]
    if primary in DEFERRED_RELATION_TYPES:
        secondary = [*secondary, "CITES"]
    return primary, secondary


def _temporal_context(*, title: str, context_text: str) -> str:
    evidence_text = " ".join(part for part in (title, context_text) if part)
    if TEMPORAL_HINT_PATTERN.search(evidence_text):
        return _normalize_whitespace(evidence_text)
    return ""


def _temporal_evidence_status(
    *,
    structured_values: list[str],
    temporal_context_text: str,
    temporal_metadata_expected: bool,
) -> str:
    has_structured = any(bool(value) for value in structured_values)
    if has_structured:
        return "available"
    if temporal_context_text:
        return "partial"
    if temporal_metadata_expected:
        return "not_available"
    return "not_applicable"


def _parsed_reference_id(
    *,
    source_legal_section_id: str,
    source_fragment_id: str,
    source_law_code: str,
    section_reference: str,
    ordinal: int,
    raw_reference_text: str,
    context_checksum: str,
) -> str:
    base = source_legal_section_id or source_fragment_id or f"{source_law_code}:{section_reference}" or "unknown"
    digest = _checksum_text(f"{base}|{ordinal}|{raw_reference_text}|{context_checksum}")[:12]
    return f"parsed-reference:{base}:{ordinal}:{digest}"


def _checksum_context(context_before: str, context_text: str, context_after: str) -> str:
    normalized = _normalize_whitespace(" ".join([context_before, context_text, context_after]))
    return _checksum_text(normalized)


def _checksum_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


__all__ = [
    "MANDATORY_CLASSIFIER_RELATION_TYPES",
    "ParsedReferenceCandidate",
    "parse_explicit_legal_references",
]
