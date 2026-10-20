"""Validate and normalize local image data before any provider receives it."""

from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from PIL import Image

from pragyantra.inputs import image as image_input
from pragyantra.inputs.image import load_image


def test_image_keeps_known_capture_time_and_uses_content_type(image_path):
    renamed = image_path.with_suffix(".unknown")
    image_path.rename(renamed)
    captured = datetime(2026, 1, 1, tzinfo=UTC)
    frame = load_image(renamed, observed_at=captured)
    assert frame.observed_at == captured
    assert frame.source == "file:scene.unknown"
    assert frame.mime_type == "image/jpeg"
    with Image.open(BytesIO(frame.data)) as decoded:
        assert decoded.size == (80, 40)
        assert decoded.format == "JPEG"


def test_default_time_means_file_acquisition_not_mtime(image_path):
    before = datetime.now(UTC)
    frame = load_image(image_path)
    assert before <= frame.observed_at <= datetime.now(UTC)


def test_orientation_resize_and_metadata_removal(tmp_path):
    path = tmp_path / "large.jpg"
    original = Image.new("RGB", (1800, 900), "blue")
    exif = Image.Exif()
    exif[274] = 6  # Rotate 90 degrees clockwise for display.
    exif[270] = "Private image comment"
    original.save(path, exif=exif)
    frame = load_image(path)
    with Image.open(BytesIO(frame.data)) as decoded:
        assert decoded.size == (512, 1024)
        assert not decoded.getexif()


def test_transparency_is_composited_on_white(tmp_path):
    path = tmp_path / "transparent.png"
    Image.new("RGBA", (8, 8), (255, 0, 0, 0)).save(path)
    with Image.open(BytesIO(load_image(path).data)) as decoded:
        assert min(decoded.getpixel((4, 4))) > 245


@pytest.mark.parametrize("contents", [b"", b"not an image", b"\x89PNG\r\n\x1a\n"])
def test_invalid_images_are_rejected(tmp_path, contents):
    path = tmp_path / "bad.png"
    path.write_bytes(contents)
    with pytest.raises(ValueError, match="decoded"):
        load_image(path)


def test_file_size_and_pixel_limits_are_applied(image_path, monkeypatch):
    monkeypatch.setattr(image_input, "MAX_PIXELS", 100)
    with pytest.raises(ValueError, match="megapixel"):
        load_image(image_path)
    monkeypatch.setattr(image_input, "MAX_FILE_BYTES", 10)
    with pytest.raises(ValueError, match="MiB"):
        load_image(image_path)


def test_unsupported_and_animated_formats_are_rejected(tmp_path):
    path = tmp_path / "scene.bmp"
    Image.new("RGB", (8, 8)).save(path)
    with pytest.raises(ValueError, match="PNG, JPEG, or WebP"):
        load_image(path)
    path = tmp_path / "animated.png"
    first = Image.new("RGB", (8, 8), "red")
    first.save(path, save_all=True, append_images=[Image.new("RGB", (8, 8), "blue")])
    with pytest.raises(ValueError, match="Animated"):
        load_image(path)


def test_future_and_ambiguous_capture_times_are_rejected(image_path):
    with pytest.raises(ValueError, match="future"):
        load_image(image_path, observed_at=datetime.now(UTC) + timedelta(days=1))
    with pytest.raises(ValueError, match="timezone"):
        load_image(image_path, observed_at=datetime(2026, 1, 1))
