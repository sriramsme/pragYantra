"""A single-stream async runner with explicit resource ownership."""

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from pragyantra.application.behavior import DescribeOnTouch
from pragyantra.application.interfaces import ObservationSource, ResponseOutput
from pragyantra.application.models import (
    TouchObservation,
    VisualObservation,
    require_aware,
)
from pragyantra.application.world_state import WorldState

_LOG = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AssistantRuntime:
    def __init__(
        self,
        behavior: DescribeOnTouch,
        *,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.state = WorldState()
        self.behavior = behavior
        self._now = now

    async def run(
        self,
        source: AbstractAsyncContextManager[ObservationSource],
        output: AbstractAsyncContextManager[ResponseOutput],
    ) -> None:
        """Close entered resources on completion, startup failure, or cancellation.

        Events must arrive in nondecreasing receipt order. Acquisition times may
        differ: delayed inference results do not replace a newer scene.
        """
        last_received_at: datetime | None = None
        async with source as observations, output as responses:
            async for event in observations:
                at = self._now()
                require_aware(at, "runtime clock")
                if event.received_at > at:
                    raise ValueError(
                        "An event cannot arrive ahead of the runtime clock"
                    )
                if last_received_at is not None:
                    if event.received_at < last_received_at:
                        raise ValueError("Events must be ordered by receipt time")
                last_received_at = event.received_at
                observation = event.observation
                match observation:
                    case VisualObservation():
                        accepted = self.state.observe(observation)
                        _LOG.debug(
                            "Visual observation source=%s observed_at=%s "
                            "received_at=%s accepted=%s",
                            observation.source,
                            observation.observed_at.isoformat(),
                            event.received_at.isoformat(),
                            accepted,
                        )
                    case TouchObservation():
                        response = self.behavior.respond(self.state, observation, at=at)
                        await responses.emit(response)
                    case _:
                        raise TypeError(f"Unsupported observation: {type(observation)}")
