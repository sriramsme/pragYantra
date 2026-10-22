"""Embed assistant turns and background perception without a CLI or device setup."""

import asyncio
from collections.abc import AsyncIterable, Awaitable, Callable
from datetime import UTC, datetime, timedelta

from pragyantra.application.behavior import DescribeOnTouch
from pragyantra.application.conversation import ConversationResult, ConversationSession
from pragyantra.application.interfaces import ImageSource, VisionProvider
from pragyantra.application.models import (
    ContextResponse,
    SensorObservation,
    TextObservation,
    TouchObservation,
    VisualObservation,
    require_aware,
)
from pragyantra.application.observation_loop import VisualObservationLoop

type AssistantInput = (
    TextObservation | SensorObservation | TouchObservation | VisualObservation
)
type AssistantResult = ConversationResult | ContextResponse


class AssistantRunner:
    """Run serial input/results alongside optional independent visual perception.

    The caller opens and closes devices/providers around ``run``. This runner
    owns its tasks and closes an input iterator when it offers ``aclose``; input
    generators can therefore release their own per-iteration resources in finally.
    Output is awaited, not buffered. Use a fresh runner for concurrent sessions.
    """

    def __init__(
        self,
        session: ConversationSession,
        *,
        image_source: ImageSource | None = None,
        vision: VisionProvider | None = None,
        vision_interval: timedelta = timedelta(seconds=5),
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if (image_source is None) != (vision is None):
            raise ValueError("Supply both image_source and vision, or neither")
        self.session = session
        self._source = image_source
        self._vision = vision
        self._now = now
        self._running = False
        self._observer = VisualObservationLoop(
            vision_interval, state=session.state, now=now, sleep=sleep
        )

    async def _handle(self, observation: AssistantInput) -> AssistantResult | None:
        if not isinstance(
            observation,
            (TextObservation, SensorObservation, TouchObservation, VisualObservation),
        ):
            raise TypeError(
                f"Unsupported assistant input: {type(observation).__name__}"
            )
        at = self._now()
        require_aware(at, "runner clock")
        if observation.observed_at > at:
            raise ValueError("Input event is ahead of the session clock")
        if isinstance(observation, (SensorObservation, VisualObservation)):
            self.session.state.observe(observation)
            return None
        if isinstance(observation, TouchObservation):
            return DescribeOnTouch(self.session.max_context_age).respond(
                self.session.state, observation, at=at
            )
        return await self.session.respond(observation)

    async def run(
        self,
        observations: AsyncIterable[AssistantInput],
        *,
        on_result: Callable[[AssistantResult], Awaitable[None]],
    ) -> None:
        """Wait for initial vision, consume inputs, and finish all owned tasks.

        EOF completes normally. Input, perception, generation or output failure
        stops the run. Cancellation propagates after task/iterator cleanup. Single
        failures propagate directly; simultaneous failures remain an ExceptionGroup.
        Resources supplied by the caller remain open until its own contexts exit.
        """
        if self._running:
            raise RuntimeError("AssistantRunner is already running")
        self._running = True
        ready = asyncio.Event()

        async def observe():
            assert self._source is not None and self._vision is not None
            async for _ in self._observer.observations(self._source, self._vision):
                ready.set()

        async def consume():
            iterator = observations.__aiter__()
            try:
                async for observation in iterator:
                    result = await self._handle(observation)
                    if result is not None:
                        await on_result(result)
            finally:
                close = getattr(iterator, "aclose", None)
                if close is not None:
                    await close()

        try:
            try:
                async with asyncio.TaskGroup() as group:
                    background = (
                        group.create_task(observe())
                        if self._source is not None
                        else None
                    )
                    try:
                        if background is not None:
                            await ready.wait()
                        await consume()
                    finally:
                        if background is not None:
                            background.cancel()
            except ExceptionGroup as errors:
                error: BaseException = errors
                while isinstance(error, ExceptionGroup) and len(error.exceptions) == 1:
                    error = error.exceptions[0]
                raise error from None
        finally:
            self._running = False
