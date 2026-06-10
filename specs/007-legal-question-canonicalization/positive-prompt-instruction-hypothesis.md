# 007 positive-instruction prompt hypothesis

Goal: test whether replacing prohibitive instructions (`do not`, `never`, `must not`, `should not`) with positive behavioral instructions improves 007 canonicalization stability.

Historical prompt profiles remain unchanged. The positive profiles below are separate experiment profiles.

## Generated Profiles

- `tg_question_canonicalizer_v6` -> `tg_question_canonicalizer_v10_positive`
- `tg_question_canonicalization_verifier_v7` -> `tg_question_canonicalization_verifier_v8_positive`
- `tg_question_canonicalization_adjudicator_v7` -> `tg_question_canonicalization_adjudicator_v8_positive`
- `tg_legal_intent_pair_judge_v1` -> `tg_legal_intent_pair_judge_v2_positive`
- `tg_qa_candidate_classifier_v4_1` -> `tg_qa_candidate_classifier_v4_2_positive`
- `tg_qa_cluster_reviewer_v4_1` -> `tg_qa_cluster_reviewer_v4_2_positive`
- `tg_qa_cluster_reviewer_compact_v4_1` -> `tg_qa_cluster_reviewer_compact_v4_2_positive`

## Before -> After Catalog

| Area | Before | After |
| --- | --- | --- |
| response boundary | `Do not answer the legal question.` | `Produce evidence/verdict/adjudication fields only; leave legal-answer content out of the response.` |
| format boundary | `Never return prose, markdown, apologies, explanations, or the legal answer itself.` | `Return exactly one valid json object and omit prose, markdown, apologies, explanations, and legal-answer text.` |
| citation boundary | `Do not invent legal citations.` | `Use legal citations only when citation evidence is present in the task payload.` |
| CJK artifact boundary | `Never output Chinese characters.` | `Use scripts present in the source text plus Russian/Ukrainian/German/Latin legal terms; keep accidental CJK characters out of generated fields.` |
| field-name boundary | `Do not assume the source is a question.` | `Treat question-like field names as historical labels; decide questionhood from the source text itself.` |
| issue-frame alignment | `Do not copy source phrasing or mechanically translate the English issue frame.` | `Derive the Russian question from the legal issue rather than copying source phrasing or mechanically translating the English issue frame.` |
| jurisdiction context | `Do not treat named third countries as target jurisdiction merely because they are named.` | `Treat named third countries as target jurisdiction only when the source explicitly asks for that jurisdiction's law.` |
| operational boundary | `Do not treat appointment/application procedure questions as appointment day confirmation/current slot availability.` | `Treat appointment/application requirement for a legal status document as a legal procedure question.` |
| wait-time boundary | `Do not treat ordinary processing/wait-time questions as legal deadline questions unless legal time limits/remedies are asked.` | `Treat ordinary production/response time as operational wait-time; classify as legal only when legal time limit, rights while waiting, consequence, delay remedy, or refusal/appeal is asked.` |
| mixed-query boundary | `Do not merge mailbox, shopping, transport, office-hour, or other practical logistics into canonical_question.` | `Leave unrelated practical logistics out of canonical_question and preserve only the standalone legal question.` |
| retry feedback boundary | `Do not restore a dropped non-legal part.` | `Keep dropped non-legal parts dropped and improve only legal extraction, law_area, and flags.` |
| single-question boundary | `Do not preserve multiple separate legal questions in canonical_question.` | `Keep exactly one central legal question in canonical_question and place sub-issues in facts or hidden_issues.` |
| answer-like text boundary | `Do not recover/reconstruct/guess a hidden legal question from an answer-like source.` | `Infer legal issue evidence only from the source author's own explicit standalone legal request/question.` |
| problematic premise | `Do not sanitize unlawful or non-existent-premise questions into neutral procedures.` | `Preserve suspected unlawful premise, missing legal basis, non-existent entitlement, or refusal to accept legal proof.` |
| intake/capacity boundary | `Do not include intake/capacity questions merely because asylum/§24/refugee/authority context is mentioned.` | `Classify current intake/capacity questions as non_legal_question even when asylum/§24/refugee/authority context is mentioned.` |
| personal-date boundary | `Do not add requires_live_operational_data just because the user mentions a personal date.` | `Treat personal dates from filing, appointment, move, or employment timeline as normal case facts.` |
| verifier excluded-case boundary | `Do not return fail because of secondary fields that do not change routing outcome.` | `Return pass/accept for correctly excluded records when secondary fields leave include/exclude routing unchanged.` |
| verifier field-scope boundary | `Do not fail canonical_question for operational details unless they actually appear in canonical_question or distort legal_issue_frame.` | `Inspect canonical_question itself and fail only when those details appear there or distort legal_issue_frame.` |
| adjudicator consistency | `Do not return pass with reject, or fail with accept.` | `Use consistent verdict/recommendation pairs: pass with accept, fail with reject or retry_generator, uncertain with human_review unless a clearer route is justified.` |
| pair-judge safety | `Do not mark safe_to_share_answer/question unless reuse is safe.` | `Mark sharing safe only when material legal assumptions and meaning are preserved.` |

