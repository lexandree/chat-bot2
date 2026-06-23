# 007 Retrieval Diagnostics Summary

Date: 2026-06-20

This document summarizes existing private retrieval diagnostics without
including private question text, Telegram content, generated vectors, or review
labels. The metrics below are evaluation evidence only. They do not create
trusted answer support, production retrieval policy, duplicate decisions, or
question-bank approvals.

## Current Corpus Scope

The latest clean and route diagnostics use the expanded six-law corpus where
available. The current observed law set includes the earlier core immigration
corpus plus the later corpus expansion used for the six-law baselines.

Generated artifacts remain private under `data/evaluation/`.

## Exact-Reference Baseline

Artifact:

`data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_explicit_reference_summary.json`

Observed aggregate:

- source dataset records: 985
- explicit law-reference cases: 99
- in-scope explicit references: 99
- exact-reference Recall@1: 1.000000
- mechanically resolved cases: 99
- excluded as no explicit section reference: 833
- excluded as reference without explicit law code: 54

Interpretation:

Exact reference resolution works for explicit in-scope references. This does
not measure semantic retrieval quality or answer support. Several explicit
references in real data later proved to be status/premise references rather
than answer-support references.

## Clean Curated Semantic Baseline

Six-law semantic artifact:

`data/evaluation/tg_qa_retrieval_benchmark/clean_curated_v1_six_law_semantic_summary.json`

Six-law curated target metrics over 24 checked cases:

- Recall@1: 0.625000
- Recall@5: 0.875000
- Recall@10: 0.916667
- MRR: 0.715972

Earlier four-law clean curated comparison over the same 24 target cases:

- Recall@1: 0.666667
- Recall@5: 0.875000
- Recall@10: 0.916667
- MRR: 0.745068

Human-reviewed clean relevance artifact:

`data/evaluation/tg_qa_retrieval_benchmark/clean_curated_v1_reviewed_relevance_final_24_summary.json`

Reviewed relevance metrics over 24 completed labels:

- Hit@1: 0.750000
- Hit@5: 0.916667
- Hit@10: 1.000000
- Recall@1: 0.446230
- Recall@5: 0.779167
- Recall@10: 0.944444
- MRR: 0.817526

Interpretation:

The clean curated set is useful as a small regression signal. It is not large
or diverse enough to approve broad retrieval changes by itself. Adding laws can
slightly reduce top-1 behavior because additional relevant-looking sections
compete with the previous corpus.

## Real-Record Stress Diagnostic

Mechanism artifact:

`data/evaluation/tg_qa_retrieval_benchmark/real_data_007_last_2000_v1_four_law_stress_mechanisms_summary_labels4.json`

Observed aggregate:

- evaluated completed labels: 28
- records with any diagnostic signal: 27
- records with retrieval-failure signals: 21
- expected reference not relevant: 20
- explicit reference not answer support: 11
- no relevant candidate shown: 11
- relevant only below top-1: 10
- relevant only below top-5: 6
- corpus expansion required: 10
- multi-law support: 3
- multi-section support: 4

Interpretation:

The real-record stress sample confirms that query-explicit references are not
safe semantic ground truth. A cited section may describe status context,
incorrect user framing, or an unrelated bureaucratic premise. Real cases often
need multi-section or multi-law support.

## Route-Ambiguity Diagnostic

Six-law route artifact:

`data/evaluation/tg_qa_retrieval_benchmark/route_ambiguity_v1_six_law_route_summary.json`

Observed aggregate:

- reference cases: 12
- evaluated route cases: 10
- unresolved route-clarification cases excluded from ordinary Recall@k: 2
- route classes: 5 `section_24`, 5 `asyl`
- both `AufenthG` and `AsylG` plausible: 4
- top-1 wrong-route cases: 4

Six-law route visibility:

- expected route hit@1: 0.600000
- expected route hit@5: 1.000000
- expected route hit@10: 1.000000
- wrong-route-only rate@1/@5/@10: 0.000000
- both-route recalled@5: 0.500000
- both-route recalled@10: 1.000000

Diagnostic route-union candidate policy:

- policy: `top1_plus_first_recorded_candidate_per_plausible_route_law_v1`
- average candidate count: 2.000000
- expected route hit: 1.000000
- expected section hit: 0.400000

Interpretation:

Unrestricted semantic top-1 is not a safe route decision. It is still useful as
one candidate source. For ambiguous `Asyl`/`refugee`/section-24 wording, the
retrieval layer should expose weak candidates for multiple plausible legal
routes and let a later clarification/review/inference layer choose the route.
The route-union policy is retained only as diagnostic evidence, not production
policy.

## Current Retrieval Guidance

- Keep exact legal-reference resolution as the first baseline.
- Treat embeddings as candidate generators, not legal truth.
- Do not promote semantic top-1 into trusted answer support.
- Evaluate future retrieval changes against both clean curated and route
  ambiguity diagnostics.
- Preserve route ambiguity instead of forcing section-24 or AsylG when material
  context is missing.
- Keep real-record stress labels separate from clean curated regression metrics.
