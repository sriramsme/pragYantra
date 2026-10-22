"""Presentation and startup for bounded request interpretation."""

import json
from datetime import UTC, datetime

from pragyantra.application.models import TextObservation
from pragyantra.application.requests import (
    IntentJudgment,
    RequestResult,
    select_behavior,
)
from pragyantra.cli.records import text_record


def judgment_record(judgment: IntentJudgment | None):
    if judgment is None:
        return None
    return {
        "intent": judgment.intent.value,
        "probabilities": dict(judgment.probabilities),
        "confidence": judgment.confidence,
        "provider": judgment.provider,
        "model": judgment.model,
        "question_version": judgment.question_version,
        "input_tokens": judgment.input_tokens,
    }


def request_record(result: RequestResult):
    return {
        "kind": "request_result",
        "status": result.status.value,
        "text": result.text,
        "input": text_record(result.message),
        "responded_at": result.responded_at.isoformat(),
        "judged_at": result.judged_at.isoformat() if result.judged_at else None,
        "judgment": judgment_record(result.judgment),
        "environment": result.environment.to_record() if result.environment else None,
        "scene_status": result.scene_status.value if result.scene_status else None,
    }


async def interpret(args):
    from pragyantra.providers.typesafe import typesafe_interpreter

    message = TextObservation("console.argument", datetime.now(UTC), args.text)
    async with typesafe_interpreter(
        model=args.decision_model, timeout=args.timeout.total_seconds()
    ) as provider:
        judgment = await provider.interpret(message)
    status = select_behavior(judgment)
    if args.json:
        print(
            json.dumps(
                {
                    "kind": "intent_judgment",
                    "status": status.value,
                    "judgment": judgment_record(judgment),
                }
            )
        )
    else:
        print(
            f"{judgment.intent.value} [{status.value}; "
            f"confidence {judgment.confidence:.3f}]"
        )
