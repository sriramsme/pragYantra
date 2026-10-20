"""Laptop/USB capture with one-shot and latest-frame streaming adapters."""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any, Self

from PIL import Image

from pragyantra.application.models import ImageFrame
from pragyantra.inputs.image import MAX_PIXELS, frame_from_image

# Raw pixels stay inside this adapter; application code only receives ImageFrame.
type _RawFrame = tuple[datetime, Any]


class _Webcam:
    """Blocking camera operations; the streaming adapter gives them one thread."""

    def __init__(self, index: int) -> None:
        if index < 0:
            raise ValueError("Webcam index must be nonnegative")
        self.index = index
        self._camera = None
        self._cv2 = None

    def open(self) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise ValueError(
                "Webcam support requires OpenCV; run uv sync --extra webcam"
            ) from exc
        self._cv2 = cv2
        try:
            self._camera = cv2.VideoCapture()
            if not self._camera.open(self.index) or not self._camera.isOpened():
                raise ValueError(
                    f"Could not open webcam {self.index}; check its index, device "
                    "access, permissions, and whether another application is using it"
                )
        except cv2.error as exc:
            raise ValueError(
                f"Webcam {self.index} capture failed; check the device"
            ) from exc

    def read_raw(self) -> _RawFrame:
        if self._camera is None or self._cv2 is None:
            raise ValueError("Webcam is not open")
        acquired_at = datetime.now(UTC)
        try:
            ok, pixels = self._camera.read()
        except self._cv2.error as exc:
            raise ValueError(
                f"Webcam {self.index} capture failed; check the device"
            ) from exc
        if not ok or pixels is None or pixels.size == 0:
            raise ValueError(f"Webcam {self.index} returned no image")
        if pixels.ndim != 3 or pixels.shape[2] != 3:
            raise ValueError("Webcam must provide a three-channel BGR image")
        if pixels.shape[0] * pixels.shape[1] > MAX_PIXELS:
            raise ValueError("Webcam frame exceeds the 16-megapixel decode limit")
        return acquired_at, pixels

    def normalize(self, raw: _RawFrame) -> ImageFrame:
        acquired_at, pixels = raw
        try:
            rgb = self._cv2.cvtColor(pixels, self._cv2.COLOR_BGR2RGB)
        except self._cv2.error as exc:
            raise ValueError("Webcam frame could not be converted to RGB") from exc
        return frame_from_image(
            Image.fromarray(rgb),
            source=f"webcam:{self.index}",
            observed_at=acquired_at,
        )

    def close(self) -> None:
        if self._camera is not None:
            try:
                self._camera.release()
            finally:
                self._camera = None


def capture_webcam(index: int = 0) -> ImageFrame:
    """Read one frame and release the camera, including on partial startup failure."""
    camera = _Webcam(index)
    try:
        camera.open()
        return camera.normalize(camera.read_raw())
    finally:
        camera.close()


class WebcamStream:
    """Keep only the latest pending raw frame while interpretation is busy.

    Open/read/release run on one dedicated worker. Only selected frames are JPEG
    encoded. Read-start timestamps are host times, not exposure timestamps; a
    driver may still buffer older frames. Shutdown waits for an active driver
    call before releasing the camera, so this is not a hard real-time adapter.
    """

    def __init__(self, index: int = 0) -> None:
        self._camera = _Webcam(index)
        self._worker: ThreadPoolExecutor | None = None
        self._producer: asyncio.Task[None] | None = None
        self._available = asyncio.Event()
        self._latest: _RawFrame | None = None
        self._error: Exception | None = None
        self._entered = False
        self._closed = True

    async def __aenter__(self) -> Self:
        if self._entered:
            raise ValueError("A webcam stream can only be entered once")
        self._entered = True
        self._worker = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="pragyantra-webcam"
        )
        try:
            await self._on_worker(self._camera.open)
        except BaseException:
            await self._shutdown()
            raise
        self._closed = False
        self._producer = asyncio.create_task(self._capture(), name="webcam-capture")
        return self

    async def _on_worker[T](self, operation: Callable[[], T]) -> T:
        if self._worker is None:
            raise ValueError("Webcam worker is not open")
        return await asyncio.get_running_loop().run_in_executor(self._worker, operation)

    async def _capture(self) -> None:
        try:
            while True:
                # Replacement, rather than a growing queue, bounds pending frames.
                self._latest = await self._on_worker(self._camera.read_raw)
                self._available.set()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._error = exc
            self._available.set()

    async def read(self) -> ImageFrame:
        """Consume a new latest frame; multiple simultaneous readers are unsupported."""
        if self._closed:
            raise ValueError("Webcam stream is not open")
        await self._available.wait()
        if self._closed:
            raise ValueError("Webcam stream is closed")
        if self._error is not None:
            raise self._error
        raw = self._latest
        self._latest = None
        self._available.clear()
        # No device operations occur in normalization, so capture can keep draining
        # on its own worker while this selected frame is processed.
        return await asyncio.to_thread(self._camera.normalize, raw)

    async def _shutdown(self) -> None:
        self._closed = True
        self._available.set()
        if self._producer is not None:
            self._producer.cancel()
            with suppress(asyncio.CancelledError):
                await self._producer
        if self._worker is not None:
            try:
                # Queued behind any active read: never race release against it.
                await self._on_worker(self._camera.close)
            finally:
                await asyncio.to_thread(self._worker.shutdown, wait=True)
                self._worker = None
        self._latest = None

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self._shutdown()
