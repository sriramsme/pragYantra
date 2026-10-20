"""Worker/lifecycle tests use fake devices; no OpenCV or physical capture needed."""

import asyncio
import threading
from datetime import UTC, datetime

import pytest

from pragyantra.application.models import ImageFrame
from pragyantra.inputs import webcam


class FakeCamera:
    def __init__(self, loop):
        self.loop = loop
        self.captured = asyncio.Queue()
        self.read_started = asyncio.Event()
        self.open_started = asyncio.Event()
        self.closed = False
        self.counter = 0
        self.device_threads = set()
        self.normalized = []
        self.open_error = None
        self.read_error = None
        self.read_gate = None
        self.open_gate = None

    def open(self):
        self.device_threads.add(threading.get_ident())
        self.loop.call_soon_threadsafe(self.open_started.set)
        if self.open_gate:
            self.open_gate.wait()
        if self.open_error:
            raise self.open_error

    def read_raw(self):
        self.device_threads.add(threading.get_ident())
        self.loop.call_soon_threadsafe(self.read_started.set)
        if self.read_gate:
            self.read_gate.wait()
        if self.read_error:
            raise self.read_error
        self.counter += 1
        self.loop.call_soon_threadsafe(self.captured.put_nowait, self.counter)
        return self.counter

    def normalize(self, raw):
        self.normalized.append(raw)
        return ImageFrame("fake.camera", datetime.now(UTC), str(raw).encode())

    def close(self):
        self.device_threads.add(threading.get_ident())
        self.closed = True

    async def until_captured(self, target):
        while await self.captured.get() < target:
            pass


def install_camera(monkeypatch):
    camera = FakeCamera(asyncio.get_running_loop())
    monkeypatch.setattr(webcam, "_Webcam", lambda index: camera)
    return camera


def test_latest_frame_replaces_pending_frames_and_only_selected_frames_are_encoded(
    monkeypatch,
):
    async def scenario():
        camera = install_camera(monkeypatch)
        source = webcam.WebcamStream()
        async with source:
            await camera.until_captured(10)
            assert camera.normalized == []
            frame = await source.read()
            # Read 10 was submitted only after frame 9 reached the latest slot.
            assert int(frame.data) >= 9
            assert len(camera.normalized) == 1
            next_frame = await source.read()
            assert int(next_frame.data) > int(frame.data)
        assert camera.closed
        assert len(camera.device_threads) == 1
        with pytest.raises(ValueError, match="not open"):
            await source.read()

    asyncio.run(scenario())


def test_capture_failure_reaches_consumer_and_releases_camera(monkeypatch):
    async def scenario():
        camera = install_camera(monkeypatch)
        camera.read_error = ValueError("camera disconnected")
        with pytest.raises(ValueError, match="camera disconnected"):
            async with webcam.WebcamStream() as source:
                await source.read()
        assert camera.closed
        assert camera.counter == 0
        assert len(camera.device_threads) == 1

    asyncio.run(scenario())


def test_partial_startup_failure_closes_worker_and_camera(monkeypatch):
    async def scenario():
        camera = install_camera(monkeypatch)
        camera.open_error = ValueError("camera unavailable")
        with pytest.raises(ValueError, match="camera unavailable"):
            async with webcam.WebcamStream():
                pytest.fail("startup must fail")
        assert camera.closed
        assert len(camera.device_threads) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["startup", "read"])
def test_cancellation_waits_for_driver_call_before_releasing(monkeypatch, stage):
    async def scenario():
        camera = install_camera(monkeypatch)
        gate = threading.Event()
        if stage == "startup":
            camera.open_gate = gate
            started = camera.open_started
        else:
            camera.read_gate = gate
            started = camera.read_started
        source = webcam.WebcamStream()
        shutting_down = asyncio.Event()
        shutdown = source._shutdown

        async def notify_shutdown():
            shutting_down.set()
            await shutdown()

        monkeypatch.setattr(source, "_shutdown", notify_shutdown)

        async def run():
            async with source:
                await source.read()

        task = asyncio.create_task(run())
        try:
            await asyncio.wait_for(started.wait(), timeout=2)
            task.cancel()
            await asyncio.wait_for(shutting_down.wait(), timeout=2)
            assert not camera.closed
        finally:
            gate.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
        assert camera.closed
        assert len(camera.device_threads) == 1

    asyncio.run(scenario())


def test_consumer_failure_stops_capture_and_closes_device(monkeypatch):
    async def scenario():
        camera = install_camera(monkeypatch)
        with pytest.raises(RuntimeError, match="output failed"):
            async with webcam.WebcamStream() as source:
                await source.read()
                raise RuntimeError("output failed")
        assert camera.closed
        counter = camera.counter
        assert source._producer.done()
        assert camera.counter == counter

    asyncio.run(scenario())
