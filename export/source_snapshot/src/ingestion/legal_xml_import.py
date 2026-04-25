"""Import helpers for legal XML corpora from gesetze-im-internet style exports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any
from xml.etree import ElementTree as ET


SECTION_PATTERN = re.compile(r"^§\s*[\dA-Za-z]+")


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _repair_xml_document(text: str) -> str:
    stripped = text.strip()
    if not stripped.endswith("</dokumente>"):
        stripped = f"{stripped}</dokumente>"
    return stripped


def _parse_root(path: Path) -> ET.Element:
    text = path.read_text(encoding="utf-8", errors="ignore")
    repaired = _repair_xml_document(text)
    return ET.fromstring(repaired)


def _first_text(node: ET.Element | None, child_name: str) -> str:
    if node is None:
        return ""
    child = node.find(child_name)
    if child is None:
        return ""
    return _normalize_whitespace("".join(child.itertext()))


def _extract_law_name(root: ET.Element, fallback_code: str) -> str:
    first_norm = root.find("norm")
    if first_norm is None:
        return fallback_code
    metadata = first_norm.find("metadaten")
    for child_name in ("kurzue", "langue", "amtabk", "jurabk"):
        value = _first_text(metadata, child_name)
        if value:
            return value
    return fallback_code


def _extract_publication_date(root: ET.Element) -> str:
    first_norm = root.find("norm")
    if first_norm is None:
        return ""
    metadata = first_norm.find("metadaten")
    return _first_text(metadata, "ausfertigung-datum")


def parse_legal_xml(
    path: str,
    *,
    law_code: str | None = None,
    jurisdiction: str = "DE",
    language: str = "de",
) -> dict[str, Any]:
    source_path = Path(path)
    resolved_code = law_code or source_path.stem.replace(".top", "")
    root = _parse_root(source_path)
    law_name = _extract_law_name(root, resolved_code)
    published_at = _extract_publication_date(root)
    documents: list[dict[str, Any]] = []
    skipped = 0

    for norm in root.findall("norm"):
        metadata = norm.find("metadaten")
        text_node = norm.find("textdaten/text")
        section_ref = _first_text(metadata, "enbez")
        title = _first_text(metadata, "titel")
        body_text = _normalize_whitespace("".join(text_node.itertext())) if text_node is not None else ""
        if not section_ref or not SECTION_PATTERN.match(section_ref) or not body_text:
            skipped += 1
            continue
        source_id = f"{resolved_code}:{section_ref}"
        documents.append(
            {
                "source_id": source_id,
                "law_code": resolved_code,
                "source_type": "law",
                "title": f"{section_ref} {title}".strip(),
                "section_ref": section_ref,
                "law_name": law_name,
                "jurisdiction": jurisdiction,
                "language": language,
                "source_uri_or_ref": str(source_path),
                "published_at": published_at,
                "effective_from": "",
                "retrieved_at": "",
                "freshness_note": "",
                "checksum": source_id,
                "body_text": body_text,
            }
        )

    return {
        "law_code": resolved_code,
        "law_name": law_name,
        "source_file": str(source_path),
        "document_count": len(documents),
        "skipped_norm_count": skipped,
        "documents": documents,
    }


def load_import_manifest(path: str) -> dict[str, Any]:
    manifest_path = Path(path)
    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_legal_import_corpus(manifest: dict[str, Any]) -> dict[str, Any]:
    imported: list[dict[str, Any]] = []
    missing_inputs: list[dict[str, Any]] = []
    for item in manifest.get("inputs", []):
        source_path = Path(str(item["path"]))
        if not source_path.exists():
            missing_inputs.append(
                {
                    "law_code": item.get("law_code", source_path.stem),
                    "path": str(source_path),
                }
            )
            continue
        imported.append(
            parse_legal_xml(
                str(source_path),
                law_code=str(item.get("law_code", source_path.stem)),
                jurisdiction=str(item.get("jurisdiction", "DE")),
                language=str(item.get("language", "de")),
            )
        )
    return {
        "manifest_name": manifest.get("name", "legal_xml_import"),
        "imported_sources": imported,
        "missing_inputs": missing_inputs,
        "imported_source_count": len(imported),
        "imported_document_count": sum(item["document_count"] for item in imported),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare legal XML import corpus")
    parser.add_argument(
        "--manifest",
        default="tests/fixtures/legal_xml_import_manifest.json",
        help="Path to the import manifest JSON",
    )
    parser.add_argument(
        "--output",
        default="tests/fixtures/legal_xml_import_preview.json",
        help="Path to the output preview JSON",
    )
    args = parser.parse_args(argv)

    manifest = load_import_manifest(args.manifest)
    corpus = build_legal_import_corpus(manifest)
    output_path = Path(args.output)
    output_path.write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Prepared legal import preview: {corpus['imported_document_count']} documents "
        f"from {corpus['imported_source_count']} source files"
    )
    if corpus["missing_inputs"]:
        print(f"Missing inputs: {len(corpus['missing_inputs'])}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI helper
    raise SystemExit(main())
