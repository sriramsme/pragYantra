"""Exercise the public demo command and argument validation as a user would."""

import builtins
import json
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest

from pragyantra import cli
from pragyantra.application.models import ImageFrame, SceneDescription


def test_demo_reports_response_evidence_as_json_lines():
    result = subprocess.run(
        [sys.executable, "-m", "pragyantra", "demo", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert [record["status"] for record in records] == [
        "unavailable",
        "current",
        "stale",
    ]
    assert records[0]["visual"] is None
    assert records[1]["visual"]["source"] == "simulated.camera"
    assert records[1]["visual_age_seconds"] == 2
    assert records[2]["visual_age_seconds"] == 7


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "1e-300", "1e300"])
def test_invalid_age_exits_with_argument_error(value):
    result = subprocess.run(
        [sys.executable, "-m", "pragyantra", "demo", "--max-visual-age", value],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "positive, finite duration" in result.stderr


def test_see_reuses_behavior_with_model_provenance(image_path, monkeypatch, capsys):
    from pragyantra.providers import openai as provider_module

    class FakeVision:
        async def describe(self, image):
            return SceneDescription("A red image.", "fake-vision", "test-model")

    closed = []

    @asynccontextmanager
    async def provider(**kwargs):
        try:
            yield FakeVision()
        finally:
            closed.append(True)

    monkeypatch.setattr(provider_module, "openai_vision", provider)
    monkeypatch.setattr(sys, "argv", ["pragyantra", "see", str(image_path), "--json"])
    cli.main()
    record = json.loads(capsys.readouterr().out)
    assert record["status"] == "current"
    assert record["visual"]["source"] == "file:scene.png"
    assert record["visual"]["provider"] == "fake-vision"
    assert record["visual"]["model"] == "test-model"
    assert record["trigger"]["source"] == "simulated.touch"
    assert closed == [True]


def test_capture_time_is_not_reset_after_inference(image_path, monkeypatch, capsys):
    from pragyantra.providers import openai as provider_module

    class FakeVision:
        async def describe(self, image):
            return SceneDescription("An old image.", "fake", "test")

    @asynccontextmanager
    async def provider(**kwargs):
        yield FakeVision()

    captured = datetime.now(UTC) - timedelta(minutes=1)
    monkeypatch.setattr(provider_module, "openai_vision", provider)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pragyantra",
            "see",
            str(image_path),
            "--captured-at",
            captured.isoformat(),
            "--json",
        ],
    )
    cli.main()
    record = json.loads(capsys.readouterr().out)
    assert record["status"] == "stale"
    assert record["visual"]["observed_at"] == captured.isoformat()
    assert record["visual_age_seconds"] >= 60


def test_invalid_image_does_not_initialize_provider(tmp_path, monkeypatch, capsys):
    from pragyantra.providers import openai as provider_module

    def unexpected_provider(**kwargs):
        pytest.fail("Invalid local input must be rejected before opening a provider")

    monkeypatch.setattr(provider_module, "openai_vision", unexpected_provider)
    monkeypatch.setattr(
        sys, "argv", ["pragyantra", "see", str(tmp_path / "missing.png")]
    )
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 1
    assert "file not found" in capsys.readouterr().err


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["scene.png", "--webcam", "0"],
        ["--webcam", "-1"],
        ["--webcam", "not-an-index"],
        ["--webcam", "0", "--captured-at", "2026-10-20T10:00:00Z"],
    ],
)
def test_see_rejects_ambiguous_or_invalid_sources(monkeypatch, arguments):
    monkeypatch.setattr(sys, "argv", ["pragyantra", "see", *arguments])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2


def test_webcam_reuses_perception_behavior_and_provenance(monkeypatch, capsys):
    from pragyantra.inputs import webcam
    from pragyantra.providers import openai as provider_module

    frame = ImageFrame("webcam:2", datetime.now(UTC), b"fake-image")
    events = []

    def capture(index):
        assert index == 2
        events.append("capture")
        return frame

    class FakeVision:
        async def describe(self, image):
            assert image is frame
            events.append("describe")
            return SceneDescription("A desk.", "fake", "test", "original")

    @asynccontextmanager
    async def provider(**kwargs):
        assert kwargs["image_detail"] == "original"
        yield FakeVision()
        events.append("provider closed")

    monkeypatch.setattr(webcam, "capture_webcam", capture)
    monkeypatch.setattr(provider_module, "openai_vision", provider)
    monkeypatch.setattr(
        sys,
        "argv",
        ["pragyantra", "see", "--webcam", "2", "--image-detail", "original", "--json"],
    )
    cli.main()
    record = json.loads(capsys.readouterr().out)
    assert record["status"] == "current"
    assert record["visual"]["source"] == "webcam:2"
    assert record["visual"]["observed_at"] == frame.observed_at.isoformat()
    assert record["visual"]["image_detail"] == "original"
    assert events == ["capture", "describe", "provider closed"]


def test_missing_webcam_extra_is_actionable_before_provider_start(monkeypatch, capsys):
    from pragyantra.providers import openai as provider_module

    original_import = builtins.__import__

    def without_opencv(name, *args, **kwargs):
        if name == "cv2":
            raise ModuleNotFoundError("No module named cv2")
        return original_import(name, *args, **kwargs)

    def unexpected_provider(**kwargs):
        pytest.fail("Failed acquisition must not initialize a provider")

    monkeypatch.setattr(builtins, "__import__", without_opencv)
    monkeypatch.setattr(provider_module, "openai_vision", unexpected_provider)
    monkeypatch.setattr(sys, "argv", ["pragyantra", "see", "--webcam", "0"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    assert "uv sync --extra webcam" in capsys.readouterr().err
