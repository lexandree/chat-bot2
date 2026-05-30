"""Load versioned LLM prompt profiles for evaluation workflows."""

from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Any


PROMPT_PROFILE_DIR = Path(__file__).with_name("prompt_profiles")
CANONICALIZATION_PROMPT_VERSION = os.environ.get(
    "TG_QUESTION_CANONICALIZATION_PROMPT_VERSION",
    "tg_question_canonicalizer_v6",
) or "tg_question_canonicalizer_v6"
CANONICALIZATION_PROMPT_PROFILE_PATH = PROMPT_PROFILE_DIR / f"{CANONICALIZATION_PROMPT_VERSION}.json"
TG_QA_CANDIDATE_PROMPT_VERSION = "tg_qa_candidate_classifier_v4_1"
TG_QA_CLUSTER_PROMPT_VERSION = "tg_qa_cluster_reviewer_v4_1"
TG_QA_CLUSTER_COMPACT_PROMPT_VERSION = "tg_qa_cluster_reviewer_compact_v4_1"
CANONICALIZATION_VERIFIER_PROMPT_VERSION = "tg_question_canonicalization_verifier_v7"
CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION = "tg_question_canonicalization_adjudicator_v7"
CANONICALIZATION_DEEPSEEK_ADJUDICATOR_PROMPT_VERSION = CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION


@lru_cache(maxsize=None)
def _load_prompt_profile(path: Path) -> dict[str, Any]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict):
        raise ValueError(f"Prompt profile must be a JSON object: {path}")
    return profile


def load_canonicalization_prompt_profile_data() -> dict[str, Any]:
    """Return the raw JSON-backed prompt profile data for canonicalization."""

    return dict(_load_prompt_profile(CANONICALIZATION_PROMPT_PROFILE_PATH))


def load_prompt_profile_data(prompt_version: str) -> dict[str, Any]:
    """Return the raw JSON-backed prompt profile data for any versioned prompt."""

    return dict(_load_prompt_profile(PROMPT_PROFILE_DIR / f"{prompt_version}.json"))


_CANONICALIZATION_PROMPT_PROFILE = load_canonicalization_prompt_profile_data()
_TG_QA_CANDIDATE_PROMPT_PROFILE = load_prompt_profile_data(TG_QA_CANDIDATE_PROMPT_VERSION)
_TG_QA_CLUSTER_PROMPT_PROFILE = load_prompt_profile_data(TG_QA_CLUSTER_PROMPT_VERSION)
_TG_QA_CLUSTER_COMPACT_PROMPT_PROFILE = load_prompt_profile_data(TG_QA_CLUSTER_COMPACT_PROMPT_VERSION)
_CANONICALIZATION_VERIFIER_PROMPT_PROFILE = load_prompt_profile_data(CANONICALIZATION_VERIFIER_PROMPT_VERSION)
_CANONICALIZATION_ADJUDICATOR_PROMPT_PROFILE = load_prompt_profile_data(CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION)

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
