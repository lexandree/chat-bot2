from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, Mapping

import pytest

from evaluation.llm_runtime_profiles import (
    load_atomic_runtime_profile_registry,
    resolve_atomic_runtime_stage,
)
from evaluation.prompts import (
    CANONICALIZATION_ADJUDICATOR_PROMPT_PROFILE,
    CANONICALIZATION_ATOMIC_CRITIC_PROMPT_PROFILE,
    CANONICALIZATION_ATOMIC_REPAIR_PROMPT_PROFILE,
    CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_PROFILE,
    CANONICALIZATION_VERIFIER_PROMPT_PROFILE,
    LEGAL_INTENT_EXTRACTOR_PROMPT_PROFILE,
    LEGAL_INTENT_PAIR_JUDGE_PROMPT_PROFILE,
    load_prompt_profile_data,
)
from evaluation.tg_question_canonicalization import (
    AdjudicationPayload,
    CANONICALIZATION_CONTRACT_VERSION,
    CANONICALIZATION_PROMPT_EXAMPLE_SET_ID,
    CANONICALIZATION_PROMPT_EXAMPLES,
    CanonicalizationResultPayload,
    CONFIDENCE_VALUES,
    DeepSeekAdjudicationPayload,
    EXCLUSION_REASONS,
    VerifierVerdictPayload,
    build_tg_qa_canonical_coverage_report,
    build_tg_qa_canonicalization_adjudication_batch,
    build_tg_qa_canonicalization_retry_batch_from_adjudication,
    build_tg_qa_canonicalization_routing,
    build_tg_qa_canonicalization_snapshot,
    build_tg_qa_issue_final_case_candidates,
    build_tg_qa_legal_intent_equivalence_report,
    build_tg_qa_legal_intent_pair_benchmark,
    build_tg_qa_legal_intent_similarity_baseline,
    build_tg_qa_legal_intent_slot_comparator_decisions,
    build_tg_qa_operator_provider_failure_retry_batch,
    build_tg_qa_question_bank,
    build_tg_qa_reviewed_evaluation_dataset,
    build_tg_qa_temporal_currentness_review_queue,
    build_langchain_canonicalization_chain,
    build_langchain_deepseek_adjudication_chain,
    build_langchain_adjudication_chain,
    build_langchain_canonicalization_atomic_critic_chain,
    build_langchain_canonicalization_atomic_repair_chain,
    build_langchain_canonicalization_atomic_verifier_chain,
    build_langchain_legal_intent_extractor_chain,
    build_langchain_legal_intent_pair_judge_chain,
    build_langchain_verifier_chain,
    build_canonicalization_atomic_claim_ledger,
    canonicalization_atomic_verification_controller,
    canonicalization_prompt_profile,
    compact_canonicalization_llm_payload,
    compact_canonicalization_atomic_critic_payload,
    cluster_tg_qa_legal_issues,
    emit_tg_qa_canonical_embedding_batch,
    emit_tg_qa_canonicalization_batch,
    export_tg_qa_canonicalization_review_cards,
    finalize_tg_qa_canonicalization_results,
    export_tg_qa_legal_intent_pair_review_html,
    import_tg_qa_canonical_embedding_records,
    import_tg_qa_canonicalization_results,
    import_tg_qa_canonicalization_review_decisions,
    import_tg_qa_cluster_review_decisions,
    import_tg_qa_legal_intent_candidates,
    import_tg_qa_legal_intent_pair_decisions,
    import_tg_qa_legal_intent_pair_review_labels,
    merge_canonicalization_atomic_verifier_critic,
    run_tg_qa_legal_intent_candidate_extractor_batch,
    run_tg_qa_legal_intent_pair_judge_batch,
    run_tg_qa_canonicalization_adjudication_batch,
    run_tg_qa_canonicalization_atomic_verify_repair_batch,
    run_tg_qa_canonicalization_deepseek_batch,
    run_tg_qa_canonicalization_llm_batch,
    run_tg_qa_canonicalization_verifier_batch,
    sample_tg_qa_canonicalization_batch,
    verify_tg_question_canonicalization_boundaries,
)
from evaluation import tg_question_canonicalization as canonicalization


