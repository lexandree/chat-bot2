"""Graph workflow repositories for schema readiness and later operations."""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any

from graph.schema import bootstrap_schema, build_schema_statements, candidate_review_placeholders_present
from graph.types import (
    DeletionReport,
    EmbeddingRunReport,
    GraphReadinessReport,
    LoadRunReport,
    VerificationReport,
)
from graph.writer import GraphWriter
from evaluation.load_cases import (
    build_graph_snapshot_artifact,
    build_legacy_baseline_graph_snapshot_artifact,
)
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

    def snapshot_scope(
        self,
        *,
        law_codes: list[str],
        read_only_baseline: bool = False,
        baseline_scope: dict[str, Any] | None = None,
        baseline_origin: str = "legacy_aufenthg_graph_scope",
    ):
        components = _collect_snapshot_components(self.client, law_codes=law_codes)
        selected_scope = {"law_codes": law_codes or []}
        if read_only_baseline:
            return build_legacy_baseline_graph_snapshot_artifact(
                selected_scope=selected_scope,
                source_scope=components["source_scope"],
                counts=components["counts"],
                labels=components["labels"],
                relation_types=components["relation_types"],
                sample_ids=components["sample_ids"],
                source_coverage=components["source_coverage"],
                embedding_profile_metadata=components["embedding_profile_metadata"],
                unresolved_reference_evidence=components["unresolved_reference_evidence"],
                baseline_scope=baseline_scope or selected_scope,
                baseline_origin=baseline_origin,
            )
        return build_graph_snapshot_artifact(
            selected_scope=selected_scope,
            source_scope=components["source_scope"],
            counts=components["counts"],
            labels=components["labels"],
            relation_types=components["relation_types"],
            sample_ids=components["sample_ids"],
            source_coverage=components["source_coverage"],
            embedding_profile_metadata=components["embedding_profile_metadata"],
            unresolved_reference_evidence=components["unresolved_reference_evidence"],
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


def _collect_snapshot_components(client: Any, *, law_codes: list[str]) -> dict[str, Any]:
    parameters = {"law_codes": law_codes or [], "limit": 5}
    counts, labels = _collect_label_counts(client, parameters)
    relation_types = _collect_relation_types(client, parameters)
    sample_ids = _collect_sample_ids(client, parameters)
    source_coverage = {
        "law_codes": sorted(set(law_codes or [])),
        "source_document_count": counts.get("SourceDocument", 0),
        "source_fragment_count": counts.get("SourceFragment", 0),
        "legal_act_count": counts.get("LegalAct", 0),
        "legal_section_count": counts.get("LegalSection", 0),
        "legal_fragment_count": counts.get("LegalFragment", 0),
        "legal_reference_count": counts.get("LegalReference", 0),
        "unresolved_reference_count": counts.get("UnresolvedLegalReference", 0),
    }
    embedding_profile_metadata = _collect_embedding_metadata(client, parameters)
    unresolved_reference_evidence = _collect_unresolved_reference_evidence(client, parameters)
    source_scope = {"source_families": ["law"], "law_codes": source_coverage["law_codes"]}
    return {
        "counts": counts,
        "labels": labels,
        "relation_types": relation_types,
        "sample_ids": sample_ids,
        "source_coverage": source_coverage,
        "embedding_profile_metadata": embedding_profile_metadata,
        "unresolved_reference_evidence": unresolved_reference_evidence,
        "source_scope": source_scope,
    }


def _collect_label_counts(client: Any, parameters: dict[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
    rows = client.read(
        "MATCH (n) "
        "WHERE size($law_codes) = 0 OR n.law_code IN $law_codes "
        "RETURN labels(n) AS labels, count(n) AS count",
        parameters,
    )
    counts: dict[str, int] = {}
    labels: dict[str, int] = {}
    for row in rows:
        count = int(row.get("count", 0))
        for label in row.get("labels") or []:
            label_name = str(label)
            counts[label_name] = counts.get(label_name, 0) + count
            labels[label_name] = labels.get(label_name, 0) + count
    unresolved_rows = client.read(
        "MATCH (n:LegalReference) "
        "WHERE n.resolution_status <> 'resolved' "
        "AND (size($law_codes) = 0 OR n.law_code IN $law_codes) "
        "RETURN count(n) AS count",
        parameters,
    )
    unresolved_count = int(unresolved_rows[0].get("count", 0)) if unresolved_rows else 0
    counts["UnresolvedLegalReference"] = unresolved_count
    counts["node_count"] = sum(labels.values())
    counts["relationship_count"] = _relation_count(client, parameters)
    return counts, labels


def _relation_count(client: Any, parameters: dict[str, Any]) -> int:
    rows = client.read(
        "MATCH (start)-[r]->(end) "
        "WHERE size($law_codes) = 0 OR coalesce(start.law_code, end.law_code) IN $law_codes "
        "RETURN count(r) AS count",
        parameters,
    )
    if not rows:
        return 0
    return int(rows[0].get("count", 0))


def _collect_relation_types(client: Any, parameters: dict[str, Any]) -> dict[str, int]:
    rows = client.read(
        "MATCH (start)-[r]->(end) "
        "WHERE size($law_codes) = 0 OR coalesce(start.law_code, end.law_code) IN $law_codes "
        "RETURN type(r) AS relation_type, count(r) AS count "
        "ORDER BY relation_type",
        parameters,
    )
    relation_types: dict[str, int] = {}
    for row in rows:
        relation_type = str(row.get("relation_type") or "")
        if not relation_type:
            continue
        relation_types[relation_type] = int(row.get("count", 0))
    return relation_types


def _collect_sample_ids(client: Any, parameters: dict[str, Any]) -> dict[str, list[str]]:
    sample_specs = [
        ("SourceDocument", "source_document_id", "source_document_ids"),
        ("SourceFragment", "source_fragment_id", "source_fragment_ids"),
        ("LegalAct", "legal_act_id", "legal_act_ids"),
        ("LegalSection", "legal_section_id", "legal_section_ids"),
        ("LegalFragment", "legal_fragment_id", "legal_fragment_ids"),
        ("LegalReference", "legal_reference_id", "legal_reference_ids"),
    ]
    sample_ids: dict[str, list[str]] = {}
    for label, id_field, output_key in sample_specs:
        rows = client.read(
            f"MATCH (n:{label}) "
            "WHERE size($law_codes) = 0 OR n.law_code IN $law_codes "
            f"RETURN n.{id_field} AS id ORDER BY id LIMIT $limit",
            parameters,
        )
        sample_ids[output_key] = [str(row.get("id")) for row in rows if row.get("id")]
    return sample_ids


def _collect_embedding_metadata(client: Any, parameters: dict[str, Any]) -> dict[str, Any]:
    rows = client.read(
        "MATCH (n) "
        "WHERE n.embedding_v1 IS NOT NULL "
        "AND (size($law_codes) = 0 OR n.law_code IN $law_codes) "
        "RETURN count(n) AS embedding_count, "
        "collect(DISTINCT n.embedding_profile_id) AS profile_ids, "
        "collect(DISTINCT n.embedding_model_id) AS model_ids, "
        "collect(DISTINCT n.embedding_dimensions) AS vector_dimensions, "
        "collect(DISTINCT n.embedding_backend_name) AS backend_names, "
        "collect(DISTINCT n.embedding_normalized) AS normalized_flags",
        parameters,
    )
    row = rows[0] if rows else {}
    return {
        "embedding_count": int(row.get("embedding_count", 0) or 0),
        "profile_ids": [item for item in row.get("profile_ids", []) if item],
        "model_ids": [item for item in row.get("model_ids", []) if item],
        "vector_dimensions": [int(item) for item in row.get("vector_dimensions", []) if item],
        "backend_names": [item for item in row.get("backend_names", []) if item],
        "normalized_flags": [bool(item) for item in row.get("normalized_flags", []) if item is not None],
    }


def _collect_unresolved_reference_evidence(client: Any, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    rows = client.read(
        "MATCH (n:LegalReference) "
        "WHERE n.resolution_status <> 'resolved' "
        "AND (size($law_codes) = 0 OR n.law_code IN $law_codes) "
        "RETURN n.legal_reference_id AS legal_reference_id, "
        "n.source_legal_section_id AS source_legal_section_id, "
        "n.source_legal_fragment_id AS source_legal_fragment_id, "
        "n.target_law_code AS target_law_code, "
        "n.target_section_reference AS target_section_reference, "
        "n.relation_type AS relation_type, "
        "n.resolution_status AS resolution_status, "
        "n.raw_reference_text AS raw_reference_text, "
        "n.normalized_reference_text AS normalized_reference_text, "
        "coalesce(n.unresolved_target_evidence_json, '') AS unresolved_target_evidence_json "
        "ORDER BY n.legal_reference_id",
        parameters,
    )
    evidence: list[dict[str, Any]] = []
    for row in rows:
        raw_payload = row.get("unresolved_target_evidence_json") or ""
        try:
            unresolved_target_evidence = json.loads(raw_payload) if raw_payload else {}
        except json.JSONDecodeError:
            unresolved_target_evidence = {"raw": raw_payload}
        evidence.append(
            {
                "legal_reference_id": row.get("legal_reference_id", ""),
                "source_legal_section_id": row.get("source_legal_section_id", ""),
                "source_legal_fragment_id": row.get("source_legal_fragment_id", ""),
                "target_law_code": row.get("target_law_code", ""),
                "target_section_reference": row.get("target_section_reference", ""),
                "relation_type": row.get("relation_type", ""),
                "resolution_status": row.get("resolution_status", ""),
                "raw_reference_text": row.get("raw_reference_text", ""),
                "normalized_reference_text": row.get("normalized_reference_text", ""),
                "unresolved_target_evidence": unresolved_target_evidence,
            }
        )
    return evidence
