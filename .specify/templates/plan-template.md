# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]  
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]  
**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]  
**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]  
**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]
**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]  
**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]  
**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]  
**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Database Before Inference**: Plan confirms the feature does not introduce
  chatbot inference, answer synthesis, or demo fallback answers before the
  database and retrieval baseline can be validated independently.
- **Structural Legal Graph**: Plan identifies affected source, legal, reference,
  temporal, provenance, checksum, and traversal contracts, or states why the
  feature does not touch them.
- **Embedding Contract**: Plan preserves `Query: ` and `Document: ` prefix
  semantics, active embedding profile metadata, vector dimensions, normalization
  expectations, and no live embedding dependency in default unit tests.
- **Review Boundary**: Plan keeps LLM-derived outputs untrusted by default and
  records source support, runtime metadata, flags, isolation, and approval state
  before any trusted use.
- **Reproducible Operations**: Plan documents idempotent or explicit write
  semantics, verification evidence, deletion/reindex behavior, and resume or
  artifact requirements for long-running work.
- **Bulk Runtime Control**: Plan keeps notebook and remote-runtime workflows
  operator-managed, disabled by default, artifact-driven, and separate from core
  application architecture.
- **Test Boundaries**: Plan separates unit, integration, and smoke tests; any
  Neo4j, Jina, paid API, filesystem integration, or remote notebook dependency
  is marked and runnable separately.
- **Minimal Trusted Surface**: Plan favors exact legal-reference resolution,
  bounded typed traversal, law and official-guidance corpus slices, and deferred
  abstractions unless evidence justifies broader scope.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# Legal GraphRAG foundation (DEFAULT)
src/
├── app/
├── graph/
├── ingestion/
├── retrieval/
├── enrichment/
├── bulk/
├── review/
└── evaluation/

tests/
├── unit/
├── integration/
├── smoke/
└── fixtures/
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
