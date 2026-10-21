"""Strict hardware-event parsing rejects ambiguous or malformed evidence."""

import json
from datetime import UTC, datetime

import pytest

from pragyantra.inputs.events import parse_event


def event():
    return {
        "version": 1,
        "type": "sensor",
        "source": "mcu",
        "observed_at": datetime.now(UTC).isoformat(),
        "kind": "temperature",
        "value": 23.5,
        "unit": "degC",
    }


@pytest.mark.parametrize(
    "change",
    [
        {"version": True},
        {"version": 2},
        {"value": True},
        {"value": float("nan")},
        {"observed_at": "2026-10-20T12:00:00"},
        {"unit": ""},
        {"unit": "degC" + " " * 20},
        {"value": 10**1000},
        {"source": ""},
        {"surprise": "extra"},
        {"kind": 42},
    ],
)
def test_invalid_device_evidence_fails(change):
    data = event() | change
    with pytest.raises(ValueError):
        parse_event(json.dumps(data))


def test_valid_scalar_keeps_unit_source_and_acquisition_time():
    data = event()
    observation = parse_event(json.dumps(data))
    assert observation.unit == "degC"
    assert observation.value == 23.5
    assert observation.source == "mcu"
    assert observation.observed_at.isoformat() == data["observed_at"]
