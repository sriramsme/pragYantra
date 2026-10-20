"""Finite observation replay with a logical clock; no devices or real-time waits."""

import asyncio
from collections.abc import AsyncIterator, Iterable
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self

from pragyantra.application.models import (
    ObservationEvent,
    TouchObservation,
    VisualObservation,
)


class SimulatedInput:
    def __init__(self, events: Iterable[ObservationEvent]) -> None:
        self._events = tuple(events)
        self._time: datetime | None = None
        self._active = False
        self.closed = False

    def now(self) -> datetime:
        """Use this as the runtime clock to advance through replay without sleeps."""
        if self._time is None:
            raise RuntimeError("The simulation clock starts with its first event")
        return self._time

    async def __aenter__(self) -> Self:
        if self._active:
            raise RuntimeError("Input is already active")
        self._active = True
        self.closed = False
        self._time = None
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._active = False
        self.closed = True

    async def __aiter__(self) -> AsyncIterator[ObservationEvent]:
        if not self._active:
            raise RuntimeError("Input must be entered before replay")
        for event in self._events:
            await asyncio.sleep(0)  # Cancellation checkpoint, not a timing simulation.
            self._time = event.received_at
            yield event


def visual_context_demo(
    *,
    scene: str = "A mug and a notebook are on a desk.",
    started_at: datetime | None = None,
) -> SimulatedInput:
    """Replay missing, current, delayed-old, and stale context on a fixed timeline."""
    start = started_at if started_at is not None else datetime.now(UTC)

    def time_at(seconds: int) -> datetime:
        return start + timedelta(seconds=seconds)

    return SimulatedInput(
        [
            ObservationEvent(
                TouchObservation("simulated.touch", time_at(0)), time_at(0)
            ),
            ObservationEvent(
                VisualObservation("simulated.camera", time_at(1), scene), time_at(2)
            ),
            ObservationEvent(
                TouchObservation("simulated.touch", time_at(3)), time_at(3)
            ),
            ObservationEvent(
                VisualObservation(
                    "simulated.camera", time_at(0), "An older scene arriving late."
                ),
                time_at(4),
            ),
            ObservationEvent(
                TouchObservation("simulated.touch", time_at(8)), time_at(8)
            ),
        ]
    )
