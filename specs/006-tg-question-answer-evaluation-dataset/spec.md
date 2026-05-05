# Feature 006: Telegram Question/Answer Evaluation Dataset

## Purpose

Build a reproducible, reviewable question/answer candidate dataset from local
Telegram exports so later retrieval and answer workflows can be measured against
real user questions.

## Scope

Inputs:

- `data/tg/**/result.json` Telegram export files
- optional Telegram wiki bot catalog seed

Outputs:

- redacted Q/A candidate JSONL
- extraction summary JSON
- optional LLM batch JSONL for external cheap/free model processing

## Boundaries

- Raw Telegram exports remain private local inputs and must not be committed.
- Extracted Telegram answers are evaluation material, not legal truth.
- LLM output, when used later, is candidate metadata only.
- No graph mutation.
- No chatbot answer generation.
- No default test may require network, paid APIs, LangChain, LangGraph, or a
  live LLM runtime.

## Minimal Acceptance

- Parse Telegram `result.json` exports deterministically.
- Normalize text from Telegram string/list text shapes.
- Redact obvious PII from emitted text.
- Detect question candidates with deterministic heuristics.
- Use wiki bot mentions as weak prioritization signals.
- Collect direct reply answers as candidate answer evidence.
- Label current-theme relevance for migration/asylum/employment topics.
- Emit JSONL records with source message ids and review status.
- Emit optional LLM batch JSONL that can be processed externally.
- Pass offline unit/smoke tests on a minimal sample export.
