"""Offline evaluation setup and metrics; these never select a live provider."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def script_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"examples/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inspection_evaluation_default_has_no_api_calls(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "examples/evaluate_inspections.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Validated 8 synthetic image cases. No API calls" in result.stdout
    assert result.stderr == ""


def test_evaluation_counts_errors_missing_usage_stale_and_estimated_cost():
    module = script_module("evaluate_inspections")
    records = [
        {
            "status": "completed",
            "prediction": True,
            "expected": {"red_visible": False, "station": "red"},
            "station": "red",
            "input_tokens": 100,
            "output_tokens": 10,
            "elapsed_seconds": 1,
        },
        {
            "status": "completed",
            "prediction": False,
            "expected": {"red_visible": True, "station": "blue"},
            "station": "none",
            "input_tokens": 200,
            "output_tokens": 0,
            "elapsed_seconds": 2,
        },
        {
            "status": "stale",
            "expected": {"red_visible": True, "station": "red"},
            "elapsed_seconds": 3,
        },
        {
            "status": "provider_failure",
            "expected": {"red_visible": False, "station": "none"},
            "elapsed_seconds": 4,
        },
        {
            "status": "completed",
            "refusals": 1,
            "expected": {"red_visible": True, "station": "red"},
            "elapsed_seconds": 5,
        },
    ]
    report = module.summary(records, input_rate=2, output_rate=4)
    assert report["predicate_decided"] == 2
    assert report["false_positives"] == report["false_negatives"] == 1
    assert (
        report["station_correct"]
        == report["stale_results"]
        == report["provider_failures"]
        == report["refusals"]
        == 1
    )
    assert report["median_seconds"] == 3 and report["p95_seconds_nearest_rank"] == 5
    assert report["usage_missing_cases"] == 3
    assert report["estimated_usd_for_reported_usage"] == pytest.approx(0.00064)
    assert module.summary(records)["estimated_usd_for_reported_usage"] is None
