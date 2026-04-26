from __future__ import annotations

from contextlib import suppress
from typing import Any

from graph.repositories import GraphDataRepository
from ingestion.legal_preview_loader import build_preview_from_manifest_path


LIVE_TEST_LAW_CODE = "TestAufenthG"
LIVE_TEST_SECTION_ID = f"legal-section:{LIVE_TEST_LAW_CODE}:1:current"


def build_live_test_preview() -> dict[str, Any]:
    preview = build_preview_from_manifest_path("tests/fixtures/legal_xml_import_manifest.json")
    return _replace_fixture_law_code(preview)


def cleanup_live_test_scope(client: Any) -> None:
    with suppress(Exception):
        GraphDataRepository(client).delete_scope(law_codes=[LIVE_TEST_LAW_CODE], confirm=True)


def _replace_fixture_law_code(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("AufenthG", LIVE_TEST_LAW_CODE)
    if isinstance(value, list):
        return [_replace_fixture_law_code(item) for item in value]
    if isinstance(value, dict):
        return {key: _replace_fixture_law_code(item) for key, item in value.items()}
    return value
