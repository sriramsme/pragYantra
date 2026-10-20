"""Serial visual interpretation with current context and explicit pacing."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta

from pragyantra.application.interfaces import ImageSource, VisionProvider
from pragyantra.application.models import ObservationEvent
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
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if interval <= timedelta(0):
            raise ValueError("Observation interval must be positive")
        if count is not None and count <= 0:
            raise ValueError("Observation count must be positive")
        self.state = WorldState()
        self._interval = interval.total_seconds()
        self._count = count
        self._sleep = sleep
        self._now = now

    async def observations(
        self, source: ImageSource, provider: VisionProvider
    ) -> AsyncIterator[ObservationEvent]:
        completed = 0
        while self._count is None or completed < self._count:
            frame = await source.read()
            visual = await perceive_image(frame, provider)
            event = ObservationEvent(visual, received_at=self._now())
            self.state.observe(visual)
            completed += 1
            yield event
            if self._count is None or completed < self._count:
                await self._sleep(self._interval)
