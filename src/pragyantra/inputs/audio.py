"""Read bounded WAV files without contacting transcription services."""

from datetime import UTC, datetime
from pathlib import Path

from pragyantra.application.audio import MAX_AUDIO_BYTES, AudioClip
from pragyantra.application.models import require_aware


def load_audio(path: Path, *, observed_at: datetime | None = None) -> AudioClip:
    acquired = datetime.now(UTC)
    timestamp = observed_at if observed_at is not None else acquired
    require_aware(timestamp, "audio capture time")
    if timestamp > acquired:
        raise ValueError("Audio capture time must not be in the future")
    with path.open("rb") as audio:
        data = audio.read(MAX_AUDIO_BYTES + 1)
    return AudioClip.from_wav(data, source=f"file:{path.name}", observed_at=timestamp)
