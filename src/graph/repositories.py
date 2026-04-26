"""Graph workflow repositories for schema readiness and later operations."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from graph.schema import bootstrap_schema, build_schema_statements, candidate_review_placeholders_present
from graph.types import DeletionReport, EmbeddingRunReport, GraphReadinessReport, LoadRunReport, VerificationReport
from graph.writer import GraphWriter
from ingestion.legal_structure_builder import build_structural_legal_graph
from ingestion.verification import (
    build_deletion_report,
    build_embedding_run_report,
    build_load_report,
    build_verification_report,
)
from retrieval.embedding_service import EmbeddingInput, EmbeddingService
from retrieval.legal_reference_resolver import ReferenceQuery
from graph.types import StructuralRetrievalResult


class GraphFoundationRepository:
    def __init__(self, client: Any, *, database_name: str = "server_default") -> None:
        self.client = client
        self.database_name = database_name or "server_default"

    def prepare_foundation(self, *, embedding_dimensions: int = 1024) -> GraphReadinessReport:
        warnings: list[str] = []
        errors: list[str] = []
        connectivity_checked = False
        schema_objects: list[str] = []
        try:
            self.client.verify_connectivity()
            connectivity_checked = True
            schema_objects = bootstrap_schema(self.client, embedding_dimensions)
            status = "ready"
        except Exception as exc:  # pragma: no cover - exact driver error type varies
            status = "failed"
            errors.append(str(exc))
        statements = build_schema_statements(embedding_dimensions)
        return GraphReadinessReport(
            status=status,
            database_name=self.database_name,
            schema_objects=schema_objects,
            vector_dimensions=embedding_dimensions,
            candidate_review_placeholders_present=candidate_review_placeholders_present(statements),
            connectivity_checked=connectivity_checked,
            warnings=warnings,
            errors=errors,
        )


class GraphDataRepository:
    def __init__(self, client: Any) -> None:
        self.client = client
        self.writer = GraphWriter(client)

    def load_preview(self, preview: dict[str, Any], *, law_codes: list[str] | None = None) -> LoadRunReport:
        scoped_preview = _filter_preview(preview, law_codes)
        graph = build_structural_legal_graph(scoped_preview)
        for record in graph["source_documents"]:
            self.writer.upsert_source_document(record)
        for record in graph["source_fragments"]:
            self.writer.upsert_source_fragment(record)
        for record in graph["legal_acts"]:
            self.writer.upsert_legal_act(record)
        for record in graph["legal_sections"]:
            self.writer.upsert_legal_section(record)
        for record in graph["legal_fragments"]:
            self.writer.upsert_legal_fragment(record)
        for record in graph["legal_references"]:
            self.writer.upsert_legal_reference(record)
        return build_load_report(scoped_preview, graph, law_codes=law_codes)

    def verify_scope(self, *, law_codes: list[str] | None = None) -> VerificationReport:
        parameters = {"law_codes": law_codes or []}
        rows = self.client.read(
            "MATCH (n) WHERE size($law_codes) = 0 OR n.law_code IN $law_codes "
            "RETURN labels(n) AS labels, count(n) AS count",
            parameters,
        )
        counts: dict[str, int] = {}
        for row in rows:
            labels = row.get("labels") or []
            count = int(row.get("count", 0))
            for label in labels:
                counts[str(label)] = counts.get(str(label), 0) + count
        unresolved_rows = self.client.read(
            "MATCH (n:LegalReference) "
            "WHERE n.resolution_status <> 'resolved' "
            "AND (size($law_codes) = 0 OR n.law_code IN $law_codes) "
            "RETURN count(n) AS count",
            parameters,
        )
        if unresolved_rows:
            counts["UnresolvedLegalReference"] = int(unresolved_rows[0].get("count", 0))
        embedding_rows = self.client.read(
            "MATCH (n) WHERE n.embedding_v1 IS NOT NULL "
            "AND (size($law_codes) = 0 OR n.law_code IN $law_codes) "
            "RETURN count(n) AS embedding_count, "
            "collect(DISTINCT n.embedding_profile_id) AS profile_ids, "
            "collect(DISTINCT n.embedding_dimensions) AS vector_dimensions, "
            "collect(DISTINCT n.embedding_backend_name) AS backend_names",
            parameters,
        )
        embedding = embedding_rows[0] if embedding_rows else {}
        return build_verification_report(
            selected_scope={"law_codes": law_codes or []},
            counts=counts,
            embedding=embedding,
        )

    def delete_scope(self, *, law_codes: list[str], confirm: bool = False) -> DeletionReport:
        if not confirm:
            raise ValueError("delete requires confirmation")
        before = self.verify_scope(law_codes=law_codes)
        self.client.write(
            "MATCH (n) WHERE n.law_code IN $law_codes DETACH DELETE n",
            {"law_codes": law_codes},
        )
        return build_deletion_report(selected_scope={"law_codes": law_codes}, matched_records=_total_records(before))

    def write_embeddings(
        self,
        *,
        law_codes: list[str],
        embedding_service: EmbeddingService,
    ) -> EmbeddingRunReport:
        rows = self.client.read(
            "MATCH (n) WHERE (n:SourceDocument OR n:SourceFragment) "
            "AND (size($law_codes) = 0 OR n.law_code IN $law_codes) "
            "RETURN labels(n) AS labels, "
            "coalesce(n.source_document_id, n.source_fragment_id) AS entity_id, "
            "coalesce(n.body_text, n.title, n.source_uri, '') AS text, "
            "n.law_code AS law_code",
            {"law_codes": law_codes},
        )
        inputs = []
        for row in rows:
            labels = set(row.get("labels") or [])
            entity_kind = "source_document" if "SourceDocument" in labels else "source_fragment"
            inputs.append(
                EmbeddingInput(
                    entity_kind=entity_kind,
                    entity_id=str(row["entity_id"]),
                    text=str(row.get("text") or ""),
                    law_code=str(row.get("law_code") or ""),
                )
            )
        records = embedding_service.embed_inputs(inputs)
        self.writer.write_source_embeddings(
            [asdict(record) for record in records],
            preflight=embedding_service.preflight,
        )
        return build_embedding_run_report(
            selected_scope={"law_codes": law_codes},
            processed_count=len(records),
            skipped_count=max(0, len(inputs) - len(records)),
            failed_count=0,
            profile=embedding_service.profile,
            backend_name=embedding_service.backend.backend_name,
        )

    def resolve_reference(
        self,
        *,
        law_code: str,
        section_reference: str,
        temporal_mode: str = "current_default",
        as_of_date: str = "",
    ) -> StructuralRetrievalResult:
        query = ReferenceQuery(
            law_code=law_code,
            section_reference=section_reference,
            temporal_mode=temporal_mode,
            as_of_date=as_of_date,
        )
        normalized = query.normalized_section_reference()
        rows = self.client.read(
            "MATCH (s:LegalSection {law_code: $law_code, normalized_reference: $section_reference}) "
            "WHERE $temporal_mode <> 'current_default' OR coalesce(s.is_current, true) = true "
            "OPTIONAL MATCH (s)-[:HAS_LEGAL_FRAGMENT]->(lf:LegalFragment)<-[:MAPS_TO]-(sf:SourceFragment) "
            "RETURN s.legal_section_id AS legal_section_id, collect(sf.source_fragment_id) AS source_references "
            "ORDER BY s.legal_section_id LIMIT 1",
            {
                "law_code": law_code,
                "section_reference": normalized,
                "temporal_mode": temporal_mode,
                "as_of_date": as_of_date,
            },
        )
        if not rows:
            return StructuralRetrievalResult(
                query_reference={"law_code": law_code, "section_reference": normalized},
                matched_legal_section_id="",
                source_references=[],
                relation_types=[],
                depth_limit=0,
                fanout_limit=0,
                node_limit=0,
                visited_count=0,
                unresolved_target_evidence=[
                    {"law_code": law_code, "section_reference": normalized, "reason": "not_found"}
                ],
            )
        row = rows[0]
        return StructuralRetrievalResult(
            query_reference={"law_code": law_code, "section_reference": normalized},
            matched_legal_section_id=str(row["legal_section_id"]),
            source_references=[item for item in row.get("source_references", []) if item],
            relation_types=[],
            depth_limit=0,
            fanout_limit=0,
            node_limit=1,
            visited_count=1,
        )

    def traverse(
        self,
        *,
        legal_section_id: str,
        allowed_relation_types: list[str],
        depth_limit: int,
        fanout_limit: int,
        node_limit: int,
    ) -> StructuralRetrievalResult:
        rows = self.client.read(
            "MATCH (start:LegalSection {legal_section_id: $legal_section_id}) "
            "OPTIONAL MATCH (start)-[r]->(neighbor:LegalSection) "
            "WHERE type(r) IN $allowed_relation_types "
            "RETURN neighbor.legal_section_id AS neighbor_id, type(r) AS relation_type, "
            "r.legal_reference_id AS reference_id "
            "LIMIT $node_limit",
            {
                "legal_section_id": legal_section_id,
                "allowed_relation_types": allowed_relation_types,
                "depth_limit": depth_limit,
                "fanout_limit": fanout_limit,
                "node_limit": node_limit,
            },
        )
        relation_types = [str(row["relation_type"]) for row in rows if row.get("relation_type")]
        source_refs = [str(row["reference_id"]) for row in rows if row.get("reference_id")]
        visited = 1 + len({row.get("neighbor_id") for row in rows if row.get("neighbor_id")})
        return StructuralRetrievalResult(
            query_reference={"legal_section_id": legal_section_id},
            matched_legal_section_id=legal_section_id,
            source_references=sorted(set(source_refs)),
            relation_types=sorted(set(relation_types)),
            depth_limit=depth_limit,
            fanout_limit=fanout_limit,
            node_limit=node_limit,
            visited_count=min(visited, node_limit),
        )


def _filter_preview(preview: dict[str, Any], law_codes: list[str] | None) -> dict[str, Any]:
    if not law_codes:
        return preview
    allowed = set(law_codes)
    source_fragments = [item for item in preview.get("source_fragments", []) if item.get("law_code") in allowed]
    document_ids = {item["source_document_id"] for item in source_fragments}
    source_documents = [
        item for item in preview.get("source_documents", []) if item.get("source_document_id") in document_ids
    ]
    scoped = dict(preview)
    scoped["source_documents"] = source_documents
    scoped["source_fragments"] = source_fragments
    scoped["source_scope"] = {"source_families": ["law"], "law_codes": sorted(allowed)}
    return scoped


def _total_records(report: VerificationReport) -> int:
    return (
        report.source_document_count
        + report.source_fragment_count
        + report.legal_act_count
        + report.legal_section_count
        + report.legal_fragment_count
        + report.legal_reference_count
    )
