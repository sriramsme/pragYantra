"""Logical-clock tests for serial inference, pacing, context, and cancellation."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from pragyantra.application.interfaces import VisionError
from pragyantra.application.models import ImageFrame, SceneDescription
from pragyantra.application.observation_loop import VisualObservationLoop


class Clock:
    def __init__(self):
        self.at = datetime(2026, 10, 20, tzinfo=UTC)
        self.sleeps = []

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.at += timedelta(seconds=seconds)


class Frames:
    def __init__(self, clock):
        self.clock = clock
        self.reads = 0

    async def read(self):
        self.reads += 1
        return ImageFrame("fake.camera", self.clock.at, str(self.reads).encode())


class Vision:
    def __init__(self, clock):
        self.clock = clock
        self.calls = 0

    async def describe(self, image):
        self.calls += 1
        self.clock.at += timedelta(seconds=2)
        return SceneDescription(f"Scene {self.calls}", "fake", "test", "low")


def test_serial_cycles_preserve_timing_pace_after_output_and_update_context():
    async def scenario():
        clock = Clock()
        frames, vision = Frames(clock), Vision(clock)
        observer = VisualObservationLoop(
            timedelta(seconds=5), count=3, sleep=clock.sleep, now=lambda: clock.at
        )
        results = []
        async for event in observer.observations(frames, vision):
            results.append(event)
            assert observer.state.visual is event.observation
            assert event.received_at - event.observation.observed_at == timedelta(
                seconds=2
            )
            # Consumer handling happens before the interval and next acquisition.
            clock.at += timedelta(seconds=1)
        assert frames.reads == vision.calls == 3
        assert clock.sleeps == [5, 5]
        assert results[1].observation.observed_at - results[0].received_at == timedelta(
            seconds=6
        )
        assert observer.state.visual.description == "Scene 3"

    asyncio.run(scenario())


def test_backpressure_does_not_start_another_request_until_iteration_resumes():
    async def scenario():
        clock = Clock()
        frames, vision = Frames(clock), Vision(clock)
        observer = VisualObservationLoop(
            count=2, sleep=clock.sleep, now=lambda: clock.at
        )
        stream = observer.observations(frames, vision)
        await anext(stream)
        assert frames.reads == vision.calls == 1
        assert clock.sleeps == []
        await stream.aclose()
        assert frames.reads == vision.calls == 1

    asyncio.run(scenario())


def test_provider_failure_stops_without_retry_or_replacing_context():
    async def scenario():
        clock = Clock()
        frames, vision = Frames(clock), Vision(clock)
        observer = VisualObservationLoop(
            count=3, sleep=clock.sleep, now=lambda: clock.at
        )
        stream = observer.observations(frames, vision)
        first = await anext(stream)

        async def fail(image):
            vision.calls += 1
            raise VisionError("provider unavailable")

        vision.describe = fail
        with pytest.raises(VisionError, match="provider unavailable"):
            await anext(stream)
        assert frames.reads == vision.calls == 2
        assert observer.state.visual is first.observation
        assert clock.sleeps == [5]

    asyncio.run(scenario())


def test_cancellation_during_inference_propagates_without_new_requests():
    async def scenario():
        clock = Clock()
        frames = Frames(clock)
        entered = asyncio.Event()

        class BlockedVision:
            async def describe(self, image):
                entered.set()
                await asyncio.Event().wait()

        observer = VisualObservationLoop(sleep=clock.sleep, now=lambda: clock.at)
        stream = observer.observations(frames, BlockedVision())
        pending = asyncio.create_task(anext(stream))
        await entered.wait()
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert observer.state.visual is None
        assert frames.reads == 1
        assert clock.sleeps == []

    asyncio.run(scenario())


def test_future_frame_cannot_poison_context():
    async def scenario():
        clock = Clock()
        frames, vision = Frames(clock), Vision(clock)
        observer = VisualObservationLoop(
            count=1, now=lambda: clock.at - timedelta(seconds=3)
        )
        with pytest.raises(ValueError, match="before acquisition"):
            await anext(observer.observations(frames, vision))
        assert observer.state.visual is None

    asyncio.run(scenario())
