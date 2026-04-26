"""Report serialization helpers for foundation artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from graph.types import to_plain_dict


FORBIDDEN_ANSWER_FIELDS = {"answer_text", "answer", "generated_answer"}


def to_artifact_dict(record: Any) -> dict[str, Any]:
    payload = to_plain_dict(record)
    if not isinstance(payload, dict):
        raise TypeError("artifact payload must be a mapping")
    return payload


def ensure_no_answer_fields(payload: Mapping[str, Any]) -> None:
    present = FORBIDDEN_ANSWER_FIELDS.intersection(payload)
    if present:
        raise ValueError(f"structural retrieval artifact contains forbidden answer fields: {sorted(present)}")


def structural_retrieval_artifact(record: Any) -> dict[str, Any]:
    payload = to_artifact_dict(record)
    ensure_no_answer_fields(payload)
    return payload


def write_json_artifact(path: str | Path, payload: Mapping[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
