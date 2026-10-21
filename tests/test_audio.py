"""WAV boundary validation and deterministic endpointing on synthetic samples."""

import struct
from datetime import UTC, datetime, timedelta

import pytest

from pragyantra.application.audio import AudioClip
from pragyantra.inputs.audio import load_audio
from pragyantra.inputs.vad import UtteranceSegmenter, rms_level

AT = datetime(2026, 10, 20, tzinfo=UTC)


def block(level=0):
    return struct.pack("<320h", *([level] * 320))


def test_pcm_wav_roundtrip_and_file_acquisition(tmp_path):
    original = AudioClip("synthetic", AT, block(4000) * 50)
    decoded = AudioClip.from_wav(original.as_wav(), source="decoded", observed_at=AT)
    assert decoded.pcm == original.pcm
    assert decoded.duration == 1
    path = tmp_path / "sample.wav"
    path.write_bytes(original.as_wav())
    acquired = load_audio(path)
    assert acquired.source == "file:sample.wav"
    assert acquired.observed_at > AT
    with pytest.raises(ValueError, match="truncated|decoded"):
        AudioClip.from_wav(original.as_wav()[:-100], source="bad", observed_at=AT)
    with pytest.raises(ValueError, match="duration"):
        AudioClip.from_wav(
            original.as_wav(), source="long", observed_at=AT, max_seconds=0.5
        )


def test_endpointing_requires_sustained_energy_and_preserves_pre_roll():
    segmenter = UtteranceSegmenter(silence_seconds=0.1)
    index = 0
    result = None
    for level in [0] * 20 + [4000] * 15 + [0] * 5:
        result = segmenter.feed(block(level), at=AT + timedelta(seconds=index * 0.02))
        index += 1
    assert result is not None
    assert result.duration < 1
    assert AT < result.observed_at < AT + timedelta(seconds=0.4)
    assert rms_level(block(0)) == 0
    assert rms_level(block(32767)) > 0.99
    with pytest.raises(ValueError, match="complete"):
        segmenter.feed(block(), at=AT)


def test_noise_burst_does_not_complete_utterance_and_continuous_speech_is_bounded():
    segmenter = UtteranceSegmenter(max_seconds=1)
    for index in range(100):
        assert segmenter.feed(block(4000 if index % 2 else 0), at=AT) is None
    result = None
    for _index in range(100):
        result = segmenter.feed(block(4000), at=AT)
        if result:
            break
    assert result is not None
    assert result.duration <= 1.02


@pytest.mark.parametrize("data", [b"", b"not wav", b"RIFF\x00\x00"])
def test_invalid_wav_is_rejected(data):
    with pytest.raises(ValueError):
        AudioClip.from_wav(data, source="bad", observed_at=AT)


def test_naive_file_capture_time_and_unbounded_endpoint_settings_fail(tmp_path):
    from pragyantra.inputs.audio import load_audio
    from pragyantra.inputs.vad import UtteranceSegmenter

    with pytest.raises(ValueError, match="timezone"):
        load_audio(tmp_path / "not-opened.wav", observed_at=AT.replace(tzinfo=None))
    with pytest.raises(ValueError, match="utterance limit"):
        UtteranceSegmenter(min_speech_seconds=100000)
