from __future__ import annotations

from ingestion.verification import build_embedding_run_report
from retrieval.embedding_profile import EmbeddingProfile


def test_embedding_run_report_assembly() -> None:
    profile = EmbeddingProfile(embedding_profile_id="profile", dimensions=1024)

    report = build_embedding_run_report(
        selected_scope={"law_codes": ["AufenthG"]},
        processed_count=2,
        skipped_count=1,
        failed_count=0,
        profile=profile,
        backend_name="local_embedding_endpoint",
    )

    assert report.embedding_profile_id == "profile"
    assert report.backend_name == "local_embedding_endpoint"
    assert report.routing_mode == "local_only"
    assert report.vector_dimensions == 1024
    assert report.batch_size == 16
    assert report.processed_count == 2
    assert report.skipped_count == 1
