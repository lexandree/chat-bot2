# Evaluation Prompt Profiles

This directory stores versioned JSON prompt profiles for evaluation workflows.

## Purpose

Keep prompt data out of runtime modules so prompt changes are:

- reviewable as data diffs;
- reusable across runners;
- versioned independently from execution code.

The loader lives in [prompts.py](../prompts.py).

## File Naming

Each profile file must be named:

`<prompt_version>.json`

Examples:

- `tg_question_canonicalizer_v1.json`
- `tg_qa_candidate_classifier_v4_1.json`
- `tg_qa_cluster_reviewer_v4_1.json`
- `tg_question_canonicalization_atomic_verifier_v6.json`
- `tg_question_canonicalization_atomic_critic_v6.json`

Atomic verifier v7/v8 compact-memo files are inactive diagnostic profiles.
Their recorded live runs make them immutable; v6 remains the active verifier
and critic contract.

Atomic verifier/critic v1-v5 and repair v1-v2 are immutable historical
profiles retained for recorded-run reproducibility. Repair v3 is active.

The `prompt_version` field inside the JSON must match the filename stem exactly.

## Canonical Structure

Every prompt profile must be a single JSON object.

Common fields:

- `prompt_version`: stable version id used in emitted artifacts
- `system_instruction`: primary task instruction string
- `expected_output_schema`: JSON object with schema hints used in task payloads

Optional fields depending on workflow:

- `prompt_example_set_id`: identifier for few-shot example bundle
- `few_shot_examples`: array of input/output examples
- `prompt_profile`: variant label such as `full` or `compact`
- `user_prompt_lines`: ordered array of user-prompt scaffold lines
- `reasoning_system_instruction` and `reasoning_user_prompt_lines`: bounded
  plain-text memo contract for an optional reasoning half-stage
- `formatter_system_instruction` and `formatter_user_prompt_lines`: strict
  schema-conversion contract for a separate no-reasoning formatter

## Change Rules

When the meaning, structure, few-shot set, or output expectations change materially:

1. create a new `prompt_version`;
2. add a new JSON file instead of editing history in place;
3. update the runtime module to point at the new version;
4. update tests and specs that assert the active version.

Small typo fixes in inactive historical profiles should be avoided.
Any profile whose hash appears in a generated run is immutable; corrections
require a new profile version even when the older profile remains active only
for comparison.

Canonicalization batches record a deterministic `prompt_profile_hash` derived
from the complete JSON profile. Operator runners reject a batch when the active
profile version differs, and importers verify the hash before admitting output.
Keep tests focused on profile version, schema, hash, and critical behavioral
invariants rather than every incidental wording fragment.

## Data Rules

Prompt profiles must contain only public, reviewable prompt data.

Do not store:

- API keys, endpoints, or local paths;
- private corpora or unsanitized examples;
- run outputs, reviewer decisions, or operator notes;
- executable logic.

Do not create few-shot examples by paraphrasing, abstracting, or otherwise
deriving them from private corpus records. A sanitized paraphrase still carries
private-corpus information. New tracked examples must have an independently
authored public provenance; otherwise express the rule as a generalized
instruction and keep task ids only in the regression registry.

Keep provider-specific runtime parameters in code or CLI options, not in these JSON files.
