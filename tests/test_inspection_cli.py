"""Inspection inputs and CLI composition use only synthetic images/providers."""

import json
import sys
from contextlib import asynccontextmanager

import pytest
from PIL import Image

from pragyantra import cli
from pragyantra.application.inspection import ImageJudgment, JudgmentBatch, QuestionKind
from pragyantra.inputs.inspection import load_questions
from pragyantra.providers import openai_decisions


def test_question_file_supports_station_no_match_and_score(tmp_path):
    path = tmp_path / "questions.json"
    path.write_text(
        json.dumps(
            [
                {"name": "target", "instructions": "Is a red shape visible?"},
                {
                    "name": "station",
                    "kind": "choice",
                    "instructions": "Which station?",
                    "options": [["desk", "A desk"], ["none", "Other or unclear"]],
                },
                {
                    "name": "coverage",
                    "kind": "score",
                    "instructions": "How much red?",
                    "options": [["empty", "None"], ["full", "All red"]],
                },
            ]
        )
    )
    questions = load_questions(path)
    assert tuple(q.kind for q in questions) == tuple(QuestionKind)
    path.write_text('[{"name":"target","instructions":"test","unexpected":1}]')
    with pytest.raises(ValueError):
        load_questions(path)
    path.write_text('[{"name":"target","instructions":"test","options": [1]}]')
    with pytest.raises(ValueError):
        load_questions(path)


def test_inspection_cli_normalizes_image_and_reports_judgment_without_conversation(
    monkeypatch, tmp_path, capsys
):
    path = tmp_path / "red.png"
    Image.new("RGB", (2048, 1000), "red").save(path)
    calls = []

    class Provider:
        async def evaluate(self, frame, questions):
            calls.append((frame, questions))
            assert frame.mime_type == "image/jpeg"
            return JudgmentBatch(
                tuple(ImageJudgment(q, probability=0.98) for q in questions),
                "fake",
                "test",
                100,
                10,
            )

    @asynccontextmanager
    async def provider(**settings):
        try:
            yield Provider()
        finally:
            calls.append("closed")

    monkeypatch.setattr(openai_decisions, "openai_decisions", provider)
    monkeypatch.setattr(
        sys,
        "argv",
        ["prag", "inspect", str(path), "--condition", "Is red visible?", "-j"],
    )
    cli.main()
    record = json.loads(capsys.readouterr().out)
    assert record["status"] == "completed"
    assert record["batch"]["judgments"][0]["probability"] == 0.98
    assert record["evidence"]["source"] == "file:red.png"
    assert calls[-1] == "closed"


def test_bad_questions_fail_before_device_acquisition(monkeypatch):
    from pragyantra.inputs import webcam

    monkeypatch.setattr(
        webcam, "capture_webcam", lambda *args: pytest.fail("Opened device")
    )
    monkeypatch.setattr(
        sys, "argv", ["prag", "inspect", "--camera", "--condition", " "]
    )
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1


def test_provider_failure_json_has_no_judgment_and_nonzero_exit(
    monkeypatch, image_path, capsys
):
    from pragyantra.application.interfaces import ProviderError

    class Failed:
        async def evaluate(self, frame, questions):
            raise ProviderError("private service details")

    @asynccontextmanager
    async def provider(**settings):
        yield Failed()

    monkeypatch.setattr(openai_decisions, "openai_decisions", provider)
    monkeypatch.setattr(
        sys,
        "argv",
        ["prag", "inspect", str(image_path), "--condition", "Is red visible?", "-j"],
    )
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    captured = capsys.readouterr()
    record = json.loads(captured.out)
    assert record["status"] == "provider_failure" and record["batch"] is None
    assert "private" not in captured.err


def test_missing_credentials_do_not_open_camera(monkeypatch):
    from pragyantra.inputs import webcam

    monkeypatch.setattr(
        webcam, "capture_webcam", lambda *args: pytest.fail("Opened camera")
    )
    monkeypatch.setattr(
        sys, "argv", ["prag", "inspect", "--camera", "--condition", "Is red visible?"]
    )
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
