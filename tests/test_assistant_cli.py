"""Exercise the real assistant CLI with fake providers and devices."""

import json
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest

from pragyantra import cli
from pragyantra.application.audio import AudioClip
from pragyantra.application.conversation import GeneratedReply
from pragyantra.application.models import ImageFrame, SceneDescription, TextObservation
from pragyantra.providers import openai_services


def test_local_script_persists_and_recalls_explicit_memory(tmp_path):
    database = tmp_path / "notes.sqlite"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pragyantra",
            "chat",
            "--commands-only",
            "--memory",
            str(database),
            "--message",
            "/remember The blue mug is mine",
            "--message",
            "/recall mug",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert "The blue mug is mine" in records[1]["text"]
    lookup = subprocess.run(
        [
            sys.executable,
            "-m",
            "pragyantra",
            "memory",
            "--database",
            str(database),
            "search",
            "mug",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(lookup.stdout)[0]["text"] == "The blue mug is mine"


def test_jsonl_hardware_events_update_context_and_touch_without_models():
    timestamp = datetime.now(UTC).isoformat()
    events = [
        {
            "version": 1,
            "type": "sensor",
            "source": "controller",
            "observed_at": timestamp,
            "kind": "temperature",
            "value": 23.5,
            "unit": "degC",
        },
        {
            "version": 1,
            "type": "text",
            "source": "operator",
            "observed_at": timestamp,
            "text": "/context",
        },
        {
            "version": 1,
            "type": "touch",
            "source": "controller",
            "observed_at": timestamp,
        },
    ]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pragyantra",
            "chat",
            "--commands-only",
            "--events",
            "--json",
        ],
        input="\n".join(json.dumps(event) for event in events),
        capture_output=True,
        text=True,
        check=True,
    )
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert records[0]["environment"]["sensors"][0]["value"] == 23.5
    assert records[1]["kind"] == "touch_response"
    assert records[1]["status"] == "unavailable"


def test_integrated_camera_audio_reply_and_speech_close_all_contexts(
    tmp_path, monkeypatch, capsys
):
    from pragyantra.inputs import webcam
    from pragyantra.outputs import audio as output

    events, requests = [], []
    clip = AudioClip("file-test", datetime.now(UTC), b"\x00\x00" * 1600)
    path = tmp_path / "utterance.wav"
    path.write_bytes(clip.as_wav())

    class Frames:
        def __init__(self, index):
            assert index == 0

        async def __aenter__(self):
            events.append("camera open")
            return self

        async def __aexit__(self, *args):
            events.append("camera close")

        async def read(self):
            return ImageFrame("camera", datetime.now(UTC), b"image")

    class Services:
        @property
        def vision(self):
            return self

        async def describe(self, frame, **kwargs):
            events.append("vision")
            return SceneDescription("A blue mug on the desk.", "fake", "vision")

        async def transcribe(self, audio):
            events.append("transcribe")
            return TextObservation(
                audio.source, audio.observed_at, "What do you see?", "fake", "asr"
            )

        async def respond(self, request):
            events.append("respond")
            requests.append(request)
            return GeneratedReply("A blue mug.", "fake", "chat")

    @asynccontextmanager
    async def provider(**kwargs):
        events.append("provider open")
        try:
            yield Services()
        finally:
            events.append("provider close")

    async def speak(text, provider, **kwargs):
        events.append("speak")
        assert text == "A blue mug."

    monkeypatch.setattr(openai_services, "openai_services", provider)
    monkeypatch.setattr(webcam, "WebcamStream", Frames)
    monkeypatch.setattr(output, "speak_text", speak)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pragyantra",
            "chat",
            "--audio",
            str(path),
            "--audio",
            str(path),
            "--webcam",
            "0",
            "--speak",
            "--json",
        ],
    )
    cli.main()
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(records) == 2
    assert requests[0].environment.visual.description == "A blue mug on the desk."
    assert len(requests[1].history) == 2
    assert events[-2:] == ["camera close", "provider close"]
    assert events.index("vision") < events.index("transcribe")


@pytest.mark.parametrize(
    "arguments",
    [
        ["chat", "--commands-only", "--voice"],
        ["chat", "--count", "2"],
        ["chat", "--message", "hi", "--events"],
        ["listen", "utterance.wav", "--microphone"],
        ["speak"],
    ],
)
def test_incompatible_modes_fail_before_devices_or_provider_start(
    monkeypatch, arguments
):
    monkeypatch.setattr(sys, "argv", ["pragyantra", *arguments])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2


