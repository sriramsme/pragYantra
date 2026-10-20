"""Small contracts consumed by the runtime, independent of concrete I/O."""

from collections.abc import AsyncIterator
from typing import Protocol

from pragyantra.application.models import (
    ContextResponse,
    ImageFrame,
    ObservationEvent,
    SceneDescription,
)


class ObservationSource(Protocol):
    def __aiter__(self) -> AsyncIterator[ObservationEvent]: ...


class ResponseOutput(Protocol):
    async def emit(self, response: ContextResponse) -> None: ...


class VisionProvider(Protocol):
    async def describe(self, image: ImageFrame) -> SceneDescription: ...


class VisionError(RuntimeError):
    """An actionable provider error safe to display without SDK request details."""
