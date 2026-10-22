"""Bounded request judgments and the small set of behaviors we can handle."""

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from pragyantra.application.conversation import ConversationResult, ConversationSession
from pragyantra.application.interfaces import ProviderError
from pragyantra.application.models import ContextStatus, TextObservation, require_aware
from pragyantra.application.world_state import EnvironmentSnapshot

QUESTION_VERSION = "intent-v1"


class Intent(StrEnum):
    CONVERSATION = "conversation"
    INSPECT = "inspect"
    FOLLOW = "follow"
    RUN_NAMED_MISSION = "run_named_mission"
    REMEMBER = "remember"
    UNKNOWN = "unknown"


class RequestStatus(StrEnum):
    CONVERSATION = "conversation"
    INSPECT = "inspect"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"
    PROVIDER_FAILURE = "provider_failure"
    STOPPED = "stopped"


def probability(value: float) -> bool:
    return type(value) in (int, float) and 0 <= value <= 1 and math.isfinite(value)


@dataclass(frozen=True, slots=True)
class IntentJudgment:
    intent: Intent
    probabilities: tuple[tuple[Intent, float], ...]
    confidence: float
    provider: str
    model: str
    input_tokens: int | None = None
    question_version: str = QUESTION_VERSION

    def __post_init__(self):
        if not isinstance(self.intent, Intent) or not probability(self.confidence):
            raise ValueError("Invalid intent or confidence")
        options = dict(self.probabilities)
        if len(self.probabilities) != len(Intent) or set(options) != set(Intent):
            raise ValueError(
                "Intent probabilities must cover every option exactly once"
            )
        if not all(
            isinstance(key, Intent) and probability(value)
            for key, value in self.probabilities
        ):
            raise ValueError("Invalid intent probabilities")
        if not math.isclose(sum(options.values()), 1, abs_tol=0.0001):
            raise ValueError("Intent probabilities must sum to one")
        if options[self.intent] < max(options.values()):
            raise ValueError("Selected intent must have the highest probability")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (self.provider, self.model, self.question_version)
        ):
            raise ValueError("Judgment provenance is required")
        if self.input_tokens is not None and (
            type(self.input_tokens) is not int or self.input_tokens < 0
        ):
            raise ValueError(
                "Input token usage must be a nonnegative integer or unknown"
            )


class RequestInterpreter(Protocol):
    async def interpret(self, message: TextObservation) -> IntentJudgment: ...


@dataclass(frozen=True, slots=True)
class RequestResult:
    message: TextObservation
    status: RequestStatus
    text: str
    responded_at: datetime
    judgment: IntentJudgment | None = None
    judged_at: datetime | None = None
    conversation: ConversationResult | None = None
    environment: EnvironmentSnapshot | None = None
    scene_status: ContextStatus | None = None


def select_behavior(
    judgment: IntentJudgment,
    *,
    min_confidence: float = 0.7,
    min_probability: float = 0.75,
) -> RequestStatus:
    if not probability(min_confidence) or not probability(min_probability):
        raise ValueError("Decision thresholds must be between zero and one")
    selected = dict(judgment.probabilities)[judgment.intent]
    if judgment.confidence < min_confidence or selected < min_probability:
        return RequestStatus.NEEDS_CLARIFICATION
    if judgment.intent == Intent.UNKNOWN:
        return RequestStatus.UNKNOWN
    if judgment.intent in (Intent.FOLLOW, Intent.RUN_NAMED_MISSION, Intent.REMEMBER):
        return RequestStatus.UNSUPPORTED
    return RequestStatus(judgment.intent.value)


class RequestRouter:
    def __init__(
        self,
        interpreter: RequestInterpreter,
        *,
        min_confidence: float = 0.7,
        min_probability: float = 0.75,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        if not probability(min_confidence) or not probability(min_probability):
            raise ValueError("Decision thresholds must be between zero and one")
        self.interpreter = interpreter
        self.min_confidence = min_confidence
        self.min_probability = min_probability
        self._now = now

    async def respond(
        self, message: TextObservation, session: ConversationSession
    ) -> RequestResult:
        started = self._now()
        require_aware(started, "interpretation clock")
        if message.observed_at > started:
            raise ValueError("Request is ahead of the interpretation clock")
        try:
            judgment = await self.interpreter.interpret(message)
            if not isinstance(judgment, IntentJudgment):
                raise ProviderError("Invalid request interpretation")
        except ProviderError:
            judgment = None
        at = self._now()
        require_aware(at, "interpretation completion time")
        if at < started:
            raise ValueError("Interpretation clock moved backwards")
        if judgment is None:
            return RequestResult(
                message,
                RequestStatus.PROVIDER_FAILURE,
                "I couldn't interpret that request. No behavior was selected.",
                at,
            )
        status = select_behavior(
            judgment,
            min_confidence=self.min_confidence,
            min_probability=self.min_probability,
        )
        if status == RequestStatus.CONVERSATION:
            conversation = await session.respond(message)
            return RequestResult(
                message,
                status,
                conversation.reply.text,
                conversation.responded_at,
                judgment,
                at,
                conversation=conversation,
            )
        environment = None
        scene_status = None
        if status == RequestStatus.INSPECT:
            # Snapshot after the judgment: its latency must count toward freshness.
            environment = session.state.snapshot(at=at, max_age=session.max_context_age)
            visual = environment.visual
            if visual is None:
                scene_status = ContextStatus.UNAVAILABLE
                text = "I don't have a visual observation yet."
            elif at - visual.observed_at > session.max_context_age:
                scene_status = ContextStatus.STALE
                text = "My last visual observation is too old to describe now."
            else:
                scene_status = ContextStatus.CURRENT
                text = f"The latest visual observation describes: {visual.description}"
        elif status == RequestStatus.NEEDS_CLARIFICATION:
            text = "I'm not sure what you want me to do. Please clarify your request."
        elif status == RequestStatus.UNKNOWN:
            text = (
                "I couldn't match that to one supported request. "
                "Please ask for one thing at a time."
            )
        else:
            text = (
                "That behavior isn't supported here. No action was requested. "
                "Use /remember TEXT to explicitly save a note."
                if judgment.intent == Intent.REMEMBER
                else "That behavior isn't supported here. No action was requested."
            )
        return RequestResult(
            message,
            status,
            text,
            at,
            judgment,
            at,
            environment=environment,
            scene_status=scene_status,
        )
