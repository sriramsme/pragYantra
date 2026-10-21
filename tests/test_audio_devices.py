"""Fake PortAudio devices verify bounded capture and device lifecycle semantics."""

import asyncio
import struct
import sys
import threading
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from pragyantra.application.audio import AudioClip
from pragyantra.inputs import microphone
from pragyantra.outputs import audio as output


class DeviceError(Exception):
    pass


class Input:
    def __init__(self, callback, levels, *, fail=False):
        self.callback = callback
        self.levels = levels
        self.fail = fail
        self.closed = self.aborted = False
        self.started = threading.Event()

    def start(self):
        self.started.set()
        if self.fail:
            raise DeviceError("cannot start")
        for level in self.levels:
            self.callback(struct.pack("<320h", *([level] * 320)), 320, None, False)

    def abort(self):
        self.aborted = True

    def close(self):
        self.closed = True


def install_input(monkeypatch, levels, fail=False):
    streams = []

    def factory(**kwargs):
        stream = Input(kwargs["callback"], levels, fail=fail)
        streams.append(stream)
        return stream

    monkeypatch.setattr(
        microphone,
        "_sounddevice",
        lambda: SimpleNamespace(RawInputStream=factory, PortAudioError=DeviceError),
    )
    return streams


def test_microphone_closes_before_returning_utterance(monkeypatch):
    streams = install_input(monkeypatch, [0] * 5 + [4000] * 10 + [0] * 35)
    clip = asyncio.run(microphone.record_microphone())
    assert clip.duration > 0.7
    assert streams[0].closed and streams[0].aborted


def test_microphone_overflow_and_failed_start_close_stream(monkeypatch):
    streams = install_input(monkeypatch, [4000] * 65)
    with pytest.raises(ValueError, match="overflow"):
        asyncio.run(microphone.record_microphone())
    assert streams[0].closed
    streams = install_input(monkeypatch, [], fail=True)
    with pytest.raises(ValueError, match="device failed"):
        asyncio.run(microphone.record_microphone())
    assert streams[0].closed


def test_cancelling_listening_waits_for_stream_close(monkeypatch):
    streams = install_input(monkeypatch, [])

    async def scenario():
        task = asyncio.create_task(microphone.record_microphone())
        while not streams or not streams[0].started.is_set():
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
        assert streams[0].closed

    asyncio.run(scenario())


def test_playback_cancellation_closes_device(monkeypatch):
    started = threading.Event()
    release = threading.Event()

    class Playback:
        closed = False
        aborted = False

        def start(self):
            pass

        def write(self, data):
            started.set()
            release.wait()
            return False

        def stop(self):
            pass

        def abort(self):
            self.aborted = True

        def close(self):
            self.closed = True

    stream = Playback()
    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        SimpleNamespace(
            RawOutputStream=lambda **kwargs: stream, PortAudioError=DeviceError
        ),
    )
    clip = AudioClip("synthetic", datetime.now(UTC), b"\x00\x00" * 16000)

    async def scenario():
        task = asyncio.create_task(output.play_audio(clip))
        try:
            while not started.is_set():
                await asyncio.sleep(0)
            task.cancel()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
        assert stream.closed and stream.aborted

    asyncio.run(scenario())


def test_playback_failed_start_still_closes_device(monkeypatch):
    class Playback:
        closed = False

        def start(self):
            raise DeviceError("failed start")

        def abort(self):
            pass

        def close(self):
            self.closed = True

    stream = Playback()
    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        SimpleNamespace(
            RawOutputStream=lambda **kwargs: stream, PortAudioError=DeviceError
        ),
    )
    clip = AudioClip("synthetic", datetime.now(UTC), b"\x00\x00" * 320)
    with pytest.raises(ValueError, match="Playback device failed"):
        asyncio.run(output.play_audio(clip))
    assert stream.closed
