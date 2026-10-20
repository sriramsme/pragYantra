"""Synthetic OpenCV frames exercise capture handling without opening a device."""

from datetime import UTC, datetime
from io import BytesIO

import pytest
from PIL import Image

from pragyantra.inputs import webcam

cv2 = pytest.importorskip("cv2", reason="Run webcam tests with --extra webcam")
np = pytest.importorskip("numpy")


class FakeCamera:
    def __init__(self, pixels):
        self.pixels = pixels
        self.open_ok = True
        self.opened = True
        self.read_ok = True
        self.error = None
        self.released = False
        self.index = None
        self.read_started_at = None

    def open(self, index):
        self.index = index
        return self.open_ok

    def isOpened(self):
        return self.opened

    def read(self):
        self.read_started_at = datetime.now(UTC)
        if self.error:
            raise self.error
        return self.read_ok, self.pixels

    def release(self):
        self.released = True


@pytest.fixture
def camera(monkeypatch):
    pixels = np.zeros((900, 1800, 3), dtype=np.uint8)
    pixels[:, :] = (0, 0, 255)  # OpenCV BGR red, not RGB blue.
    device = FakeCamera(pixels)
    monkeypatch.setattr(cv2, "VideoCapture", lambda: device)
    return device


def test_capture_normalizes_color_size_source_and_time_and_releases(camera):
    before = datetime.now(UTC)
    frame = webcam.capture_webcam(2)
    assert camera.index == 2
    assert camera.released
    assert frame.source == "webcam:2"
    assert before <= frame.observed_at <= camera.read_started_at
    assert frame.mime_type == "image/jpeg"
    with Image.open(BytesIO(frame.data)) as decoded:
        assert decoded.size == (1024, 512)
        red, green, blue = decoded.getpixel((0, 0))
        assert red > 245 and green < 10 and blue < 10
        assert not decoded.getexif()


@pytest.mark.parametrize("failure", ["open", "closed", "read", "none", "empty"])
def test_failed_acquisition_releases_device(camera, failure):
    if failure == "open":
        camera.open_ok = False
    elif failure == "closed":
        camera.opened = False
    elif failure == "read":
        camera.read_ok = False
    elif failure == "none":
        camera.pixels = None
    else:
        camera.pixels = np.zeros((0, 0, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="Could not open|returned no image"):
        webcam.capture_webcam()
    assert camera.released


@pytest.mark.parametrize("failure", [cv2.error("driver error"), KeyboardInterrupt()])
def test_driver_error_or_interrupt_releases_device(camera, failure):
    camera.error = failure
    expected = ValueError if isinstance(failure, cv2.error) else KeyboardInterrupt
    with pytest.raises(expected):
        webcam.capture_webcam()
    assert camera.released


def test_oversized_frame_is_rejected_before_color_conversion(camera, monkeypatch):
    monkeypatch.setattr(webcam, "MAX_PIXELS", 100)
    with pytest.raises(ValueError, match="megapixel"):
        webcam.capture_webcam()
    assert camera.released


def test_normalization_error_releases_device(camera, monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("normalization failed")

    monkeypatch.setattr(webcam, "frame_from_image", fail)
    with pytest.raises(ValueError, match="normalization failed"):
        webcam.capture_webcam()
    assert camera.released


def test_backend_initialization_error_is_actionable(monkeypatch):
    def fail():
        raise cv2.error("backend initialization failed")

    monkeypatch.setattr(cv2, "VideoCapture", fail)
    with pytest.raises(ValueError, match="capture failed; check the device"):
        webcam.capture_webcam()
