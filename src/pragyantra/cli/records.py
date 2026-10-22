"""Shared JSON fields for CLI output."""

from pragyantra.application.models import TextObservation


def text_record(message: TextObservation) -> dict[str, object]:
    return {
        "source": message.source,
        "observed_at": message.observed_at.isoformat(),
        "text": message.text,
        "provider": message.provider,
        "model": message.model,
    }
