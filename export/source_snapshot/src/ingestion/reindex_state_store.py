"""File-backed operational state store for reindex and enrichment jobs."""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import asdict

from ingestion.reindex_state import (
    EnrichmentExecutionState,
    EnrichmentRunItemState,
    EnrichmentRunRecord,
    LegalExtractionExecutionState,
    LegalExtractionItemState,
    LegalExtractionRunState,
    ReindexExecutionState,
    ReindexItemState,
    ReindexJob,
)


class FileReindexStateStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def save(self, state: ReindexExecutionState) -> None:
        payload = {
            "job": asdict(state.job),
            "items": [asdict(item) for item in state.items],
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self) -> ReindexExecutionState | None:
        if not self.path.exists():
            return None
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        job = ReindexJob(**payload["job"])
        items = [ReindexItemState(**item) for item in payload.get("items", [])]
        return ReindexExecutionState(job=job, items=items)

    def save_enrichment_run(self, state: EnrichmentExecutionState) -> None:
        payload = {
            "run": asdict(state.run),
            "items": [asdict(item) for item in state.items],
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_enrichment_run(self) -> EnrichmentExecutionState | None:
        if not self.path.exists():
            return None
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if "run" not in payload:
            return None
        run = EnrichmentRunRecord(**payload["run"])
        items = [EnrichmentRunItemState(**item) for item in payload.get("items", [])]
        return EnrichmentExecutionState(run=run, items=items)

    def save_legal_extraction_run(self, state: LegalExtractionExecutionState) -> None:
        payload = {
            "run": asdict(state.run),
            "items": [asdict(item) for item in state.items],
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_legal_extraction_run(self) -> LegalExtractionExecutionState | None:
        if not self.path.exists():
            return None
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if "run" not in payload:
            return None
        run = LegalExtractionRunState(**payload["run"])
        items = [LegalExtractionItemState(**item) for item in payload.get("items", [])]
        return LegalExtractionExecutionState(run=run, items=items)
