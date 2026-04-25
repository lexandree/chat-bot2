"""Evaluation and validation fixture loading helpers."""

from __future__ import annotations

import json
from pathlib import Path


def load_evaluation_cases(path: str) -> list[dict[str, object]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_validation_question_set(path: str) -> dict[str, object]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if "question_set_id" not in payload:
        raise ValueError("Validation question set fixture must include question_set_id")
    if "questions" not in payload:
        raise ValueError("Validation question set fixture must include questions")
    return payload


def load_legal_validation_set(path: str) -> dict[str, object]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if "validation_set_id" not in payload:
        raise ValueError("Legal validation fixture must include validation_set_id")
    if "cases" not in payload:
        raise ValueError("Legal validation fixture must include cases")
    return payload
