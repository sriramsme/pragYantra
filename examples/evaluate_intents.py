"""Evaluate curated request labels. Paid calls require the explicit --live flag."""

import argparse
import asyncio
import json
import math
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

from pragyantra.application.interfaces import ProviderError
from pragyantra.application.models import TextObservation
from pragyantra.application.requests import Intent, RequestStatus, select_behavior


def load_cases(path, limit):
    with path.open("rb") as source:
        data = source.read(262145)
    if len(data) > 262144:
        raise ValueError("Cases file exceeds 256 KiB")
    cases = json.loads(data)
    if not isinstance(cases, list) or not 1 <= len(cases) <= 100:
        raise ValueError("Supply between 1 and 100 labeled cases")
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"id", "text", "expected"}:
            raise ValueError("Each case needs id, text, expected")
        if (
            not isinstance(case["id"], str)
            or not case["id"].strip()
            or case["id"] in seen
        ):
            raise ValueError("Case IDs must be nonempty and unique")
        seen.add(case["id"])
        Intent(case["expected"])
        TextObservation("evaluation", datetime.now(UTC), case["text"])
    if not 1 <= limit <= 100:
        raise ValueError("Case limit must be between 1 and 100")
    return cases[:limit]


async def evaluate(cases, model, timeout):
    from pragyantra.providers.typesafe import typesafe_interpreter

    records = []
    async with typesafe_interpreter(model=model, timeout=timeout) as interpreter:
        for case in cases:
            started = time.perf_counter()
            record = {
                "id": case["id"],
                "expected": case["expected"],
                "text": case["text"],
            }
            try:
                judgment = await interpreter.interpret(
                    TextObservation("evaluation", datetime.now(UTC), case["text"])
                )
                record.update(
                    intent=judgment.intent.value,
                    confidence=judgment.confidence,
                    probabilities=dict(judgment.probabilities),
                    model=judgment.model,
                    question_version=judgment.question_version,
                    input_tokens=judgment.input_tokens,
                    status=select_behavior(judgment).value,
                )
            except ProviderError as error:
                record.update(intent=None, status="provider_failure", error=str(error))
            record["elapsed_seconds"] = round(time.perf_counter() - started, 6)
            records.append(record)
    elapsed = sorted(row["elapsed_seconds"] for row in records)
    return {
        "started_from": "synthetic text cases; no image/audio/device input",
        "recorded_at": datetime.now(UTC).isoformat(),
        "requested_model": model,
        "provider_failures": sum(
            row["status"] == "provider_failure" for row in records
        ),
        "cases": len(records),
        "correct_intents": sum(row["intent"] == row["expected"] for row in records),
        "accepted_route_errors": sum(
            row["status"] in (RequestStatus.CONVERSATION, RequestStatus.INSPECT)
            and row["intent"] != row["expected"]
            for row in records
        ),
        "clarifications": sum(
            row["status"] == RequestStatus.NEEDS_CLARIFICATION for row in records
        ),
        "median_seconds": statistics.median(elapsed),
        "p95_seconds_nearest_rank": elapsed[math.ceil(0.95 * len(elapsed)) - 1],
        "reported_input_tokens": sum(row.get("input_tokens") or 0 for row in records),
        "usage_missing_cases": sum(row.get("input_tokens") is None for row in records),
        "cost_usd": None,
        "records": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Send cases to TypeSafe; incurs API usage"
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "tests/fixtures/intent_requests.json",
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--model", default="jev-1.14.0")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--input-usd-per-million", type=float)
    args = parser.parse_args()
    try:
        rate = args.input_usd_per_million
        if rate is not None and (not math.isfinite(rate) or rate < 0):
            raise ValueError("Input token rate must be finite and nonnegative")
        cases = load_cases(args.cases, args.limit)
        if not args.live:
            print(
                f"Validated {len(cases)} cases. "
                "No API calls; pass --live to evaluate Jev."
            )
            return
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)
        report = asyncio.run(evaluate(cases, args.model, args.timeout))
        report["assumed_input_usd_per_million"] = rate
        report["estimated_usd_for_reported_input"] = (
            report["reported_input_tokens"] * rate / 1_000_000
            if rate is not None
            else None
        )
        print(json.dumps(report, indent=2))
    except (ValueError, OSError, ProviderError) as error:
        parser.exit(1, f"Evaluation failed: {error}\n")


if __name__ == "__main__":
    main()
