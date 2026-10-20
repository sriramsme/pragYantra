"""Deterministic behavior for requesting current visual context via touch."""

from datetime import datetime, timedelta

from pragyantra.application.models import (
    ContextResponse,
    ContextStatus,
    TouchObservation,
    require_aware,
)
from pragyantra.application.world_state import WorldState


class DescribeOnTouch:
    def __init__(self, max_visual_age: timedelta = timedelta(seconds=5)) -> None:
        if max_visual_age <= timedelta(0):
            raise ValueError("max_visual_age must be positive")
        self.max_visual_age = max_visual_age

    def respond(
        self, state: WorldState, touch: TouchObservation, *, at: datetime
    ) -> ContextResponse:
        """Evaluate freshness at response time, including any processing delay."""
        require_aware(at, "response time")
        if touch.observed_at > at:
            raise ValueError("Cannot respond before the touch occurred")
        visual = state.visual
        if visual is None:
            status = ContextStatus.UNAVAILABLE
            text = "I don't have a visual observation yet."
        else:
            age = at - visual.observed_at
            if age < timedelta(0):
                raise ValueError("Visual observation is ahead of the response clock")
            if age > self.max_visual_age:
                status = ContextStatus.STALE
                text = "My last visual observation is too old to describe now."
            else:
                status = ContextStatus.CURRENT
                text = f"The latest visual observation describes: {visual.description}"
        return ContextResponse(status, text, touch, at, visual)
