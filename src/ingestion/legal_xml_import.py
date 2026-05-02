"""German legal XML parser for gesetze-im-internet style files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from xml.etree import ElementTree as ET


SECTION_PATTERN = re.compile(r"^§\s*(?P<number>[0-9]+[a-zA-Z]?)")


class LegalXmlImportError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LegalXmlSection:
    law_code: str
    law_title: str
    jurisdiction: str
    language: str
    section_reference: str
    normalized_reference: str
    title: str
    body_text: str
    source_uri: str
    publication_date: str = ""
    source_version_id: str = ""
    source_revision_marker: str = ""
    build_date: str = ""
    status_marker_text: str = ""


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_section_reference(value: str) -> str:
    normalized = normalize_whitespace(value)
    if normalized and not normalized.startswith("§"):
        normalized = f"§ {normalized}"
    match = SECTION_PATTERN.match(normalized)
    if not match:
        raise LegalXmlImportError(f"unsupported section reference: {value!r}")
    return f"§ {match.group('number')}"


def section_reference_slug(section_reference: str) -> str:
    return normalize_section_reference(section_reference).replace("§", "").strip().replace(" ", "-")


def _first_text(node: ET.Element | None, name: str) -> str:
    if node is None:
        return ""
    child = node.find(name)
    if child is None:
        return ""
    return normalize_whitespace("".join(child.itertext()))


def _first_text_any(node: ET.Element | None, names: tuple[str, ...]) -> str:
    for name in names:
        value = _first_text(node, name)
        if value:
            return value
    return ""


def _parse_root(path: Path) -> ET.Element:
    try:
        return ET.fromstring(path.read_text(encoding="utf-8"))
    except ET.ParseError as exc:
        raise LegalXmlImportError(f"malformed XML in {path}: {exc}") from exc


def parse_legal_xml_file(
    path: str | Path,
    *,
    law_code: str | None = None,
    jurisdiction: str = "DE",
    language: str = "de",
) -> list[LegalXmlSection]:
    source_path = Path(path)
    root = _parse_root(source_path)
    resolved_law_code = law_code or source_path.stem
    sections: list[LegalXmlSection] = []
    law_title = resolved_law_code
    publication_date = ""
    for norm in root.findall("norm"):
        metadata = norm.find("metadaten")
        if not publication_date:
            publication_date = _first_text(metadata, "ausfertigung-datum")
        for title_field in ("kurzue", "langue", "amtabk", "jurabk"):
            value = _first_text(metadata, title_field)
            if value:
                law_title = value
                break
        raw_ref = _first_text(metadata, "enbez")
        if not raw_ref:
            continue
        try:
            normalized_ref = normalize_section_reference(raw_ref)
        except LegalXmlImportError:
            continue
        title = _first_text(metadata, "titel")
        source_version_id = _first_text_any(metadata, ("fassung", "version", "source-version-id"))
        source_revision_marker = _first_text_any(metadata, ("standangabe", "stand", "revision"))
        build_date = _first_text_any(metadata, ("build-date", "build_date", "datenstand"))
        status_marker_text = _first_text_any(metadata, ("status", "status-marker", "status_marker"))
        text_node = norm.find("textdaten/text")
        body_text = normalize_whitespace("".join(text_node.itertext())) if text_node is not None else ""
        if not body_text:
            continue
        sections.append(
            LegalXmlSection(
                law_code=resolved_law_code,
                law_title=law_title,
                jurisdiction=jurisdiction,
                language=language,
                section_reference=normalized_ref,
                normalized_reference=normalized_ref,
                title=title,
                body_text=body_text,
                source_uri=str(source_path),
                publication_date=publication_date,
                source_version_id=source_version_id,
                source_revision_marker=source_revision_marker,
                build_date=build_date,
                status_marker_text=status_marker_text,
            )
        )
    return sections
