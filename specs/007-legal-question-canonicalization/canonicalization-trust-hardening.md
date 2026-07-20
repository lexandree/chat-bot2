# Canonicalization Trust Hardening

Date: 2026-07-10

## Decision

007 keeps its existing staged architecture: canonicalizer, verifier,
adjudicator, human review, and downstream evaluation artifacts remain separate.
This change hardens the control plane rather than changing legal reasoning or
adding graph writes.

## Immutable Evidence Identity

Every emitted canonicalization task has a deterministic task-input hash,
prompt-profile hash, batch id, and batch hash. Importers recompute these values
from the supplied batch and reject mismatched, missing, duplicate, or unknown
results in strict mode. Runtime profiles and canonical evidence are separately
hashed.

Derived retry tasks are distinct inputs because retry context is material. They
retain a `canonicalization_source_identity` pointing to the original task. A
finalizer can select a retry only when it validates against its own retry batch
and its root identity matches the base batch task.

## Review Admission

Routing reconciles the entire batch, including missing and duplicate result
rows. The default policy is `hold`: an unreviewed result stays in backlog.
`first_pass` remains available only as an explicit diagnostic mode and is not
eligible for finalization.

Verifier records are tied to the canonical evidence hash plus verifier prompt
and runtime profiles. Adjudication records preserve their own prompt/batch
identity. A material conflict between adjudicators is routed to human review,
not silently retried.

Human acceptance is established by a valid decision supplied through the
explicit review-decision import artifact. `reviewer_hash` is retained only as
an optional compatibility field and is not a trust condition in the
single-reviewer workflow. New review-card exports bind the exact displayed
candidate and verifier context with `review_payload_hash`; import rejects a
changed payload and marks older hashless decisions `legacy_unverified` for
benchmark purposes without revoking their explicit manual-review status.
Finalization refuses unreviewed, legacy-unverified canonicalization evidence,
incompatible, duplicate, or missing evidence. It preserves the actual source
run id and records selection provenance instead of rewriting all outputs into a
synthetic merged run.

## Reproducible Operations

Canonicalizer, verifier, and adjudicator runners bind resume state to a runtime
profile and input identity. Each writes a checkpoint and a run-bundle sidecar
with command metadata and optional log path. Default provider retry is finite.

The core CLI owns finalization and private snapshot creation. Temporary scripts
may orchestrate operator steps but must call those commands and must not merge
JSONL with `jq` or rewrite run ids.

## Model Selection By Batch Scale

For a bounded calibration, review, retry, or adjudication batch of at most 100
records, use the best currently available OpenCode model rather than compensating
for a weaker model with an agent wrapper. The current operator default is
`glm-5.2`; its exact model id, runtime profile, and endpoint contour are written
to the run bundle.

This is a runtime-selection policy, not a new trust boundary: GLM output remains
review evidence and still passes the same validation, verifier, adjudication,
and human-review gates. Existing Qwen artifacts and bulk economics remain
historical or separately evaluated; they are not silently relabeled or merged.

## Compatibility

Historical artifacts remain read-only. `--allow-legacy-identity` is an explicit
operator escape hatch for inspection/import; it marks evidence unverified and
does not make it acceptable for a strict finalized snapshot. No Neo4j mutation,
retrieval-policy change, legal-answer promotion, or change to asymmetric
embedding prefixes is introduced.
