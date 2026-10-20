"""Small generated image fixtures; no personal images or model downloads."""

import pytest
from PIL import Image


@pytest.fixture
def image_path(tmp_path):
    path = tmp_path / "scene.png"
    Image.new("RGB", (80, 40), "red").save(path)
    return path
