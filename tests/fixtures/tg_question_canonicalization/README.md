# Telegram Question Canonicalization Fixtures

Fixtures in this directory are redacted, synthetic examples for the 007
canonical legal question workflow. They must not contain raw Telegram exports,
private corpora, endpoint URLs, secrets, or local environment values.

Tests may create temporary JSONL artifacts from these shapes:

- redacted 006-style QA candidates;
- operator canonicalization result lines;
- external vector records for canonical question and issue-frame embeddings;
- cluster review decisions for question-bank and final evaluation promotion.
- Phase 8 legal-intent pair benchmark examples for hard positives, hard
  negatives, and excluded canonical question cases.
