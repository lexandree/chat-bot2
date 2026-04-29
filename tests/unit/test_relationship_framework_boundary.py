from __future__ import annotations

import re
from pathlib import Path


RELATIONSHIP_SOURCE_FILES = [
    Path("src/ingestion/legal_reference_parser.py"),
    Path("src/ingestion/legal_structure_builder.py"),
    Path("src/graph/writer.py"),
    Path("src/evaluation/load_cases.py"),
    Path("src/app/commands.py"),
]

ACCEPTANCE_DOCS = [
    Path("specs/003-legal-graph-relationships/spec.md"),
    Path("specs/003-legal-graph-relationships/plan.md"),
    Path("specs/003-legal-graph-relationships/quickstart.md"),
    Path("LEGAL_GRAPH_RELATIONSHIP_METHODS.md"),
]


def test_relationship_source_imports_no_chatbot_llm_or_graphrag_sidecars() -> None:
    forbidden_import = re.compile(r"^\s*(from|import)\s+.*(chatbot|llm|graphrag|kg_builder)", re.IGNORECASE)

    offenders: list[str] = []
    for path in RELATIONSHIP_SOURCE_FILES:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if forbidden_import.search(line):
                offenders.append(f"{path}:{line_no}:{line}")

    assert offenders == []


def test_relationship_acceptance_docs_do_not_promote_legacy_or_framework_output_as_truth() -> None:
    forbidden_phrases = [
        "legacy graph is source of truth",
        "legacy baseline is source of truth",
        "framework output is source of truth",
        "graphrag output is source of truth",
        "must run microsoft graphrag",
        "must run neo4j graphrag",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in ACCEPTANCE_DOCS)

    for phrase in forbidden_phrases:
        assert phrase not in combined
    assert "no legacy graph comparison is required" in combined
    assert "acceptance does not require running either framework" in combined
