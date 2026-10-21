"""Versioned JSON-line boundary for external text, touch, and scalar sensors."""

import json
from datetime import datetime

from pragyantra.application.models import (
    SensorObservation,
    TextObservation,
    TouchObservation,
)


def parse_event(line: str):
    if len(line.encode("utf-8")) > 16384:
        raise ValueError("Device event exceeds 16 KiB")
    try:
        data = json.loads(line)
        if (
            not isinstance(data, dict)
            or type(data.get("version")) is not int
            or data["version"] != 1
        ):
            raise ValueError("Device events require version 1 objects")
        kind = data["type"]
        fields = {"version", "type", "source", "observed_at"}
        if kind == "sensor":
            fields |= {"kind", "value", "unit"}
        elif kind == "text":
            fields |= {"text"}
        elif kind != "touch":
            raise ValueError("Supported event types: sensor, text, touch")
        if set(data) != fields:
            raise ValueError("Device event has missing or unexpected fields")
        observed_at = datetime.fromisoformat(data["observed_at"])
        source = data["source"]
        if not isinstance(source, str) or not 1 <= len(source) <= 80:
            raise ValueError("Device source requires 1–80 characters")
        if kind == "sensor":
            if not isinstance(data["kind"], str) or not isinstance(data["unit"], str):
                raise ValueError("Sensor kind/unit must be text")
            return SensorObservation(
                source, observed_at, data["kind"], data["value"], data["unit"]
            )
        if kind == "text":
            if not isinstance(data["text"], str):
                raise ValueError("Text event requires text")
            return TextObservation(source, observed_at, data["text"])
        return TouchObservation(source, observed_at)
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid device event") from exc
