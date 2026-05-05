"""Graph workflow repositories for schema readiness and later operations."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import re
from typing import Any

from graph.schema import bootstrap_schema, build_schema_statements, candidate_review_placeholders_present
from graph.types import (
    CLASSIFIER_POLICY_VERSION,
    STRUCTURE_CLASSES,
    STRUCTURE_CLASS_RULES_VERSION,
    DeletionReport,
    EmbeddingRunReport,
    GraphReadinessReport,
    LoadRunReport,
    RELATION_TYPES,
    RESOLUTION_STATUSES,
    RelationshipRefreshReport,
    RelationshipVerificationReport,
    TARGET_UNIT_STATUSES,
    TEMPORAL_EVIDENCE_STATUSES,
    UNIT_STATUSES,
    UNRESOLVED_REASONS,
    VerificationReport,
)
from graph.writer import GraphWriter
from evaluation.load_cases import (
    build_corpus_readiness_artifact,
    build_graph_snapshot_artifact,
    build_legacy_baseline_graph_snapshot_artifact,
    build_relationship_quality_artifact,
    build_structural_workflow_artifact,
)
from ingestion.legal_structure_builder import (
    build_relationship_evidence_from_records,
    build_structural_legal_graph,
)
from ingestion.verification import (
    build_deletion_report,
    build_embedding_run_report,
    build_load_report,
    build_verification_report,
)
from retrieval.embedding_service import EmbeddingInput, EmbeddingService
from retrieval.legal_reference_resolver import ReferenceQuery
from retrieval.legal_traversal import (
    TraversalEdge,
    bounded_structural_traversal,
    normalize_allowed_relation_types,
)
from graph.types import StructuralRetrievalResult
from graph.types import StructuralWorkflowRequest


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
        return build_load_report(scoped_preview, graph, law_codes=law_codes)

    def refresh_relationships(
        self,
        *,
        law_codes: list[str],
        classifier_policy_version: str = CLASSIFIER_POLICY_VERSION,
    ) -> RelationshipRefreshReport:
        if not law_codes:
            raise ValueError("relationship refresh requires at least one law code")
        started_at = _utc_timestamp()
        try:
            source = _collect_relationship_source(self.client, law_codes=law_codes)
            references = build_relationship_evidence_from_records(
                source_fragments=source["source_fragments"],
                legal_sections=source["legal_sections"],
                source_documents=source["source_documents"],
                law_codes=law_codes,
                classifier_policy_version=classifier_policy_version,
            )
            self.writer.cleanup_relationships_for_scope(law_codes=law_codes)
            for reference in references:
                self.writer.upsert_legal_reference(reference)
            status = "completed"
            errors: list[str] = []
        except Exception as exc:
            references = []
            source = {"source_fragments": []}
            status = "failed"
            errors = [str(exc)]
        finished_at = _utc_timestamp()
        counts_by_relation_type = _count_records(references, "primary_relation_type", RELATION_TYPES)
        counts_by_resolution_status = _count_records(references, "resolution_status", RESOLUTION_STATUSES)
        counts_by_target_unit_status = _count_records(references, "target_unit_status", TARGET_UNIT_STATUSES)
        counts_by_unresolved_reason = _count_records(references, "unresolved_reason", UNRESOLVED_REASONS)
        resolved_count = counts_by_resolution_status.get("resolved", 0)
        return RelationshipRefreshReport(
            refresh_id=f"relationship-refresh:{classifier_policy_version}:{','.join(sorted(law_codes))}",
            selected_scope={"law_codes": law_codes},
            classifier_policy_version=classifier_policy_version,
            started_at=started_at,
            finished_at=finished_at,
            processed_fragment_count=len(source.get("source_fragments", [])),
            created_reference_count=len(references),
            updated_reference_count=0,
            created_edge_count=resolved_count,
            updated_edge_count=0,
            skipped_count=0,
            failed_count=1 if status == "failed" else 0,
            status=status,
            counts_by_relation_type=counts_by_relation_type,
            counts_by_resolution_status=counts_by_resolution_status,
            counts_by_target_unit_status=counts_by_target_unit_status,
            counts_by_unresolved_reason=counts_by_unresolved_reason,
            errors=errors,
        )

    def verify_relationships(
        self,
        *,
        law_codes: list[str],
        classifier_policy_version: str = "",
    ) -> RelationshipVerificationReport:
        version = classifier_policy_version or _collect_classifier_policy_version(self.client, law_codes)
        counts_by_relation_type = _collect_reference_relation_counts(self.client, law_codes=law_codes)
        counts_by_resolution_status = _collect_reference_status_counts(self.client, law_codes=law_codes)
        counts_by_target_unit_status = _collect_reference_target_status_counts(
            self.client,
            law_codes=law_codes,
        )
        counts_by_unresolved_reason = _collect_reference_unresolved_reason_counts(
            self.client,
            law_codes=law_codes,
        )
        sample_reference_ids = _collect_reference_ids(self.client, law_codes=law_codes, limit=10)
        sample_edge_ids = _collect_relationship_edge_ids(self.client, law_codes=law_codes, limit=10)
        unresolved_evidence = _collect_reference_evidence(
            self.client,
            law_codes=law_codes,
            statuses=["unresolved", "out_of_scope"],
            limit=10,
        )
        ambiguous_evidence = _collect_reference_evidence(
            self.client,
            law_codes=law_codes,
            statuses=["ambiguous"],
            limit=10,
        )
        return RelationshipVerificationReport(
            selected_scope={"law_codes": law_codes},
            classifier_policy_version=version,
            counts_by_relation_type=counts_by_relation_type,
            counts_by_resolution_status=counts_by_resolution_status,
            counts_by_target_unit_status=counts_by_target_unit_status,
            counts_by_unresolved_reason=counts_by_unresolved_reason,
            sample_reference_ids=sample_reference_ids,
            sample_edge_ids=sample_edge_ids,
            unresolved_reference_evidence=unresolved_evidence,
            ambiguous_reference_evidence=ambiguous_evidence,
        )

    def relationship_quality_artifact(
        self,
        *,
        law_codes: list[str],
        classifier_policy_version: str = "",
    ):
        version = classifier_policy_version or _collect_classifier_policy_version(self.client, law_codes)
        selected_scope = {"law_codes": law_codes}
        return build_relationship_quality_artifact(
            selected_scope=selected_scope,
            classifier_policy_version=version,
            generated_at=_utc_timestamp(),
            counts_by_relation_type=_collect_reference_relation_counts(self.client, law_codes=law_codes),
            counts_by_resolution_status=_collect_reference_status_counts(self.client, law_codes=law_codes),
            counts_by_source_unit_status=_collect_source_unit_status_counts(
                self.client,
                law_codes=law_codes,
            ),
            counts_by_target_unit_status=_collect_reference_target_status_counts(
                self.client,
                law_codes=law_codes,
            ),
            counts_by_unresolved_reason=_collect_reference_unresolved_reason_counts(
                self.client,
                law_codes=law_codes,
            ),
            sample_edges_by_relation_type=_collect_sample_edges_by_relation_type(
                self.client,
                law_codes=law_codes,
                limit=5,
            ),
            sample_reference_evidence=_collect_reference_evidence(
                self.client,
                law_codes=law_codes,
                statuses=list(RESOLUTION_STATUSES),
                limit=10,
            ),
            top_unresolved_targets=_collect_top_unresolved_targets(self.client, law_codes=law_codes, limit=10),
            top_missing_targets=_collect_top_missing_targets(self.client, law_codes=law_codes, limit=10),
            source_to_relation_coverage=_collect_source_to_relation_coverage(
                self.client,
                law_codes=law_codes,
            ),
            fanout_summary=_collect_relationship_fanout_summary(self.client, law_codes=law_codes, limit=10),
            temporal_metadata_completeness=_collect_temporal_metadata_completeness(
                self.client,
                law_codes=law_codes,
                selected_scope=selected_scope,
            ),
        )

    def corpus_readiness_artifact(self, *, law_codes: list[str]):
        components = _collect_corpus_readiness_components(self.client, law_codes=law_codes)
        return build_corpus_readiness_artifact(
            selected_scope={"law_codes": law_codes},
            generated_at=_utc_timestamp(),
            counts_by_unit_status=components["counts_by_unit_status"],
            counts_by_structure_class=components["counts_by_structure_class"],
            active_unit_samples=components["active_unit_samples"],
            inactive_unit_samples=components["inactive_unit_samples"],
            complexity_summary=components["complexity_summary"],
            excluded_semantic_candidates=components["excluded_semantic_candidates"],
        )

    def structural_workflow_artifact(
        self,
        *,
        workflow_mode: str,
        seed_legal_section_ids: list[str] | None = None,
        law_codes: list[str] | None = None,
        allowed_relation_types: list[str] | None = None,
        direction: str = "outgoing",
        max_depth: int = 1,
        fanout_limit: int = 25,
        node_limit: int = 100,
        edge_limit: int = 500,
        source_sample_limit: int = 5,
        include_boundary_stops: bool = True,
        include_inactive_sections: bool = True,
        missing_target_inventory_reference: dict[str, Any] | None = None,
        source_relationship_quality_artifact: str = "",
    ):
        seed_ids = sorted({str(item) for item in (seed_legal_section_ids or []) if str(item)})
        law_scope = sorted({str(item) for item in (law_codes or []) if str(item)})
        relation_types = sorted(normalize_allowed_relation_types(allowed_relation_types or RELATION_TYPES))
        request = StructuralWorkflowRequest(
            workflow_mode=workflow_mode,
            seed_legal_section_ids=seed_ids,
            law_codes=law_scope,
            direction=direction,
            max_depth=max_depth,
            allowed_relation_types=relation_types,
            fanout_limit=fanout_limit,
            node_limit=node_limit,
            edge_limit=edge_limit,
            source_sample_limit=source_sample_limit,
            include_boundary_stops=include_boundary_stops,
            include_inactive_sections=include_inactive_sections,
        )
        if workflow_mode == "seed_neighborhood":
            components = _collect_seed_neighborhood_components(
                self.client,
                seed_legal_section_ids=seed_ids,
                law_codes=law_scope,
                allowed_relation_types=relation_types,
                direction=direction,
                max_depth=max_depth,
                fanout_limit=fanout_limit,
                node_limit=node_limit,
                edge_limit=edge_limit,
            )
        elif workflow_mode == "law_scope_overview":
            components = _collect_law_scope_overview_components(
                self.client,
                law_codes=law_scope,
                allowed_relation_types=relation_types,
                direction=direction,
                node_limit=node_limit,
                edge_limit=edge_limit,
            )
        else:
            raise ValueError(f"unknown structural workflow mode: {workflow_mode}")
        unresolved_references = []
        if include_boundary_stops:
            if workflow_mode == "seed_neighborhood":
                unresolved_references = _collect_workflow_unresolved_references_by_sections(
                    self.client,
                    legal_section_ids=[item["legal_section_id"] for item in components["sections"]],
                )
            else:
                unresolved_references = _collect_workflow_unresolved_references_by_law_code(
                    self.client,
                    law_codes=law_scope,
                )
        return build_structural_workflow_artifact(
            workflow_request=request,
            selected_scope={"source_families": ["law"], "law_codes": law_scope},
            generated_at=_utc_timestamp(),
            sections=components["sections"],
            resolved_edges=components["resolved_edges"],
            unresolved_references=unresolved_references,
            traversal_metadata=components["traversal_metadata"],
            missing_target_inventory_reference=missing_target_inventory_reference,
            source_relationship_quality_artifact=source_relationship_quality_artifact,
        )

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
        for status, count in _collect_source_unit_status_counts(self.client, law_codes=law_codes or []).items():
            counts[f"LegalSection:{status}"] = count
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
        allowed_relation_types = sorted(normalize_allowed_relation_types(allowed_relation_types))
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


def _collect_seed_neighborhood_components(
    client: Any,
    *,
    seed_legal_section_ids: list[str],
    law_codes: list[str],
    allowed_relation_types: list[str],
    direction: str,
    max_depth: int,
    fanout_limit: int,
    node_limit: int,
    edge_limit: int,
) -> dict[str, Any]:
    if not seed_legal_section_ids:
        raise ValueError("seed_neighborhood requires seed legal section ids")
    candidate_edge_limit = max(edge_limit, node_limit * max(fanout_limit, 1), 1)
    edge_rows = _collect_workflow_resolved_edge_rows(
        client,
        law_codes=law_codes,
        allowed_relation_types=allowed_relation_types,
        direction=direction,
        limit=candidate_edge_limit,
    )
    edge_index = _workflow_edge_index(edge_rows)
    traversal_edges = [
        TraversalEdge(
            source_id=row["source_legal_section_id"],
            target_id=row["target_legal_section_id"],
            relation_type=row["relation_type"],
            source_references=[row["legal_reference_id"]] if row.get("legal_reference_id") else [],
        )
        for row in edge_rows
    ]
    traversal = bounded_structural_traversal(
        seed_section_ids=seed_legal_section_ids,
        edges=traversal_edges,
        allowed_relation_types=allowed_relation_types,
        direction=direction,
        depth_limit=max_depth,
        fanout_limit=fanout_limit,
        node_limit=node_limit,
        edge_limit=edge_limit,
    )
    sections = _collect_workflow_sections_by_ids(client, legal_section_ids=traversal.visited_section_ids)
    found_section_ids = {section["legal_section_id"] for section in sections}
    missing_seeds = sorted(set(seed_legal_section_ids).difference(found_section_ids))
    if missing_seeds:
        raise ValueError(f"seed legal section not found: {missing_seeds}")
    role_by_id = {
        section_id: "seed" if section_id in seed_legal_section_ids else "resolved_neighbor"
        for section_id in traversal.visited_section_ids
    }
    section_records = [
        _workflow_section_record(
            section,
            role=("inactive_context" if section.get("unit_status") == "inactive" and role_by_id[section["legal_section_id"]] != "seed" else role_by_id[section["legal_section_id"]]),
            depth=traversal.section_depths.get(section["legal_section_id"], 0),
        )
        for section in sections
    ]
    resolved_edges = []
    for traversed_edge in traversal.traversed_edges:
        key = (
            traversed_edge.source_id,
            traversed_edge.target_id,
            traversed_edge.relation_type,
        )
        resolved_edges.append(
            _workflow_edge_record(
                edge_index.get(key, []),
                source_id=traversed_edge.source_id,
                target_id=traversed_edge.target_id,
                relation_type=traversed_edge.relation_type,
                depth=traversed_edge.depth,
                cycle_boundary=traversed_edge.cycle_boundary,
                truncated=traversed_edge.truncated,
            )
        )
    return {
        "sections": section_records,
        "resolved_edges": resolved_edges,
        "traversal_metadata": {
            "truncation_count": traversal.truncation_count,
            "cycle_boundary_count": traversal.cycle_boundary_count,
            "skipped_path_count": traversal.skipped_path_count,
        },
    }


def _collect_law_scope_overview_components(
    client: Any,
    *,
    law_codes: list[str],
    allowed_relation_types: list[str],
    direction: str,
    node_limit: int,
    edge_limit: int,
) -> dict[str, Any]:
    if not law_codes:
        raise ValueError("law_scope_overview requires law codes")
    scope_sections = _collect_workflow_sections_by_law_code(client, law_codes=law_codes, limit=node_limit + 1)
    edge_rows = _collect_workflow_resolved_edge_rows(
        client,
        law_codes=law_codes,
        allowed_relation_types=allowed_relation_types,
        direction=direction,
        limit=edge_limit + 1,
    )
    endpoint_ids = sorted(
        {
            row[item]
            for row in edge_rows
            for item in ("source_legal_section_id", "target_legal_section_id")
            if row.get(item)
        }
    )
    endpoint_sections = _collect_workflow_sections_by_ids(client, legal_section_ids=endpoint_ids)
    section_by_id = {section["legal_section_id"]: section for section in endpoint_sections}
    for section in scope_sections:
        section_by_id.setdefault(section["legal_section_id"], section)
    section_records = []
    for section in section_by_id.values():
        if section.get("law_code") in law_codes:
            role = "scope_member"
        elif section.get("unit_status") == "inactive":
            role = "inactive_context"
        else:
            role = "cross_scope_context"
        section_records.append(_workflow_section_record(section, role=role, depth=0))
    resolved_edges = [
        _workflow_edge_record(
            [row],
            source_id=row["source_legal_section_id"],
            target_id=row["target_legal_section_id"],
            relation_type=row["relation_type"],
            depth=1,
        )
        for row in edge_rows
    ]
    return {
        "sections": section_records,
        "resolved_edges": resolved_edges,
        "traversal_metadata": {
            "truncation_count": 0,
            "cycle_boundary_count": 0,
            "skipped_path_count": 0,
        },
    }


def _collect_workflow_sections_by_law_code(
    client: Any,
    *,
    law_codes: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in client.read(
            "MATCH (s:LegalSection) "
            "WHERE s.law_code IN $law_codes "
            "RETURN s.legal_section_id AS legal_section_id, "
            "s.legal_act_id AS legal_act_id, "
            "s.law_code AS law_code, "
            "s.section_reference AS section_reference, "
            "s.normalized_reference AS normalized_reference, "
            "s.title AS title, "
            "coalesce(s.unit_status, 'active') AS unit_status, "
            "s.status_marker_text AS status_marker_text, "
            "s.source_document_id AS source_document_id, "
            "s.source_fragment_id AS source_fragment_id, "
            "s.source_version_id AS source_version_id, "
            "s.source_revision_marker AS source_revision_marker, "
            "s.build_date AS build_date, "
            "s.content_checksum AS content_checksum "
            "ORDER BY s.law_code, s.normalized_reference, s.legal_section_id "
            "LIMIT $limit",
            {"law_codes": law_codes, "limit": limit},
        )
    ]


def _collect_workflow_sections_by_ids(
    client: Any,
    *,
    legal_section_ids: list[str],
) -> list[dict[str, Any]]:
    if not legal_section_ids:
        return []
    return [
        dict(row)
        for row in client.read(
            "MATCH (s:LegalSection) "
            "WHERE s.legal_section_id IN $legal_section_ids "
            "RETURN s.legal_section_id AS legal_section_id, "
            "s.legal_act_id AS legal_act_id, "
            "s.law_code AS law_code, "
            "s.section_reference AS section_reference, "
            "s.normalized_reference AS normalized_reference, "
            "s.title AS title, "
            "coalesce(s.unit_status, 'active') AS unit_status, "
            "s.status_marker_text AS status_marker_text, "
            "s.source_document_id AS source_document_id, "
            "s.source_fragment_id AS source_fragment_id, "
            "s.source_version_id AS source_version_id, "
            "s.source_revision_marker AS source_revision_marker, "
            "s.build_date AS build_date, "
            "s.content_checksum AS content_checksum "
            "ORDER BY s.law_code, s.normalized_reference, s.legal_section_id",
            {"legal_section_ids": legal_section_ids},
        )
    ]


def _collect_workflow_resolved_edge_rows(
    client: Any,
    *,
    law_codes: list[str],
    allowed_relation_types: list[str],
    direction: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows = client.read(
        "MATCH (s:LegalSection)-[r]->(t:LegalSection) "
        "WHERE type(r) IN $allowed_relation_types "
        "AND (size($law_codes) = 0 "
        "OR ($direction = 'outgoing' AND s.law_code IN $law_codes) "
        "OR ($direction = 'incoming' AND t.law_code IN $law_codes) "
        "OR ($direction = 'both' AND (s.law_code IN $law_codes OR t.law_code IN $law_codes))) "
        "OPTIONAL MATCH (s)-[:HAS_REFERENCE]->(ref:LegalReference {legal_reference_id: r.legal_reference_id}) "
        "RETURN s.legal_section_id AS source_legal_section_id, "
        "t.legal_section_id AS target_legal_section_id, "
        "type(r) AS relation_type, "
        "r.legal_reference_id AS legal_reference_id, "
        "ref.source_fragment_id AS source_fragment_id, "
        "coalesce(ref.target_law_code, t.law_code) AS target_law_code, "
        "coalesce(ref.target_section_reference, t.section_reference) AS target_section_reference, "
        "coalesce(r.target_unit_status, ref.target_unit_status, t.unit_status, 'active') AS target_unit_status, "
        "coalesce(r.classifier_policy_version, ref.classifier_policy_version, '') AS classifier_policy_version, "
        "coalesce(r.effective_from, ref.effective_from, '') AS effective_from, "
        "coalesce(r.effective_until, ref.effective_until, '') AS effective_until, "
        "coalesce(r.publication_date, ref.publication_date, '') AS publication_date, "
        "coalesce(r.source_version_id, ref.source_version_id, '') AS source_version_id, "
        "coalesce(r.source_revision_marker, ref.source_revision_marker, '') AS source_revision_marker, "
        "coalesce(r.build_date, ref.build_date, '') AS build_date, "
        "coalesce(r.temporal_evidence_status, ref.temporal_evidence_status, '') AS temporal_evidence_status "
        "ORDER BY relation_type, source_legal_section_id, target_legal_section_id, legal_reference_id "
        "LIMIT $limit",
        {
            "law_codes": law_codes,
            "allowed_relation_types": allowed_relation_types,
            "direction": direction,
            "limit": limit,
        },
    )
    return [dict(row) for row in rows if row.get("source_legal_section_id") and row.get("target_legal_section_id")]


def _collect_workflow_unresolved_references_by_law_code(
    client: Any,
    *,
    law_codes: list[str],
) -> list[dict[str, Any]]:
    return _collect_workflow_unresolved_references(
        client,
        where_clause="n.law_code IN $law_codes",
        parameters={"law_codes": law_codes},
    )


def _collect_workflow_unresolved_references_by_sections(
    client: Any,
    *,
    legal_section_ids: list[str],
) -> list[dict[str, Any]]:
    if not legal_section_ids:
        return []
    return _collect_workflow_unresolved_references(
        client,
        where_clause="n.source_legal_section_id IN $legal_section_ids",
        parameters={"legal_section_ids": legal_section_ids},
    )


def _collect_workflow_unresolved_references(
    client: Any,
    *,
    where_clause: str,
    parameters: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = client.read(
        "MATCH (n:LegalReference) "
        f"WHERE {where_clause} "
        "AND n.resolution_status <> 'resolved' "
        "RETURN n.legal_reference_id AS legal_reference_id, "
        "n.source_legal_section_id AS source_legal_section_id, "
        "n.source_fragment_id AS source_fragment_id, "
        "n.raw_reference_text AS raw_reference_text, "
        "n.normalized_reference_text AS normalized_reference_text, "
        "n.target_law_code AS target_law_code, "
        "n.target_section_reference AS target_section_reference, "
        "n.unresolved_reason AS unresolved_reason, "
        "n.resolution_status AS resolution_status "
        "ORDER BY n.unresolved_reason, n.target_law_code, n.target_section_reference, n.source_legal_section_id, n.legal_reference_id",
        parameters,
    )
    return [dict(row) for row in rows]


def _workflow_section_record(row: dict[str, Any], *, role: str, depth: int) -> dict[str, Any]:
    return {
        "legal_section_id": str(row.get("legal_section_id") or ""),
        "legal_act_id": str(row.get("legal_act_id") or ""),
        "law_code": str(row.get("law_code") or ""),
        "section_reference": str(row.get("section_reference") or ""),
        "normalized_reference": str(row.get("normalized_reference") or ""),
        "title": str(row.get("title") or ""),
        "unit_status": str(row.get("unit_status") or "active"),
        "status_marker_text": str(row.get("status_marker_text") or ""),
        "source_document_id": str(row.get("source_document_id") or ""),
        "source_fragment_id": str(row.get("source_fragment_id") or ""),
        "source_version_id": str(row.get("source_version_id") or ""),
        "source_revision_marker": str(row.get("source_revision_marker") or ""),
        "build_date": str(row.get("build_date") or ""),
        "content_checksum": str(row.get("content_checksum") or ""),
        "role": role,
        "depth": depth,
    }


def _workflow_edge_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    index: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            str(row.get("source_legal_section_id") or ""),
            str(row.get("target_legal_section_id") or ""),
            str(row.get("relation_type") or ""),
        )
        index.setdefault(key, []).append(row)
    return index


def _workflow_edge_record(
    rows: list[dict[str, Any]],
    *,
    source_id: str,
    target_id: str,
    relation_type: str,
    depth: int,
    cycle_boundary: bool = False,
    truncated: bool = False,
) -> dict[str, Any]:
    legal_reference_ids = sorted({str(row.get("legal_reference_id") or "") for row in rows if row.get("legal_reference_id")})
    source_fragment_ids = sorted({str(row.get("source_fragment_id") or "") for row in rows if row.get("source_fragment_id")})
    first = rows[0] if rows else {}
    return {
        "source_legal_section_id": source_id,
        "target_legal_section_id": target_id,
        "relation_type": relation_type,
        "depth": depth,
        "legal_reference_ids": legal_reference_ids,
        "source_fragment_ids": source_fragment_ids,
        "target_law_code": str(first.get("target_law_code") or ""),
        "target_section_reference": str(first.get("target_section_reference") or ""),
        "target_unit_status": str(first.get("target_unit_status") or ""),
        "classifier_policy_version": str(first.get("classifier_policy_version") or ""),
        "effective_from": str(first.get("effective_from") or ""),
        "effective_until": str(first.get("effective_until") or ""),
        "publication_date": str(first.get("publication_date") or ""),
        "source_version_id": str(first.get("source_version_id") or ""),
        "source_revision_marker": str(first.get("source_revision_marker") or ""),
        "build_date": str(first.get("build_date") or ""),
        "temporal_evidence_status": str(first.get("temporal_evidence_status") or ""),
        "cycle_boundary": cycle_boundary,
        "truncated": truncated,
    }


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


def _collect_relationship_source(client: Any, *, law_codes: list[str]) -> dict[str, Any]:
    parameters = {"law_codes": law_codes}
    source_fragment_rows = client.read(
        "MATCH (sf:SourceFragment)-[:MAPS_TO]->(lf:LegalFragment)<-[:HAS_LEGAL_FRAGMENT]-(s:LegalSection) "
        "WHERE sf.law_code IN $law_codes "
        "RETURN sf.source_fragment_id AS source_fragment_id, "
        "sf.source_document_id AS source_document_id, "
        "sf.law_code AS law_code, "
        "sf.section_reference AS section_reference, "
        "sf.title AS title, "
        "sf.body_text AS body_text, "
        "sf.checksum AS checksum, "
        "sf.source_version_id AS source_version_id, "
        "sf.source_revision_marker AS source_revision_marker, "
        "sf.build_date AS build_date, "
        "sf.status_marker_text AS status_marker_text, "
        "s.legal_section_id AS source_legal_section_id, "
        "s.unit_status AS source_unit_status, "
        "s.status_marker_text AS source_status_marker_text, "
        "lf.legal_fragment_id AS source_legal_fragment_id "
        "ORDER BY law_code, section_reference, source_fragment_id",
        parameters,
    )
    legal_section_rows = client.read(
        "MATCH (s:LegalSection) "
        "WHERE s.law_code IN $law_codes "
        "RETURN s.legal_section_id AS legal_section_id, "
        "s.legal_act_id AS legal_act_id, "
        "s.law_code AS law_code, "
        "s.section_reference AS section_reference, "
        "s.normalized_reference AS normalized_reference, "
        "s.title AS title, "
        "s.valid_from AS valid_from, "
        "s.valid_to AS valid_to, "
        "s.version_identity AS version_identity, "
        "s.unit_status AS unit_status, "
        "s.status_marker_text AS status_marker_text, "
        "s.source_document_id AS source_document_id, "
        "s.source_fragment_id AS source_fragment_id, "
        "s.source_version_id AS source_version_id, "
        "s.source_revision_marker AS source_revision_marker, "
        "s.build_date AS build_date, "
        "s.content_checksum AS content_checksum "
        "ORDER BY law_code, normalized_reference, legal_section_id",
        parameters,
    )
    source_document_rows = client.read(
        "MATCH (d:SourceDocument) "
        "WHERE d.law_code IN $law_codes "
        "RETURN d.source_document_id AS source_document_id, "
        "d.source_family AS source_family, "
        "d.jurisdiction AS jurisdiction, "
        "d.language AS language, "
        "d.law_code AS law_code, "
        "d.source_uri AS source_uri, "
        "d.local_reference AS local_reference, "
        "d.publication_date AS publication_date, "
        "d.effective_date AS effective_date, "
        "d.retrieved_at AS retrieved_at, "
        "d.source_version_id AS source_version_id, "
        "d.source_revision_marker AS source_revision_marker, "
        "d.build_date AS build_date, "
        "d.checksum AS checksum "
        "ORDER BY source_document_id",
        parameters,
    )
    source_documents = {
        str(row.get("source_document_id", "")): dict(row)
        for row in source_document_rows
        if row.get("source_document_id")
    }
    return {
        "source_fragments": [dict(row) for row in source_fragment_rows],
        "legal_sections": [dict(row) for row in legal_section_rows],
        "source_documents": source_documents,
    }


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _count_records(records: list[dict[str, Any]], key: str, allowed_keys: tuple[str, ...]) -> dict[str, int]:
    counts = {allowed_key: 0 for allowed_key in allowed_keys}
    for record in records:
        value = str(record.get(key) or "")
        if value in counts:
            counts[value] += 1
    return counts


def _complete_counts(raw_counts: dict[str, int], allowed_keys: tuple[str, ...]) -> dict[str, int]:
    return {key: int(raw_counts.get(key, 0) or 0) for key in allowed_keys}


def _collect_classifier_policy_version(client: Any, law_codes: list[str]) -> str:
    rows = client.read(
        "MATCH (n:LegalReference) "
        "WHERE size($law_codes) = 0 OR n.law_code IN $law_codes "
        "RETURN collect(DISTINCT n.classifier_policy_version) AS versions",
        {"law_codes": law_codes},
    )
    versions = sorted(str(item) for item in (rows[0].get("versions", []) if rows else []) if item)
    return versions[0] if versions else CLASSIFIER_POLICY_VERSION


def _collect_reference_relation_counts(client: Any, *, law_codes: list[str]) -> dict[str, int]:
    rows = client.read(
        "MATCH (n:LegalReference) "
        "WHERE size($law_codes) = 0 OR n.law_code IN $law_codes "
        "RETURN coalesce(n.primary_relation_type, n.relation_type, 'CITES') AS relation_type, "
        "count(n) AS count "
        "ORDER BY relation_type",
        {"law_codes": law_codes},
    )
    counts = {str(row.get("relation_type") or ""): int(row.get("count", 0) or 0) for row in rows}
    return _complete_counts(counts, RELATION_TYPES)


def _collect_reference_status_counts(client: Any, *, law_codes: list[str]) -> dict[str, int]:
    rows = client.read(
        "MATCH (n:LegalReference) "
        "WHERE size($law_codes) = 0 OR n.law_code IN $law_codes "
        "RETURN coalesce(n.resolution_status, 'unresolved') AS resolution_status, "
        "count(n) AS count "
        "ORDER BY resolution_status",
        {"law_codes": law_codes},
    )
    counts = {str(row.get("resolution_status") or ""): int(row.get("count", 0) or 0) for row in rows}
    return _complete_counts(counts, RESOLUTION_STATUSES)


def _collect_source_unit_status_counts(client: Any, *, law_codes: list[str]) -> dict[str, int]:
    rows = client.read(
        "MATCH (s:LegalSection) "
        "WHERE size($law_codes) = 0 OR s.law_code IN $law_codes "
        "RETURN coalesce(s.unit_status, 'active') AS unit_status, "
        "count(s) AS count "
        "ORDER BY unit_status",
        {"law_codes": law_codes},
    )
    counts = {str(row.get("unit_status") or ""): int(row.get("count", 0) or 0) for row in rows}
    return _complete_counts(counts, UNIT_STATUSES)


def _collect_reference_target_status_counts(client: Any, *, law_codes: list[str]) -> dict[str, int]:
    rows = client.read(
        "MATCH (n:LegalReference) "
        "WHERE size($law_codes) = 0 OR n.law_code IN $law_codes "
        "WITH CASE "
        "WHEN coalesce(n.target_unit_status, '') <> '' THEN n.target_unit_status "
        "WHEN n.resolution_status = 'resolved' THEN 'active' "
        "ELSE '' END AS target_unit_status "
        "RETURN target_unit_status AS target_unit_status, count(*) AS count "
        "ORDER BY target_unit_status",
        {"law_codes": law_codes},
    )
    counts = {
        str(row.get("target_unit_status") or ""): int(row.get("count", 0) or 0)
        for row in rows
        if row.get("target_unit_status")
    }
    return _complete_counts(counts, TARGET_UNIT_STATUSES)


def _collect_reference_unresolved_reason_counts(client: Any, *, law_codes: list[str]) -> dict[str, int]:
    rows = client.read(
        "MATCH (n:LegalReference) "
        "WHERE (size($law_codes) = 0 OR n.law_code IN $law_codes) "
        "AND coalesce(n.unresolved_reason, '') <> '' "
        "RETURN n.unresolved_reason AS unresolved_reason, count(n) AS count "
        "ORDER BY unresolved_reason",
        {"law_codes": law_codes},
    )
    counts = {str(row.get("unresolved_reason") or ""): int(row.get("count", 0) or 0) for row in rows}
    return _complete_counts(counts, UNRESOLVED_REASONS)


def _collect_reference_ids(client: Any, *, law_codes: list[str], limit: int) -> list[str]:
    rows = client.read(
        "MATCH (n:LegalReference) "
        "WHERE size($law_codes) = 0 OR n.law_code IN $law_codes "
        "RETURN n.legal_reference_id AS id "
        "ORDER BY id LIMIT $limit",
        {"law_codes": law_codes, "limit": limit},
    )
    return [str(row.get("id")) for row in rows if row.get("id")]


def _collect_relationship_edge_ids(client: Any, *, law_codes: list[str], limit: int) -> list[str]:
    rows = client.read(
        "MATCH (s:LegalSection)-[r]->(t:LegalSection) "
        "WHERE type(r) IN $relation_types "
        "AND (size($law_codes) = 0 OR s.law_code IN $law_codes) "
        "RETURN r.legal_reference_id AS id "
        "ORDER BY id LIMIT $limit",
        {"law_codes": law_codes, "relation_types": list(RELATION_TYPES), "limit": limit},
    )
    return [str(row.get("id")) for row in rows if row.get("id")]


def _collect_reference_evidence(
    client: Any,
    *,
    law_codes: list[str],
    statuses: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    rows = client.read(
        "MATCH (n:LegalReference) "
        "WHERE (size($law_codes) = 0 OR n.law_code IN $law_codes) "
        "AND n.resolution_status IN $statuses "
        "RETURN n.legal_reference_id AS legal_reference_id, "
        "n.source_legal_section_id AS source_legal_section_id, "
        "n.source_legal_fragment_id AS source_legal_fragment_id, "
        "n.source_fragment_id AS source_fragment_id, "
        "n.law_code AS law_code, "
        "n.target_law_code AS target_law_code, "
        "n.target_section_reference AS target_section_reference, "
        "n.target_legal_section_id AS target_legal_section_id, "
        "n.target_unit_status AS target_unit_status, "
        "n.unresolved_reason AS unresolved_reason, "
        "n.primary_relation_type AS primary_relation_type, "
        "n.relation_type AS relation_type, "
        "n.resolution_status AS resolution_status, "
        "n.classifier_policy_version AS classifier_policy_version, "
        "n.raw_reference_text AS raw_reference_text, "
        "n.normalized_reference_text AS normalized_reference_text, "
        "n.context_checksum AS context_checksum, "
        "n.source_version_id AS source_version_id, "
        "n.source_revision_marker AS source_revision_marker, "
        "n.build_date AS build_date, "
        "n.temporal_evidence_status AS temporal_evidence_status, "
        "coalesce(n.subsection_anchor_json, '') AS subsection_anchor_json, "
        "coalesce(n.secondary_relation_signals_json, '') AS secondary_relation_signals_json, "
        "coalesce(n.unresolved_target_evidence_json, '') AS unresolved_target_evidence_json "
        "ORDER BY n.legal_reference_id LIMIT $limit",
        {"law_codes": law_codes, "statuses": statuses, "limit": limit},
    )
    evidence: list[dict[str, Any]] = []
    for row in rows:
        evidence.append(
            {
                "legal_reference_id": row.get("legal_reference_id", ""),
                "source_legal_section_id": row.get("source_legal_section_id", ""),
                "source_legal_fragment_id": row.get("source_legal_fragment_id", ""),
                "source_fragment_id": row.get("source_fragment_id", ""),
                "law_code": row.get("law_code", ""),
                "target_law_code": row.get("target_law_code", ""),
                "target_section_reference": row.get("target_section_reference", ""),
                "target_legal_section_id": row.get("target_legal_section_id", ""),
                "target_unit_status": row.get("target_unit_status", ""),
                "unresolved_reason": row.get("unresolved_reason", ""),
                "primary_relation_type": row.get("primary_relation_type") or row.get("relation_type", ""),
                "resolution_status": row.get("resolution_status", ""),
                "classifier_policy_version": row.get("classifier_policy_version", ""),
                "raw_reference_text": row.get("raw_reference_text", ""),
                "normalized_reference_text": row.get("normalized_reference_text", ""),
                "context_checksum": row.get("context_checksum", ""),
                "source_version_id": row.get("source_version_id", ""),
                "source_revision_marker": row.get("source_revision_marker", ""),
                "build_date": row.get("build_date", ""),
                "temporal_evidence_status": row.get("temporal_evidence_status", ""),
                "subsection_anchor": _json_property(row.get("subsection_anchor_json")),
                "secondary_relation_signals": _json_property(row.get("secondary_relation_signals_json"), []),
                "unresolved_target_evidence": _json_property(row.get("unresolved_target_evidence_json")),
            }
        )
    return evidence


def _collect_sample_edges_by_relation_type(
    client: Any,
    *,
    law_codes: list[str],
    limit: int,
) -> dict[str, list[dict[str, Any]]]:
    samples: dict[str, list[dict[str, Any]]] = {}
    for relation_type in RELATION_TYPES:
        rows = client.read(
            "MATCH (s:LegalSection)-[r]->(t:LegalSection) "
            "WHERE type(r) = $relation_type "
            "AND (size($law_codes) = 0 OR s.law_code IN $law_codes) "
            "RETURN s.legal_section_id AS source_legal_section_id, "
            "t.legal_section_id AS target_legal_section_id, "
            "r.legal_reference_id AS legal_reference_id, "
            "r.target_unit_status AS target_unit_status, "
            "r.classifier_policy_version AS classifier_policy_version, "
            "r.temporal_evidence_status AS temporal_evidence_status "
            "ORDER BY legal_reference_id LIMIT $limit",
            {"law_codes": law_codes, "relation_type": relation_type, "limit": limit},
        )
        samples[relation_type] = [
            {
                "relation_type": relation_type,
                "source_legal_section_id": row.get("source_legal_section_id", ""),
                "target_legal_section_id": row.get("target_legal_section_id", ""),
                "legal_reference_id": row.get("legal_reference_id", ""),
                "target_unit_status": row.get("target_unit_status", ""),
                "classifier_policy_version": row.get("classifier_policy_version", ""),
                "temporal_evidence_status": row.get("temporal_evidence_status", ""),
            }
            for row in rows
        ]
    return samples


def _collect_top_unresolved_targets(client: Any, *, law_codes: list[str], limit: int) -> list[dict[str, Any]]:
    rows = client.read(
        "MATCH (n:LegalReference) "
        "WHERE (size($law_codes) = 0 OR n.law_code IN $law_codes) "
        "AND n.resolution_status <> 'resolved' "
        "RETURN n.target_law_code AS target_law_code, "
        "n.target_section_reference AS target_section_reference, "
        "n.unresolved_reason AS unresolved_reason, "
        "n.resolution_status AS resolution_status, "
        "count(n) AS count "
        "ORDER BY count DESC, target_law_code, target_section_reference, resolution_status, unresolved_reason "
        "LIMIT $limit",
        {"law_codes": law_codes, "limit": limit},
    )
    return [
        {
            "target_law_code": row.get("target_law_code", ""),
            "target_section_reference": row.get("target_section_reference", ""),
            "resolution_status": row.get("resolution_status", ""),
            "unresolved_reason": row.get("unresolved_reason", ""),
            "count": int(row.get("count", 0) or 0),
        }
        for row in rows
    ]


def _collect_top_missing_targets(client: Any, *, law_codes: list[str], limit: int) -> list[dict[str, Any]]:
    rows = client.read(
        "MATCH (n:LegalReference) "
        "WHERE (size($law_codes) = 0 OR n.law_code IN $law_codes) "
        "AND n.unresolved_reason = 'missing_target_in_corpus' "
        "AND coalesce(n.target_law_code, '') <> '' "
        "AND coalesce(n.target_section_reference, '') <> '' "
        "WITH n ORDER BY n.legal_reference_id "
        "WITH n.target_law_code AS target_law_code, "
        "n.target_section_reference AS target_section_reference, "
        "count(n) AS count, "
        "collect({legal_reference_id: n.legal_reference_id, "
        "source_legal_section_id: n.source_legal_section_id, "
        "source_fragment_id: n.source_fragment_id, "
        "raw_reference_text: n.raw_reference_text})[0..5] AS source_samples "
        "RETURN target_law_code AS target_law_code, "
        "target_section_reference AS target_section_reference, "
        "'missing_target_in_corpus' AS reason, "
        "count AS count, "
        "source_samples AS source_samples "
        "ORDER BY count DESC, target_law_code, target_section_reference "
        "LIMIT $limit",
        {"law_codes": law_codes, "limit": limit},
    )
    return [
        {
            "target_law_code": row.get("target_law_code", ""),
            "target_section_reference": row.get("target_section_reference", ""),
            "reason": "missing_target_in_corpus",
            "count": int(row.get("count", 0) or 0),
            "source_samples": [
                {
                    "legal_reference_id": sample.get("legal_reference_id", ""),
                    "source_legal_section_id": sample.get("source_legal_section_id", ""),
                    "source_fragment_id": sample.get("source_fragment_id", ""),
                    "raw_reference_text": sample.get("raw_reference_text", ""),
                }
                for sample in row.get("source_samples", [])
                if isinstance(sample, dict)
            ],
        }
        for row in rows
    ]


def _collect_source_to_relation_coverage(client: Any, *, law_codes: list[str]) -> dict[str, Any]:
    source_rows = client.read(
        "MATCH (sf:SourceFragment) "
        "WHERE size($law_codes) = 0 OR sf.law_code IN $law_codes "
        "RETURN sf.law_code AS law_code, count(sf) AS source_fragment_count "
        "ORDER BY law_code",
        {"law_codes": law_codes},
    )
    relation_rows = client.read(
        "MATCH (n:LegalReference) "
        "WHERE size($law_codes) = 0 OR n.law_code IN $law_codes "
        "RETURN n.law_code AS law_code, "
        "coalesce(n.primary_relation_type, n.relation_type, 'CITES') AS relation_type, "
        "count(n) AS count "
        "ORDER BY law_code, relation_type",
        {"law_codes": law_codes},
    )
    coverage: dict[str, Any] = {
        "selected_law_codes": sorted(law_codes),
        "by_law_code": {},
    }
    for row in source_rows:
        law_code = str(row.get("law_code", ""))
        coverage["by_law_code"][law_code] = {
            "source_fragment_count": int(row.get("source_fragment_count", 0) or 0),
            "reference_count": 0,
            "counts_by_relation_type": _complete_counts({}, RELATION_TYPES),
        }
    for row in relation_rows:
        law_code = str(row.get("law_code", ""))
        relation_type = str(row.get("relation_type") or "")
        count = int(row.get("count", 0) or 0)
        law_coverage = coverage["by_law_code"].setdefault(
            law_code,
            {
                "source_fragment_count": 0,
                "reference_count": 0,
                "counts_by_relation_type": _complete_counts({}, RELATION_TYPES),
            },
        )
        if relation_type in RELATION_TYPES:
            law_coverage["counts_by_relation_type"][relation_type] += count
            law_coverage["reference_count"] += count
    return coverage


def _collect_relationship_fanout_summary(client: Any, *, law_codes: list[str], limit: int) -> dict[str, Any]:
    rows = client.read(
        "MATCH (s:LegalSection)-[r]->(:LegalSection) "
        "WHERE type(r) IN $relation_types "
        "AND (size($law_codes) = 0 OR s.law_code IN $law_codes) "
        "WITH s.legal_section_id AS legal_section_id, count(r) AS fanout "
        "RETURN count(legal_section_id) AS source_section_count, "
        "coalesce(max(fanout), 0) AS max_fanout, "
        "coalesce(avg(fanout), 0.0) AS avg_fanout, "
        "collect({legal_section_id: legal_section_id, fanout: fanout})[0..$limit] AS top_fanout_sections",
        {"law_codes": law_codes, "relation_types": list(RELATION_TYPES), "limit": limit},
    )
    row = rows[0] if rows else {}
    return {
        "source_section_count": int(row.get("source_section_count", 0) or 0),
        "max_fanout": int(row.get("max_fanout", 0) or 0),
        "avg_fanout": float(row.get("avg_fanout", 0.0) or 0.0),
        "top_fanout_sections": [
            {"legal_section_id": str(item.get("legal_section_id", "")), "fanout": int(item.get("fanout", 0) or 0)}
            for item in row.get("top_fanout_sections", [])
            if isinstance(item, dict)
        ],
    }


def _collect_temporal_metadata_completeness(
    client: Any,
    *,
    law_codes: list[str],
    selected_scope: dict[str, Any],
) -> dict[str, Any]:
    fields = (
        "effective_from",
        "effective_until",
        "publication_date",
        "source_version_id",
        "source_revision_marker",
        "temporal_context_text",
        "temporal_context_checksum",
    )
    rows = client.read(
        "MATCH (n:LegalReference) "
        "WHERE size($law_codes) = 0 OR n.law_code IN $law_codes "
        "RETURN coalesce(n.primary_relation_type, n.relation_type, 'CITES') AS relation_type, "
        "coalesce(n.temporal_evidence_status, 'not_applicable') AS temporal_evidence_status, "
        "n.effective_from AS effective_from, "
        "n.effective_until AS effective_until, "
        "n.publication_date AS publication_date, "
        "n.source_version_id AS source_version_id, "
        "n.source_revision_marker AS source_revision_marker, "
        "n.temporal_context_text AS temporal_context_text, "
        "n.temporal_context_checksum AS temporal_context_checksum "
        "ORDER BY relation_type",
        {"law_codes": law_codes},
    )
    counts_by_status = _complete_counts({}, TEMPORAL_EVIDENCE_STATUSES)
    counts_by_relation_type = {
        relation_type: {"total": 0, "with_any_temporal_metadata": 0, "missing_required_temporal_fields": 0}
        for relation_type in RELATION_TYPES
    }
    missing_field_summary = {field: 0 for field in fields}
    for row in rows:
        relation_type = str(row.get("relation_type") or "CITES")
        if relation_type not in counts_by_relation_type:
            continue
        status = str(row.get("temporal_evidence_status") or "not_applicable")
        if status not in counts_by_status:
            status = "not_applicable"
        counts_by_status[status] += 1
        relation_counts = counts_by_relation_type[relation_type]
        relation_counts["total"] += 1
        missing_fields = [field for field in fields if not row.get(field)]
        if len(missing_fields) < len(fields):
            relation_counts["with_any_temporal_metadata"] += 1
        relation_counts["missing_required_temporal_fields"] += len(missing_fields)
        for field in missing_fields:
            missing_field_summary[field] += 1
    return {
        "selected_scope": selected_scope,
        "counts_by_temporal_evidence_status": counts_by_status,
        "counts_by_relation_type": counts_by_relation_type,
        "missing_field_summary": missing_field_summary,
        "total_reference_evidence_count": len(rows),
    }


def _collect_corpus_readiness_components(client: Any, *, law_codes: list[str]) -> dict[str, Any]:
    rows = client.read(
        "MATCH (s:LegalSection) "
        "WHERE size($law_codes) = 0 OR s.law_code IN $law_codes "
        "OPTIONAL MATCH (s)-[:HAS_LEGAL_FRAGMENT]->(lf:LegalFragment) "
        "OPTIONAL MATCH (sf:SourceFragment)-[:MAPS_TO]->(lf) "
        "OPTIONAL MATCH (s)-[:HAS_REFERENCE]->(ref:LegalReference) "
        "WITH s, "
        "collect(DISTINCT lf.text) AS legal_fragment_texts, "
        "collect(DISTINCT sf.body_text) AS source_fragment_texts, "
        "count(DISTINCT CASE WHEN coalesce(ref.primary_relation_type, ref.relation_type, '') = 'DEFINES' "
        "THEN ref.legal_reference_id END) AS defines_evidence_count "
        "RETURN s.legal_section_id AS legal_section_id, "
        "s.law_code AS law_code, "
        "s.section_reference AS section_reference, "
        "s.title AS title, "
        "coalesce(s.unit_status, 'active') AS unit_status, "
        "s.status_marker_text AS status_marker_text, "
        "s.source_document_id AS source_document_id, "
        "s.source_fragment_id AS source_fragment_id, "
        "s.source_version_id AS source_version_id, "
        "s.source_revision_marker AS source_revision_marker, "
        "s.build_date AS build_date, "
        "s.content_checksum AS content_checksum, "
        "legal_fragment_texts AS legal_fragment_texts, "
        "source_fragment_texts AS source_fragment_texts, "
        "defines_evidence_count AS defines_evidence_count "
        "ORDER BY law_code, section_reference, legal_section_id",
        {"law_codes": law_codes},
    )
    unit_records = [_classify_corpus_readiness_row(dict(row)) for row in rows]
    counts_by_unit_status = _complete_counts({}, UNIT_STATUSES)
    counts_by_structure_class = _complete_counts({}, STRUCTURE_CLASSES)
    for record in unit_records:
        status = record["unit_status"]
        structure_class = record["structure_class"]
        if status in counts_by_unit_status:
            counts_by_unit_status[status] += 1
        if structure_class in counts_by_structure_class:
            counts_by_structure_class[structure_class] += 1
    active_samples = [
        _readiness_sample(record)
        for record in unit_records
        if record["unit_status"] == "active"
    ][:10]
    inactive_samples = [
        _readiness_sample(record)
        for record in unit_records
        if record["unit_status"] == "inactive"
    ][:10]
    complexity_summary = _readiness_complexity_summary(unit_records)
    return {
        "counts_by_unit_status": counts_by_unit_status,
        "counts_by_structure_class": counts_by_structure_class,
        "active_unit_samples": active_samples,
        "inactive_unit_samples": inactive_samples,
        "complexity_summary": complexity_summary,
        "excluded_semantic_candidates": {
            "LegalNorm": 0,
            "Condition": 0,
            "LegalEffect": 0,
            "Exception": 0,
        },
    }


def _classify_corpus_readiness_row(row: dict[str, Any]) -> dict[str, Any]:
    title = str(row.get("title") or "")
    body_text = _readiness_body_text(row)
    unit_status = str(row.get("unit_status") or "active")
    if unit_status not in UNIT_STATUSES:
        unit_status = "active"
    paragraph_count = _paragraph_count(body_text)
    body_text_length = len(body_text)
    definition_marker_count = _definition_marker_count(" ".join([title, body_text]))
    defines_evidence_count = int(row.get("defines_evidence_count", 0) or 0)
    list_marker_count = _list_marker_count(body_text)
    inactive_signal = unit_status != "active"
    definition_signal = definition_marker_count > 0 or defines_evidence_count >= 2
    list_signal = list_marker_count >= 3
    long_or_multi_paragraph_signal = paragraph_count >= 2 or body_text_length > 1200
    matched_signals = sum([definition_signal, list_signal, long_or_multi_paragraph_signal])
    if inactive_signal:
        structure_class = "inactive_skipped"
    elif matched_signals >= 2:
        structure_class = "mixed_content"
    elif definition_signal:
        structure_class = "definition_heavy"
    elif list_signal:
        structure_class = "list_heavy"
    elif body_text_length <= 1200 and paragraph_count <= 1:
        structure_class = "simple_paragraph"
    else:
        structure_class = "unknown"
    return {
        "legal_section_id": str(row.get("legal_section_id") or ""),
        "law_code": str(row.get("law_code") or ""),
        "section_reference": str(row.get("section_reference") or ""),
        "title": title,
        "unit_status": unit_status,
        "status_marker_text": str(row.get("status_marker_text") or ""),
        "source_document_id": str(row.get("source_document_id") or ""),
        "source_fragment_id": str(row.get("source_fragment_id") or ""),
        "source_version_id": str(row.get("source_version_id") or ""),
        "source_revision_marker": str(row.get("source_revision_marker") or ""),
        "build_date": str(row.get("build_date") or ""),
        "content_checksum": str(row.get("content_checksum") or ""),
        "structure_class": structure_class,
        "signals": {
            "inactive_signal": inactive_signal,
            "definition_signal": definition_signal,
            "list_signal": list_signal,
            "long_or_multi_paragraph_signal": long_or_multi_paragraph_signal,
            "body_text_length": body_text_length,
            "paragraph_count": paragraph_count,
            "list_marker_count": list_marker_count,
            "definition_marker_count": definition_marker_count,
            "defines_evidence_count": defines_evidence_count,
        },
    }


def _readiness_body_text(row: dict[str, Any]) -> str:
    source_texts = sorted(str(item) for item in row.get("source_fragment_texts", []) if item)
    legal_texts = sorted(str(item) for item in row.get("legal_fragment_texts", []) if item)
    return "\n\n".join(source_texts or legal_texts)


DEFINITION_MARKER_PATTERN = re.compile(
    r"\b(begriffsbestimmung|definition|im\s+sinne|bedeutet|bezeichnet)\b",
    re.IGNORECASE,
)
LIST_MARKER_PATTERN = re.compile(
    r"(?:^|[\n;:])\s*(?:\d+\.|\(\d+\)|[a-z]\)|\([a-z]\)|[a-z]{2}\))\s+",
    re.IGNORECASE,
)


def _paragraph_count(body_text: str) -> int:
    if not body_text.strip():
        return 0
    return len([part for part in re.split(r"\n\s*\n+", body_text.strip()) if part.strip()])


def _definition_marker_count(text: str) -> int:
    return len(DEFINITION_MARKER_PATTERN.findall(text))


def _list_marker_count(body_text: str) -> int:
    return len(LIST_MARKER_PATTERN.findall(body_text))


def _readiness_sample(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "legal_section_id": record["legal_section_id"],
        "law_code": record["law_code"],
        "section_reference": record["section_reference"],
        "title": record["title"],
        "unit_status": record["unit_status"],
        "status_marker_text": record["status_marker_text"],
        "source_document_id": record["source_document_id"],
        "source_fragment_id": record["source_fragment_id"],
        "structure_class": record["structure_class"],
        "signals": record["signals"],
    }


def _readiness_complexity_summary(unit_records: list[dict[str, Any]]) -> dict[str, Any]:
    signal_counts = {
        "inactive_signal": 0,
        "definition_signal": 0,
        "list_signal": 0,
        "long_or_multi_paragraph_signal": 0,
    }
    totals = {
        "body_text_length": 0,
        "paragraph_count": 0,
        "list_marker_count": 0,
        "definition_marker_count": 0,
        "defines_evidence_count": 0,
    }
    maximums = dict.fromkeys(totals, 0)
    unit_signals = []
    for record in unit_records:
        signals = record["signals"]
        for key in signal_counts:
            signal_counts[key] += 1 if signals[key] else 0
        for key in totals:
            value = int(signals[key])
            totals[key] += value
            maximums[key] = max(int(maximums[key]), value)
        unit_signals.append(
            {
                "legal_section_id": record["legal_section_id"],
                "structure_class": record["structure_class"],
                **signals,
            }
        )
    return {
        "structure_class_rules_version": STRUCTURE_CLASS_RULES_VERSION,
        "total_unit_count": len(unit_records),
        "signal_counts": signal_counts,
        "signal_totals": totals,
        "signal_maximums": maximums,
        "unit_signals": sorted(unit_signals, key=lambda item: item["legal_section_id"]),
    }


def _json_property(value: Any, default: Any | None = None) -> Any:
    if default is None:
        default = {}
    if not value:
        return default
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return {"raw": value}


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
        "n.unresolved_reason AS unresolved_reason, "
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
                "unresolved_reason": row.get("unresolved_reason", ""),
                "raw_reference_text": row.get("raw_reference_text", ""),
                "normalized_reference_text": row.get("normalized_reference_text", ""),
                "unresolved_target_evidence": unresolved_target_evidence,
            }
        )
    return evidence
