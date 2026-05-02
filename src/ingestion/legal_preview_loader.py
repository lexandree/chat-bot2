"""Deterministic legal XML preview assembly."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable

from ingestion.legal_xml_import import (
    LegalXmlImportError,
    LegalXmlSection,
    parse_legal_xml_file,
    section_reference_slug,
)


DETERMINISTIC_CREATED_AT = "1970-01-01T00:00:00Z"


def sha256_text(text: str) -> str:
    return "sha256:" + sha256(text.encode("utf-8")).hexdigest()


def stable_source_document_id(section: LegalXmlSection) -> str:
    return f"source-document:{section.jurisdiction}:{section.language}:{section.law_code}"


def stable_source_fragment_id(section: LegalXmlSection) -> str:
    return f"source-fragment:{section.law_code}:{section_reference_slug(section.section_reference)}"


def load_manifest(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _matches_law_filter(law_code: str, law_codes: Iterable[str] | None) -> bool:
    if not law_codes:
        return True
    allowed = {code.strip() for code in law_codes if code.strip()}
    return law_code in allowed


def build_preview_from_manifest(
    manifest: dict[str, Any],
    *,
    law_codes: list[str] | None = None,
) -> dict[str, Any]:
    missing_inputs: list[dict[str, Any]] = []
    source_documents_by_id: dict[str, dict[str, Any]] = {}
    fragments: list[dict[str, Any]] = []
    for item in manifest.get("inputs", []):
        law_code = str(item.get("law_code", ""))
        if not _matches_law_filter(law_code, law_codes):
            continue
        source_path = Path(str(item["path"]))
        required = bool(item.get("required", True))
        if not source_path.exists():
            missing = {"path": str(source_path), "required": required, "reason": "missing"}
            missing_inputs.append(missing)
            if required:
                raise FileNotFoundError(f"required legal XML input missing: {source_path}")
            continue
        try:
            sections = parse_legal_xml_file(
                source_path,
                law_code=law_code or None,
                jurisdiction=str(item.get("jurisdiction", "DE")),
                language=str(item.get("language", "de")),
            )
        except LegalXmlImportError as exc:
            if required:
                raise LegalXmlImportError(f"{source_path}: {exc}") from exc
            missing_inputs.append({"path": str(source_path), "required": required, "reason": "malformed"})
            continue
        for section in sections:
            source_document_id = stable_source_document_id(section)
            source_documents_by_id.setdefault(
                source_document_id,
                {
                    "source_document_id": source_document_id,
                    "source_family": "law",
                    "jurisdiction": section.jurisdiction,
                    "language": section.language,
                    "law_code": section.law_code,
                    "source_uri": section.source_uri,
                    "title": section.law_title,
                    "publication_date": section.publication_date,
                    "source_version_id": section.source_version_id,
                    "source_revision_marker": section.source_revision_marker,
                    "build_date": section.build_date,
                    "checksum": sha256_text(section.source_uri + section.law_code + section.law_title),
                },
            )
            fragment_payload = {
                "source_fragment_id": stable_source_fragment_id(section),
                "source_document_id": source_document_id,
                "law_code": section.law_code,
                "section_reference": section.section_reference,
                "normalized_reference": section.normalized_reference,
                "title": section.title,
                "body_text": section.body_text,
                "order_index": len(fragments) + 1,
                "checksum": sha256_text(section.body_text),
                "source_version_id": section.source_version_id,
                "source_revision_marker": section.source_revision_marker,
                "build_date": section.build_date,
                "status_marker_text": section.status_marker_text,
            }
            fragments.append(fragment_payload)
    source_documents = sorted(source_documents_by_id.values(), key=lambda item: item["source_document_id"])
    fragments = sorted(fragments, key=lambda item: (item["law_code"], item["section_reference"], item["source_fragment_id"]))
    for index, fragment in enumerate(fragments, start=1):
        fragment["order_index"] = index
    source_scope = {
        "source_families": ["law"],
        "law_codes": sorted({fragment["law_code"] for fragment in fragments} or set(law_codes or [])),
    }
    fingerprint = sha256_text(json.dumps([source_documents, fragments, missing_inputs], sort_keys=True))
    return {
        "preview_id": f"preview:{fingerprint.removeprefix('sha256:')[:16]}",
        "created_at": DETERMINISTIC_CREATED_AT,
        "source_scope": source_scope,
        "missing_inputs": sorted(missing_inputs, key=lambda item: item["path"]),
        "source_documents": source_documents,
        "source_fragments": fragments,
    }


def build_preview_from_manifest_path(
    manifest_path: str | Path,
    *,
    law_codes: list[str] | None = None,
) -> dict[str, Any]:
    return build_preview_from_manifest(load_manifest(manifest_path), law_codes=law_codes)


def write_preview_artifact(path: str | Path, preview: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(preview, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
