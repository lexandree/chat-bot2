# Adoption Notes

## Do Not Import The Snapshot Wholesale

`source_snapshot/` is a curated code reference. It is intentionally not a
drop-in package for the new project.

Adopt files by concern:

1. settings and typed configuration
2. real Neo4j client and schema bootstrap
3. legal XML import
4. structural legal graph builder
5. embedding profile and local-only graph-write embedding path
6. exact reference resolver and bounded traversal
7. review-gated semantic candidates
8. validation fixtures and metrics
9. operator-managed bulk runner contracts

## Required Cleanups Before Adoption

- Replace old package imports with the new package layout.
- Replace the old recording-only Neo4j facade with a real driver-backed client.
- Split validation helpers away from old chatbot flow.
- Recreate tests under the new `tests/unit`, `tests/integration`, and
  `tests/smoke` layout.
- Keep live Neo4j and live Jina checks out of default unit tests.
- Treat notebooks as operator surfaces. Move reusable logic into project modules
  before depending on it from tests or production commands.
- Keep private `.env` snapshots and notebook artifacts out of any public
  repository or public Kaggle dataset unless they are explicitly sanitized.

## First Implementation Order

1. Create project skeleton from `project_seed/`.
2. Implement settings and config validation.
3. Implement real Neo4j client.
4. Port schema bootstrap and graph types.
5. Port legal XML import and add fixture-local tests.
6. Port structural graph build and traversal.
7. Port embedding profile and local-only embedding integration.
8. Add load, verify, delete commands.
9. Add semantic candidate extraction only after structural validation passes.
10. Add bulk-run artifact and checkpoint contracts before scaling extraction.
11. Evaluate GraphRAG inference frameworks only after the database foundation is
    stable.
