"""Read and normalize one local image, without knowing any model provider."""

import warnings
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from pragyantra.application.models import ImageFrame, require_aware

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_EDGE = 1024


def load_image(path: Path, *, observed_at: datetime | None = None) -> ImageFrame:
    """Validate PNG/JPEG/WebP and return an oriented, bounded JPEG without metadata.

    Without a supplied capture time, the timestamp means file acquisition for
    this pipeline. It does not establish when the photograph was originally taken.
    """
    acquired_at = datetime.now(UTC)
    timestamp = observed_at if observed_at is not None else acquired_at
    require_aware(timestamp, "image capture time")
    if timestamp > acquired_at:
        raise ValueError("Image capture time must not be in the future")
    if not path.is_file():
        raise ValueError(f"Image file not found: {path}")
    with path.open("rb") as image_file:
        data = image_file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Image file exceeds the 10 MiB input limit")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as original:
                if original.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ValueError("Use a PNG, JPEG, or WebP image")
                if getattr(original, "n_frames", 1) != 1:
                    raise ValueError("Animated images are not supported")
                if original.width * original.height > MAX_PIXELS:
                    raise ValueError("Image exceeds the 16-megapixel decode limit")
                original.load()
                image = ImageOps.exif_transpose(original)
                image.thumbnail((MAX_EDGE, MAX_EDGE))
                if "A" in image.getbands() or "transparency" in image.info:
                    rgba = image.convert("RGBA")
                    background = Image.new("RGBA", rgba.size, "white")
                    image = Image.alpha_composite(background, rgba)
                # A new image prevents EXIF/XMP/comment metadata being re-emitted.
                clean = Image.new("RGB", image.size)
                clean.paste(image.convert("RGB"))
                buffer = BytesIO()
                clean.save(buffer, format="JPEG", quality=85)
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as exc:
        raise ValueError("Image could not be decoded safely") from exc
    return ImageFrame(f"file:{path.name}", timestamp, buffer.getvalue())
