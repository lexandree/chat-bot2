# Bulk Notebook Processing

## Purpose

The notebook work defines an operator-managed bulk execution contour. It is not
the interactive chatbot inference layer.

The useful pattern is:

1. prepare source or preview artifacts outside the notebook
2. attach prebuilt runtime and model artifacts
3. explicitly opt in to execution
4. stage a local server runtime into notebook working storage
5. process a bounded corpus slice
6. export a complete artifact bundle for review and project handoff

## Retained Notebook Ideas

### Guarded Execution

Every notebook runtime path should be disabled by default.

Required guard pattern:

- `RUN_NOTEBOOK = False` or equivalent
- explicit operator inputs near the top
- workflow or process selection before execution
- no accidental build, publish, or paid/runtime-heavy action

### Workflow Process Map

The full runtime notebook uses numbered processes:

- environment checks
- artifact discovery
- model binding
- optional rebuild
- packaging and dataset upload
- isolated runtime sandbox
- health/model/slot checks
- client helpers
- artifact export

This is valuable because notebook sessions are stateful and fragile. Numbered
processes make execution order visible and reduce hidden helper-state mistakes.

### Runtime Artifacts Are Separate From Project Code

The notebooks separate:

- project source code
- prebuilt `llama-server` runtime artifact
- GGUF model artifact
- optional multimodal projection file
- generated run artifacts

The new project should keep this separation. Runtime binaries and model files
should not become normal source-code files.

### GPU And CPU Runtime Profiles Are Distinct

GPU and CPU `llama-server` artifacts should live in separate artifact families.

Do not point a CPU profile at a GPU runtime dataset or reuse a CUDA artifact
slug for CPU execution.

### Staged Runtime And Sandbox

Notebook execution should copy the runtime into `/kaggle/working` or another
working directory before launch.

The source artifact should remain immutable. The running server should be
managed from the staged copy or isolated sandbox.

### PID-File Lifecycle

Server lifecycle should be explicit:

- write a PID file
- write command metadata
- stop only the tracked PID
- avoid broad port-wide kill fallbacks
- record logs in a known file

This makes runtime failure and cleanup auditable.

### Health Checks Before Bulk Work

Before extraction or validation starts, the notebook should check:

- TCP port availability
- `/health`
- model metadata endpoint
- optional slot endpoint
- log tail for load errors
- resource snapshot

Bulk processing should fail before corpus work begins if the runtime is not
ready.

## Legal Extraction Bulk Pattern

The legal extraction notebook contributes a project-facing bulk flow:

1. clone or install the selected project branch
2. stage prebuilt `llama-server`
3. start local OpenAI-compatible server
4. load legal preview corpus
5. limit scope with `MAX_DOCUMENTS` and `LAW_CODES`
6. build a proposition extractor around the active model
7. call the application-level semantic validation cycle
8. export result artifacts

The target system should generalize this into a bulk job runner rather than
keeping it as a one-off notebook-only flow.

## Bulk Job Contract

Every bulk run should record:

- run id
- run name
- runtime contour
- source scope
- input manifest path or dataset id
- validation fixture path
- effective LLM backend
- effective embedding backend
- model id
- prompt or extraction-policy version
- corpus limits such as law codes and max documents
- processed count
- skipped count
- failed count
- elapsed time
- server/runtime parameters

Every item should record:

- source id or fragment id
- item state
- attempt count
- last error
- output reference
- review state where applicable

## Artifact Bundle Contract

A completed useful notebook run should export one coherent artifact directory.

Minimum artifacts:

- `run_manifest.json`
- `profile_report.json`
- extraction or validation result JSON
- server command JSON
- server log

Optional artifacts:

- dataset metadata JSON for private Kaggle artifact publishing
- checkpoint or resume state
- failed item report
- prompt samples with source references

The artifact bundle should be suitable for either download or private Kaggle
dataset versioning.

## Resume And Checkpoint Policy

Notebook sessions can restart or expire. Bulk processing therefore needs
checkpoint support.

Required behavior:

- process items in a stable order
- persist cursor or per-item state regularly
- resume from the last completed item
- never mark a run completed if unprocessed items remain
- export checkpoint state with the artifact bundle

The current snapshots already include state-store ideas. The new project should
make them a first-class bulk runner concern.

## Privacy And Artifact Placement

Runtime demo notebooks and reusable runtime build assets may be public.

Project-specific legal inputs, extraction outputs, validation results, and
environment files should be private unless explicitly sanitized.

Recommended placement:

- public Kaggle: reusable runtime demos and public model runtime examples
- private Kaggle artifacts: project-specific legal extraction inputs and run
  reports
- source repository: reusable modules, schemas, tests, docs, and safe examples

## Relationship To Foundation Stage

Bulk notebook processing comes after the database foundation can load and verify
source data.

It should not block the first foundation milestone, but the foundation should
define the contracts that bulk processing will consume:

- preview corpus format
- legal fragment identifiers
- extraction policy version
- candidate output schema
- validation fixture schema
- review boundary
- runtime metadata fields

## Anti-Patterns

- enabling notebook execution by default
- combining build, publish, extraction, and demo paths without workflow guards
- mutating attached runtime artifacts directly
- hiding runtime command parameters
- exporting scattered files instead of one run artifact bundle
- treating notebook output as trusted graph state without review
- storing project-specific legal artifacts publicly by default
