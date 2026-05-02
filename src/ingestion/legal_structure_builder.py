"""Build source/legal graph records and relationship evidence from previews."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from typing import Any, Iterable

from graph.types import CLASSIFIER_POLICY_VERSION, LegalAct, LegalFragment, LegalReference, LegalSection
from ingestion.legal_reference_parser import ParsedReferenceCandidate, parse_explicit_legal_references
from ingestion.legal_xml_import import normalize_section_reference, section_reference_slug
from ingestion.legal_preview_loader import sha256_text


def legal_act_id(law_code: str) -> str:
    return f"legal-act:{law_code}"


def legal_section_id(law_code: str, section_reference: str, *, version_identity: str = "current") -> str:
    return f"legal-section:{law_code}:{section_reference_slug(section_reference)}:{version_identity}"


def legal_fragment_id(law_code: str, section_reference: str, order_index: int) -> str:
    return f"legal-fragment:{law_code}:{section_reference_slug(section_reference)}:{order_index}"


def build_structural_legal_graph(preview: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Build the base graph shape without trusted relationship evidence."""
    legal_acts: dict[str, LegalAct] = {}
    sections: dict[str, LegalSection] = {}
    fragments: dict[str, LegalFragment] = {}

    for source_fragment in preview.get("source_fragments", []):
        law_code = str(source_fragment["law_code"])
        section_reference = str(source_fragment["section_reference"])
        document = _source_document_for_fragment(preview, str(source_fragment["source_document_id"]))
        source_status = _source_status(source_fragment, document)
        source_version_id = _source_version_id(source_fragment, document)
        source_revision_marker = _source_revision_marker(source_fragment, document)
        build_date = _build_date(source_fragment, document)
        legal_acts.setdefault(
            law_code,
            LegalAct(
                legal_act_id=legal_act_id(law_code),
                law_code=law_code,
                title=str(document.get("title") or law_code),
                source_family=str(document.get("source_family", "law")),
                jurisdiction=str(document.get("jurisdiction", "DE")),
                language=str(document.get("language", "de")),
                valid_from=str(document.get("effective_date", "")),
                is_current=True,
            ),
        )
        section_id = legal_section_id(law_code, section_reference)
        sections.setdefault(
            section_id,
            LegalSection(
                legal_section_id=section_id,
                legal_act_id=legal_act_id(law_code),
                law_code=law_code,
                section_reference=section_reference,
                title=str(source_fragment.get("title", "")),
                normalized_reference=str(source_fragment.get("normalized_reference", section_reference)),
                valid_from=str(document.get("effective_date", "")),
                version_identity="current",
                is_current=True,
                unit_status=source_status["unit_status"],
                status_marker_text=source_status["status_marker_text"],
                source_document_id=str(source_fragment.get("source_document_id", "")),
                source_fragment_id=str(source_fragment.get("source_fragment_id", "")),
                source_version_id=source_version_id,
                source_revision_marker=source_revision_marker,
                build_date=build_date,
                content_checksum=str(
                    source_fragment.get("checksum") or sha256_text(str(source_fragment.get("body_text", "")))
                ),
            ),
        )
        fragment_id = legal_fragment_id(law_code, section_reference, 1)
        fragments.setdefault(
            fragment_id,
            LegalFragment(
                legal_fragment_id=fragment_id,
                legal_section_id=section_id,
                source_fragment_id=str(source_fragment["source_fragment_id"]),
                text=str(source_fragment.get("body_text", "")),
                order_index=1,
                checksum=str(source_fragment.get("checksum") or sha256_text(str(source_fragment.get("body_text", "")))),
            ),
        )

    return {
        "source_documents": list(preview.get("source_documents", [])),
        "source_fragments": list(preview.get("source_fragments", [])),
        "legal_acts": [asdict(item) for item in legal_acts.values()],
        "legal_sections": [asdict(item) for item in sections.values()],
        "legal_fragments": [asdict(item) for item in fragments.values()],
        "legal_references": [],
    }


