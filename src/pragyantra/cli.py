"""CLI and composition root for the application.

Wire concrete inputs, outputs, and providers here as behaviors are implemented.
"""

import argparse
import asyncio
import json
import math
import os
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path

from pragyantra.application.behavior import DescribeOnTouch
from pragyantra.application.interfaces import VisionError
from pragyantra.application.models import (
    ContextResponse,
    ObservationEvent,
    TouchObservation,
    VisualObservation,
    require_aware,
)
from pragyantra.application.runtime import AssistantRuntime
from pragyantra.inputs.simulated import SimulatedInput, visual_context_demo
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


def _capture_time(value: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value)
        require_aware(timestamp, "capture time")
        return timestamp
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Use an ISO 8601 timestamp including its timezone"
        ) from exc


def _camera_index(value: str) -> int:
    try:
        index = int(value)
        if index < 0:
            raise ValueError
        return index
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use a nonnegative webcam index") from exc


def _positive_count(value: str) -> int:
    try:
        count = int(value)
        if count <= 0:
            raise ValueError
        return count
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use a positive observation count") from exc


async def _see(args: argparse.Namespace) -> tuple[ContextResponse, ...]:
    # Keep image libraries and model SDKs out of demo/help startup.
    from pragyantra.application.perception import perceive_image
    from pragyantra.inputs.image import load_image
    from pragyantra.providers.openai import DEFAULT_MODEL, openai_vision

    if args.webcam is not None:
        from pragyantra.inputs.webcam import capture_webcam

        frame = await asyncio.to_thread(capture_webcam, args.webcam)
    else:
        frame = await asyncio.to_thread(
            load_image, args.image, observed_at=args.captured_at
        )
    async with openai_vision(
        model=args.model or DEFAULT_MODEL,
        timeout=args.timeout.total_seconds(),
        reasoning_effort=args.reasoning_effort,
        image_detail=args.image_detail,
    ) as provider:
        visual = await perceive_image(frame, provider)
        received_at = datetime.now(UTC)

    # Reuse the existing behavior with a clearly simulated touch. Crucially, the
    # runtime keeps its real clock; API latency is not reset or simulated away.
    touched_at = datetime.now(UTC)
    source = SimulatedInput(
        [
            ObservationEvent(visual, received_at),
            ObservationEvent(
                TouchObservation("simulated.touch", touched_at), touched_at
            ),
        ]
    )
    output = RecordingOutput()
    runtime = AssistantRuntime(DescribeOnTouch(args.max_visual_age))
    await runtime.run(source, output)
    return output.responses


async def _watch(args: argparse.Namespace) -> None:
    from pragyantra.application.observation_loop import VisualObservationLoop
    from pragyantra.inputs.webcam import WebcamStream
    from pragyantra.providers.openai import DEFAULT_MODEL, openai_vision

    observer = VisualObservationLoop(args.interval, count=args.count)
    async with (
        openai_vision(
            model=args.model or DEFAULT_MODEL,
            timeout=args.timeout.total_seconds(),
            reasoning_effort=args.reasoning_effort,
            image_detail=args.image_detail,
        ) as provider,
        WebcamStream(args.webcam) as source,
    ):
        async for event in observer.observations(source, provider):
            visual = event.observation
            assert isinstance(visual, VisualObservation)
            age = (event.received_at - visual.observed_at).total_seconds()
            if args.json:
                print(
                    json.dumps(
                        {
                            "kind": "visual_observation",
                            "source": visual.source,
                            "observed_at": visual.observed_at.isoformat(),
                            "received_at": event.received_at.isoformat(),
                            "visual_age_seconds": age,
                            "description": visual.description,
                            "provider": visual.provider,
                            "model": visual.model,
                            "image_detail": visual.image_detail,
                        }
                    ),
                    flush=True,
                )
            else:
                print(f"[age {age:.2f}s] {visual.description}", flush=True)


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
            "provider": visual.provider,
            "model": visual.model,
            "image_detail": visual.image_detail,
        }
        if visual is not None
        else None,
        "visual_age_seconds": age.total_seconds() if age is not None else None,
    }


def main() -> None:
    """Initialize providers only for commands that explicitly request them."""
    parser = argparse.ArgumentParser(
        prog="pragyantra",
        description="PragYantra: a modular foundation for an embodied assistant.",
        epilog=(
            "The demo uses simulated observations and records text responses. "
            "The see command sends a file or webcam image to OpenAI. "
            "The watch command repeats webcam vision requests. "
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
    see = commands.add_parser(
        "see", help="Describe a file or one webcam frame using OpenAI vision"
    )
    see.add_argument(
        "image", nargs="?", type=Path, help="PNG, JPEG, or WebP file to send"
    )
    see.add_argument(
        "--webcam",
        type=_camera_index,
        metavar="INDEX",
        help="Capture and send one webcam frame instead of a file (usually index 0)",
    )
    watch = commands.add_parser(
        "watch", help="Repeatedly describe webcam frames; sends images to OpenAI"
    )
    watch.add_argument(
        "--webcam",
        type=_camera_index,
        default=0,
        metavar="INDEX",
        help="Webcam index (default: 0)",
    )
    watch.add_argument(
        "--interval",
        type=_positive_duration,
        default=timedelta(seconds=5),
        metavar="SECONDS",
        help="Wait after each completed result (default: 5 seconds)",
    )
    watch.add_argument(
        "--count",
        type=_positive_count,
        help="Stop after this many observations; otherwise run until Ctrl+C",
    )
    for command in (see, watch):
        command.add_argument(
            "--model",
            default=os.getenv("PRAGYANTRA_VISION_MODEL"),
            help="Override the default gpt-5.6-luna vision model",
        )
        command.add_argument(
            "--image-detail",
            choices=["low", "high", "auto", "original"],
            default="low",
            help="Provider image detail for the normalized upload (default: low)",
        )
        command.add_argument(
            "--reasoning-effort",
            choices=["none", "low", "medium", "high", "xhigh", "max"],
            default="none",
            help="Reasoning effort supported by the selected model (default: none)",
        )
        command.add_argument(
            "--timeout",
            type=_positive_duration,
            default=timedelta(seconds=20),
            metavar="SECONDS",
            help="Vision request deadline, excluding acquisition (default: 20 seconds)",
        )
    see.add_argument(
        "--captured-at",
        type=_capture_time,
        help="Known image capture time; otherwise acquisition means file loading",
    )
    for command in (demo, see):
        command.add_argument(
            "--max-visual-age",
            type=_positive_duration,
            default=timedelta(seconds=5),
            metavar="SECONDS",
            help="Maximum usable image age (default: 5 seconds)",
        )
    for command in (demo, see, watch):
        command.add_argument(
            "--json", action="store_true", help="Print structured output as JSON lines"
        )
    args = parser.parse_args()
    if args.command == "see":
        if (args.image is None) == (args.webcam is None):
            parser.error("see requires either an image file or --webcam INDEX")
        if args.webcam is not None and args.captured_at is not None:
            parser.error("--captured-at applies only to image files")
    if args.command is None:
        parser.print_help()
        return
    try:
        if args.command == "watch":
            asyncio.run(_watch(args))
            return
        responses = asyncio.run(
            _demo(args.max_visual_age) if args.command == "demo" else _see(args)
        )
    except KeyboardInterrupt:
        parser.exit(130, "Interrupted.\n")
    except (VisionError, ValueError, OSError) as exc:
        parser.exit(1, f"Could not describe image: {exc}\n")
    for response in responses:
        if args.json:
            print(json.dumps(_response_record(response)))
        else:
            print(f"[{response.status.value}] {response.text}")
