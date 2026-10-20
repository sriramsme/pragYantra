"""Small contracts consumed by the runtime, independent of concrete I/O."""

from collections.abc import AsyncIterator
from typing import Protocol

from pragyantra.application.models import ContextResponse, ObservationEvent


class ObservationSource(Protocol):
    def __aiter__(self) -> AsyncIterator[ObservationEvent]: ...


class ResponseOutput(Protocol):
    async def emit(self, response: ContextResponse) -> None: ...
