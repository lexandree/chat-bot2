"""Exact legal reference resolution without generated answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ingestion.legal_xml_import import normalize_section_reference
from graph.types import StructuralRetrievalResult


@dataclass(frozen=True, slots=True)
class ReferenceQuery:
    law_code: str
    section_reference: str
    temporal_mode: str = "current_default"
    as_of_date: str = ""

    def normalized_section_reference(self) -> str:
        return normalize_section_reference(self.section_reference)


def resolve_from_section_records(
    query: ReferenceQuery,
    sections: list[dict[str, Any]],
) -> StructuralRetrievalResult:
    normalized_ref = query.normalized_section_reference()
    candidates = [
        section
        for section in sections
        if section.get("law_code") == query.law_code
        and section.get("normalized_reference", section.get("section_reference")) == normalized_ref
    ]
    if query.temporal_mode == "current_default":
        current = [section for section in candidates if section.get("is_current", True)]
        if current:
            candidates = current
    if not candidates:
        return StructuralRetrievalResult(
            query_reference={"law_code": query.law_code, "section_reference": normalized_ref},
            matched_legal_section_id="",
            source_references=[],
            relation_types=[],
            depth_limit=0,
            fanout_limit=0,
            node_limit=0,
            visited_count=0,
            unresolved_target_evidence=[
                {"law_code": query.law_code, "section_reference": normalized_ref, "reason": "not_found"}
            ],
        )
    selected = sorted(candidates, key=lambda item: str(item.get("legal_section_id", "")))[0]
    return StructuralRetrievalResult(
        query_reference={"law_code": query.law_code, "section_reference": normalized_ref},
        matched_legal_section_id=str(selected["legal_section_id"]),
        source_references=list(selected.get("source_references", [])),
        relation_types=[],
        depth_limit=0,
        fanout_limit=0,
        node_limit=1,
        visited_count=1,
    )
