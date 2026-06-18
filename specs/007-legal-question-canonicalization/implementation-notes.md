# Implementation Notes: Legal Question Canonicalization And Cluster Coverage

## Run Log

- Implemented `src/evaluation/tg_question_canonicalization.py` as an offline
  file-artifact workflow for canonicalization evidence, canonical embedding
  import, issue clusters, coverage, cluster review import, question-bank build,
  final promotion gating, reviewed dataset export, and boundary verification.
- Wired 007 evaluation CLI commands in `src/app/commands.py`.
- Added unit coverage in `tests/unit/test_tg_question_canonicalization.py`.
- Added an offline CLI smoke pipeline in `tests/smoke/test_cli_offline.py`.
- Added synthetic fixture guidance in
  `tests/fixtures/tg_question_canonicalization/README.md`.
- Added Pydantic payload schemas for canonicalization and verifier outputs,
  reused by local import validation and optional LangChain structured-output
  chains.
- Added compact LLM payload assembly that removes source artifact paths, source
  message ids, and selected answer metadata before live LLM calls.
- Added optional LangChain `with_structured_output` chain builders for
  canonicalization and verifier calls. Instructor was removed from tracked
  optional dependencies because it is not used by the current implementation.
- Implemented the Phase 8 legal-intent equivalence diagnostic layer as an
  offline artifact workflow: pair benchmark build, legal-intent candidate
  import, pair-decision import, static pair-review HTML export, human label
  import, and equivalence evaluation reports. Outputs remain review evidence
  under `data/evaluation/tg_qa_legal_intent_equivalence/`.
- Added Phase 8 decision producers for method comparison: a cosine+recos
  similarity baseline, a deterministic legal-slot comparator over imported
  legal-intent candidates, and an operator-managed structured-output LLM pair
  judge runner using `tg_legal_intent_pair_judge_v1`.
- Added a bounded schema-guided legal-intent candidate extractor using
  `tg_legal_intent_extractor_v1_positive`. Pair-benchmark scoping limits live
  extraction to unique evidence referenced by reviewed pairs, while source
  identity fields remain controlled by canonicalization evidence.
- Evaluated extracted slots on the reviewed 23-pair benchmark. The
  deterministic slot comparator classified every pair as
  `same_topic_different_issue`, proving that free-form normalized slot strings
  are too sensitive to synonyms for a standalone positive-equivalence
  decision. Passing the candidates to the Qwen 3.7 pair judge changed exactly
  one verdict: it corrected the material distinction between `leave and
  re-enter` and `re-enter only`. Question-reuse safety agreement improved from
  21/23 to 22/23 and false-duplicate risks fell from 2 to 1, at 15.3% more
  judge tokens. Use extracted slots as a confirmation gate for proposed
  equivalence or answer sharing, not as a mass standalone comparator.
- Added a private artifact snapshot manifest that records stable hashes, byte
  counts, line counts, and privacy classification without copying dataset rows.
- Added a corpus-bounded explicit-reference benchmark over canonical questions.
  It reuses the existing legal-reference parser, structural preview builder,
  and exact-reference resolver. It measures mechanical resolution only and
  explicitly leaves legal-reference correctness unreviewed.
- Strengthened `.gitignore` with a complete `data/evaluation/` boundary so new
  private formats cannot bypass extension-specific rules.
- Frozen private `last_2000_v1` snapshot:
  `private-artifact-snapshot:67170d3d81914e18ea6c`, containing four core
  artifacts and 985 dataset rows.
- Ran the three-law explicit-reference benchmark against preview
  `preview:060fb3c068c3e78b`: 99 query-explicit cases, 98 `AufenthG`, one
  `AsylG`, zero `BeschV`, and 99 mechanically resolved targets. The single
  `AsylG` case demonstrates why mechanical resolution must not be interpreted
  as legal-reference correctness.
- Added the file-based corpus-bounded semantic retrieval diagnostic using the
  existing `Query: ` / `Document: ` contract and source-fragment body text.
  The GTX 1060 run completed all 455 vectors with HTTP batch size 16; batch
  size 88 caused 264 client timeouts even though the server could process the
  individual records.
- Ran the semantic diagnostic over 99 query-explicit silver cases and 356
  sections: Recall@1 `0.010101`, Recall@5 `0.040404`, Recall@10 `0.060606`,
  MRR `0.031257`, and nDCG@10 `0.029340`. These values must not be interpreted
  as general semantic-retrieval quality: 92 of 99 silver targets cite
  `§24 AufenthG`, often as status context rather than the section that answers
  the question. The result establishes that exact reference resolution must
  precede semantic retrieval and that query-explicit references are unsuitable
  as unreviewed gold relevance labels.
