"""Load versioned LLM prompt profiles for evaluation workflows."""

from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Any, Mapping


PROMPT_PROFILE_DIR = Path(__file__).with_name("prompt_profiles")
CANONICALIZATION_PROMPT_VERSION = os.environ.get(
    "TG_QUESTION_CANONICALIZATION_PROMPT_VERSION",
    "tg_question_canonicalizer_v22_positive",
) or "tg_question_canonicalizer_v22_positive"
CANONICALIZATION_PROMPT_PROFILE_PATH = PROMPT_PROFILE_DIR / f"{CANONICALIZATION_PROMPT_VERSION}.json"
TG_QA_CANDIDATE_PROMPT_VERSION = os.environ.get(
    "TG_QA_CANDIDATE_PROMPT_VERSION",
    "tg_qa_candidate_classifier_v4_1",
) or "tg_qa_candidate_classifier_v4_1"
TG_QA_CLUSTER_PROMPT_VERSION = os.environ.get(
    "TG_QA_CLUSTER_PROMPT_VERSION",
    "tg_qa_cluster_reviewer_v4_1",
) or "tg_qa_cluster_reviewer_v4_1"
TG_QA_CLUSTER_COMPACT_PROMPT_VERSION = os.environ.get(
    "TG_QA_CLUSTER_COMPACT_PROMPT_VERSION",
    "tg_qa_cluster_reviewer_compact_v4_1",
) or "tg_qa_cluster_reviewer_compact_v4_1"
CANONICALIZATION_VERIFIER_PROMPT_VERSION = os.environ.get(
    "TG_QUESTION_CANONICALIZATION_VERIFIER_PROMPT_VERSION",
    "tg_question_canonicalization_verifier_v9_positive",
) or "tg_question_canonicalization_verifier_v9_positive"
CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION = os.environ.get(
    "TG_QUESTION_CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION",
    "tg_question_canonicalization_adjudicator_v10_positive",
) or "tg_question_canonicalization_adjudicator_v10_positive"
CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_VERSION = os.environ.get(
    "TG_QUESTION_CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_VERSION",
    "tg_question_canonicalization_atomic_verifier_v6",
) or "tg_question_canonicalization_atomic_verifier_v6"
CANONICALIZATION_ATOMIC_CRITIC_PROMPT_VERSION = os.environ.get(
    "TG_QUESTION_CANONICALIZATION_ATOMIC_CRITIC_PROMPT_VERSION",
    "tg_question_canonicalization_atomic_critic_v6",
) or "tg_question_canonicalization_atomic_critic_v6"
CANONICALIZATION_ATOMIC_REPAIR_PROMPT_VERSION = os.environ.get(
    "TG_QUESTION_CANONICALIZATION_ATOMIC_REPAIR_PROMPT_VERSION",
    "tg_question_canonicalization_atomic_repair_v3",
) or "tg_question_canonicalization_atomic_repair_v3"
CANONICALIZATION_DEEPSEEK_ADJUDICATOR_PROMPT_VERSION = CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION
LEGAL_INTENT_PAIR_JUDGE_PROMPT_VERSION = os.environ.get(
    "TG_LEGAL_INTENT_PAIR_JUDGE_PROMPT_VERSION",
    "tg_legal_intent_pair_judge_v1",
) or "tg_legal_intent_pair_judge_v1"
LEGAL_INTENT_EXTRACTOR_PROMPT_VERSION = os.environ.get(
    "TG_LEGAL_INTENT_EXTRACTOR_PROMPT_VERSION",
    "tg_legal_intent_extractor_v1_positive",
) or "tg_legal_intent_extractor_v1_positive"


@lru_cache(maxsize=None)
def _load_prompt_profile(path: Path) -> dict[str, Any]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict):
        raise ValueError(f"Prompt profile must be a JSON object: {path}")
    return profile


def _materialize_prompt_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    materialized = dict(profile)
    instruction = str(
        materialized.get("system_instruction_override", materialized["system_instruction"])
    ).strip()
    if "few_shot_examples_override" in materialized:
        examples_override = materialized["few_shot_examples_override"]
        if not isinstance(examples_override, list):
            raise ValueError("few_shot_examples_override must be a list")
        materialized["few_shot_examples"] = examples_override
    replacements = materialized.get("system_instruction_replacements", [])
    if not isinstance(replacements, list):
        raise ValueError("system_instruction_replacements must be a list")
    for replacement in replacements:
        if not isinstance(replacement, Mapping):
            raise ValueError("system_instruction_replacements entries must be objects")
        old = str(replacement.get("old", ""))
        new = str(replacement.get("new", ""))
        if not old or instruction.count(old) != 1:
            raise ValueError("system_instruction replacement must match exactly once")
        instruction = instruction.replace(old, new)
    appendix = str(materialized.get("system_instruction_appendix", "")).strip()
    if appendix:
        instruction = f"{instruction.rstrip()} {appendix}"
    materialized["system_instruction"] = instruction
    return materialized


