"""A recording output for finite simulations and tests; it does not produce audio."""

from types import TracebackType
from typing import Self

from pragyantra.application.models import ContextResponse


class RecordingOutput:
    def __init__(self) -> None:
        self._responses: list[ContextResponse] = []
        self._active = False
        self.closed = False

    @property
    def responses(self) -> tuple[ContextResponse, ...]:
        return tuple(self._responses)

    async def __aenter__(self) -> Self:
        if self._active:
            raise RuntimeError("Output is already active")
        self._active = True
        self.closed = False
        self._responses.clear()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._active = False
        self.closed = True

    async def emit(self, response: ContextResponse) -> None:
        if not self._active:
            raise RuntimeError("Output must be entered before recording")
        self._responses.append(response)
