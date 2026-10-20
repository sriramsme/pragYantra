"""Stream CLI output and close contexts without cameras, API calls, or real waits."""

import json
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest

from pragyantra import cli
from pragyantra.application import observation_loop
from pragyantra.application.interfaces import VisionError
from pragyantra.application.models import ImageFrame, SceneDescription
from pragyantra.inputs import webcam
from pragyantra.providers import openai as provider_module


def install_components(monkeypatch, *, fail_second=False, before_second=None):
    events = []
    observers = []
    real_observer = observation_loop.VisualObservationLoop

    async def sleep(seconds):
        events.append(("wait", seconds))

    def observer(interval, *, count):
        assert interval == timedelta(seconds=5)
        result = real_observer(interval, count=count, sleep=sleep)
        observers.append(result)
        return result

    class Frames:
        def __init__(self, index):
            assert index == 2
            self.reads = 0

        async def __aenter__(self):
            events.append("camera opened")
            return self

        async def __aexit__(self, *args):
            events.append("camera closed")

        async def read(self):
            self.reads += 1
            return ImageFrame(
                "fake.camera", datetime.now(UTC), str(self.reads).encode()
            )

    class Vision:
        calls = 0

        async def describe(self, image):
            self.calls += 1
            if self.calls == 2:
                if before_second:
                    before_second()
                if fail_second:
                    raise VisionError("provider unavailable")
            events.append(("describe", self.calls))
            return SceneDescription(f"Scene {self.calls}", "fake", "test-model", "low")

    vision = Vision()

    @asynccontextmanager
    async def provider(**kwargs):
        events.append("provider opened")
        try:
            yield vision
        finally:
            events.append("provider closed")

    monkeypatch.setattr(observation_loop, "VisualObservationLoop", observer)
    monkeypatch.setattr(webcam, "WebcamStream", Frames)
    monkeypatch.setattr(provider_module, "openai_vision", provider)
    monkeypatch.setattr(
        sys, "argv", ["pragyantra", "watch", "--webcam", "2", "--count", "2", "--json"]
    )
    return events, vision, observers


def test_watch_streams_each_result_and_closes_resources_at_count(monkeypatch, capsys):
    first_output = []

    def before_second():
        first_output.append(capsys.readouterr().out)
        assert "Scene 1" in first_output[0]

    events, vision, observers = install_components(
        monkeypatch, before_second=before_second
    )
    cli.main()
    output = "".join(first_output) + capsys.readouterr().out
    records = [json.loads(line) for line in output.splitlines()]
    assert [record["description"] for record in records] == ["Scene 1", "Scene 2"]
    assert all(record["kind"] == "visual_observation" for record in records)
    assert all(record["visual_age_seconds"] >= 0 for record in records)
    assert all(record["image_detail"] == "low" for record in records)
    assert vision.calls == 2
    assert observers[0].state.visual.description == "Scene 2"
    assert events == [
        "provider opened",
        "camera opened",
        ("describe", 1),
        ("wait", 5),
        ("describe", 2),
        "camera closed",
        "provider closed",
    ]


def test_watch_provider_error_stops_without_retry_and_closes_contexts(
    monkeypatch, capsys
):
    events, vision, observers = install_components(monkeypatch, fail_second=True)
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert "Scene 1" in captured.out
    assert "provider unavailable" in captured.err
    assert vision.calls == 2
    assert observers[0].state.visual.description == "Scene 1"
    assert events[-2:] == ["camera closed", "provider closed"]


@pytest.mark.parametrize(
    "arguments",
    [
        ["--interval", "0"],
        ["--interval", "nan"],
        ["--count", "0"],
        ["--count", "-1"],
        ["--count", "1.5"],
    ],
)
def test_watch_rejects_invalid_pacing_or_count(monkeypatch, arguments):
    monkeypatch.setattr(sys, "argv", ["pragyantra", "watch", *arguments])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
