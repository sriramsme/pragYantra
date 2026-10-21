"""Bounded microphone capture; opens only for the listening part of a voice turn."""

import asyncio
import queue
import threading
import time
from datetime import UTC, datetime, timedelta

from pragyantra.application.audio import AudioClip
from pragyantra.inputs.vad import UtteranceSegmenter


def _sounddevice():
    try:
        import sounddevice

        return sounddevice
    except (ImportError, OSError) as exc:
        raise ValueError(
            "Audio devices require uv sync --extra audio and system PortAudio"
        ) from exc


def _record(
    stop: threading.Event, *, device=None, idle_timeout: float = 30, **vad_settings
) -> AudioClip:
    segmenter = UtteranceSegmenter(**vad_settings)
    sd = _sounddevice()
    pending: queue.Queue[tuple[datetime, bytes]] = queue.Queue(maxsize=64)
    overflow = threading.Event()

    def callback(data, frames, time_info, status):
        if status:
            overflow.set()
        observed_at = datetime.now(UTC) - timedelta(
            seconds=frames / segmenter.sample_rate
        )
        try:
            pending.put_nowait((observed_at, bytes(data)))
        except queue.Full:
            overflow.set()

    started = time.monotonic()
    stream = None
    try:
        stream = sd.RawInputStream(
            samplerate=segmenter.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=segmenter.block_frames,
            device=device,
            callback=callback,
        )
        stream.start()
        while not stop.is_set():
            if overflow.is_set():
                raise ValueError("Microphone overflow; audio was not transcribed")
            if time.monotonic() - started > idle_timeout:
                raise TimeoutError("No complete utterance before the listening timeout")
            try:
                acquired_at, pcm = pending.get(timeout=0.1)
            except queue.Empty:
                continue
            clip = segmenter.feed(
                pcm,
                at=acquired_at,
                source=f"microphone:{device if device is not None else 'default'}",
            )
            if clip is not None:
                return clip
    except sd.PortAudioError as exc:
        raise ValueError(
            "Microphone device failed; check device index, permissions and sample rate"
        ) from exc
    finally:
        if stream is not None:
            try:
                stream.abort()
            finally:
                stream.close()
    raise asyncio.CancelledError


async def record_microphone(
    *, device=None, idle_timeout: float = 30, **vad_settings
) -> AudioClip:
    if not 0 < idle_timeout <= 300:
        raise ValueError("Listening timeout must be 0–300 seconds")
    stop = threading.Event()
    task = asyncio.create_task(
        asyncio.to_thread(
            _record, stop, device=device, idle_timeout=idle_timeout, **vad_settings
        )
    )
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        stop.set()
        try:
            await task
        except (asyncio.CancelledError, ValueError, OSError):
            pass
        raise
