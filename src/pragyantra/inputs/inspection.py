"""Read bounded application question definitions, independent of any SDK."""

import json
from pathlib import Path

from pragyantra.application.inspection import (
    InspectionQuestion,
    QuestionKind,
    validate_questions,
)


def load_questions(path: Path) -> tuple[InspectionQuestion, ...]:
    with path.open("rb") as source:
        raw = source.read(65537)
    if len(raw) > 65536:
        raise ValueError("Question file exceeds 64 KiB")
    try:
        records = json.loads(raw)
        if not isinstance(records, list) or not 1 <= len(records) <= 16:
            raise ValueError("Supply 1–16 inspection questions")
        questions = []
        for row in records:
            if (
                not isinstance(row, dict)
                or not {"name", "instructions"} <= row.keys()
                or row.keys() - {"name", "instructions", "kind", "options", "version"}
            ):
                raise ValueError("Invalid question fields")
            options = row.get("options", [])
            if not isinstance(options, list) or any(
                not isinstance(pair, list)
                or len(pair) != 2
                or any(not isinstance(v, str) for v in pair)
                for pair in options
            ):
                raise ValueError("Options must be [label, description] pairs")
            if any(
                not isinstance(row.get(key, default), str)
                for key, default in (
                    ("name", ""),
                    ("instructions", ""),
                    ("version", "1"),
                )
            ):
                raise ValueError("Question text fields must be strings")
            questions.append(
                InspectionQuestion(
                    row["name"],
                    row["instructions"],
                    QuestionKind(row.get("kind", "predicate")),
                    tuple(tuple(p) for p in options),
                    row.get("version", "1"),
                )
            )
        result = tuple(questions)
        validate_questions(result)
        return result
    except (TypeError, AttributeError, KeyError) as exc:
        raise ValueError("Invalid inspection question definitions") from exc