def load_canonicalization_prompt_profile_data() -> dict[str, Any]:
    """Return the materialized JSON-backed canonicalization prompt profile."""

    return _materialize_prompt_profile(_load_prompt_profile(CANONICALIZATION_PROMPT_PROFILE_PATH))


def load_prompt_profile_data(prompt_version: str) -> dict[str, Any]:
    """Return materialized JSON-backed data for any versioned prompt."""

    return _materialize_prompt_profile(
        _load_prompt_profile(PROMPT_PROFILE_DIR / f"{prompt_version}.json")
    )


_CANONICALIZATION_PROMPT_PROFILE = load_canonicalization_prompt_profile_data()
_TG_QA_CANDIDATE_PROMPT_PROFILE = load_prompt_profile_data(TG_QA_CANDIDATE_PROMPT_VERSION)
_TG_QA_CLUSTER_PROMPT_PROFILE = load_prompt_profile_data(TG_QA_CLUSTER_PROMPT_VERSION)
_TG_QA_CLUSTER_COMPACT_PROMPT_PROFILE = load_prompt_profile_data(TG_QA_CLUSTER_COMPACT_PROMPT_VERSION)
_CANONICALIZATION_VERIFIER_PROMPT_PROFILE = load_prompt_profile_data(CANONICALIZATION_VERIFIER_PROMPT_VERSION)
_CANONICALIZATION_ADJUDICATOR_PROMPT_PROFILE = load_prompt_profile_data(CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION)
_CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_PROFILE = load_prompt_profile_data(
    CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_VERSION
)
_CANONICALIZATION_ATOMIC_CRITIC_PROMPT_PROFILE = load_prompt_profile_data(
    CANONICALIZATION_ATOMIC_CRITIC_PROMPT_VERSION
)
_CANONICALIZATION_ATOMIC_REPAIR_PROMPT_PROFILE = load_prompt_profile_data(
    CANONICALIZATION_ATOMIC_REPAIR_PROMPT_VERSION
)
_LEGAL_INTENT_PAIR_JUDGE_PROMPT_PROFILE = load_prompt_profile_data(LEGAL_INTENT_PAIR_JUDGE_PROMPT_VERSION)
_LEGAL_INTENT_EXTRACTOR_PROMPT_PROFILE = load_prompt_profile_data(LEGAL_INTENT_EXTRACTOR_PROMPT_VERSION)

CANONICALIZATION_PROMPT_EXAMPLE_SET_ID = str(_CANONICALIZATION_PROMPT_PROFILE["prompt_example_set_id"])
EXPECTED_CANONICALIZATION_SCHEMA = dict(_CANONICALIZATION_PROMPT_PROFILE["expected_output_schema"])
CANONICALIZATION_SYSTEM_INSTRUCTION = str(_CANONICALIZATION_PROMPT_PROFILE["system_instruction"])
CANONICALIZATION_PROMPT_EXAMPLES = tuple(_CANONICALIZATION_PROMPT_PROFILE["few_shot_examples"])
TG_QA_CANDIDATE_PROMPT_PROFILE = dict(_TG_QA_CANDIDATE_PROMPT_PROFILE)
TG_QA_CLUSTER_PROMPT_PROFILE = dict(_TG_QA_CLUSTER_PROMPT_PROFILE)
TG_QA_CLUSTER_COMPACT_PROMPT_PROFILE = dict(_TG_QA_CLUSTER_COMPACT_PROMPT_PROFILE)
CANONICALIZATION_VERIFIER_PROMPT_PROFILE = dict(_CANONICALIZATION_VERIFIER_PROMPT_PROFILE)
CANONICALIZATION_ADJUDICATOR_PROMPT_PROFILE = dict(_CANONICALIZATION_ADJUDICATOR_PROMPT_PROFILE)
CANONICALIZATION_DEEPSEEK_ADJUDICATOR_PROMPT_PROFILE = dict(_CANONICALIZATION_ADJUDICATOR_PROMPT_PROFILE)
CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_PROFILE = dict(
    _CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_PROFILE
)
CANONICALIZATION_ATOMIC_CRITIC_PROMPT_PROFILE = dict(
    _CANONICALIZATION_ATOMIC_CRITIC_PROMPT_PROFILE
)
CANONICALIZATION_ATOMIC_REPAIR_PROMPT_PROFILE = dict(
    _CANONICALIZATION_ATOMIC_REPAIR_PROMPT_PROFILE
)
LEGAL_INTENT_PAIR_JUDGE_PROMPT_PROFILE = dict(_LEGAL_INTENT_PAIR_JUDGE_PROMPT_PROFILE)
LEGAL_INTENT_EXTRACTOR_PROMPT_PROFILE = dict(_LEGAL_INTENT_EXTRACTOR_PROMPT_PROFILE)
