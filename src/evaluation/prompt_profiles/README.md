# Evaluation Prompt Profiles

This directory stores versioned JSON prompt profiles for evaluation workflows.

## Purpose

Keep prompt data out of runtime modules so prompt changes are:

- reviewable as data diffs;
- reusable across runners;
- versioned independently from execution code.

The loader lives in [prompts.py](/home/admin2/chat_bot2/src/evaluation/prompts.py).

## File Naming

Each profile file must be named:

`<prompt_version>.json`

Examples:

- `tg_question_canonicalizer_v1.json`
- `tg_qa_candidate_classifier_v4_1.json`
- `tg_qa_cluster_reviewer_v4_1.json`

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

## Change Rules

When the meaning, structure, few-shot set, or output expectations change materially:

1. create a new `prompt_version`;
2. add a new JSON file instead of editing history in place;
3. update the runtime module to point at the new version;
4. update tests and specs that assert the active version.

Small typo fixes in inactive historical profiles should be avoided.

## Data Rules

Prompt profiles must contain only public, reviewable prompt data.

Do not store:

- API keys, endpoints, or local paths;
- private corpora or unsanitized examples;
- run outputs, reviewer decisions, or operator notes;
- executable logic.

Keep provider-specific runtime parameters in code or CLI options, not in these JSON files.