def build_relationship_evidence_from_preview(
    preview: dict[str, Any],
    *,
    law_codes: list[str] | None = None,
    classifier_policy_version: str = CLASSIFIER_POLICY_VERSION,
) -> list[dict[str, Any]]:
    graph = build_structural_legal_graph(preview)
    source_documents = {
        str(document.get("source_document_id", "")): document for document in preview.get("source_documents", [])
    }
    legal_sections = graph["legal_sections"]
    source_fragments = []
    for fragment in preview.get("source_fragments", []):
        law_code = str(fragment.get("law_code", ""))
        section_reference = str(fragment.get("section_reference", ""))
        source_fragments.append(
            {
                **fragment,
                "source_legal_section_id": legal_section_id(law_code, section_reference),
                "source_legal_fragment_id": legal_fragment_id(law_code, section_reference, 1),
            }
        )
    return build_relationship_evidence_from_records(
        source_fragments=source_fragments,
        legal_sections=legal_sections,
        source_documents=source_documents,
        law_codes=law_codes,
        classifier_policy_version=classifier_policy_version,
    )


def build_relationship_evidence_from_records(
    *,
    source_fragments: Iterable[dict[str, Any]],
    legal_sections: Iterable[dict[str, Any]],
    source_documents: dict[str, dict[str, Any]] | None = None,
    law_codes: list[str] | None = None,
    classifier_policy_version: str = CLASSIFIER_POLICY_VERSION,
) -> list[dict[str, Any]]:
    source_documents = source_documents or {}
    fragment_rows = sorted(
        list(source_fragments),
        key=lambda item: (
            str(item.get("law_code", "")),
            str(item.get("section_reference", "")),
            str(item.get("source_fragment_id", "")),
        ),
    )
    section_rows = sorted(
        list(legal_sections),
        key=lambda item: (
            str(item.get("law_code", "")),
            str(item.get("section_reference") or item.get("normalized_reference") or ""),
            str(item.get("legal_section_id", "")),
        ),
    )
    selected_law_codes = _selected_law_codes(law_codes, fragment_rows, section_rows)
    section_index = _section_index(section_rows)
    references: list[dict[str, Any]] = []
    for fragment in fragment_rows:
        law_code = str(fragment.get("law_code", ""))
        if law_code not in selected_law_codes:
            continue
        document = source_documents.get(str(fragment.get("source_document_id", "")), {})
        source_legal_section_id = str(
            fragment.get("source_legal_section_id")
            or legal_section_id(law_code, str(fragment.get("section_reference", "")))
        )
        source_legal_fragment_id = str(
            fragment.get("source_legal_fragment_id")
            or legal_fragment_id(law_code, str(fragment.get("section_reference", "")), 1)
        )
        temporal_metadata = _temporal_metadata(fragment, document)
        candidates = parse_explicit_legal_references(
            str(fragment.get("body_text", "")),
            default_law_code=law_code,
            source_legal_section_id=source_legal_section_id,
            source_legal_fragment_id=source_legal_fragment_id,
            source_fragment_id=str(fragment.get("source_fragment_id", "")),
            law_code=law_code,
            section_reference=str(fragment.get("section_reference", "")),
            title=str(fragment.get("title") or document.get("title") or ""),
            classifier_policy_version=classifier_policy_version,
            **temporal_metadata,
        )
        for ordinal, candidate in enumerate(candidates, start=1):
            references.append(
                asdict(
                    _resolve_candidate(
                        candidate,
                        ordinal=ordinal,
                        selected_law_codes=selected_law_codes,
                        section_index=section_index,
                    )
                )
            )
    return references


