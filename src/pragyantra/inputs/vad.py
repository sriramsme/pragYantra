"""Configurable energy endpointing on fixed PCM16 blocks; no neural VAD claim."""

import math
import sys
from array import array
from collections import deque
from datetime import datetime

from pragyantra.application.audio import AudioClip
from pragyantra.application.models import require_aware


def rms_level(pcm: bytes) -> float:
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    return (
        math.sqrt(sum(sample * sample for sample in samples) / len(samples)) / 32768
        if samples
        else 0
    )


class UtteranceSegmenter:
    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        threshold: float = 0.015,
        silence_seconds: float = 0.7,
        min_speech_seconds: float = 0.12,
        pre_roll_seconds: float = 0.2,
        max_seconds: float = 15,
    ) -> None:
        if not 8000 <= sample_rate <= 48000 or not 0 < threshold < 1:
            raise ValueError("Invalid sample rate or energy threshold")
        if not all(
            math.isfinite(x) and x > 0
            for x in (silence_seconds, min_speech_seconds, max_seconds)
        ):
            raise ValueError("Speech timing must be positive and finite")
        if not 0 <= pre_roll_seconds <= 1 or not 1 <= max_seconds <= 60:
            raise ValueError(
                "Pre-roll must be 0–1 seconds; utterances must be 1–60 seconds"
            )
        if max(silence_seconds, min_speech_seconds) > max_seconds:
            raise ValueError("Speech/silence thresholds must fit the utterance limit")
        self.sample_rate = sample_rate
        self.block_frames = sample_rate // 50  # 20 ms at common supported rates.
        self._threshold = threshold
        self._quiet_limit = math.ceil(silence_seconds * sample_rate / self.block_frames)
        self._voice_limit = math.ceil(
            min_speech_seconds * sample_rate / self.block_frames
        )
        self._maximum = math.ceil(max_seconds * sample_rate / self.block_frames)
        pre_blocks = max(
            self._voice_limit,
            math.ceil(pre_roll_seconds * sample_rate / self.block_frames),
        )
        self._pre: deque[tuple[datetime, bytes]] = deque(maxlen=pre_blocks)
        self._blocks: list[tuple[datetime, bytes]] = []
        self._voiced = self._quiet = 0
        self._active = self._finished = False

    def feed(
        self, pcm: bytes, *, at: datetime, source: str = "microphone"
    ) -> AudioClip | None:
        require_aware(at, "audio block time")
        if self._finished:
            raise ValueError("Utterance segmenter is complete")
        if len(pcm) != self.block_frames * 2:
            raise ValueError("Microphone block has an unexpected size")
        voiced = rms_level(pcm) >= self._threshold
        if not self._active:
            self._pre.append((at, pcm))
            self._voiced = self._voiced + 1 if voiced else 0
            if self._voiced >= self._voice_limit:
                self._blocks.extend(self._pre)
                self._pre.clear()
                self._active = True
            return None
        self._blocks.append((at, pcm))
        self._quiet = 0 if voiced else self._quiet + 1
        if self._quiet >= self._quiet_limit or len(self._blocks) >= self._maximum:
            self._finished = True
            return AudioClip(
                source,
                self._blocks[0][0],
                b"".join(block for _, block in self._blocks),
                self.sample_rate,
            )
        return None
