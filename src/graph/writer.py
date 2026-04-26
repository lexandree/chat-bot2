"""Neo4j graph write helpers for source and structural legal records."""

from __future__ import annotations

import json
from typing import Any


ALLOWED_RELATION_TYPES = {
    "CITES",
    "DEFINES",
    "APPLIES_IF",
    "REQUIRES",
    "EXCEPTION_TO",
    "EXCLUDES_IF",
    "AMENDS",
    "SUPERSEDED_BY",
}


class GraphWriter:
    def __init__(self, client: Any) -> None:
        self.client = client

    def upsert_source_document(self, record: dict[str, Any]) -> None:
        self.client.write(
            "MERGE (n:SourceDocument {source_document_id: $source_document_id}) "
            "SET n += $record",
            {"source_document_id": record["source_document_id"], "record": _neo4j_properties(record)},
        )

    def upsert_source_fragment(self, record: dict[str, Any]) -> None:
        self.client.write(
            "MERGE (n:SourceFragment {source_fragment_id: $source_fragment_id}) "
            "SET n += $record "
            "WITH n MATCH (d:SourceDocument {source_document_id: $source_document_id}) "
            "MERGE (d)-[:HAS_SOURCE_FRAGMENT]->(n)",
            {
                "source_fragment_id": record["source_fragment_id"],
                "source_document_id": record["source_document_id"],
                "record": _neo4j_properties(record),
            },
        )

    def upsert_legal_act(self, record: dict[str, Any]) -> None:
        self.client.write(
            "MERGE (n:LegalAct {legal_act_id: $legal_act_id}) SET n += $record",
            {"legal_act_id": record["legal_act_id"], "record": _neo4j_properties(record)},
        )

    def upsert_legal_section(self, record: dict[str, Any]) -> None:
        self.client.write(
            "MERGE (n:LegalSection {legal_section_id: $legal_section_id}) "
            "SET n += $record "
            "WITH n MATCH (a:LegalAct {legal_act_id: $legal_act_id}) "
            "MERGE (a)-[:HAS_SECTION]->(n)",
            {
                "legal_section_id": record["legal_section_id"],
                "legal_act_id": record["legal_act_id"],
                "record": _neo4j_properties(record),
            },
        )

    def upsert_legal_fragment(self, record: dict[str, Any]) -> None:
        self.client.write(
            "MERGE (n:LegalFragment {legal_fragment_id: $legal_fragment_id}) "
            "SET n += $record "
            "WITH n MATCH (s:LegalSection {legal_section_id: $legal_section_id}) "
            "MERGE (s)-[:HAS_LEGAL_FRAGMENT]->(n) "
            "WITH n MATCH (f:SourceFragment {source_fragment_id: $source_fragment_id}) "
            "MERGE (f)-[:MAPS_TO]->(n)",
            {
                "legal_fragment_id": record["legal_fragment_id"],
                "legal_section_id": record["legal_section_id"],
                "source_fragment_id": record["source_fragment_id"],
                "record": _neo4j_properties(record),
            },
        )

    def upsert_legal_reference(self, record: dict[str, Any]) -> None:
        self.client.write(
            "MERGE (n:LegalReference {legal_reference_id: $legal_reference_id}) "
            "SET n += $record "
            "WITH n MATCH (s:LegalSection {legal_section_id: $source_legal_section_id}) "
            "MERGE (s)-[:HAS_REFERENCE]->(n)",
            {
                "legal_reference_id": record["legal_reference_id"],
                "source_legal_section_id": record["source_legal_section_id"],
                "record": _neo4j_properties(record),
            },
        )
        if record.get("target_legal_section_id"):
            relation_type = str(record.get("relation_type") or "CITES")
            if relation_type not in ALLOWED_RELATION_TYPES:
                raise ValueError(f"unsupported legal relation type: {relation_type}")
            self.client.write(
                "MATCH (s:LegalSection {legal_section_id: $source_legal_section_id}) "
                "MATCH (t:LegalSection {legal_section_id: $target_legal_section_id}) "
                f"MERGE (s)-[:{relation_type} {{legal_reference_id: $legal_reference_id}}]->(t)",
                {
                    "source_legal_section_id": record["source_legal_section_id"],
                    "target_legal_section_id": record["target_legal_section_id"],
                    "legal_reference_id": record["legal_reference_id"],
                },
            )

    def write_source_embeddings(self, records: list[dict[str, Any]], *, preflight) -> None:
        preflight()
        for record in records:
            if record["entity_kind"] == "source_document":
                label = "SourceDocument"
                id_field = "source_document_id"
            elif record["entity_kind"] == "source_fragment":
                label = "SourceFragment"
                id_field = "source_fragment_id"
            else:
                raise ValueError(f"unsupported embedding entity kind: {record['entity_kind']}")
            self.client.write(
                f"MATCH (n:{label} {{{id_field}: $entity_id}}) "
                "SET n.embedding_v1 = $vector, "
                "n.embedding_profile_id = $embedding_profile_id, "
                "n.embedding_model_id = $model_id, "
                "n.embedding_backend_name = $backend_name, "
                "n.embedding_routing_mode = $routing_mode, "
                "n.embedding_dimensions = $vector_dimensions, "
                "n.embedding_normalized = $normalized",
                {
                    "entity_id": record["entity_id"],
                    "vector": record["vector"],
                    "embedding_profile_id": record["embedding_profile_id"],
                    "model_id": record["model_id"],
                    "backend_name": record["backend_name"],
                    "routing_mode": record["routing_mode"],
                    "vector_dimensions": record["vector_dimensions"],
                    "normalized": record["normalized"],
                },
            )


def _neo4j_properties(record: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for key, value in record.items():
        if value is None:
            continue
        if isinstance(value, dict | list):
            properties[f"{key}_json"] = json.dumps(value, sort_keys=True, separators=(",", ":"))
        else:
            properties[key] = value
    return properties