def _resolve_candidate(
    candidate: ParsedReferenceCandidate,
    *,
    ordinal: int,
    selected_law_codes: set[str],
    section_index: dict[tuple[str, str], list[dict[str, str]]],
) -> LegalReference:
    target_law_code = candidate.target_law_code
    target_section_reference = (
        normalize_section_reference(candidate.target_section_reference)
        if candidate.target_section_reference
        else ""
    )
    target_key = (target_law_code, target_section_reference)
    target_candidates = section_index.get(target_key, [])
    target_legal_section_id = ""
    unresolved_target_evidence: dict[str, Any] = {}
    target_unit_status = ""
    unresolved_reason = ""
    if not target_law_code and target_section_reference:
        resolution_status = "unresolved"
        unresolved_reason = "target_without_law_code"
        unresolved_target_evidence = _unresolved_evidence(candidate, reason=unresolved_reason)
    elif not target_section_reference:
        resolution_status = "unresolved"
        unresolved_reason = "parse_incomplete"
        unresolved_target_evidence = _unresolved_evidence(candidate, reason=unresolved_reason)
    elif target_law_code not in selected_law_codes:
        resolution_status = "out_of_scope"
        target_unit_status = "out_of_scope_law"
        unresolved_reason = "out_of_scope_law"
        unresolved_target_evidence = _unresolved_evidence(candidate, reason=unresolved_reason)
    elif len(target_candidates) == 1:
        resolution_status = "resolved"
        target_legal_section_id = target_candidates[0]["legal_section_id"]
        target_unit_status = target_candidates[0]["unit_status"] or "active"
    elif len(target_candidates) > 1:
        resolution_status = "ambiguous"
        unresolved_reason = "ambiguous_target"
        unresolved_target_evidence = _unresolved_evidence(
            candidate,
            reason=unresolved_reason,
            candidate_legal_section_ids=[item["legal_section_id"] for item in target_candidates],
        )
    else:
        resolution_status = "unresolved"
        target_unit_status = "missing_target_in_corpus"
        unresolved_reason = "missing_target_in_corpus"
        unresolved_target_evidence = _unresolved_evidence(candidate, reason=unresolved_reason)

    return LegalReference(
        legal_reference_id=_legal_reference_id(candidate, ordinal=ordinal),
        source_legal_section_id=candidate.source_legal_section_id,
        target_law_code=target_law_code,
        target_section_reference=target_section_reference,
        source_legal_fragment_id=candidate.source_legal_fragment_id,
        source_fragment_id=candidate.source_fragment_id,
        law_code=candidate.law_code,
        raw_reference_text=candidate.raw_reference_text,
        normalized_reference_text=candidate.normalized_reference_text,
        target_legal_section_id=target_legal_section_id,
        target_unit_status=target_unit_status,
        unresolved_reason=unresolved_reason,
        subsection_anchor=candidate.subsection_anchor,
        context_before=candidate.context_before,
        context_text=candidate.context_text,
        context_after=candidate.context_after,
        context_checksum=candidate.context_checksum,
        primary_relation_type=candidate.primary_relation_type,
        secondary_relation_signals=candidate.secondary_relation_signals,
        classifier_policy_version=candidate.classifier_policy_version,
        relation_type=candidate.primary_relation_type,
        resolution_status=resolution_status,
        unresolved_target_evidence=unresolved_target_evidence,
        effective_from=candidate.effective_from,
        effective_until=candidate.effective_until,
        publication_date=candidate.publication_date,
        source_version_id=candidate.source_version_id,
        source_revision_marker=candidate.source_revision_marker,
        build_date=candidate.build_date,
        temporal_context_text=candidate.temporal_context_text,
        temporal_context_checksum=candidate.temporal_context_checksum,
        temporal_evidence_status=candidate.temporal_evidence_status,
    )


