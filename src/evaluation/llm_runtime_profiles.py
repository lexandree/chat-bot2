"""Typed operator LLM runtime profiles for reproducible evaluation runs."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ATOMIC_RUNTIME_STAGES = ("verifier", "critic", "repair")
DEFAULT_ATOMIC_RUNTIME_PROFILE_REGISTRY = (
    Path(__file__).with_name("runtime_profiles")
    / "tg_question_canonicalization_atomic_models_v2.json"
)

ATOMIC_STRUCTURED_OUTPUT_ADAPTER_VERSIONS = {
    "function_calling": "langchain_native_structured_output_v1",
    "json_mode": "langchain_native_structured_output_v1",
    "json_schema": "langchain_native_structured_output_v1",
    "prompt_json": "atomic_prompt_json_strict_v1",
}


class AtomicRuntimeStageOptions(BaseModel):
    """Native request settings for one model and one atomic stage."""

    model_config = ConfigDict(extra="forbid")

    max_tokens: int = Field(gt=0)
    timeout_seconds: int = Field(default=300, gt=0)
    temperature: float | None = None
    request_parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("request_parameters")
    @classmethod
    def _json_request_parameters(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            json.dumps(value, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("runtime request_parameters must be JSON serializable") from exc
        _reject_secret_keys(value)
        return value


class AtomicModelRuntimeProfile(BaseModel):
    """Transport and stage settings for one model deployment."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1)
    provider: Literal["anthropic", "openai"]
    parameter_transport: Literal["anthropic_constructor", "openai_extra_body"]
    endpoint_url: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    reasoning_mode: Literal["enabled", "disabled", "provider_default"] = "provider_default"
    structured_output_method: Literal[
        "function_calling",
        "json_mode",
        "json_schema",
        "prompt_json",
    ]
    qualification_status: Literal[
        "baseline",
        "candidate",
        "conformance_passed",
        "conformance_failed",
        "operationally_unqualified",
        "target_quality_failed",
    ] = "candidate"
    qualification_note: str = ""
    stages: dict[str, AtomicRuntimeStageOptions]
    pricing_snapshot: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _valid_transport_and_stages(self) -> "AtomicModelRuntimeProfile":
        expected_transport = (
            "anthropic_constructor" if self.provider == "anthropic" else "openai_extra_body"
        )
        if self.parameter_transport != expected_transport:
            raise ValueError("runtime profile provider and parameter_transport disagree")
        missing = sorted(set(ATOMIC_RUNTIME_STAGES) - set(self.stages))
        unknown = sorted(set(self.stages) - set(ATOMIC_RUNTIME_STAGES))
        if missing or unknown:
            raise ValueError(f"runtime profile stage mismatch: missing={missing}; unknown={unknown}")
        explicit_modes = {
            _explicit_reasoning_mode(options.request_parameters)
            for options in self.stages.values()
        } - {None}
        contradictory_mode = "enabled" if self.reasoning_mode == "disabled" else "disabled"
        if self.reasoning_mode in {"enabled", "disabled"} and contradictory_mode in explicit_modes:
            raise ValueError(
                "runtime profile reasoning_mode contradicts native request parameters"
            )
        _reject_secret_keys(self.pricing_snapshot)
        return self


class AtomicRuntimeProfileRegistry(BaseModel):
    """Versioned collection of model-native atomic runtime profiles."""

    model_config = ConfigDict(extra="forbid")

    artifact_type: Literal["tg_qa_canonicalization_atomic_runtime_profile_registry"]
    profile_set_version: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    profiles: dict[str, AtomicModelRuntimeProfile]
    trust_boundary: Literal["runtime_profiles_contain_no_secrets_or_private_inputs"]

    @model_validator(mode="after")
    def _matching_profile_ids(self) -> "AtomicRuntimeProfileRegistry":
        mismatches = sorted(
            key for key, profile in self.profiles.items() if key != profile.profile_id
        )
        if mismatches:
            raise ValueError(f"runtime profile key/id mismatch: {mismatches}")
        return self