def test_canonicalization_constants_slug_ids_and_privacy_guard_are_stable() -> None:
    assert CANONICALIZATION_CONTRACT_VERSION == "tg_question_canonicalization_v2"
    assert CANONICALIZATION_PROMPT_EXAMPLE_SET_ID == "tg_question_canonicalizer_examples_v12_positive"
    assert len(CANONICALIZATION_PROMPT_EXAMPLES) == 26

    prompt_profile = canonicalization_prompt_profile()
    assert prompt_profile["prompt_example_set_id"] == CANONICALIZATION_PROMPT_EXAMPLE_SET_ID
    assert prompt_profile["prompt_profile_hash"] == canonicalization._canonicalization_prompt_profile_hash(
        canonicalization.CANONICALIZATION_PROMPT_VERSION
    )
    assert all(
        isinstance(example.get("input"), dict) and isinstance(example.get("output"), dict)
        for example in prompt_profile["few_shot_examples"]
    )
    assert {
        "canonical_question",
        "legal_issue_frame",
        "legal_issue_frame_slug",
        "exclusion_reason",
    } <= set(prompt_profile["expected_output_schema"])
    assert prompt_profile["few_shot_examples"][0]["output"]["exclusion_reason"] == "none"
    assert prompt_profile["few_shot_examples"][3]["output"]["exclusion_reason"] == "non_legal_question"

    instruction = str(prompt_profile["system_instruction"])
    for invariant in (
        "Return exactly one valid json object",
        "Produce evidence fields only",
        "IMPORTANT QUESTION-ANSWER BOUNDARY",
        "IMPORTANT LEGAL-OPERATIONAL BOUNDARY",
        "IMPORTANT ATOMIC CANONICAL QUESTION",
    ):
        assert invariant in instruction

    verifier_instruction = str(CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"])
    for invariant in (
        "verdict exactly as one of: pass, fail, uncertain",
        "suggested_action exactly as one of: accept, reject, retry_qwen, send_deepseek, human_review",
        "IMPORTANT QUESTION-ANSWER BOUNDARY",
        "IMPORTANT FIELD-SCOPE CHECK",
    ):
        assert invariant in verifier_instruction

    adjudicator_instruction = str(CANONICALIZATION_ADJUDICATOR_PROMPT_PROFILE["system_instruction"])
    for invariant in (
        "Routing semantics",
        "only after checking the candidate canonical_question and legal_issue_frame themselves",
        "IMPORTANT FIELD-SCOPE CHECK",
    ):
        assert invariant in adjudicator_instruction

    assert CANONICALIZATION_VERIFIER_PROMPT_PROFILE["prompt_version"] == "tg_question_canonicalization_verifier_v9_positive"
    assert CANONICALIZATION_ADJUDICATOR_PROMPT_PROFILE["prompt_version"] == "tg_question_canonicalization_adjudicator_v10_positive"
    assert CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_PROFILE["prompt_version"] == (
        "tg_question_canonicalization_atomic_verifier_v6"
    )
    assert CANONICALIZATION_ATOMIC_CRITIC_PROMPT_PROFILE["prompt_version"] == (
        "tg_question_canonicalization_atomic_critic_v6"
    )
    assert CANONICALIZATION_ATOMIC_REPAIR_PROMPT_PROFILE["prompt_version"] == (
        "tg_question_canonicalization_atomic_repair_v3"
    )
    assert "field ownership first" in str(
        CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_PROFILE["system_instruction"]
    )
    assert "smallest sufficient edit" in str(
        CANONICALIZATION_ATOMIC_REPAIR_PROMPT_PROFILE["system_instruction"]
    )
    assert "plain-text decision memo" in str(
        CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_PROFILE["reasoning_system_instruction"]
    )
    assert "without performing a new legal analysis" in str(
        CANONICALIZATION_ATOMIC_VERIFIER_PROMPT_PROFILE["formatter_system_instruction"]
    )
    atomic_schema = canonicalization.AtomicVerificationPayload.model_json_schema()
    assert atomic_schema["properties"]["route"]["enum"] == ["pass", "revise", "hold"]
    atomic_claim_schema = atomic_schema["$defs"]["AtomicClaimVerdictPayload"]["properties"]
    assert atomic_claim_schema["support"]["enum"] == [
        "explicit",
        "necessary_inference",
        "unsupported",
        "unresolved",
    ]
    assert "eligibility_condition" in atomic_claim_schema["relation_kind"]["enum"]
    assert CanonicalizationResultPayload.model_config["extra"] == "forbid"
    assert VerifierVerdictPayload.model_config["extra"] == "forbid"
    assert AdjudicationPayload.model_config["extra"] == "forbid"
    assert "none" in EXCLUSION_REASONS
    assert CONFIDENCE_VALUES == ("low", "medium", "high")
    assert canonicalization._slugify("Residence Document Address Update") == "residence_document_address_update"
    assert canonicalization._slugify("Blaue Karte Übertrag") == "blaue_karte_uebertrag"
    assert canonicalization._stable_id("x", "a", {"b": 1}) == canonicalization._stable_id("x", "a", {"b": 1})

    with pytest.raises(ValueError, match="private or unsafe"):
        canonicalization._ensure_public_payload({"path": "data/tg/raw-result.json"})
    with pytest.raises(ValueError, match="private or unsafe"):
        canonicalization._ensure_public_payload({"endpoint": "http://example.test/v1"})


def test_canonicalizer_v25_foreign_activity_rule_has_no_case_derived_examples() -> None:
    baseline = load_prompt_profile_data("tg_question_canonicalizer_v22_positive")
    profile = load_prompt_profile_data("tg_question_canonicalizer_v25_positive")

    assert profile["prompt_example_set_id"] == baseline["prompt_example_set_id"]
    assert profile["few_shot_examples"] == baseline["few_shot_examples"]
    assert len(profile["few_shot_examples"]) == 26
    instruction = str(profile["system_instruction"])
    assert "IMPORTANT FOREIGN-REGISTERED ACTIVITY THRESHOLD" in instruction
    assert "Do not put an authority in authority_context merely because" in instruction
    assert "do not label it double taxation" in instruction
    assert "tg-question-canonicalization-task:" not in json.dumps(profile, ensure_ascii=False)


def test_canonicalizer_v26_changes_only_instruction_structure() -> None:
    baseline = load_prompt_profile_data("tg_question_canonicalizer_v25_positive")
    profile = load_prompt_profile_data("tg_question_canonicalizer_v26_structured")

    assert profile["prompt_example_set_id"] == baseline["prompt_example_set_id"]
    assert profile["expected_output_schema"] == baseline["expected_output_schema"]
    assert profile["few_shot_examples"] == baseline["few_shot_examples"]
    structured = str(profile["system_instruction"])
    restored = re.sub(r"\n\n\d+\. (?=IMPORTANT [A-Z -]+:)", " ", structured)
    assert restored == baseline["system_instruction"]
    assert len(re.findall(r"\n\n\d+\. IMPORTANT [A-Z -]+:", structured)) == 16
    assert "tg-question-canonicalization-task:" not in json.dumps(profile, ensure_ascii=False)


def test_canonicalizer_v27_diagnostic_is_deletion_only_and_has_no_examples() -> None:
    baseline = load_prompt_profile_data("tg_question_canonicalizer_v25_positive")
    profile = load_prompt_profile_data("tg_question_canonicalizer_v27_compact_foreign_activity_diagnostic")

    assert profile["expected_output_schema"] == baseline["expected_output_schema"]
    assert profile["prompt_example_set_id"] == "tg_question_canonicalizer_examples_none_diagnostic_v1"
    assert profile["few_shot_examples"] == []
    instruction = str(profile["system_instruction"])
    for retained_block in instruction.split("\n\n"):
        assert retained_block in baseline["system_instruction"]
    assert "IMPORTANT FOREIGN-REGISTERED ACTIVITY THRESHOLD" in instruction
    assert "tg-question-canonicalization-task:" not in json.dumps(profile, ensure_ascii=False)


def test_canonicalizer_v28_uses_compact_positive_prerequisite_rules() -> None:
    profile = load_prompt_profile_data("tg_question_canonicalizer_v28_compact_positive_prerequisite")

    assert profile["prompt_example_set_id"] == "tg_question_canonicalizer_examples_none_diagnostic_v1"
    assert profile["few_shot_examples"] == []
    assert set(profile["expected_output_schema"]) == {
        "legal_issue_frame",
        "legal_issue_frame_slug",
        "canonical_question",
        "canonical_question_language",
        "law_area",
        "facts",
        "desired_outcome",
        "authority_context",
        "hidden_issues",
        "is_legal_answer_required",
        "is_standalone_question",
        "exclusion_reason",
        "confidence",
        "quality_flags",
    }
    instruction = str(profile["system_instruction"])
    assert "Apply this decision sequence" in instruction
    assert "Choose the prerequisite" in instruction
    assert "remains independently answerable" in instruction
    assert "applicable registration duties explicitly in hidden_issues" in instruction
    negative_directives = re.findall(r"\b(?:do not|don't|never|avoid)\b", instruction, re.IGNORECASE)
    assert len(negative_directives) <= 3
    assert len(instruction) <= 4_500
    assert "tg-question-canonicalization-task:" not in json.dumps(profile, ensure_ascii=False)


def test_canonicalizer_v29_has_mandatory_foreign_activity_gate() -> None:
    baseline = load_prompt_profile_data("tg_question_canonicalizer_v28_compact_positive_prerequisite")
    profile = load_prompt_profile_data("tg_question_canonicalizer_v29_compact_positive_mandatory_activity_gate")

    assert profile["expected_output_schema"] == baseline["expected_output_schema"]
    assert profile["prompt_example_set_id"] == baseline["prompt_example_set_id"]
    assert profile["few_shot_examples"] == []
    instruction = str(profile["system_instruction"])
    assert "Apply the mandatory foreign-activity gate" in instruction
    assert "Select the applicable German registration duties" in instruction
    assert "has priority over downstream requests" in instruction
    assert "explicitly requests application of a tax treaty or credit" in instruction
    assert len(re.findall(r"\b(?:do not|don't|never|avoid)\b", instruction, re.IGNORECASE)) <= 3
    assert len(instruction) <= 4_500
    assert "tg-question-canonicalization-task:" not in json.dumps(profile, ensure_ascii=False)


def test_canonicalizer_v30_tightens_activity_gate_output_precision() -> None:
    profile = load_prompt_profile_data("tg_question_canonicalizer_v30_compact_activity_gate_precision")

    assert profile["prompt_example_set_id"] == "tg_question_canonicalizer_examples_none_diagnostic_v1"
    assert profile["few_shot_examples"] == []
    instruction = str(profile["system_instruction"])
    assert "ask only which registration duties arise" in instruction
    assert "Set law_area exactly to self_employment" in instruction
    assert "Use an empty authority_context" in instruction
    assert "Never add an authority solely because" in instruction
    assert "Foreign tax payment alone is not such a request" in instruction
    assert len(re.findall(r"\b(?:do not|don't|never|avoid)\b", instruction, re.IGNORECASE)) <= 3
    assert len(instruction) <= 4_500
    assert "tg-question-canonicalization-task:" not in json.dumps(profile, ensure_ascii=False)


def test_canonicalizer_v31_tightens_activity_gate_semantic_precision() -> None:
    profile = load_prompt_profile_data("tg_question_canonicalizer_v31_compact_activity_gate_semantic_precision")

    assert profile["prompt_example_set_id"] == "tg_question_canonicalizer_examples_none_diagnostic_v1"
    assert profile["few_shot_examples"] == []
    instruction = str(profile["system_instruction"])
    assert "Never turn that non-contact into an eligibility condition" in instruction
    assert "Never infer one of these mechanisms from foreign tax payment" in instruction
    assert "правовой режим социального страхования" in instruction
    assert len(re.findall(r"\b(?:do not|don't|never|avoid)\b", instruction, re.IGNORECASE)) <= 3
    assert len(instruction) <= 4_800
    assert "tg-question-canonicalization-task:" not in json.dumps(profile, ensure_ascii=False)


def test_canonicalizer_v32_keeps_failure_concepts_out_of_attention() -> None:
    profile = load_prompt_profile_data("tg_question_canonicalizer_v32_compact_activity_gate_attention_focus")

    assert profile["prompt_example_set_id"] == "tg_question_canonicalizer_examples_none_diagnostic_v1"
    assert profile["few_shot_examples"] == []
    instruction = str(profile["system_instruction"])
    assert "Place contextual history about contacts with authorities in facts" in instruction
    assert "Express benefit issues through the legal eligibility criteria" in instruction
    assert "Represent the tax dimension through German tax residence" in instruction
    assert re.search(r"\b(do not|don't|never|avoid)\b", instruction, re.IGNORECASE) is None
    attention_text = json.dumps(profile, ensure_ascii=False).lower()
    assert "double taxation" not in attention_text
    assert "tax treaty" not in attention_text
    assert "not contacted" not in attention_text
    assert "tg-question-canonicalization-task:" not in attention_text
    assert len(instruction) <= 4_800


def test_canonicalizer_v33_audits_weak_hint_dependencies_across_all_fields() -> None:
    baseline = load_prompt_profile_data("tg_question_canonicalizer_v22_positive")
    profile = load_prompt_profile_data(
        "tg_question_canonicalizer_v33_positive_hint_independence_audit"
    )

    instruction = str(profile["system_instruction"])
    assert profile["few_shot_examples"] == baseline["few_shot_examples"]
    assert profile["expected_output_schema"] == baseline["expected_output_schema"]
    assert "review every output field" in instruction
    assert "requires independent support" in instruction
    assert "rederive every output field that may depend on it" in instruction


def test_canonicalizer_v34_limits_route_ambiguity_to_migration_questions() -> None:
    baseline = load_prompt_profile_data("tg_question_canonicalizer_v22_positive")
    profile = load_prompt_profile_data(
        "tg_question_canonicalizer_v34_positive_contextual_route_and_hint_audit"
    )

    instruction = str(profile["system_instruction"])
    assert profile["few_shot_examples"] == baseline["few_shot_examples"]
    assert profile["expected_output_schema"] == baseline["expected_output_schema"]
    assert "When the source asks about a migration route or status" in instruction
    assert "When refugee wording only describes a person, payment, or benefit" in instruction
    assert "represent both routes explicitly" not in instruction
    assert "review every output field" in instruction


def test_canonicalizer_v35_uses_compact_field_ownership_without_examples() -> None:
    profile = load_prompt_profile_data(
        "tg_question_canonicalizer_v35_compact_field_ownership_and_hint_independence"
    )

    instruction = str(profile["system_instruction"])
    assert profile["prompt_example_set_id"] == (
        "tg_question_canonicalizer_examples_none_field_ownership_v1"
    )
    assert profile["few_shot_examples"] == []
    assert "Field ownership:" in instruction
    assert "authority_context" in instruction
    assert "remains empty while the applicable regime" in instruction
    assert "audit every output field" in instruction
    assert "tg-question-canonicalization-task:" not in instruction
    assert len(instruction) < 2_500


def test_canonicalizer_v36_selects_one_entitlement_consequence() -> None:
    profile = load_prompt_profile_data(
        "tg_question_canonicalizer_v36_compact_field_ownership_single_proposition"
    )

    instruction = str(profile["system_instruction"])
    assert profile["few_shot_examples"] == []
    assert "FINAL SINGLE-PROPOSITION CHECK" in instruction
    assert "select the entitlement consequence" in instruction
    assert "preserve activity permission in hidden_issues" in instruction
    assert len(instruction) < 2_500


def test_canonicalizer_v37_preserves_full_source_legal_object_and_procedure() -> None:
    baseline = load_prompt_profile_data("tg_question_canonicalizer_v22_positive")
    profile = load_prompt_profile_data(
        "tg_question_canonicalizer_v37_full_source_legal_object_and_procedure"
    )

    instruction = str(profile["system_instruction"])
    assert profile["few_shot_examples"] == baseline["few_shot_examples"]
    assert profile["expected_output_schema"] == baseline["expected_output_schema"]
    assert "create, renew, change, surrender, or terminate" in instruction
    assert "Reiseausweis für Ausländer" in instruction
    assert "complete sequence of questions" in instruction
    assert "ONGOING FOREIGN EARNINGS CLASSIFICATION" in instruction
    assert "DATE-AWARE STATUS PROOF" in instruction
    assert "tg-question-canonicalization-task:" not in instruction


def test_canonicalizer_v38_adds_actor_action_location_foreign_activity_gate() -> None:
    baseline = load_prompt_profile_data(
        "tg_question_canonicalizer_v37_full_source_legal_object_and_procedure"
    )
    profile = load_prompt_profile_data(
        "tg_question_canonicalizer_v38_full_source_foreign_activity_gate"
    )

    assert profile["expected_output_schema"] == baseline["expected_output_schema"]
    assert profile["prompt_example_set_id"] == baseline["prompt_example_set_id"]
    assert profile["few_shot_examples"] == baseline["few_shot_examples"]
    instruction = str(profile["system_instruction"])
    assert "First establish an actor-action-location link" in instruction
    assert "foreign sole-proprietor or business registration requires hidden_issues" in instruction
    assert "Treat foreign registration and foreign tax payment as source facts" in instruction
    assert "only as proof" in instruction
    assert "tg-question-canonicalization-task:" not in instruction


def test_canonicalizer_v39_structures_full_source_and_foreign_activity_rules() -> None:
    structured = load_prompt_profile_data("tg_question_canonicalizer_v26_structured")
    profile = load_prompt_profile_data("tg_question_canonicalizer_v39_structured_full_source")

    assert profile["expected_output_schema"] == structured["expected_output_schema"]
    assert profile["prompt_example_set_id"] == structured["prompt_example_set_id"]
    assert profile["few_shot_examples"] == structured["few_shot_examples"]
    instruction = str(profile["system_instruction"])
    for marker in (
        "16. IMPORTANT FOREIGN-REGISTERED ACTIVITY THRESHOLD",
        "17. IMPORTANT ONGOING FOREIGN SALARY CLASSIFICATION",
        "18. IMPORTANT DATE-AWARE STATUS PROOF",
        "create, renew, change, surrender, or terminate",
        "Reiseausweis für Ausländer",
        "complete sequence of questions",
    ):
        assert instruction.count(marker) == 1
    assert "tg-question-canonicalization-task:" not in instruction


def test_canonicalizer_v40_is_focused_on_preselected_foreign_activity() -> None:
    profile = load_prompt_profile_data(
        "tg_question_canonicalizer_v40_foreign_activity_selected"
    )
    instruction = str(profile["system_instruction"])

    assert profile["few_shot_examples"] == []
    assert "record preselected" in instruction
    assert "Select the source author's explicit child or household benefit question" in instruction
    assert "hidden_issues must preserve all material German-law dimensions" in instruction
    assert "It is not a general condition for child-benefit eligibility" in instruction
    assert "how competing taxation is relieved" in instruction
    assert len(instruction) < 3_500
    assert "tg-question-canonicalization-task:" not in instruction


def test_canonicalizer_v41_owns_jobcenter_and_child_benefit_fields() -> None:
    profile = load_prompt_profile_data(
        "tg_question_canonicalizer_v41_foreign_activity_selected_field_ownership"
    )
    instruction = str(profile["system_instruction"])

    assert profile["few_shot_examples"] == []
    assert "Omit Jobcenter from authority_context" in instruction
    assert "omit every Kindergeld-Jobcenter eligibility relation" in instruction
    assert "law_area=social_benefits" in instruction
    assert "authority_context limited to Familienkasse" in instruction
    assert len(instruction) < 3_500


def test_foreign_activity_regression_checks_are_language_and_field_aware() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    registry = _read_json(
        repo_root / "specs/007-legal-question-canonicalization/prompt-regression-cases.json"
    )
    case = next(item for item in registry["cases"] if item["case_id"].startswith("pr-062-"))
    checks = case["automatic_checks"]

    assert checks["required_all_evidence_term_groups"] == [
        ["German", "немецк"],
        ["registration", "регистрац"],
        ["self-employment", "самозанят", "предпринимательск"],
    ]
    assert checks["forbidden_authority_context_terms"] == ["Jobcenter"]
    assert checks["forbidden_hidden_issue_term_pairs"] == [["Kindergeld", "Jobcenter"]]


def test_structured_models_and_compact_llm_payload_avoid_private_context(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    summary_path = tmp_path / "summary.json"
    _write_jsonl(
        candidates_path,
        [_candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", "m1")],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=summary_path,
        filter_mode="law_or_topic",
    )
    batch_item = _read_jsonl(batch_path)[0]

    compact = compact_canonicalization_llm_payload(batch_item)
    serialized_compact = json.dumps(compact, ensure_ascii=False, sort_keys=True)
    assert compact["prompt_example_set_id"] == CANONICALIZATION_PROMPT_EXAMPLE_SET_ID
    assert compact["input"]["question_date"] == "2026-01-01T00:00:00"
    assert "source_message_ids" not in serialized_compact
    assert "source_candidate_artifact" not in serialized_compact
    assert "selected_answer_metadata" not in serialized_compact
    retry_batch_item = dict(batch_item)
    retry_batch_item["retry_context"] = {
        "previous_candidate": {"candidate_key": "primary", "law_area": "employment"},
        "verifier_votes": [{"candidate_key": "primary", "bad_fields": ["law_area"], "short_reason": "Wrong law area."}],
        "human_triage": {"decision": "retry_qwen", "decision_reason": "law_area_wrong"},
    }
    retry_compact = compact_canonicalization_llm_payload(retry_batch_item)
    assert retry_compact["retry_context"]["previous_candidate"]["law_area"] == "employment"
    assert retry_compact["retry_context"]["verifier_votes"][0]["bad_fields"] == ["law_area"]
    assert retry_compact["retry_context"]["human_triage"]["decision"] == "retry_qwen"

    result = CanonicalizationResultPayload.model_validate(
        _canonical_result(batch_item, include_operator_identity=False)
    )
    assert result.legal_issue_frame_slug == "residence_document_address_update_after_moving"
    assert result.is_legal_answer_required is True

    verifier = VerifierVerdictPayload.model_validate(
        {
            "verdict": "pass",
            "confidence": 93,
            "risk": "low",
            "bad_fields": [],
            "short_reason": "Fixture is internally consistent.",
            "suggested_action": "accept",
        }
    )
    assert verifier.model_dump()["suggested_action"] == "accept"
    adjudication = AdjudicationPayload.model_validate(
        {
            "verdict": "fail",
            "confidence": 90,
            "risk": "medium",
            "bad_fields": ["law_area"],
            "short_reason": "Retry the only candidate.",
            "final_recommendation": "retry_generator",
        }
    )
    assert adjudication.selected_candidate_key == ""
    with pytest.raises(ValueError, match="inconsistent_verdict_final_recommendation"):
        AdjudicationPayload.model_validate(
            {
                "verdict": "pass",
                "confidence": 80,
                "risk": "low",
                "bad_fields": [],
                "short_reason": "Candidate is acceptable.",
                "final_recommendation": "reject",
            }
        )
    with pytest.raises(ValueError, match="inconsistent_verdict_final_recommendation"):
        AdjudicationPayload.model_validate(
            {
                "verdict": "fail",
                "confidence": 80,
                "risk": "medium",
                "bad_fields": ["exclusion_reason"],
                "short_reason": "Candidate is not acceptable.",
                "final_recommendation": "accept",
                "selected_candidate_key": "primary",
            }
        )
    with pytest.raises(ValueError, match="missing_short_reason_for_non_pass_verdict"):
        VerifierVerdictPayload.model_validate(
            {
                "verdict": None,
                "confidence": 0,
                "risk": None,
                "bad_fields": None,
                "short_reason": None,
                "suggested_action": None,
            }
        )
    uncertain_verifier = VerifierVerdictPayload.model_validate(
        {
            "verdict": "uncertain",
            "confidence": 0,
            "risk": "medium",
            "bad_fields": [],
            "short_reason": "Needs human review.",
            "suggested_action": "human_review",
        }
    )
    assert uncertain_verifier.verdict == "uncertain"
    assert uncertain_verifier.short_reason == "Needs human review."
    quoted_verifier = VerifierVerdictPayload.model_validate(
        {
            "verdict": '"pass"',
            "confidence": 88,
            "risk": '"low"',
            "bad_fields": [],
            "short_reason": "fixture",
            "suggested_action": '"accept"',
        }
    )
    assert quoted_verifier.verdict == "pass"
    assert quoted_verifier.risk == "low"
    assert quoted_verifier.suggested_action == "accept"
    enum_confidence_verifier = VerifierVerdictPayload.model_validate(
        {
            "verdict": "pass",
            "confidence": "high",
            "risk": "low",
            "bad_fields": [],
            "short_reason": "fixture",
            "suggested_action": "accept",
        }
    )
    assert enum_confidence_verifier.confidence == 90
    wrapped_verifier = canonicalization._verifier_payload_for_review(
        {
            "answer": {
                "verdict": "pass",
                "confidence": "high",
                "risk": "none",
                "bad_fields": [],
                "short_reason": "Wrapped payload is valid.",
                "suggested_action": "accept",
            }
        }
    )
    assert wrapped_verifier["verdict"] == "pass"
    assert wrapped_verifier["confidence"] == 90


def test_review_llm_payload_repeats_candidate_field_scope_without_source_details() -> None:
    source_question = (
        "По поводу учебы, можно ли беженцам пойти учиться в колледж или университет, "
        "выбрать направление? На каком языке преподают? Сколько лет учиться? Кто оплачивает учебу?"
    )
    candidate = {
        "candidate_key": "qwen",
        "candidate_id": "tg-qa-candidate:education",
        "model_id": "qwen3.6-plus",
        "status": "completed",
        "canonical_question": (
            "Имеют ли лица со статусом беженца право на поступление в колледж или университет, "
            "выбор направления обучения, и кто оплачивает учебу?"
        ),
        "canonical_question_language": "ru",
        "legal_issue_frame": "Refugee access to higher education and financial support eligibility",
        "legal_issue_frame_slug": "refugee_access_to_higher_education_and_financial_support",
        "law_area": "education",
        "facts": ["source also asks about language requirements and duration"],
        "desired_outcome": "clarify eligibility for higher education and funding sources for refugees",
        "authority_context": ["university", "college"],
        "hidden_issues": ["language proficiency requirements for admission"],
        "is_legal_answer_required": True,
        "is_standalone_question": True,
        "exclusion_reason": "none",
        "confidence": "high",
        "quality_flags": ["mixed_with_non_legal_query"],
        "question_date": "2025-01-01T00:00:00Z",
    }
    evidence = {
        "task_id": "tg-question-canonicalization-task:education",
        "candidate_id": candidate["candidate_id"],
        "source_question_text_redacted": source_question,
        **candidate,
    }

    verifier_payload = canonicalization._compact_verifier_llm_payload(evidence)
    verifier_scope = verifier_payload["field_scope_review"]["qwen"]
    assert "language requirements" in verifier_payload["qwen"]["facts"][0]
    assert "На каком языке" in verifier_payload["source_question_text_redacted"]
    assert verifier_payload["question_date"] == "2025-01-01T00:00:00Z"
    assert "На каком языке" not in verifier_scope["canonical_question_under_review"]
    assert "Сколько лет" not in verifier_scope["canonical_question_under_review"]
    assert verifier_scope["canonical_question_under_review"] == candidate["canonical_question"]
    assert verifier_scope["legal_issue_frame_under_review"] == candidate["legal_issue_frame"]

    adjudication_payload = canonicalization._compact_adjudication_payload(
        {
            "task_id": "tg-question-canonicalization-task:education",
            "candidate_id": candidate["candidate_id"],
            "source_question_text_redacted": source_question,
            "question_date": "2025-01-01T00:00:00Z",
            "candidates": [candidate],
            "verifier_votes": [
                {
                    "candidate_key": "qwen",
                    "verifier_key": "qwen37",
                    "status": "completed",
                    "verdict": "fail",
                    "bad_fields": ["canonical_question"],
                    "short_reason": "The source mentions language of instruction and study duration.",
                    "suggested_action": "retry_qwen",
                }
            ],
        }
    )
    adjudication_scope = adjudication_payload["field_scope_review"]["candidates"][0]
    assert adjudication_payload["question_date"] == "2025-01-01T00:00:00Z"
    assert "source mentions language" in adjudication_payload["verifier_votes"][0]["short_reason"]
    assert "На каком языке" in adjudication_payload["source_question_text_redacted"]
    assert "На каком языке" not in adjudication_scope["canonical_question_under_review"]
    assert "Сколько лет" not in adjudication_scope["canonical_question_under_review"]
    assert adjudication_scope["canonical_question_under_review"] == candidate["canonical_question"]
    rendered_adjudication = canonicalization._review_payload_for_prompt(adjudication_payload)
    assert rendered_adjudication.count("FINAL FIELD-SCOPE REVIEW") == 1
    assert rendered_adjudication.rfind("canonical_question_under_review") > rendered_adjudication.rfind(
        "source mentions language"
    )
    assert rendered_adjudication.rfind(candidate["canonical_question"]) > rendered_adjudication.rfind(
        source_question
    )


def test_atomic_claim_ledger_and_controller_routes_are_deterministic() -> None:
    source = "Автор переехал и спрашивает, нужно ли менять адрес в ВНЖ."
    evidence = _evidence("evidence:atomic", "candidate:atomic", source)
    evidence.update(
        {
            "facts": ["Автор переехал"],
            "desired_outcome": "Узнать, нужно ли менять адрес в ВНЖ",
            "authority_context": [],
            "hidden_issues": [],
        }
    )
    evidence["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(evidence)
    first = build_canonicalization_atomic_claim_ledger(evidence)
    second = build_canonicalization_atomic_claim_ledger(evidence)
    assert first == second
    assert first["claims"]
    assert len({claim["claim_id"] for claim in first["claims"]}) == len(first["claims"])

    span = canonicalization.AtomicSourceSpanPayload(start=0, end=len(source), quote=source)
    pass_verdicts = [
        canonicalization.AtomicClaimVerdictPayload(
            claim_id=claim["claim_id"],
            support="explicit",
            relation_kind=claim["claim_type"] if claim["claim_type"] in canonicalization.ATOMIC_CLAIM_RELATION_KINDS else "other",
            materiality=claim["materiality"],
            source_spans=[span],
        )
        for claim in first["claims"]
    ]
    passed = canonicalization_atomic_verification_controller(
        canonicalization.AtomicVerificationPayload(route="pass", claim_verdicts=pass_verdicts),
        first,
        source,
    )
    assert passed["route"] == "pass"

    normalized_offsets = list(pass_verdicts)
    normalized_offsets[0] = canonicalization.AtomicClaimVerdictPayload(
        claim_id=first["claims"][0]["claim_id"],
        support="explicit",
        relation_kind="canonical_issue",
        materiality="high",
        source_spans=[
            canonicalization.AtomicSourceSpanPayload(
                start=0,
                end=len(source) - 1,
                quote=source,
            )
        ],
    )
    normalized = canonicalization_atomic_verification_controller(
        canonicalization.AtomicVerificationPayload(route="pass", claim_verdicts=normalized_offsets),
        first,
        source,
    )
    assert normalized["route"] == "pass"
    assert normalized["normalized_source_span_count"] == 1
    assert normalized["normalized_source_spans"][0]["normalized_end"] == len(source)
    assert normalized["normalized_source_spans"][0]["normalization_mode"] == "end_offset_corrected"

    unsupported = list(pass_verdicts)
    target = first["claims"][0]
    unsupported[0] = canonicalization.AtomicClaimVerdictPayload(
        claim_id=target["claim_id"],
        support="unsupported",
        relation_kind="canonical_issue",
        materiality="high",
        source_spans=[],
        correction="Use the source-supported issue.",
        short_reason="The proposed issue adds an unsupported dependency.",
    )
    revise = canonicalization_atomic_verification_controller(
        canonicalization.AtomicVerificationPayload(route="revise", claim_verdicts=unsupported),
        first,
        source,
    )
    assert revise["route"] == "revise"
    assert revise["unsupported_claim_ids"] == [target["claim_id"]]

    invalid_span = list(pass_verdicts)
    invalid_span[0] = canonicalization.AtomicClaimVerdictPayload(
        claim_id=target["claim_id"],
        support="explicit",
        relation_kind="canonical_issue",
        materiality="high",
        source_spans=[canonicalization.AtomicSourceSpanPayload(start=0, end=5, quote="xxxxx")],
    )
    hold = canonicalization_atomic_verification_controller(
        canonicalization.AtomicVerificationPayload(route="pass", claim_verdicts=invalid_span),
        first,
        source,
    )
    assert hold["route"] == "hold"
    assert "invalid_or_missing_source_spans" in hold["reason_codes"]


def test_atomic_controller_holds_exact_untrusted_law_hint_reuse_in_any_field() -> None:
    source = "Можно ли работать, получая пособие для беженцев?"
    evidence = _evidence("evidence:hint-audit", "candidate:hint-audit", source)
    evidence.update(
        {
            "hidden_issues": ["Нужно ли разрешение на работу по BeschV"],
            "untrusted_law_code_hints": ["AsylG", "BeschV"],
        }
    )
    evidence["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(
        evidence
    )
    ledger = build_canonicalization_atomic_claim_ledger(evidence)
    verifier_payload = canonicalization.compact_canonicalization_atomic_verifier_payload(
        evidence,
        ledger,
    )
    assert "controller_audit" not in verifier_payload["claim_ledger"]
    span = canonicalization.AtomicSourceSpanPayload(start=0, end=len(source), quote=source)
    verdicts = [
        canonicalization.AtomicClaimVerdictPayload(
            claim_id=claim["claim_id"],
            support="necessary_inference",
            relation_kind=(
                claim["claim_type"]
                if claim["claim_type"] in canonicalization.ATOMIC_CLAIM_RELATION_KINDS
                else "other"
            ),
            materiality=claim["materiality"],
            source_spans=[span],
        )
        for claim in ledger["claims"]
    ]

    controller = canonicalization_atomic_verification_controller(
        canonicalization.AtomicVerificationPayload(route="pass", claim_verdicts=verdicts),
        ledger,
        source,
    )

    assert controller["route"] == "hold"
    assert controller["reason_codes"] == [
        "model_controller_route_disagreement",
        "untrusted_input_hint_reused",
    ]
    assert len(controller["untrusted_hint_conflicts"]) == 1
    assert controller["untrusted_hint_conflicts"][0] == {
        "hint": "BeschV",
        "claim_id": controller["untrusted_hint_claim_ids"][0],
        "field_name": "hidden_issues",
        "field_index": 0,
        "claim_text": "Нужно ли разрешение на работу по BeschV",
    }


def test_atomic_controller_allows_hint_named_by_source() -> None:
    source = "Применяется ли BeschV к моему разрешению на работу?"
    evidence = _evidence("evidence:source-hint", "candidate:source-hint", source)
    evidence.update(
        {
            "canonical_question": source,
            "untrusted_law_code_hints": ["BeschV"],
        }
    )
    evidence["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(
        evidence
    )
    ledger = build_canonicalization_atomic_claim_ledger(evidence)
    span = canonicalization.AtomicSourceSpanPayload(start=0, end=len(source), quote=source)
    verdicts = [
        canonicalization.AtomicClaimVerdictPayload(
            claim_id=claim["claim_id"],
            support="explicit",
            relation_kind=(
                claim["claim_type"]
                if claim["claim_type"] in canonicalization.ATOMIC_CLAIM_RELATION_KINDS
                else "other"
            ),
            materiality=claim["materiality"],
            source_spans=[span],
        )
        for claim in ledger["claims"]
    ]

    controller = canonicalization_atomic_verification_controller(
        canonicalization.AtomicVerificationPayload(route="pass", claim_verdicts=verdicts),
        ledger,
        source,
    )

    assert controller["route"] == "pass"
    assert controller["untrusted_hint_conflicts"] == []


def test_atomic_controller_audits_candidate_fields_without_claims() -> None:
    source = "Какое пособие применяется в моем случае?"
    evidence = _evidence("evidence:slug-hint", "candidate:slug-hint", source)
    evidence.update(
        {
            "legal_issue_frame_slug": "benefits_under_asylg",
            "untrusted_law_code_hints": ["AsylG"],
        }
    )
    evidence["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(
        evidence
    )
    ledger = build_canonicalization_atomic_claim_ledger(evidence)
    span = canonicalization.AtomicSourceSpanPayload(start=0, end=len(source), quote=source)
    verdicts = [
        canonicalization.AtomicClaimVerdictPayload(
            claim_id=claim["claim_id"],
            support="necessary_inference",
            relation_kind=(
                claim["claim_type"]
                if claim["claim_type"] in canonicalization.ATOMIC_CLAIM_RELATION_KINDS
                else "other"
            ),
            materiality=claim["materiality"],
            source_spans=[span],
        )
        for claim in ledger["claims"]
    ]

    controller = canonicalization_atomic_verification_controller(
        canonicalization.AtomicVerificationPayload(route="pass", claim_verdicts=verdicts),
        ledger,
        source,
    )

    assert controller["route"] == "hold"
    assert controller["untrusted_hint_claim_ids"] == []
    assert controller["untrusted_hint_conflicts"][0]["field_name"] == (
        "legal_issue_frame_slug"
    )


def test_atomic_relation_guards_block_known_compound_false_passes() -> None:
    positive_source = (
        "Мы живем в Германии и работаем ФОП на украинскую фирму. "
        "В Jobcenter не обращались. Полагается ли выплата на ребёнка и нужно ли "
        "платить налог в Германии? Steuer-ID пока не пришёл."
    )
    positive = _evidence(
        "evidence:atomic-relation-positive",
        "candidate:atomic-relation-positive",
        positive_source,
    )
    positive.update(
        {
            "canonical_question": (
                "Какие регистрационные обязанности возникают в Германии для украинского ФОП?"
            ),
            "desired_outcome": (
                "Установить право на выплату на ребёнка без регистрации в Jobcenter"
            ),
            "hidden_issues": [
                "Право на Kindergeld при отсутствии регистрации в Jobcenter",
                "Двойное налогообложение дохода украинского ФОП",
                "Steuer-ID как предварительное условие для налоговой регистрации",
            ],
        }
    )
    positive["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(
        positive
    )
    positive_ledger = build_canonicalization_atomic_claim_ledger(positive)
    positive_span = canonicalization.AtomicSourceSpanPayload(
        start=0,
        end=len(positive_source),
        quote=positive_source,
    )
    positive_verdicts = [
        canonicalization.AtomicClaimVerdictPayload(
            claim_id=claim["claim_id"],
            support="necessary_inference",
            relation_kind=(
                claim["claim_type"]
                if claim["claim_type"] in canonicalization.ATOMIC_CLAIM_RELATION_KINDS
                else "other"
            ),
            materiality=claim["materiality"],
            source_spans=[positive_span],
        )
        for claim in positive_ledger["claims"]
    ]
    positive_controller = canonicalization_atomic_verification_controller(
        canonicalization.AtomicVerificationPayload(
            route="pass",
            claim_verdicts=positive_verdicts,
        ),
        positive_ledger,
        positive_source,
    )

    assert positive_controller["route"] == "hold"
    assert {
        item["guard_id"] for item in positive_controller["relation_guard_conflicts"]
    } == {
        "child_benefit_jobcenter_compound_relation",
        "cross_border_tax_mechanism_missing",
        "identifier_prerequisite_missing",
    }
    assert "foreign_activity_actor_action_link_missing" not in {
        item["guard_id"] for item in positive_controller["relation_guard_conflicts"]
    }

    document_source = (
        "Я нахожусь в Германии. Какие документы подтверждают доход: банковская выписка "
        "или ФОП счёт?"
    )
    document_only = _evidence(
        "evidence:atomic-relation-document",
        "candidate:atomic-relation-document",
        document_source,
    )
    document_only.update(
        {
            "canonical_question": (
                "Какие регистрационные обязанности возникают в Германии для украинского ФОП?"
            ),
            "hidden_issues": [
                "Немецкая классификация деятельности украинского ФОП как Gewerbe"
            ],
        }
    )
    document_only["canonicalization_evidence_hash"] = (
        canonicalization._canonicalization_evidence_hash(document_only)
    )
    document_ledger = build_canonicalization_atomic_claim_ledger(document_only)
    document_span = canonicalization.AtomicSourceSpanPayload(
        start=0,
        end=len(document_source),
        quote=document_source,
    )
    document_verdicts = [
        canonicalization.AtomicClaimVerdictPayload(
            claim_id=claim["claim_id"],
            support="necessary_inference",
            relation_kind=(
                claim["claim_type"]
                if claim["claim_type"] in canonicalization.ATOMIC_CLAIM_RELATION_KINDS
                else "other"
            ),
            materiality=claim["materiality"],
            source_spans=[document_span],
        )
        for claim in document_ledger["claims"]
    ]
    document_controller = canonicalization_atomic_verification_controller(
        canonicalization.AtomicVerificationPayload(
            route="pass",
            claim_verdicts=document_verdicts,
        ),
        document_ledger,
        document_source,
    )

    assert document_controller["route"] == "hold"
    assert "deterministic_relation_guard_conflict" in document_controller["reason_codes"]
    assert {
        item["guard_id"] for item in document_controller["relation_guard_conflicts"]
    } == {"foreign_activity_actor_action_link_missing"}
    assert len(document_controller["relation_guard_claim_ids"]) == 2


def test_atomic_relation_risk_split_preserves_evidence_and_writes_diagnostics(
    tmp_path: Path,
) -> None:
    benefit = _evidence(
        "evidence:risk-benefit",
        "candidate:risk-benefit",
        "Семья живёт в Германии, в Jobcenter не обращалась и спрашивает о выплате на ребёнка.",
    )
    benefit["hidden_issues"] = [
        "Право на Kindergeld при отсутствии регистрации в Jobcenter"
    ]
    document = _evidence(
        "evidence:risk-document",
        "candidate:risk-document",
        "Автор в Германии спрашивает, предоставить банковскую выписку или ФОП счёт.",
    )
    document["canonical_question"] = (
        "Какие регистрационные обязанности возникают для украинского ФОП в Германии?"
    )
    clean = _evidence(
        "evidence:risk-clean",
        "candidate:risk-clean",
        "Автор переехал и спрашивает, нужно ли менять адрес в ВНЖ.",
    )
    for record in (benefit, document, clean):
        record["canonicalization_evidence_hash"] = (
            canonicalization._canonicalization_evidence_hash(record)
        )

    evidence_path = tmp_path / "evidence.jsonl"
    risk_path = tmp_path / "risk.jsonl"
    low_risk_path = tmp_path / "low-risk.jsonl"
    diagnostics_path = tmp_path / "diagnostics.jsonl"
    summary_path = tmp_path / "summary.json"
    _write_jsonl(evidence_path, [benefit, document, clean])

    result = canonicalization.split_tg_qa_canonicalization_atomic_relation_risks(
        evidence_path=evidence_path,
        risk_evidence_output_path=risk_path,
        low_risk_evidence_output_path=low_risk_path,
        diagnostics_output_path=diagnostics_path,
        summary_output_path=summary_path,
    )

    assert _read_jsonl(risk_path) == [benefit, document]
    assert _read_jsonl(low_risk_path) == [clean]
    diagnostics = _read_jsonl(diagnostics_path)
    assert [item["has_relation_risk"] for item in diagnostics] == [True, True, False]
    assert result["summary"]["relation_risk_record_count"] == 2
    assert result["summary"]["low_risk_record_count"] == 1
    assert result["summary"]["relation_risk_record_counts"] == {
        "child_benefit_jobcenter_compound_relation": 1,
        "foreign_activity_actor_action_link_missing": 1,
    }


def test_foreign_activity_candidate_split_requires_actor_action_location_link(
    tmp_path: Path,
) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    selected_path = tmp_path / "foreign_activity.jsonl"
    ordinary_path = tmp_path / "ordinary.jsonl"
    diagnostics_path = tmp_path / "diagnostics.jsonl"
    summary_path = tmp_path / "summary.json"
    _write_jsonl(
        candidates_path,
        [
            _candidate(
                "tg-qa-candidate:positive",
                "Мы живем в Германии и работаем ФОП на украинскую фирму.",
                "m1",
            ),
            _candidate(
                "tg-qa-candidate:document",
                "Я в Германии. Для страховки нужна выписка банка или ФОП счет?",
                "m2",
            ),
        ],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="law_or_topic",
    )
    source = _read_jsonl(batch_path)

    result = canonicalization.split_tg_qa_canonicalization_foreign_activity_candidates(
        batch_path=batch_path,
        foreign_activity_output_path=selected_path,
        ordinary_output_path=ordinary_path,
        diagnostics_output_path=diagnostics_path,
        summary_output_path=summary_path,
        foreign_activity_prompt_version="tg_question_canonicalizer_v26_structured",
    )

    selected = _read_jsonl(selected_path)
    ordinary = _read_jsonl(ordinary_path)
    diagnostics = _read_jsonl(diagnostics_path)
    assert result["summary"]["foreign_activity_count"] == 1
    assert result["summary"]["ordinary_count"] == 1
    assert selected[0]["candidate_id"] == "tg-qa-candidate:positive"
    assert selected[0]["prompt_version"] == "tg_question_canonicalizer_v26_structured"
    assert ordinary[0]["candidate_id"] == "tg-qa-candidate:document"
    assert selected[0]["canonicalization_source_identity"]["task_input_hash"] == (
        source[0]["task_input_hash"]
    )
    assert ordinary[0]["canonicalization_source_identity"]["task_input_hash"] == (
        source[1]["task_input_hash"]
    )
    assert [item["selected_for_foreign_activity_prompt"] for item in diagnostics] == [
        True,
        False,
    ]
    assert "question_text_redacted" not in diagnostics[0]
    canonicalization._canonicalization_batch_identity_index(selected)
    canonicalization._canonicalization_batch_identity_index(ordinary)
    assert json.loads(summary_path.read_text(encoding="utf-8")) == result["summary"]


def test_atomic_relation_risk_split_rejects_incomplete_derived_records(
    tmp_path: Path,
) -> None:
    incomplete = _evidence(
        "evidence:risk-incomplete",
        "candidate:risk-incomplete",
        "Автор спрашивает о регистрации деятельности в Германии.",
    )
    incomplete.pop("source_question_text_redacted")
    evidence_path = tmp_path / "incomplete.jsonl"
    _write_jsonl(evidence_path, [incomplete])

    with pytest.raises(
        ValueError,
        match=(
            "atomic_relation_risk_split_invalid_evidence:"
            "index=0:missing=canonicalization_evidence_hash,source_question_text_redacted"
        ),
    ):
        canonicalization.split_tg_qa_canonicalization_atomic_relation_risks(
            evidence_path=evidence_path,
            risk_evidence_output_path=tmp_path / "risk.jsonl",
            low_risk_evidence_output_path=tmp_path / "low-risk.jsonl",
            diagnostics_output_path=tmp_path / "diagnostics.jsonl",
            summary_output_path=tmp_path / "summary.json",
        )


def test_atomic_critic_conservatively_overrides_primary_pass() -> None:
    source = "Автор работает через иностранную регистрацию и не обращался в Jobcenter."
    evidence = _evidence("evidence:atomic-critic", "candidate:atomic-critic", source)
    evidence.update(
        {
            "desired_outcome": "Узнать о детском пособии",
            "authority_context": [],
            "hidden_issues": ["Право на пособие зависит от регистрации в Jobcenter"],
        }
    )
    evidence["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(evidence)
    ledger = build_canonicalization_atomic_claim_ledger(evidence)
    span = canonicalization.AtomicSourceSpanPayload(start=0, end=len(source), quote=source)
    primary_verdicts = [
        canonicalization.AtomicClaimVerdictPayload(
            claim_id=claim["claim_id"],
            support="necessary_inference",
            relation_kind=(
                claim["claim_type"]
                if claim["claim_type"] in canonicalization.ATOMIC_CLAIM_RELATION_KINDS
                else "other"
            ),
            materiality=claim["materiality"],
            source_spans=[span],
        )
        for claim in ledger["claims"]
    ]
    primary = canonicalization.AtomicVerificationPayload(
        route="pass",
        claim_verdicts=primary_verdicts,
    )
    critic_payload = compact_canonicalization_atomic_critic_payload(evidence, ledger, primary)
    critic_ledger = critic_payload["critic_claim_ledger"]
    critic_verdicts = []
    target_claim_id = ""
    for claim in critic_ledger["claims"]:
        if claim["field_name"] == "hidden_issues":
            target_claim_id = claim["claim_id"]
            critic_verdicts.append(
                canonicalization.AtomicClaimVerdictPayload(
                    claim_id=claim["claim_id"],
                    support="unsupported",
                    relation_kind="eligibility_condition",
                    materiality=claim["materiality"],
                    correction="Remove the Jobcenter eligibility dependency.",
                    short_reason="The source reports no contact but does not establish an eligibility condition.",
                )
            )
        else:
            critic_verdicts.append(
                canonicalization.AtomicClaimVerdictPayload(
                    claim_id=claim["claim_id"],
                    support="necessary_inference",
                    relation_kind=(
                        claim["claim_type"]
                        if claim["claim_type"] in canonicalization.ATOMIC_CLAIM_RELATION_KINDS
                        else "other"
                    ),
                    materiality=claim["materiality"],
                    source_spans=[span],
                )
            )
    critic = canonicalization.AtomicVerificationPayload(
        route="revise",
        claim_verdicts=critic_verdicts,
    )

    merged = merge_canonicalization_atomic_verifier_critic(
        primary,
        critic,
        ledger,
        critic_ledger,
        source,
    )
    combined = canonicalization.AtomicVerificationPayload.model_validate(
        merged["combined_verification"]
    )

    assert merged["merge_valid"] is True
    assert merged["critic_controller"]["route"] == "revise"
    assert any(item["claim_id"] == target_claim_id for item in merged["disagreements"])
    assert next(item for item in combined.claim_verdicts if item.claim_id == target_claim_id).support == (
        "unsupported"
    )


def test_atomic_verify_repair_runner_reverifies_changed_candidate(tmp_path: Path) -> None:
    source = "Автор спрашивает, полагаются ли выплаты на ребёнка."
    evidence = _evidence("evidence:atomic-run", "candidate:atomic-run", source, law_area="social_benefits")
    evidence.update(
        {
            "facts": ["У автора есть ребёнок"],
            "desired_outcome": "Установить право на выплаты на ребёнка",
            "authority_context": [],
            "hidden_issues": ["Право на выплаты зависит от регистрации в Jobcenter"],
        }
    )
    evidence["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(evidence)
    evidence_path = tmp_path / "evidence.jsonl"
    output_path = tmp_path / "atomic.jsonl"
    summary_path = tmp_path / "atomic_summary.json"
    checkpoint_path = tmp_path / "atomic_checkpoint.json"
    bundle_path = tmp_path / "atomic_bundle.json"
    _write_jsonl(evidence_path, [evidence])

    result = run_tg_qa_canonicalization_atomic_verify_repair_batch(
        evidence_path=evidence_path,
        output_path=output_path,
        summary_output_path=summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-glm",
        atomic_run_id="atomic-run:fixture",
        checkpoint_output_path=checkpoint_path,
        run_bundle_output_path=bundle_path,
        enable_critic=True,
        verifier_chain=_FakeAtomicVerifierChain(),
        critic_chain=_EchoAtomicCriticChain(),
        repair_chain=_FakeAtomicRepairChain(),
        provider_max_attempts=1,
    )

    record = _read_jsonl(output_path)[0]
    assert result["summary"]["pass_repaired_count"] == 1
    assert result["summary"]["hold_count"] == 0
    assert record["route"] == "pass_repaired"
    assert record["repair_attempted"] is True
    assert record["changed_fields"] == ["hidden_issues"]
    assert record["repaired_candidate"]["hidden_issues"] == []
    assert record["repair_scope_violations"] == []
    assert record["deterministic_list_repairs"][0]["proposal_changed"] is False
    assert record["initial_claim_ledger"]["claim_ledger_hash"] != record["final_claim_ledger"]["claim_ledger_hash"]
    assert record["runtime_metadata"]["call_count"] == 5
    assert [item["call_stage"] for item in record["stage_runtime"]] == [
        "initial_verifier",
        "initial_critic",
        "repair",
        "final_verifier",
        "final_critic",
    ]
    assert result["summary"]["atomic_critic_enabled"] is True
    assert result["summary"]["atomic_verifier_output_schema_hash"]
    assert result["summary"]["atomic_repair_output_schema_hash"]
    assert result["summary"]["runtime_profile"]["verifier_output_schema_hash"]
    assert json.loads(checkpoint_path.read_text(encoding="utf-8"))["stage"] == "atomic_verify_repair"
    assert json.loads(bundle_path.read_text(encoding="utf-8"))["stage"] == "atomic_verify_repair"


def test_atomic_verify_repair_runner_rejects_completed_evidence_without_source(
    tmp_path: Path,
) -> None:
    evidence = _evidence(
        "evidence:atomic-missing-source",
        "candidate:atomic-missing-source",
        "Исходный вопрос",
    )
    evidence.pop("source_question_text_redacted")
    evidence["canonicalization_evidence_hash"] = "a" * 64
    evidence_path = tmp_path / "evidence.jsonl"
    output_path = tmp_path / "atomic.jsonl"
    _write_jsonl(evidence_path, [evidence])

    with pytest.raises(ValueError, match="requires imported evidence"):
        run_tg_qa_canonicalization_atomic_verify_repair_batch(
            evidence_path=evidence_path,
            output_path=output_path,
            summary_output_path=tmp_path / "summary.json",
            endpoint_url="https://redacted.test/v1/chat/completions",
            model_id="fixture-glm",
            atomic_run_id="atomic-run:missing-source",
            max_repairs=0,
            verifier_chain=_UnexpectedAtomicChain(),
        )

    assert not output_path.exists()


def test_atomic_model_runtime_registry_preserves_native_parameters() -> None:
    registry, registry_hash, registry_path = load_atomic_runtime_profile_registry()

    qwen = resolve_atomic_runtime_stage(
        registry,
        profile_id="opencode_go_qwen36_plus_structured_v1",
        stage="verifier",
        registry_hash=registry_hash,
    )
    kimi = resolve_atomic_runtime_stage(
        registry,
        profile_id="opencode_go_kimi_k26_reasoning_v1",
        stage="verifier",
        registry_hash=registry_hash,
    )
    kimi27 = resolve_atomic_runtime_stage(
        registry,
        profile_id="opencode_go_kimi_k27_code_reasoning_v1",
        stage="verifier",
        registry_hash=registry_hash,
    )
    qwen_max = resolve_atomic_runtime_stage(
        registry,
        profile_id="opencode_go_qwen37_max_reasoning_v1",
        stage="critic",
        registry_hash=registry_hash,
    )

    assert registry_path.is_file()
    assert registry.profile_set_version == "tg_question_canonicalization_atomic_models_v2"
    assert len(registry.profiles) == 20
    assert qwen["provider"] == "anthropic"
    assert qwen["parameter_transport"] == "anthropic_constructor"
    assert qwen["structured_output_method"] == "function_calling"
    assert qwen["request_parameters"] == {"thinking": {"type": "disabled"}}
    assert qwen["reasoning_mode"] == "disabled"
    assert qwen["max_tokens"] == 8192
    assert kimi["provider"] == "openai"
    assert kimi["request_parameters"] == {"reasoning": {"enabled": True}}
    assert kimi27["structured_output_method"] == "prompt_json"
    assert kimi27["structured_output_adapter_version"] == "atomic_prompt_json_strict_v1"
    assert kimi27["temperature"] is None
    assert qwen_max["provider"] == "anthropic"
    assert qwen_max["request_parameters"]["thinking"]["budget_tokens"] == 16384
    assert qwen["request_parameters_hash"] != kimi["request_parameters_hash"]


def test_atomic_qwen_two_step_registry_separates_reasoning_and_formatting() -> None:
    registry_path = (
        Path(__file__).resolve().parents[2]
        / "src/evaluation/runtime_profiles/"
        "tg_question_canonicalization_atomic_qwen_two_step_models_v1.json"
    )
    registry, registry_hash, _ = load_atomic_runtime_profile_registry(registry_path)

    qwen37 = resolve_atomic_runtime_stage(
        registry,
        profile_id="opencode_go_qwen37_plus_reasoning_two_step_v1",
        stage="verifier",
        registry_hash=registry_hash,
    )
    qwen36 = resolve_atomic_runtime_stage(
        registry,
        profile_id="opencode_go_qwen36_plus_reasoning_two_step_v1",
        stage="critic",
        registry_hash=registry_hash,
    )
    formatter = resolve_atomic_runtime_stage(
        registry,
        profile_id="opencode_go_deepseek_v4_flash_formatter_v1",
        stage="verifier",
        registry_hash=registry_hash,
    )

    assert registry.profile_set_version == (
        "tg_question_canonicalization_atomic_qwen_two_step_models_v1"
    )
    assert len(registry.profiles) == 3
    assert qwen37["reasoning_mode"] == "enabled"
    assert qwen37["structured_output_method"] == "prompt_json"
    assert qwen37["request_parameters"] == {
        "thinking": {"type": "enabled", "budget_tokens": 16384}
    }
    assert qwen36["reasoning_mode"] == "enabled"
    assert formatter["reasoning_mode"] == "disabled"
    assert formatter["request_parameters"] == {"thinking": {"type": "disabled"}}


def test_atomic_no_reasoning_candidate_registry_is_explicit_and_immutable() -> None:
    registry_path = (
        Path(__file__).resolve().parents[2]
        / "src/evaluation/runtime_profiles/"
        "tg_question_canonicalization_atomic_no_reasoning_candidates_v1.json"
    )
    registry, registry_hash, _ = load_atomic_runtime_profile_registry(registry_path)
    verifier = resolve_atomic_runtime_stage(
        registry,
        profile_id="opencode_go_glm52_no_reasoning_v1",
        stage="verifier",
        registry_hash=registry_hash,
    )

    assert registry_hash == (
        "9031e81af8fa98e904940a4de9f7aa0ca46bfc99a5970543dbaffc071b85006c"
    )
    assert registry.profile_set_version == (
        "tg_question_canonicalization_atomic_no_reasoning_candidates_v1"
    )
    assert verifier["model_id"] == "glm-5.2"
    assert verifier["reasoning_mode"] == "disabled"
    assert verifier["structured_output_method"] == "json_schema"
    assert verifier["request_parameters"] == {"thinking": {"type": "disabled"}}


def test_atomic_glm52_escalation_registry_separates_first_pass_and_critic() -> None:
    registry_path = (
        Path(__file__).resolve().parents[2]
        / "src/evaluation/runtime_profiles/"
        "tg_question_canonicalization_atomic_glm52_escalation_v1.json"
    )
    registry, registry_hash, _ = load_atomic_runtime_profile_registry(registry_path)
    verifier = resolve_atomic_runtime_stage(
        registry,
        profile_id="opencode_go_glm52_no_reasoning_v1",
        stage="verifier",
        registry_hash=registry_hash,
    )
    critic = resolve_atomic_runtime_stage(
        registry,
        profile_id="opencode_go_glm52_reasoning_v1",
        stage="critic",
        registry_hash=registry_hash,
    )
    formatter = resolve_atomic_runtime_stage(
        registry,
        profile_id="opencode_go_deepseek_v4_flash_formatter_v1",
        stage="critic",
        registry_hash=registry_hash,
    )

    assert registry_hash == (
        "308aa001891f118e105b9b787a833318b93da63e08e60efa46cdcd4d4b948c6a"
    )
    assert verifier["reasoning_mode"] == "disabled"
    assert verifier["max_tokens"] == 8192
    assert critic["reasoning_mode"] == "enabled"
    assert critic["max_tokens"] == 32768
    assert formatter["model_id"] == "deepseek-v4-flash"
    assert formatter["reasoning_mode"] == "disabled"


def test_atomic_mixed_critic_registry_preserves_recorded_roles() -> None:
    registry_path = (
        Path(__file__).resolve().parents[2]
        / "src/evaluation/runtime_profiles/"
        "tg_question_canonicalization_atomic_glm52_qwen37_critic_v1.json"
    )
    registry, registry_hash, _ = load_atomic_runtime_profile_registry(registry_path)

    verifier = resolve_atomic_runtime_stage(
        registry,
        profile_id="opencode_go_glm52_reasoning_v1",
        stage="verifier",
        registry_hash=registry_hash,
    )
    critic = resolve_atomic_runtime_stage(
        registry,
        profile_id="opencode_go_qwen37_plus_reasoning_two_step_v1",
        stage="critic",
        registry_hash=registry_hash,
    )
    formatter = resolve_atomic_runtime_stage(
        registry,
        profile_id="opencode_go_deepseek_v4_flash_formatter_v1",
        stage="critic",
        registry_hash=registry_hash,
    )

    assert registry_hash == (
        "be4da1b7fc6823e7544180683bd2361ecc25a25248d903d3bb1933f6e1d8caaa"
    )
    assert verifier["model_id"] == "glm-5.2"
    assert verifier["reasoning_mode"] == "enabled"
    assert critic["model_id"] == "qwen3.7-plus"
    assert critic["reasoning_mode"] == "enabled"
    assert formatter["model_id"] == "deepseek-v4-flash"
    assert formatter["reasoning_mode"] == "disabled"


def test_atomic_v5_prompt_profiles_separate_questions_from_legal_relations() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    verifier = _read_json(
        repo_root
        / "src/evaluation/prompt_profiles/tg_question_canonicalization_atomic_verifier_v5.json"
    )
    critic = _read_json(
        repo_root
        / "src/evaluation/prompt_profiles/tg_question_canonicalization_atomic_critic_v5.json"
    )

    assert verifier["prompt_version"] == "tg_question_canonicalization_atomic_verifier_v5"
    assert critic["prompt_version"] == "tg_question_canonicalization_atomic_critic_v5"
    for profile in (verifier, critic):
        instruction = profile["reasoning_system_instruction"]
        assert "FIELD ROLES" in instruction
        assert "ACTIVITY_GATE: grounded|not_grounded|unresolved" in instruction
        assert "CHILD_BENEFIT_JOBCENTER" in instruction
        assert "FOREIGN_TAX_MECHANISM" in instruction
        assert "IDENTIFIER_REGISTRATION" in instruction
        assert "facts and desired_outcome preserve" in instruction
        assert "tg-question-canonicalization-task:" not in json.dumps(profile)
        assert "without performing a new legal analysis" in profile["formatter_system_instruction"]


def test_atomic_v6_prompt_profiles_audit_compound_dependencies_and_exact_quotes() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    verifier = _read_json(
        repo_root
        / "src/evaluation/prompt_profiles/tg_question_canonicalization_atomic_verifier_v6.json"
    )
    critic = _read_json(
        repo_root
        / "src/evaluation/prompt_profiles/tg_question_canonicalization_atomic_critic_v6.json"
    )

    assert verifier["prompt_version"] == "tg_question_canonicalization_atomic_verifier_v6"
    assert critic["prompt_version"] == "tg_question_canonicalization_atomic_critic_v6"
    for profile in (verifier, critic):
        reasoning_instruction = profile["reasoning_system_instruction"]
        direct_instruction = profile["system_instruction"]
        assert "asserts a dependency rather than neutral context" in reasoning_instruction
        assert "Never join fragments with + or ellipsis" in reasoning_instruction
        assert "one contiguous exact quote per span" in direct_instruction
        assert "eligibility when, without, or при a Jobcenter status" in direct_instruction
        assert "tg-question-canonicalization-task:" not in json.dumps(profile)


def test_atomic_compact_memo_profiles_deduplicate_quotes_and_preserve_field_roles() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    v7 = _read_json(
        repo_root
        / "src/evaluation/prompt_profiles/tg_question_canonicalization_atomic_verifier_v7_compact_memo.json"
    )
    v8 = _read_json(
        repo_root
        / "src/evaluation/prompt_profiles/tg_question_canonicalization_atomic_verifier_v8_compact_memo.json"
    )

    assert v7["prompt_version"] == (
        "tg_question_canonicalization_atomic_verifier_v7_compact_memo"
    )
    assert v8["prompt_version"] == (
        "tg_question_canonicalization_atomic_verifier_v8_compact_memo"
    )
    for profile in (v7, v8):
        reasoning_instruction = profile["reasoning_system_instruction"]
        formatter_instruction = profile["formatter_system_instruction"]
        assert "QUOTE Q<number>" in reasoning_instruction
        assert "Reuse one quote id across claims" in reasoning_instruction
        assert "replace claim quote-id references" in formatter_instruction
        assert "tg-question-canonicalization-task:" not in json.dumps(profile)
    assert "controlled classifications" in v8["reasoning_system_instruction"]
    assert "authority's proper name" in v8["reasoning_system_instruction"]
    assert "exclusion_reason=none" in v8["reasoning_system_instruction"]


def test_atomic_runtime_resolves_explicit_no_reasoning_formatter() -> None:
    stage_runtimes, registry_metadata = canonicalization._resolve_atomic_stage_runtimes(
        provider="openai",
        endpoint_url="",
        model_id="",
        structured_output_method="json_schema",
        timeout_seconds=300,
        verifier_max_tokens=32768,
        critic_max_tokens=32768,
        repair_max_tokens=16384,
        extra_body=None,
        runtime_profile_registry_path=None,
        verifier_runtime_profile_id="opencode_go_minimax_m3_reasoning_v1",
        critic_runtime_profile_id="",
        repair_runtime_profile_id="opencode_go_deepseek_v4_flash_formatter_v1",
        verifier_formatter_runtime_profile_id=(
            "opencode_go_deepseek_v4_flash_formatter_v1"
        ),
        critic_formatter_runtime_profile_id="",
        repair_formatter_runtime_profile_id="",
    )

    verifier = stage_runtimes["verifier"]
    repair = stage_runtimes["repair"]
    verifier_identity = canonicalization._atomic_stage_runtime_identity(verifier)
    assert verifier["execution_mode"] == "reasoning_then_formatter"
    assert verifier["formatter_output_contract"] == (
        "atomic_verification_quotes_to_offsets_v1"
    )
    assert verifier["model_id"] == "minimax-m3"
    assert verifier["formatter_runtime"]["model_id"] == "deepseek-v4-flash"
    assert verifier["formatter_runtime"]["reasoning_mode"] == "disabled"
    assert verifier_identity["formatter_runtime"]["profile_id"] == (
        "opencode_go_deepseek_v4_flash_formatter_v1"
    )
    assert "endpoint_url" not in verifier_identity
    assert "endpoint_url" not in verifier_identity["formatter_runtime"]
    assert repair["execution_mode"] == "direct_structured"
    assert repair["reasoning_mode"] == "disabled"
    assert registry_metadata["formatter_profile_ids"] == {
        "verifier": "opencode_go_deepseek_v4_flash_formatter_v1"
    }

    with pytest.raises(ValueError, match="must declare reasoning_mode=disabled"):
        canonicalization._resolve_atomic_stage_runtimes(
            provider="openai",
            endpoint_url="",
            model_id="",
            structured_output_method="json_schema",
            timeout_seconds=300,
            verifier_max_tokens=32768,
            critic_max_tokens=32768,
            repair_max_tokens=16384,
            extra_body=None,
            runtime_profile_registry_path=None,
            verifier_runtime_profile_id="opencode_go_minimax_m3_reasoning_v1",
            critic_runtime_profile_id="",
            repair_runtime_profile_id="",
            verifier_formatter_runtime_profile_id="opencode_go_glm52_reasoning_v1",
            critic_formatter_runtime_profile_id="",
            repair_formatter_runtime_profile_id="",
        )


def test_atomic_two_step_retries_only_formatter_and_retains_memo() -> None:
    from langchain_core.messages import AIMessage

    class _ReasoningChain:
        invocation_count = 0

        def invoke(self, payload: Mapping[str, Any]) -> AIMessage:
            self.invocation_count += 1
            assert "atomic_verifier_payload" in payload
            return AIMessage(
                content=(
                    "ROUTE: pass\nCLAIM: claim:1\nSUPPORT: explicit\n"
                    "RELATION_KIND: source_fact\nSOURCE_QUOTE: факт\n"
                    "CORRECTION:\nREASON: stated"
                )
            )

    class _FormatterChain:
        invocation_count = 0
        payloads: list[dict[str, Any]] = []

        def invoke(self, payload: Mapping[str, Any]) -> dict[str, Any]:
            self.invocation_count += 1
            self.payloads.append(dict(payload))
            if self.invocation_count == 1:
                return {
                    "raw": AIMessage(content="not-json"),
                    "parsed": None,
                    "parsing_error": "fixture-invalid-json",
                }
            return {
                "raw": AIMessage(content='{"route":"pass"}'),
                "parsed": canonicalization.AtomicVerificationPayload(
                    route="pass",
                    claim_verdicts=[],
                    short_reason="fixture",
                ),
                "parsing_error": None,
            }

    reasoning = _ReasoningChain()
    formatter = _FormatterChain()
    runner = canonicalization.AtomicTwoStepRunner(
        reasoning_runner=reasoning,
        formatter_runner=formatter,
        reasoning_runtime_profile={"profile_id": "reasoner", "component_role": "reasoning"},
        formatter_runtime_profile={"profile_id": "formatter", "component_role": "formatter"},
    )

    raw, parsed, attempts, retries = canonicalization._atomic_invoke_with_retry(
        runner,
        {"atomic_verifier_payload": "fixture-payload"},
        parser=canonicalization._atomic_verification_from_structured_output,
        call_stage="initial_verifier",
        provider_max_attempts=2,
        provider_retry_delay_seconds=0,
    )

    assert reasoning.invocation_count == 1
    assert formatter.invocation_count == 2
    assert retries == 1
    assert parsed.route == "pass"
    assert [item["call_stage"] for item in attempts] == [
        "initial_verifier_reasoning",
        "initial_verifier_formatter",
        "initial_verifier_formatter",
    ]
    assert attempts[1]["invalid_output"]["text"] == "not-json"
    assert formatter.payloads[0]["atomic_stage_payload"] == "fixture-payload"
    assert formatter.payloads[0]["atomic_reasoning_memo"].startswith("ROUTE: pass")
    assert formatter.payloads[0]["atomic_formatter_validation_feedback"] == ""
    assert "fixture-invalid-json" in formatter.payloads[1][
        "atomic_formatter_validation_feedback"
    ]
    memo_artifact = canonicalization._atomic_reasoning_memo_artifact(raw)
    assert memo_artifact is not None
    assert memo_artifact["memo"].startswith("ROUTE: pass")
    assert memo_artifact["memo_character_count"] > 20


def test_atomic_formatter_quotes_receive_deterministic_offsets() -> None:
    source = "Начало. Точный фрагмент источника. Конец."
    raw_result = canonicalization.AtomicFormatterVerificationPayload(
        route="pass",
        claim_verdicts=[
            canonicalization.AtomicFormatterClaimVerdictPayload(
                claim_id="claim:1",
                support="explicit",
                relation_kind="source_fact",
                materiality="medium",
                source_quotes=["Точный фрагмент источника"],
                short_reason="stated",
            )
        ],
        short_reason="complete",
    )

    parsed = canonicalization._atomic_verification_from_formatter_output(
        raw_result,
        json.dumps({"source_question_text_redacted": source}, ensure_ascii=False),
    )

    span = parsed.claim_verdicts[0].source_spans[0]
    assert span.start == source.index("Точный фрагмент источника")
    assert span.end == span.start + len(span.quote)
    assert source[span.start : span.end] == span.quote

    ambiguous = canonicalization._atomic_verification_from_formatter_output(
        canonicalization.AtomicFormatterVerificationPayload(
            route="pass",
            claim_verdicts=[
                canonicalization.AtomicFormatterClaimVerdictPayload(
                    claim_id="claim:1",
                    support="explicit",
                    relation_kind="source_fact",
                    source_quotes=["повтор"],
                    short_reason="stated",
                )
            ],
        ),
        json.dumps(
            {"source_question_text_redacted": "повтор и ещё повтор"},
            ensure_ascii=False,
        ),
    )
    assert ambiguous.claim_verdicts[0].source_spans == []
    assert ambiguous.claim_verdicts[0].support == "unresolved"
    assert ambiguous.route == "hold"


def test_atomic_cost_estimate_marks_missing_and_partial_prices() -> None:
    calls = [
        {
            "call_stage": "initial_verifier",
            "input_tokens": 1000,
            "output_tokens": 500,
        },
        {
            "call_stage": "initial_critic",
            "input_tokens": 1000,
            "output_tokens": 500,
        },
    ]
    stage_runtimes = {
        "verifier": {"pricing_snapshot": {"note": "price unavailable"}},
        "critic": {
            "pricing_snapshot": {
                "input_usd_per_million": 1.0,
                "output_usd_per_million": 2.0,
            }
        },
    }

    partial = canonicalization._atomic_cost_estimate(calls, stage_runtimes)
    unpriced = canonicalization._atomic_cost_estimate(calls[:1], stage_runtimes)

    assert partial["estimated_uncached_cost_usd"] == 0.002
    assert partial["priced_attempt_count"] == 1
    assert partial["unpriced_attempt_count"] == 1
    assert partial["unpriced_reason_counts"] == {"token_rate_missing": 1}
    assert partial["cost_estimate_complete"] is False
    assert unpriced["estimated_uncached_cost_usd"] is None
    assert unpriced["cost_estimate_complete"] is False


def test_atomic_cost_estimate_prices_two_step_components_separately() -> None:
    calls = [
        {
            "call_stage": "initial_verifier_reasoning",
            "input_tokens": 1000,
            "output_tokens": 500,
        },
        {
            "call_stage": "initial_verifier_formatter",
            "input_tokens": 1500,
            "output_tokens": 200,
        },
    ]
    stage_runtimes = {
        "verifier": {
            "pricing_snapshot": {
                "input_usd_per_million": 1.0,
                "output_usd_per_million": 2.0,
            },
            "formatter_runtime": {
                "pricing_snapshot": {
                    "input_usd_per_million": 0.1,
                    "output_usd_per_million": 0.2,
                }
            },
        }
    }

    estimate = canonicalization._atomic_cost_estimate(calls, stage_runtimes)

    assert estimate["estimated_uncached_cost_usd"] == 0.00219
    assert estimate["estimated_uncached_cost_usd_by_stage"] == {
        "verifier_formatter": 0.00019,
        "verifier_reasoning": 0.002,
    }
    assert estimate["cost_estimate_complete"] is True


def test_atomic_runner_binds_distinct_stage_runtime_profiles(tmp_path: Path) -> None:
    source = "Автор спрашивает, положена ли выплата на ребёнка."
    evidence = _evidence("evidence:atomic-profiles", "candidate:atomic-profiles", source)
    evidence["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(
        evidence
    )
    evidence_path = tmp_path / "evidence.jsonl"
    output_path = tmp_path / "atomic.jsonl"
    summary_path = tmp_path / "atomic_summary.json"
    _write_jsonl(evidence_path, [evidence])

    result = run_tg_qa_canonicalization_atomic_verify_repair_batch(
        evidence_path=evidence_path,
        output_path=output_path,
        summary_output_path=summary_path,
        atomic_run_id="atomic-run:profiles-fixture",
        verifier_runtime_profile_id="opencode_go_deepseek_v4_flash_reasoning_v1",
        critic_runtime_profile_id="opencode_go_qwen36_plus_structured_v1",
        max_repairs=0,
        enable_critic=True,
        critic_policy="before_pass",
        verifier_chain=_PassAtomicVerifierChain(),
        critic_chain=_EchoAtomicCriticChain(),
        provider_max_attempts=1,
    )

    record = _read_jsonl(output_path)[0]
    stage_profiles = result["summary"]["stage_runtime_profiles"]
    assert result["summary"]["pass_count"] == 1
    assert stage_profiles["verifier"]["model_id"] == "deepseek-v4-flash"
    assert stage_profiles["critic"]["model_id"] == "qwen3.6-plus"
    assert record["stage_runtime"][0]["stage_runtime_profile"]["profile_id"] == (
        "opencode_go_deepseek_v4_flash_reasoning_v1"
    )
    assert record["stage_runtime"][1]["stage_runtime_profile"]["profile_id"] == (
        "opencode_go_qwen36_plus_structured_v1"
    )
    assert record["runtime_profile_hash"] == result["summary"]["runtime_profile_hash"]
    assert result["summary"]["invocation_metrics_scope"] == (
        "records_processed_in_current_invocation"
    )
    assert result["summary"]["cumulative_output_metrics"]["record_count"] == 1
    assert result["summary"]["cumulative_output_metrics"]["route_counts"] == {
        "pass": 1
    }


def test_atomic_summary_separates_resumed_invocation_from_cumulative_output(
    tmp_path: Path,
) -> None:
    evidence_records = [
        _evidence(
            f"evidence:atomic-summary-{index}",
            f"candidate:atomic-summary-{index}",
            f"Автор спрашивает о праве на выплату {index}.",
        )
        for index in range(2)
    ]
    for evidence in evidence_records:
        evidence["canonicalization_evidence_hash"] = (
            canonicalization._canonicalization_evidence_hash(evidence)
        )
    evidence_path = tmp_path / "evidence.jsonl"
    output_path = tmp_path / "atomic.jsonl"
    summary_path = tmp_path / "atomic_summary.json"
    _write_jsonl(evidence_path, evidence_records)

    common = {
        "evidence_path": evidence_path,
        "output_path": output_path,
        "summary_output_path": summary_path,
        "endpoint_url": "https://redacted.test/v1/chat/completions",
        "model_id": "fixture-glm",
        "atomic_run_id": "atomic-run:cumulative-summary-fixture",
        "max_items": 1,
        "max_repairs": 0,
        "provider_max_attempts": 1,
    }
    first = run_tg_qa_canonicalization_atomic_verify_repair_batch(
        **common,
        verifier_chain=_PassAtomicVerifierChain(),
    )
    second = run_tg_qa_canonicalization_atomic_verify_repair_batch(
        **common,
        verifier_chain=_PassAtomicVerifierChain(),
    )

    assert first["summary"]["processed_count"] == 1
    assert first["summary"]["cumulative_output_metrics"]["record_count"] == 1
    assert second["summary"]["processed_count"] == 1
    assert second["summary"]["resumed_existing_count"] == 1
    assert second["summary"]["cumulative_output_metrics"]["record_count"] == 2
    assert second["summary"]["cumulative_output_metrics"]["status_counts"] == {
        "completed": 2
    }
    assert second["summary"]["cumulative_output_metrics"]["route_counts"] == {
        "pass": 2
    }
    assert len(_read_jsonl(output_path)) == 2


def test_atomic_cumulative_metrics_tolerate_invalid_retry_values() -> None:
    metrics = canonicalization._atomic_cumulative_output_metrics(
        [
            {
                "status": "completed",
                "route": "hold",
                "provider_retry_count": "2",
            },
            {
                "status": "failed",
                "route": "revise",
                "provider_retry_count": "unknown",
            },
        ]
    )

    assert metrics["record_count"] == 2
    assert metrics["provider_retry_count"] == 2


def test_atomic_runner_persists_two_step_memo_and_component_calls(tmp_path: Path) -> None:
    from langchain_core.messages import AIMessage

    source = "Автор спрашивает, положена ли выплата на ребёнка."
    evidence = _evidence("evidence:atomic-two-step", "candidate:atomic-two-step", source)
    evidence["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(
        evidence
    )
    evidence_path = tmp_path / "evidence.jsonl"
    output_path = tmp_path / "atomic.jsonl"
    summary_path = tmp_path / "atomic_summary.json"
    _write_jsonl(evidence_path, [evidence])

    class _ReasoningChain:
        def invoke(self, payload: Mapping[str, Any]) -> AIMessage:
            assert "atomic_verifier_payload" in payload
            return AIMessage(content="ROUTE: pass\nAll claims are explicit in the fixture source.")

    class _FormatterAdapter:
        def __init__(self) -> None:
            self.delegate = _PassAtomicVerifierChain()

        def invoke(self, payload: Mapping[str, Any]) -> canonicalization.AtomicVerificationPayload:
            assert payload["atomic_reasoning_memo"].startswith("ROUTE: pass")
            return self.delegate.invoke(
                {"atomic_verifier_payload": payload["atomic_stage_payload"]}
            )

    verifier = canonicalization.AtomicTwoStepRunner(
        reasoning_runner=_ReasoningChain(),
        formatter_runner=_FormatterAdapter(),
        reasoning_runtime_profile={"profile_id": "fixture-reasoner"},
        formatter_runtime_profile={"profile_id": "fixture-formatter"},
    )
    result = run_tg_qa_canonicalization_atomic_verify_repair_batch(
        evidence_path=evidence_path,
        output_path=output_path,
        summary_output_path=summary_path,
        atomic_run_id="atomic-run:two-step-fixture",
        verifier_runtime_profile_id="opencode_go_minimax_m3_reasoning_v1",
        verifier_formatter_runtime_profile_id=(
            "opencode_go_deepseek_v4_flash_formatter_v1"
        ),
        max_repairs=0,
        verifier_chain=verifier,
        provider_max_attempts=1,
    )

    record = _read_jsonl(output_path)[0]
    assert record["route"] == "pass"
    assert record["initial_verifier_reasoning_memo"]["memo"].startswith("ROUTE: pass")
    assert [item["call_stage"] for item in record["stage_runtime"]] == [
        "initial_verifier_reasoning",
        "initial_verifier_formatter",
    ]
    assert result["summary"]["execution_modes_by_stage"] == {
        "verifier": "reasoning_then_formatter"
    }
    assert result["summary"]["formatter_model_ids_by_stage"] == {
        "verifier": "deepseek-v4-flash"
    }
    assert result["summary"]["stage_runtime_profiles"]["verifier"][
        "formatter_runtime"
    ]["reasoning_mode"] == "disabled"


def test_atomic_before_pass_policy_skips_critic_for_primary_revise(tmp_path: Path) -> None:
    source = "Автор спрашивает, полагаются ли выплаты на ребёнка."
    evidence = _evidence("evidence:atomic-critic-policy", "candidate:atomic-critic-policy", source)
    evidence["hidden_issues"] = ["Право зависит от регистрации в Jobcenter"]
    evidence["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(
        evidence
    )
    evidence_path = tmp_path / "evidence.jsonl"
    output_path = tmp_path / "atomic.jsonl"
    summary_path = tmp_path / "atomic_summary.json"
    _write_jsonl(evidence_path, [evidence])

    result = run_tg_qa_canonicalization_atomic_verify_repair_batch(
        evidence_path=evidence_path,
        output_path=output_path,
        summary_output_path=summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-glm",
        atomic_run_id="atomic-run:critic-policy-fixture",
        max_repairs=0,
        enable_critic=True,
        critic_policy="before_pass",
        verifier_chain=_FakeAtomicVerifierChain(),
        critic_chain=_UnexpectedAtomicChain(),
        provider_max_attempts=1,
    )

    record = _read_jsonl(output_path)[0]
    assert result["summary"]["hold_count"] == 1
    assert result["summary"]["atomic_critic_policy"] == "before_pass"
    assert record["initial_primary_controller"]["route"] == "revise"
    assert record["initial_critic_executed"] is False
    assert record["initial_critic_skipped_reason"] == (
        "primary_route_nonpass_under_before_pass_policy"
    )
    assert [item["call_stage"] for item in record["stage_runtime"]] == ["initial_verifier"]


def test_atomic_runner_normalizes_list_item_replacement_to_claim_scope(tmp_path: Path) -> None:
    source = "Автор спрашивает, полагаются ли выплаты на ребёнка."
    evidence = _evidence("evidence:atomic-scope", "candidate:atomic-scope", source)
    evidence.update(
        {
            "desired_outcome": "Установить право на выплаты на ребёнка",
            "authority_context": [],
            "hidden_issues": ["Право зависит от регистрации в Jobcenter"],
        }
    )
    evidence["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(evidence)
    evidence_path = tmp_path / "evidence.jsonl"
    output_path = tmp_path / "atomic.jsonl"
    summary_path = tmp_path / "atomic_summary.json"
    _write_jsonl(evidence_path, [evidence])
    verifier = _FakeAtomicVerifierChain()

    run_tg_qa_canonicalization_atomic_verify_repair_batch(
        evidence_path=evidence_path,
        output_path=output_path,
        summary_output_path=summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-glm",
        atomic_run_id="atomic-run:scope-fixture",
        verifier_chain=verifier,
        repair_chain=_ReplacingAtomicRepairChain(),
        provider_max_attempts=1,
    )

    record = _read_jsonl(output_path)[0]
    assert verifier.invocation_count == 2
    assert record["route"] == "pass_repaired"
    assert record["repair_scope_violations"] == []
    assert record["repaired_candidate"]["hidden_issues"] == []
    assert record["deterministic_list_repairs"][0]["field_name"] == "hidden_issues"
    assert record["deterministic_list_repairs"][0]["provided_items"] == [
        "Право на выплаты на ребёнка"
    ]
    assert record["deterministic_list_repairs"][0]["proposal_changed"] is True


def test_atomic_runner_records_every_exhausted_output_attempt(tmp_path: Path) -> None:
    source = "Автор спрашивает о регистрации деятельности."
    evidence = _evidence("evidence:atomic-failed", "candidate:atomic-failed", source)
    evidence["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(evidence)
    evidence_path = tmp_path / "evidence.jsonl"
    output_path = tmp_path / "atomic.jsonl"
    summary_path = tmp_path / "atomic_summary.json"
    _write_jsonl(evidence_path, [evidence])

    result = run_tg_qa_canonicalization_atomic_verify_repair_batch(
        evidence_path=evidence_path,
        output_path=output_path,
        summary_output_path=summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-glm",
        atomic_run_id="atomic-run:failed-fixture",
        max_repairs=0,
        verifier_chain=_AlwaysInvalidAtomicVerifierChain(),
        provider_max_attempts=2,
        provider_retry_delay_seconds=0,
    )

    record = _read_jsonl(output_path)[0]
    assert record["status"] == "failed"
    assert record["failure_stage"] == "initial_verifier"
    assert record["provider_retry_count"] == 1
    assert record["runtime_metadata"]["call_count"] == 2
    assert record["runtime_metadata"]["attempts_used"] == 2
    assert [attempt["attempt_number"] for attempt in record["stage_runtime"]] == [1, 2]
    assert all(attempt["outcome"] == "failed" for attempt in record["stage_runtime"])
    assert result["summary"]["provider_retry_count"] == 1
    assert result["summary"]["provider_retry_exhausted_count"] == 1
    assert result["summary"]["runtime_profile"]["prompt_version"] == (
        "tg_question_canonicalization_atomic_verifier_v6"
    )
    assert result["summary"]["runtime_profile"]["critic_output_schema_hash"] == "disabled"
    assert result["summary"]["runtime_profile"]["repair_output_schema_hash"] == "disabled"


def test_atomic_runner_resumes_final_verifier_from_stage_checkpoint(tmp_path: Path) -> None:
    source = "Автор спрашивает, полагаются ли выплаты на ребёнка."
    evidence = _evidence("evidence:atomic-resume", "candidate:atomic-resume", source)
    evidence.update(
        {
            "facts": ["У автора есть ребёнок"],
            "desired_outcome": "Установить право на выплаты на ребёнка",
            "authority_context": [],
            "hidden_issues": ["Право зависит от регистрации в Jobcenter"],
        }
    )
    evidence["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(evidence)
    evidence_path = tmp_path / "evidence.jsonl"
    output_path = tmp_path / "atomic.jsonl"
    summary_path = tmp_path / "atomic_summary.json"
    stage_checkpoint_path = tmp_path / "atomic_stage_checkpoint.json"
    _write_jsonl(evidence_path, [evidence])

    with pytest.raises(KeyboardInterrupt):
        run_tg_qa_canonicalization_atomic_verify_repair_batch(
            evidence_path=evidence_path,
            output_path=output_path,
            summary_output_path=summary_path,
            endpoint_url="https://redacted.test/v1/chat/completions",
            model_id="fixture-glm",
            atomic_run_id="atomic-run:resume-fixture",
            stage_checkpoint_output_path=stage_checkpoint_path,
            verifier_chain=_InterruptingFinalAtomicVerifierChain(),
            repair_chain=_FakeAtomicRepairChain(),
            provider_max_attempts=1,
        )

    interrupted_checkpoint = json.loads(stage_checkpoint_path.read_text(encoding="utf-8"))
    assert interrupted_checkpoint["stage"] == "repair_completed"
    assert output_path.read_text(encoding="utf-8") == ""

    final_verifier = _PassAtomicVerifierChain()
    result = run_tg_qa_canonicalization_atomic_verify_repair_batch(
        evidence_path=evidence_path,
        output_path=output_path,
        summary_output_path=summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-glm",
        atomic_run_id="atomic-run:resume-fixture",
        stage_checkpoint_output_path=stage_checkpoint_path,
        verifier_chain=final_verifier,
        repair_chain=_FakeAtomicRepairChain(),
        provider_max_attempts=1,
    )

    record = _read_jsonl(output_path)[0]
    assert final_verifier.invocation_count == 1
    assert record["resumed_stage_checkpoint"] == "repair_completed"
    assert record["route"] == "pass_repaired"
    assert record["runtime_metadata"]["call_count"] == 3
    assert result["summary"]["stage_checkpoint_output_path"] == str(stage_checkpoint_path)
    completed_checkpoint = json.loads(stage_checkpoint_path.read_text(encoding="utf-8"))
    assert completed_checkpoint["stage"] == "item_completed"


def test_atomic_runner_resumes_final_critic_without_repeating_final_verifier(tmp_path: Path) -> None:
    source = "Автор спрашивает, полагаются ли выплаты на ребёнка."
    evidence = _evidence("evidence:atomic-critic-resume", "candidate:atomic-critic-resume", source)
    evidence.update(
        {
            "facts": ["У автора есть ребёнок"],
            "desired_outcome": "Установить право на выплаты на ребёнка",
            "authority_context": [],
            "hidden_issues": ["Право зависит от регистрации в Jobcenter"],
        }
    )
    evidence["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(evidence)
    evidence_path = tmp_path / "evidence.jsonl"
    output_path = tmp_path / "atomic.jsonl"
    summary_path = tmp_path / "atomic_summary.json"
    stage_checkpoint_path = tmp_path / "atomic_stage_checkpoint.json"
    _write_jsonl(evidence_path, [evidence])

    with pytest.raises(KeyboardInterrupt):
        run_tg_qa_canonicalization_atomic_verify_repair_batch(
            evidence_path=evidence_path,
            output_path=output_path,
            summary_output_path=summary_path,
            endpoint_url="https://redacted.test/v1/chat/completions",
            model_id="fixture-glm",
            atomic_run_id="atomic-run:critic-resume-fixture",
            enable_critic=True,
            stage_checkpoint_output_path=stage_checkpoint_path,
            verifier_chain=_FakeAtomicVerifierChain(),
            critic_chain=_InterruptingFinalAtomicCriticChain(),
            repair_chain=_FakeAtomicRepairChain(),
            provider_max_attempts=1,
        )

    interrupted_checkpoint = json.loads(stage_checkpoint_path.read_text(encoding="utf-8"))
    assert interrupted_checkpoint["stage"] == "final_primary_verified"
    assert output_path.read_text(encoding="utf-8") == ""

    final_critic = _EchoAtomicCriticChain()
    result = run_tg_qa_canonicalization_atomic_verify_repair_batch(
        evidence_path=evidence_path,
        output_path=output_path,
        summary_output_path=summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-glm",
        atomic_run_id="atomic-run:critic-resume-fixture",
        enable_critic=True,
        stage_checkpoint_output_path=stage_checkpoint_path,
        verifier_chain=_UnexpectedAtomicChain(),
        critic_chain=final_critic,
        repair_chain=_UnexpectedAtomicChain(),
        provider_max_attempts=1,
    )

    record = _read_jsonl(output_path)[0]
    assert record["resumed_stage_checkpoint"] == "final_primary_verified"
    assert record["route"] == "pass_repaired"
    assert record["runtime_metadata"]["call_count"] == 5
    assert result["summary"]["pass_repaired_count"] == 1


def test_live_runner_shapes_stream_results_with_fake_structured_chains(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    qwen_summary_path = tmp_path / "qwen_summary.json"
    qwen_checkpoint_path = tmp_path / "qwen_checkpoint.json"
    qwen_run_bundle_path = tmp_path / "qwen_run_bundle.json"
    evidence_path = tmp_path / "evidence.jsonl"
    manifest_path = tmp_path / "manifest.json"
    verifier_results_path = tmp_path / "verifier_results.jsonl"
    verifier_summary_path = tmp_path / "verifier_summary.json"
    _write_jsonl(
        candidates_path,
        [_candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", "m1")],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="law_or_topic",
    )
    batch_item = _read_jsonl(batch_path)[0]

    qwen_result = run_tg_qa_canonicalization_llm_batch(
        batch_path=batch_path,
        output_path=qwen_results_path,
        summary_output_path=qwen_summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-qwen",
        canonicalization_run_id="tg-question-canonicalization-run:fixture",
        checkpoint_output_path=qwen_checkpoint_path,
        run_bundle_output_path=qwen_run_bundle_path,
        chain=_FakeCanonicalizationChain(batch_item),
    )
    import_tg_qa_canonicalization_results(
        batch_path=batch_path,
        result_path=qwen_results_path,
        output_path=evidence_path,
        manifest_output_path=manifest_path,
        canonicalization_run_id="tg-question-canonicalization-run:fixture",
    )
    verifier_result = run_tg_qa_canonicalization_verifier_batch(
        evidence_path=evidence_path,
        output_path=verifier_results_path,
        summary_output_path=verifier_summary_path,
        endpoint_url="https://redacted.test/anthropic",
        model_id="fixture-minimax",
        verifier_run_id="tg-question-canonicalization-verifier-run:fixture",
        chain=_FakeVerifierChain(),
    )

    qwen_records = _read_jsonl(qwen_results_path)
    verifier_records = _read_jsonl(verifier_results_path)
    assert qwen_result["summary"]["completed_count"] == 1
    assert qwen_result["summary"]["runtime_metadata_record_count"] == 1
    assert qwen_result["summary"]["usage_metadata_record_count"] == 0
    assert qwen_records[0]["task_id"] == batch_item["task_id"]
    assert qwen_records[0]["backend"] == "opencode"
    assert qwen_records[0]["runtime_metadata"]["attempts_used"] == 1
    assert qwen_records[0]["runtime_metadata"]["llm_usage_available"] is False
    assert qwen_records[0]["runtime_metadata"]["request_duration_seconds"] >= 0
    qwen_checkpoint = json.loads(qwen_checkpoint_path.read_text(encoding="utf-8"))
    qwen_bundle = json.loads(qwen_run_bundle_path.read_text(encoding="utf-8"))
    assert qwen_checkpoint["runtime_profile_hash"] == qwen_records[0]["runtime_profile_hash"]
    assert qwen_bundle["result_output_path"] == str(qwen_results_path)
    assert qwen_bundle["checkpoint_output_path"] == str(qwen_checkpoint_path)
    assert verifier_result["summary"]["completed_count"] == 1
    assert verifier_result["summary"]["runtime_metadata_record_count"] == 1
    assert verifier_records[0]["verdict"] == "pass"
    assert verifier_records[0]["suggested_action"] == "accept"
    assert verifier_records[0]["runtime_metadata"]["attempts_used"] == 1


def test_langchain_review_prompt_builders_accept_literal_json_few_shots() -> None:
    canonicalization_model = _StructuredOutputOnlyChatModel()
    verifier_model = _StructuredOutputOnlyChatModel()
    adjudication_model = _StructuredOutputOnlyChatModel()
    atomic_verifier_model = _StructuredOutputOnlyChatModel()
    atomic_critic_model = _StructuredOutputOnlyChatModel()
    atomic_repair_model = _StructuredOutputOnlyChatModel()
    pair_judge_model = _StructuredOutputOnlyChatModel()
    legal_intent_extractor_model = _StructuredOutputOnlyChatModel()
    canonicalization_chain = build_langchain_canonicalization_chain(canonicalization_model, method="json_mode")
    verifier_chain = build_langchain_verifier_chain(verifier_model, method="function_calling")
    adjudication_chain = build_langchain_adjudication_chain(
        adjudication_model,
        method="json_mode",
    )
    atomic_verifier_chain = build_langchain_canonicalization_atomic_verifier_chain(
        atomic_verifier_model,
        method="json_mode",
    )
    atomic_critic_chain = build_langchain_canonicalization_atomic_critic_chain(
        atomic_critic_model,
        method="json_mode",
    )
    atomic_repair_chain = build_langchain_canonicalization_atomic_repair_chain(
        atomic_repair_model,
        method="json_mode",
    )
    pair_judge_chain = build_langchain_legal_intent_pair_judge_chain(
        pair_judge_model,
        method="json_mode",
    )
    legal_intent_extractor_chain = build_langchain_legal_intent_extractor_chain(
        legal_intent_extractor_model,
        method="json_mode",
    )

    assert canonicalization_chain is not None
    assert verifier_chain is not None
    assert adjudication_chain is not None
    assert atomic_verifier_chain is not None
    assert atomic_critic_chain is not None
    assert atomic_repair_chain is not None
    assert pair_judge_chain is not None
    assert legal_intent_extractor_chain is not None
    assert canonicalization_model.include_raw is True
    assert verifier_model.include_raw is True
    assert adjudication_model.include_raw is True
    assert atomic_verifier_model.include_raw is True
    assert atomic_critic_model.include_raw is True
    assert atomic_repair_model.include_raw is True
    assert pair_judge_model.include_raw is True
    assert legal_intent_extractor_model.include_raw is True


def test_operator_runtime_metadata_extracts_langchain_usage() -> None:
    class _RawMessage:
        usage_metadata = {
            "input_tokens": 101,
            "output_tokens": 33,
            "total_tokens": 134,
            "output_token_details": {"reasoning": 17},
        }
        response_metadata = {
            "finish_reason": "stop",
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 34,
                "total_tokens": 134,
                "completion_tokens_details": {"reasoning_tokens": 16},
            },
        }

    parsed = CanonicalizationResultPayload.model_validate(
        {
            "task_id": "tg-question-canonicalization-task:fixture",
            "candidate_id": "tg-qa-candidate:fixture",
            "canonical_question": "Нужно ли менять адрес на ВНЖ после переезда?",
            "legal_issue_frame": "Residence permit address update after moving",
            "legal_issue_frame_slug": "residence_permit_address_update_after_moving",
            "law_area": "migration_status",
            "is_legal_answer_required": True,
            "is_standalone_question": True,
            "exclusion_reason": "none",
            "confidence": "high",
        }
    )
    raw_result = {"raw": _RawMessage(), "parsed": parsed, "parsing_error": None}
    metadata = canonicalization._operator_record_runtime_metadata(
        raw_result,
        request_duration_seconds=1.23456,
        attempts_used=2,
    )

    assert metadata == {
        "request_duration_seconds": 1.235,
        "attempts_used": 2,
        "input_tokens": 101,
        "output_tokens": 33,
        "total_tokens": 134,
        "reasoning_tokens": 17,
        "usage_source": "langchain_usage_metadata+response_metadata_token_usage",
        "llm_usage_available": True,
    }

    plain_message_metadata = canonicalization._operator_record_runtime_metadata(
        _RawMessage(),
        request_duration_seconds=0.25,
        attempts_used=1,
    )
    assert plain_message_metadata == {
        "request_duration_seconds": 0.25,
        "attempts_used": 1,
        "input_tokens": 101,
        "output_tokens": 33,
        "total_tokens": 134,
        "reasoning_tokens": 17,
        "usage_source": "langchain_usage_metadata+response_metadata_token_usage",
        "llm_usage_available": True,
    }


def test_structured_output_payload_falls_back_to_raw_text_json() -> None:
    class _RawMessage:
        content = [
            {"type": "thinking", "thinking": "ignored hidden reasoning block"},
            {
                "type": "text",
                "text": (
                    "{"
                    '"verdict":"fail",'
                    '"confidence":90,'
                    '"risk":"low",'
                    '"bad_fields":["law_area"],'
                    '"short_reason":"Law area should be corrected.",'
                    '"final_recommendation":"retry_generator",'
                    '"selected_candidate_key":"qwen"'
                    "}"
                ),
            },
        ]

    payload = canonicalization._structured_output_payload(
        {"raw": _RawMessage(), "parsed": None, "parsing_error": None}
    )

    assert AdjudicationPayload.model_validate(payload).final_recommendation == "retry_generator"
    assert payload["bad_fields"] == ["law_area"]


def test_prompt_profile_versions_can_be_overridden_by_env() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_root / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}"
    env.update(
        {
            "TG_QUESTION_CANONICALIZATION_PROMPT_VERSION": "tg_question_canonicalizer_v11_positive",
            "TG_QA_CANDIDATE_PROMPT_VERSION": "tg_qa_candidate_classifier_v4_2_positive",
            "TG_QA_CLUSTER_PROMPT_VERSION": "tg_qa_cluster_reviewer_v4_2_positive",
            "TG_QA_CLUSTER_COMPACT_PROMPT_VERSION": "tg_qa_cluster_reviewer_compact_v4_2_positive",
            "TG_QUESTION_CANONICALIZATION_VERIFIER_PROMPT_VERSION": (
                "tg_question_canonicalization_verifier_v8_positive"
            ),
            "TG_QUESTION_CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION": (
                "tg_question_canonicalization_adjudicator_v8_positive"
            ),
            "TG_LEGAL_INTENT_PAIR_JUDGE_PROMPT_VERSION": "tg_legal_intent_pair_judge_v2_positive",
        }
    )
    code = """
import json
from evaluation import prompts

print(json.dumps({
    "canonicalization": prompts.CANONICALIZATION_PROMPT_VERSION,
    "candidate": prompts.TG_QA_CANDIDATE_PROMPT_VERSION,
    "cluster": prompts.TG_QA_CLUSTER_PROMPT_VERSION,
    "cluster_compact": prompts.TG_QA_CLUSTER_COMPACT_PROMPT_VERSION,
    "verifier": prompts.CANONICALIZATION_VERIFIER_PROMPT_VERSION,
    "adjudicator": prompts.CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION,
    "pair_judge": prompts.LEGAL_INTENT_PAIR_JUDGE_PROMPT_VERSION,
}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        cwd=repo_root,
        env=env,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "adjudicator": "tg_question_canonicalization_adjudicator_v8_positive",
        "candidate": "tg_qa_candidate_classifier_v4_2_positive",
        "canonicalization": "tg_question_canonicalizer_v11_positive",
        "cluster": "tg_qa_cluster_reviewer_v4_2_positive",
        "cluster_compact": "tg_qa_cluster_reviewer_compact_v4_2_positive",
        "pair_judge": "tg_legal_intent_pair_judge_v2_positive",
        "verifier": "tg_question_canonicalization_verifier_v8_positive",
    }


def test_canonicalizer_v11_preserves_source_intent_strength() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    profile = _read_json(
        repo_root / "src/evaluation/prompt_profiles/tg_question_canonicalizer_v11_positive.json"
    )
    instruction = profile["system_instruction"]
    examples = profile["few_shot_examples"]

    assert profile["prompt_version"] == "tg_question_canonicalizer_v11_positive"
    assert profile["prompt_example_set_id"] == "tg_question_canonicalizer_examples_v5_positive"
    assert len(examples) == 15
    assert "IMPORTANT SOURCE-INTENT STRENGTH" in instruction
    assert "whether temporary or one-night shelter is available" in instruction
    assert "confirmation or clarification fragments" in instruction
    assert "how that trigger affects an existing status" in instruction
    assert examples[-2]["output"]["exclusion_reason"] == "non_legal_question"
    assert examples[-2]["output"]["quality_flags"] == [
        "operational_logistics_only",
        "requires_live_operational_data",
    ]
    assert examples[-1]["output"]["exclusion_reason"] == "not_standalone_question"
    assert examples[-1]["output"]["is_standalone_question"] is False


def test_canonicalizer_v12_does_not_promote_unverified_authority_options() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    profile = _read_json(
        repo_root / "src/evaluation/prompt_profiles/tg_question_canonicalizer_v12_positive.json"
    )
    instruction = profile["system_instruction"]
    example = profile["few_shot_examples"][-1]
    output = example["output"]

    assert profile["prompt_version"] == "tg_question_canonicalizer_v12_positive"
    assert profile["prompt_example_set_id"] == "tg_question_canonicalizer_examples_v6_positive"
    assert len(profile["few_shot_examples"]) == 16
    assert "IMPORTANT UNVERIFIED AUTHORITY OPTIONS" in instruction
    assert "authority names proposed by the source as claims that may be mistaken" in instruction
    assert "without presenting those names as valid alternatives" in instruction
    assert "БАМФ" not in output["canonical_question"]
    assert output["authority_context"] == ["competent_benefits_authority"]
    assert output["quality_flags"] == []


def test_canonicalizer_v13_distinguishes_multiple_legal_questions_from_mixed_queries() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    profile = _read_json(
        repo_root / "src/evaluation/prompt_profiles/tg_question_canonicalizer_v13_positive.json"
    )
    instruction = profile["system_instruction"]

    assert profile["prompt_version"] == "tg_question_canonicalizer_v13_positive"
    assert profile["prompt_example_set_id"] == "tg_question_canonicalizer_examples_v6_positive"
    assert len(profile["few_shot_examples"]) == 16
    assert "IMPORTANT SOURCE-LEVEL QUERY COMPOSITION" in instruction
    assert "independently from the single selected canonical_question" in instruction
    assert "quality_flags=multiple_legal_questions" in instruction
    assert "quality_flags=mixed_with_non_legal_query" in instruction
    assert instruction.index("IMPORTANT SINGLE-QUESTION RULE") < instruction.index(
        "IMPORTANT SOURCE-LEVEL QUERY COMPOSITION"
    )
    assert instruction.index("IMPORTANT SOURCE-LEVEL QUERY COMPOSITION") < instruction.index(
        "For cross-border money transfers"
    )


def test_canonicalizer_v14_treats_conversational_framing_as_neutral() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    profile = _read_json(
        repo_root / "src/evaluation/prompt_profiles/tg_question_canonicalizer_v14_positive.json"
    )
    instruction = profile["system_instruction"]

    assert profile["prompt_version"] == "tg_question_canonicalizer_v14_positive"
    assert profile["prompt_example_set_id"] == "tg_question_canonicalizer_examples_v6_positive"
    assert len(profile["few_shot_examples"]) == 16
    assert "classify the substantive requests in the full source" in instruction
    assert "conversational framing without a separate request as neutral framing" in instruction
    assert "all substantive requests are legal" in instruction
    assert "as the composition flag" in instruction
    assert "a separate substantive non-legal or operational request" in instruction


def test_canonicalizer_v15_defines_composition_flags_in_schema_and_examples() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    profile = _read_json(
        repo_root / "src/evaluation/prompt_profiles/tg_question_canonicalizer_v15_positive.json"
    )
    instruction = profile["system_instruction"]
    examples = profile["few_shot_examples"]
    multiple_legal = examples[-2]["output"]
    missing_basis = examples[-1]["output"]

    assert profile["prompt_version"] == "tg_question_canonicalizer_v15_positive"
    assert profile["prompt_example_set_id"] == "tg_question_canonicalizer_examples_v7_positive"
    assert len(examples) == 18
    assert "facts, and omitted secondary legal issues as neutral" in instruction
    assert "one substantive legal request uses neither composition flag" in instruction
    assert "may use both composition flags" in instruction
    assert "multiple_legal_questions=two or more substantive legal requests" in profile[
        "expected_output_schema"
    ]["quality_flags"]
    assert multiple_legal["quality_flags"] == ["multiple_legal_questions"]
    assert missing_basis["quality_flags"] == [
        "missing_legal_basis",
        "potentially_unlawful_arrangement",
    ]


def test_canonicalizer_v16_contrasts_mixed_legal_and_operational_requests() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    profile = _read_json(
        repo_root / "src/evaluation/prompt_profiles/tg_question_canonicalizer_v16_positive.json"
    )
    example = profile["few_shot_examples"][-1]

    assert profile["prompt_version"] == "tg_question_canonicalizer_v16_positive"
    assert profile["prompt_example_set_id"] == "tg_question_canonicalizer_examples_v8_positive"
    assert len(profile["few_shot_examples"]) == 19
    assert "current border-control practice" in example["output"]["facts"][-1]
    assert example["output"]["quality_flags"] == ["mixed_with_non_legal_query"]
    assert example["output"]["canonical_question"].count("?") == 1


def test_canonicalizer_v17_moves_material_field_rules_into_schema_and_examples() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    profile = _read_json(
        repo_root / "src/evaluation/prompt_profiles/tg_question_canonicalizer_v17_positive.json"
    )
    schema = profile["expected_output_schema"]
    examples = profile["few_shot_examples"]

    assert profile["prompt_version"] == "tg_question_canonicalizer_v17_positive"
    assert profile["prompt_example_set_id"] == "tg_question_canonicalizer_examples_v9_positive"
    assert len(examples) == 22
    assert "IMPORTANT UNRESOLVED ROUTE AMBIGUITY" in profile["system_instruction"]
    assert "exactly one central reusable legal question" in schema["canonical_question"]
    assert "customs_and_tax for temporary admission/import of foreign vehicles" in schema["law_area"]
    assert "unresolved route or status ambiguity" in schema["hidden_issues"]
    assert "not merely current law or a dated rumor" in schema["quality_flags"]
    assert examples[-3]["output"]["quality_flags"] == [
        "multiple_legal_questions",
        "mixed_with_non_legal_query",
    ]
    assert examples[-2]["output"]["law_area"] == "banking_compliance"
    assert examples[-2]["output"]["quality_flags"] == []
    assert "вид на жительство" in examples[-1]["output"]["canonical_question"]


def test_canonicalizer_v18_distinguishes_legal_currentness_from_live_operations() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    profile = _read_json(
        repo_root / "src/evaluation/prompt_profiles/tg_question_canonicalizer_v18_positive.json"
    )
    examples = profile["few_shot_examples"]

    assert profile["prompt_version"] == "tg_question_canonicalizer_v18_positive"
    assert profile["prompt_example_set_id"] == "tg_question_canonicalizer_examples_v10_positive"
    assert len(examples) == 24
    assert "IMPORTANT LEGAL CURRENTNESS VERSUS LIVE OPERATIONS" in profile["system_instruction"]
    assert "currently applicable official legal rule" in profile["system_instruction"]
    assert "how long, how difficult, or how quickly" in profile["system_instruction"]
    assert "current official legal rule or dated legal restriction alone is not live" in profile[
        "expected_output_schema"
    ]["quality_flags"]
    assert examples[-2]["output"]["quality_flags"] == ["mixed_with_non_legal_query"]
    assert examples[-1]["output"]["quality_flags"] == []


def test_canonicalizer_v19_resolves_tz_from_migration_context() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    profile = _read_json(
        repo_root / "src/evaluation/prompt_profiles/tg_question_canonicalizer_v19_positive.json"
    )
    multiple_example = profile["few_shot_examples"][16]

    assert profile["prompt_version"] == "tg_question_canonicalizer_v19_positive"
    assert profile["prompt_example_set_id"] == "tg_question_canonicalizer_examples_v11_positive"
    assert len(profile["few_shot_examples"]) == 24
    assert "IMPORTANT CONTEXTUAL ABBREVIATIONS" in profile["system_instruction"]
    assert "'тз' referring to a country-issued status means temporary protection" in profile[
        "system_instruction"
    ]
    assert "resolve contextual abbreviations" in profile["expected_output_schema"]["facts"]
    assert "тз Португалии" in multiple_example["input"]["question_text_redacted"]
    assert "temporary protection from Portugal" in multiple_example["output"]["facts"][0]
    assert multiple_example["output"]["quality_flags"] == ["multiple_legal_questions"]


def test_verifier_v9_preserves_field_ownership_and_central_selection() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    profile = _read_json(
        repo_root / "src/evaluation/prompt_profiles/tg_question_canonicalization_verifier_v9_positive.json"
    )
    instruction = profile["system_instruction"]
    examples = profile["few_shot_examples"]

    assert profile["prompt_version"] == "tg_question_canonicalization_verifier_v9_positive"
    assert len(examples) == 12
    assert "IMPORTANT REVIEW FIELD OWNERSHIP" in instruction
    assert "mixed_with_non_legal_query is valid when the source contains" in instruction
    assert "IMPORTANT CENTRAL-SELECTION SEMANTICS" in instruction
    assert "selecting one central legal question" in instruction
    assert "inseparable parts of the same legal relationship" in instruction
    assert examples[-3]["input"]["task_id"] == "fixture:central-question-selected"
    assert examples[-3]["output"]["verdict"] == "pass"
    assert examples[-2]["input"]["task_id"] == "fixture:mixed-source-flag-after-omission"
    assert examples[-2]["output"]["verdict"] == "pass"
    assert examples[-1]["input"]["task_id"] == "fixture:integrated-obligation-and-consequence"
    assert examples[-1]["output"]["verdict"] == "pass"


def test_adjudicator_v9_preserves_source_flags_and_operational_routing() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    profile = _read_json(
        repo_root / "src/evaluation/prompt_profiles/tg_question_canonicalization_adjudicator_v9_positive.json"
    )
    instruction = profile["system_instruction"]
    examples = profile["few_shot_examples"]

    assert profile["prompt_version"] == "tg_question_canonicalization_adjudicator_v9_positive"
    assert len(examples) == 8
    assert "IMPORTANT REVIEW FIELD OWNERSHIP" in instruction
    assert "not only against the cleaned canonical_question" in instruction
    assert "IMPORTANT OPERATIONAL ROUTING STABILITY" in instruction
    assert "current city, region, camp, or office intake capacity" in instruction
    assert "only what a legal-status document looks like" in instruction
    assert examples[-4]["input"]["task_id"] == "fixture:adjudicator-mixed-source-flag"
    assert examples[-3]["input"]["task_id"] == "fixture:adjudicator-multiple-legal-source-flag"
    assert examples[-2]["input"]["task_id"] == "fixture:adjudicator-live-region-intake"
    assert examples[-1]["input"]["task_id"] == "fixture:adjudicator-document-appearance"
    assert all(example["output"]["final_recommendation"] == "accept" for example in examples[-4:])


def test_adjudicator_v10_overrides_unanimous_errors_and_retries_material_flags() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    profile = _read_json(
        repo_root / "src/evaluation/prompt_profiles/tg_question_canonicalization_adjudicator_v10_positive.json"
    )
    instruction = profile["system_instruction"]
    examples = profile["few_shot_examples"]

    assert profile["prompt_version"] == "tg_question_canonicalization_adjudicator_v10_positive"
    assert len(examples) == 11
    assert "IMPORTANT EVIDENCE PRIORITY" in instruction
    assert "even when every verifier repeats the same contrary interpretation" in instruction
    assert "IMPORTANT INCLUDED-FLAG MATERIALITY" in instruction
    assert "changes downstream filtering or review selection" in instruction
    assert examples[-3]["input"]["task_id"] == "fixture:adjudicator-unanimous-live-intake-error"
    assert examples[-3]["output"]["final_recommendation"] == "accept"
    assert examples[-2]["input"]["task_id"] == "fixture:adjudicator-unanimous-card-timing-error"
    assert examples[-2]["output"]["final_recommendation"] == "accept"
    assert examples[-1]["input"]["task_id"] == "fixture:adjudicator-material-included-flags"
    assert examples[-1]["output"]["bad_fields"] == ["quality_flags"]
    assert examples[-1]["output"]["final_recommendation"] == "retry_generator"


def test_prompt_regression_registry_covers_all_prompt_lessons_without_raw_corpus() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    registry = _read_json(repo_root / "specs/007-legal-question-canonicalization/prompt-regression-cases.json")
    prompt_lessons = (repo_root / "specs/007-legal-question-canonicalization/prompt-lessons.md").read_text(
        encoding="utf-8"
    )
    lesson_ids = {
        line.split(":", 1)[0].removeprefix("## ").strip()
        for line in prompt_lessons.splitlines()
        if line.startswith("## PL-")
    }
    cases = registry["cases"]
    covered_lessons = {lesson_id for case in cases for lesson_id in case["lesson_ids"]}
    case_ids = [case["case_id"] for case in cases]
    real_task_ids = [case["task_id"] for case in cases if case["source_kind"] == "real_task"]
    lesson_task_ids = {
        line.split("`", 2)[1]
        for line in prompt_lessons.splitlines()
        if line.startswith("- `tg-question-canonicalization-task:")
    }

    assert registry["trust_boundary"] == "task_ids_and_expected_invariants_only_no_raw_private_corpus"
    assert len(case_ids) == len(set(case_ids))
    assert len(real_task_ids) == len(set(real_task_ids))
    assert set(real_task_ids) == lesson_task_ids
    assert covered_lessons == lesson_ids
    assert all(case["prompt_families"] for case in cases)

    activity_document_case = next(
        case
        for case in cases
        if case["case_id"]
        == "pr-063-canonicalizer-foreign-fop-health-insurance-registration-gate"
    )
    checks = activity_document_case["automatic_checks"]
    assert "registration" not in checks.get("required_all_evidence_terms", [])
    assert "регистрац" in checks["forbidden_canonical_question_terms"]
    assert {"atomic_verifier", "atomic_critic"}.issubset(
        activity_document_case["prompt_families"]
    )
    assert all(
        "fixture_profile" in case and "fixture_task_id" in case
        for case in cases
        if case["source_kind"] == "prompt_profile_fixture"
    )
    assert "source_question_text_redacted" not in json.dumps(registry, ensure_ascii=False)


def test_openai_verifier_chain_passes_extra_body(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def with_structured_output(self, schema: object, method: str = "", include_raw: bool = False) -> object:
            captured["include_raw"] = include_raw
            return lambda payload: payload

    fake_module = types.SimpleNamespace(ChatOpenAI=_FakeChatOpenAI)
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_module)

    chain = canonicalization._build_verifier_chain(
        provider="openai",
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-qwen",
        timeout_seconds=60,
        max_tokens=256,
        structured_output_method="json_mode",
        api_key_env="",
        extra_body={"enable_thinking": False},
    )

    assert chain is not None
    assert captured["extra_body"] == {"enable_thinking": False}
    assert captured["include_raw"] is True


def test_anthropic_verifier_chain_normalizes_messages_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeChatAnthropic:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def with_structured_output(self, schema: object, method: str = "", include_raw: bool = False) -> object:
            captured["include_raw"] = include_raw
            return lambda payload: payload

    fake_module = types.SimpleNamespace(ChatAnthropic=_FakeChatAnthropic)
    monkeypatch.setitem(sys.modules, "langchain_anthropic", fake_module)

    chain = canonicalization._build_verifier_chain(
        provider="anthropic",
        endpoint_url="https://opencode.ai/zen/go/v1/messages",
        model_id="minimax-m2.7",
        timeout_seconds=60,
        max_tokens=256,
        structured_output_method="function_calling",
        api_key_env="",
        extra_body={"thinking": {"type": "disabled"}},
    )

    assert chain is not None
    assert captured["base_url"] == "https://opencode.ai/zen/go"
    assert captured["thinking"] == {"type": "disabled"}
    assert captured["include_raw"] is True


def test_anthropic_canonicalization_chain_normalizes_messages_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeChatAnthropic:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def with_structured_output(self, schema: object, method: str = "", include_raw: bool = False) -> object:
            captured["structured_method"] = method
            captured["include_raw"] = include_raw
            return lambda payload: payload

    fake_module = types.SimpleNamespace(ChatAnthropic=_FakeChatAnthropic)
    monkeypatch.setitem(sys.modules, "langchain_anthropic", fake_module)

    chain = canonicalization._build_canonicalization_chain(
        provider="anthropic",
        endpoint_url="https://opencode.ai/zen/go/v1/messages",
        model_id="minimax-m3",
        timeout_seconds=60,
        max_tokens=1024,
        structured_output_method="function_calling",
        api_key_env="",
        extra_body={"thinking": {"type": "disabled"}},
    )

    assert chain is not None
    assert captured["base_url"] == "https://opencode.ai/zen/go"
    assert captured["model"] == "minimax-m3"
    assert captured["thinking"] == {"type": "disabled"}
    assert captured["structured_method"] == "function_calling"
    assert captured["include_raw"] is True


def test_atomic_chat_models_use_native_parameters_and_disable_sdk_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anthropic_captured: dict[str, object] = {}
    openai_captured: dict[str, object] = {}

    class _FakeChatAnthropic:
        def __init__(self, **kwargs: object) -> None:
            anthropic_captured.update(kwargs)

    class _FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            openai_captured.update(kwargs)

    monkeypatch.setitem(
        sys.modules,
        "langchain_anthropic",
        types.SimpleNamespace(ChatAnthropic=_FakeChatAnthropic),
    )
    monkeypatch.setitem(
        sys.modules,
        "langchain_openai",
        types.SimpleNamespace(ChatOpenAI=_FakeChatOpenAI),
    )

    canonicalization._build_atomic_operator_chat_model(
        provider="anthropic",
        endpoint_url="https://opencode.ai/zen/go/v1/messages",
        model_id="qwen3.7-plus",
        timeout_seconds=420,
        max_tokens=32768,
        api_key_env="",
        extra_body={"thinking": {"type": "enabled", "budget_tokens": 16384}},
        parameter_transport="anthropic_constructor",
    )
    canonicalization._build_atomic_operator_chat_model(
        provider="openai",
        endpoint_url="https://opencode.ai/zen/go/v1/chat/completions",
        model_id="kimi-k2.6",
        timeout_seconds=420,
        max_tokens=32768,
        api_key_env="",
        extra_body={"reasoning": {"enabled": True}},
        temperature=0,
        parameter_transport="openai_extra_body",
    )

    assert anthropic_captured["base_url"] == "https://opencode.ai/zen/go"
    assert anthropic_captured["thinking"] == {
        "type": "enabled",
        "budget_tokens": 16384,
    }
    assert anthropic_captured["max_retries"] == 0
    assert openai_captured["extra_body"] == {"reasoning": {"enabled": True}}
    assert openai_captured["max_retries"] == 0

    openai_captured.clear()
    canonicalization._build_atomic_operator_chat_model(
        provider="openai",
        endpoint_url="https://opencode.ai/zen/go/v1/chat/completions",
        model_id="kimi-k2.7-code",
        timeout_seconds=420,
        max_tokens=32768,
        api_key_env="",
        extra_body={},
        temperature=None,
        parameter_transport="openai_extra_body",
    )
    assert "temperature" not in openai_captured

    with pytest.raises(ValueError, match="unsupported anthropic atomic request parameters"):
        canonicalization._build_atomic_operator_chat_model(
            provider="anthropic",
            endpoint_url="https://opencode.ai/zen/go/v1/messages",
            model_id="qwen3.7-plus",
            timeout_seconds=420,
            max_tokens=32768,
            api_key_env="",
            extra_body={"silently_ignored_before": True},
            parameter_transport="anthropic_constructor",
        )


def test_atomic_prompt_json_chain_preserves_raw_message_and_validates_schema() -> None:
    from langchain_core.messages import AIMessage
    from langchain_core.runnables import RunnableLambda

    raw_message = AIMessage(
        content='```json\n{"route":"pass","claim_verdicts":[],"short_reason":"ok"}\n```'
    )
    model = RunnableLambda(lambda _: raw_message)

    chain = canonicalization.build_langchain_canonicalization_atomic_verifier_chain(
        model,
        method="prompt_json",
    )
    result = chain.invoke({"atomic_verifier_payload": "{}"})

    assert result["raw"] is raw_message
    assert result["parsing_error"] is None
    assert result["parsed"].route == "pass"

    invalid_model = RunnableLambda(
        lambda _: AIMessage(
            content=(
                '{"route":"pass","claim_verdicts":[],"short_reason":"ok",'
                '"forbidden":true}'
            )
        )
    )
    invalid_chain = canonicalization.build_langchain_canonicalization_atomic_verifier_chain(
        invalid_model,
        method="prompt_json",
    )
    invalid_result = invalid_chain.invoke({"atomic_verifier_payload": "{}"})

    assert invalid_result["parsed"] is None
    assert isinstance(invalid_result["parsing_error"], canonicalization.ValidationError)

    trailing_model = RunnableLambda(
        lambda _: AIMessage(
            content='{"route":"pass","claim_verdicts":[],"short_reason":"ok"}\nDone.'
        )
    )
    trailing_chain = canonicalization.build_langchain_canonicalization_atomic_verifier_chain(
        trailing_model,
        method="prompt_json",
    )
    trailing_result = trailing_chain.invoke({"atomic_verifier_payload": "{}"})

    assert trailing_result["parsed"] is None
    assert trailing_result["parsing_error"] == "prompt_json_missing_object"

    formatter_model = RunnableLambda(
        lambda _: AIMessage(
            content='{"route":"hold","claim_verdicts":[],"short_reason":"memo incomplete"}'
        )
    )
    formatter_chain = (
        canonicalization.build_langchain_canonicalization_atomic_formatter_chain(
            formatter_model,
            stage="verifier",
            method="prompt_json",
        )
    )
    formatter_result = formatter_chain.invoke(
        {
            "atomic_stage_payload": "{}",
            "atomic_reasoning_memo": "ROUTE: hold",
            "atomic_formatter_validation_feedback": "",
        }
    )

    assert formatter_result["parsing_error"] is None
    assert formatter_result["parsed"].route == "hold"


def test_deepseek_runner_shapes_stream_results_with_fake_structured_chain(tmp_path: Path) -> None:
    batch_path = tmp_path / "send_deepseek_batch.jsonl"
    deepseek_results_path = tmp_path / "deepseek_results.jsonl"
    deepseek_summary_path = tmp_path / "deepseek_summary.json"
    batch_item = {
        "task_id": "tg-question-canonicalization-task:fixture-deepseek",
        "candidate_id": "tg-qa-candidate:fixture-deepseek",
        "adjudication_prompt_version": canonicalization.CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION,
        "source_question_text_redacted": "Как обновить статус в C24 при автоматическом продлении?",
        "candidates": [
            {
                "candidate_key": "primary",
                "model_id": "fixture-qwen",
                "status": "completed",
                "canonical_question": "Как обновить статус в банке при автоматическом продлении ВНЖ?",
                "canonical_question_language": "ru",
                "legal_issue_frame": "Automatic permit extension proof accepted by bank",
                "legal_issue_frame_slug": "automatic_permit_extension_proof_accepted_by_bank",
                "law_area": "migration_status",
                "facts": ["bank requests upload", "permit card date expired"],
                "desired_outcome": "bank accepts current proof bundle",
                "authority_context": ["bank"],
                "hidden_issues": ["third-party acceptance of status proof"],
                "is_legal_answer_required": True,
                "is_standalone_question": True,
                "exclusion_reason": "none",
                "confidence": "medium",
                "quality_flags": [],
            }
        ],
        "verifier_votes": [
            {
                "candidate_key": "primary",
                "verifier_key": "reviewer_1",
                "model_id": "fixture-verifier",
                "status": "completed",
                "verdict": "uncertain",
                "confidence": 58,
                "risk": "medium",
                "bad_fields": ["is_legal_answer_required"],
                "short_reason": "Might be procedural-vs-legal-adjacent.",
                "suggested_action": "send_deepseek",
            }
        ],
        "consensus_summary": {
            "unanimous": False,
            "escalation_reason_codes": ["verifier_uncertain"],
            "candidate_summaries": [
                {
                    "candidate_key": "primary",
                    "vote_count": 1,
                    "pass_count": 0,
                    "fail_count": 0,
                    "uncertain_count": 1,
                }
            ],
        },
        "human_triage": {
            "decision": "send_deepseek",
            "decision_reason": "bank_status_proof_conflict",
            "reviewer_hash": "",
        },
        "expected_output_schema": {
            "verdict": "pass|fail|uncertain",
            "confidence": "0-100 integer",
            "risk": "none|low|medium|high",
            "bad_fields": "array[string]",
            "short_reason": "string",
            "final_recommendation": "accept|reject|retry_generator|human_review",
            "selected_candidate_key": "string",
        },
    }
    _write_jsonl(batch_path, [batch_item])

    result = run_tg_qa_canonicalization_adjudication_batch(
        batch_path=batch_path,
        output_path=deepseek_results_path,
        summary_output_path=deepseek_summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-deepseek",
        adjudication_run_id="tg-question-canonicalization-deepseek-run:fixture",
        chain=_FakeDeepSeekChain(),
    )

    deepseek_records = _read_jsonl(deepseek_results_path)
    assert result["summary"]["completed_count"] == 1
    assert deepseek_records[0]["task_id"] == batch_item["task_id"]
    assert deepseek_records[0]["verdict"] == "pass"
    assert deepseek_records[0]["final_recommendation"] == "accept"
    assert deepseek_records[0]["selected_candidate_key"] == "primary"


def test_live_runner_progress_and_failure_reason_are_diagnostic(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    qwen_summary_path = tmp_path / "qwen_summary.json"
    _write_jsonl(
        candidates_path,
        [_candidate("tg-qa-candidate:1", "Где купить кофе?", "m1")],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="all",
    )

    chain = _FailingCanonicalizationChain()
    result = run_tg_qa_canonicalization_llm_batch(
        batch_path=batch_path,
        output_path=qwen_results_path,
        summary_output_path=qwen_summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-qwen",
        canonicalization_run_id="tg-question-canonicalization-run:fixture",
        progress=True,
        stop_on_failure=True,
        chain=chain,
    )

    captured = capsys.readouterr()
    records = _read_jsonl(qwen_results_path)
    assert result["summary"]["failed_count"] == 1
    assert result["summary"]["progress"] is True
    assert chain.attempt_count == 1
    assert records[0]["failure_reason"].startswith("endpoint_error:OutputParserException:")
    assert "Invalid json output" in records[0]["failure_reason"]
    assert "[url]" in records[0]["failure_reason"]
    assert "https://" not in records[0]["failure_reason"]
    assert "sk-" not in records[0]["failure_reason"]
    assert "tg-qa-canonicalization-llm-run" in captured.err
    assert "failed" in captured.err
    assert "last_status=request" in captured.err
    assert "last_status=failed" in captured.err
    assert records[0]["task_id"] in captured.err


def test_live_runner_preserves_batch_contract_version(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    results_path = tmp_path / "results.jsonl"
    summary_path = tmp_path / "summary.json"
    _write_jsonl(
        candidates_path,
        [_candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ?", "m1")],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="law_or_topic",
    )
    batch = _read_jsonl(batch_path)
    batch[0]["canonicalization_contract_version"] = "tg_question_canonicalization_v1"
    canonicalization._bind_canonicalization_batch_identity(batch)
    _write_jsonl(batch_path, batch)

    run_tg_qa_canonicalization_llm_batch(
        batch_path=batch_path,
        output_path=results_path,
        summary_output_path=summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-qwen",
        canonicalization_run_id="tg-question-canonicalization-run:legacy-contract",
        chain=_FakeCanonicalizationChain(batch[0]),
    )

    assert _read_jsonl(results_path)[0]["canonicalization_contract_version"] == (
        "tg_question_canonicalization_v1"
    )


def test_failed_live_runner_preserves_batch_contract_version() -> None:
    record = canonicalization._operator_failed_canonicalization_record(
        {
            "task_id": "tg-question-canonicalization-task:legacy",
            "candidate_id": "tg-qa-candidate:legacy",
            "canonicalization_contract_version": "tg_question_canonicalization_v1",
        },
        canonicalization_run_id="tg-question-canonicalization-run:legacy-contract",
        failure_reason="fixture_failure",
        runtime_contour="fixture",
        backend="fixture",
        model_id="fixture-qwen",
    )

    assert record["canonicalization_contract_version"] == "tg_question_canonicalization_v1"


def test_live_runner_resumes_existing_output_without_duplicate_processing(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    qwen_summary_path = tmp_path / "qwen_summary.json"
    _write_jsonl(
        candidates_path,
        [
            _candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", "m1"),
            _candidate("tg-qa-candidate:2", "Как обновить адрес на пластиковой карте ВНЖ?", "m2"),
        ],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="law_or_topic",
    )
    batch = _read_jsonl(batch_path)
    first_chain = _SelectiveCanonicalizationChain({batch[0]["task_id"]: batch[0]})
    run_tg_qa_canonicalization_llm_batch(
        batch_path=batch_path,
        output_path=qwen_results_path,
        summary_output_path=qwen_summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-qwen",
        canonicalization_run_id="tg-question-canonicalization-run:fixture",
        max_items=1,
        chain=first_chain,
    )
    chain = _SelectiveCanonicalizationChain({batch[1]["task_id"]: batch[1]})

    result = run_tg_qa_canonicalization_llm_batch(
        batch_path=batch_path,
        output_path=qwen_results_path,
        summary_output_path=qwen_summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-qwen",
        canonicalization_run_id="tg-question-canonicalization-run:fixture",
        max_items=1,
        chain=chain,
    )

    records = _read_jsonl(qwen_results_path)
    assert result["summary"]["resume"] is True
    assert result["summary"]["resumed_existing_count"] == 1
    assert result["summary"]["max_items"] == 1
    assert result["summary"]["requested_item_count"] == 1
    assert result["summary"]["processed_count"] == 1
    assert chain.invoked_task_ids == [batch[1]["task_id"]]
    assert [record["task_id"] for record in records] == [batch[0]["task_id"], batch[1]["task_id"]]


def test_live_runner_retries_transient_provider_errors(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    qwen_summary_path = tmp_path / "qwen_summary.json"
    _write_jsonl(
        candidates_path,
        [_candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", "m1")],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="law_or_topic",
    )
    batch_item = _read_jsonl(batch_path)[0]
    chain = _RetryingCanonicalizationChain(batch_item, fail_attempts=1)

    result = run_tg_qa_canonicalization_llm_batch(
        batch_path=batch_path,
        output_path=qwen_results_path,
        summary_output_path=qwen_summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-qwen",
        canonicalization_run_id="tg-question-canonicalization-run:fixture",
        provider_max_attempts=3,
        provider_retry_delay_seconds=0,
        chain=chain,
    )

    records = _read_jsonl(qwen_results_path)
    assert chain.attempt_count == 2
    assert result["summary"]["max_items"] == 0
    assert result["summary"]["provider_retry_count"] == 1
    assert result["summary"]["provider_retry_exhausted_count"] == 0
    assert result["summary"]["completed_count"] == 1
    assert records[0]["status"] == "completed"


def test_live_runner_retries_cjk_contaminated_canonicalization_output(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    qwen_summary_path = tmp_path / "qwen_summary.json"
    _write_jsonl(
        candidates_path,
        [_candidate("tg-qa-candidate:1", "Можно ли сменить работодателя с Blue Card?", "m1")],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="law_or_topic",
    )
    batch_item = _read_jsonl(batch_path)[0]
    chain = _CjkThenValidCanonicalizationChain(batch_item)

    result = run_tg_qa_canonicalization_llm_batch(
        batch_path=batch_path,
        output_path=qwen_results_path,
        summary_output_path=qwen_summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-qwen",
        canonicalization_run_id="tg-question-canonicalization-run:fixture",
        provider_max_attempts=0,
        provider_retry_delay_seconds=0,
        chain=chain,
    )

    records = _read_jsonl(qwen_results_path)
    assert chain.attempt_count == 2
    assert result["summary"]["provider_retry_count"] == 0
    assert result["summary"]["output_retry_count"] == 1
    assert result["summary"]["output_retry_exhausted_count"] == 0
    assert result["summary"]["completed_count"] == 1
    assert "持有" not in records[0]["canonical_question"]


def test_live_runner_supports_infinite_transient_retries(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    qwen_summary_path = tmp_path / "qwen_summary.json"
    _write_jsonl(
        candidates_path,
        [_candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", "m1")],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="law_or_topic",
    )
    batch_item = _read_jsonl(batch_path)[0]
    chain = _RetryingCanonicalizationChain(batch_item, fail_attempts=3)

    result = run_tg_qa_canonicalization_llm_batch(
        batch_path=batch_path,
        output_path=qwen_results_path,
        summary_output_path=qwen_summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-qwen",
        canonicalization_run_id="tg-question-canonicalization-run:fixture",
        provider_max_attempts=0,
        provider_retry_delay_seconds=0,
        chain=chain,
    )

    records = _read_jsonl(qwen_results_path)
    assert chain.attempt_count == 4
    assert result["summary"]["provider_retry_forever"] is True
    assert result["summary"]["provider_retry_count"] == 3
    assert result["summary"]["provider_retry_exhausted_count"] == 0
    assert result["summary"]["completed_count"] == 1
    assert records[0]["status"] == "completed"


def test_live_runner_stops_after_consecutive_provider_failures(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    qwen_summary_path = tmp_path / "qwen_summary.json"
    _write_jsonl(
        candidates_path,
        [
            _candidate(f"tg-qa-candidate:{index}", "Можно ли продлить ВНЖ после переезда?", f"m{index}")
            for index in range(5)
        ],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="law_or_topic",
    )
    chain = _AlwaysFailingProviderCanonicalizationChain()

    result = run_tg_qa_canonicalization_llm_batch(
        batch_path=batch_path,
        output_path=qwen_results_path,
        summary_output_path=qwen_summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-qwen",
        canonicalization_run_id="tg-question-canonicalization-run:fixture",
        provider_max_attempts=1,
        provider_retry_delay_seconds=0,
        stop_after_consecutive_provider_failures=3,
        chain=chain,
    )

    records = _read_jsonl(qwen_results_path)
    assert chain.attempt_count == 3
    assert len(records) == 3
    assert all(record["status"] == "failed" for record in records)
    assert result["summary"]["requested_item_count"] == 5
    assert result["summary"]["processed_count"] == 3
    assert result["summary"]["failed_count"] == 3
    assert result["summary"]["provider_retry_exhausted_count"] == 3
    assert result["summary"]["stop_after_consecutive_provider_failures"] == 3
    assert result["summary"]["stopped_by_provider_failure_guard"] is True
    assert result["summary"]["provider_failure_guard_trigger"] == "endpoint_error:InternalServerError:530"
    assert result["summary"]["consecutive_provider_failure_count"] == 3
    assert result["summary"]["unprocessed_count_due_to_provider_failure_guard"] == 2


def test_provider_failure_retry_batch_selects_only_provider_failures(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    results_path = tmp_path / "results.jsonl"
    retry_path = tmp_path / "retry.jsonl"
    retry_summary_path = tmp_path / "retry_summary.json"
    retry_with_tail_path = tmp_path / "retry_with_tail.jsonl"
    retry_with_tail_summary_path = tmp_path / "retry_with_tail_summary.json"
    _write_jsonl(
        candidates_path,
        [
            _candidate(f"tg-qa-candidate:{index}", "Можно ли продлить ВНЖ после переезда?", f"m{index}")
            for index in range(4)
        ],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="law_or_topic",
    )
    batch = _read_jsonl(batch_path)
    _write_jsonl(
        results_path,
        [
            _canonical_result(batch[0]),
            {
                "task_id": batch[1]["task_id"],
                "candidate_id": batch[1]["candidate_id"],
                "status": "failed",
                "failure_reason": "endpoint_error:InternalServerError:Error code: 530 retry_attempts=1",
            },
            {
                "task_id": batch[2]["task_id"],
                "candidate_id": batch[2]["candidate_id"],
                "status": "failed",
                "failure_reason": "endpoint_error:ValidationError:1 validation error for payload",
            },
        ],
    )

    result = build_tg_qa_operator_provider_failure_retry_batch(
        batch_path=batch_path,
        results_path=results_path,
        output_path=retry_path,
        summary_output_path=retry_summary_path,
    )
    result_with_tail = build_tg_qa_operator_provider_failure_retry_batch(
        batch_path=batch_path,
        results_path=results_path,
        output_path=retry_with_tail_path,
        summary_output_path=retry_with_tail_summary_path,
        include_unprocessed=True,
    )

    retry_items = _read_jsonl(retry_path)
    retry_with_tail_items = _read_jsonl(retry_with_tail_path)
    assert [item["task_id"] for item in retry_items] == [batch[1]["task_id"]]
    assert [item["task_id"] for item in retry_with_tail_items] == [batch[1]["task_id"], batch[3]["task_id"]]
    assert result["summary"]["provider_failed_result_count"] == 1
    assert result["summary"]["non_provider_failed_result_count"] == 1
    assert result["summary"]["unprocessed_batch_item_count"] == 1
    assert result["summary"]["provider_failure_keys"] == {"endpoint_error:InternalServerError:530": 1}
    assert result_with_tail["summary"]["selected_retry_item_count"] == 2


def test_live_runner_honors_max_items_limit(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    qwen_summary_path = tmp_path / "qwen_summary.json"
    _write_jsonl(
        candidates_path,
        [
            _candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", "m1"),
            _candidate("tg-qa-candidate:2", "Как обновить адрес на пластиковой карте ВНЖ?", "m2"),
        ],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="law_or_topic",
    )
    batch = _read_jsonl(batch_path)
    chain = _SelectiveCanonicalizationChain({item["task_id"]: item for item in batch})

    result = run_tg_qa_canonicalization_llm_batch(
        batch_path=batch_path,
        output_path=qwen_results_path,
        summary_output_path=qwen_summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-qwen",
        canonicalization_run_id="tg-question-canonicalization-run:fixture",
        max_items=1,
        chain=chain,
    )

    records = _read_jsonl(qwen_results_path)
    assert result["summary"]["max_items"] == 1
    assert result["summary"]["requested_item_count"] == 1
    assert result["summary"]["processed_count"] == 1
    assert chain.invoked_task_ids == [batch[0]["task_id"]]
    assert [record["task_id"] for record in records] == [batch[0]["task_id"]]


def test_canonicalization_batch_and_import_validate_results_idempotently(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    summary_path = tmp_path / "batch_summary.json"
    result_path = tmp_path / "results.jsonl"
    evidence_path = tmp_path / "evidence.jsonl"
    manifest_path = tmp_path / "manifest.json"
    _write_jsonl(
        candidates_path,
        [
            _candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", "m1"),
            _candidate("tg-qa-candidate:2", "Как обновить адрес на пластиковой карте ВНЖ?", "m2"),
            {
                "candidate_id": "tg-qa-candidate:noise",
                "question_text_redacted": "Где купить кофе?",
                "topic_labels": [],
                "law_code_candidates": [],
                "answer_candidate_status": "missing",
            },
        ],
    )

    batch_result = emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=summary_path,
        filter_mode="law_or_topic",
    )

    batch = _read_jsonl(batch_path)
    assert batch_result["summary"]["emitted_task_count"] == 2
    assert batch_result["summary"]["prompt_example_count"] == len(CANONICALIZATION_PROMPT_EXAMPLES)
    assert batch[0]["canonicalization_contract_version"] == CANONICALIZATION_CONTRACT_VERSION
    assert batch[0]["prompt_example_set_id"] == CANONICALIZATION_PROMPT_EXAMPLE_SET_ID
    assert batch[0]["expected_output_schema"]["canonical_question"].startswith("string")
    assert batch[0]["input"]["source_message_ids"] == ["m1"]

    result_records = [
        _canonical_result(batch[0], confidence="high"),
        _canonical_result(batch[0], confidence="medium"),
        _canonical_result(batch[1], confidence="medium"),
    ]
    result_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in result_records)
        + "\n{not-json\n",
        encoding="utf-8",
    )

    import_result = import_tg_qa_canonicalization_results(
        batch_path=batch_path,
        result_path=result_path,
        output_path=evidence_path,
        manifest_output_path=manifest_path,
        canonicalization_run_id="tg-question-canonicalization-run:test",
    )

    evidence = _read_jsonl(evidence_path)
    completed = [item for item in evidence if item["status"] == "completed"]
    assert len(completed) == 1
    assert {item["canonical_question_language"] for item in completed} == {"ru"}
    assert {item["legal_issue_frame_slug"] for item in completed} == {
        "residence_document_address_update_after_moving"
    }
    assert {tuple(item["untrusted_law_code_hints"]) for item in completed} == {
        ("AufenthG",)
    }
    assert import_result["manifest"]["duplicate_result_count"] == 1
    assert import_result["manifest"]["failed_count"] == 2
    assert any(item["status"] == "failed" and item["failure_reason"].startswith("invalid_json") for item in evidence)
    assert any(item["failure_reason"] == "duplicate_result_for_run_task_identity" for item in evidence)


def test_canonicalization_import_can_limit_scope_to_results_task_ids(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    summary_path = tmp_path / "batch_summary.json"
    result_path = tmp_path / "results.jsonl"
    evidence_path = tmp_path / "evidence.jsonl"
    manifest_path = tmp_path / "manifest.json"
    _write_jsonl(
        candidates_path,
        [
            _candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", "m1"),
            _candidate("tg-qa-candidate:2", "Как обновить адрес на пластиковой карте ВНЖ?", "m2"),
        ],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=summary_path,
        filter_mode="law_or_topic",
    )
    batch = _read_jsonl(batch_path)
    _write_jsonl(result_path, [_canonical_result(batch[0])])

    import_result = import_tg_qa_canonicalization_results(
        batch_path=batch_path,
        result_path=result_path,
        output_path=evidence_path,
        manifest_output_path=manifest_path,
        canonicalization_run_id="tg-question-canonicalization-run:test",
        only_results_task_ids=True,
    )

    evidence = _read_jsonl(evidence_path)
    assert len(evidence) == 1
    assert evidence[0]["task_id"] == batch[0]["task_id"]
    assert import_result["manifest"]["completed_count"] == 1
    assert import_result["manifest"]["skipped_count"] == 0
    assert import_result["manifest"]["input_scope"]["effective_task_count"] == 1
    assert import_result["manifest"]["input_scope"]["import_scope_mode"] == "results_task_ids_only"


def test_canonicalization_import_rejects_mismatched_batch_identity(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    results_path = tmp_path / "results.jsonl"
    evidence_path = tmp_path / "evidence.jsonl"
    manifest_path = tmp_path / "manifest.json"
    _write_jsonl(
        candidates_path,
        [_candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", "m1")],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
    )
    batch_item = _read_jsonl(batch_path)[0]
    result = _canonical_result(batch_item)
    result["canonicalization_batch_hash"] = "incorrect-batch-hash"
    _write_jsonl(results_path, [result])

    imported = import_tg_qa_canonicalization_results(
        batch_path=batch_path,
        result_path=results_path,
        output_path=evidence_path,
        manifest_output_path=manifest_path,
        canonicalization_run_id="tg-question-canonicalization-run:test",
    )

    evidence = _read_jsonl(evidence_path)
    assert imported["manifest"]["completed_count"] == 0
    assert evidence[0]["failure_reason"] == "identity_mismatch:canonicalization_batch_hash"


def test_canonicalization_routing_reconciles_full_batch_and_holds_unreviewed_results(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    routed_path = tmp_path / "routed.jsonl"
    routing_summary_path = tmp_path / "routing_summary.json"
    ledger_path = tmp_path / "ledger.jsonl"
    backlog_path = tmp_path / "backlog.jsonl"
    _write_jsonl(
        candidates_path,
        [
            _candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", "m1"),
            _candidate("tg-qa-candidate:2", "Как обновить адрес на пластиковой карте ВНЖ?", "m2"),
        ],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
    )
    batch = _read_jsonl(batch_path)
    _write_jsonl(qwen_results_path, [_canonical_result(batch[0])])

    routed = build_tg_qa_canonicalization_routing(
        batch_path=batch_path,
        qwen_results_path=qwen_results_path,
        output_path=routed_path,
        summary_output_path=routing_summary_path,
        decision_ledger_output_path=ledger_path,
        backlog_output_path=backlog_path,
    )

    ledger_by_task = {item["task_id"]: item for item in _read_jsonl(ledger_path)}
    assert routed["summary"]["accepted_result_count"] == 0
    assert routed["summary"]["decision_ledger_count"] == 2
    assert routed["summary"]["backlog_count"] == 2
    assert ledger_by_task[batch[0]["task_id"]]["decision_source"] == "unreviewed_hold"
    assert ledger_by_task[batch[1]["task_id"]]["failure_reason"] == "missing_qwen_result_for_batch_task"


def test_imported_review_without_reviewer_hash_can_be_finalized(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    raw_decisions_path = tmp_path / "raw_decisions.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    decisions_summary_path = tmp_path / "decisions_summary.json"
    routed_path = tmp_path / "routed.jsonl"
    routing_summary_path = tmp_path / "routing_summary.json"
    finalized_path = tmp_path / "finalized.jsonl"
    final_manifest_path = tmp_path / "final_manifest.json"
    final_backlog_path = tmp_path / "final_backlog.jsonl"
    snapshot_path = tmp_path / "snapshot.jsonl"
    snapshot_manifest_path = tmp_path / "snapshot_manifest.json"
    snapshot_quality_path = tmp_path / "snapshot_quality.json"
    snapshot_backlog_path = tmp_path / "snapshot_backlog.jsonl"
    _write_jsonl(
        candidates_path,
        [_candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", "m1")],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
    )
    batch_item = _read_jsonl(batch_path)[0]
    qwen_result = _canonical_result(batch_item)
    _write_jsonl(qwen_results_path, [qwen_result])
    _write_jsonl(
        raw_decisions_path,
        [
            {
                "task_id": batch_item["task_id"],
                "candidate_id": batch_item["candidate_id"],
                "decision": "accept",
                "reviewed_at": "2026-07-10T00:00:00Z",
            }
        ],
    )
    import_tg_qa_canonicalization_review_decisions(
        batch_path=batch_path,
        qwen_results_path=qwen_results_path,
        decisions_path=raw_decisions_path,
        output_path=decisions_path,
        summary_output_path=decisions_summary_path,
    )
    build_tg_qa_canonicalization_routing(
        batch_path=batch_path,
        qwen_results_path=qwen_results_path,
        output_path=routed_path,
        summary_output_path=routing_summary_path,
        review_decisions_path=decisions_path,
    )
    finalization = finalize_tg_qa_canonicalization_results(
        batch_path=batch_path,
        base_accepted_results_path=routed_path,
        output_path=finalized_path,
        manifest_output_path=final_manifest_path,
        backlog_output_path=final_backlog_path,
    )
    snapshot = build_tg_qa_canonicalization_snapshot(
        evidence_specs=[f"reviewed=silver={finalized_path}"],
        snapshot_name="fixture_snapshot",
        output_path=snapshot_path,
        manifest_output_path=snapshot_manifest_path,
        quality_output_path=snapshot_quality_path,
        backlog_output_path=snapshot_backlog_path,
    )

    assert finalization["manifest"]["finalized_record_count"] == 1
    assert finalization["manifest"]["backlog_count"] == 0
    assert snapshot["manifest"]["record_count"] == 1
    record = _read_jsonl(snapshot_path)[0]
    assert record["canonicalization_run_id"] == qwen_result["canonicalization_run_id"]
    assert record["prompt_profile_hash"] == qwen_result["prompt_profile_hash"]
    assert record["review_provenance"]["reviewer_hash"] == ""
    assert record["review_provenance"]["decision_source"] == "human_review"
    assert record["finalization_provenance"]["finalization_id"] == finalization["manifest"]["finalization_id"]


def test_finalization_accepts_reviewed_retry_only_with_matching_source_batch_lineage(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    base_results_path = tmp_path / "base_results.jsonl"
    base_decisions_raw_path = tmp_path / "base_decisions_raw.jsonl"
    base_decisions_path = tmp_path / "base_decisions.jsonl"
    base_decisions_summary_path = tmp_path / "base_decisions_summary.json"
    base_routed_path = tmp_path / "base_routed.jsonl"
    base_routing_summary_path = tmp_path / "base_routing_summary.json"
    retry_batch_path = tmp_path / "retry_batch.jsonl"
    retry_results_path = tmp_path / "retry_results.jsonl"
    retry_decisions_raw_path = tmp_path / "retry_decisions_raw.jsonl"
    retry_decisions_path = tmp_path / "retry_decisions.jsonl"
    retry_decisions_summary_path = tmp_path / "retry_decisions_summary.json"
    retry_routed_path = tmp_path / "retry_routed.jsonl"
    retry_routing_summary_path = tmp_path / "retry_routing_summary.json"
    finalized_path = tmp_path / "finalized.jsonl"
    final_manifest_path = tmp_path / "final_manifest.json"
    final_backlog_path = tmp_path / "final_backlog.jsonl"

    _write_jsonl(
        candidates_path,
        [
            _candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", "m1"),
            _candidate("tg-qa-candidate:2", "Как обновить адрес на пластиковой карте ВНЖ?", "m2"),
        ],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
    )
    base_batch = _read_jsonl(batch_path)
    base_results = [_canonical_result(item) for item in base_batch]
    _write_jsonl(base_results_path, base_results)
    _write_jsonl(
        base_decisions_raw_path,
        [
            {
                "task_id": item["task_id"],
                "candidate_id": item["candidate_id"],
                "decision": "accept",
                "reviewer_hash": "reviewer:base",
                "reviewed_at": "2026-07-10T00:00:00Z",
            }
            for item in base_batch
        ],
    )
    import_tg_qa_canonicalization_review_decisions(
        batch_path=batch_path,
        qwen_results_path=base_results_path,
        decisions_path=base_decisions_raw_path,
        output_path=base_decisions_path,
        summary_output_path=base_decisions_summary_path,
    )
    build_tg_qa_canonicalization_routing(
        batch_path=batch_path,
        qwen_results_path=base_results_path,
        output_path=base_routed_path,
        summary_output_path=base_routing_summary_path,
        review_decisions_path=base_decisions_path,
    )

    retry_item = canonicalization._retry_qwen_batch_item(
        source_task=base_batch[1],
        qwen_payload=base_results[1],
        verifier_payload={},
        decision={"decision": "retry_qwen", "reviewer_hash": "reviewer:base"},
    )
    canonicalization._bind_canonicalization_batch_identity([retry_item])
    _write_jsonl(retry_batch_path, [retry_item])
    retry_result = _canonical_result(retry_item)
    retry_result["canonicalization_run_id"] = "tg-question-canonicalization-run:fixture-retry"
    retry_result["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(retry_result)
    _write_jsonl(retry_results_path, [retry_result])
    _write_jsonl(
        retry_decisions_raw_path,
        [
            {
                "task_id": retry_item["task_id"],
                "candidate_id": retry_item["candidate_id"],
                "decision": "accept",
                "reviewer_hash": "reviewer:retry",
                "reviewed_at": "2026-07-10T00:00:00Z",
            }
        ],
    )
    import_tg_qa_canonicalization_review_decisions(
        batch_path=retry_batch_path,
        qwen_results_path=retry_results_path,
        decisions_path=retry_decisions_raw_path,
        output_path=retry_decisions_path,
        summary_output_path=retry_decisions_summary_path,
    )
    build_tg_qa_canonicalization_routing(
        batch_path=retry_batch_path,
        qwen_results_path=retry_results_path,
        output_path=retry_routed_path,
        summary_output_path=retry_routing_summary_path,
        review_decisions_path=retry_decisions_path,
    )

    finalization = finalize_tg_qa_canonicalization_results(
        batch_path=batch_path,
        base_accepted_results_path=base_routed_path,
        replacement_accepted_result_specs=[f"retry={retry_routed_path}"],
        replacement_batch_specs=[f"retry={retry_batch_path}"],
        output_path=finalized_path,
        manifest_output_path=final_manifest_path,
        backlog_output_path=final_backlog_path,
    )

    finalized_by_task = {item["task_id"]: item for item in _read_jsonl(finalized_path)}
    replacement = finalized_by_task[base_batch[1]["task_id"]]
    assert finalization["manifest"]["backlog_count"] == 0
    assert replacement["canonicalization_run_id"] == "tg-question-canonicalization-run:fixture-retry"
    assert replacement["finalization_provenance"]["source_label"] == "retry"
    assert replacement["finalization_provenance"]["source_root_identity"] == canonicalization._canonicalization_root_identity(
        base_batch[1]
    )


def test_canonicalization_import_rejects_cjk_characters_in_result_fields(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    summary_path = tmp_path / "batch_summary.json"
    result_path = tmp_path / "results.jsonl"
    evidence_path = tmp_path / "evidence.jsonl"
    manifest_path = tmp_path / "manifest.json"
    _write_jsonl(
        candidates_path,
        [_candidate("tg-qa-candidate:1", "Можно ли сменить работодателя с Blue Card?", "m1")],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=summary_path,
        filter_mode="law_or_topic",
    )
    batch = _read_jsonl(batch_path)
    bad_result = _canonical_result(batch[0])
    bad_result["canonical_question"] = "Можно ли 持有 сменить работодателя с Blue Card?"
    _write_jsonl(result_path, [bad_result])

    import_result = import_tg_qa_canonicalization_results(
        batch_path=batch_path,
        result_path=result_path,
        output_path=evidence_path,
        manifest_output_path=manifest_path,
        canonicalization_run_id="tg-question-canonicalization-run:test",
    )

    evidence = _read_jsonl(evidence_path)
    assert import_result["manifest"]["failed_count"] == 1
    assert evidence[0]["status"] == "failed"
    assert evidence[0]["failure_reason"] == "contract_invalid:cjk_characters_detected:canonical_question"


def test_canonicalization_sample_and_review_cards_use_compact_operator_payloads(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    sample_path = tmp_path / "sample.jsonl"
    sample_summary_path = tmp_path / "sample_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    verifier_results_path = tmp_path / "verifier_results.jsonl"
    review_html_path = tmp_path / "review.html"
    review_summary_path = tmp_path / "review_summary.json"
    candidates = [
        _candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", "m1"),
        _candidate("tg-qa-candidate:2", "Как продлить Blue Card?", "m2"),
        {
            **_candidate("tg-qa-candidate:3", "Можно ли работать студенту?", "m3"),
            "topic_labels": ["work_authorization"],
            "answer_candidate_status": "weak",
        },
        {
            **_candidate("tg-qa-candidate:4", "Что нужно для воссоединения семьи?", "m4"),
            "topic_labels": ["family_reunification"],
            "answer_candidate_status": "missing",
        },
    ]
    _write_jsonl(candidates_path, candidates)
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="law_or_topic",
    )

    sample_result = sample_tg_qa_canonicalization_batch(
        batch_path=batch_path,
        output_path=sample_path,
        summary_output_path=sample_summary_path,
        sample_size=3,
    )

    sample = _read_jsonl(sample_path)
    assert sample_result["summary"]["emitted_sample_count"] == 3
    assert len({item["task_id"] for item in sample}) == 3
    assert sample_result["summary"]["sampling_policy"] == (
        "deterministic_round_robin_by_answer_status_and_first_topic_label"
    )
    assert sample_result["summary"]["sampling_policy_id"] == "balanced"
    assert sample_result["summary"]["sample_seed"] == ""

    qwen_result = _canonical_result(sample[0])
    _write_jsonl(qwen_results_path, [qwen_result])
    _write_jsonl(
        verifier_results_path,
        [
            {
                "task_id": sample[0]["task_id"],
                "verdict": "uncertain",
                "confidence": 71,
                "risk": "medium",
                "bad_fields": ["hidden_issues"],
                "short_reason": "Needs human review.",
                "suggested_action": "human_review",
            }
        ],
    )
    review_result = export_tg_qa_canonicalization_review_cards(
        batch_path=sample_path,
        html_output_path=review_html_path,
        summary_output_path=review_summary_path,
        qwen_results_path=qwen_results_path,
        verifier_results_path=verifier_results_path,
    )

    html = review_html_path.read_text(encoding="utf-8")
    cards = review_result["cards"]
    assert review_result["summary"]["card_count"] == 3
    assert cards[0]["input"]["question_date"] == sample[0]["input"]["question_date"]
    assert cards[0]["qwen"]["canonical_question"] == sample[0]["input"]["question_text_redacted"]
    assert cards[0]["verifier"]["verdict"] == "uncertain"
    assert cards[0]["review_binding"]["qwen_canonicalization_evidence_hash"] == (
        qwen_result["canonicalization_evidence_hash"]
    )
    assert cards[0]["review_payload_version"] == (
        canonicalization.CANONICALIZATION_REVIEW_PAYLOAD_VERSION
    )
    assert cards[0]["review_payload_hash"]
    assert "retry_context" in cards[0]
    assert "Export JSONL" in html
    assert "retry decision reason" in html
    assert "date=${card.input.question_date || 'unknown'}" in html
    assert "manual canonicalization JSON" in html
    assert "manual_canonicalization_text" in html
    assert "review_payload_version: card.review_payload_version" in html
    assert "review_payload_hash: card.review_payload_hash" in html
    assert "reviewer_hash" not in html
    assert 'a.download = "review_decisions.jsonl"' in html
    assert 'const storageKey = "tg007ReviewDecisions:review"' in html
    assert "source_message_ids" not in html
    assert "expected_output_schema" not in html

    _write_jsonl(
        verifier_results_path,
        [
            {
                "artifact_type": "tg_qa_canonicalization_atomic_verify_repair_record",
                "operator_stage": "atomic_verify_repair",
                "task_id": sample[0]["task_id"],
                "status": "completed",
                "route": "pass_repaired",
                "repair_attempted": True,
                "changed_fields": ["hidden_issues"],
                "initial_verification": {
                    "short_reason": "One unsupported claim was repaired."
                },
                "initial_controller": {
                    "feedback": [
                        {
                            "field_name": "hidden_issues",
                            "short_reason": "The original mechanism was unsupported.",
                            "correction": "Use the source-grounded mechanism.",
                        }
                    ]
                },
                "repaired_candidate": {
                    "hidden_issues": ["source-grounded mechanism"]
                },
            }
        ],
    )
    atomic_review = export_tg_qa_canonicalization_review_cards(
        batch_path=sample_path,
        html_output_path=review_html_path,
        summary_output_path=review_summary_path,
        qwen_results_path=qwen_results_path,
        verifier_results_path=verifier_results_path,
    )
    atomic_view = atomic_review["cards"][0]["verifier"]
    assert atomic_view["verdict"] == "pass"
    assert atomic_view["risk"] == "medium"
    assert atomic_view["bad_fields"] == ["hidden_issues"]
    assert '"source-grounded mechanism"' in atomic_view["short_reason"]
    assert atomic_view["suggested_action"] == "human_review"


def test_canonicalization_stable_hash_sample_is_seeded_and_reproducible(
    tmp_path: Path,
) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    candidates = [
        _candidate(
            f"tg-qa-candidate:stable-sample-{index}",
            f"Можно ли изменить условие договора {index}?",
            f"m{index}",
        )
        for index in range(20)
    ]
    _write_jsonl(candidates_path, candidates)
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="all",
    )

    selections = []
    summaries = []
    for label, seed in (
        ("first", "qualification-v1"),
        ("repeat", "qualification-v1"),
        ("other", "qualification-v2"),
    ):
        output_path = tmp_path / f"{label}.jsonl"
        summary_path = tmp_path / f"{label}.json"
        result = sample_tg_qa_canonicalization_batch(
            batch_path=batch_path,
            output_path=output_path,
            summary_output_path=summary_path,
            sample_size=6,
            sampling_policy="stable_hash",
            sample_seed=seed,
        )
        selections.append([item["task_id"] for item in _read_jsonl(output_path)])
        summaries.append(result["summary"])

    assert selections[0] == selections[1]
    assert selections[0] != selections[2]
    assert summaries[0]["sampling_policy_id"] == "stable_hash"
    assert summaries[0]["sampling_policy"] == (
        "deterministic_sha256_order_over_seed_and_task_id"
    )
    assert summaries[0]["sample_seed"] == "qualification-v1"
    assert summaries[0]["selected_task_id_hash"] == summaries[1]["selected_task_id_hash"]
    assert summaries[0]["source_canonicalization_batch_id"]
    assert summaries[0]["source_canonicalization_batch_hash"]
    with pytest.raises(ValueError, match="sample_seed is required"):
        sample_tg_qa_canonicalization_batch(
            batch_path=batch_path,
            output_path=tmp_path / "missing-seed.jsonl",
            summary_output_path=tmp_path / "missing-seed.json",
            sample_size=6,
            sampling_policy="stable_hash",
        )


def test_review_import_binds_decision_to_exact_rendered_payload(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    decisions_path = tmp_path / "review_decisions.jsonl"
    imported_path = tmp_path / "imported.jsonl"
    imported_summary_path = tmp_path / "imported_summary.json"
    changed_imported_path = tmp_path / "changed_imported.jsonl"
    changed_summary_path = tmp_path / "changed_summary.json"

    _write_jsonl(
        candidates_path,
        [_candidate("tg-qa-candidate:review-binding", "Можно ли сменить работодателя?", "m1")],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="all",
    )
    batch_item = _read_jsonl(batch_path)[0]
    qwen_result = _canonical_result(batch_item)
    _write_jsonl(qwen_results_path, [qwen_result])
    review_card = canonicalization._review_card_record(
        batch_item,
        qwen_result=qwen_result,
        verifier_result=None,
    )
    _write_jsonl(
        decisions_path,
        [
            {
                "task_id": batch_item["task_id"],
                "candidate_id": batch_item["candidate_id"],
                "decision": "accept",
                "review_payload_version": review_card["review_payload_version"],
                "review_payload_hash": review_card["review_payload_hash"],
            }
        ],
    )

    valid = import_tg_qa_canonicalization_review_decisions(
        batch_path=batch_path,
        qwen_results_path=qwen_results_path,
        decisions_path=decisions_path,
        output_path=imported_path,
        summary_output_path=imported_summary_path,
    )
    valid_record = _read_jsonl(imported_path)[0]
    assert valid_record["status"] == "completed"
    assert valid_record["review_payload_version"] == (
        canonicalization.CANONICALIZATION_REVIEW_PAYLOAD_VERSION
    )
    assert valid_record["review_evidence_binding_status"] == "validated"
    assert valid["summary"]["counts_by_review_evidence_binding_status"] == {
        "validated": 1
    }

    decision_without_version = canonicalization._canonicalization_review_decision_record(
        {
            "task_id": batch_item["task_id"],
            "candidate_id": batch_item["candidate_id"],
            "decision": "accept",
            "review_payload_hash": review_card["review_payload_hash"],
        },
        tasks_by_id={batch_item["task_id"]: batch_item},
        qwen_by_task={batch_item["task_id"]: qwen_result},
        verifier_by_task={},
    )
    assert decision_without_version["failure_reason"] == "review_payload_version_missing"
    assert decision_without_version["review_evidence_binding_status"] == "missing_version"

    decision_with_unknown_version = canonicalization._canonicalization_review_decision_record(
        {
            "task_id": batch_item["task_id"],
            "candidate_id": batch_item["candidate_id"],
            "decision": "accept",
            "review_payload_version": "tg_qa_canonicalization_review_payload_v0",
            "review_payload_hash": review_card["review_payload_hash"],
        },
        tasks_by_id={batch_item["task_id"]: batch_item},
        qwen_by_task={batch_item["task_id"]: qwen_result},
        verifier_by_task={},
    )
    assert decision_with_unknown_version["failure_reason"] == (
        "unsupported_review_payload_version:tg_qa_canonicalization_review_payload_v0"
    )
    assert decision_with_unknown_version["review_evidence_binding_status"] == (
        "unsupported_version"
    )

    qwen_result["canonical_question"] = "Можно ли сменить работодателя без согласования?"
    qwen_result["canonicalization_evidence_hash"] = (
        canonicalization._canonicalization_evidence_hash(qwen_result)
    )
    _write_jsonl(qwen_results_path, [qwen_result])
    changed = import_tg_qa_canonicalization_review_decisions(
        batch_path=batch_path,
        qwen_results_path=qwen_results_path,
        decisions_path=decisions_path,
        output_path=changed_imported_path,
        summary_output_path=changed_summary_path,
    )
    changed_record = _read_jsonl(changed_imported_path)[0]
    assert changed_record["status"] == "failed"
    assert changed_record["failure_reason"] == "review_payload_hash_mismatch"
    assert changed_record["review_evidence_binding_status"] == "mismatch"
    assert changed["summary"]["failed_count"] == 1


def test_manual_review_canonicalization_override_accepts_failed_qwen_result(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    review_export_path = tmp_path / "review_decisions.jsonl"
    imported_decisions_path = tmp_path / "imported_review_decisions.jsonl"
    imported_decisions_summary_path = tmp_path / "imported_review_decisions_summary.json"
    routed_results_path = tmp_path / "routed_results.jsonl"
    routed_summary_path = tmp_path / "routed_summary.json"
    decision_ledger_path = tmp_path / "decision_ledger.jsonl"
    backlog_path = tmp_path / "backlog.jsonl"

    _write_jsonl(
        candidates_path,
        [
            _candidate(
                "tg-qa-candidate:1",
                "Я хочу уволиться с мини джоб после испытательного срока. Сколько нужно отработать?",
                "m1",
            )
        ],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="all",
    )
    batch = _read_jsonl(batch_path)
    failed_qwen = canonicalization._operator_failed_canonicalization_record(
        batch[0],
        canonicalization_run_id="tg-question-canonicalization-run:qwen-failed",
        failure_reason="contract_invalid:cjk_characters_detected:canonical_question",
        runtime_contour="fixture",
        backend="opencode",
        model_id="qwen3.6-plus",
    )
    failed_qwen["candidate_id"] = "tg-qa-candidate:stale-runtime-id"
    manual_canonicalization = {
        "canonical_question": "Какой срок уведомления нужно соблюдать при увольнении с mini-job после испытательного срока?",
        "canonical_question_language": "ru",
        "legal_issue_frame": "Employee resignation notice period for a mini-job after probation",
        "legal_issue_frame_slug": "employee_resignation_notice_period_for_mini_job_after_probation",
        "law_area": "employment",
        "facts": ["mini-job employment", "probation period has passed", "employee wants to resign"],
        "desired_outcome": "determine required notice period before leaving employment",
        "authority_context": ["employer"],
        "hidden_issues": ["employment contract notice clause", "statutory employee notice period"],
        "is_legal_answer_required": True,
        "is_standalone_question": True,
        "exclusion_reason": "none",
        "confidence": "high",
        "quality_flags": [],
    }
    _write_jsonl(qwen_results_path, [failed_qwen])
    _write_jsonl(
        review_export_path,
        [
            {
                "task_id": batch[0]["task_id"],
                "candidate_id": batch[0]["candidate_id"],
                "decision": "accept",
                "reviewer_hash": "reviewer:fixture",
                "manual_canonicalization": manual_canonicalization,
            }
        ],
    )

    import_result = import_tg_qa_canonicalization_review_decisions(
        batch_path=batch_path,
        qwen_results_path=qwen_results_path,
        decisions_path=review_export_path,
        output_path=imported_decisions_path,
        summary_output_path=imported_decisions_summary_path,
    )
    routing_result = build_tg_qa_canonicalization_routing(
        batch_path=batch_path,
        qwen_results_path=qwen_results_path,
        output_path=routed_results_path,
        summary_output_path=routed_summary_path,
        review_decisions_path=imported_decisions_path,
        decision_ledger_output_path=decision_ledger_path,
        backlog_output_path=backlog_path,
    )

    imported = _read_jsonl(imported_decisions_path)
    accepted = _read_jsonl(routed_results_path)
    ledger = _read_jsonl(decision_ledger_path)
    backlog = _read_jsonl(backlog_path)
    assert import_result["summary"]["counts_by_decision"] == {"accept": 1}
    assert imported[0]["manual_canonicalization"]["canonical_question"] == manual_canonicalization["canonical_question"]
    assert routing_result["summary"]["accepted_result_count"] == 1
    assert routing_result["summary"]["backlog_count"] == 0
    assert accepted[0]["backend"] == "human_review"
    assert accepted[0]["candidate_id"] == batch[0]["candidate_id"]
    assert accepted[0]["model_id"] == "manual_override"
    assert accepted[0]["status"] == "completed"
    assert accepted[0]["exclusion_reason"] == "none"
    assert accepted[0]["canonical_question"] == manual_canonicalization["canonical_question"]
    assert "manual_canonicalization_override" in accepted[0]["quality_flags"]
    assert ledger[0]["manual_canonicalization_status"] == "present"
    assert ledger[0]["candidate_id"] == batch[0]["candidate_id"]
    assert backlog == []


def test_partial_review_import_and_routing_keep_unreviewed_majority_scalable(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    verifier_results_path = tmp_path / "verifier_results.jsonl"
    review_export_path = tmp_path / "review_decisions_disputed.jsonl"
    imported_decisions_path = tmp_path / "imported_review_decisions.jsonl"
    imported_decisions_summary_path = tmp_path / "imported_review_decisions_summary.json"
    routed_results_path = tmp_path / "routed_results.jsonl"
    routed_summary_path = tmp_path / "routed_summary.json"
    decision_ledger_path = tmp_path / "decision_ledger.jsonl"
    retry_qwen_batch_path = tmp_path / "retry_qwen_batch.jsonl"
    send_deepseek_batch_path = tmp_path / "send_deepseek_batch.jsonl"
    backlog_path = tmp_path / "backlog.jsonl"

    _write_jsonl(
        candidates_path,
        [
            _candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", "m1"),
            _candidate("tg-qa-candidate:2", "Где купить детскую смесь в Кронахе?", "m2"),
            _candidate("tg-qa-candidate:3", "Как обновить статус в C24 при автоматическом продлении?", "m3"),
            _candidate("tg-qa-candidate:4", "Считается ли это вообще legal case или просто жалоба?", "m4"),
        ],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="all",
    )
    batch = _read_jsonl(batch_path)

    qwen_records = [
        _canonical_result(batch[0], confidence="high"),
        {
            **_canonical_result(batch[1], confidence="high"),
            "canonical_question": "",
            "legal_issue_frame": "",
            "legal_issue_frame_slug": "",
            "law_area": "",
            "facts": [],
            "desired_outcome": "",
            "authority_context": [],
            "hidden_issues": [],
            "is_legal_answer_required": False,
            "is_standalone_question": True,
            "exclusion_reason": "non_legal_question",
            "quality_flags": ["topic_hint_false_positive"],
        },
        _canonical_result(batch[2], confidence="medium"),
        _canonical_result(batch[3], confidence="medium"),
    ]
    for record in qwen_records:
        record["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(record)
    verifier_records = [
        {
            "task_id": batch[2]["task_id"],
            "verdict": "fail",
            "confidence": 82,
            "risk": "medium",
            "bad_fields": ["law_area"],
            "short_reason": "Law area looks too narrow for the dispute framing.",
            "suggested_action": "retry_qwen",
        },
        {
            "task_id": batch[3]["task_id"],
            "verdict": "uncertain",
            "confidence": 58,
            "risk": "medium",
            "bad_fields": ["is_legal_answer_required"],
            "short_reason": "Escalate for alternative model adjudication.",
            "suggested_action": "send_deepseek",
        },
    ]
    _write_jsonl(qwen_results_path, qwen_records)
    _write_jsonl(verifier_results_path, verifier_records)
    _write_jsonl(
        review_export_path,
        [
            {
                "task_id": batch[2]["task_id"],
                "candidate_id": batch[2]["candidate_id"],
                "decision": "retry_qwen",
                "reviewer_hash": "reviewer:fixture",
            },
            {
                "task_id": batch[3]["task_id"],
                "candidate_id": batch[3]["candidate_id"],
                "decision": "send_deepseek",
                "reviewer_hash": "reviewer:fixture",
                "decision_reason": "bank_status_proof_conflict",
            },
        ],
    )

    import_result = import_tg_qa_canonicalization_review_decisions(
        batch_path=batch_path,
        qwen_results_path=qwen_results_path,
        decisions_path=review_export_path,
        output_path=imported_decisions_path,
        summary_output_path=imported_decisions_summary_path,
        verifier_results_path=verifier_results_path,
    )
    routing_result = build_tg_qa_canonicalization_routing(
        batch_path=batch_path,
        qwen_results_path=qwen_results_path,
        output_path=routed_results_path,
        summary_output_path=routed_summary_path,
        review_decisions_path=imported_decisions_path,
        verifier_results_path=verifier_results_path,
        decision_ledger_output_path=decision_ledger_path,
        retry_qwen_batch_output_path=retry_qwen_batch_path,
        send_deepseek_batch_output_path=send_deepseek_batch_path,
        backlog_output_path=backlog_path,
        unreviewed_policy="first_pass",
    )

    imported = _read_jsonl(imported_decisions_path)
    accepted = _read_jsonl(routed_results_path)
    ledger = _read_jsonl(decision_ledger_path)
    retry_batch = _read_jsonl(retry_qwen_batch_path)
    deepseek_batch = _read_jsonl(send_deepseek_batch_path)
    backlog = _read_jsonl(backlog_path)

    assert import_result["summary"]["imported_count"] == 2
    assert import_result["summary"]["counts_by_decision"] == {"retry_qwen": 1, "send_deepseek": 1}
    assert {item["decision"] for item in imported} == {"retry_qwen", "send_deepseek"}

    assert routing_result["summary"]["accepted_result_count"] == 1
    assert routing_result["summary"]["counts_by_decision"] == {
        "accept": 1,
        "reject": 1,
        "retry_qwen": 1,
        "send_deepseek": 1,
    }
    assert routed_summary_path.exists()
    assert [item["task_id"] for item in accepted] == [batch[0]["task_id"]]

    ledger_by_task = {item["task_id"]: item for item in ledger}
    assert ledger_by_task[batch[0]["task_id"]]["decision"] == "accept"
    assert ledger_by_task[batch[0]["task_id"]]["decision_source"] == "explicit_first_pass_accept_qwen_included"
    assert ledger_by_task[batch[1]["task_id"]]["decision"] == "reject"
    assert ledger_by_task[batch[1]["task_id"]]["decision_source"] == "explicit_first_pass_reject_qwen_exclusion"
    assert ledger_by_task[batch[2]["task_id"]]["decision"] == "retry_qwen"
    assert ledger_by_task[batch[2]["task_id"]]["decision_source"] == "human_review"
    assert ledger_by_task[batch[3]["task_id"]]["decision"] == "send_deepseek"
    assert ledger_by_task[batch[3]["task_id"]]["decision_reason"] == "bank_status_proof_conflict"

    assert [item["task_id"] for item in retry_batch] == [batch[2]["task_id"]]
    assert retry_batch[0]["input"]["question_text_redacted"] == batch[2]["input"]["question_text_redacted"]
    assert retry_batch[0]["retry_context"]["previous_candidate"]["law_area"] == "migration_status"
    assert retry_batch[0]["retry_context"]["verifier_votes"][0]["bad_fields"] == ["law_area"]
    assert retry_batch[0]["retry_context"]["human_triage"]["decision"] == "retry_qwen"
    assert [item["task_id"] for item in deepseek_batch] == [batch[3]["task_id"]]
    assert (
        deepseek_batch[0]["adjudication_prompt_version"]
        == canonicalization.CANONICALIZATION_ADJUDICATOR_PROMPT_VERSION
    )
    assert deepseek_batch[0]["human_triage"]["decision"] == "send_deepseek"
    assert deepseek_batch[0]["human_triage"]["decision_reason"] == "bank_status_proof_conflict"
    assert deepseek_batch[0]["candidates"][0]["candidate_key"] == "primary"

    assert {item["decision"] for item in backlog} == {"reject", "retry_qwen", "send_deepseek"}
    assert batch[1]["input"]["question_text_redacted"] in {
        item["source_question_text_redacted"] for item in backlog if item["decision"] == "reject"
    }


def test_adjudication_batch_supports_variable_verifier_counts_and_non_unanimous_filter(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    deepseek_results_path = tmp_path / "deepseek_results.jsonl"
    qwen_qwen_verifier_path = tmp_path / "qwen_qwen_verifier.jsonl"
    deepseek_qwen_verifier_path = tmp_path / "deepseek_qwen_verifier.jsonl"
    qwen_mimo_verifier_path = tmp_path / "qwen_mimo_verifier.jsonl"
    adjudication_batch_path = tmp_path / "adjudication_batch.jsonl"
    adjudication_summary_path = tmp_path / "adjudication_summary.json"
    adjudication_results_path = tmp_path / "adjudication_results.jsonl"
    adjudication_results_path_2 = tmp_path / "adjudication_results_2.jsonl"
    retry_batch_path = tmp_path / "retry_batch.jsonl"
    retry_summary_path = tmp_path / "retry_summary.json"
    multi_retry_batch_path = tmp_path / "multi_retry_batch.jsonl"
    multi_retry_summary_path = tmp_path / "multi_retry_summary.json"
    blocked_retry_batch_path = tmp_path / "blocked_retry_batch.jsonl"
    blocked_retry_summary_path = tmp_path / "blocked_retry_summary.json"
    manual_retry_results_path = tmp_path / "manual_retry_results.jsonl"
    manual_retry_batch_path = tmp_path / "manual_retry_batch.jsonl"
    manual_retry_summary_path = tmp_path / "manual_retry_summary.json"

    _write_jsonl(
        candidates_path,
        [
            _candidate("tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", "m1"),
            _candidate("tg-qa-candidate:2", "Работает ли Ausländerbehörde в воскресенье?", "m2"),
        ],
    )
    emit_tg_qa_canonicalization_batch(
        candidates_path=candidates_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
        filter_mode="all",
    )
    batch = _read_jsonl(batch_path)

    qwen_results = [
        _canonical_result(batch[0], confidence="high"),
        _canonical_result(batch[1], confidence="high"),
    ]
    deepseek_results = [
        _canonical_result(batch[0], confidence="high"),
        {
            **_canonical_result(batch[1], confidence="high"),
            "canonical_question": "",
            "legal_issue_frame": "",
            "legal_issue_frame_slug": "",
            "law_area": "",
            "facts": [],
            "desired_outcome": "",
            "authority_context": [],
            "hidden_issues": [],
            "is_legal_answer_required": False,
            "is_standalone_question": True,
            "exclusion_reason": "non_legal_question",
            "quality_flags": ["topic_hint_false_positive"],
        },
    ]
    for record in [*qwen_results, *deepseek_results]:
        record["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(record)
    qwen_qwen_verifier = [
        {
            "task_id": batch[0]["task_id"],
            "verdict": "pass",
            "confidence": 95,
            "risk": "low",
            "bad_fields": [],
            "short_reason": "Consistent.",
                "suggested_action": "accept",
                "status": "completed",
                "model_id": "qwen3.6-plus",
                "canonicalization_evidence_hash": qwen_results[0]["canonicalization_evidence_hash"],
        },
        {
            "task_id": batch[1]["task_id"],
            "verdict": "uncertain",
            "confidence": 55,
            "risk": "medium",
            "bad_fields": ["is_legal_answer_required"],
            "short_reason": "Operational-vs-legal boundary is unclear.",
                "suggested_action": "retry_qwen",
                "status": "completed",
                "model_id": "qwen3.6-plus",
                "canonicalization_evidence_hash": qwen_results[1]["canonicalization_evidence_hash"],
        },
    ]
    qwen_mimo_verifier = [
        {
            "task_id": batch[0]["task_id"],
            "verdict": "pass",
            "confidence": 92,
            "risk": "low",
            "bad_fields": [],
            "short_reason": "Consistent.",
                "suggested_action": "accept",
                "status": "completed",
                "model_id": "mimo-v2.5-pro",
                "canonicalization_evidence_hash": qwen_results[0]["canonicalization_evidence_hash"],
        }
    ]
    deepseek_qwen_verifier = [
        {
            "task_id": batch[0]["task_id"],
            "verdict": "pass",
            "confidence": 93,
            "risk": "low",
            "bad_fields": [],
            "short_reason": "Consistent.",
                "suggested_action": "accept",
                "status": "completed",
                "model_id": "qwen3.6-plus",
                "canonicalization_evidence_hash": deepseek_results[0]["canonicalization_evidence_hash"],
        },
        {
            "task_id": batch[1]["task_id"],
            "verdict": "fail",
            "confidence": 89,
            "risk": "medium",
            "bad_fields": ["exclusion_reason"],
            "short_reason": "The source should be excluded as non-legal.",
                "suggested_action": "retry_qwen",
                "status": "completed",
                "model_id": "qwen3.6-plus",
                "canonicalization_evidence_hash": deepseek_results[1]["canonicalization_evidence_hash"],
        },
    ]
    _write_jsonl(qwen_results_path, qwen_results)
    _write_jsonl(deepseek_results_path, deepseek_results)
    _write_jsonl(qwen_qwen_verifier_path, qwen_qwen_verifier)
    _write_jsonl(qwen_mimo_verifier_path, qwen_mimo_verifier)
    _write_jsonl(deepseek_qwen_verifier_path, deepseek_qwen_verifier)

    result = build_tg_qa_canonicalization_adjudication_batch(
        batch_path=batch_path,
        candidate_result_specs=[
            f"qwen={qwen_results_path}",
            f"deepseek={deepseek_results_path}",
        ],
        verifier_result_specs=[
            f"qwen:qwen={qwen_qwen_verifier_path}",
            f"qwen:mimo={qwen_mimo_verifier_path}",
            f"deepseek:qwen={deepseek_qwen_verifier_path}",
        ],
        output_path=adjudication_batch_path,
        summary_output_path=adjudication_summary_path,
        mode="non_unanimous",
    )

    records = _read_jsonl(adjudication_batch_path)
    assert result["summary"]["emitted_task_count"] == 1
    assert result["summary"]["counts"]["filtered_unanimous"] == 1
    assert records[0]["task_id"] == batch[1]["task_id"]
    assert len(records[0]["candidates"]) == 2
    assert len(records[0]["verifier_votes"]) == 2
    assert records[0]["consensus_summary"]["unanimous"] is False
    assert "candidate_signature_disagreement" in records[0]["consensus_summary"]["escalation_reason_codes"]
    assert "verifier_uncertain" in records[0]["consensus_summary"]["escalation_reason_codes"]
    candidate_summaries = {
        item["candidate_key"]: item
        for item in records[0]["consensus_summary"]["candidate_summaries"]
    }
    assert candidate_summaries["qwen"]["vote_count"] == 1
    assert candidate_summaries["deepseek"]["vote_count"] == 1

    _write_jsonl(
        adjudication_results_path,
        [
            {
                "task_id": batch[1]["task_id"],
                "candidate_id": batch[1]["candidate_id"],
                "status": "completed",
                "verdict": "uncertain",
                "confidence": 70,
                "risk": "medium",
                "bad_fields": ["is_legal_answer_required"],
                "short_reason": "Retry with clearer operational-vs-legal framing.",
                "final_recommendation": "retry_generator",
                "selected_candidate_key": "qwen",
                "model_id": "fixture-judge",
                "adjudication_run_id": "fixture-adjudication-run",
            }
        ],
    )
    retry_result = build_tg_qa_canonicalization_retry_batch_from_adjudication(
        batch_path=batch_path,
        adjudication_batch_path=adjudication_batch_path,
        adjudication_results_path=adjudication_results_path,
        output_path=retry_batch_path,
        summary_output_path=retry_summary_path,
    )
    retry_records = _read_jsonl(retry_batch_path)
    assert retry_result["summary"]["emitted_task_count"] == 1
    assert retry_records[0]["task_id"] == batch[1]["task_id"]
    assert retry_records[0]["retry_context"]["previous_candidate"]["candidate_key"] == "qwen"
    assert retry_records[0]["retry_context"]["verifier_votes"][0]["verifier_key"] == "qwen"
    assert retry_records[0]["retry_context"]["adjudication"]["final_recommendation"] == "retry_generator"
    assert retry_records[0]["retry_context"]["adjudication_results"][0]["final_recommendation"] == "retry_generator"

    _write_jsonl(
        adjudication_results_path_2,
        [
            {
                "task_id": batch[1]["task_id"],
                "candidate_id": batch[1]["candidate_id"],
                "status": "completed",
                "verdict": "uncertain",
                "confidence": 74,
                "risk": "medium",
                "bad_fields": ["is_legal_answer_required"],
                "short_reason": "Second judge also wants retry for the same field.",
                "final_recommendation": "retry_generator",
                "selected_candidate_key": "qwen",
                "model_id": "fixture-judge-2",
                "adjudication_run_id": "fixture-adjudication-run-2",
            }
        ],
    )
    multi_retry_result = build_tg_qa_canonicalization_retry_batch_from_adjudication(
        batch_path=batch_path,
        adjudication_batch_path=adjudication_batch_path,
        adjudication_results_paths=[
            f"judge1={adjudication_results_path}",
            f"judge2={adjudication_results_path_2}",
        ],
        output_path=multi_retry_batch_path,
        summary_output_path=multi_retry_summary_path,
    )
    multi_retry_records = _read_jsonl(multi_retry_batch_path)
    assert multi_retry_result["summary"]["emitted_task_count"] == 1
    assert len(multi_retry_records[0]["retry_context"]["adjudication_results"]) == 2
    assert {
        item["result_key"] for item in multi_retry_records[0]["retry_context"]["adjudication_results"]
    } == {"judge1", "judge2"}
    assert multi_retry_records[0]["retry_context"]["retry_triage"]["route"] == "auto_retry"

    _write_jsonl(
        adjudication_results_path_2,
        [
            {
                "task_id": batch[1]["task_id"],
                "candidate_id": batch[1]["candidate_id"],
                "status": "completed",
                "verdict": "fail",
                "confidence": 88,
                "risk": "medium",
                "bad_fields": ["law_area"],
                "short_reason": "Different judge wants retry for law area.",
                "final_recommendation": "retry_generator",
                "selected_candidate_key": "qwen",
                "model_id": "fixture-judge-2",
                "adjudication_run_id": "fixture-adjudication-run-2",
            }
        ],
    )
    cautious_retry_result = build_tg_qa_canonicalization_retry_batch_from_adjudication(
        batch_path=batch_path,
        adjudication_batch_path=adjudication_batch_path,
        adjudication_results_paths=[
            f"judge1={adjudication_results_path}",
            f"judge2={adjudication_results_path_2}",
        ],
        output_path=blocked_retry_batch_path,
        summary_output_path=blocked_retry_summary_path,
    )
    cautious_retry_records = _read_jsonl(blocked_retry_batch_path)
    assert cautious_retry_result["summary"]["emitted_task_count"] == 0
    assert cautious_retry_records == []
    assert cautious_retry_result["summary"]["skipped_reasons"] == {
        "human_review_before_retry:material_retry_disagreement_requires_human_review": 1
    }

    _write_jsonl(
        manual_retry_results_path,
        [
            {
                "task_id": batch[1]["task_id"],
                "candidate_id": batch[1]["candidate_id"],
                "status": "completed",
                "verdict": "fail",
                "confidence": 100,
                "risk": "medium",
                "bad_fields": [],
                "short_reason": "Manual reviewer chose retry after inspecting verifier disagreement.",
                "final_recommendation": "retry_generator",
                "selected_candidate_key": "deepseek",
                "model_id": "human-reviewer",
                "adjudication_run_id": "manual-adjudication-review",
            }
        ],
    )
    manual_retry_result = build_tg_qa_canonicalization_retry_batch_from_adjudication(
        batch_path=batch_path,
        adjudication_batch_path=adjudication_batch_path,
        adjudication_results_paths=[
            f"judge1={adjudication_results_path}",
            f"manual={manual_retry_results_path}",
        ],
        output_path=manual_retry_batch_path,
        summary_output_path=manual_retry_summary_path,
    )
    manual_retry_records = _read_jsonl(manual_retry_batch_path)
    assert manual_retry_result["summary"]["emitted_task_count"] == 1
    assert manual_retry_records[0]["retry_context"]["previous_candidate"]["candidate_key"] == "deepseek"
    assert manual_retry_records[0]["retry_context"]["retry_triage"]["reason_code"] == "manual_review_retry"
    assert {
        result["result_key"] for result in manual_retry_records[0]["retry_context"]["adjudication_results"]
    } == {"judge1", "manual"}


def test_canonical_embedding_import_and_issue_clustering_keep_query_semantics(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.jsonl"
    batch_path = tmp_path / "embedding_batch.jsonl"
    batch_summary_path = tmp_path / "embedding_batch_summary.json"
    vectors_path = tmp_path / "vectors.jsonl"
    records_path = tmp_path / "embedding_records.jsonl"
    records_summary_path = tmp_path / "embedding_summary.json"
    clusters_path = tmp_path / "clusters.jsonl"
    clusters_summary_path = tmp_path / "cluster_summary.json"
    clusters_manifest_path = tmp_path / "cluster_manifest.json"
    evidence = [
        _evidence("e1", "tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?", confidence="high"),
        _evidence("e2", "tg-qa-candidate:2", "Как обновить адрес на пластиковой карте ВНЖ?", confidence="medium"),
        _evidence(
            "e3",
            "tg-qa-candidate:3",
            "Где купить кофе?",
            slug="non_legal_noise",
            exclusion_reason="non_legal_question",
        ),
    ]
    _write_jsonl(evidence_path, evidence)

    batch_result = emit_tg_qa_canonical_embedding_batch(
        canonicalization_evidence_path=evidence_path,
        output_path=batch_path,
        summary_output_path=batch_summary_path,
    )

    embedding_batch = _read_jsonl(batch_path)
    assert batch_result["summary"]["emitted_item_count"] == 4
    assert {item["text_role"] for item in embedding_batch} == {"canonical_question", "legal_issue_frame"}
    assert all(item["embedding_input_text"].startswith("Query: ") for item in embedding_batch)

    vector_records = []
    for index, item in enumerate(embedding_batch):
        vector_records.append(
            {
                "embedding_item_id": item["embedding_item_id"],
                "backend_name": "fixture_vectors",
                "vector": [1.0, 0.0, 0.0] if index != 1 else [1.0, 0.0],
            }
        )
    _write_jsonl(vectors_path, vector_records)

    embedding_import = import_tg_qa_canonical_embedding_records(
        embedding_batch_path=batch_path,
        external_vectors_path=vectors_path,
        output_path=records_path,
        summary_output_path=records_summary_path,
        profile_metadata={"embedding_profile_id": "fixture_profile", "dimensions": 3},
    )

    assert embedding_import["summary"]["embedding_profile"]["embedding_profile_id"] == "fixture_profile"
    assert embedding_import["summary"]["completed_count"] == 3
    assert embedding_import["summary"]["failed_count"] == 1

    cluster_result = cluster_tg_qa_legal_issues(
        canonicalization_evidence_path=evidence_path,
        embedding_records_path=records_path,
        output_path=clusters_path,
        summary_output_path=clusters_summary_path,
        manifest_output_path=clusters_manifest_path,
    )

    clusters = _read_jsonl(clusters_path)
    assert cluster_result["summary"]["emitted_cluster_count"] == 1
    assert clusters[0]["cluster_size"] == 2
    assert clusters[0]["review_route"] == "needs_cluster_review"
    assert clusters[0]["representative_raw_questions"]
    assert clusters[0]["merge_policy_version"] == "tg_legal_issue_cluster_policy_v1"
    assert _read_json(clusters_manifest_path)["known_limitations"][0].startswith("clustering is by canonical issue")


def test_legal_intent_pair_benchmark_has_stable_order_independent_ids(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    pairs_summary_path = tmp_path / "pairs_summary.json"
    pairs_second_path = tmp_path / "pairs_second.jsonl"
    pairs_second_summary_path = tmp_path / "pairs_second_summary.json"
    evidence = [
        _evidence("e2", "tg-qa-candidate:2", "Как обновить адрес на пластиковой карте ВНЖ?"),
        _evidence("e1", "tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?"),
        _evidence(
            "e3",
            "tg-qa-candidate:3",
            "Можно ли расторгнуть договор с Telekom?",
            slug="consumer_telecom_contract_cancellation",
            law_area="consumer_protection",
        ),
    ]
    _write_jsonl(evidence_path, evidence)

    first = build_tg_qa_legal_intent_pair_benchmark(
        canonicalization_evidence_path=evidence_path,
        output_path=pairs_path,
        summary_output_path=pairs_summary_path,
        max_random_negatives=1,
    )
    second = build_tg_qa_legal_intent_pair_benchmark(
        canonicalization_evidence_path=evidence_path,
        output_path=pairs_second_path,
        summary_output_path=pairs_second_summary_path,
        max_random_negatives=1,
    )

    pair_ids = [item["pair_id"] for item in _read_jsonl(pairs_path)]
    assert pair_ids == [item["pair_id"] for item in _read_jsonl(pairs_second_path)]
    assert first["summary"]["pair_count"] == second["summary"]["pair_count"] == 2
    assert first["records"][0]["pair_id"] == canonicalization._legal_intent_pair_id("e1", "e2")
    assert first["records"][0]["pair_id"] == canonicalization._legal_intent_pair_id("e2", "e1")
    assert first["records"][0]["left"]["question_date"] == "2024-01-01T00:00:00Z"
    assert "preserved_variant_candidate" in first["summary"]["counts_by_pair_source_reason"]


def test_legal_intent_pair_benchmark_balances_random_negative_anchors(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    pairs_summary_path = tmp_path / "pairs_summary.json"
    evidence = []
    for index in range(12):
        law_area = "migration_status" if index % 2 == 0 else "social_benefits"
        evidence.append(
            _evidence(
                f"e{index:02d}",
                f"tg-qa-candidate:{index:02d}",
                f"Fixture legal question {index}",
                slug=f"fixture_issue_{index:02d}",
                law_area=law_area,
            )
        )
    _write_jsonl(evidence_path, evidence)

    result = build_tg_qa_legal_intent_pair_benchmark(
        canonicalization_evidence_path=evidence_path,
        output_path=pairs_path,
        summary_output_path=pairs_summary_path,
        max_random_negatives=6,
    )

    random_negative_pairs = [
        item
        for item in result["records"]
        if "random_negative" in item.get("pair_source_reasons", [])
    ]
    left_candidate_ids = {item["left_candidate_id"] for item in random_negative_pairs}
    right_candidate_ids = {item["right_candidate_id"] for item in random_negative_pairs}
    assert len(random_negative_pairs) == 6
    assert len(left_candidate_ids) > 1
    assert result["summary"]["random_negative_unique_left_candidate_count"] == len(left_candidate_ids)
    assert result["summary"]["random_negative_unique_right_candidate_count"] == len(right_candidate_ids)


def test_legal_intent_pair_benchmark_accepts_dataset_record_ids_and_task_similarity_pairs(tmp_path: Path) -> None:
    evidence_path = tmp_path / "dataset_records.jsonl"
    similarity_pairs_path = tmp_path / "similarity_pairs.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    pairs_summary_path = tmp_path / "pairs_summary.json"
    left = _evidence(
        "unused-left",
        "tg-qa-candidate:left",
        "Можно ли въехать обратно в Германию по Fiktionsbescheinigung после выезда?",
    )
    right = _evidence(
        "unused-right",
        "tg-qa-candidate:right",
        "Можно ли вернуться в Германию с Fiktionsbescheinigung после поездки?",
    )
    left.pop("canonicalization_evidence_id")
    right.pop("canonicalization_evidence_id")
    left["dataset_record_id"] = "dataset:left"
    right["dataset_record_id"] = "dataset:right"
    _write_jsonl(evidence_path, [left, right])
    _write_jsonl(
        similarity_pairs_path,
        [
            {
                "pair_type": "preserve_as_variant_candidate",
                "canonical_question_score": 0.91,
                "left": {"task_id": left["task_id"], "candidate_id": left["candidate_id"]},
                "right": {"task_id": right["task_id"], "candidate_id": right["candidate_id"]},
            }
        ],
    )

    result = build_tg_qa_legal_intent_pair_benchmark(
        canonicalization_evidence_path=evidence_path,
        similarity_pairs_path=similarity_pairs_path,
        output_path=pairs_path,
        summary_output_path=pairs_summary_path,
    )

    records = result["records"]
    assert len(records) == 1
    assert records[0]["left_canonicalization_evidence_id"] == "dataset:left"
    assert records[0]["right_canonicalization_evidence_id"] == "dataset:right"
    assert "high_canonical_question_similarity" in records[0]["pair_source_reasons"]


def test_legal_intent_candidate_and_pair_decision_import_validate_contracts(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.jsonl"
    candidates_input_path = tmp_path / "intent_candidates_input.jsonl"
    candidates_path = tmp_path / "intent_candidates.jsonl"
    candidates_summary_path = tmp_path / "intent_candidates_summary.json"
    pairs_path = tmp_path / "pairs.jsonl"
    pairs_summary_path = tmp_path / "pairs_summary.json"
    decisions_input_path = tmp_path / "decisions_input.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    decisions_summary_path = tmp_path / "decisions_summary.json"
    evidence = [
        _evidence("e1", "tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?"),
        _evidence("e2", "tg-qa-candidate:2", "Как обновить адрес на пластиковой карте ВНЖ?"),
    ]
    _write_jsonl(evidence_path, evidence)
    _write_jsonl(
        candidates_input_path,
        [
            {
                "canonicalization_evidence_id": "e1",
                "legal_domain": "residence_status",
                "desired_action": "update_residence_document_address",
                "legal_object": "residence_document_address",
                "authority_context": ["Buergeramt"],
                "material_slots_unknown": ["temporal_condition"],
                "evidence_refs": [{"field": "desired_action", "source_field": "canonical_question"}],
                "confidence": "high",
            },
            {
                "canonicalization_evidence_id": "missing",
                "confidence": "medium",
            },
        ],
    )

    candidate_import = import_tg_qa_legal_intent_candidates(
        canonicalization_evidence_path=evidence_path,
        candidates_path=candidates_input_path,
        output_path=candidates_path,
        summary_output_path=candidates_summary_path,
    )

    imported_candidates = _read_jsonl(candidates_path)
    assert candidate_import["summary"]["completed_count"] == 1
    assert candidate_import["summary"]["failed_count"] == 1
    assert "high_confidence_with_unresolved_material_slots" in imported_candidates[0]["validation_flags"]

    build_tg_qa_legal_intent_pair_benchmark(
        canonicalization_evidence_path=evidence_path,
        output_path=pairs_path,
        summary_output_path=pairs_summary_path,
    )
    pair_id = _read_jsonl(pairs_path)[0]["pair_id"]
    _write_jsonl(
        decisions_input_path,
        [
            {
                "pair_id": pair_id,
                "decision_source": "fixture_judge",
                "pair_class": "same_topic_different_issue",
                "answer_equivalence": "not_safe_to_share_answer",
                "canonical_question_equivalence": "not_safe_to_share_question",
                "allowed_downstream_actions": ["route_human_review", "preserve_hard_negative"],
                "material_differences": [{"field": "desired_action", "left": "address", "right": "document"}],
                "short_reason": "Fixture material distinction.",
                "confidence": "medium",
                "risk": "low",
            },
            {
                "pair_id": pair_id,
                "decision_source": "fixture_bad",
                "pair_class": "same_topic_different_issue",
                "answer_equivalence": "safe_to_share_answer",
                "canonical_question_equivalence": "not_safe_to_share_question",
                "allowed_downstream_actions": ["allow_reference_answer_sharing"],
                "confidence": "medium",
                "risk": "low",
            },
        ],
    )

    decision_import = import_tg_qa_legal_intent_pair_decisions(
        pair_benchmark_path=pairs_path,
        decisions_path=decisions_input_path,
        output_path=decisions_path,
        summary_output_path=decisions_summary_path,
    )

    imported_decisions = _read_jsonl(decisions_path)
    assert decision_import["summary"]["completed_count"] == 2
    assert imported_decisions[1]["validation_flags"] == [
        "missing_material_differences_for_non_equivalent_pair",
        "non_equivalent_pair_allows_strict_sharing",
    ]


def test_legal_intent_similarity_baseline_uses_cosine_and_recos(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    pairs_summary_path = tmp_path / "pairs_summary.json"
    similarity_pairs_path = tmp_path / "similarity_pairs.jsonl"
    embedding_records_path = tmp_path / "embedding_records.jsonl"
    decisions_path = tmp_path / "similarity_decisions.jsonl"
    decisions_summary_path = tmp_path / "similarity_decisions_summary.json"
    evidence = [
        _evidence("e1", "tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?"),
        _evidence("e2", "tg-qa-candidate:2", "Как обновить адрес на пластиковой карте ВНЖ?"),
    ]
    _write_jsonl(evidence_path, evidence)
    _write_jsonl(
        similarity_pairs_path,
        [
            {
                "left_canonicalization_evidence_id": "e1",
                "right_canonicalization_evidence_id": "e2",
                "canonical_question_score": 0.74,
                "legal_issue_frame_score": 0.72,
            }
        ],
    )
    _write_jsonl(
        embedding_records_path,
        [
            {
                "candidate_id": "tg-qa-candidate:1",
                "text_role": "canonical_question",
                "embedding_status": "completed",
                "vector": [1.0, 0.0],
            },
            {
                "candidate_id": "tg-qa-candidate:2",
                "text_role": "canonical_question",
                "embedding_status": "completed",
                "vector": [0.9, 0.1],
            },
        ],
    )
    build_tg_qa_legal_intent_pair_benchmark(
        canonicalization_evidence_path=evidence_path,
        similarity_pairs_path=similarity_pairs_path,
        output_path=pairs_path,
        summary_output_path=pairs_summary_path,
    )

    result = build_tg_qa_legal_intent_similarity_baseline(
        pair_benchmark_path=pairs_path,
        embedding_records_path=embedding_records_path,
        output_path=decisions_path,
        summary_output_path=decisions_summary_path,
        same_intent_threshold=0.90,
    )

    decision = _read_jsonl(decisions_path)[0]
    assert result["summary"]["recos_available_count"] == 1
    assert decision["pair_class"] == "same_legal_intent"
    assert decision["answer_equivalence"] == "uncertain"
    assert float(decision["runtime_metadata"]["recos_canonical_question_score"]) >= 0.99
    assert "similarity_only_baseline_not_safe_for_automatic_action" in decision["validation_flags"]


def test_legal_intent_slot_comparator_flags_material_slot_differences(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    pairs_summary_path = tmp_path / "pairs_summary.json"
    candidates_input_path = tmp_path / "intent_candidates_input.jsonl"
    candidates_path = tmp_path / "intent_candidates.jsonl"
    candidates_summary_path = tmp_path / "intent_candidates_summary.json"
    decisions_path = tmp_path / "slot_decisions.jsonl"
    decisions_summary_path = tmp_path / "slot_decisions_summary.json"
    evidence = [
        _evidence("e1", "tg-qa-candidate:1", "Можно ли подать заявление на ВНЖ?"),
        _evidence("e2", "tg-qa-candidate:2", "Можно ли подать заявление на ВНЖ без регистрации?"),
    ]
    _write_jsonl(evidence_path, evidence)
    build_tg_qa_legal_intent_pair_benchmark(
        canonicalization_evidence_path=evidence_path,
        output_path=pairs_path,
        summary_output_path=pairs_summary_path,
    )
    _write_jsonl(
        candidates_input_path,
        [
            {
                "canonicalization_evidence_id": "e1",
                "desired_action": "apply_for_residence_permit",
                "legal_object": "residence_permit",
                "evidence_refs": [{"field": "desired_action", "source_field": "canonical_question"}],
                "confidence": "medium",
            },
            {
                "canonicalization_evidence_id": "e2",
                "desired_action": "apply_for_residence_permit_without_registration",
                "legal_object": "residence_permit_application_condition",
                "evidence_refs": [{"field": "desired_action", "source_field": "canonical_question"}],
                "confidence": "medium",
            },
        ],
    )
    import_tg_qa_legal_intent_candidates(
        canonicalization_evidence_path=evidence_path,
        candidates_path=candidates_input_path,
        output_path=candidates_path,
        summary_output_path=candidates_summary_path,
    )

    result = build_tg_qa_legal_intent_slot_comparator_decisions(
        pair_benchmark_path=pairs_path,
        legal_intent_candidates_path=candidates_path,
        output_path=decisions_path,
        summary_output_path=decisions_summary_path,
    )

    decision = _read_jsonl(decisions_path)[0]
    assert result["summary"]["counts_by_pair_class"] == {"same_topic_different_issue": 1}
    assert decision["answer_equivalence"] == "not_safe_to_share_answer"
    assert decision["material_differences"][0]["field"] == "desired_action"


def test_legal_intent_candidate_extractor_scopes_to_pair_benchmark_and_forces_source_identity(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "evidence.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    pairs_summary_path = tmp_path / "pairs_summary.json"
    results_path = tmp_path / "extractor_results.jsonl"
    summary_path = tmp_path / "extractor_summary.json"
    imported_path = tmp_path / "extractor_imported.jsonl"
    imported_summary_path = tmp_path / "extractor_imported_summary.json"
    evidence = [
        _evidence("e1", "tg-qa-candidate:1", "Можно ли подать заявление на ВНЖ?"),
        _evidence("e2", "tg-qa-candidate:2", "Можно ли подать заявление на ВНЖ без регистрации?"),
        _evidence("e3", "tg-qa-candidate:3", "Можно ли сменить работодателя?"),
    ]
    for item in evidence:
        item.pop("canonicalization_evidence_id")
    _write_jsonl(evidence_path, evidence)
    build_tg_qa_legal_intent_pair_benchmark(
        canonicalization_evidence_path=evidence_path,
        output_path=pairs_path,
        summary_output_path=pairs_summary_path,
    )
    scoped_pair = _read_jsonl(pairs_path)[0]
    _write_jsonl(pairs_path, [scoped_pair])
    expected_ids = {
        scoped_pair["left_canonicalization_evidence_id"],
        scoped_pair["right_canonicalization_evidence_id"],
    }

    result = run_tg_qa_legal_intent_candidate_extractor_batch(
        canonicalization_evidence_path=evidence_path,
        pair_benchmark_path=pairs_path,
        output_path=results_path,
        summary_output_path=summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-qwen",
        extractor_run_id="tg-legal-intent-extractor-run:fixture",
        chain=_FakeLegalIntentExtractorChain(),
    )

    records = _read_jsonl(results_path)
    by_id = {item["canonicalization_evidence_id"]: item for item in records}
    assert result["summary"]["completed_count"] == 2
    assert result["summary"]["scoped_evidence_count"] == 2
    assert set(by_id) == expected_ids
    assert all(item["task_id"] == item["canonicalization_evidence_id"] for item in records)
    assert all(item["law_area"] == "migration_status" for item in records)
    assert all(item["source_canonical_question"] != "hallucinated question" for item in records)
    assert all(item["runtime_metadata"]["prompt_version"] for item in records)
    imported = import_tg_qa_legal_intent_candidates(
        canonicalization_evidence_path=evidence_path,
        candidates_path=results_path,
        output_path=imported_path,
        summary_output_path=imported_summary_path,
    )
    assert imported["summary"]["completed_count"] == 2
    assert imported["summary"]["failed_count"] == 0


def test_legal_intent_pair_judge_runner_streams_review_evidence(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    pairs_summary_path = tmp_path / "pairs_summary.json"
    results_path = tmp_path / "pair_judge_results.jsonl"
    summary_path = tmp_path / "pair_judge_summary.json"
    evidence = [
        _evidence("e1", "tg-qa-candidate:1", "Нужно ли менять адрес на ВНЖ после переезда?"),
        _evidence("e2", "tg-qa-candidate:2", "Как обновить адрес на пластиковой карте ВНЖ?"),
    ]
    _write_jsonl(evidence_path, evidence)
    build_tg_qa_legal_intent_pair_benchmark(
        canonicalization_evidence_path=evidence_path,
        output_path=pairs_path,
        summary_output_path=pairs_summary_path,
    )

    result = run_tg_qa_legal_intent_pair_judge_batch(
        pair_benchmark_path=pairs_path,
        output_path=results_path,
        summary_output_path=summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-qwen",
        judge_run_id="tg-legal-intent-pair-judge-run:fixture",
        chain=_FakeLegalIntentPairJudgeChain(),
    )

    record = _read_jsonl(results_path)[0]
    assert result["summary"]["completed_count"] == 1
    assert record["task_id"] == record["pair_id"]
    assert record["decision_source"] == "tg-legal-intent-pair-judge-run:fixture"
    assert record["pair_class"] == "same_legal_intent"
    assert record["runtime_metadata"]["model_id"] == "fixture-qwen"


def test_legal_intent_pair_review_html_has_priority_filters(tmp_path: Path) -> None:
    pairs_path = tmp_path / "pairs.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    labels_path = tmp_path / "labels.jsonl"
    html_path = tmp_path / "review.html"
    summary_path = tmp_path / "review_summary.json"
    _write_jsonl(
        pairs_path,
        [
            {
                "pair_id": "pair:hard",
                "pair_source_reasons": ["high_canonical_question_similarity"],
                "similarity_evidence": {"canonical_question_score": 0.91},
                "left": {"candidate_id": "left:1", "canonical_question": "A"},
                "right": {"candidate_id": "right:1", "canonical_question": "B"},
            },
            {
                "pair_id": "pair:random",
                "pair_source_reasons": ["random_negative"],
                "similarity_evidence": {"canonical_question_score": 0.12},
                "left": {"candidate_id": "left:2", "canonical_question": "C"},
                "right": {"candidate_id": "right:2", "canonical_question": "D"},
            },
        ],
    )
    _write_jsonl(
        decisions_path,
        [
            {
                "pair_id": "pair:hard",
                "decision_source": "similarity_fixture",
                "pair_class": "same_legal_intent",
                "answer_equivalence": "safe_to_share_answer",
                "canonical_question_equivalence": "safe_to_share_question",
                "allowed_downstream_actions": ["allow_reference_answer_sharing"],
                "short_reason": "Fixture.",
            }
        ],
    )
    _write_jsonl(
        labels_path,
        [
            {
                "pair_id": "pair:hard",
                "status": "completed",
                "pair_class": "same_topic_different_issue",
                "answer_equivalence": "not_safe_to_share_answer",
                "canonical_question_equivalence": "not_safe_to_share_question",
                "allowed_downstream_actions": [],
                "decision_reason": "Already reviewed fixture.",
                "reviewed_at": "2026-06-10T00:00:00Z",
            }
        ],
    )

    result = export_tg_qa_legal_intent_pair_review_html(
        pair_benchmark_path=pairs_path,
        pair_decisions_path=decisions_path,
        output_path=html_path,
        summary_output_path=summary_path,
    )

    html = html_path.read_text(encoding="utf-8")
    assert result["summary"]["card_count"] == 2
    assert '<option value="source-hard">source hard pairs</option>' in html
    assert '<option value="not-different">not different</option>' in html
    assert '<option value="random-control">random control</option>' in html
    assert "v.includes('negative')" not in html
    assert "v !== 'random_negative'" in html
    assert "applyPairClassDefaults" in html
    assert "answerEq').value = 'not_safe_to_share_answer'" in html
    assert "questionEq').value = 'not_safe_to_share_question'" in html

    unreviewed_result = export_tg_qa_legal_intent_pair_review_html(
        pair_benchmark_path=pairs_path,
        pair_decisions_path=decisions_path,
        review_labels_path=labels_path,
        review_filter="unreviewed",
        output_path=html_path,
        summary_output_path=summary_path,
    )
    unreviewed_html = html_path.read_text(encoding="utf-8")
    assert unreviewed_result["summary"]["card_count"] == 1
    assert unreviewed_result["summary"]["available_reviewed_label_count"] == 1
    assert unreviewed_result["summary"]["excluded_reviewed_label_count"] == 1
    assert "pair:hard" not in unreviewed_html
    assert "pair:random" in unreviewed_html


def test_legal_intent_review_labels_and_evaluation_report_flag_hard_negatives(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    pairs_summary_path = tmp_path / "pairs_summary.json"
    labels_input_path = tmp_path / "labels_input.jsonl"
    labels_path = tmp_path / "labels.jsonl"
    labels_summary_path = tmp_path / "labels_summary.json"
    decisions_input_path = tmp_path / "decisions_input.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    decisions_summary_path = tmp_path / "decisions_summary.json"
    report_path = tmp_path / "report.jsonl"
    report_summary_path = tmp_path / "report_summary.json"
    similarity_pairs_path = tmp_path / "similarity_pairs.jsonl"
    evidence = [
        _evidence("e1", "tg-qa-candidate:1", "Можно ли подать заявление на ВНЖ?"),
        _evidence("e2", "tg-qa-candidate:2", "Можно ли подать заявление на ВНЖ без регистрации?", slug="residence_permit_application_without_registration"),
    ]
    _write_jsonl(evidence_path, evidence)
    _write_jsonl(
        similarity_pairs_path,
        [
            {
                "left_canonicalization_evidence_id": "e1",
                "right_canonicalization_evidence_id": "e2",
                "canonical_question_score": 0.92,
                "legal_issue_frame_score": 0.86,
            }
        ],
    )
    build_tg_qa_legal_intent_pair_benchmark(
        canonicalization_evidence_path=evidence_path,
        similarity_pairs_path=similarity_pairs_path,
        output_path=pairs_path,
        summary_output_path=pairs_summary_path,
    )
    pair_id = _read_jsonl(pairs_path)[0]["pair_id"]
    _write_jsonl(
        labels_input_path,
        [
            {
                "pair_id": pair_id,
                "pair_class": "same_topic_different_issue",
                "answer_equivalence": "not_safe_to_share_answer",
                "canonical_question_equivalence": "not_safe_to_share_question",
                "allowed_downstream_actions": ["preserve_hard_negative"],
                "decision_reason": "Registration condition changes the legal issue.",
            }
        ],
    )
    import_tg_qa_legal_intent_pair_review_labels(
        pair_benchmark_path=pairs_path,
        labels_path=labels_input_path,
        output_path=labels_path,
        summary_output_path=labels_summary_path,
    )
    _write_jsonl(
        decisions_input_path,
        [
            {
                "pair_id": pair_id,
                "decision_source": "fixture_judge",
                "pair_class": "same_legal_intent",
                "answer_equivalence": "safe_to_share_answer",
                "canonical_question_equivalence": "safe_to_share_question",
                "allowed_downstream_actions": ["allow_reference_answer_sharing"],
                "short_reason": "Incorrectly treats the registration condition as context only.",
                "confidence": "high",
                "risk": "medium",
            }
        ],
    )
    import_tg_qa_legal_intent_pair_decisions(
        pair_benchmark_path=pairs_path,
        decisions_path=decisions_input_path,
        output_path=decisions_path,
        summary_output_path=decisions_summary_path,
    )

    report = build_tg_qa_legal_intent_equivalence_report(
        pair_benchmark_path=pairs_path,
        pair_decisions_path=decisions_path,
        review_labels_path=labels_path,
        output_path=report_path,
        summary_output_path=report_summary_path,
    )

    assert report["summary"]["hard_negative_count"] == 1
    assert report["summary"]["false_duplicate_risk_count"] == 1
    assert report["summary"]["available_reviewed_label_count"] == 1
    assert report["summary"]["reviewed_label_count"] == 1
    assert report["summary"]["counts_by_question_equivalence_match_status"] == {"mismatch": 1}
    assert report["summary"]["counts_by_answer_equivalence_match_status"] == {"mismatch": 1}
    assert report["summary"]["counts_by_question_reuse_safety_match_status"] == {"mismatch": 1}
    assert report["summary"]["counts_by_answer_reuse_safety_match_status"] == {"mismatch": 1}
    assert report["summary"]["method_suitability"] == "insufficient_reviewed_labels"
    assert "reviewed_pair_label_count_below_100" in report["summary"]["insufficient_label_warnings"]


def test_canonical_coverage_statuses_do_not_count_uncertain_as_uncovered(tmp_path: Path) -> None:
    clusters_path = tmp_path / "clusters.jsonl"
    cases_path = tmp_path / "cases.jsonl"
    question_bank_path = tmp_path / "question_bank.jsonl"
    report_path = tmp_path / "coverage.jsonl"
    summary_path = tmp_path / "coverage_summary.json"
    _write_jsonl(
        clusters_path,
        [
            _cluster("covered", "residence_document_address_update_after_moving"),
            _cluster("partial", "work_authorization_contract_change"),
            _cluster("uncovered", "tax_self_employment_income_reporting"),
            _cluster(
                "uncertain",
                "family_reunification_income_evidence",
                confidence="low",
                flags=["low_confidence_present"],
            ),
        ],
    )
    _write_jsonl(cases_path, [{"case_id": "case:covered", "legal_issue_frame_slug": "residence_document_address_update_after_moving"}])
    _write_jsonl(
        question_bank_path,
        [
            {
                "question_bank_entry_id": "qb:partial",
                "legal_issue_frame_slug": "work_authorization_contract_change",
            }
        ],
    )

    result = build_tg_qa_canonical_coverage_report(
        issue_clusters_path=clusters_path,
        reviewed_final_cases_path=cases_path,
        question_bank_path=question_bank_path,
        output_path=report_path,
        summary_output_path=summary_path,
    )

    counts = result["summary"]["counts_by_coverage_status"]
    assert counts == {"covered": 1, "partial": 1, "uncertain": 1, "uncovered": 1}
    assert result["summary"]["uncertain_count"] == 1
    assert result["summary"]["top_uncovered_issue_clusters"][0]["legal_issue_frame_slug"] == (
        "tax_self_employment_income_reporting"
    )


def test_review_promotion_gates_final_cases_and_redacts_manual_answers(tmp_path: Path) -> None:
    clusters_path = tmp_path / "clusters.jsonl"
    decision_input_path = tmp_path / "decision_input.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    decisions_summary_path = tmp_path / "decisions_summary.json"
    question_bank_path = tmp_path / "question_bank.jsonl"
    question_bank_summary_path = tmp_path / "question_bank_summary.json"
    question_bank_manifest_path = tmp_path / "question_bank_manifest.json"
    candidates_path = tmp_path / "final_candidates.jsonl"
    candidates_summary_path = tmp_path / "final_candidates_summary.json"
    candidates_manifest_path = tmp_path / "final_candidates_manifest.json"
    cases_path = tmp_path / "reviewed_cases.jsonl"
    dataset_manifest_path = tmp_path / "dataset_manifest.json"
    dataset_quality_path = tmp_path / "dataset_quality.json"
    clusters = [
        _cluster("qb", "residence_document_address_update_after_moving"),
        _cluster("telegram", "work_authorization_contract_change"),
        _cluster("llm", "tax_self_employment_income_reporting"),
        _cluster("blocked", "family_reunification_income_evidence"),
        _cluster("manual", "asylum_deadline_proof"),
    ]
    _write_jsonl(clusters_path, clusters)
    _write_jsonl(
        decision_input_path,
        [
            _decision(clusters[0], "approve_question_bank", "none"),
            _decision(
                clusters[1],
                "approve_final_evaluation",
                "keep_selected_telegram_answer",
                selected_answer="Принятый Telegram-ответ после ревью.",
            ),
            _decision(
                clusters[1],
                "approve_final_evaluation",
                "keep_selected_telegram_answer",
                selected_answer="Дубликат должен быть отклонен.",
            ),
            _decision(
                clusters[2],
                "approve_final_evaluation",
                "replace_manual",
                source="llm_canonicalization_only",
                manual_answer="LLM-only text.",
            ),
            _decision(clusters[3], "approve_final_evaluation", "needs_manual_answer"),
            _decision(
                clusters[4],
                "approve_final_evaluation",
                "replace_manual",
                manual_answer="Ручной ответ от reviewer@example.com после проверки.",
            ),
        ],
    )

    import_result = import_tg_qa_cluster_review_decisions(
        issue_clusters_path=clusters_path,
        decisions_path=decision_input_path,
        output_path=decisions_path,
        summary_output_path=decisions_summary_path,
    )

    assert import_result["summary"]["failed_count"] == 1
    assert "reviewer@example.com" not in decisions_path.read_text(encoding="utf-8")

    bank_result = build_tg_qa_question_bank(
        issue_clusters_path=clusters_path,
        review_decisions_path=decisions_path,
        output_path=question_bank_path,
        summary_output_path=question_bank_summary_path,
        manifest_output_path=question_bank_manifest_path,
    )

    assert bank_result["summary"]["completed_entry_count"] == 5
    assert bank_result["summary"]["missing_reference_answer_count"] == 2

    final_result = build_tg_qa_issue_final_case_candidates(
        question_bank_path=question_bank_path,
        review_decisions_path=decisions_path,
        output_path=candidates_path,
        summary_output_path=candidates_summary_path,
        manifest_output_path=candidates_manifest_path,
    )

    assert final_result["summary"]["eligible_count"] == 2
    assert final_result["summary"]["blocked_missing_reference_answer_count"] == 1
    assert final_result["summary"]["llm_only_rejection_count"] == 1
    assert final_result["summary"]["accepted_telegram_reference_answer_count"] == 1
    assert final_result["summary"]["manual_reference_answer_count"] == 1

    dataset_result = build_tg_qa_reviewed_evaluation_dataset(
        final_case_candidates_path=candidates_path,
        output_path=cases_path,
        manifest_output_path=dataset_manifest_path,
        quality_output_path=dataset_quality_path,
    )

    cases = _read_jsonl(cases_path)
    assert dataset_result["manifest"]["case_count"] == 2
    assert {case["reference_answer_source"] for case in cases} == {
        "accepted_telegram_answer",
        "manual_review_override",
    }
    assert {case["temporal_relevance_state"] for case in cases} == {"current_reusable"}
    assert all(case["source_question_dates"] == ["2024-01-01T00:00:00Z"] for case in cases)
    assert _read_json(dataset_quality_path)["llm_only_exclusion_count"] == 1
    assert "reviewer@example.com" not in cases_path.read_text(encoding="utf-8")
    assert verify_tg_question_canonicalization_boundaries()["status"] == "passed"


def test_temporal_currentness_fixture_covers_all_review_states() -> None:
    fixture_path = (
        Path("specs")
        / "007-legal-question-canonicalization"
        / "temporal-currentness-reference-cases.jsonl"
    )
    cases = _read_jsonl(fixture_path)
    states = {case["expected_temporal_relevance_state"] for case in cases}

    assert len(cases) == 5
    assert len({case["benchmark_case_id"] for case in cases}) == len(cases)
    assert states == {
        "current_reusable",
        "historical_but_generalizable",
        "transition_bound",
        "superseded_or_expired",
        "unresolved_currentness",
    }
    assert all(case["evaluation_date"] and case["legal_corpus_as_of_date"] for case in cases)
    assert all(case["trust_boundary"] == "temporal_fixture_not_legal_answer_support" for case in cases)


def test_temporal_currentness_blocks_current_default_promotion_and_retains_history(tmp_path: Path) -> None:
    clusters_path = tmp_path / "clusters.jsonl"
    queue_path = tmp_path / "temporal_queue.jsonl"
    queue_summary_path = tmp_path / "temporal_queue_summary.json"
    decisions_input_path = tmp_path / "decisions_input.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    decisions_summary_path = tmp_path / "decisions_summary.json"
    question_bank_path = tmp_path / "question_bank.jsonl"
    question_bank_summary_path = tmp_path / "question_bank_summary.json"
    candidates_path = tmp_path / "final_candidates.jsonl"
    candidates_summary_path = tmp_path / "final_candidates_summary.json"
    temporal_blocked_path = tmp_path / "temporal_blocked.jsonl"

    current = _cluster("current", "stable_registration_address_update")
    expired = _cluster("expired", "expired_transition_document_extension_deadline")
    _write_jsonl(clusters_path, [current, expired])

    queue = build_tg_qa_temporal_currentness_review_queue(
        issue_clusters_path=clusters_path,
        output_path=queue_path,
        summary_output_path=queue_summary_path,
        evaluation_date="2026-06-18",
        legal_corpus_as_of_date="2026-06-18",
    )

    assert queue["summary"]["queue_record_count"] == 2
    assert queue["summary"]["counts_by_suggested_temporal_relevance_state"] == {
        "unresolved_currentness": 2
    }

    _write_jsonl(
        decisions_input_path,
        [
            _decision(
                current,
                "approve_final_evaluation",
                "replace_manual",
                manual_answer="Stable reviewed answer.",
                temporal_state="historical_but_generalizable",
            ),
            _decision(
                expired,
                "approve_final_evaluation",
                "replace_manual",
                manual_answer="Expired reviewed answer retained for history.",
                temporal_state="superseded_or_expired",
            ),
        ],
    )
    import_tg_qa_cluster_review_decisions(
        issue_clusters_path=clusters_path,
        decisions_path=decisions_input_path,
        output_path=decisions_path,
        summary_output_path=decisions_summary_path,
    )
    bank = build_tg_qa_question_bank(
        issue_clusters_path=clusters_path,
        review_decisions_path=decisions_path,
        output_path=question_bank_path,
        summary_output_path=question_bank_summary_path,
    )
    assert bank["summary"]["counts_by_temporal_relevance_state"] == {
        "historical_but_generalizable": 1,
        "superseded_or_expired": 1,
    }
    assert bank["summary"]["current_default_eligible_count"] == 1
    assert bank["summary"]["current_default_blocked_temporal_count"] == 1

    final = build_tg_qa_issue_final_case_candidates(
        question_bank_path=question_bank_path,
        review_decisions_path=decisions_path,
        output_path=candidates_path,
        summary_output_path=candidates_summary_path,
        temporal_blocked_output_path=temporal_blocked_path,
    )

    assert final["summary"]["eligible_count"] == 1
    assert final["summary"]["blocked_temporal_currentness_count"] == 1
    blocked = _read_jsonl(temporal_blocked_path)
    assert len(blocked) == 1
    assert blocked[0]["promotion_status"] == "blocked_temporal_currentness"
    assert blocked[0]["temporal_relevance_state"] == "superseded_or_expired"
    assert "temporal_currentness:superseded_or_expired" in blocked[0]["promotion_reasons"]


def _candidate(candidate_id: str, question: str, message_id: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "question_text_redacted": question,
        "topic_labels": ["migration_status"],
        "law_code_candidates": ["AufenthG"],
        "question_date": "2026-01-01T00:00:00",
        "answer_candidate_status": "strong",
        "quality_flags": [],
        "source_message_id": message_id,
    }


def _canonical_result(
    batch_item: dict,
    *,
    confidence: str = "high",
    include_operator_identity: bool = True,
) -> dict:
    record = {
        "task_id": batch_item["task_id"],
        "task_scope": "question_candidate",
        "candidate_id": batch_item["candidate_id"],
        "canonicalization_run_id": "tg-question-canonicalization-run:test",
        "canonicalization_contract_version": CANONICALIZATION_CONTRACT_VERSION,
        "prompt_version": canonicalization.CANONICALIZATION_PROMPT_VERSION,
        "runtime_contour": "fixture",
        "backend": "deterministic_fixture",
        "model_id": "",
        "status": "completed",
        "failure_reason": "",
        "canonical_question": batch_item["input"]["question_text_redacted"],
        "canonical_question_language": "ru",
        "legal_issue_frame": "Residence document address update after moving",
        "legal_issue_frame_slug": "residence_document_address_update_after_moving",
        "law_area": "migration_status",
        "facts": ["moved residence"],
        "desired_outcome": "update residence document address",
        "authority_context": ["Buergeramt", "Auslaenderbehoerde"],
        "hidden_issues": ["continued lawful stay evidence"],
        "is_legal_answer_required": True,
        "is_standalone_question": True,
        "exclusion_reason": "none",
        "confidence": confidence,
        "quality_flags": [],
    }
    if include_operator_identity:
        runtime_profile = {
            "stage": "canonicalization",
            "provider": "fixture",
            "runtime_contour": "fixture",
            "backend": "deterministic_fixture",
            "model_id": "",
        }
        record.update(
            {
                "canonicalization_identity_policy_version": canonicalization.CANONICALIZATION_IDENTITY_POLICY_VERSION,
                "canonicalization_batch_id": batch_item["canonicalization_batch_id"],
                "canonicalization_batch_hash": batch_item["canonicalization_batch_hash"],
                "task_input_hash": batch_item["task_input_hash"],
                "prompt_profile_hash": batch_item["prompt_profile_hash"],
                "operator_stage": "canonicalization",
                "runtime_profile": runtime_profile,
                "runtime_profile_hash": canonicalization._stable_json_hash(runtime_profile),
            }
        )
        if isinstance(batch_item.get("canonicalization_source_identity"), dict):
            record["canonicalization_source_identity"] = dict(
                batch_item["canonicalization_source_identity"]
            )
        record["canonicalization_evidence_hash"] = canonicalization._canonicalization_evidence_hash(record)
    return record


class _FakeCanonicalizationChain:
    def __init__(self, batch_item: dict) -> None:
        self.batch_item = batch_item

    def invoke(self, payload: dict) -> CanonicalizationResultPayload:
        assert "source_message_ids" not in payload["task_payload"]
        return CanonicalizationResultPayload.model_validate(
            _canonical_result(self.batch_item, include_operator_identity=False)
        )


class _FakeVerifierChain:
    def invoke(self, payload: dict) -> VerifierVerdictPayload:
        assert "source_message_ids" not in payload["verifier_payload"]
        return VerifierVerdictPayload(
            verdict="pass",
            confidence=94,
            risk="low",
            bad_fields=[],
            short_reason="Fixture canonicalization is internally consistent.",
            suggested_action="accept",
        )


class _FakeAtomicVerifierChain:
    def __init__(self) -> None:
        self.invocation_count = 0

    def invoke(self, payload: dict) -> canonicalization.AtomicVerificationPayload:
        self.invocation_count += 1
        task_payload = json.loads(payload["atomic_verifier_payload"])
        source = task_payload["source_question_text_redacted"]
        claim_verdicts = []
        route = "pass"
        for claim in task_payload["claim_ledger"]["claims"]:
            if self.invocation_count == 1 and claim["field_name"] == "hidden_issues":
                route = "revise"
                claim_verdicts.append(
                    canonicalization.AtomicClaimVerdictPayload(
                        claim_id=claim["claim_id"],
                        support="unsupported",
                        relation_kind="eligibility_condition",
                        materiality="high",
                        source_spans=[],
                        correction="Keep the child-benefit issue broad.",
                        short_reason="The source does not make Jobcenter registration an eligibility condition.",
                    )
                )
                continue
            claim_verdicts.append(
                canonicalization.AtomicClaimVerdictPayload(
                    claim_id=claim["claim_id"],
                    support="explicit",
                    relation_kind=(
                        claim["claim_type"]
                        if claim["claim_type"] in canonicalization.ATOMIC_CLAIM_RELATION_KINDS
                        else "other"
                    ),
                    materiality=claim["materiality"],
                    source_spans=[
                        canonicalization.AtomicSourceSpanPayload(
                            start=0,
                            end=len(source),
                            quote=source,
                        )
                    ],
                )
            )
        return canonicalization.AtomicVerificationPayload(
            route=route,
            claim_verdicts=claim_verdicts,
            short_reason="Fixture atomic verification.",
        )


class _EchoAtomicCriticChain:
    def invoke(self, payload: dict) -> canonicalization.AtomicVerificationPayload:
        task_payload = json.loads(payload["atomic_critic_payload"])
        verdicts = [
            canonicalization.AtomicClaimVerdictPayload.model_validate(item)
            for item in task_payload["prior_verdicts"]
        ]
        supports = {verdict.support for verdict in verdicts}
        route = "hold" if "unresolved" in supports else ("revise" if "unsupported" in supports else "pass")
        return canonicalization.AtomicVerificationPayload(
            route=route,
            claim_verdicts=verdicts,
            short_reason="Fixture critic echoes selected structured verdicts.",
        )


class _InterruptingFinalAtomicCriticChain(_EchoAtomicCriticChain):
    def __init__(self) -> None:
        self.invocation_count = 0

    def invoke(self, payload: dict) -> canonicalization.AtomicVerificationPayload:
        self.invocation_count += 1
        if self.invocation_count == 2:
            raise KeyboardInterrupt
        return super().invoke(payload)


class _UnexpectedAtomicChain:
    def invoke(self, payload: dict) -> None:
        raise AssertionError(f"unexpected atomic invocation: {sorted(payload)}")


class _FakeAtomicRepairChain:
    def invoke(self, payload: dict) -> canonicalization.AtomicRepairPayload:
        repair_payload = json.loads(payload["atomic_repair_payload"])
        candidate = dict(repair_payload["current_candidate"])
        candidate["hidden_issues"] = []
        return canonicalization.AtomicRepairPayload(
            repaired_claim_ids=[item["claim_id"] for item in repair_payload["repairs"]],
            corrected_output=CanonicalizationResultPayload.model_validate(candidate),
        )


class _ReplacingAtomicRepairChain:
    def invoke(self, payload: dict) -> canonicalization.AtomicRepairPayload:
        repair_payload = json.loads(payload["atomic_repair_payload"])
        candidate = dict(repair_payload["current_candidate"])
        candidate["hidden_issues"] = ["Право на выплаты на ребёнка"]
        return canonicalization.AtomicRepairPayload(
            repaired_claim_ids=[item["claim_id"] for item in repair_payload["repairs"]],
            corrected_output=CanonicalizationResultPayload.model_validate(candidate),
        )


class _AlwaysInvalidAtomicVerifierChain:
    def invoke(self, payload: dict) -> dict:
        assert "atomic_verifier_payload" in payload
        return {"claim_verdicts": "not-a-list"}


class _InterruptingFinalAtomicVerifierChain(_FakeAtomicVerifierChain):
    def invoke(self, payload: dict) -> canonicalization.AtomicVerificationPayload:
        if self.invocation_count >= 1:
            self.invocation_count += 1
            raise KeyboardInterrupt
        return super().invoke(payload)


class _PassAtomicVerifierChain:
    def __init__(self) -> None:
        self.invocation_count = 0

    def invoke(self, payload: dict) -> canonicalization.AtomicVerificationPayload:
        self.invocation_count += 1
        task_payload = json.loads(payload["atomic_verifier_payload"])
        source = task_payload["source_question_text_redacted"]
        claim_verdicts = [
            canonicalization.AtomicClaimVerdictPayload(
                claim_id=claim["claim_id"],
                support="explicit",
                relation_kind=(
                    claim["claim_type"]
                    if claim["claim_type"] in canonicalization.ATOMIC_CLAIM_RELATION_KINDS
                    else "other"
                ),
                materiality=claim["materiality"],
                source_spans=[
                    canonicalization.AtomicSourceSpanPayload(
                        start=0,
                        end=len(source),
                        quote=source,
                    )
                ],
            )
            for claim in task_payload["claim_ledger"]["claims"]
        ]
        return canonicalization.AtomicVerificationPayload(
            route="pass",
            claim_verdicts=claim_verdicts,
            short_reason="Fixture pass after stage resume.",
        )


class _FakeLegalIntentPairJudgeChain:
    def invoke(self, payload: dict) -> canonicalization.LegalIntentPairDecisionPayload:
        pair_payload = json.loads(payload["pair_payload"])
        assert "source_message_ids" not in payload["pair_payload"]
        return canonicalization.LegalIntentPairDecisionPayload(
            pair_id=pair_payload["pair_id"],
            pair_class="same_legal_intent",
            answer_equivalence="safe_to_share_answer",
            canonical_question_equivalence="safe_to_share_question",
            allowed_downstream_actions=["allow_reference_answer_sharing"],
            material_differences=[],
            shared_material_facts=["fixture"],
            short_reason="Fixture pair judge accepts same legal intent.",
            confidence="high",
            risk="low",
        )


class _FakeLegalIntentExtractorChain:
    def invoke(self, payload: dict) -> canonicalization.LegalIntentCandidatePayload:
        candidate_payload = json.loads(payload["candidate_payload"])
        assert "source_message_ids" not in payload["candidate_payload"]
        return canonicalization.LegalIntentCandidatePayload(
            candidate_id="hallucinated-candidate",
            canonicalization_evidence_id="hallucinated-evidence",
            source_canonical_question="hallucinated question",
            law_area="hallucinated-law-area",
            legal_domain="residence_status",
            actor="foreign_national",
            subject="self",
            desired_action="apply_for_residence_permit",
            legal_object="residence_permit",
            authority_context=candidate_payload["authority_context"],
            evidence_refs=[
                {
                    "field": "desired_action",
                    "source_field": "canonical_question",
                    "support_text": "подать заявление на ВНЖ",
                }
            ],
            confidence="medium",
        )


class _StructuredOutputOnlyChatModel:
    def with_structured_output(self, schema: object, method: str = "", include_raw: bool = False) -> object:
        self.schema = schema
        self.method = method
        self.include_raw = include_raw
        return lambda payload: payload


class _FakeDeepSeekChain:
    def invoke(self, payload: dict) -> DeepSeekAdjudicationPayload:
        assert "source_message_ids" not in payload["adjudication_payload"]
        return DeepSeekAdjudicationPayload(
            verdict="pass",
            confidence=87,
            risk="low",
            bad_fields=[],
            short_reason="Escalated record is acceptable as-is.",
            final_recommendation="accept",
            selected_candidate_key="primary",
        )


class OutputParserException(Exception):
    def __init__(self) -> None:
        super().__init__(
            "Invalid json output from [url]. Authorization: Bearer sk-testsecret1234567890"
        )
        self.observation = "The model returned text outside JSON."
        self.llm_output = "Sure, here is the answer: {'not': 'json'}"


class _FailingCanonicalizationChain:
    def __init__(self) -> None:
        self.attempt_count = 0

    def invoke(self, payload: dict) -> CanonicalizationResultPayload:
        self.attempt_count += 1
        assert "source_message_ids" not in payload["task_payload"]
        raise OutputParserException()


class RateLimitError(Exception):
    pass


class InternalServerError(Exception):
    pass


class _RetryingCanonicalizationChain:
    def __init__(self, batch_item: dict, *, fail_attempts: int) -> None:
        self.batch_item = batch_item
        self.fail_attempts = fail_attempts
        self.attempt_count = 0

    def invoke(self, payload: dict) -> CanonicalizationResultPayload:
        self.attempt_count += 1
        assert "source_message_ids" not in payload["task_payload"]
        if self.attempt_count <= self.fail_attempts:
            raise RateLimitError("429 rate limit from upstream provider, try again later")
        return CanonicalizationResultPayload.model_validate(
            _canonical_result(self.batch_item, include_operator_identity=False)
        )


class _AlwaysFailingProviderCanonicalizationChain:
    def __init__(self) -> None:
        self.attempt_count = 0

    def invoke(self, payload: dict) -> CanonicalizationResultPayload:
        self.attempt_count += 1
        assert "source_message_ids" not in payload["task_payload"]
        raise InternalServerError("Error code: 530 - Cloudflare Tunnel error 1033")


class _CjkThenValidCanonicalizationChain:
    def __init__(self, batch_item: dict) -> None:
        self.batch_item = batch_item
        self.attempt_count = 0

    def invoke(self, payload: dict) -> CanonicalizationResultPayload:
        self.attempt_count += 1
        assert "source_message_ids" not in payload["task_payload"]
        result = _canonical_result(self.batch_item, include_operator_identity=False)
        if self.attempt_count == 1:
            result["canonical_question"] = "Можно ли 持有 сменить работодателя с Blue Card?"
        return CanonicalizationResultPayload.model_validate(result)


class _SelectiveCanonicalizationChain:
    def __init__(self, batch_items_by_task_id: dict[str, dict]) -> None:
        self.batch_items_by_task_id = batch_items_by_task_id
        self.invoked_task_ids: list[str] = []

    def invoke(self, payload: dict) -> CanonicalizationResultPayload:
        assert "source_message_ids" not in payload["task_payload"]
        task_payload = json.loads(payload["task_payload"])
        task_id = str(task_payload["task_id"])
        self.invoked_task_ids.append(task_id)
        return CanonicalizationResultPayload.model_validate(
            _canonical_result(self.batch_items_by_task_id[task_id], include_operator_identity=False)
        )


def _evidence(
    evidence_id: str,
    candidate_id: str,
    question: str,
    *,
    slug: str = "residence_document_address_update_after_moving",
    confidence: str = "high",
    exclusion_reason: str = "none",
    law_area: str = "migration_status",
) -> dict:
    return {
        "canonicalization_evidence_id": evidence_id,
        "task_id": f"task:{evidence_id}",
        "task_scope": "question_candidate",
        "candidate_id": candidate_id,
        "canonicalization_run_id": "run:test",
        "canonicalization_contract_version": CANONICALIZATION_CONTRACT_VERSION,
        "prompt_version": canonicalization.CANONICALIZATION_PROMPT_VERSION,
        "runtime_contour": "fixture",
        "backend": "deterministic_fixture",
        "model_id": "",
        "status": "completed",
        "failure_reason": "",
        "canonical_question": question,
        "canonical_question_language": "ru",
        "legal_issue_frame": slug.replace("_", " ").title(),
        "legal_issue_frame_slug": slug,
        "law_area": law_area,
        "facts": [],
        "desired_outcome": "",
        "authority_context": ["Buergeramt"],
        "hidden_issues": [],
        "is_legal_answer_required": exclusion_reason == "none",
        "is_standalone_question": exclusion_reason == "none",
        "exclusion_reason": exclusion_reason,
        "confidence": confidence,
        "quality_flags": [],
        "question_date": "2024-01-01T00:00:00Z",
        "source_question_text_redacted": question,
        "provenance": {"source_message_ids": [candidate_id]},
    }


def _cluster(
    suffix: str,
    slug: str,
    *,
    confidence: str = "high",
    flags: list[str] | None = None,
) -> dict:
    return {
        "legal_issue_cluster_id": f"cluster:{suffix}",
        "legal_issue_frame_slug": slug,
        "canonical_question_representative": f"Question for {slug}",
        "law_area": "migration_status",
        "authority_context": ["Buergeramt"],
        "candidate_ids": [f"candidate:{suffix}"],
        "canonicalization_evidence_ids": [f"evidence:{suffix}"],
        "source_question_dates": ["2024-01-01T00:00:00Z"],
        "representative_raw_questions": [f"Raw question {suffix}"],
        "cluster_size": 1,
        "cluster_confidence": confidence,
        "cluster_quality_flags": flags or [],
        "merge_policy_version": "tg_legal_issue_cluster_policy_v1",
        "review_route": "needs_cluster_review",
        "coverage_status": "unmeasured",
    }


def _decision(
    cluster: dict,
    decision: str,
    action: str,
    *,
    source: str = "",
    selected_answer: str = "",
    manual_answer: str = "",
    temporal_state: str = "current_reusable",
) -> dict:
    return {
        "legal_issue_cluster_id": cluster["legal_issue_cluster_id"],
        "decision": decision,
        "reference_answer_action": action,
        "reference_answer_source": source,
        "reviewed_canonical_question": cluster["canonical_question_representative"],
        "reviewed_legal_issue_frame_slug": cluster["legal_issue_frame_slug"],
        "selected_reference_answer_text_redacted": selected_answer,
        "manual_reference_answer_text_redacted": manual_answer,
        "temporal_relevance_state": temporal_state,
        "source_question_date": "2024-01-01T00:00:00Z",
        "legal_corpus_as_of_date": "2026-06-18",
        "temporal_review_date": "2026-06-18T00:00:00Z",
        "temporal_review_reason": "fixture temporal review",
        "reviewer_hash": "reviewer:test",
        "decision_reason": "fixture decision",
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
