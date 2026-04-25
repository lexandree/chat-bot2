# Source Snapshot

This directory contains selected implementation files from the current
repository. They are reference material for a clean new project.

The snapshot intentionally omits the old chatbot flow, `.env`, raw local data,
generated reports, notebooks, and the recording-only Neo4j facade.

Before adopting any file:

- align imports with the new package layout
- add or update tests in the new repository
- replace test doubles with real runtime adapters only at integration
  boundaries
- keep live service dependencies out of unit tests
