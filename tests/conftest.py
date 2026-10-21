"""Small generated image fixtures; no personal images or model downloads."""

import pytest
from PIL import Image


@pytest.fixture
def image_path(tmp_path):
    path = tmp_path / "scene.png"
    Image.new("RGB", (80, 40), "red").save(path)
    return path


@pytest.fixture(autouse=True)
def no_live_io(monkeypatch):
    """Unexpected hardware/network use fails before acquisition or paid requests."""
    import socket
    import sys
    from types import SimpleNamespace

    def blocked(*args, **kwargs):
        pytest.fail("Normal tests must use fake devices and HTTP transports")

    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        SimpleNamespace(
            RawInputStream=blocked,
            RawOutputStream=blocked,
            query_devices=blocked,
            PortAudioError=RuntimeError,
        ),
    )
    if "cv2" in sys.modules:
        monkeypatch.setattr(sys.modules["cv2"], "VideoCapture", blocked)