- Added a bounded human retrieval-relevance review contour: deterministic
  diverse sampling, static HTML review, validated label import, and reviewed
  positive-label metrics with a separate bounded-candidate failure rate.
- Generated a private 30-card `last_2000_v1` relevance-review batch over
  semantic top-10 candidates plus query-explicit targets. The sample represents
  all eight query-explicit target sections present in the 99 semantic cases;
  human review remains pending.
- The first relevance-review card exposed one legacy `v1` canonicalization
  error: a weak `law_code_candidates=["AsylG"]` hint combined with an informal
  "24 paragraph" source mention and produced the false citation `§24 AsylG`.
  A targeted Qwen 3.6 smoke with `tg_question_canonicalizer_v22_positive`
  correctly emitted `§24 AufenthG` and passed the new cumulative regression
  invariant. The corrected result remains private correction evidence until a
  new dataset snapshot and its dependent retrieval vectors are rebuilt.
- Relevance-review cards now show the private redacted source question when the
  dataset is supplied and warn when the query-explicit target law code was not
  named in the source. The warning requires review and is not an automatic
  rejection because inferred law codes may be correct.
- Relevance review now permits the reviewer to add a known relevant section
  from the selected corpus when it was absent from shown candidates. Such
  reviewer-added sections remain auditable and count as retrieval misses
  without an invented rank.
- Separated initial retrieval evaluation from canonicalization debugging.
  The query-explicit private relevance review is now explicitly treated as a
  later stress/backlog diagnostic. A separate curated initial benchmark must
  use coherent, moderate, independently checked single-issue questions.
- Added the publication-safe clean curated retrieval baseline with 24
  single-issue questions, balanced across `AufenthG`, `AsylG`, and `BeschV`.
  Questions contain no explicit section numbers and use independently checked
  `curated_checked` primary targets.
- Initial clean Jina result: Recall@1 `0.666667`, Recall@5 `0.875`, Recall@10
  `0.916667`, and MRR `0.745068`. The clean review HTML is generated under the
  ignored `data/evaluation/tg_qa_retrieval_benchmark/clean_curated_v1_*`
  artifact family.
- Generalized semantic benchmark metrics and review-card labels so curated
  checked targets are not misreported as query-explicit silver references.
- Added the independent `rerun_after_corpus_expansion` relevance-review routing
  marker, including `VwVfG` UI shortcut, generic law-code input, JSONL
  export/import preservation, summary counts, and a `corpus rerun` filter.
- Added `VwVfG` to the active legal corpus through the guarded new-law
  workflow. The offline four-law preflight parsed 477 sections and 1,922
  relationship references; all five incoming references from existing laws to
  `VwVfG` resolved. The live load completed with 1,796 resolved relationship
  edges and no reported graph-write failures.
- Added stage progress reporting for relationship refresh and graph embedding
  writes. Progress is written to stderr with counts, rate, and ETA, while final
  command reports remain JSON on stdout. Non-interactive logs emit bounded
  ten-percent milestones instead of one line per record.
- Fixed graph embedding writes so `SourceFragment` records use their own
  `source_fragment_id` instead of the parent `source_document_id`. Graph writes
  now fail when an embedding record does not match exactly one graph node.
  Re-running the VwVfG embedding stage produced 122 verified embeddings: one
  source document plus 121 source fragments.
- Completed human relevance review of all 24 clean curated questions. The
  final reviewed metrics are Hit@1 `0.750000`, Hit@5 `0.916667`, Hit@10
  `1.000000`, Recall@10 `0.944444`, Recall@40 `1.000000`, and MRR `0.817526`.
  All 24 labels are valid and no `rerun_after_corpus_expansion` marker remains.
- The four-law rerun for
  `tg-qa-clean-retrieval-case:asylg-hearing-assistant` retrieves `AsylG §25`
  at rank 1 and `VwVfG §14` at rank 34. Typed traversal from `AsylG §25`
  resolves the direct `DEFINES` edge to `VwVfG §14`, demonstrating that
  semantic retrieval should identify the primary section and bounded
  structural traversal should add dependent legal support.

## Verification

- `python -m compileall src tests`:
  passed.
- `python -m pytest tests/unit/test_tg_question_canonicalization.py tests/smoke/test_cli_offline.py`:
  44 passed.
- After adding the bounded legal-intent extractor:
  `python -m pytest`: 169 passed, 11 skipped; canonicalization boundary check
  passed with no failed source checks or missing ignore patterns.
- After adding private snapshots and the corpus-bounded explicit-reference
  benchmark: `python -m pytest -q`: 172 passed, 11 skipped; compileall,
  canonicalization boundary check, and `git diff --check` passed.
- After adding the corpus-bounded semantic retrieval diagnostic:
  `python -m pytest -q`: 174 passed, 11 skipped; compileall,
  canonicalization boundary check, `git diff --check`, and private artifact
  ignore checks passed.
