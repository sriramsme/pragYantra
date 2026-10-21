"""WAV artifacts and cancellable PCM playback, separate from synthesis."""

import asyncio
import threading
from pathlib import Path

from pragyantra.application.audio import AudioClip
from pragyantra.application.interfaces import SpeechProvider


def save_audio(audio: AudioClip, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(audio.as_wav())


def _play(audio: AudioClip, stop: threading.Event, device=None) -> None:
    try:
        import sounddevice as sd
    except (ImportError, OSError) as exc:
        raise ValueError(
            "Playback requires uv sync --extra audio and system PortAudio"
        ) from exc
    stream = None
    try:
        stream = sd.RawOutputStream(
            samplerate=audio.sample_rate,
            channels=audio.channels,
            dtype="int16",
            device=device,
        )
        stream.start()
        stride = max(1, audio.sample_rate // 10) * audio.channels * 2
        for offset in range(0, len(audio.pcm), stride):
            if stop.is_set():
                stream.abort()
                return
            if stream.write(audio.pcm[offset : offset + stride]):
                raise ValueError("Audio playback underflow")
        stream.stop()
    except sd.PortAudioError as exc:
        raise ValueError(
            "Playback device failed; check the device and sample rate"
        ) from exc

    finally:
        if stream is not None:
            try:
                stream.abort()
            finally:
                stream.close()


async def play_audio(audio: AudioClip, *, device=None) -> None:
    stop = threading.Event()
    task = asyncio.create_task(asyncio.to_thread(_play, audio, stop, device))
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        stop.set()
        try:
            await task
        except (ValueError, OSError):
            pass
        raise


async def speak_text(text: str, provider: SpeechProvider, *, device=None) -> None:
    # Limit each synthesis request; split only at whitespace when possible.
    remaining = text.strip()
    while remaining:
        end = min(1000, len(remaining))
        if end < len(remaining):
            split = remaining.rfind(" ", 0, end)
            if split > 0:
                end = split
        chunk, remaining = remaining[:end], remaining[end:].lstrip()
        audio = await provider.synthesize(chunk)
        await play_audio(audio, device=device)
