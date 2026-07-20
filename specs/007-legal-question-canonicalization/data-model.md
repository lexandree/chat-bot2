# Data Model: Legal Question Canonicalization And Cluster Coverage

## CanonicalizationBatchItem

Review task emitted for a deterministic or LLM-assisted canonicalization pass.

Required fields:

- `task_id`
- `candidate_id`
- `task_scope`: `question_candidate`
- `canonicalization_contract_version`
- `prompt_version` or `policy_version`
- `prompt_example_set_id`
- `canonicalization_identity_policy_version`
- `canonicalization_batch_id` and `canonicalization_batch_hash`
- `task_input_hash`
- `prompt_profile_hash`
- `runtime_hint`
- redacted `input`
- `expected_output_schema`

Input must include redacted 006 candidate evidence only: source ids, redacted
question text, source `question_date` when available, topic labels, law-code
candidates, dialogue flags, selected answer metadata when available, and source
artifact references. Raw Telegram exports and unredacted text are forbidden.

Derived retry tasks additionally carry `canonicalization_source_identity`, the
immutable identity of the original task being reconsidered. It is part of the
retry task identity and is required before a retry can replace base evidence.

## CanonicalizationSampleSummary

Identity and selection metadata for a calibration or qualification sample.

Required fields:

- source and emitted batch identities
- requested and emitted sample counts
- `sampling_policy_id`: `balanced` or `stable_hash`
- deterministic `sampling_policy` description
- `sample_seed`, required and non-empty for `stable_hash`
- `selected_task_id_hash`
- source-status and topic-label counts

`balanced` preserves the existing round-robin diagnostic coverage by answer
status and first topic label. `stable_hash` orders the complete source batch by
SHA-256 of the declared seed and task id; use it for a predeclared qualification
sample whose membership must not depend on file order or model output.

## CanonicalizationEvidence

Imported canonicalization result for one 006 candidate.

Required fields:

- `canonicalization_evidence_id`
- `task_id`
- `candidate_id`
- `canonicalization_run_id`
- `canonicalization_contract_version`
- `canonicalization_identity_policy_version`
- `canonicalization_batch_id` and `canonicalization_batch_hash`
- `task_input_hash`
- `prompt_profile_hash`
- `runtime_profile` and `runtime_profile_hash`
- `canonicalization_evidence_hash`
- `prompt_version` or `policy_version`
- `runtime_contour`
- `backend`
- `model_id` when applicable
- `status`: `completed`, `failed`, or `skipped`
- `failure_reason`
- `canonical_question`
- `canonical_question_language`
- `legal_issue_frame`
- `legal_issue_frame_slug`
- `law_area`
- `facts`
- `desired_outcome`
- `authority_context`
- `hidden_issues`
- `is_legal_answer_required`
- `is_standalone_question`
- `exclusion_reason`
- `confidence`: `low`, `medium`, or `high`
- `quality_flags`
- `question_date` when present in source evidence
- `provenance`

Optional review/finalization fields:

- `untrusted_law_code_hints`: input `law_code_candidates` retained only for
  deterministic non-leakage audit; these values are not legal evidence and are
  not sent to the atomic verifier
- `canonicalization_source_identity` for a derived retry
- `review_provenance`, including decision source, reviewer hash, verifier and
  adjudicator lineage
- `finalization_provenance`, including selected source label, run, evidence,
  batch, and root identity

Validation rules:

- `canonical_question` must preserve the source user's language when status is
  `completed` and the candidate is not excluded.
- `legal_issue_frame_slug` must be stable, lowercase, and machine-oriented.
- `exclusion_reason=none` is valid only when `is_legal_answer_required=true`
  and `is_standalone_question=true`.
- LLM-created fields are review evidence only and cannot create final dataset
  eligibility.
- Unreviewed first-pass evidence, legacy-identity evidence, and evidence without
  human acceptance remain in routing/finalization backlog.

## CanonicalizationReviewDecision

An operator decision imported from an explicitly supplied review-decision
artifact.

Required fields:

- `task_id`
- optional `candidate_id`, which must match the batch task when present
- `decision`: `accept`, `reject`, `retry_qwen`, `send_deepseek`, or `hold`
- optional `decision_reason`
- optional corrected canonicalization fields
- optional `review_payload_version`, emitted with a current review-card hash
- optional `review_payload_hash`, emitted by current review cards and covering
  the exact displayed review payload plus canonicalization evidence identity

