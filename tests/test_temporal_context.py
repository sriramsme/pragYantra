"""Context selection uses acquisition time and flat, bounded prior evidence."""

import asyncio
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest

from pragyantra.application.models import (
    MAX_PREVIOUS_DESCRIPTION_CHARS,
    ImageFrame,
    PreviousSceneContext,
    SceneDescription,
)
from pragyantra.application.observation_loop import VisualObservationLoop
from pragyantra.application.perception import perceive_image

BASE = datetime(2026, 10, 20, tzinfo=UTC)


async def run_frames(frames, *, enabled=True, max_gap=30, first_description="Scene 1"):
    class Frames:
        async def read(self):
            return next(pending)

    class Vision:
        def __init__(self):
            self.contexts = []

        async def describe(self, image, *, previous=None):
            self.contexts.append(previous)
            text = (
                first_description
                if len(self.contexts) == 1
                else f"Scene {len(self.contexts)}"
            )
            return SceneDescription(text, "fake", "test-model")

    async def no_wait(seconds):
        pass

    pending = iter(frames)
    provider = Vision()
    observer = VisualObservationLoop(
        count=len(frames),
        temporal_context=enabled,
        context_max_gap=timedelta(seconds=max_gap),
        sleep=no_wait,
        # Completion times deliberately differ from the frame-to-frame gaps.
        now=lambda: BASE + timedelta(hours=1),
    )
    events = [event async for event in observer.observations(Frames(), provider)]
    return events, provider.contexts, observer


def frame(seconds, source="camera"):
    return ImageFrame(source, BASE + timedelta(seconds=seconds), b"fake")


def test_independent_default_does_not_send_or_record_previous_descriptions():
    events, contexts, _ = asyncio.run(run_frames([frame(0), frame(7)], enabled=False))
    assert contexts == [None, None]
    assert all(event.observation.previous_context is None for event in events)


def test_opt_in_preserves_actual_gap_and_only_the_immediately_previous_description():
    events, contexts, observer = asyncio.run(
        run_frames([frame(0), frame(7), frame(14)])
    )
    assert contexts[0] is None
    assert contexts[1].description == "Scene 1"
    assert contexts[2].description == "Scene 2"
    for index in (1, 2):
        previous = contexts[index]
        assert previous.observed_at == events[index - 1].observation.observed_at
        assert previous.gap == timedelta(seconds=7)
        assert previous.provider == "fake"
        assert previous.model == "test-model"
        assert events[index].observation.previous_context is previous
        assert "previous_context" not in asdict(previous)
    assert observer.state.visual is events[-1].observation


@pytest.mark.parametrize(
    "gap,source,description_size,max_gap,expected",
    [
        (30, "camera", 10, 30, True),
        (30.000001, "camera", 10, 30, False),
        (0, "camera", 10, 30, False),
        (-1, "camera", 10, 30, False),
        (7, "other-camera", 10, 30, False),
        (7, "camera", MAX_PREVIOUS_DESCRIPTION_CHARS, 30, True),
        (7, "camera", MAX_PREVIOUS_DESCRIPTION_CHARS + 1, 30, False),
        (7, "camera", 10, 5, False),
        (7, "camera", 10, 10, True),
    ],
)
def test_context_eligibility_boundaries(
    gap, source, description_size, max_gap, expected
):
    events, contexts, _ = asyncio.run(
        run_frames(
            [frame(0), frame(gap, source)],
            max_gap=max_gap,
            first_description="x" * description_size,
        )
    )
    assert (contexts[1] is not None) is expected
    assert events[1].observation.previous_context is contexts[1]


@pytest.mark.parametrize("source,gap", [("other-camera", 7), ("camera", 8)])
def test_inconsistent_explicit_context_is_rejected_before_calling_provider(source, gap):
    previous = PreviousSceneContext(
        "camera", BASE, "An earlier scene.", timedelta(seconds=gap)
    )

    class UnexpectedVision:
        async def describe(self, *args, **kwargs):
            pytest.fail("Invalid context must not reach the provider")

    with pytest.raises(ValueError, match="source and acquisition gap"):
        asyncio.run(
            perceive_image(frame(7, source), UnexpectedVision(), previous=previous)
        )
