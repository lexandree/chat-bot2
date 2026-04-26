"""Neo4j schema definition assembly and bootstrap execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from review.schema_boundary import CandidateReviewSchemaBoundary


@dataclass(frozen=True, slots=True)
class SchemaStatement:
    name: str
    cypher: str
    category: str


SOURCE_CONSTRAINTS = [
    ("source_document_id_unique", "SourceDocument", "source_document_id"),
    ("source_fragment_id_unique", "SourceFragment", "source_fragment_id"),
]
LEGAL_CONSTRAINTS = [
    ("legal_act_id_unique", "LegalAct", "legal_act_id"),
    ("legal_section_id_unique", "LegalSection", "legal_section_id"),
    ("legal_fragment_id_unique", "LegalFragment", "legal_fragment_id"),
    ("legal_reference_id_unique", "LegalReference", "legal_reference_id"),
]
RUN_CONSTRAINTS = [
    ("embedding_profile_id_unique", "EmbeddingProfile", "embedding_profile_id"),
    ("load_run_id_unique", "LoadRun", "load_run_id"),
    ("embedding_run_id_unique", "EmbeddingRun", "embedding_run_id"),
    ("validation_result_id_unique", "ValidationResult", "validation_result_id"),
]
PLACEHOLDER_CONSTRAINTS = [
    ("candidate_id_unique", "Candidate", "candidate_id"),
    ("candidate_support_id_unique", "CandidateSupport", "support_reference_id"),
]
VECTOR_INDEX_TARGETS = [
    ("source_document_embedding_v1", "SourceDocument"),
    ("source_fragment_embedding_v1", "SourceFragment"),
    ("legal_fragment_embedding_v1", "LegalFragment"),
]


def _constraint_statement(name: str, label: str, property_name: str) -> SchemaStatement:
    return SchemaStatement(
        name=name,
        category="constraint",
        cypher=(
            f"CREATE CONSTRAINT {name} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{property_name} IS UNIQUE"
        ),
    )


def _vector_statement(name: str, label: str, dimensions: int) -> SchemaStatement:
    if dimensions <= 0:
        raise ValueError("embedding vector dimensions must be positive")
    return SchemaStatement(
        name=name,
        category="vector_index",
        cypher=(
            f"CREATE VECTOR INDEX {name} IF NOT EXISTS "
            f"FOR (n:{label}) ON (n.embedding_v1) "
            "OPTIONS {indexConfig: {"
            f"`vector.dimensions`: {dimensions}, "
            "`vector.similarity_function`: 'cosine'"
            "}}"
        ),
    )


def build_schema_statements(embedding_dimensions: int = 1024) -> list[SchemaStatement]:
    statements: list[SchemaStatement] = []
    for name, label, property_name in [
        *SOURCE_CONSTRAINTS,
        *LEGAL_CONSTRAINTS,
        *RUN_CONSTRAINTS,
        *PLACEHOLDER_CONSTRAINTS,
    ]:
        statements.append(_constraint_statement(name, label, property_name))
    for name, label in VECTOR_INDEX_TARGETS:
        statements.append(_vector_statement(name, label, embedding_dimensions))
    return statements


def schema_object_names(embedding_dimensions: int = 1024) -> list[str]:
    return [statement.name for statement in build_schema_statements(embedding_dimensions)]


def candidate_review_placeholders_present(statements: Iterable[SchemaStatement]) -> bool:
    names = {statement.name for statement in statements}
    return set(CandidateReviewSchemaBoundary().constraint_names()).issubset(names)


def bootstrap_schema(client, embedding_dimensions: int = 1024) -> list[str]:
    statements = build_schema_statements(embedding_dimensions)
    for statement in statements:
        client.write(statement.cypher, {})
    return [statement.name for statement in statements]
