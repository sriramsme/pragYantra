"""Startup wiring for image inspection and continuous webcam observation."""

import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta

from pragyantra.application.behavior import DescribeOnTouch
from pragyantra.application.models import (
    ContextResponse,
    ObservationEvent,
    PreviousSceneContext,
    TouchObservation,
    VisualObservation,
)
from pragyantra.application.runtime import AssistantRuntime
from pragyantra.inputs.simulated import SimulatedInput
from pragyantra.outputs.simulated import RecordingOutput


async def see(args: argparse.Namespace) -> tuple[ContextResponse, ...]:
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


def _previous_context_record(
    previous: PreviousSceneContext | None,
) -> dict[str, object] | None:
    if previous is None:
        return None
    return {
        "source": previous.source,
        "observed_at": previous.observed_at.isoformat(),
        "description": previous.description,
        "gap_seconds": previous.gap.total_seconds(),
        "provider": previous.provider,
        "model": previous.model,
    }


async def watch(args: argparse.Namespace) -> None:
    from pragyantra.application.observation_loop import VisualObservationLoop
    from pragyantra.inputs.webcam import WebcamStream
    from pragyantra.providers.openai import DEFAULT_MODEL, openai_vision

    observer = VisualObservationLoop(
        args.interval,
        count=args.count,
        temporal_context=args.temporal_context,
        context_max_gap=args.context_max_gap or timedelta(seconds=30),
    )
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
                            "previous_context": _previous_context_record(
                                visual.previous_context
                            ),
                        }
                    ),
                    flush=True,
                )
            else:
                print(f"[age {age:.2f}s] {visual.description}", flush=True)