- After adding the bounded human retrieval-relevance diagnostic:
  `python -m pytest -q`: 176 passed, 11 skipped; both 006 and 007 boundary
  checks, compileall, `git diff --check`, and private artifact ignore checks
  passed.
- After separating the clean initial benchmark from real-record stress/backlog
  review and allowing reviewer-added omitted sections:
  `python -m pytest -q`: 178 passed, 11 skipped; both 006 and 007 boundary
  checks, compileall, `git diff --check`, and private artifact ignore checks
  passed.
- After adding the clean curated retrieval baseline and target-evidence metric
  scopes: `python -m pytest -q`: 180 passed, 11 skipped; both 006 and 007
  boundary checks, generated review JavaScript syntax check, compileall, and
  `git diff --check` passed.
- After adding `rerun_after_corpus_expansion`: `python -m pytest -q`: 181
  passed, 11 skipped; existing four-label export imported with 4/4 completed;
  both boundary checks, generated review JavaScript syntax check, compileall,
  and `git diff --check` passed.
- After adding the guarded VwVfG corpus-expansion workflow, progress reporting,
  bounded graph embeddings, and exact graph-write matching:
  `tests/unit` passed with 178 tests and `tests/smoke` passed with 17 tests;
  compileall, shell syntax checks, and `git diff --check` passed.
- Live VwVfG verification after correcting embedding writes reported one
  source document, 121 source fragments, 121 legal sections, 118 legal
  references, 122 embeddings, and no errors or warnings.
- The final clean curated relevance export imported with 24/24 completed
  labels and zero pending corpus-expansion reruns.
- Rebuilt the private real-record stress review against the active four-law
  corpus (`AufenthG`, `AsylG`, `BeschV`, `VwVfG`) by reusing 576/576 compatible
  vectors with zero missing or duplicate embedding item IDs. The resulting
  bounded review contains 30 cards over 99 source cases.
- Added an offline deterministic retrieval-mechanism report over completed
  human relevance labels. On the reviewed clean 24-case baseline it found six
  cases with first relevant evidence below top-1, two below top-5, one wrong-law
  top-1, and seven cases without any diagnostic signal. Multi-section and
  multi-law support remain separate complexity signals rather than retrieval
  failures.
- After the four-law stress-review rebuild and retrieval-mechanism report:
  `python -m pytest -q` passed with 197 tests and 11 skipped; both 006 and 007
  boundary checks, compileall, and `git diff --check` passed.
- The four-law real-record stress review was completed with
  `tg_007_retrieval_relevance_review_labels4.jsonl`. Import validation
  completed 30/30 labels with zero failures: 28 reviewed records and 2 skipped
  records. The reviewed positive-label report evaluated 18 records with
  Hit@1 `0.388889`, Hit@5 `0.611111`, Hit@10 `0.777778`,
  Recall@1 `0.324074`, Recall@5 `0.564815`, Recall@10 `0.759259`, and
  MRR `0.491425`.
- The stress mechanism report over the same labels found 21 records with at
  least one retrieval-failure signal. The main signals were 11 records with no
  relevant candidate shown, 10 where relevant evidence appeared only below
  top-1, 6 where it appeared only below top-5, and 1 reviewer-added relevant
  section absent from the recorded ranking. Ten records require corpus
  expansion before a fair rerun; the normalized missing-law markers are
  `AsylbLG`, `AufenthV`, `BGB`, `FeV`, `SGB_5`, and `SGB_12`.
- A general retrieval method change must now report both the clean 24-case
  reviewed baseline and the four-law real-record stress review before it is
  retained. Single-case fixes may still be explored, but they are not accepted
  as general method evidence without this cumulative comparison.
- Added the first route-ambiguity benchmark contract and a tracked 12-record
  publication-safe fixture. The fixture contains 5 section-24 temporary
  protection records, 5 AsylG asylum-procedure records, and 2 unresolved
  route-clarification records. It includes paired or near-identical Russian
  surface wording where material context changes the expected route, including
  Ukrainian wartime displacement, individual persecution, Ukrainian residence
  history, and third-country nationals with temporary Ukrainian residence.
- Added a dedicated route-ambiguity retrieval runner. The runner emits a
  four-law embedding batch, vectorizes only resolvable route queries, reuses
  existing four-law document vectors, and refuses to finish when query
  vectorization fails. The current environment did not have a live embedding
  endpoint on `127.0.0.1:18080`, so the route semantic baseline remains pending
  until the local endpoint is started.
- After adding the route-ambiguity contract, fixture, and runner:
  `python -m pytest -q` passed with 198 tests and 11 skipped; both 006 and 007
  boundary checks and `git diff --check` passed.
