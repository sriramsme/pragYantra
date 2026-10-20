"""Minimal current context, rather than a history or a claim of full awareness."""

from pragyantra.application.models import VisualObservation


class WorldState:
    """Keep the latest acquired visual observation, regardless of delivery order."""

    def __init__(self) -> None:
        self._visual: VisualObservation | None = None

    @property
    def visual(self) -> VisualObservation | None:
        return self._visual

    def observe(self, observation: VisualObservation) -> bool:
        """Return whether context changed; keep the first result on equal times."""
        if self._visual is not None:
            if observation.observed_at <= self._visual.observed_at:
                return False
        self._visual = observation
        return True
