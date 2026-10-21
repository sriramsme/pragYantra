"""Serial visual interpretation with current context and explicit pacing."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta

from pragyantra.application.interfaces import ImageSource, VisionProvider
from pragyantra.application.models import (
    MAX_PREVIOUS_DESCRIPTION_CHARS,
    ImageFrame,
    ObservationEvent,
    PreviousSceneContext,
)
from pragyantra.application.perception import perceive_image
from pragyantra.application.world_state import WorldState


class VisualObservationLoop:
    """Interpret one frame at a time and retain the newest acquired scene.

    The interval is a delay after the caller handles each result, not a capture
    rate or deadline. Acquisition adapters decide how to select the next frame.
    The caller owns source/provider contexts and output; no history is accumulated.
    """

    def __init__(
        self,
        interval: timedelta = timedelta(seconds=5),
        *,
        count: int | None = None,
        temporal_context: bool = False,
        context_max_gap: timedelta = timedelta(seconds=30),
        state: WorldState | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if interval <= timedelta(0):
            raise ValueError("Observation interval must be positive")
        if count is not None and count <= 0:
            raise ValueError("Observation count must be positive")
        if context_max_gap <= timedelta(0):
            raise ValueError("Context maximum gap must be positive")
        self.state = state if state is not None else WorldState()
        self._interval = interval.total_seconds()
        self._count = count
        self._temporal_context = temporal_context
        self._context_max_gap = context_max_gap
        self._sleep = sleep
        self._now = now

    def _context_for(self, frame: ImageFrame) -> PreviousSceneContext | None:
        previous = self.state.visual
        if not self._temporal_context or previous is None:
            return None
        gap = frame.observed_at - previous.observed_at
        if (
            frame.source != previous.source
            or gap <= timedelta(0)
            or gap > self._context_max_gap
            or len(previous.description) > MAX_PREVIOUS_DESCRIPTION_CHARS
        ):
            return None
        return PreviousSceneContext(
            source=previous.source,
            observed_at=previous.observed_at,
            description=previous.description,
            gap=gap,
            provider=previous.provider,
            model=previous.model,
        )

    async def observations(
        self, source: ImageSource, provider: VisionProvider
    ) -> AsyncIterator[ObservationEvent]:
        completed = 0
        while self._count is None or completed < self._count:
            frame = await source.read()
            visual = await perceive_image(
                frame, provider, previous=self._context_for(frame)
            )
            event = ObservationEvent(visual, received_at=self._now())
            self.state.observe(visual)
            completed += 1
            yield event
            if self._count is None or completed < self._count:
                await self._sleep(self._interval)
