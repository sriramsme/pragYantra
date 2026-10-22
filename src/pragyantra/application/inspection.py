"""Direct image judgments, kept separate from captions and physical measurements."""

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from typing import Protocol

from pragyantra.application.interfaces import ProviderError
from pragyantra.application.models import (
    ImageFrame,
    is_probability,
    require_aware,
)


class QuestionKind(StrEnum):
    PREDICATE = "predicate"
    CHOICE = "choice"
    SCORE = "score"


@dataclass(frozen=True, slots=True)
class InspectionQuestion:
    name: str
    instructions: str
    kind: QuestionKind = QuestionKind.PREDICATE
    options: tuple[tuple[str, str], ...] = ()
    version: str = "1"

    def __post_init__(self):
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", self.name):
            raise ValueError("Question name must be a short identifier")
        if not self.instructions.strip() or len(self.instructions) > 2000:
            raise ValueError("Question instructions require 1–2000 characters")
        if not isinstance(self.kind, QuestionKind):
            raise ValueError("Unknown inspection question kind")
        if not self.version.strip() or len(self.version) > 80:
            raise ValueError("Question version requires 1–80 characters")
        if self.kind == QuestionKind.PREDICATE:
            if self.options:
                raise ValueError("Predicates have no options")
        else:
            if not 2 <= len(self.options) <= 32:
                raise ValueError("Choice/score questions need 2–32 options")
            labels = []
            for label, description in self.options:
                if not label.strip() or len(label) > 80 or len(description) > 1000:
                    raise ValueError("Options need short labels and descriptions")
                labels.append(label)
            if len(set(labels)) != len(labels):
                raise ValueError("Option labels must be unique")


def validate_questions(questions: tuple[InspectionQuestion, ...]):
    if not 1 <= len(questions) <= 16:
        raise ValueError("Inspect 1–16 questions at a time")
    if not all(isinstance(q, InspectionQuestion) for q in questions):
        raise ValueError("Expected typed inspection questions")
    if len({q.name for q in questions}) != len(questions):
        raise ValueError("Question names must be unique")
    if (
        sum(
            len(q.instructions) + sum(len(a) + len(b) for a, b in q.options)
            for q in questions
        )
        > 32000
    ):
        raise ValueError("Inspection questions exceed the 32000-character budget")


@dataclass(frozen=True, slots=True)
class ImageJudgment:
    question: InspectionQuestion
    value: str | float | None = None
    probability: float | None = None
    confidence: float | None = None
    probabilities: tuple[tuple[str, float], ...] = ()
    refused: bool = False

    def __post_init__(self):
        if type(self.refused) is not bool:
            raise ValueError("Refusal must be explicit")
        if self.refused:
            if (
                any(
                    x is not None
                    for x in (self.value, self.probability, self.confidence)
                )
                or self.probabilities
            ):
                raise ValueError("Refusals cannot carry a judgment")
            return
        if self.question.kind == QuestionKind.PREDICATE:
            # A predicate is a probability, not a measured boolean fact.
            if (
                self.value is not None
                or self.confidence is not None
                or self.probabilities
                or not is_probability(self.probability)
            ):
                raise ValueError("Predicates require only their returned probability")
            return
        if self.probability is not None or not is_probability(self.confidence):
            raise ValueError("Choice/score judgments require returned confidence")
        labels = [label for label, _ in self.question.options]
        probs = dict(self.probabilities)
        if len(self.probabilities) != len(labels) or set(probs) != set(labels):
            raise ValueError("Judgment must cover every configured option exactly once")
        if not all(is_probability(p) for p in probs.values()) or not math.isclose(
            sum(probs.values()), 1, abs_tol=0.0001
        ):
            raise ValueError("Invalid judgment probability distribution")
        if self.question.kind == QuestionKind.CHOICE:
            if (
                type(self.value) is not str
                or self.value not in probs
                or probs[self.value] < max(probs.values())
            ):
                raise ValueError(
                    "Choice must be a configured maximum-probability option"
                )
        else:
            if type(self.value) not in (int, float) or not math.isfinite(self.value):
                raise ValueError("Score must be finite")
            expected = sum(i * probs[label] for i, label in enumerate(labels))
            if not math.isclose(self.value, expected, abs_tol=0.0001):
                raise ValueError("Score must match the returned ordered distribution")


