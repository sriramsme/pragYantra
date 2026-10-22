"""Evaluate direct image judgments on synthetic shapes; paid calls require --live."""

import argparse
import asyncio
import json
import math
import statistics
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

from pragyantra.application.inspection import (
    ImageInspector,
    InspectionQuestion,
    QuestionKind,
)
from pragyantra.application.interfaces import ProviderError
from pragyantra.inputs.image import frame_from_image

QUESTIONS = (
    InspectionQuestion("red_visible", "Is any clearly red shape visible in the image?"),
    InspectionQuestion(
        "station",
        "Which synthetic station marker best matches the image? "
        "Choose none if there is no red or blue shape.",
        QuestionKind.CHOICE,
        (
            ("red", "A red geometric shape on white"),
            ("blue", "A blue geometric shape on white"),
            ("none", "Neither, or unclear"),
        ),
    ),
    InspectionQuestion(
        "coverage",
        "How much of the image is occupied by a red shape?",
        QuestionKind.SCORE,
        (
            ("none", "No red pixels"),
            ("some", "Some red, less than half the image"),
            ("most", "Red occupies at least half the image"),
        ),
    ),
)


def load_cases(path):
    with path.open("rb") as source:
        raw = source.read(65537)
    if len(raw) > 65536:
        raise ValueError("Fixture exceeds 64 KiB")
    cases = json.loads(raw)
    if not isinstance(cases, list) or not 1 <= len(cases) <= 100:
        raise ValueError("Supply 1–100 cases")
    seen = set()
    for row in cases:
        if not isinstance(row, dict) or set(row) != {
            "id",
            "shape",
            "color",
            "size",
            "red_visible",
            "station",
        }:
            raise ValueError("Invalid fixture fields")
        if not isinstance(row["id"], str) or not row["id"].strip() or row["id"] in seen:
            raise ValueError("Case IDs must be unique")
        seen.add(row["id"])
        if (
            row["shape"] not in ("square", "circle")
            or row["color"] not in ("red", "blue", "gray", "white")
            or type(row["size"]) is not int
            or not 1 <= row["size"] <= 200
            or type(row["red_visible"]) is not bool
            or row["station"] not in ("red", "blue", "none")
        ):
            raise ValueError("Invalid fixture values")
    return cases


def make_frame(case):
    image = Image.new("RGB", (200, 200), "white")
    draw = ImageDraw.Draw(image)
    edge = (200 - case["size"]) // 2
    bounds = (edge, edge, edge + case["size"] - 1, edge + case["size"] - 1)
    if case["shape"] == "square":
        draw.rectangle(bounds, fill=case["color"])
    else:
        draw.ellipse(bounds, fill=case["color"])
    return frame_from_image(
        image, source="synthetic:" + case["id"], observed_at=datetime.now(UTC)
    )


def summary(records, input_rate=None, output_rate=None):
    elapsed = sorted(row["elapsed_seconds"] for row in records)
    pred = [row for row in records if row.get("prediction") is not None]
    inputs = sum(row.get("input_tokens") or 0 for row in records)
    outputs = sum(row.get("output_tokens") or 0 for row in records)
    return {
        "cases": len(records),
        "predicate_decided": len(pred),
        "false_positives": sum(
            row["prediction"] and not row["expected"]["red_visible"] for row in pred
        ),
        "false_negatives": sum(
            not row["prediction"] and row["expected"]["red_visible"] for row in pred
        ),
        "station_correct": sum(
            row.get("station") == row["expected"]["station"] for row in records
        ),
        "stale_results": sum(row["status"] == "stale" for row in records),
        "provider_failures": sum(
            row["status"] == "provider_failure" for row in records
        ),
        "refusals": sum(row.get("refusals", 0) for row in records),
        "median_seconds": statistics.median(elapsed),
        "p95_seconds_nearest_rank": elapsed[math.ceil(0.95 * len(elapsed)) - 1],
        "reported_input_tokens": inputs,
        "reported_output_tokens": outputs,
        "usage_missing_cases": sum(
            row.get("input_tokens") is None or row.get("output_tokens") is None
            for row in records
        ),
        "estimated_usd_for_reported_usage": None
        if input_rate is None or output_rate is None
        else (inputs * input_rate + outputs * output_rate) / 1_000_000,
        "assumed_usd_per_million": {"input": input_rate, "output": output_rate},
        "records": records,
    }


async def evaluate(cases, model, timeout):
    from pragyantra.providers.openai_decisions import openai_decisions

    records = []
    async with openai_decisions(model=model, timeout=timeout) as provider:
        inspector = ImageInspector(provider, max_age=timedelta(seconds=5))
        for case in cases:
            started = time.perf_counter()
            result = await inspector.inspect(make_frame(case), QUESTIONS)
            record = {
                "id": case["id"],
                "expected": {
                    "red_visible": case["red_visible"],
                    "station": case["station"],
                },
                "result": result.to_record(at=datetime.now(UTC)),
            }
            record["status"] = record["result"]["status"]
            if result.batch:
                record.update(
                    input_tokens=result.batch.input_tokens,
                    output_tokens=result.batch.output_tokens,
                    refusals=sum(j.refused for j in result.batch.judgments),
                )
                if record["status"] == "completed":
                    red, station, _ = result.batch.judgments
                    if not red.refused and (
                        red.probability >= 0.8 or red.probability <= 0.2
                    ):
                        record["prediction"] = red.probability >= 0.8
                    if (
                        not station.refused
                        and station.confidence >= 0.7
                        and dict(station.probabilities)[station.value] >= 0.75
                    ):
                        record["station"] = station.value
            record["elapsed_seconds"] = round(time.perf_counter() - started, 6)
            records.append(record)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "tests/fixtures/inspection_cases.json",
    )
    parser.add_argument("--model", default="gpt-6-luna")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--input-usd-per-million", type=float)
    parser.add_argument("--output-usd-per-million", type=float)
    args = parser.parse_args()
    try:
        for rate in (args.input_usd_per_million, args.output_usd_per_million):
            if rate is not None and (not math.isfinite(rate) or rate < 0):
                raise ValueError("Rates must be finite and nonnegative")
        cases = load_cases(args.cases)
        if not args.live:
            for case in cases:
                make_frame(case)
            print(
                f"Validated {len(cases)} synthetic image cases. "
                "No API calls; use --live."
            )
            return
        from dotenv import load_dotenv

        load_dotenv(Path.cwd() / ".env", override=False)
        records = asyncio.run(evaluate(cases, args.model, args.timeout))
        report = summary(
            records, args.input_usd_per_million, args.output_usd_per_million
        )
        report.update(
            recorded_at=datetime.now(UTC).isoformat(),
            requested_model=args.model,
            evidence="Synthetic shapes; no hardware or real station recognition",
            actual_billed_cost_usd=None,
        )
        print(json.dumps(report, indent=2))
    except (ValueError, OSError, ProviderError) as error:
        parser.exit(1, f"Evaluation failed: {error}\n")


if __name__ == "__main__":
    main()