## Test Design

- Use 20 records: 7 straightforward records and 13 boundary records.
- Run the same 20 records with baseline `tg_question_canonicalizer_v6` and positive `tg_question_canonicalizer_v10_positive`.
- Compare schema success, include/exclude routing, canonical question shape, law_area, hidden_issues, and quality_flags.
- Follow with verifier/adjudicator positive-profile checks only if canonicalizer output is technically clean.

The concrete record set and commands live in `tmp/run_007_positive_prompt_ab_smoke.sh` and `data/evaluation/tg_qa_canonicalization/real_data_007_positive_prompt_ab_20_manifest.json`.

## First Smoke Result

Run date: 2026-06-02.

Model: `qwen3.6-plus`, OpenAI-compatible opencode endpoint, `enable_thinking=false`, 20 baseline calls plus 20 positive-profile calls.

Artifacts:

- Baseline results: `data/evaluation/tg_qa_canonicalization/real_data_007_positive_prompt_ab_20_v6_qwen_results.jsonl`
- Positive results: `data/evaluation/tg_qa_canonicalization/real_data_007_positive_prompt_ab_20_positive_qwen_results.jsonl`
- Comparison: `data/evaluation/tg_qa_canonicalization/real_data_007_positive_prompt_ab_20_compare.json`
- TSV: `data/evaluation/tg_qa_canonicalization/real_data_007_positive_prompt_ab_20_compare.tsv`
- Review HTML baseline: `data/evaluation/tg_qa_canonicalization/real_data_007_positive_prompt_ab_20_v6_review.html`
- Review HTML positive: `data/evaluation/tg_qa_canonicalization/real_data_007_positive_prompt_ab_20_positive_review.html`

Technical results:

- Baseline: 20/20 completed, 0 failed, 0 provider retries, 0 output retries.
- Positive: 20/20 completed, 0 failed, 0 provider retries, 0 output retries.
- Baseline duration: 519.342 seconds, 0.039 items/second.
- Positive duration: 198.898 seconds, 0.101 items/second.
- Positive output had no CJK violations and no multi-question violations in this sample.

Comparison counts:

- `baseline_matches_manifest_routing`: 18/20
- `positive_matches_manifest_routing`: 18/20
- `routing_changed`: 2/20
- `law_area_changed`: 2/20
- `quality_flags_changed`: 4/20
- `canonical_question_changed`: 14/20

Interpretation:

- The positive rewrite is technically safe on the 20-record smoke set.
- The positive rewrite is not proven better on routing: baseline and positive both matched expected routing on 18/20.
- Positive corrected the `complex_procedural_appointment_required` scenario where the fresh baseline run excluded a procedure question that should be included.
- Positive regressed the `complex_live_intake_capacity` scenario by including an operational placement/intake question that should remain excluded.
- Both profiles failed the `complex_answer_like_legal_topic` standalone boundary by including a context-dependent fragment.

Working conclusion:

- Keep the positive prompt profiles as experiment profiles only.
- Do not promote `tg_question_canonicalizer_v10_positive` as the default from this smoke alone.
- The useful next prompt work is targeted: strengthen intake/capacity exclusion and standalone-fragment detection while preserving the improved appointment/procedure inclusion behavior.
