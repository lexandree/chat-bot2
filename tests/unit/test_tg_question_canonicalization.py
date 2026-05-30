from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from evaluation.prompts import (
    CANONICALIZATION_ADJUDICATOR_PROMPT_PROFILE,
    CANONICALIZATION_VERIFIER_PROMPT_PROFILE,
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
    build_tg_qa_issue_final_case_candidates,
    build_tg_qa_legal_intent_equivalence_report,
    build_tg_qa_legal_intent_pair_benchmark,
    build_tg_qa_question_bank,
    build_tg_qa_reviewed_evaluation_dataset,
    build_langchain_deepseek_adjudication_chain,
    build_langchain_adjudication_chain,
    build_langchain_verifier_chain,
    canonicalization_prompt_profile,
    compact_canonicalization_llm_payload,
    cluster_tg_qa_legal_issues,
    emit_tg_qa_canonical_embedding_batch,
    emit_tg_qa_canonicalization_batch,
    export_tg_qa_canonicalization_review_cards,
    import_tg_qa_canonical_embedding_records,
    import_tg_qa_canonicalization_results,
    import_tg_qa_canonicalization_review_decisions,
    import_tg_qa_cluster_review_decisions,
    import_tg_qa_legal_intent_candidates,
    import_tg_qa_legal_intent_pair_decisions,
    import_tg_qa_legal_intent_pair_review_labels,
    run_tg_qa_canonicalization_adjudication_batch,
    run_tg_qa_canonicalization_deepseek_batch,
    run_tg_qa_canonicalization_llm_batch,
    run_tg_qa_canonicalization_verifier_batch,
    sample_tg_qa_canonicalization_batch,
    verify_tg_question_canonicalization_boundaries,
)
from evaluation import tg_question_canonicalization as canonicalization


