# Data Model: German Legal Graph Foundation

## Configuration Profile

Effective runtime settings for an operator run.

**Fields**:
- `neo4j_uri`, `neo4j_username`, `neo4j_password`, `neo4j_database`
- `embedding_profile_id`, `embedding_model_id`, `embedding_provider`
- `embedding_vector_dimensions`, default `1024`
- `embedding_normalized`, default `true`
- `embedding_variant`, default `Q8`
- `embedding_query_prefix`, fixed `Query: `
- `embedding_document_prefix`, fixed `Document: `
- `embedding_routing_mode`, graph writes fixed `local_only`
- `embedding_endpoint_url`, default `http://127.0.0.1:18080/v1/embeddings`
- `run_live_neo4j_tests`, `run_live_embedding_tests`
- `default_temporal_mode`, default `current_default`

**Validation rules**:
- Required Neo4j fields must be present for live graph operations.
- Embedding dimensions must be positive and match the active profile.
- Graph-write routing mode must be `local_only`.
- Default unit tests must not require live Neo4j or Jina.

## Graph Readiness Report

Operator-facing result of settings, connectivity, and schema bootstrap.

**Fields**:
- `status`: `ready` or `failed`
- `database_name`
- `schema_objects`: stable constraint/index names
- `vector_dimensions`
- `candidate_review_placeholders_present`
- `connectivity_checked`
- `warnings`
- `errors`

## Source Document

Normalized source-level legal input.

**Fields**:
- `source_document_id`
- `source_family`: `law` or `official_guidance`
- `jurisdiction`
- `language`
- `law_code`
- `source_uri` or `local_reference`
- `publication_date`, `effective_date`, `retrieved_at`, `freshness_metadata`
- `checksum`

**Relationships**:
- Has many `SourceFragment`.
- Supports one or more structural legal objects.

**Validation rules**:
- `source_document_id` and `checksum` are stable for unchanged source content.
- Missing optional inputs are reported in preview rather than represented as
  failed source documents.

## Source Fragment

Text fragment derived from a source document.

**Fields**:
- `source_fragment_id`
- `source_document_id`
- `law_code`
- `section_reference`
- `title`
- `body_text`
- `order_index`
- `checksum`

**Relationships**:
- Belongs to one `SourceDocument`.
- May map to one `LegalFragment`.
- May receive one `embedding_v1` vector.

## Legal Act

Canonical graph identity for a law or official legal source family.

**Fields**:
- `legal_act_id`
- `law_code`
- `title`
- `source_family`
- `jurisdiction`
- `language`
- `valid_from`, `valid_to`
- `is_current`

**Relationships**:
- Has many `LegalSection`.

## Legal Section

Canonical structural legal unit.

**Fields**:
- `legal_section_id`
- `legal_act_id`
- `law_code`
- `section_reference`
- `title`
- `normalized_reference`
- `valid_from`, `valid_to`
- `version_identity`
- `is_current`

**Relationships**:
- Belongs to one `LegalAct`.
- Has one or more `LegalFragment`.
- Has outgoing/incoming typed legal references.

**Validation rules**:
- The tuple `law_code + normalized_reference + version_identity/current flag`
  must identify a section version.
- Current-default resolution must select current sections when available.

## Legal Fragment

Structural text unit attached to a legal section.

**Fields**:
- `legal_fragment_id`
- `legal_section_id`
- `source_fragment_id`
- `text`
- `order_index`
- `checksum`

**Relationships**:
- Belongs to one `LegalSection`.
- Links back to one `SourceFragment`.
- May receive one `embedding_v1` vector.

## Legal Reference

Parsed legal reference between legal units.

**Fields**:
- `legal_reference_id`
- `source_legal_section_id` or `source_legal_fragment_id`
- `target_law_code`
- `target_section_reference`
- `target_legal_section_id` when resolved
- `relation_type`: `CITES`, `DEFINES`, `APPLIES_IF`, `REQUIRES`,
  `EXCEPTION_TO`, `EXCLUDES_IF`, `AMENDS`, `SUPERSEDED_BY`
- `resolution_status`: `resolved`, `unresolved`, `ambiguous`
- `unresolved_target_evidence`

**State transitions**:
- `unresolved` -> `resolved` when target section becomes available.
- `resolved` -> `ambiguous` only when multiple current targets match.

## Embedding Profile

Immutable contract for graph-written embeddings.

**Fields**:
- `embedding_profile_id`
- `provider`
- `model_id`
- `variant`
- `dimensions`
- `normalized`
- `query_prefix`
- `document_prefix`
- `query_task`
- `document_task`
- `routing_mode`
- `vector_field`, fixed `embedding_v1`

**Validation rules**:
- Document embeddings must use `Document: ` prefix.
- Query embeddings must use `Query: ` prefix.
- Vectors must match configured dimensions and normalization status.

## Embedding Run

Operator run that writes embeddings for a selected scope.

**Fields**:
- `embedding_run_id`
- `selected_scope`
- `embedding_profile_id`
- `backend_name`
- `model_id`
- `routing_mode`
- `processed_count`
- `skipped_count`
- `failed_count`
- `started_at`, `finished_at`
- `failure_reason`

**State transitions**:
- `pending` -> `running` -> `completed`
- `running` -> `failed` before partial writes if backend health/profile checks
  fail.

## Candidate/Review Schema Placeholder

Future-ready schema identity for untrusted semantic candidates.

**Fields**:
- `candidate_id`
- `support_reference_id`
- `review_state`
- `grounding_flags`
- `isolation_state`
- `runtime_metadata`

**Rules**:
- Schema exists only to preserve future constraints and boundaries.
- No extraction, review task workflow, promotion, or trusted-use behavior is
  implemented in this feature.

## Load Run

Record of a graph load attempt.

**Fields**:
- `load_run_id`
- `selected_scope`
- `input_manifest`
- `processed_count`
- `skipped_count`
- `failed_count`
- `write_semantics`: `idempotent_upsert`
- `started_at`, `finished_at`
- `warnings`, `errors`

## Verification Report

Report describing graph state after load, embedding, traversal, or delete.

**Fields**:
- `selected_scope`
- `source_document_count`
- `source_fragment_count`
- `legal_act_count`
- `legal_section_count`
- `legal_fragment_count`
- `legal_reference_count`
- `unresolved_reference_count`
- `embedding_count`
- `embedding_profile_ids`
- `vector_dimensions`
- `backend_names`
- `candidate_review_placeholders_present`
- `warnings`
- `errors`

## Deletion Report

Report for selected-scope deletion.

**Fields**:
- `selected_scope`
- `matched_records`
- `removed_records`
- `skipped_records`
- `retained_related_records`
- `warnings`
- `errors`

## Structural Retrieval Result

Output of exact reference resolution and bounded typed traversal.

**Fields**:
- `query_reference`
- `matched_legal_section_id`
- `source_references`
- `relation_types`
- `depth_limit`
- `fanout_limit`
- `node_limit`
- `visited_count`
- `unresolved_target_evidence`

**Validation rules**:
- Traversal must never exceed relation/depth/fanout/node limits.
- Structural retrieval results MUST NOT include answer text fields such as
  `answer_text`, `answer`, or `generated_answer`; they return only source
  references, resolved nodes, traversal edges, and limit metadata.
