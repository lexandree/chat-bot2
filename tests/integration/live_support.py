from __future__ import annotations

from contextlib import suppress
from typing import Any

from graph.repositories import GraphDataRepository
from ingestion.legal_preview_loader import build_preview_from_manifest_path
from ingestion.legal_preview_loader import sha256_text


LIVE_TEST_LAW_CODE = "TestAufenthG"
LIVE_TEST_SECTION_ID = f"legal-section:{LIVE_TEST_LAW_CODE}:1:current"
LIVE_RELATIONSHIP_LAW_CODE = "TestRelG"


def build_live_test_preview() -> dict[str, Any]:
    preview = build_preview_from_manifest_path("tests/fixtures/legal_xml_import_manifest.json")
    return _replace_fixture_law_code(preview)


def build_live_relationship_test_preview() -> dict[str, Any]:
    fragments = [
        (
            "1",
            "Grundsatz",
            "Die Einzelheiten ergeben sich aus § 2 TestRelG.",
        ),
        (
            "2",
            "Begriffe",
            "Aufenthalt im Sinne des § 1 TestRelG ist der tatsaechliche Aufenthalt.",
        ),
        (
            "3",
            "Ausnahmen",
            "Abweichend von § 99 TestRelG kann die Behoerde eine Ausnahme zulassen.",
        ),
        (
            "4",
            "Andere Gesetze",
            "Die Vorschrift gilt, wenn die Voraussetzungen des § 1 OtherRelG vorliegen.",
        ),
    ]
    source_document = {
        "source_document_id": "source-document:DE:de:TestRelG",
        "source_family": "law",
        "jurisdiction": "DE",
        "language": "de",
        "law_code": LIVE_RELATIONSHIP_LAW_CODE,
        "title": "Test Relationship Law",
        "source_uri": "fixture://testrelg",
        "local_reference": "tests/fixtures/live_relationship",
        "publication_date": "2026-01-01",
        "effective_date": "2026-01-01",
        "retrieved_at": "2026-01-01T00:00:00Z",
        "checksum": "fixture-live-relationship",
    }
    source_fragments = []
    for index, title, body_text in fragments:
        source_fragments.append(
            {
                "source_fragment_id": f"source-fragment:TestRelG:{index}",
                "source_document_id": source_document["source_document_id"],
                "law_code": LIVE_RELATIONSHIP_LAW_CODE,
                "section_reference": f"§ {index}",
                "normalized_reference": f"§ {index}",
                "title": title,
                "body_text": body_text,
                "order_index": int(index),
                "checksum": sha256_text(body_text),
            }
        )
    return {
        "preview_id": "preview:live-relationship-testrelg",
        "source_scope": {"source_families": ["law"], "law_codes": [LIVE_RELATIONSHIP_LAW_CODE]},
        "source_documents": [source_document],
        "source_fragments": source_fragments,
        "missing_inputs": [],
    }


def cleanup_live_test_scope(client: Any) -> None:
    with suppress(Exception):
        GraphDataRepository(client).delete_scope(law_codes=[LIVE_TEST_LAW_CODE], confirm=True)
    with suppress(Exception):
        GraphDataRepository(client).delete_scope(law_codes=[LIVE_RELATIONSHIP_LAW_CODE], confirm=True)


def _replace_fixture_law_code(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("AufenthG", LIVE_TEST_LAW_CODE)
    if isinstance(value, list):
        return [_replace_fixture_law_code(item) for item in value]
    if isinstance(value, dict):
        return {key: _replace_fixture_law_code(item) for key, item in value.items()}
    return value
