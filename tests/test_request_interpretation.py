"""Application policy over fake judgments; these are not model accuracy tests."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from pragyantra.application.conversation import ConversationSession, GeneratedReply
from pragyantra.application.interfaces import ProviderError
from pragyantra.application.models import TextObservation, VisualObservation
from pragyantra.application.requests import (
    Intent,
    IntentJudgment,
    RequestRouter,
    RequestStatus,
    select_behavior,
)
from pragyantra.application.runner import AssistantRunner

AT = datetime(2026, 10, 21, tzinfo=UTC)


def judgment(intent=Intent.INSPECT, confidence=0.9, selected=0.95):
    return IntentJudgment(
        intent,
        tuple(
            (item, selected if item == intent else (1 - selected) / 5)
            for item in Intent
        ),
        confidence,
        "fake",
        "test",
    )


class Interpreter:
    def __init__(self, result=None, failure=False):
        self.result = result or judgment()
        self.failure = failure
        self.calls = []

    async def interpret(self, message):
        self.calls.append(message)
        if self.failure:
            raise ProviderError("private provider details")
        return self.result


class Conversation:
    def __init__(self):
        self.calls = []

    async def respond(self, request):
        self.calls.append(request)
        return GeneratedReply("Hello", "fake", "chat")


@pytest.mark.parametrize(
    "intent,expected",
    [
        (Intent.CONVERSATION, RequestStatus.CONVERSATION),
        (Intent.INSPECT, RequestStatus.INSPECT),
        (Intent.FOLLOW, RequestStatus.UNSUPPORTED),
        (Intent.RUN_NAMED_MISSION, RequestStatus.UNSUPPORTED),
        (Intent.REMEMBER, RequestStatus.UNSUPPORTED),
        (Intent.UNKNOWN, RequestStatus.UNKNOWN),
    ],
)
def test_known_intents_cannot_bypass_application_capabilities(intent, expected):
    assert select_behavior(judgment(intent)) == expected


def test_uncertainty_checks_confidence_and_probability_separately():
    assert (
        select_behavior(judgment(confidence=0.4)) == RequestStatus.NEEDS_CLARIFICATION
    )
    assert select_behavior(judgment(selected=0.5)) == RequestStatus.NEEDS_CLARIFICATION
    assert (
        select_behavior(judgment(selected=0.75, confidence=0.7))
        == RequestStatus.INSPECT
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"confidence": float("nan")},
        {"confidence": True},
        {"intent": "follow"},
        {"probabilities": ()},
        {"model": ""},
        {"input_tokens": -1},
        {"probabilities": tuple((item, 1) for item in Intent)},
    ],
)
def test_malformed_judgments_are_rejected(changes):
    original = judgment()
    from dataclasses import replace

    with pytest.raises(ValueError):
        replace(original, **changes)


@pytest.mark.parametrize(
    "age,delay,status",
    [(0, 0, "current"), (5, 0, "current"), (5, 1, "stale"), (None, 0, "unavailable")],
)
def test_inspection_uses_post_judgment_freshness_without_generation(age, delay, status):
    async def scenario():
        clock = [AT]
        chat = Conversation()
        session = ConversationSession(chat, now=lambda: clock[0])
        if age is not None:
            session.state.observe(
                VisualObservation("camera", AT - timedelta(seconds=age), "A blue mug.")
            )

        class Slow(Interpreter):
            async def interpret(self, message):
                clock[0] += timedelta(seconds=delay)
                return await super().interpret(message)

        router = RequestRouter(Slow(), now=lambda: clock[0])
        result = await router.respond(
            TextObservation("user", AT, "Look around"), session
        )
        assert result.status == RequestStatus.INSPECT
        assert result.scene_status.value == status
        assert result.environment.as_of == clock[0]
        assert chat.calls == [] and session.history.messages == ()
        assert result.judgment.model == "test"
        if status != "current":
            assert "blue mug" not in result.text

    asyncio.run(scenario())


def test_conversation_preserves_normal_history_and_failed_judgment_does_not_fall_back():
    async def scenario():
        chat = Conversation()
        session = ConversationSession(chat, now=lambda: AT)
        interpreter = Interpreter(judgment(Intent.CONVERSATION))
        router = RequestRouter(interpreter, now=lambda: AT)
        result = await router.respond(TextObservation("user", AT, "Hello"), session)
        assert result.conversation.reply.text == "Hello"
        before = session.history.messages
        interpreter.failure = True
        result = await router.respond(TextObservation("user", AT, "Follow me"), session)
        assert result.status == RequestStatus.PROVIDER_FAILURE
        assert result.judgment is None and result.conversation is None
        assert "private" not in result.text
        assert len(chat.calls) == 1 and session.history.messages == before

    asyncio.run(scenario())


def test_explicit_commands_and_stop_bypass_judgment_and_stop_closes_stream():
    async def scenario():
        interpreter, chat, results, events = Interpreter(), Conversation(), [], []
        session = ConversationSession(chat, now=lambda: AT)
        runner = AssistantRunner(
            session, router=RequestRouter(interpreter, now=lambda: AT), now=lambda: AT
        )

        async def inputs():
            try:
                for text in (
                    "/remember A blue mug",
                    "/context",
                    "/stop",
                    "never consumed",
                ):
                    events.append(text)
                    yield TextObservation("user", AT, text)
            finally:
                events.append("closed")

        async def output(result):
            results.append(result)

        await runner.run(inputs(), on_result=output)
        assert interpreter.calls == [] and chat.calls == []
        assert results[-1].status == RequestStatus.STOPPED
        assert events == ["/remember A blue mug", "/context", "/stop", "closed"]
        assert len(session.notes.search("mug")) == 1

    asyncio.run(scenario())


def test_cancellation_during_judgment_propagates_without_a_result():
    async def scenario():
        entered = asyncio.Event()

        class Blocking:
            async def interpret(self, message):
                entered.set()
                await asyncio.Event().wait()

        session = ConversationSession(Conversation(), now=lambda: AT)
        router = RequestRouter(Blocking(), now=lambda: AT)
        task = asyncio.create_task(
            router.respond(TextObservation("user", AT, "Look around"), session)
        )
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert session.history.messages == ()

    asyncio.run(scenario())
