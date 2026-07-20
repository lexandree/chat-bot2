# Evaluation Runtime Profiles

Tracked files in this directory describe secret-free, model-native operator
request contours. They are configuration and provenance, not credentials.

`tg_question_canonicalization_atomic_models_v1.json` is the immutable direct-
structured experiment registry. Version v2 retains those profiles and adds
explicit no-reasoning formatter candidates. Each profile binds an atomic model
to its API family, reasoning mode, structured-output method, stage budgets,
native request parameters, and a dated pricing snapshot. Verifier, critic, and
repair may use different semantic and formatter profile ids. Generated runs
retain the registry hash and all effective active component identities.

`tg_question_canonicalization_atomic_qwen_two_step_models_v1.json` is an
isolated qualification registry for Qwen3.7 Plus and Qwen3.6 Plus reasoning
followed by DeepSeek V4 Flash formatting. It exists because the earlier Qwen
profiles deliberately disabled reasoning for direct structured output. It is
not the default registry and does not imply model qualification.

`tg_question_canonicalization_atomic_glm52_qwen37_critic_v1.json` is the
immutable mixed-role registry used to compare a Qwen3.7 Plus adversarial critic
against the GLM-5.2 verifier control. Its bounded positive-target run did not
qualify Qwen as a critic.

`tg_question_canonicalization_atomic_no_reasoning_candidates_v1.json` is the
immutable direct no-reasoning GLM-5.2 candidate registry. It exists to measure
whether a faster first pass can replace semantic reasoning. Guarded canaries
show that it is useful for review triage, but it is not qualified for automatic
acceptance.

`tg_question_canonicalization_atomic_glm52_escalation_v1.json` is the immutable
mixed-mode registry for a no-reasoning GLM-5.2 verifier, a reasoning GLM-5.2
critic, and a DeepSeek V4 Flash formatter. Its mixed-target run demonstrated
that a later reasoning call does not reliably recover every false pass, so the
profile remains diagnostic rather than a production default.

Treat a registry version as immutable after any run records its hash. New
qualification conclusions belong in the dated evaluation report or a new
registry version; editing an existing file would break artifact lineage.

`prompt_json` is the bounded fallback for deployments that reject provider
`response_format` and forced tools. The model receives the same expected schema,
the final text must contain one JSON object, and that object still passes the
same strict Pydantic model with unknown fields forbidden. A stage may also omit
temperature when the provider rejects an explicit value. The effective stage
identity records `structured_output_adapter_version`, so parser changes cannot
silently reuse an older checkpoint.

Missing price fields mean unknown cost, never zero cost. Runtime cost estimates
use observed input/output tokens and the dated uncached rates. Reasoning and
formatter calls are priced separately. A partial mixed-model estimate is
marked incomplete when any component lacks usage or pricing.

Do not add API keys, authorization headers, private inputs, raw prompts, or
generated responses here. A parameter whose transport is not explicitly
supported must fail validation rather than be ignored.
