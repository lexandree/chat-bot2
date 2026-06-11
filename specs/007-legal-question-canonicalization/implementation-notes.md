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
