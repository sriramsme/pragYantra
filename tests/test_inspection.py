"""Image judgments are evidence-bound values, not captions or device readings."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from pragyantra.application.inspection import (
    ImageInspector,
    ImageJudgment,
    InspectionQuestion,
    JudgmentBatch,
    QuestionKind,
)
from pragyantra.application.interfaces import ProviderError
from pragyantra.application.models import ImageFrame

AT = datetime(2026, 10, 21, tzinfo=UTC)
Q = InspectionQuestion("visible", "Is a red shape visible?")


class Provider:
    def __init__(self, clock, delay=0, fail=False):
        self.clock, self.delay, self.fail, self.calls = clock, delay, fail, 0

    async def evaluate(self, frame, questions):
        self.calls += 1
        self.clock[0] += timedelta(seconds=self.delay)
        if self.fail:
            raise ProviderError("private details")
        return JudgmentBatch(
            tuple(ImageJudgment(q, probability=0.9) for q in questions),
            "fake",
            "test",
            10,
            2,
        )


@pytest.mark.parametrize(
    "age,delay,status,calls",
    [
        (6, 0, "stale", 0),
        (5, 0, "completed", 1),
        (4, 2, "stale", 1),
        (0, 0, "completed", 1),
    ],
)
def test_acquisition_delay_and_consumption_freshness(age, delay, status, calls):
    async def scenario():
        clock = [AT]
        provider = Provider(clock, delay)
        inspector = ImageInspector(provider, now=lambda: clock[0])
        frame = ImageFrame("fixture", AT - timedelta(seconds=age), b"synthetic")
        result = await inspector.inspect(frame, (Q,))
        assert result.status_at(clock[0]) == status and provider.calls == calls
        record = result.to_record(at=clock[0])
        assert record["evidence"]["acquired_at"] == frame.observed_at.isoformat()
        assert record["evidence"]["id"].startswith("sha256:")
        clock[0] += timedelta(seconds=6)
        assert result.status_at(clock[0]) == "stale"
        if result.batch:
            assert result.batch.judgments[0].probability == 0.9
            assert result.batch.judgments[0].value is None

    asyncio.run(scenario())


def test_future_evidence_and_failures():
    async def scenario():
        clock = [AT]
        provider = Provider(clock, fail=True)
        inspector = ImageInspector(provider, now=lambda: clock[0])
        with pytest.raises(ValueError, match="future"):
            await inspector.inspect(
                ImageFrame("test", AT + timedelta(seconds=1), b"x"), (Q,)
            )
        assert provider.calls == 0
        result = await inspector.inspect(ImageFrame("test", AT, b"x"), (Q,))
        assert result.outcome == "provider_failure" and result.batch is None
        with pytest.raises(ValueError, match="before"):
            result.status_at(AT - timedelta(seconds=1))

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "changes",
    [
        {"probability": float("nan")},
        {"probability": True},
        {"probability": -1},
        {"confidence": 0.9},
        {"value": True},
        {"refused": True, "probability": 0.9},
    ],
)
def test_predicates_cannot_invent_booleans_confidence_or_refusal_values(changes):
    with pytest.raises(ValueError):
        replace(ImageJudgment(Q, probability=0.9), **changes)


def test_choice_and_score_validation():
    choice = InspectionQuestion(
        "station",
        "Which station?",
        QuestionKind.CHOICE,
        (("desk", "Desk"), ("none", "Other")),
    )
    valid = ImageJudgment(
        choice,
        value="desk",
        confidence=0.9,
        probabilities=(("desk", 0.9), ("none", 0.1)),
    )
    for changes in (
        {"value": "invented"},
        {"value": "none"},
        {"probabilities": (("desk", 1),)},
        {"confidence": None},
    ):
        with pytest.raises(ValueError):
            replace(valid, **changes)
    score = replace(choice, kind=QuestionKind.SCORE)
    ImageJudgment(score, value=0.1, confidence=0.8, probabilities=valid.probabilities)
    with pytest.raises(ValueError, match="distribution"):
        ImageJudgment(
            score, value=0.9, confidence=0.8, probabilities=valid.probabilities
        )
    assert ImageJudgment(Q, refused=True).probability is None


def test_cancellation_is_not_a_failed_judgment():
    async def scenario():
        entered = asyncio.Event()

        class Blocking:
            async def evaluate(self, frame, questions):
                entered.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(
            ImageInspector(Blocking(), now=lambda: AT).inspect(
                ImageFrame("fixture", AT, b"x"), (Q,)
            )
        )
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
