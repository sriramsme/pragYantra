"""Immutable observations and responses shared across component boundaries."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum


def require_aware(value: datetime, name: str) -> None:
    """Reject ambiguous timestamps rather than guessing their timezone."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")


def _validate_observation(source: str, observed_at: datetime) -> None:
    if not source.strip():
        raise ValueError("Observation source must not be empty")
    require_aware(observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class VisualObservation:
    """An interpreted scene, timestamped when its source image was acquired."""

    source: str
    observed_at: datetime
    description: str
    provider: str | None = None
    model: str | None = None
    image_detail: str | None = None

    def __post_init__(self) -> None:
        _validate_observation(self.source, self.observed_at)
        if not self.description.strip():
            raise ValueError("Visual description must not be empty")


@dataclass(frozen=True, slots=True)
class ImageFrame:
    """Acquired image bytes; providers must not replace their acquisition time."""

    source: str
    observed_at: datetime
    data: bytes = field(repr=False)
    mime_type: str = "image/jpeg"

    def __post_init__(self) -> None:
        _validate_observation(self.source, self.observed_at)
        if not self.data:
            raise ValueError("Image data must not be empty")


@dataclass(frozen=True, slots=True)
class SceneDescription:
    """Provider-independent interpretation with provider/model provenance."""

    text: str
    provider: str
    model: str
    image_detail: str | None = None

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.text, self.provider, self.model)):
            raise ValueError("Description and provider/model names must not be empty")


@dataclass(frozen=True, slots=True)
class TouchObservation:
    """A touch event; its interpretation belongs to application behavior."""

    source: str
    observed_at: datetime

    def __post_init__(self) -> None:
        _validate_observation(self.source, self.observed_at)


type Observation = VisualObservation | TouchObservation


@dataclass(frozen=True, slots=True)
class ObservationEvent:
    """An observation with a separate time of delivery to the application."""

    observation: Observation
    received_at: datetime

    def __post_init__(self) -> None:
        require_aware(self.received_at, "received_at")
        if self.observation.observed_at > self.received_at:
            raise ValueError("An observation cannot be received before acquisition")


class ContextStatus(StrEnum):
    CURRENT = "current"
    UNAVAILABLE = "unavailable"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class ContextResponse:
    """An output request with the evidence used to select its wording."""

    status: ContextStatus
    text: str
    trigger: TouchObservation
    responded_at: datetime
    visual: VisualObservation | None = None

    @property
    def visual_age(self) -> timedelta | None:
        if self.visual is None:
            return None
        return self.responded_at - self.visual.observed_at
