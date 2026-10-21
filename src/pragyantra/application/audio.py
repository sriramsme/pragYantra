"""Bounded PCM16 audio values and lossless WAV serialization, without device I/O."""

import wave
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO

from pragyantra.application.models import require_aware

MAX_AUDIO_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class AudioClip:
    source: str
    observed_at: datetime
    pcm: bytes = field(repr=False)
    sample_rate: int = 16000
    channels: int = 1

    def __post_init__(self) -> None:
        require_aware(self.observed_at, "audio acquisition time")
        if not self.source.strip():
            raise ValueError("Audio source is required")
        if self.channels not in (1, 2) or not 8000 <= self.sample_rate <= 48000:
            raise ValueError("Audio requires mono/stereo at 8000–48000 Hz")
        if (
            not self.pcm
            or len(self.pcm) > MAX_AUDIO_BYTES
            or len(self.pcm) % (2 * self.channels)
        ):
            raise ValueError("Audio must contain bounded, complete PCM16 frames")
        if self.duration > 300:
            raise ValueError("Audio duration exceeds five minutes")

    @property
    def duration(self) -> float:
        return len(self.pcm) / (2 * self.channels * self.sample_rate)

    def as_wav(self) -> bytes:
        buffer = BytesIO()
        with wave.open(buffer, "wb") as audio:
            audio.setnchannels(self.channels)
            audio.setsampwidth(2)
            audio.setframerate(self.sample_rate)
            audio.writeframes(self.pcm)
        return buffer.getvalue()

    @classmethod
    def from_wav(
        cls, data: bytes, *, source: str, observed_at: datetime, max_seconds: float = 60
    ) -> "AudioClip":
        if len(data) > MAX_AUDIO_BYTES:
            raise ValueError("WAV exceeds the 20 MiB input limit")
        try:
            with wave.open(BytesIO(data), "rb") as audio:
                if audio.getcomptype() != "NONE" or audio.getsampwidth() != 2:
                    raise ValueError("Use an uncompressed 16-bit PCM WAV")
                rate, channels, frames = (
                    audio.getframerate(),
                    audio.getnchannels(),
                    audio.getnframes(),
                )
                if channels not in (1, 2) or not 8000 <= rate <= 48000:
                    raise ValueError("WAV requires mono/stereo at 8000–48000 Hz")
                if frames <= 0 or frames / rate > max_seconds:
                    raise ValueError(
                        f"WAV duration must be within (0, {max_seconds:g}] seconds"
                    )
                pcm = audio.readframes(frames)
                if len(pcm) != frames * channels * 2:
                    raise ValueError("WAV audio data is truncated")
        except (wave.Error, EOFError) as exc:
            raise ValueError("WAV could not be decoded") from exc
        return cls(source, observed_at, pcm, rate, channels)
