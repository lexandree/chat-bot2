# Kaggle workflow playbook

## Purpose

This file records the intended division of responsibilities between:

- public Kaggle notebooks and datasets
- private Kaggle artifacts used by the project
- GitHub project code and specifications

The goal is to keep Kaggle useful as a public runtime and discovery surface
without polluting public assets with project-specific internals.

## Three-contour model

### 1. Kaggle public

Use public Kaggle assets for:

- public runtime notebooks
- public launch recipes
- public model or server demonstrations
- public benchmark and profiling outputs from those notebooks
- public packaged artifacts that are useful to other users

Examples:

- `Gemma 4 + llama-server on Kaggle`
- public `llama-server` build or launch notebooks
- public run outputs that demonstrate performance, context limits, or server behavior

Public Kaggle assets are the preferred home for:

- discoverability
- reuse by other Kaggle users
- ranking and community visibility
- demonstration-oriented reproducibility

### 2. Kaggle private artifacts

Use private Kaggle datasets or notebook outputs only for project-specific or
operationally sensitive assets.

Examples:

- project-side modules that run on Kaggle
- private import previews
- private validation fixtures or internal corpora snapshots
- `004` project handoff artifacts
- internal run manifests and profile reports tied to project logic

Private Kaggle artifacts should not become a dumping ground for all runs.
Use them when the artifact is:

- specific to the chatbot project
- not suitable for public reuse
- part of internal iteration, integration, or evaluation

### 3. GitHub project integration

Use GitHub for:

- source code
- specifications and planning artifacts
- tests
- reusable modules extracted from Kaggle experimentation
- playbooks and operational documentation
- project-specific notebook adapters or wrappers

GitHub is not required to be the canonical home of public Kaggle notebooks.
Those notebooks may be Kaggle-first assets.

## Simple placement rule

Ask one question first:

- Is this asset mainly about running or demonstrating a model on Kaggle for any user?

If yes:

- prefer **public Kaggle**

If not, ask:

- Is this asset specific to the chatbot project, internal evaluation, or private operational workflow?

If yes:

- prefer **private Kaggle artifacts** or **GitHub project code**, depending on whether it is a runtime artifact or project source

## Recommended artifact classes

### Public Kaggle

- public runtime notebooks
- public build notebooks
- public model launch recipes
- public benchmark and profiling outputs
- public datasets containing generally useful runtime bundles

### Private Kaggle

- project-side runtime datasets
- private corpora and previews
- internal validation artifacts
- run manifests for project-specific evaluation
- profile reports tied to project workflows

### GitHub

- extracted reusable Python modules
- project-side orchestration logic
- `004` adapters and validation entrypoints
- schema and contract files
- operational notes and playbooks

## Results policy

Results from public Kaggle notebooks should usually remain public.

That includes:

- successful launch reports
- profiling summaries
- benchmark snapshots
- public demo outputs

Keep them public unless they expose:

- project-specific private data
- internal-only corpora
- credentials or host details
- non-public evaluation workflows

## Notebook discipline

For multi-purpose Kaggle notebooks:

1. Use one explicit session goal per run.
2. Guard goal-specific cells.
3. Keep generic utilities separate from project-specific handoff logic.
4. Export structured artifacts at the end of useful runs.
5. If a previously generic cell becomes specialized, move it into a dedicated
   section instead of silently broadening its scope.

## Export policy

Useful Kaggle runs should export structured artifacts such as:

- `run_manifest.json`
- `profile_report.json`
- relevant logs

For public notebooks:

- public run outputs may remain public

For project-specific runs:

- export to private Kaggle artifacts or move the results into project-side storage

## Relationship to `004`

For `004` legal extraction:

- public Kaggle notebooks may remain the canonical home for model runtime demonstrations
- private Kaggle artifacts should hold project-specific legal extraction inputs and reports
- GitHub should hold the reusable integration modules that connect those runtime capabilities back into the chatbot project

## Anti-patterns

Avoid these:

- storing all Kaggle experiments privately by default
- making public notebooks depend on project-private datasets without clear reason
- treating GitHub as the only valid home for Kaggle runtime work
- mixing public demo logic and internal project orchestration in one indistinguishable notebook flow
- keeping useful run evidence only in notebook outputs without exporting structured artifacts
