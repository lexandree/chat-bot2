"""Build structural legal graph records from preview artifacts."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from graph.types import LegalAct, LegalFragment, LegalReference, LegalSection
from ingestion.legal_reference_parser import parse_explicit_legal_references
from ingestion.legal_xml_import import section_reference_slug
from ingestion.legal_preview_loader import sha256_text


def legal_act_id(law_code: str) -> str:
    return f"legal-act:{law_code}"


def legal_section_id(law_code: str, section_reference: str, *, version_identity: str = "current") -> str:
    return f"legal-section:{law_code}:{section_reference_slug(section_reference)}:{version_identity}"


def legal_fragment_id(law_code: str, section_reference: str, order_index: int) -> str:
    return f"legal-fragment:{law_code}:{section_reference_slug(section_reference)}:{order_index}"


def build_structural_legal_graph(preview: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    legal_acts: dict[str, LegalAct] = {}
    sections: list[LegalSection] = []
    fragments: list[LegalFragment] = []
    references: list[dict[str, Any]] = []
    section_lookup: dict[tuple[str, str], str] = {}

    for source_fragment in preview.get("source_fragments", []):
        law_code = str(source_fragment["law_code"])
        section_reference = str(source_fragment["section_reference"])
        document = _source_document_for_fragment(preview, str(source_fragment["source_document_id"]))
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
        section_lookup[(law_code, section_reference)] = section_id
        sections.append(
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
            )
        )
        fragments.append(
            LegalFragment(
                legal_fragment_id=legal_fragment_id(law_code, section_reference, 1),
                legal_section_id=section_id,
                source_fragment_id=str(source_fragment["source_fragment_id"]),
                text=str(source_fragment.get("body_text", "")),
                order_index=1,
                checksum=str(source_fragment.get("checksum") or sha256_text(str(source_fragment.get("body_text", "")))),
            )
        )

    for source_fragment in preview.get("source_fragments", []):
        law_code = str(source_fragment["law_code"])
        section_reference = str(source_fragment["section_reference"])
        source_section_id = legal_section_id(law_code, section_reference)
        parsed_refs = parse_explicit_legal_references(
            str(source_fragment.get("body_text", "")),
            default_law_code=law_code,
        )
        for ordinal, parsed in enumerate(parsed_refs, start=1):
            target_key = (parsed.target_law_code or law_code, parsed.target_section_reference)
            target_section_id = section_lookup.get(target_key, "")
            status = "resolved" if target_section_id else "unresolved"
            reference = asdict(
                LegalReference(
                    legal_reference_id=f"legal-reference:{source_section_id}:{ordinal}",
                    source_legal_section_id=source_section_id,
                    source_legal_fragment_id=legal_fragment_id(law_code, section_reference, 1),
                    target_law_code=target_key[0],
                    target_section_reference=target_key[1],
                    target_legal_section_id=target_section_id,
                    relation_type=parsed.relation_type,
                    resolution_status=status,
                    unresolved_target_evidence=(
                        {}
                        if target_section_id
                        else {
                            "target_law_code": target_key[0],
                            "target_section_reference": target_key[1],
                            "raw_reference_text": parsed.raw_reference_text,
                        }
                    ),
                    raw_reference_text=parsed.raw_reference_text,
                    normalized_reference_text=parsed.normalized_reference_text,
                )
            )
            reference["law_code"] = law_code
            references.append(reference)

    return {
        "source_documents": list(preview.get("source_documents", [])),
        "source_fragments": list(preview.get("source_fragments", [])),
        "legal_acts": [asdict(item) for item in legal_acts.values()],
        "legal_sections": [asdict(item) for item in sections],
        "legal_fragments": [asdict(item) for item in fragments],
        "legal_references": references,
    }


def _source_document_for_fragment(preview: dict[str, Any], source_document_id: str) -> dict[str, Any]:
    for document in preview.get("source_documents", []):
        if document.get("source_document_id") == source_document_id:
            return document
    return {}