`reviewer_hash` is optional compatibility metadata. Its presence or value is
ignored for import, routing, and finalization in the single-reviewer workflow.
Successful import of the supplied decision artifact establishes the manual
review boundary. The imported record retains its decision id, review time, and
batch/task/evidence lineage. When `review_payload_hash` is supplied, import
must match it against a freshly reconstructed card. Imported decisions record
`review_evidence_binding_status` as `validated`, `legacy_identity_unverified`,
`legacy_unverified`, `missing_version`, `unsupported_version`, or `mismatch`;
the final three states fail import. Missing hashes in historical files do not
invalidate the operator's manual-review confirmation, but those decisions are
not suitable as reproducible classifier labels.

## CanonicalizationRunManifest

Run-level metadata for one canonicalization pass.

Required fields:

- `canonicalization_run_id`
- `input_artifact_path`
- `batch_artifact_path`
- `result_artifact_path`
- `evidence_output_path`
- `runtime_contour`
- `backend`
- `model_id` when applicable
- `prompt_version` or `policy_version`
- `canonicalization_contract_version`
- `canonicalization_batch_id` and `canonicalization_batch_hash`
- `prompt_profile_hash`
- `runtime_profile_hashes`
- `input_scope`
- `processed_count`
- `completed_count`
- `failed_count`
- `skipped_count`
- `excluded_count`
- `uncertain_count`
- `started_at`
- `completed_at`
- `known_limitations`

## CanonicalizationOperatorRunBundle

Private sidecar for an LLM canonicalizer, verifier, or adjudicator run.

Required fields:

- `stage`
- result, summary, and checkpoint paths
- optional `log_path`
- runtime profile and `runtime_profile_hash`
- command metadata, including resume and bounded retry settings

## CanonicalizationFinalizationManifest

Control-plane artifact selecting human-reviewed evidence without changing source
run identity. It records the base batch identity, source result/batch artifacts,
selected source run ids, finalization policy, and backlog count.

## CanonicalizationSnapshotManifest

Private export manifest for finalized canonical evidence. It records source
quality tiers, prompt/runtime profile hashes, source run ids, record count, and
strict-validation backlog count. Snapshot records retain review and
finalization provenance; they remain review evidence, not legal authority.

## CanonicalEmbeddingBatchItem

External vectorization input for canonical question and issue-frame text.

Required fields:

- `embedding_item_id`
- `candidate_id`
- `canonicalization_evidence_id`
- `text_role`: `canonical_question` or `legal_issue_frame`
- `embedding_input_text`
- `embedding_prefix`: `Query:`
- `cluster_usage`
- `canonicalization_run_id`
- `embedding_profile_expected`

## CanonicalEmbeddingRecord

Imported vector evidence for a canonical embedding item.

Required fields:

- `embedding_item_id`
- `candidate_id`
- `canonicalization_evidence_id`
- `text_role`
- `embedding_profile_id`
- `provider`
- `model`
- `variant`
- `dimensions`
- `normalized`
- `query_prefix`
- `document_prefix`
- `routing_mode`
- `task_semantics`
- `backend_name`
- `vector`
- `embedding_status`
- `failure_reason`

Embedding records are evaluation artifacts and do not write vectors to Neo4j.

## LegalIntentCandidate

Optional diagnostic interpretation of one included canonical question for
pair-equivalence evaluation.

Phase 8 artifacts live under ignored
`data/evaluation/tg_qa_legal_intent_equivalence/` unless a later publication
step explicitly sanitizes them.

Required fields:

- `legal_intent_candidate_id`
- `candidate_id`
- `canonicalization_evidence_id`
- `source_canonical_question`
- `source_legal_issue_frame`
- `law_area`
- material legal slots such as `legal_domain`, `actor`, `subject`,
  `current_status`, `target_status`, `desired_action`, `legal_object`,
  `authority_context`, `third_party_context`, `location_scope`,
  `temporal_condition`, and `operational_boundary`
- `material_slots_unknown`
- `ambiguities`
- `evidence_refs`
- `validation_flags`
- `confidence`: `low`, `medium`, or `high`
- `review_status`: `candidate`, `review_approved`, `review_rejected`,
  `needs_more_context`, or `uncertain`
- `policy_version`
- `provenance`

Legal intent candidates are review evidence only. Unsupported material slots
must be unknown or ambiguous rather than guessed.

## QuestionPairBenchmarkRecord

Stable diagnostic pair comparing two canonical questions.

Required fields:

- `pair_id`
- `left_canonicalization_evidence_id`
- `right_canonicalization_evidence_id`
- `left_candidate_id`
- `right_candidate_id`
- `pair_source_reasons`
- `similarity_evidence`
- `benchmark_status`
- `provenance`

