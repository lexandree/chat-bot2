"""Build a structural legal baseline from normalized legal preview documents."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from hashlib import sha1
from typing import Any

from graph.repositories import build_legal_extraction_repositories
from graph.types import LegalAct, LegalFragment, LegalReference, LegalSection
from ingestion.legal_reference_parser import parse_explicit_legal_references


def _checksum(text: str) -> str:
    return sha1(text.encode("utf-8")).hexdigest()


def build_structural_legal_graph(documents: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    legal_acts: dict[str, dict[str, Any]] = {}
    sections: list[dict[str, Any]] = []
    fragments: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    section_lookup: dict[tuple[str, str], str] = {}

    for document in documents:
        law_code = str(document.get("law_code", ""))
        if law_code not in legal_acts:
            legal_acts[law_code] = asdict(
                LegalAct(
                    law_code=law_code,
                    title=str(document.get("law_name") or law_code),
                    jurisdiction=str(document.get("jurisdiction", "DE")),
                    language=str(document.get("language", "de")),
                    source_uri_or_ref=str(document.get("source_uri_or_ref", "")),
                    published_at=str(document.get("published_at", "")),
                    valid_from=str(document.get("effective_from", "")),
                    current_version=True,
                )
            )
        section_id = str(document["source_id"])
        section_ref = str(document.get("section_ref", ""))
        body_text = str(document.get("body_text", ""))
        sections.append(
            asdict(
                LegalSection(
                    section_id=section_id,
                    law_code=law_code,
                    section_ref=section_ref,
                    title=str(document.get("title", "")),
                    body_text=body_text,
                    valid_from=str(document.get("effective_from", "")),
                    version_key="current",
                    is_current=True,
                )
            )
        )
        fragments.append(
            asdict(
                LegalFragment(
                    fragment_id=f"{section_id}:fragment:1",
                    section_id=section_id,
                    ordinal=1,
                    text=body_text,
                    start_ref=section_ref,
                    end_ref=section_ref,
                    checksum=_checksum(body_text or section_id),
                )
            )
        )
        section_lookup[(law_code, section_ref)] = section_id

    edges: list[dict[str, Any]] = []
    for document in documents:
        source_section_id = str(document["source_id"])
        law_code = str(document.get("law_code", ""))
        body_text = str(document.get("body_text", ""))
        for ordinal, parsed in enumerate(
            parse_explicit_legal_references(body_text, default_law_code=law_code),
            start=1,
        ):
            target_key = (parsed.target_law_code or law_code, parsed.target_section_ref)
            target_section_id = section_lookup.get(target_key, "")
            resolution_state = "resolved" if target_section_id else "unresolved"
            reference = asdict(
                LegalReference(
                    reference_id=f"{source_section_id}:ref:{ordinal}",
                    source_section_id=source_section_id,
                    raw_reference_text=parsed.raw_reference_text,
                    normalized_reference_text=parsed.normalized_reference_text,
                    target_law_code=target_key[0],
                    target_section_ref=target_key[1],
                    reference_type=parsed.reference_type,
                    resolution_state=resolution_state,
                )
            )
            references.append(reference)
            if target_section_id:
                edges.append(
                    {
                        "source_section_id": source_section_id,
                        "target_section_id": target_section_id,
                        "reference_type": parsed.reference_type,
                        "reference_id": reference["reference_id"],
                    }
                )

    return {
        "legal_acts": list(legal_acts.values()),
        "legal_sections": sections,
        "legal_fragments": fragments,
        "legal_references": references,
        "typed_edges": edges,
    }


def persist_structural_legal_graph(client, structural_graph: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    repositories = build_legal_extraction_repositories(client)
    for act in structural_graph["legal_acts"]:
        repositories["legal_act"].upsert(act)
    for section in structural_graph["legal_sections"]:
        repositories["legal_section"].upsert(section)
        client.execute(
            "MATCH (a:LegalAct {law_code: $law_code}) "
            "MATCH (s:LegalSection {section_id: $section_id}) "
            "MERGE (a)-[:HAS_SECTION]->(s)",
            law_code=section["law_code"],
            section_id=section["section_id"],
        )
    for fragment in structural_graph["legal_fragments"]:
        repositories["legal_fragment"].upsert(fragment)
        client.execute(
            "MATCH (s:LegalSection {section_id: $section_id}) "
            "MATCH (f:LegalFragment {fragment_id: $fragment_id}) "
            "MERGE (s)-[:HAS_FRAGMENT]->(f)",
            section_id=fragment["section_id"],
            fragment_id=fragment["fragment_id"],
        )
    for reference in structural_graph["legal_references"]:
        repositories["legal_reference"].upsert(reference)
        client.execute(
            "MATCH (s:LegalSection {section_id: $section_id}) "
            "MATCH (r:LegalReference {reference_id: $reference_id}) "
            "MERGE (s)-[:HAS_REFERENCE]->(r)",
            section_id=reference["source_section_id"],
            reference_id=reference["reference_id"],
        )
    for edge in structural_graph["typed_edges"]:
        client.execute(
            f"MATCH (s:LegalSection {{section_id: $source_section_id}}) "
            f"MATCH (t:LegalSection {{section_id: $target_section_id}}) "
            f"MERGE (s)-[:{edge['reference_type']}]->(t)",
            source_section_id=edge["source_section_id"],
            target_section_id=edge["target_section_id"],
        )
    return {
        "legal_act_count": len(structural_graph["legal_acts"]),
        "legal_section_count": len(structural_graph["legal_sections"]),
        "legal_fragment_count": len(structural_graph["legal_fragments"]),
        "legal_reference_count": len(structural_graph["legal_references"]),
        "typed_edge_count": len(structural_graph["typed_edges"]),
    }
