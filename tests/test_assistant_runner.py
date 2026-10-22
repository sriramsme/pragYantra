"""Programmatic assistant use: shared state, task supervision and iterator lifetime."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest

from pragyantra.application.conversation import (
    ConversationResult,
    ConversationSession,
    GeneratedReply,
)
from pragyantra.application.models import (
    ContextResponse,
    ImageFrame,
    SceneDescription,
    SensorObservation,
    TextObservation,
    TouchObservation,
    VisualObservation,
)
from pragyantra.application.runner import AssistantRunner

AT = datetime(2026, 10, 21, 12, tzinfo=UTC)


class Provider:
    def __init__(self):
        self.requests = []

    async def respond(self, request):
        self.requests.append(request)
        return GeneratedReply(
            "A reply using supplied evidence.", "fake", "conversation"
        )

    async def describe(self, frame):
        return SceneDescription("A blue mug.", "fake", "vision")


def session(provider):
    return ConversationSession(provider, now=lambda: AT)


async def text_source(*texts):
    for text in texts:
        yield TextObservation("test.user", AT, text)


async def discard(result):
    pass


async def block(seconds):
    await asyncio.Event().wait()


def test_typed_observations_and_results_share_context_without_cli(capsys):
    async def scenario():
        provider = Provider()
        conversation = session(provider)
        runner = AssistantRunner(conversation, now=lambda: AT)
        results = []

        async def inputs():
            yield SensorObservation("controller", AT, "temperature", 23.5, "degC")
            yield VisualObservation("camera", AT, "A blue mug.")
            yield TouchObservation("controller", AT)
            yield TextObservation("operator", AT, "What do you see?")

        async def receive(result):
            results.append(result)

        await runner.run(inputs(), on_result=receive)
        assert isinstance(results[0], ContextResponse)
        assert results[0].visual.description == "A blue mug."
        assert isinstance(results[1], ConversationResult)
        assert results[1].environment.sensors[0].value == 23.5
        assert provider.requests[0].environment.visual.source == "camera"
        assert results[1].responded_at == AT

    asyncio.run(scenario())
    assert capsys.readouterr().out == ""


def test_background_vision_continues_while_reply_uses_frozen_first_snapshot():
    async def scenario():
        generating, second_scene = asyncio.Event(), asyncio.Event()
        events = []

        class Frames:
            count = 0

            async def read(self):
                self.count += 1
                events.append(f"capture {self.count}")
                return ImageFrame(
                    "camera", AT - timedelta(seconds=2 - self.count), b"synthetic"
                )

        class Services(Provider):
            descriptions = 0

            async def describe(self, frame):
                self.descriptions += 1
                events.append(f"describe {self.descriptions}")
                return SceneDescription(f"Scene {self.descriptions}", "fake", "vision")

            async def respond(self, request):
                generating.set()
                await second_scene.wait()
                assert conversation.state.visual.description == "Scene 2"
                assert request.environment.visual.description == "Scene 1"
                return await super().respond(request)

        services = Services()
        conversation = session(services)

        async def pacing(seconds):
            assert seconds == 5
            if services.descriptions == 1:
                await generating.wait()
            else:
                second_scene.set()
                await asyncio.Event().wait()

        async def inputs():
            events.append("input consumed")
            yield TextObservation("user", AT, "What is visible?")

        runner = AssistantRunner(
            conversation,
            image_source=Frames(),
            vision=services,
            now=lambda: AT,
            sleep=pacing,
        )
        await asyncio.wait_for(runner.run(inputs(), on_result=discard), timeout=2)
        assert events.index("describe 1") < events.index("input consumed")
        assert services.descriptions == 2
        assert conversation.state.visual.observed_at == AT

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "failure", ["capture", "vision", "input", "conversation", "output"]
)
def test_failure_stops_tasks_and_caller_contexts_close_in_order(failure):
    async def scenario():
        events = []

        class Frames:
            async def read(self):
                if failure == "capture":
                    raise OSError("capture failed")
                return ImageFrame("camera", AT, b"synthetic")

        class Services(Provider):
            async def describe(self, frame):
                if failure == "vision":
                    raise ValueError("vision failed")
                return await super().describe(frame)

            async def respond(self, request):
                if failure == "conversation":
                    raise ValueError("conversation failed")
                return await super().respond(request)

        @asynccontextmanager
        async def owned(name, resource):
            events.append(f"{name} open")
            try:
                yield resource
            finally:
                events.append(f"{name} close")

        async def inputs():
            events.append("input open")
            try:
                if failure == "input":
                    raise ValueError("input failed")
                yield TextObservation("user", AT, "Hello")
            finally:
                events.append("input close")

        async def output(result):
            if failure == "output":
                raise OSError("output failed")

        with pytest.raises((ValueError, OSError), match=f"{failure} failed"):
            async with (
                owned("provider", Services()) as provider,
                owned("camera", Frames()) as frames,
            ):
                runner = AssistantRunner(
                    session(provider),
                    image_source=frames,
                    vision=provider,
                    now=lambda: AT,
                    sleep=block,
                )
                await runner.run(inputs(), on_result=output)
        assert events[-2:] == ["camera close", "provider close"]
        if failure not in ("capture", "vision"):
            assert events.index("input close") < events.index("camera close")
        else:
            assert "input open" not in events

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["capture", "conversation", "output"])
def test_cancellation_finishes_owned_work_before_host_releases_resources(stage):
    async def scenario():
        started = asyncio.Event()
        events = []

        class Frames:
            async def read(self):
                if stage == "capture":
                    started.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        events.append("capture cancelled")
                return ImageFrame("camera", AT, b"synthetic")

        class Services(Provider):
            async def respond(self, request):
                if stage == "conversation":
                    started.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        events.append("generation cancelled")
                return await super().respond(request)

        async def inputs():
            try:
                yield TextObservation("user", AT, "Hello")
            finally:
                events.append("input closed")

        async def output(result):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                events.append("output cancelled")

        @asynccontextmanager
        async def camera():
            try:
                yield Frames()
            finally:
                events.append("camera closed")

        async def host():
            async with camera() as frames:
                runner = AssistantRunner(
                    session(Services()),
                    image_source=frames,
                    vision=Provider(),
                    now=lambda: AT,
                    sleep=block,
                )
                await runner.run(inputs(), on_result=output)

        task = asyncio.create_task(host())
        await asyncio.wait_for(started.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert events[-1] == "camera closed"
        assert any("cancelled" in event for event in events)
        if stage != "capture":
            assert "input closed" in events

    asyncio.run(scenario())


def test_output_backpressure_and_concurrent_run_guard_then_sequential_reuse():
    async def scenario():
        delivering, allow_output = asyncio.Event(), asyncio.Event()
        yielded, results = [], []
        runner = AssistantRunner(session(Provider()), now=lambda: AT)

        async def inputs():
            for text in ("first", "second"):
                yielded.append(text)
                yield TextObservation("user", AT, text)

        async def output(result):
            delivering.set()
            await allow_output.wait()
            results.append(result)

        task = asyncio.create_task(runner.run(inputs(), on_result=output))
        await asyncio.wait_for(delivering.wait(), timeout=2)
        assert yielded == ["first"]
        with pytest.raises(RuntimeError, match="already running"):
            await runner.run(text_source("duplicate"), on_result=discard)
        allow_output.set()
        await task
        assert len(results) == 2
        await runner.run(text_source("third"), on_result=discard)
        assert len(runner.session.history.messages) == 6

    asyncio.run(scenario())


def test_supplied_resources_stay_open_and_iterator_closes_on_output_failure():
    async def scenario():
        events = []
        provider = Provider()

        class Frames:
            closed = False

            async def aclose(self):
                self.closed = True

            async def read(self):
                assert not self.closed
                return ImageFrame("camera", AT, b"synthetic")

        frames = Frames()

        async def inputs():
            try:
                yield TextObservation("user", AT, "Hello")
            finally:
                events.append("iterator closed")

        async def output(result):
            raise OSError("consumer disconnected")

        runner = AssistantRunner(
            session(provider),
            image_source=frames,
            vision=provider,
            now=lambda: AT,
            sleep=block,
        )
        with pytest.raises(OSError):
            await runner.run(inputs(), on_result=output)
        assert events == ["iterator closed"]
        assert not frames.closed  # Host ownership is not taken over by the runner.

    asyncio.run(scenario())


def test_bad_configuration_and_invalid_evidence_fail_before_generation():
    provider = Provider()
    for settings in (
        {"image_source": object()},
        {"vision": provider},
        {"vision_interval": timedelta(0)},
    ):
        with pytest.raises(ValueError):
            AssistantRunner(session(provider), **settings)

    async def scenario():
        runner = AssistantRunner(session(provider), now=lambda: AT)

        async def future():
            yield TextObservation("user", AT + timedelta(seconds=1), "Hello")

        with pytest.raises(ValueError, match="ahead"):
            await runner.run(future(), on_result=discard)
        assert provider.requests == []

    asyncio.run(scenario())


def test_background_failure_after_startup_cancels_inflight_generation():
    async def scenario():
        generating = asyncio.Event()
        events = []

        class Frames:
            count = 0

            async def read(self):
                self.count += 1
                if self.count > 1:
                    await generating.wait()
                    raise OSError("camera disconnected")
                return ImageFrame("camera", AT, b"synthetic")

        class Services(Provider):
            async def respond(self, request):
                generating.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    events.append("generation cancelled")

        async def pacing(seconds):
            await generating.wait()

        async def inputs():
            try:
                yield TextObservation("user", AT, "Hello")
            finally:
                events.append("iterator closed")

        provider = Services()
        conversation = session(provider)
        runner = AssistantRunner(
            conversation,
            image_source=Frames(),
            vision=provider,
            now=lambda: AT,
            sleep=pacing,
        )
        with pytest.raises(OSError, match="camera disconnected"):
            await asyncio.wait_for(runner.run(inputs(), on_result=discard), timeout=2)
        assert events == ["generation cancelled", "iterator closed"]
        assert conversation.history.messages == ()

    asyncio.run(scenario())


def test_simultaneous_output_and_background_cleanup_errors_are_preserved():
    async def scenario():
        pacing_started = asyncio.Event()

        class Frames:
            async def read(self):
                return ImageFrame("camera", AT, b"synthetic")

        async def pacing(seconds):
            pacing_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                raise ValueError("background cleanup failed")

        async def output(result):
            await pacing_started.wait()
            raise OSError("output failed")

        runner = AssistantRunner(
            session(Provider()),
            image_source=Frames(),
            vision=Provider(),
            now=lambda: AT,
            sleep=pacing,
        )
        with pytest.raises(ExceptionGroup) as error:
            await runner.run(text_source("Hello"), on_result=output)
        assert {str(item) for item in error.value.exceptions} == {
            "background cleanup failed",
            "output failed",
        }

    asyncio.run(scenario())


def test_embedding_example_runs_from_another_directory_without_credentials(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    example = Path(__file__).resolve().parents[1] / "examples" / "embed_assistant.py"
    result = subprocess.run(
        [sys.executable, str(example)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    assert result.stdout.splitlines() == [
        "Fixture reply: A solid blue square.",
        "Image source closed: True",
    ]
    assert result.stderr == ""
