"""CLI and composition root for the application.

Wire concrete inputs, outputs, and providers here as behaviors are implemented.
"""

import argparse
import asyncio
import json
import math
from datetime import timedelta
from importlib.metadata import version

from pragyantra.application.behavior import DescribeOnTouch
from pragyantra.application.models import ContextResponse
from pragyantra.application.runtime import AssistantRuntime
from pragyantra.inputs.simulated import visual_context_demo
from pragyantra.outputs.simulated import RecordingOutput


def _positive_duration(value: str) -> timedelta:
    try:
        seconds = float(value)
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError
        duration = timedelta(seconds=seconds)
        if duration <= timedelta(0):
            raise ValueError
        return duration
    except (ValueError, OverflowError) as exc:
        raise argparse.ArgumentTypeError(
            "Use a positive, finite duration in seconds"
        ) from exc


async def _demo(max_visual_age: timedelta) -> tuple[ContextResponse, ...]:
    source = visual_context_demo()
    output = RecordingOutput()
    runtime = AssistantRuntime(DescribeOnTouch(max_visual_age), now=source.now)
    await runtime.run(source, output)
    return output.responses


def _response_record(response: ContextResponse) -> dict[str, object]:
    visual = response.visual
    age = response.visual_age
    return {
        "status": response.status.value,
        "text": response.text,
        "responded_at": response.responded_at.isoformat(),
        "trigger": {
            "source": response.trigger.source,
            "observed_at": response.trigger.observed_at.isoformat(),
        },
        "visual": {
            "source": visual.source,
            "observed_at": visual.observed_at.isoformat(),
            "description": visual.description,
        }
        if visual is not None
        else None,
        "visual_age_seconds": age.total_seconds() if age is not None else None,
    }


def main() -> None:
    """Run explicit commands without initializing devices or model providers."""
    parser = argparse.ArgumentParser(
        prog="pragyantra",
        description="PragYantra: a modular foundation for an embodied assistant.",
        epilog=(
            "The demo uses simulated observations and records text responses. "
            "Real devices and model providers are not connected yet. "
            "The original prototype is archived in legacy/."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version('pragyantra')}"
    )
    commands = parser.add_subparsers(dest="command")
    demo = commands.add_parser(
        "demo", help="Replay the simulated visual-context behavior"
    )
    demo.add_argument(
        "--max-visual-age",
        type=_positive_duration,
        default=timedelta(seconds=5),
        metavar="SECONDS",
        help="Maximum usable age of a visual observation (default: 5 seconds)",
    )
    demo.add_argument(
        "--json", action="store_true", help="Print response evidence as JSON lines"
    )
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    try:
        responses = asyncio.run(_demo(args.max_visual_age))
    except KeyboardInterrupt:
        parser.exit(130, "Simulation interrupted.\n")
    for response in responses:
        if args.json:
            print(json.dumps(_response_record(response)))
        else:
            print(f"[{response.status.value}] {response.text}")