Pair identity must be independent of left/right ordering. Similarity evidence
is candidate-generation evidence only.

## PairEquivalenceDecision

Reviewable candidate judgment for one benchmark pair.

Required fields:

- `pair_decision_id`
- `pair_id`
- `decision_source`
- `pair_class`: `exact_duplicate`, `same_legal_intent`,
  `same_topic_different_issue`, `related_context`, `different`, or
  `uncertain`
- `answer_equivalence`: `safe_to_share_answer`, `not_safe_to_share_answer`, or
  `uncertain`
- `canonical_question_equivalence`: `safe_to_share_question`,
  `not_safe_to_share_question`, or `uncertain`
- `allowed_downstream_actions`
- `material_differences`
- `shared_material_facts`
- `unknowns`
- `ambiguities`
- `short_reason`
- `confidence`
- `risk`
- `validation_flags`
- `policy_version`
- `runtime_metadata`

Pair decisions must record downstream safety separately from pair class.

Implemented diagnostic decision sources:

- similarity baseline over cosine plus optional recos scores;
- deterministic legal-slot comparator over imported `LegalIntentCandidate`
  records;
- operator-managed LLM pair judge with structured `PairEquivalenceDecision`
  output.

## PairReviewLabel

Human label for one benchmark pair.

Required fields:

- `pair_review_label_id`
- `pair_id`
- `pair_class`
- `answer_equivalence`
- `canonical_question_equivalence`
- `allowed_downstream_actions`
- `decision_reason`
- `reviewer_hash`
- `reviewed_at`

Import must reject duplicate pair ids with conflicting labels unless an
explicit replacement mode is used.

## EquivalenceEvaluationReport

Diagnostic report comparing pair methods against reviewed labels.

Required fields:

- source dataset, benchmark, legal-intent candidate, pair decision, and review
  label artifact paths
- counts by pair class, law area, pair source reason, review state, method, and
  risk
- confusion counts when reviewed labels are sufficient
- false duplicate risk examples
- false separation risk examples
- high-similarity hard negatives
- insufficient-label warnings
- policy versions, embedding profile ids, runtime contour, and generated
  timestamp

Evaluation reports may recommend candidate-generation methods, but they must
not approve automatic duplicate removal or answer reuse without reviewed
support.

## LegalIssueCluster

Cluster of canonicalized candidates representing one reviewable legal issue.

Required fields:

- `legal_issue_cluster_id`
- `legal_issue_frame_slug`
- `canonical_question_representative`
- `law_area`
- `authority_context`
- `candidate_ids`
- `canonicalization_evidence_ids`
- `source_question_dates`
- `representative_raw_questions`
- `cluster_size`
- `cluster_confidence`
- `cluster_quality_flags`
- `merge_policy_version`
- `review_route`
- `coverage_status`

Quality flags must identify broad, low-cohesion, conflicting, low-confidence,
or privacy-sensitive clusters instead of silently approving them.

## LegalIssueCluster Summary And Manifest

Issue cluster generation must write a cluster JSONL artifact plus summary and
manifest artifacts.

Summary required fields:

- source canonicalization evidence artifact path
- source canonical embedding record artifact path
- processed evidence count
- completed cluster count
- emitted cluster count
- excluded evidence count
- uncertain evidence count
- failed evidence count
- counts by law area
- counts by authority context
- counts by cluster quality flag
- counts by review route
- merge policy version
- runtime contour
- generated timestamp

Manifest required fields:

- artifact type
- input artifact paths
- output artifact paths
- policy versions
- embedding profile ids when embeddings were used
- runtime contour
- known limitations
- unresolved backlog counts

## ClusterCoverageRecord

Coverage evidence comparing one canonical issue cluster to reviewed 006 seed
cases or question-bank entries.

Required fields:

- `coverage_record_id`
- `legal_issue_cluster_id`
- `coverage_analysis_version`
- `coverage_status`: `covered`, `partial`, `uncovered`, `excluded`, or
  `uncertain`
- `best_reviewed_case_id`
- `best_question_bank_entry_id`
- `question_similarity_score`
- `issue_frame_similarity_score`
- `supporting_candidate_ids`
- `coverage_gap_flags`
- `known_limitations`

Coverage records must not treat Telegram answers as legal truth.

## ClusterReviewDecision

Human decision for one legal issue cluster.

Required fields:

- `cluster_review_decision_id`
- `legal_issue_cluster_id`
- `decision`: `approve_question_bank`, `approve_final_evaluation`, `reject`,
  `merge`, `split`, `needs_more_context`, or `uncertain`
