"""Small contracts consumed by the runtime, independent of concrete I/O."""

from collections.abc import AsyncIterator
from typing import Protocol

from pragyantra.application.audio import AudioClip
from pragyantra.application.models import (
    ContextResponse,
    ImageFrame,
    ObservationEvent,
    PreviousSceneContext,
    SceneDescription,
    TextObservation,
)


class ObservationSource(Protocol):
    def __aiter__(self) -> AsyncIterator[ObservationEvent]: ...


class ResponseOutput(Protocol):
    async def emit(self, response: ContextResponse) -> None: ...


class VisionProvider(Protocol):
    async def describe(
        self, image: ImageFrame, *, previous: PreviousSceneContext | None = None
    ) -> SceneDescription: ...


class ImageSource(Protocol):
    async def read(self) -> ImageFrame: ...


class TranscriptionProvider(Protocol):
    async def transcribe(self, audio: AudioClip) -> TextObservation: ...


class SpeechProvider(Protocol):
    async def synthesize(self, text: str) -> AudioClip: ...


class ProviderError(RuntimeError):
    """A sanitized external capability failure."""


class VisionError(ProviderError):
    """An actionable provider error safe to display without SDK request details."""
