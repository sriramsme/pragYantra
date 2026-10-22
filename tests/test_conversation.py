"""Integrated context, bounded history, explicit actions, and failure atomicity."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from pragyantra.application.conversation import ConversationSession, GeneratedReply
from pragyantra.application.models import (
    SensorObservation,
    TextObservation,
    VisualObservation,
)

NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)


class Provider:
    def __init__(self):
        self.requests = []
        self.fail = False

    async def respond(self, request):
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("provider failed")
        return GeneratedReply("Based on the supplied context.", "fake", "test")


def message(text):
    return TextObservation("test.user", NOW, text)


def test_context_memory_and_prior_conversation_reach_provider():
    async def scenario():
        provider = Provider()
        session = ConversationSession(provider, now=lambda: NOW)
        session.state.observe(
            VisualObservation("camera", NOW - timedelta(seconds=7), "A red mug.")
        )
        session.state.observe(
            SensorObservation("mcu", NOW, "temperature", 24.5, "degC")
        )
        await session.respond(message("/remember The red mug belongs to Alex"))
        first = await session.respond(message("Whose mug is it?"))
        assert first.memories[0].id == 1
        request = provider.requests[0]
        evidence = request.environment.to_record()
        assert evidence["visual"]["status"] == "stale"
        assert evidence["sensors"][0]["status"] == "current"
        assert evidence["sensors"][0]["unit"] == "degC"
        assert len(request.history) == 2
        await session.respond(message("And what is its color?"))
        assert len(provider.requests[-1].history) == 4
        assert provider.requests[-1].history[-1].role == "assistant"

    asyncio.run(scenario())


def test_commands_never_call_model_and_notes_can_be_forgotten():
    async def scenario():
        provider = Provider()
        session = ConversationSession(provider, now=lambda: NOW)
        await session.respond(message("/remember A blue door"))
        assert (
            "blue door" in (await session.respond(message("/recall door"))).reply.text
        )
        await session.respond(message("/forget 1"))
        assert (
            await session.respond(message("/recall door"))
        ).reply.text == "No matching memories."
        assert provider.requests == []

    asyncio.run(scenario())


def test_failed_generation_does_not_commit_history_and_turn_bound_is_enforced():
    async def scenario():
        provider = Provider()
        session = ConversationSession(provider, now=lambda: NOW, max_turns=2)
        for text in ("first", "second", "third"):
            await session.respond(message(text))
        assert [entry.text for entry in session.history.messages[::2]] == [
            "second",
            "third",
        ]
        before = session.history.messages
        provider.fail = True
        with pytest.raises(RuntimeError):
            await session.respond(message("not committed"))
        assert session.history.messages == before

    asyncio.run(scenario())


def test_sensor_order_capacity_and_nonfinite_values():
    from pragyantra.application.world_state import WorldState

    state = WorldState(sensor_capacity=1)
    state.observe(SensorObservation("mcu", NOW, "temperature", 24, "degC"))
    assert not state.observe(
        SensorObservation("mcu", NOW - timedelta(seconds=1), "temperature", 10, "degC")
    )
    assert state.snapshot(at=NOW).to_record()["sensors"][0]["value"] == 24
    with pytest.raises(ValueError, match="capacity"):
        state.observe(SensorObservation("mcu", NOW, "force", 3, "N"))
    for value in (True, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="finite"):
            SensorObservation("mcu", NOW, "temperature", value, "degC")


def test_semantic_session_remembers_and_recalls_without_keyword_overlap():
    from pragyantra.application.memory import TextEmbedding

    class Embeddings:
        def __init__(self):
            self.inputs = []
            self.fail = False

        async def embed(self, text):
            self.inputs.append(text)
            if self.fail:
                raise RuntimeError("embedding failed")
            return TextEmbedding("fake", (1, 0))

    async def scenario():
        provider, embeddings = Provider(), Embeddings()
        session = ConversationSession(provider, now=lambda: NOW, embeddings=embeddings)
        await session.respond(message("/remember The ceramic vessel is blue"))
        result = await session.respond(message("Where is my mug?"))
        assert result.memories[0].text == "The ceramic vessel is blue"
        assert embeddings.inputs == ["The ceramic vessel is blue", "Where is my mug?"]
        embeddings.fail = True
        before = session.history.messages
        with pytest.raises(RuntimeError):
            await session.respond(message("/remember Should not be stored"))
        assert session.history.messages == before
        assert len(session.notes.search("")) == 1

    asyncio.run(scenario())