- `decision_scope`
- `reviewed_canonical_question`
- `reviewed_legal_issue_frame_slug`
- `reference_answer_action`: `none`, `keep_selected_telegram_answer`,
  `replace_manual`, or `needs_manual_answer`
- `reference_answer_source`
- `selected_reference_answer_text_redacted` when retaining a reviewed Telegram
  answer for final evaluation promotion
- `manual_reference_answer_text_redacted`
- `reviewer_hash`
- `reviewed_at`
- `decision_reason`
- `temporal_relevance_state`
- `source_question_date`
- `evaluation_date`
- `legal_corpus_as_of_date`
- `temporal_review_date`
- `temporal_review_reason`

Allowed `temporal_relevance_state` values:

- `current_reusable`
- `historical_but_generalizable`
- `transition_bound`
- `superseded_or_expired`
- `unresolved_currentness`

Promotion rule:

- `approve_question_bank` may create a question-bank entry without a reference
  answer.
- `approve_final_evaluation` requires reviewed reference answer material.
- Absence of a reviewed temporal state is treated as
  `unresolved_currentness`.

## TemporalCurrentnessReviewRecord

Review queue record for deciding whether an issue cluster may enter
current-default retrieval or must remain historical/temporal evidence.

Required fields:

- `temporal_currentness_review_id`
- `legal_issue_cluster_id`
- `canonical_question_representative`
- `law_area`
- `authority_context`
- `source_question_dates`
- `evaluation_date`
- `legal_corpus_as_of_date`
- `suggested_temporal_relevance_state`
- `allowed_temporal_relevance_states`
- `current_default_eligible`
- `review_decision_template`
- `policy_version`
- `trust_boundary`

`current_reusable` and `historical_but_generalizable` may enter
current-default promotion after review. `transition_bound`,
`superseded_or_expired`, and `unresolved_currentness` are retained for audit or
temporal evaluation and blocked from current-default promotion.

## QuestionBankEntry

Reviewed or reviewable canonical issue entry.

Required fields:

- `question_bank_entry_id`
- `legal_issue_cluster_id`
- `canonical_question`
- `legal_issue_frame_slug`
- `law_area`
- `authority_context`
- `representative_raw_questions`
- `source_question_dates`
- `temporal_relevance_state`
- `current_default_eligible`
- `temporal_currentness`
- `coverage_status`
- `review_status`
- `reference_answer_status`
- `provenance`

## QuestionBank Summary And Manifest

Question-bank build must write a question-bank JSONL artifact plus summary and
manifest artifacts.

Summary required fields:

- source issue cluster artifact path
- source review decision artifact path
- processed cluster count
- completed entry count
- excluded count
- failed decision count
- approved entry count
- rejected entry count
- needs-more-context count
- uncertain count
- missing reference answer count
- counts by law area
- counts by authority context
- counts by coverage status
- counts by reference answer status
- counts by temporal relevance state
- current-default eligible count
- current-default blocked temporal count
- review policy version
- question-bank policy version
- temporal-currentness policy version
- runtime contour
- generated timestamp

Manifest required fields:

- artifact type
- input artifact paths
- output artifact paths
- review policy version
- question-bank policy version
- known limitations
- unresolved backlog counts

## ReviewedEvaluationCaseCandidate

Candidate for a final evaluation case created from a reviewed issue cluster.

Required fields:

- `case_candidate_id`
- `legal_issue_cluster_id`
- `source_006_case_id` when applicable
- `canonical_question`
- `question_text_redacted`
- `reference_answer_text_redacted`
- `reference_answer_source`
- `reference_answer_role`
- `review_status`
- `promotion_status`: `eligible`, `blocked_missing_reference_answer`,
  `blocked_temporal_currentness`, or `rejected`
- `source_question_dates`
- `temporal_relevance_state`
- `current_default_eligible`
- `temporal_currentness`
- `provenance`

Only `eligible` records with reviewed reference answer material and a
current-default-eligible temporal state may enter a reviewed evaluation dataset.

## FinalCaseCandidate Promotion Summary And Manifest

Final case candidate promotion must write a candidate JSONL artifact plus
summary and manifest artifacts.

Summary required fields:

- source question-bank artifact path
- source review decision artifact path
- processed question-bank entry count
- completed candidate count
- excluded count
- uncertain count
- failed count
- emitted candidate count
- eligible count
- blocked missing reference answer count
- blocked temporal currentness count
- rejected count
- LLM-only rejection count
- manual reference answer count
- accepted Telegram reference answer count
- counts by law area
- counts by authority context
- counts by temporal relevance state
- promotion policy version
- reference answer policy version
- temporal-currentness policy version
- runtime contour
- generated timestamp