@dataclass(frozen=True, slots=True)
class JudgmentBatch:
    judgments: tuple[ImageJudgment, ...]
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    image_detail: str | None = None

    def __post_init__(self):
        if not all(isinstance(j, ImageJudgment) for j in self.judgments):
            raise ValueError("Expected typed image judgments")
        validate_questions(tuple(j.question for j in self.judgments))
        if not all(
            isinstance(v, str) and v.strip() for v in (self.provider, self.model)
        ):
            raise ValueError("Judgment provenance is required")
        for usage in (self.input_tokens, self.output_tokens):
            if usage is not None and (type(usage) is not int or usage < 0):
                raise ValueError("Token usage must be nonnegative or unknown")
        if self.image_detail not in (None, "low", "high", "auto", "original"):
            raise ValueError("Unknown image detail")


class InspectionProvider(Protocol):
    async def evaluate(
        self, frame: ImageFrame, questions: tuple[InspectionQuestion, ...]
    ) -> JudgmentBatch: ...


@dataclass(frozen=True, slots=True)
class InspectionResult:
    evidence_id: str
    source: str
    acquired_at: datetime
    requested_at: datetime
    completed_at: datetime
    max_age: timedelta
    outcome: str
    questions: tuple[InspectionQuestion, ...]
    batch: JudgmentBatch | None = None

    def status_at(self, at: datetime) -> str:
        """Call when consuming a result; time spent after inference also counts."""
        require_aware(at, "inspection consumption time")
        if at < self.completed_at:
            raise ValueError("Cannot consume a result before it completed")
        if self.outcome != "completed":
            return self.outcome
        return "stale" if at - self.acquired_at > self.max_age else "completed"

    def to_record(self, *, at: datetime):
        from dataclasses import asdict

        return {
            "kind": "image_inspection",
            "status": self.status_at(at),
            "evidence": {
                "id": self.evidence_id,
                "source": self.source,
                "acquired_at": self.acquired_at.isoformat(),
            },
            "requested_at": self.requested_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "consumed_at": at.isoformat(),
            "max_age_seconds": self.max_age.total_seconds(),
            "questions": [asdict(q) for q in self.questions],
            "batch": asdict(self.batch) if self.batch else None,
        }


class ImageInspector:
    def __init__(
        self,
        provider: InspectionProvider,
        *,
        max_age=timedelta(seconds=5),
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        if max_age <= timedelta(0):
            raise ValueError("Inspection evidence age must be positive")
        self.provider, self.max_age, self._now = provider, max_age, now

    async def inspect(
        self, frame: ImageFrame, questions: tuple[InspectionQuestion, ...]
    ) -> InspectionResult:
        validate_questions(questions)
        if (
            frame.mime_type not in ("image/jpeg", "image/png", "image/webp")
            or len(frame.data) > 10 * 1024 * 1024
        ):
            raise ValueError("Inspection requires a PNG/JPEG/WebP of at most 10 MiB")
        started = self._now()
        require_aware(started, "inspection clock")
        if frame.observed_at > started:
            raise ValueError("Inspection evidence is from the future")
        outcome, batch = "stale", None
        if started - frame.observed_at <= self.max_age:
            try:
                batch = await self.provider.evaluate(frame, questions)
                if (
                    not isinstance(batch, JudgmentBatch)
                    or tuple(j.question for j in batch.judgments) != questions
                ):
                    raise ProviderError("Invalid inspection batch")
                outcome = "completed"
            except ProviderError:
                outcome, batch = "provider_failure", None
        completed = self._now()
        require_aware(completed, "inspection completion time")
        if completed < started:
            raise ValueError("Inspection clock moved backwards")
        return InspectionResult(
            "sha256:" + sha256(frame.data).hexdigest(),
            frame.source,
            frame.observed_at,
            started,
            completed,
            self.max_age,
            outcome,
            questions,
            batch,
        )
