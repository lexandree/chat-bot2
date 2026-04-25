# Operator Command Contracts

These contracts describe the operator-facing command surfaces for the
foundation. Exact executable names may be finalized during implementation, but
inputs, outputs, and failure semantics must remain stable.

## Common Rules

- Commands return structured reports and non-zero exit status on failure.
- Commands never print secrets.
- Commands accept a selected scope with optional `law_codes`.
- Live Neo4j commands require configured Neo4j settings.
- Live embedding commands require the operator-started local-only
  Jina-compatible endpoint.
- Default unit tests exercise command planning/report assembly without live
  services.

## `foundation settings validate`

**Purpose**: Validate configuration before graph writes.

**Inputs**:
- Environment settings from `.env` or process environment.
- Optional `--profile` for named runtime profile.

**Success output**:
- Configuration profile summary.
- Redacted Neo4j connection target.
- Embedding profile id, dimensions, normalization, routing mode.
- Test boundary flags.

**Failure output**:
- Missing/invalid setting names.
- No graph data is written.

## `foundation schema bootstrap`

**Purpose**: Prepare Neo4j constraints and indexes.

**Inputs**:
- Neo4j connection settings.
- Embedding vector dimensions.

**Success output**:
- Graph readiness report.
- Stable constraint/index names.
- Candidate/review placeholder schema status.
- Vector index dimensions.

**Failure output**:
- Connectivity or Cypher error.
- No fallback to a recording facade.

## `foundation preview legal-xml`

**Purpose**: Generate deterministic normalized preview from configured German
legal XML inputs without graph writes.

**Inputs**:
- Corpus manifest or configured legal XML directory.
- Optional `law_codes`.
- Optional output path.

**Success output**:
- Preview artifact path.
- Source document and fragment counts.
- `missing_inputs` list.
- Checksums.

**Failure output**:
- Malformed required file path and source item context.

## `foundation graph load`

**Purpose**: Load previewed source and structural legal graph data.

**Inputs**:
- Preview artifact path.
- Selected scope with `law_codes`.
- Write semantics fixed to idempotent upsert.

**Success output**:
- Load run report.
- Processed/skipped/failed counts.
- Source/legal/reference counts.
- Unresolved reference count.

**Failure output**:
- Invalid preview contract or graph write error.
- Partial failure details by source item where possible.

## `foundation embeddings write`

**Purpose**: Write source document and source fragment embeddings.

**Inputs**:
- Selected scope with `law_codes`.
- Active embedding profile.
- Local-only Jina-compatible endpoint URL.

**Preconditions**:
- Source documents/fragments are loaded.
- Local embedding endpoint is reachable.
- Returned vectors match profile dimensions and normalization expectation.

**Success output**:
- Embedding run report.
- Processed/skipped/failed counts.
- Embedding profile id, model id, backend name, routing mode, dimensions,
  normalization status.

**Failure output**:
- Endpoint unavailable or profile mismatch.
- Must fail before partial graph writes when preflight checks fail.

## `foundation graph verify`

**Purpose**: Verify loaded graph state.

**Inputs**:
- Selected scope with optional `law_codes`.

**Success output**:
- Verification report with source/legal/reference/unresolved/embedding counts.
- Embedding profile ids, vector dimensions, backend names.
- Candidate/review placeholder schema status.
- Warnings.

## `foundation graph delete`

**Purpose**: Delete selected loaded scope without full database reset.

**Inputs**:
- Selected scope with `law_codes`.
- Confirmation flag for destructive action.

**Success output**:
- Deletion report with matched, removed, skipped, and retained related records.

**Failure output**:
- Missing confirmation.
- Invalid scope.
- Graph write error with selected scope preserved in report.

## `foundation references resolve`

**Purpose**: Resolve an exact law code plus section reference.

**Inputs**:
- `law_code`
- `section_reference`
- Optional temporal mode or as-of date.

**Success output**:
- Matched legal section id.
- Source references.
- Temporal status when available.

**Failure output**:
- Unresolved or ambiguous target evidence.
- Result MUST NOT include answer text fields, including `answer_text`, `answer`,
  or `generated_answer`.

## `foundation traversal run`

**Purpose**: Run bounded typed traversal from a resolved section.

**Inputs**:
- `legal_section_id` or exact reference.
- Allowed relation types.
- Depth, fanout, and node limits.

**Success output**:
- Structural retrieval result with relation types, source refs, depth, limits,
  visited count, and unresolved target evidence.
- Result MUST NOT include answer text fields, including `answer_text`, `answer`,
  or `generated_answer`.

**Failure output**:
- Invalid relation type.
- Limit violation prevented and reported.