- Completed the current unrestricted four-law route-ambiguity baseline after
  the local embedding endpoint was available. The generic semantic report over
  10 resolvable route records produced Recall@1 `0.400000`, Recall@5
  `0.500000`, Recall@10 `0.600000`, and MRR `0.466774`; 2 unresolved route
  records were excluded from ordinary Recall@k by contract. The route-specific
  report found expected-route hit `0.900000` at k=1 and `1.000000` at k=5/k=10,
  one top-1 wrong-route case, wrong-route-only rate `0.000000` at all measured
  k values, and both `AufenthG`/`AsylG` recalled for `0.750000` of dual-route
  cases at k=5 and `1.000000` at k=10.
- After adding and running the route-ambiguity report:
  `python -m pytest -q` passed with 199 tests and 11 skipped; both 006 and 007
  boundary checks and `git diff --check` passed.
- `python -m pytest`:
  148 passed, 11 skipped.
- `PYTHONPATH=src python -m app evaluation tg-qa-canonical-boundary-check`:
  passed with no failed source checks and no missing ignore patterns.
- `git diff --check`:
  passed.
- `python -m pytest tests/unit/test_tg_question_canonicalization.py tests/smoke/test_cli_offline.py -k "canonicalization"`:
  8 passed, 12 deselected after the Pydantic/LangChain refactor.
- Local LangChain construction smoke:
  `ChatOpenAI(...).with_structured_output(CanonicalizationResultPayload)` and
  `ChatAnthropic(...).with_structured_output(VerifierVerdictPayload)` both
  built `RunnableSequence` chains without a network call.
- `python -m pytest tests/unit/test_tg_question_canonicalization.py -k "legal_intent or langchain_review_prompt"`:
  7 passed, 22 deselected.
- `python -m pytest tests/smoke/test_cli_offline.py -k "legal_intent_pair_review"`:
  1 passed, 14 deselected.
- `python -m pytest tests/unit/test_tg_question_canonicalization.py tests/smoke/test_cli_offline.py`:
  44 passed.

## Skipped Live-Service Tests

The full test run skipped the existing live integration tests because the
default test contour does not opt in to Neo4j, live embedding services, paid
APIs, network services, or remote notebooks.

## Artifact And Privacy Checks

- Generated 007 artifact directories under `data/evaluation/` are covered by
  `.gitignore`.
- No generated vectors, LLM outputs, review sheets, raw Telegram exports,
  tunnel URLs, API keys, or local environment values were staged.
- The 007 privacy guard rejects raw Telegram input path references, endpoint
  URLs, API-key-like values, and `.env`-style values in emitted artifacts.

## Known Limitations

- Canonicalization output and issue clusters are review evidence only; they do
  not approve legal issues or create trusted answers.
- Deterministic issue clustering groups by canonical issue-frame slug and flags
  low-confidence or broad cases instead of relying on raw question similarity.
- Final evaluation dataset export accepts only eligible candidates with
  reviewed reference answer material.
- Legal-intent equivalence reports evaluate pair decisions against reviewed
  labels. They do not approve automatic duplicate removal or answer reuse.
- The clean curated reviewed baseline is small and intentionally moderate. It
  does not replace the pending real-record stress/backlog review or the route
  ambiguity and temporal-relevance diagnostics.
- After the six-law corpus import, relationship preflight exposed false
  `missing_target_in_corpus` noise from external law references whose full-name
  aliases were not recognized. Added aliases for common external laws such as
  `ZPO`, `StGB`, `BGB`, `VwGO`, and selected `SGB_*` books. Offline six-law
  preflight shifted counts from `unresolved=170/out_of_scope=2` to
  `unresolved=79/out_of_scope=152`; the follow-up six-law relationship refresh
  produced the same live counts.
- Clean curated and route ambiguity retrieval runners now support explicit
  `LAW_CODES` and `full-fresh` vectorization so expanded-corpus diagnostics do
  not reuse stale four-law document vectors.
- The clean six-law retrieval baseline completed with 648/648 vectors and zero
  failures. On the same 24 curated records, Recall@1 shifted from `0.666667`
  to `0.625`, Recall@5 stayed `0.875`, Recall@10 stayed `0.916667`, and MRR
  shifted from `0.745068` to `0.715972`.
- The six-law route-ambiguity baseline completed with 10/10 query vectors and
  zero failures. Expected-route hit@1 shifted from `0.900000` to `0.600000`,
  while hit@5 and hit@10 stayed `1.000000`; top-1 wrong-route cases increased
  from 1 to 4 because `AufenthV` competes with section-24 `AufenthG` records.
  This confirms that unrestricted semantic top-1 must remain diagnostic only,
  and candidate-generation or route-hint changes require cumulative clean and
  route evidence before retention.
