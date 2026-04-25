"""Repository layer for graph-backed entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .neo4j_client import Neo4jClient


@dataclass(slots=True)
class GraphRepository:
    client: Neo4jClient
    label: str
    key_field: str

    def upsert(self, payload: dict[str, Any]) -> dict[str, Any]:
        key = payload[self.key_field]
        query = f"MERGE (n:{self.label} {{{self.key_field}: $key}}) SET n += $payload RETURN n"
        self.client.execute(query, key=key, payload=payload)
        return payload


def build_core_repositories(client: Neo4jClient) -> dict[str, GraphRepository]:
    return {
        "knowledge_source": GraphRepository(client, "KnowledgeSource", "source_id"),
        "legal_norm": GraphRepository(client, "LegalNorm", "norm_id"),
        "procedure": GraphRepository(client, "Procedure", "procedure_id"),
        "requirement": GraphRepository(client, "Requirement", "requirement_id"),
        "benefit": GraphRepository(client, "Benefit", "benefit_id"),
        "authority": GraphRepository(client, "Authority", "authority_id"),
        "user_query": GraphRepository(client, "UserQuery", "query_id"),
        "observation_claim": GraphRepository(client, "ObservationClaim", "claim_id"),
    }


def build_bulk_enrichment_repositories(client: Neo4jClient) -> dict[str, GraphRepository]:
    return {
        "source_document": GraphRepository(client, "SourceDocument", "source_id"),
        "source_fragment": GraphRepository(client, "SourceFragment", "fragment_id"),
        "candidate_entity": GraphRepository(client, "CandidateEntity", "candidate_entity_id"),
        "candidate_claim": GraphRepository(client, "CandidateClaim", "candidate_claim_id"),
        "enrichment_run": GraphRepository(client, "EnrichmentRun", "run_id"),
        "validation_question_set": GraphRepository(
            client, "ValidationQuestionSet", "question_set_id"
        ),
        "validation_question": GraphRepository(client, "ValidationQuestion", "question_id"),
        "validation_run_result": GraphRepository(
            client, "ValidationRunResult", "validation_result_id"
        ),
    }


def build_legal_extraction_repositories(client: Neo4jClient) -> dict[str, GraphRepository]:
    return {
        "legal_act": GraphRepository(client, "LegalAct", "law_code"),
        "legal_section": GraphRepository(client, "LegalSection", "section_id"),
        "legal_fragment": GraphRepository(client, "LegalFragment", "fragment_id"),
        "legal_reference": GraphRepository(client, "LegalReference", "reference_id"),
        "proposition_candidate": GraphRepository(
            client, "PropositionCandidate", "proposition_candidate_id"
        ),
        "proposition_support": GraphRepository(client, "PropositionSupport", "support_id"),
        "extraction_run": GraphRepository(client, "ExtractionRun", "run_id"),
        "validation_case_set": GraphRepository(client, "ValidationCaseSet", "validation_set_id"),
        "validation_case": GraphRepository(client, "ValidationCase", "case_id"),
        "validation_result": GraphRepository(client, "ValidationResult", "validation_result_id"),
    }
