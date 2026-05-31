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

## Verification

- `python -m compileall src tests`:
  passed.
- `python -m pytest tests/unit/test_tg_question_canonicalization.py tests/smoke/test_cli_offline.py`:
  44 passed.
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
