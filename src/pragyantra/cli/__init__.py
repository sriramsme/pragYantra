"""CLI and composition root for the application.

Wire concrete inputs, outputs, and providers here as behaviors are implemented.
"""

import argparse
import asyncio
import json
import math
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from importlib.metadata import version
from pathlib import Path

from pragyantra.application.behavior import DescribeOnTouch
from pragyantra.application.interfaces import ProviderError
from pragyantra.application.models import (
    ContextResponse,
    require_aware,
)
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
    """Load invocation configuration before building defaults or opening resources."""
    from pragyantra.cli.environment import cli_environment

    name = Path(sys.argv[0]).stem
    prog = name if name in ("prag", "pragyantra") else "pragyantra"
    with cli_environment(sys.argv[1:], prog=prog) as argv:
        _run(argv, prog=prog)


def _run(argv: list[str], *, prog: str) -> None:
    from pragyantra.cli.parser import CLIParser

    parser = CLIParser(
        prog=prog,
        description="PragYantra — see, hear, converse and remember.",
        epilog=(
            f"Examples:\n"
            f"  {prog} chat                         Start a text conversation\n"
            f"  {prog} chat --voice --camera         Talk with visual context\n"
            f"  {prog} see photo.jpg                 Describe an image\n"
            f"  {prog} listen                        Transcribe your microphone\n"
            f"  {prog} speak 'Hello'                 Speak some text\n\n"
            "Reads .env from the current directory. Shell variables take precedence.\n"
            "Camera/audio uploads and hosted inference run only when requested."
        ),
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"%(prog)s {version('pragyantra')}"
    )
    commands = parser.add_subparsers(
        dest="command", title="Commands", metavar="COMMAND"
    )
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
        "--camera",
        "--webcam",
        dest="webcam",
        nargs="?",
        const=0,
        type=_camera_index,
        metavar="INDEX",
        help="Capture one camera frame (default index: 0)",
    )
    watch = commands.add_parser(
        "watch", help="Repeatedly describe webcam frames; sends images to OpenAI"
    )
    watch.add_argument(
        "--camera",
        "--webcam",
        dest="webcam",
        nargs="?",
        const=0,
        type=_camera_index,
        default=0,
        metavar="INDEX",
        help="Camera index (default: 0)",
    )
    watch.add_argument(
        "--interval",
        type=_positive_duration,
        default=timedelta(seconds=5),
        metavar="SECONDS",
        help="Wait after each completed result (default: 5 seconds)",
    )
    watch.add_argument(
        "-n",
        "--count",
        type=_positive_count,
        help="Stop after this many observations; otherwise run until Ctrl+C",
    )
    watch.add_argument(
        "--temporal-context",
        action="store_true",
        help="Experiment with one earlier description and acquisition-time gap",
    )
    watch.add_argument(
        "--context-max-gap",
        type=_positive_duration,
        metavar="SECONDS",
        help=(
            "Maximum frame-to-frame context gap; requires --temporal-context "
            "(default: 30 seconds)"
        ),
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
            "-j",
            "--json",
            action="store_true",
            help="Print structured output as JSON lines",
        )
    from pragyantra.cli.configure import add_commands, validate

    add_commands(
        commands,
        duration=_positive_duration,
        count=_positive_count,
        timestamp=_capture_time,
        camera_index=_camera_index,
    )
    args = parser.parse_args(argv)
    validate(args, parser)
    if args.command == "see":
        if (args.image is None) == (args.webcam is None):
            parser.error("see requires either an image file or --webcam INDEX")
        if args.webcam is not None and args.captured_at is not None:
            parser.error("--captured-at applies only to image files")
    if args.command == "watch":
        if args.context_max_gap is not None and not args.temporal_context:
            parser.error("--context-max-gap requires --temporal-context")
    if args.command is None:
        parser.print_help()
        return
    try:
        if args.command == "interpret":
            from pragyantra.cli.requests import interpret

            asyncio.run(interpret(args))
            return
        if args.command == "chat":
            from pragyantra.cli.assistant import run_assistant

            asyncio.run(run_assistant(args))
            return
        if args.command in ("listen", "speak"):
            from pragyantra.cli.audio import listen, speak

            asyncio.run(listen(args) if args.command == "listen" else speak(args))
            return
        if args.command == "devices":
            from pragyantra.cli.audio import devices

            devices()
            return
        if args.command == "memory":
            from pragyantra.cli.memory import run_memory

            run_memory(args)
            return
        if args.command == "calc":
            from pragyantra.application.actions import calculate

            print(calculate(args.expression))
            return
        if args.command == "watch":
            from pragyantra.cli.vision import watch

            asyncio.run(watch(args))
            return
        from pragyantra.cli.vision import see

        responses = asyncio.run(
            _demo(args.max_visual_age) if args.command == "demo" else see(args)
        )
    except KeyboardInterrupt:
        parser.exit(130, "Interrupted.\n")
    except sqlite3.Error as exc:
        parser.exit(1, f"Memory storage failed: {exc}\n")
    except (ProviderError, ValueError, OSError) as exc:
        parser.exit(1, f"PragYantra failed: {exc}\n")
    for response in responses:
        if args.json:
            print(json.dumps(_response_record(response)))
        else:
            print(f"[{response.status.value}] {response.text}")