def load_atomic_runtime_profile_registry(
    path: str | Path | None = None,
) -> tuple[AtomicRuntimeProfileRegistry, str, Path]:
    """Load a tracked, secret-free runtime profile registry and its content hash."""

    registry_path = Path(path or DEFAULT_ATOMIC_RUNTIME_PROFILE_REGISTRY)
    raw = registry_path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    registry = AtomicRuntimeProfileRegistry.model_validate(payload)
    return registry, sha256(raw).hexdigest(), registry_path


def resolve_atomic_runtime_stage(
    registry: AtomicRuntimeProfileRegistry,
    *,
    profile_id: str,
    stage: Literal["verifier", "critic", "repair"],
    registry_hash: str,
) -> dict[str, Any]:
    """Resolve one profile stage into an internal config with stable lineage."""

    try:
        profile = registry.profiles[profile_id]
    except KeyError as exc:
        raise ValueError(f"unknown atomic runtime profile: {profile_id}") from exc
    options = profile.stages[stage]
    request_parameters = dict(options.request_parameters)
    return {
        "profile_set_version": registry.profile_set_version,
        "profile_registry_hash": registry_hash,
        "profile_id": profile.profile_id,
        "stage": stage,
        "provider": profile.provider,
        "parameter_transport": profile.parameter_transport,
        "endpoint_url": profile.endpoint_url,
        "model_id": profile.model_id,
        "reasoning_mode": profile.reasoning_mode,
        "structured_output_method": profile.structured_output_method,
        "structured_output_adapter_version": atomic_structured_output_adapter_version(
            profile.structured_output_method
        ),
        "qualification_status": profile.qualification_status,
        "qualification_note": profile.qualification_note,
        "max_tokens": options.max_tokens,
        "timeout_seconds": options.timeout_seconds,
        "temperature": options.temperature,
        "request_parameters": request_parameters,
        "request_parameters_hash": _stable_json_hash(request_parameters),
        "sdk_max_retries": 0,
        "pricing_snapshot": dict(profile.pricing_snapshot),
    }


def atomic_structured_output_adapter_version(method: str) -> str:
    """Return the runtime-identity version for one structured-output adapter."""

    try:
        return ATOMIC_STRUCTURED_OUTPUT_ADAPTER_VERSIONS[method]
    except KeyError as exc:
        raise ValueError(f"unknown atomic structured-output adapter: {method}") from exc


def _reject_secret_keys(value: Any, *, path: str = "") -> None:
    if not isinstance(value, Mapping):
        if isinstance(value, list):
            for index, item in enumerate(value):
                _reject_secret_keys(item, path=f"{path}[{index}]")
        return
    for key, item in value.items():
        normalized = str(key).lower().replace("-", "_")
        key_path = f"{path}.{key}" if path else str(key)
        if any(
            token in normalized
            for token in ("api_key", "authorization", "secret", "access_token", "bearer_token")
        ):
            raise ValueError(f"runtime profile contains forbidden secret-like key: {key_path}")
        _reject_secret_keys(item, path=key_path)


def _explicit_reasoning_mode(request_parameters: Mapping[str, Any]) -> str | None:
    thinking = request_parameters.get("thinking")
    if isinstance(thinking, Mapping):
        thinking_type = str(thinking.get("type", "")).lower()
        if thinking_type in {"enabled", "disabled"}:
            return thinking_type
    reasoning = request_parameters.get("reasoning")
    if isinstance(reasoning, Mapping) and isinstance(reasoning.get("enabled"), bool):
        return "enabled" if reasoning["enabled"] else "disabled"
    enable_thinking = request_parameters.get("enable_thinking")
    if isinstance(enable_thinking, bool):
        return "enabled" if enable_thinking else "disabled"
    return None


def _stable_json_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()