def _section_index(legal_sections: Iterable[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    index: dict[tuple[str, str], list[dict[str, str]]] = {}
    for section in legal_sections:
        law_code = str(section.get("law_code", ""))
        reference = normalize_section_reference(
            str(section.get("section_reference") or section.get("normalized_reference") or "")
        )
        section_id = str(section.get("legal_section_id", ""))
        if law_code and reference and section_id:
            index.setdefault((law_code, reference), []).append(
                {
                    "legal_section_id": section_id,
                    "unit_status": str(section.get("unit_status") or "active"),
                }
            )
    for key, values in list(index.items()):
        deduped = {
            item["legal_section_id"]: item
            for item in values
        }
        index[key] = [deduped[section_id] for section_id in sorted(deduped)]
    return index


def _selected_law_codes(
    law_codes: list[str] | None,
    source_fragments: Iterable[dict[str, Any]],
    legal_sections: Iterable[dict[str, Any]],
) -> set[str]:
    if law_codes:
        return {code for code in law_codes if code}
    selected = {str(item.get("law_code", "")) for item in source_fragments if item.get("law_code")}
    selected.update(str(item.get("law_code", "")) for item in legal_sections if item.get("law_code"))
    return selected


def _temporal_metadata(fragment: dict[str, Any], document: dict[str, Any]) -> dict[str, str | bool]:
    return {
        "effective_from": str(
            fragment.get("effective_from")
            or fragment.get("effective_date")
            or document.get("effective_from")
            or document.get("effective_date")
            or ""
        ),
        "effective_until": str(fragment.get("effective_until") or document.get("effective_until") or ""),
        "publication_date": str(fragment.get("publication_date") or document.get("publication_date") or ""),
        "source_version_id": str(fragment.get("source_version_id") or document.get("source_version_id") or ""),
        "source_revision_marker": str(
            fragment.get("source_revision_marker") or document.get("source_revision_marker") or ""
        ),
        "build_date": _build_date(fragment, document),
        "temporal_metadata_expected": bool(
            fragment.get("temporal_metadata_expected") or document.get("temporal_metadata_expected") or False
        ),
    }


def _unresolved_evidence(
    candidate: ParsedReferenceCandidate,
    *,
    reason: str,
    candidate_legal_section_ids: list[str] | None = None,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "reason": reason,
        "target_law_code": candidate.target_law_code,
        "target_section_reference": candidate.target_section_reference,
        "raw_reference_text": candidate.raw_reference_text,
        "normalized_reference_text": candidate.normalized_reference_text,
    }
    if candidate_legal_section_ids:
        evidence["candidate_legal_section_ids"] = candidate_legal_section_ids
    return evidence


def _legal_reference_id(candidate: ParsedReferenceCandidate, *, ordinal: int) -> str:
    digest = sha256(
        "|".join(
            [
                candidate.parsed_reference_id,
                candidate.source_legal_section_id,
                str(ordinal),
                candidate.target_law_code,
                candidate.target_section_reference,
                candidate.context_checksum,
            ]
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"legal-reference:{candidate.source_legal_section_id}:{ordinal}:{digest}"


def _source_document_for_fragment(preview: dict[str, Any], source_document_id: str) -> dict[str, Any]:
    for document in preview.get("source_documents", []):
        if document.get("source_document_id") == source_document_id:
            return document
    return {}


_INACTIVE_MARKERS = ("(weggefallen)", "weggefallen", "aufgehoben", "außer kraft", "ausser kraft")


def _source_status(fragment: dict[str, Any], document: dict[str, Any]) -> dict[str, str]:
    for value in (
        fragment.get("status_marker_text"),
        fragment.get("unit_status_marker"),
        fragment.get("source_status"),
        document.get("status_marker_text"),
        document.get("source_status"),
        fragment.get("title"),
    ):
        marker = _inactive_marker(str(value or ""))
        if marker:
            return {"unit_status": "inactive", "status_marker_text": marker}
    body_marker = _leading_body_status_marker(str(fragment.get("body_text", "")))
    if body_marker:
        return {"unit_status": "inactive", "status_marker_text": body_marker}
    return {"unit_status": "active", "status_marker_text": ""}


def _inactive_marker(value: str) -> str:
    normalized = value.strip()
    lowered = normalized.lower()
    for marker in _INACTIVE_MARKERS:
        if marker in lowered:
            return normalized
    return ""


def _leading_body_status_marker(body_text: str) -> str:
    normalized = " ".join(body_text.split())
    lowered = normalized.lower()
    for marker in _INACTIVE_MARKERS:
        if lowered == marker or lowered.startswith(f"{marker}.") or lowered.startswith(f"{marker};"):
            first_clause = normalized.split(".", 1)[0].split(";", 1)[0].strip()
            if first_clause.lower() == marker:
                return first_clause
    return ""


def _source_version_id(fragment: dict[str, Any], document: dict[str, Any]) -> str:
    return str(fragment.get("source_version_id") or document.get("source_version_id") or "")


def _source_revision_marker(fragment: dict[str, Any], document: dict[str, Any]) -> str:
    return str(fragment.get("source_revision_marker") or document.get("source_revision_marker") or "")


def _build_date(fragment: dict[str, Any], document: dict[str, Any]) -> str:
    return str(
        fragment.get("build_date")
        or document.get("build_date")
        or fragment.get("publication_date")
        or document.get("publication_date")
        or ""
    )