Manifest required fields:

- artifact type
- input artifact paths
- output artifact paths
- promotion policy version
- reference answer policy version
- known limitations
- unresolved backlog counts

## ReviewedEvaluationDataset Artifact

Exported final evaluation dataset produced from eligible
`ReviewedEvaluationCaseCandidate` records.

Required files:

- reviewed final cases JSONL
- manifest JSON
- quality summary JSON

Each reviewed final case must include:

- `case_id`
- `case_candidate_id`
- `legal_issue_cluster_id`
- `canonical_question`
- `question_text_redacted`
- `reference_answer_text_redacted`
- `reference_answer_source`
- `reference_answer_role`
- `review_status`
- `source_question_dates`
- `temporal_relevance_state`
- `temporal_currentness`
- `provenance`

The manifest must include:

- source final case candidate artifact path
- case count
- counts by reference answer source
- counts by law area
- counts by review status
- policy versions
- generated timestamp
- known limitations

The quality summary must include:

- eligible input count
- exported case count
- blocked/rejected excluded counts
- missing reference answer exclusion count
- temporal currentness exclusion count
- LLM-only exclusion count
- duplicate cluster or case id rejection count

## State Transitions

- Canonicalization evidence: `pending` -> `completed`, `failed`, or `skipped`.
- Issue cluster: `draft` -> `needs_review`, `review_approved`,
  `review_rejected`, `needs_split`, `needs_merge`, or `uncertain`.
- Question-bank entry: `candidate` -> `approved` or `rejected`.
- Evaluation promotion: `candidate` -> `eligible`,
  `blocked_missing_reference_answer`, `blocked_temporal_currentness`, or
  `rejected`.
- Reviewed evaluation dataset case: `eligible_candidate` -> `exported` or
  `excluded`.

## AtomicVerificationSidecar

Optional review evidence attached to one immutable canonicalization evidence
hash. It contains a deterministic field claim ledger, independent verifier
verdicts, optional independent critic verdicts and disagreement evidence, exact
source spans, controller reasons, optional bounded repair, and post-repair
re-verification.

An exact quote with an incorrect offset may be normalized only from a valid
start anchor or a unique source occurrence. The sidecar records supplied and
normalized offsets; absent or ambiguous quotes remain invalid. Runtime entries
are attempt-level so failed parse/provider calls are not erased from lineage.
Unsupported list atoms transition only by deterministic deletion; supported
list items remain unchanged. Critic disagreement remains explicit and uses a
conservative merge rather than majority selection.

An atomic semantic stage may use direct structured output or a two-step
execution. The two-step form stores a bounded plain-text decision memo and its
raw SHA-256, then sends that memo plus the original compact payload to a
separate no-reasoning formatter. Native hidden reasoning is not the memo. A
critic creates its own memo and never receives the verifier memo.
Formatter verification claims carry exact quote strings. Deterministic code
derives offsets only for a unique exact occurrence and converts a supported
claim with no resolvable quote to `unresolved`.

State transitions:

- `completed evidence -> pass`
- `completed evidence -> revise -> pass_repaired`
- `completed evidence -> verifier/critic disagreement -> revise | hold`
- `completed evidence -> hold`
- provider/schema failure -> `failed`
- non-completed input evidence -> `skipped`

`pass` and `pass_repaired` do not represent human acceptance. `hold` is terminal
for one run and requires a new operator run or human review; the contour does
not recurse.

## AtomicModelRuntimeProfile

A tracked, secret-free deployment profile for one atomic model. It contains a
stable profile id, provider, parameter transport, endpoint, model id,
structured-output method, and explicit verifier/critic/repair options. Stage
options contain output-token limit, timeout, temperature, and native request
parameters. `reasoning_mode` declares whether a deployment runs with reasoning
enabled, disabled, or at its provider default. A stage may bind a second
profile as formatter; that profile must declare disabled reasoning. The
registry version and content hash, both effective component profiles, and the
execution mode bind run and resume identity.

The endpoint URL and pricing source remain registry configuration; generated
records retain a redacted endpoint shape and dated numeric pricing snapshot.
API keys, authorization headers, private inputs, and raw prompts are forbidden.

The atomic run also records critic policy. `always` invokes the critic after
every primary verifier. `before_pass` invokes it only when the primary
controller would otherwise pass, including after repair. Per-record
`initial_critic_executed` and `final_critic_executed` fields, plus deterministic
skip reasons, preserve the actual state transition.
