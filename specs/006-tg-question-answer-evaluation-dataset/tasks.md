# Tasks: Telegram Q/A Evaluation Dataset

## Current Scope

- [x] Stage 1 deterministic Telegram export parsing
- [x] PII redaction and source metadata retention
- [x] Initial Q/A candidate extraction from direct replies
- [x] Question and answer embedding batch contract
- [x] Known wiki-bot answer source marking
- [x] Admin-triggered wiki-bot answer linking
- [ ] External embedding/clustering stage
- [ ] LLM review stage for uncertain clusters
- [ ] Manual review artifact
- [ ] Final approved evaluation dataset artifact

## Admin-Triggered Bot Answer Linking

- [x] Detect short non-question trigger messages authored by non-bot users.
- [x] Link `question -> trigger reply -> known wiki-bot reply` as
  `answer_link_type=bot_reply_to_trigger` with `link_confidence=high`.
- [x] Link nearby `question ... trigger ... known wiki-bot answer` chains within
  bounded message/time windows as `answer_link_type=bot_after_trigger` with
  `link_confidence=medium`.
- [x] Preserve trigger messages as `trigger_evidence`, not as answer candidates.
- [x] Deduplicate answer candidates by `message_id` while preserving all link
  metadata that explains how the answer was found.
- [x] Emit summary counts for direct answers and trigger-linked answers.
- [ ] Emit orphan trigger/bot chain counts across the whole export.
- [x] Cover direct trigger and nearby trigger cases in offline fixtures.

## Boundaries

- [ ] Do not write graph state.
- [ ] Do not treat Telegram or bot answers as legal truth.
- [ ] Do not require network, paid APIs, LangChain, LangGraph, embeddings, or
  live LLM services in default tests.
