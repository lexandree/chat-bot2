# Route-Ambiguity Retrieval Benchmark

## Purpose

This benchmark measures whether retrieval can keep plausible legal routes
visible when colloquial Russian wording such as "беженство", "убежище",
"лагерь", or "беженец" may refer either to:

- temporary protection under `AufenthG`, especially `§ 24`; or
- the asylum procedure under `AsylG`.

It is a diagnostic benchmark, not a trusted answer source. It must not force a
hard legal route when material facts are missing.

## Contract

Each JSONL record contains:

- `artifact_type`: `tg_qa_route_ambiguity_reference_case`
- `benchmark_case_id`: stable route benchmark id
- `canonical_question`: publication-safe Russian diagnostic question
- `material_context`: the fact that makes the route resolvable or unresolved
- `surface_group_id`: id for paired or near-identical surface wording
- `route_class`: one of `section_24`, `asyl`, or
  `unresolved_requires_clarification`
- `plausible_route_law_codes`: route laws that should remain reviewable
- `expected_route_law_codes`: reviewed route law codes for resolvable records,
  or all plausible laws for unresolved records
- `outcome`: `mechanically_resolved` only when one primary expected legal
  section is defined; otherwise `route_unresolved_requires_clarification`
- `expected_legal_section_id`: the primary expected section for current
  semantic baseline compatibility, empty for unresolved records
- `target_evidence_type`: `route_ambiguity_checked`
- `curation_reason`: why the route is selected or unresolved

## Review Rules

1. Similar surface wording is intentional. A correct method must use material
   context, not the word "беженство" alone.
2. Ukrainian nationality alone is not a complete hard route decision. The
   question may still require residence-history, displacement, date, prior
   protection, or status-history facts.
3. Third-country nationals with Ukrainian temporary residence must not be
   treated as automatically continuing `§ 24` cases.
4. Unresolved records should produce both plausible routes for review rather
   than a single hidden decision.
5. Retain a candidate-generation or route-hint policy only after reporting this
   route benchmark together with the clean retrieval baseline.

## Initial Fixture

The tracked fixture is:

```text
specs/007-legal-question-canonicalization/route-ambiguity-reference-cases.jsonl
```

It starts with a small balanced set of section-24, asylum, and unresolved
records. Later expansion should preserve paired surface groups and add new
examples only when the route distinction is general, not a one-off correction.

## Baseline Runner

Use the dedicated runner so route records are not mixed with clean retrieval
artifacts:

```bash
bash scripts/evaluation/run_007_route_ambiguity_retrieval.sh prepare
bash scripts/evaluation/run_007_route_ambiguity_retrieval.sh embed-queries
bash scripts/evaluation/run_007_route_ambiguity_retrieval.sh finish
```

`prepare` writes a four-law embedding batch and excludes unresolved records
from ordinary Recall@k query evaluation. `embed-queries` requires the local
embedding endpoint. `finish` reuses the existing four-law document vectors and
stops if query vectorization has any failures.

After corpus expansion, run the same diagnostic with explicit six-law scope and
fresh query+document vectors:

```bash
LEGAL_PREVIEW=data/corpus_expansion/core_six_law_alias_fix_20260618/active_corpus_preview.json \
PREFIX=route_ambiguity_v1_six_law \
LAW_CODES='AufenthG AsylG BeschV VwVfG AsylbLG AufenthV' \
VECTOR_MODE=full \
BATCH_SIZE=16 \
bash scripts/evaluation/run_007_route_ambiguity_retrieval.sh full-fresh
```

The route report writes:

- `expected_route_hit_rate`: whether at least one candidate from the expected
  route law appears at k;
- `wrong_route_only_rate`: whether only a wrong plausible route appears at k;
- `both_aufenthg_asylg_recalled_rate`: among records where both routes should
  remain visible, whether both route laws appear at k;
- `avg_plausible_route_law_code_recall`: average recall of reviewable route
  law-code hints.

Current unrestricted four-law baseline:

- expected-route hit: `0.900000` at k=1, `1.000000` at k=5 and k=10;
- top-1 wrong route count: `1/10`;
- wrong-route-only rate: `0.000000` at k=1, k=5, and k=10;
- both `AufenthG`/`AsylG` recalled: `0.000000` at k=1, `0.750000` at k=5,
  `1.000000` at k=10;
- ordinary expected-section Recall@1/5/10: `0.400000`, `0.500000`,
  `0.600000`.

The single top-1 route error is
`tg-qa-route-ambiguity-case:ua-section24-fiktionsbescheinigung`, where the
unrestricted semantic top law is `AsylG` while the expected route is
`AufenthG`. This is diagnostic evidence for multi-hypothesis route candidate
generation, not a hard rule change.

Current unrestricted six-law baseline after adding `AsylbLG` and `AufenthV`:

- expected-route hit: `0.600000` at k=1, `1.000000` at k=5 and k=10;
- top-1 wrong route count: `4/10`;
- wrong-route-only rate: `0.000000` at k=1, k=5, and k=10;
- both `AufenthG`/`AsylG` recalled: `0.000000` at k=1, `0.500000` at k=5,
  `1.000000` at k=10;
- ordinary expected-section Recall@1/5/10: `0.400000`, `0.500000`,
  `0.600000`.

The six-law expansion intentionally increased retrieval complexity. Three new
top-1 route errors are `AufenthV` over `AufenthG` for section-24 questions, and
the previous `ua-section24-fiktionsbescheinigung` `AsylG` top-1 error remains.
The expected route is still present in top-5 for every evaluated record, so
this is evidence against trusting unrestricted semantic top-1 as route policy,
not evidence that the expanded corpus is unusable.

Route-union candidate-generation diagnostic:

- policy: `top1_plus_first_recorded_candidate_per_plausible_route_law_v1`;
- four-law expected-route hit: `1.000000`, expected-section hit: `0.400000`,
  average candidate count: `1.700000`;
- six-law expected-route hit: `1.000000`, expected-section hit: `0.400000`,
  average candidate count: `2.000000`.

This supports weak multi-route candidate generation for ambiguous
refugee/asylum wording: keep both `AufenthG` and `AsylG` visible when material
facts can change the route, and treat nationality, corpus prior, status
history, and date as reviewable ranking evidence rather than hard route
decisions. The route union is not answer support and does not prove that the
exact expected legal section has been retrieved.
