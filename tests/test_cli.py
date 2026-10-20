"""Exercise the public demo command and argument validation as a user would."""

import json
import subprocess
import sys

import pytest


def test_demo_reports_response_evidence_as_json_lines():
    result = subprocess.run(
        [sys.executable, "-m", "pragyantra", "demo", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert [record["status"] for record in records] == [
        "unavailable",
        "current",
        "stale",
    ]
    assert records[0]["visual"] is None
    assert records[1]["visual"]["source"] == "simulated.camera"
    assert records[1]["visual_age_seconds"] == 2
    assert records[2]["visual_age_seconds"] == 7


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "1e-300", "1e300"])
def test_invalid_age_exits_with_argument_error(value):
    result = subprocess.run(
        [sys.executable, "-m", "pragyantra", "demo", "--max-visual-age", value],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "positive, finite duration" in result.stderr