@pytest.mark.parametrize("failure", ["camera_open", "vision", "speech"])
def test_integrated_failure_unwinds_camera_and_provider(monkeypatch, failure):
    from pragyantra.application.interfaces import ProviderError
    from pragyantra.inputs import webcam
    from pragyantra.outputs import audio as output

    events = []

    class Frames:
        def __init__(self, index):
            pass

        async def __aenter__(self):
            events.append("camera open")
            if failure == "camera_open":
                raise ValueError("camera startup failed")
            return self

        async def __aexit__(self, *args):
            events.append("camera close")

        async def read(self):
            return ImageFrame("camera", datetime.now(UTC), b"image")

    class Services:
        vision = None

        def __init__(self):
            self.vision = self

        async def describe(self, frame, **kwargs):
            if failure == "vision":
                raise ProviderError("vision failed")
            return SceneDescription("A mug.", "fake", "vision")

        async def respond(self, request):
            return GeneratedReply("A mug.", "fake", "chat")

    @asynccontextmanager
    async def provider(**kwargs):
        events.append("provider open")
        try:
            yield Services()
        finally:
            events.append("provider close")

    async def speech(*args, **kwargs):
        raise ValueError("speech failed")

    monkeypatch.setattr(openai_services, "openai_services", provider)
    monkeypatch.setattr(webcam, "WebcamStream", Frames)
    monkeypatch.setattr(output, "speak_text", speech)
    monkeypatch.setattr(
        sys,
        "argv",
        ["pragyantra", "chat", "--webcam", "0", "--message", "Hello", "--speak"],
    )
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    assert events[-1] == "provider close"
    if failure != "camera_open":
        assert events[-2] == "camera close"


def test_voice_turns_are_half_duplex_and_stop_phrase_skips_generation(monkeypatch):
    from pragyantra.inputs import microphone
    from pragyantra.outputs import audio as output

    events = []
    transcripts = iter(["Hello", "Stop PragYantra."])

    class Services:
        async def transcribe(self, clip):
            events.append("transcribe")
            return TextObservation(clip.source, clip.observed_at, next(transcripts))

        async def respond(self, request):
            events.append("respond")
            return GeneratedReply("Hi.", "fake", "chat")

    @asynccontextmanager
    async def provider(**kwargs):
        try:
            yield Services()
        finally:
            events.append("close")

    async def record(**kwargs):
        events.append("record-and-close")
        return AudioClip("fake", datetime.now(UTC), b"\x00\x00" * 320)

    async def speak(*args, **kwargs):
        events.append("speak-and-close")

    monkeypatch.setattr(openai_services, "openai_services", provider)
    monkeypatch.setattr(microphone, "record_microphone", record)
    monkeypatch.setattr(output, "speak_text", speak)
    monkeypatch.setattr(sys, "argv", ["pragyantra", "chat", "--voice"])
    cli.main()
    assert events == [
        "record-and-close",
        "transcribe",
        "respond",
        "speak-and-close",
        "record-and-close",
        "transcribe",
        "close",
    ]


def test_cancel_combined_session_waits_for_provider_and_camera_cleanup(monkeypatch):
    import argparse
    import asyncio

    from pragyantra.cli.assistant import run_assistant
    from pragyantra.cli.configure import add_commands
    from pragyantra.inputs import webcam

    events = []

    async def scenario():
        generating = asyncio.Event()

        class Frames:
            def __init__(self, index):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                events.append("camera close")

            async def read(self):
                return ImageFrame("camera", datetime.now(UTC), b"image")

        class Services:
            @property
            def vision(self):
                return self

            async def describe(self, frame, **kwargs):
                return SceneDescription("A mug.", "fake", "vision")

            async def respond(self, request):
                generating.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    events.append("generation cancelled")

        @asynccontextmanager
        async def provider(**kwargs):
            try:
                yield Services()
            finally:
                events.append("provider close")

        monkeypatch.setattr(openai_services, "openai_services", provider)
        monkeypatch.setattr(webcam, "WebcamStream", Frames)
        parser = argparse.ArgumentParser()
        add_commands(
            parser.add_subparsers(dest="command"),
            duration=cli._positive_duration,
            count=cli._positive_count,
            timestamp=cli._capture_time,
            camera_index=cli._camera_index,
        )
        args = parser.parse_args(["chat", "--webcam", "0", "--message", "Hello"])
        task = asyncio.create_task(run_assistant(args))
        await asyncio.wait_for(generating.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert events == ["generation cancelled", "camera close", "provider close"]

    asyncio.run(scenario())
