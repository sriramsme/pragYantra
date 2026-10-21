"""Latest sensory context, with acquisition ordering and bounded device channels."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from pragyantra.application.models import (
    SensorObservation,
    VisualObservation,
    require_aware,
)


@dataclass(frozen=True, slots=True)
class EnvironmentSnapshot:
    as_of: datetime
    max_age: timedelta
    visual: VisualObservation | None
    sensors: tuple[SensorObservation, ...]

    def to_record(self) -> dict[str, object]:
        def evidence(observation):
            age = (self.as_of - observation.observed_at).total_seconds()
            if age < 0:
                raise ValueError("Sensory context is ahead of the snapshot clock")
            return {
                "source": observation.source,
                "observed_at": observation.observed_at.isoformat(),
                "age_seconds": age,
                "status": "current" if age <= self.max_age.total_seconds() else "stale",
            }

        visual = None
        if self.visual is not None:
            visual = {
                **evidence(self.visual),
                "description": self.visual.description,
                "provider": self.visual.provider,
                "model": self.visual.model,
            }
        sensors = [
            {
                **evidence(reading),
                "kind": reading.kind,
                "value": reading.value,
                "unit": reading.unit,
            }
            for reading in self.sensors
        ]
        return {"as_of": self.as_of.isoformat(), "visual": visual, "sensors": sensors}


class WorldState:
    """Keep the newest acquisition per channel, not an inferred physical world."""

    def __init__(self, sensor_capacity: int = 32) -> None:
        if sensor_capacity <= 0:
            raise ValueError("Sensor capacity must be positive")
        self._visual: VisualObservation | None = None
        self._sensors: dict[tuple[str, str], SensorObservation] = {}
        self._sensor_capacity = sensor_capacity

    @property
    def visual(self) -> VisualObservation | None:
        return self._visual

    def observe(self, observation: VisualObservation | SensorObservation) -> bool:
        if isinstance(observation, SensorObservation):
            key = (observation.source, observation.kind)
            previous = self._sensors.get(key)
            if previous is not None and observation.observed_at <= previous.observed_at:
                return False
            if previous is None and len(self._sensors) >= self._sensor_capacity:
                raise ValueError("Sensor channel capacity reached")
            self._sensors[key] = observation
            return True
        if self._visual is not None:
            if observation.observed_at <= self._visual.observed_at:
                return False
        self._visual = observation
        return True

    def snapshot(
        self, *, at: datetime, max_age: timedelta = timedelta(seconds=5)
    ) -> EnvironmentSnapshot:
        require_aware(at, "snapshot time")
        if max_age <= timedelta(0):
            raise ValueError("Context maximum age must be positive")
        snapshot = EnvironmentSnapshot(
            at, max_age, self._visual, tuple(self._sensors.values())
        )
        snapshot.to_record()  # Reject future evidence before exposing it to a provider.
        return snapshot
