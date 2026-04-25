"""Graph schema bootstrap helpers."""

from __future__ import annotations

from .neo4j_client import Neo4jClient


CONSTRAINT_QUERIES = [
    "CREATE CONSTRAINT embedding_profile_id IF NOT EXISTS FOR (n:EmbeddingProfile) REQUIRE n.profile_id IS UNIQUE",
    "CREATE CONSTRAINT knowledge_source_id IF NOT EXISTS FOR (n:KnowledgeSource) REQUIRE n.source_id IS UNIQUE",
    "CREATE CONSTRAINT legal_norm_id IF NOT EXISTS FOR (n:LegalNorm) REQUIRE n.norm_id IS UNIQUE",
    "CREATE CONSTRAINT procedure_id IF NOT EXISTS FOR (n:Procedure) REQUIRE n.procedure_id IS UNIQUE",
    "CREATE CONSTRAINT requirement_id IF NOT EXISTS FOR (n:Requirement) REQUIRE n.requirement_id IS UNIQUE",
    "CREATE CONSTRAINT benefit_id IF NOT EXISTS FOR (n:Benefit) REQUIRE n.benefit_id IS UNIQUE",
    "CREATE CONSTRAINT authority_id IF NOT EXISTS FOR (n:Authority) REQUIRE n.authority_id IS UNIQUE",
    "CREATE CONSTRAINT user_query_id IF NOT EXISTS FOR (n:UserQuery) REQUIRE n.query_id IS UNIQUE",
    "CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (n:ObservationClaim) REQUIRE n.claim_id IS UNIQUE",
    "CREATE CONSTRAINT source_document_id IF NOT EXISTS FOR (n:SourceDocument) REQUIRE n.source_id IS UNIQUE",
    "CREATE CONSTRAINT source_fragment_id IF NOT EXISTS FOR (n:SourceFragment) REQUIRE n.fragment_id IS UNIQUE",
    "CREATE CONSTRAINT candidate_entity_id IF NOT EXISTS FOR (n:CandidateEntity) REQUIRE n.candidate_entity_id IS UNIQUE",
    "CREATE CONSTRAINT candidate_claim_id IF NOT EXISTS FOR (n:CandidateClaim) REQUIRE n.candidate_claim_id IS UNIQUE",
    "CREATE CONSTRAINT enrichment_run_id IF NOT EXISTS FOR (n:EnrichmentRun) REQUIRE n.run_id IS UNIQUE",
    "CREATE CONSTRAINT validation_question_set_id IF NOT EXISTS FOR (n:ValidationQuestionSet) REQUIRE n.question_set_id IS UNIQUE",
    "CREATE CONSTRAINT validation_question_id IF NOT EXISTS FOR (n:ValidationQuestion) REQUIRE n.question_id IS UNIQUE",
    "CREATE CONSTRAINT validation_run_result_id IF NOT EXISTS FOR (n:ValidationRunResult) REQUIRE n.validation_result_id IS UNIQUE",
    "CREATE CONSTRAINT legal_act_law_code IF NOT EXISTS FOR (n:LegalAct) REQUIRE n.law_code IS UNIQUE",
    "CREATE CONSTRAINT legal_section_id IF NOT EXISTS FOR (n:LegalSection) REQUIRE n.section_id IS UNIQUE",
    "CREATE CONSTRAINT legal_fragment_id IF NOT EXISTS FOR (n:LegalFragment) REQUIRE n.fragment_id IS UNIQUE",
    "CREATE CONSTRAINT legal_reference_id IF NOT EXISTS FOR (n:LegalReference) REQUIRE n.reference_id IS UNIQUE",
    "CREATE CONSTRAINT proposition_candidate_id IF NOT EXISTS FOR (n:PropositionCandidate) REQUIRE n.proposition_candidate_id IS UNIQUE",
    "CREATE CONSTRAINT proposition_support_id IF NOT EXISTS FOR (n:PropositionSupport) REQUIRE n.support_id IS UNIQUE",
    "CREATE CONSTRAINT extraction_run_id IF NOT EXISTS FOR (n:ExtractionRun) REQUIRE n.run_id IS UNIQUE",
    "CREATE CONSTRAINT validation_case_set_id IF NOT EXISTS FOR (n:ValidationCaseSet) REQUIRE n.validation_set_id IS UNIQUE",
    "CREATE CONSTRAINT validation_case_id IF NOT EXISTS FOR (n:ValidationCase) REQUIRE n.case_id IS UNIQUE",
    "CREATE CONSTRAINT validation_result_id IF NOT EXISTS FOR (n:ValidationResult) REQUIRE n.validation_result_id IS UNIQUE",
]

VECTOR_INDEX_SPECS = [
    ("legal_fragment_embedding", "LegalFragment"),
    ("source_document_embedding", "SourceDocument"),
    ("source_fragment_embedding", "SourceFragment"),
    ("knowledge_source_embedding", "KnowledgeSource"),
    ("legal_norm_embedding", "LegalNorm"),
    ("procedure_embedding", "Procedure"),
    ("requirement_embedding", "Requirement"),
    ("benefit_embedding", "Benefit"),
    ("authority_embedding", "Authority"),
    ("observation_claim_embedding", "ObservationClaim"),
    ("user_query_embedding", "UserQuery"),
]


def build_schema_queries(embedding_dimensions: int = 1024) -> list[str]:
    queries = list(CONSTRAINT_QUERIES)
    for index_name, label in VECTOR_INDEX_SPECS:
        queries.append(
            "CREATE VECTOR INDEX "
            f"{index_name} IF NOT EXISTS FOR (n:{label}) ON (n.embedding_v1) "
            "OPTIONS {indexConfig: {"
            f"`vector.dimensions`: {embedding_dimensions}, "
            "`vector.similarity_function`: 'cosine'"
            "}}"
        )
    return queries


def bootstrap_schema(client: Neo4jClient, embedding_dimensions: int = 1024) -> int:
    for query in build_schema_queries(embedding_dimensions):
        client.execute(query)
    return len(build_schema_queries(embedding_dimensions))
