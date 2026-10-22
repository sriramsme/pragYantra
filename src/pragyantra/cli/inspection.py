"""Compose direct image judgments over a file or one explicitly selected camera."""

import asyncio
import json
from datetime import UTC, datetime

from pragyantra.application.inspection import (
    ImageInspector,
    InspectionQuestion,
    validate_questions,
)
from pragyantra.application.interfaces import ProviderError
from pragyantra.inputs.inspection import load_questions


async def inspect_image(args):
    from pragyantra.inputs.image import load_image
    from pragyantra.providers.openai_decisions import openai_decisions

    questions = tuple(
        InspectionQuestion(f"condition_{i}", text)
        for i, text in enumerate(args.condition, start=1)
    )
    if args.questions is not None:
        questions += load_questions(args.questions)
    validate_questions(questions)
    # Check questions and provider configuration before opening a device.
    async with openai_decisions(
        model=args.model,
        timeout=args.timeout.total_seconds(),
        image_detail=args.image_detail,
    ) as provider:
        if args.camera is not None:
            from pragyantra.inputs.webcam import capture_webcam

            frame = await asyncio.to_thread(capture_webcam, args.camera)
        else:
            frame = await asyncio.to_thread(
                load_image, args.image, observed_at=args.captured_at
            )
        result = await ImageInspector(provider, max_age=args.max_age).inspect(
            frame, questions
        )
    record = result.to_record(at=datetime.now(UTC))
    if args.json:
        print(json.dumps(record))
    elif record["status"] != "completed":
        print(f"Inspection {record['status']}; no usable judgment.")
    else:
        for judgment in result.batch.judgments:
            value = (
                "refused"
                if judgment.refused
                else f"probability {judgment.probability:.3f}"
                if judgment.probability is not None
                else f"{judgment.value} (confidence {judgment.confidence:.3f})"
            )
            print(f"{judgment.question.name}: {value}")
    if record["status"] == "provider_failure":
        raise ProviderError("Image inspection failed; no usable judgment")
