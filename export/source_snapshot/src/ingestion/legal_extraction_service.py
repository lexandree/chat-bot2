"""LLM-backed proposition extraction over legal fragments."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4

from app.settings import AppSettings, load_settings
from graph.types import ExtractionRun
from ingestion.legal_proposition_extractor import build_proposition_prompt, parse_proposition_output
from ingestion.reindex_state import (
    LegalExtractionExecutionState,
    LegalExtractionItemState,
    LegalExtractionRunState,
)
from review.review_service import build_proposition_review_task


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _persist_graph_links(
    legal_repositories: dict[str, object],
    candidate: dict[str, object],
    supports: list[dict[str, object]],
) -> None:
    client = legal_repositories["proposition_candidate"].client
    client.execute(
        """
        MATCH (candidate:PropositionCandidate {proposition_candidate_id: $candidate_id})
        MATCH (run:ExtractionRun {run_id: $run_id})
        MERGE (candidate)-[:EXTRACTED_IN]->(run)
        """,
        candidate_id=candidate["proposition_candidate_id"],
        run_id=candidate["run_id"],
    )
    for support in supports:
        client.execute(
            """
            MATCH (candidate:PropositionCandidate {proposition_candidate_id: $candidate_id})
            MATCH (support:PropositionSupport {support_id: $support_id})
            MATCH (fragment:LegalFragment {fragment_id: $fragment_id})
            MATCH (section:LegalSection {section_id: $section_id})
            MERGE (candidate)-[:SUPPORTED_BY]->(support)
            MERGE (support)-[:USES_FRAGMENT]->(fragment)
            MERGE (support)-[:USES_SECTION]->(section)
            """,
            candidate_id=candidate["proposition_candidate_id"],
            support_id=support["support_id"],
            fragment_id=support["fragment_id"],
            section_id=support["section_id"],
        )


def plan_legal_extraction_run(
    fragment_count: int,
    *,
    runtime_contour: str | None = None,
    settings: AppSettings | None = None,
    max_items: int | None = None,
) -> dict[str, object]:
    active_settings = settings or load_settings()
    selected_contour = runtime_contour or active_settings.legal_runtime_contour
    if selected_contour == "managed_paid":
        backend_metadata = {
            "runtime_contour": selected_contour,
            "effective_llm_backend": active_settings.legal_managed_llm_backend,
            "effective_embedding_backend": active_settings.legal_managed_embedding_backend,
            "llm_model_id": active_settings.legal_managed_llm_backend,
            "embedding_model_id": active_settings.legal_managed_embedding_backend,
        }
        planned_limit = min(max_items or fragment_count, active_settings.legal_managed_smoke_limit)
    elif selected_contour == "operator_managed":
        backend_metadata = {
            "runtime_contour": selected_contour,
            "effective_llm_backend": active_settings.legal_operator_llm_backend,
            "effective_embedding_backend": active_settings.legal_operator_embedding_backend,
            "llm_model_id": active_settings.legal_operator_llm_backend,
            "embedding_model_id": active_settings.legal_operator_embedding_backend,
        }
        planned_limit = min(max_items or fragment_count, fragment_count)
    else:
        raise ValueError(f"Unsupported legal runtime contour: {selected_contour}")
    return {
        **backend_metadata,
        "planned_limit": planned_limit,
        "prompt_or_policy_version": active_settings.legal_extraction_policy_version,
    }


def run_legal_extraction(
    fragments: list[dict[str, object]],
    *,
    sections_by_id: dict[str, dict[str, object]],
    extractor,
    run_name: str,
    run_mode: str = "semantic_enriched",
    runtime_contour: str | None = None,
    settings: AppSettings | None = None,
    prompt_or_policy_version: str | None = None,
    validation_set_ref: str = "",
    source_scope_ref: str = "",
    claim_repository=None,
    review_task_repository=None,
    legal_repositories: dict[str, object] | None = None,
    max_items: int | None = None,
    resume_state: LegalExtractionExecutionState | None = None,
    state_store=None,
) -> dict[str, object]:
    active_settings = settings or load_settings()
    plan = plan_legal_extraction_run(
        len(fragments),
        runtime_contour=runtime_contour,
        settings=active_settings,
        max_items=max_items,
    )
    selected_contour = str(plan["runtime_contour"])
    backend_metadata = {
        key: value
        for key, value in plan.items()
        if key in {"effective_llm_backend", "effective_embedding_backend", "llm_model_id", "embedding_model_id"}
    }
    run_id = f"{run_name}:{selected_contour}"
    started_at = resume_state.run.created_at if resume_state is not None else _iso_now()
    run = ExtractionRun(
        run_id=run_id,
        run_name=run_name,
        status="running" if resume_state is None else resume_state.run.status,
        run_mode=run_mode,
        runtime_contour=selected_contour,
        prompt_or_policy_version=prompt_or_policy_version or str(plan["prompt_or_policy_version"]),
        created_at=datetime.fromisoformat(started_at) if started_at else _iso_now(),
        started_at=started_at,
        updated_at=_iso_now(),
        **backend_metadata,
    )
    if resume_state is not None:
        run.status = resume_state.run.status
        run.processed_count = resume_state.run.processed_count
        run.skipped_count = resume_state.run.skipped_count
        run.failed_count = resume_state.run.failed_count
        run.resume_cursor = resume_state.run.resume_cursor
    state = resume_state or LegalExtractionExecutionState(
        run=LegalExtractionRunState(
            run_id=run.run_id,
            run_name=run.run_name,
            runtime_contour=run.runtime_contour,
            run_mode=run.run_mode,
            prompt_or_policy_version=run.prompt_or_policy_version,
            source_scope_ref=source_scope_ref,
            validation_set_ref=validation_set_ref,
            status="running",
            effective_llm_backend=run.effective_llm_backend,
            effective_embedding_backend=run.effective_embedding_backend,
            llm_model_id=run.llm_model_id,
            embedding_model_id=run.embedding_model_id,
            created_at=run.started_at,
            updated_at=run.updated_at,
        ),
        items=[],
    )
    if legal_repositories is not None:
        legal_repositories["extraction_run"].upsert(
            {
                **asdict(run),
                "validation_set_ref": validation_set_ref,
                "source_scope_ref": source_scope_ref,
            }
        )
    seen_texts: set[str] = set()
    candidates: list[dict[str, object]] = []
    supports: list[dict[str, object]] = []
    review_tasks: list[dict[str, object]] = []
    rejected_outputs: list[dict[str, object]] = []
    limit = int(plan["planned_limit"])
    start_index = state.run.resume_cursor
    for fragment in fragments[start_index:limit]:
        section = sections_by_id[str(fragment["section_id"])]
        prompt = build_proposition_prompt(
            fragment=fragment,
            section=section,
            prompt_or_policy_version=run.prompt_or_policy_version,
        )
        raw_output = extractor(prompt=prompt, fragment=fragment, section=section, run=asdict(run))
        try:
            extracted = parse_proposition_output(raw_output)
        except Exception as exc:
            run.failed_count += 1
            state.run.failed_count += 1
            run.resume_cursor = state.run.resume_cursor + 1
            state.run.resume_cursor += 1
            state.items.append(
                LegalExtractionItemState(
                    fragment_id=str(fragment["fragment_id"]),
                    state="failed",
                    last_error=str(exc),
                )
            )
            rejected_outputs.append(
                {
                    "fragment_id": fragment["fragment_id"],
                    "reason": "invalid_output",
                    "error": str(exc),
                }
            )
            if state_store is not None:
                state_store.save_legal_extraction_run(state)
            continue
        run.processed_count += 1
        state.run.processed_count += 1
        run.resume_cursor = state.run.resume_cursor + 1
        state.run.resume_cursor += 1
        state.items.append(LegalExtractionItemState(fragment_id=str(fragment["fragment_id"]), state="completed"))
        for proposition in extracted:
            proposition_id = str(uuid4())
            normalized_text = proposition["proposition_text"].strip().lower()
            review_state = "pending"
            flag_state = ""
            isolation_state = ""
            if not proposition["supporting_source_citations"] or not proposition["structural_parent_references"]:
                flag_state = "weak_grounding"
            elif normalized_text in seen_texts:
                isolation_state = "ambiguous_duplicate"
            else:
                seen_texts.add(normalized_text)
            candidate = {
                "proposition_candidate_id": proposition_id,
                "proposition_text": proposition["proposition_text"],
                "proposition_type": proposition["proposition_type"],
                "run_id": run.run_id,
                "review_state": review_state,
                "trusted": False,
                "created_at": _iso_now(),
                "flag_state": flag_state,
                "isolation_state": isolation_state,
                "structural_parent_refs": proposition["structural_parent_references"],
                "supporting_source_citations": proposition["supporting_source_citations"],
            }
            candidate_supports: list[dict[str, object]] = []
            for citation_text in proposition["supporting_source_citations"]:
                support = {
                    "support_id": str(uuid4()),
                    "proposition_candidate_id": proposition_id,
                    "fragment_id": fragment["fragment_id"],
                    "section_id": section["section_id"],
                    "citation_text": citation_text,
                    "support_role": "primary",
                }
                candidate_supports.append(support)
                supports.append(support)
                if claim_repository is not None:
                    claim_repository.save_proposition_support(support)
                if legal_repositories is not None:
                    legal_repositories["proposition_support"].upsert(support)
            if claim_repository is not None:
                claim_repository.save_proposition_candidate(candidate)
            if legal_repositories is not None:
                legal_repositories["proposition_candidate"].upsert(candidate)
                _persist_graph_links(legal_repositories, candidate, candidate_supports)
            task_payload = build_proposition_review_task(candidate)
            if review_task_repository is not None:
                saved_task = review_task_repository.create_proposition_review_task(
                    proposition_candidate_id=proposition_id,
                    run_id=run.run_id,
                    assigned_reviewer=str(task_payload["assigned_reviewer"]),
                )
                review_tasks.append(saved_task)
            candidates.append(candidate)
        if state_store is not None:
            state_store.save_legal_extraction_run(state)
    run.status = "completed"
    run.updated_at = _iso_now()
    run.finished_at = run.updated_at
    state.run.status = "completed"
    state.run.updated_at = run.updated_at
    state.run.finished_at = run.finished_at
    if legal_repositories is not None:
        legal_repositories["extraction_run"].upsert(
            {
                **asdict(run),
                "validation_set_ref": validation_set_ref,
                "source_scope_ref": source_scope_ref,
            }
        )
    if state_store is not None:
        state_store.save_legal_extraction_run(state)
    return {
        "run": asdict(run),
        "state": state,
        "plan": plan,
        "candidates": candidates,
        "supports": supports,
        "review_tasks": review_tasks,
        "rejected_outputs": rejected_outputs,
        "validation_set_ref": validation_set_ref,
        "source_scope_ref": source_scope_ref,
    }