def test_canonicalization_constants_slug_ids_and_privacy_guard_are_stable() -> None:
    assert CANONICALIZATION_CONTRACT_VERSION == "tg_question_canonicalization_v1"
    assert CANONICALIZATION_PROMPT_EXAMPLE_SET_ID == "tg_question_canonicalizer_examples_v4"
    assert len(CANONICALIZATION_PROMPT_EXAMPLES) == 13
    prompt_profile = canonicalization_prompt_profile()
    assert prompt_profile["prompt_example_set_id"] == CANONICALIZATION_PROMPT_EXAMPLE_SET_ID
    assert list(prompt_profile["expected_output_schema"])[:4] == [
        "legal_issue_frame",
        "legal_issue_frame_slug",
        "canonical_question",
        "canonical_question_language",
    ]
    assert list(prompt_profile["few_shot_examples"][0]["output"])[:4] == [
        "legal_issue_frame",
        "legal_issue_frame_slug",
        "canonical_question",
        "canonical_question_language",
    ]
    assert prompt_profile["few_shot_examples"][0]["output"]["exclusion_reason"] == "none"
    assert prompt_profile["few_shot_examples"][2]["output"]["exclusion_reason"] == "not_standalone_question"
    assert prompt_profile["few_shot_examples"][3]["output"]["exclusion_reason"] == "non_legal_question"
    assert prompt_profile["few_shot_examples"][4]["output"]["quality_flags"] == [
        "operational_logistics_only"
    ]
    assert prompt_profile["few_shot_examples"][5]["output"]["quality_flags"] == [
        "answer_or_explanation_without_question"
    ]
    assert prompt_profile["few_shot_examples"][6]["output"]["quality_flags"] == [
        "dialogue_context_missing",
        "clarifying_question_without_original_request",
    ]
    assert prompt_profile["few_shot_examples"][7]["output"]["exclusion_reason"] == "non_legal_question"
    assert prompt_profile["few_shot_examples"][7]["output"]["quality_flags"] == [
        "operational_logistics_only",
        "requires_live_operational_data",
    ]
    assert prompt_profile["few_shot_examples"][8]["output"]["quality_flags"] == [
        "third_party_refuses_legal_status_proof"
    ]
    assert prompt_profile["few_shot_examples"][9]["output"]["quality_flags"] == [
        "potentially_unlawful_arrangement",
        "nonexistent_entitlement",
    ]
    assert prompt_profile["few_shot_examples"][10]["output"]["quality_flags"] == [
        "nonexistent_entitlement"
    ]
    assert prompt_profile["few_shot_examples"][11]["output"]["law_area"] == "consumer_protection"
    assert "Do not answer the legal question" in prompt_profile["system_instruction"]
    assert "Return one valid json object only" in prompt_profile["system_instruction"]
    assert "Always return exactly one structured object" in prompt_profile["system_instruction"]
    assert "exclusion_reason=non_legal_question" in prompt_profile["system_instruction"]
    assert "requires_live_operational_data" in prompt_profile["system_instruction"]
    assert "currently accepting refugees/new arrivals" in prompt_profile["system_instruction"]
    assert "Do not include such intake/capacity questions" in prompt_profile["system_instruction"]
    assert "appointment/application requirement for a legal status action" in prompt_profile["system_instruction"]
    assert "whether/where/how to apply for or renew a residence permit" in prompt_profile["system_instruction"]
    assert "appointment day confirmation or current slot availability" in prompt_profile["system_instruction"]
    assert "ordinary processing/production/response/wait time for a document" in prompt_profile["system_instruction"]
    assert "how long a card/document/application/letter/authority reply" in prompt_profile["system_instruction"]
    assert "IMPORTANT MIXED-QUERY BOUNDARY" in prompt_profile["system_instruction"]
    assert "canonicalize only the legal question" in prompt_profile["system_instruction"]
    assert "mixed_with_non_legal_query" in prompt_profile["system_instruction"]
    assert "cross-border money transfers" in prompt_profile["system_instruction"]
    assert "mandatory reporting or arrival timing" in prompt_profile["system_instruction"]
    assert "personal re-admission/placement after prior departure or closed case" in prompt_profile["system_instruction"]
    assert "Direct address to a named person" in prompt_profile["system_instruction"]
    assert "IMPORTANT PROBLEMATIC-PREMISE BOUNDARY" in prompt_profile["system_instruction"]
    assert "fictitious residence/registration" in prompt_profile["system_instruction"]
    assert "third parties refusing legal status proof" in prompt_profile["system_instruction"]
    assert "missing legal basis for stay/work" in prompt_profile["system_instruction"]
    assert "stay first, settle, and only later work" in prompt_profile["system_instruction"]
    assert "§24 automatic extensions" in prompt_profile["system_instruction"]
    assert "IMPORTANT DEFAULT CORPUS CONTEXT" in prompt_profile["system_instruction"]
    assert "Ukrainian refugees in Germany and German law" in prompt_profile["system_instruction"]
    assert "Israel is prior/current third-country context" in prompt_profile["system_instruction"]
    assert "IMPORTANT GENERALIZED CANONICAL QUESTION" in prompt_profile["system_instruction"]
    assert "not a detailed paraphrase of the source" in prompt_profile["system_instruction"]
    assert "IMPORTANT ISSUE-FRAME ALIGNMENT" in prompt_profile["system_instruction"]
    assert "planning anchor for the abstract legal issue" in prompt_profile["system_instruction"]
    assert "not as text to translate word-for-word" in prompt_profile["system_instruction"]
    assert "idiomatic Russian legal question" in prompt_profile["system_instruction"]
    assert "Keep secondary issues in facts or hidden_issues" in prompt_profile["system_instruction"]
    assert "family ties can justify choosing the registration/allocation location" in prompt_profile["system_instruction"]
    assert "If retry_context is present" in prompt_profile["system_instruction"]
    assert "do not infer a hypothetical legal question" in prompt_profile["system_instruction"]
    assert "do not assume the source is a question" in prompt_profile["system_instruction"]
    assert "IMPORTANT QUESTION-ANSWER BOUNDARY" in prompt_profile["system_instruction"]
    assert "IMPORTANT LEGAL-OPERATIONAL BOUNDARY" in prompt_profile["system_instruction"]
    assert "consumer service contract can be canceled" in prompt_profile["system_instruction"]
    assert "verdict exactly as one of: pass, fail, uncertain" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "suggested_action exactly as one of: accept, reject, retry_qwen, send_deepseek, human_review" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "valid json verdict object" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "confidence is a string enum" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "If exclusion_reason is not none, this is an excluded case" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "Do not infer a hypothetical legal question" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "IMPORTANT QUESTION-ANSWER BOUNDARY" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "IMPORTANT LEGAL-OPERATIONAL BOUNDARY" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "IMPORTANT DEFAULT CORPUS CONTEXT" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "Ukrainian refugees in Germany and German law" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "IMPORTANT GENERALIZED CANONICAL QUESTION" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "IMPORTANT ISSUE-FRAME ALIGNMENT" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "mechanically translated from the English issue frame" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "Secondary issues may belong in facts or hidden_issues" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "social benefit, payment, or other legal entitlement exists" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "nonexistent_entitlement" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "currently accepting refugees/new arrivals" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "appointment/application requirement for a legal status action" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "whether/where/how to apply for or renew a residence permit" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "ordinary processing/production/response/wait time for a document" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "IMPORTANT MIXED-QUERY BOUNDARY" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "IMPORTANT FIELD-SCOPE CHECK" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "inspect the candidate canonical_question text itself" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "Do not fail because mailbox" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "mandatory reporting or arrival timing" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    assert "Direct address to a named person" in CANONICALIZATION_VERIFIER_PROMPT_PROFILE["system_instruction"]
    verifier_user_lines = "\n".join(CANONICALIZATION_VERIFIER_PROMPT_PROFILE["user_prompt_lines"])
    assert "empty canonical fields may be valid" in verifier_user_lines
    assert "valid json object" in verifier_user_lines
    adjudicator_instruction = CANONICALIZATION_ADJUDICATOR_PROMPT_PROFILE["system_instruction"]
    assert "Routing semantics" in adjudicator_instruction
    assert "correctly excludes the source" in adjudicator_instruction
    assert "secondary fields" in adjudicator_instruction
    assert "whether/where/how to apply for or renew a residence permit" in adjudicator_instruction
    assert "ordinary processing/production/response/wait time for a document" in adjudicator_instruction
    assert "IMPORTANT DEFAULT CORPUS CONTEXT" in adjudicator_instruction
    assert "Ukrainian refugees in Germany and German law" in adjudicator_instruction
    assert "IMPORTANT GENERALIZED CANONICAL QUESTION" in adjudicator_instruction
    assert "IMPORTANT ISSUE-FRAME ALIGNMENT" in adjudicator_instruction
    assert "not text that canonical_question must translate word-for-word" in adjudicator_instruction
    assert "idiomatic question preserving the same abstract issue" in adjudicator_instruction
    assert "Secondary issues may belong in facts or hidden_issues" in adjudicator_instruction
    assert "IMPORTANT MIXED-QUERY BOUNDARY" in adjudicator_instruction
    assert "IMPORTANT FIELD-SCOPE CHECK" in adjudicator_instruction
    assert "Do not repeat a verifier's claim" in adjudicator_instruction
    assert "extracts only the legal question" in adjudicator_instruction
    assert "social benefit, payment, or other legal entitlement exists" in adjudicator_instruction
    assert "nonexistent_entitlement" in adjudicator_instruction
    assert "Do not return pass with reject, or fail with accept" in adjudicator_instruction
    assert "currently accepting refugees/new arrivals" in adjudicator_instruction
    assert "none" in EXCLUSION_REASONS
    assert CONFIDENCE_VALUES == ("low", "medium", "high")
    assert canonicalization._slugify("Residence Document Address Update") == "residence_document_address_update"
    assert canonicalization._slugify("Blaue Karte Übertrag") == "blaue_karte_uebertrag"
    assert canonicalization._stable_id("x", "a", {"b": 1}) == canonicalization._stable_id("x", "a", {"b": 1})

    with pytest.raises(ValueError, match="private or unsafe"):
        canonicalization._ensure_public_payload({"path": "data/tg/raw-result.json"})
    with pytest.raises(ValueError, match="private or unsafe"):
        canonicalization._ensure_public_payload({"endpoint": "http://example.test/v1"})


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

    result = CanonicalizationResultPayload.model_validate(_canonical_result(batch_item))
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


def test_live_runner_shapes_stream_results_with_fake_structured_chains(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    batch_path = tmp_path / "batch.jsonl"
    batch_summary_path = tmp_path / "batch_summary.json"
    qwen_results_path = tmp_path / "qwen_results.jsonl"
    qwen_summary_path = tmp_path / "qwen_summary.json"
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
    assert qwen_records[0]["task_id"] == batch_item["task_id"]
    assert qwen_records[0]["backend"] == "opencode"
    assert verifier_result["summary"]["completed_count"] == 1
    assert verifier_records[0]["verdict"] == "pass"
    assert verifier_records[0]["suggested_action"] == "accept"


def test_langchain_review_prompt_builders_accept_literal_json_few_shots() -> None:
    verifier_chain = build_langchain_verifier_chain(_StructuredOutputOnlyChatModel(), method="function_calling")
    adjudication_chain = build_langchain_adjudication_chain(
        _StructuredOutputOnlyChatModel(),
        method="json_mode",
    )

    assert verifier_chain is not None
    assert adjudication_chain is not None


def test_openai_verifier_chain_passes_extra_body(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeChatOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def with_structured_output(self, schema: object, method: str = "") -> object:
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


def test_anthropic_verifier_chain_normalizes_messages_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeChatAnthropic:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def with_structured_output(self, schema: object, method: str = "") -> object:
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
        extra_body=None,
    )

    assert chain is not None
    assert captured["base_url"] == "https://opencode.ai/zen/go"


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
    _write_jsonl(qwen_results_path, [_canonical_result(batch[0])])
    chain = _SelectiveCanonicalizationChain({batch[1]["task_id"]: batch[1]})

    result = run_tg_qa_canonicalization_llm_batch(
        batch_path=batch_path,
        output_path=qwen_results_path,
        summary_output_path=qwen_summary_path,
        endpoint_url="https://redacted.test/v1/chat/completions",
        model_id="fixture-qwen",
        canonicalization_run_id="tg-question-canonicalization-run:fixture",
        chain=chain,
    )

    records = _read_jsonl(qwen_results_path)
    assert result["summary"]["resume"] is True
    assert result["summary"]["resumed_existing_count"] == 1
    assert result["summary"]["max_items"] == 0
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
    assert batch[0]["expected_output_schema"]["canonical_question"] == "string"
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
    assert len(completed) == 2
    assert {item["canonical_question_language"] for item in completed} == {"ru"}
    assert {item["legal_issue_frame_slug"] for item in completed} == {
        "residence_document_address_update_after_moving"
    }
    assert import_result["manifest"]["duplicate_result_count"] == 1
    assert import_result["manifest"]["failed_count"] == 1
    assert any(item["status"] == "failed" and item["failure_reason"].startswith("invalid_json") for item in evidence)


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

    _write_jsonl(qwen_results_path, [_canonical_result(sample[0])])
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
    assert cards[0]["qwen"]["canonical_question"] == sample[0]["input"]["question_text_redacted"]
    assert cards[0]["verifier"]["verdict"] == "uncertain"
    assert "retry_context" in cards[0]
    assert "Export JSONL" in html
    assert "retry decision reason" in html
    assert "manual canonicalization JSON" in html
    assert "manual_canonicalization_text" in html
    assert 'a.download = "review_decisions.jsonl"' in html
    assert 'const storageKey = "tg007ReviewDecisions:review"' in html
    assert "source_message_ids" not in html
    assert "expected_output_schema" not in html


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
            },
            {
                "task_id": batch[3]["task_id"],
                "candidate_id": batch[3]["candidate_id"],
                "decision": "send_deepseek",
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
    assert ledger_by_task[batch[0]["task_id"]]["decision_source"] == "implicit_accept_qwen_included"
    assert ledger_by_task[batch[1]["task_id"]]["decision"] == "reject"
    assert ledger_by_task[batch[1]["task_id"]]["decision_source"] == "implicit_reject_qwen_exclusion"
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
    blocked_retry_result = build_tg_qa_canonicalization_retry_batch_from_adjudication(
        batch_path=batch_path,
        adjudication_batch_path=adjudication_batch_path,
        adjudication_results_paths=[
            f"judge1={adjudication_results_path}",
            f"judge2={adjudication_results_path_2}",
        ],
        output_path=blocked_retry_batch_path,
        summary_output_path=blocked_retry_summary_path,
    )
    assert blocked_retry_result["summary"]["emitted_task_count"] == 0
    assert blocked_retry_result["summary"]["skipped_reasons"][
        "human_review_before_retry:retry_consensus_but_reason_disagreement"
    ] == 1

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
        adjudication_results_paths=[f"manual={manual_retry_results_path}"],
        output_path=manual_retry_batch_path,
        summary_output_path=manual_retry_summary_path,
    )
    manual_retry_records = _read_jsonl(manual_retry_batch_path)
    assert manual_retry_result["summary"]["emitted_task_count"] == 1
    assert manual_retry_records[0]["retry_context"]["previous_candidate"]["candidate_key"] == "deepseek"
    assert manual_retry_records[0]["retry_context"]["retry_triage"]["reason_code"] == "manual_review_retry"


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
    assert "preserved_variant_candidate" in first["summary"]["counts_by_pair_source_reason"]


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
    assert _read_json(dataset_quality_path)["llm_only_exclusion_count"] == 1
    assert "reviewer@example.com" not in cases_path.read_text(encoding="utf-8")
    assert verify_tg_question_canonicalization_boundaries()["status"] == "passed"


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


def _canonical_result(batch_item: dict, *, confidence: str = "high") -> dict:
    return {
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


class _FakeCanonicalizationChain:
    def __init__(self, batch_item: dict) -> None:
        self.batch_item = batch_item

    def invoke(self, payload: dict) -> CanonicalizationResultPayload:
        assert "source_message_ids" not in payload["task_payload"]
        return CanonicalizationResultPayload.model_validate(_canonical_result(self.batch_item))


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


class _StructuredOutputOnlyChatModel:
    def with_structured_output(self, schema: object, method: str = "") -> object:
        self.schema = schema
        self.method = method
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
        return CanonicalizationResultPayload.model_validate(_canonical_result(self.batch_item))


class _CjkThenValidCanonicalizationChain:
    def __init__(self, batch_item: dict) -> None:
        self.batch_item = batch_item
        self.attempt_count = 0

    def invoke(self, payload: dict) -> CanonicalizationResultPayload:
        self.attempt_count += 1
        assert "source_message_ids" not in payload["task_payload"]
        result = _canonical_result(self.batch_item)
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
        return CanonicalizationResultPayload.model_validate(_canonical_result(self.batch_items_by_task_id[task_id]))


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
