"""Exercise conversation and audio SDK contracts over an in-memory HTTP transport."""

import asyncio
import json
import struct
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx2
import pytest

from pragyantra.application.audio import AudioClip
from pragyantra.application.conversation import ConversationRequest
from pragyantra.application.interfaces import ProviderError
from pragyantra.application.memory import ChatMessage, MemoryNote
from pragyantra.application.models import TextObservation
from pragyantra.application.world_state import WorldState
from pragyantra.providers import openai_services as module

AT = datetime(2026, 10, 20, tzinfo=UTC)


def response(text="A blue mug is visible.", status="completed"):
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 0,
        "status": status,
        "model": "gpt-5.6-luna",
        "output": [
            {
                "type": "message",
                "id": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
    }


def audio():
    return AudioClip("synthetic", AT, struct.pack("<1600h", *([1000] * 1600)))


@asynccontextmanager
async def services(monkeypatch, handler, **settings):
    client_type = module.AsyncOpenAI
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    def factory(**kwargs):
        assert kwargs["max_retries"] == 0
        return client_type(
            **kwargs, http_client=http, base_url="https://api.openai.com/v1"
        )

    monkeypatch.setattr(module, "AsyncOpenAI", factory)
    try:
        async with module.openai_services(api_key="test-key", **settings) as instance:
            yield instance
    finally:
        assert http.is_closed


def request():
    return ConversationRequest(
        TextObservation("user", AT, "Whose mug is it?"),
        (ChatMessage("user", "Hello"), ChatMessage("assistant", "Hi")),
        WorldState().snapshot(at=AT),
        (MemoryNote(1, "The mug belongs to Alex", AT),),
    )


def test_conversation_context_history_and_memories_are_explicit_not_tools(monkeypatch):
    calls = []

    def handler(http_request):
        calls.append(json.loads(http_request.content))
        assert http_request.url.path == "/v1/responses"
        return httpx2.Response(200, json=response())

    async def scenario():
        async with services(monkeypatch, handler) as provider:
            return await provider.respond(request())

    result = asyncio.run(scenario())
    assert result.provider == "openai"
    body = calls[0]
    assert body["input"][0] == {"role": "user", "content": "Hello"}
    assert body["input"][-1]["content"] == "Whose mug is it?"
    evidence = json.loads(body["input"][-2]["content"].split("\n", 1)[1])
    assert evidence["memories"][0]["id"] == 1
    assert evidence["environment"]["visual"] is None
    assert body["store"] is False
    assert body["reasoning"]["effort"] == "none"
    assert "tools" not in body and "previous_response_id" not in body


def test_transcription_uses_wav_and_preserves_audio_acquisition_time(monkeypatch):
    clip = audio()

    def handler(http_request):
        assert http_request.url.path == "/v1/audio/transcriptions"
        assert b"RIFF" in http_request.content
        assert b"gpt-4o-mini-transcribe" in http_request.content
        return httpx2.Response(200, json={"text": "A blue mug."})

    async def scenario():
        async with services(monkeypatch, handler) as provider:
            return await provider.transcribe(clip)

    transcript = asyncio.run(scenario())
    assert transcript.text == "A blue mug."
    assert transcript.observed_at == clip.observed_at
    assert transcript.source == clip.source


def test_synthesis_returns_validated_pcm_audio(monkeypatch):
    def handler(http_request):
        body = json.loads(http_request.content)
        assert body["voice"] == "coral"
        assert body["response_format"] == "pcm"
        assert body["input"] == "Hello there."
        return httpx2.Response(
            200, content=audio().pcm, headers={"content-type": "audio/pcm"}
        )

    async def scenario():
        async with services(monkeypatch, handler) as provider:
            return await provider.synthesize("Hello there.")

    result = asyncio.run(scenario())
    assert result.pcm == audio().pcm
    assert result.source == "openai.speech"
    assert result.sample_rate == 24000


@pytest.mark.parametrize("method", ["respond", "transcribe", "synthesize"])
@pytest.mark.parametrize("code", [401, 429, 500])
def test_provider_errors_are_sanitized_and_not_retried(monkeypatch, method, code):
    calls = []

    def handler(http_request):
        calls.append(http_request)
        return httpx2.Response(code, json={"error": {"message": "secret-request-body"}})

    async def scenario():
        async with services(monkeypatch, handler) as provider:
            value = {
                "respond": request(),
                "transcribe": audio(),
                "synthesize": "Hello",
            }[method]
            with pytest.raises(ProviderError) as error:
                await getattr(provider, method)(value)
            assert "secret-request-body" not in str(error.value)

    asyncio.run(scenario())
    assert len(calls) == 1


def test_timeout_closes_the_client(monkeypatch):
    async def handler(http_request):
        await asyncio.Event().wait()

    async def scenario():
        async with services(monkeypatch, handler, timeout=0.02) as provider:
            with pytest.raises(ProviderError, match="timed out"):
                await provider.respond(request())

    asyncio.run(scenario())


@pytest.mark.parametrize("payload", [b"not audio", b""])
def test_invalid_speech_is_not_playable_audio(monkeypatch, payload):
    async def scenario():
        async with services(
            monkeypatch, lambda request: httpx2.Response(200, content=payload)
        ) as provider:
            with pytest.raises(ProviderError, match="invalid PCM"):
                await provider.synthesize("Hello")

    asyncio.run(scenario())


def test_embedding_uses_explicit_float_response_and_keeps_model(monkeypatch):
    def handler(http_request):
        assert http_request.url.path == "/v1/embeddings"
        body = json.loads(http_request.content)
        assert body == {
            "model": "text-embedding-3-small",
            "input": "blue mug",
            "encoding_format": "float",
        }
        return httpx2.Response(
            200,
            json={
                "object": "list",
                "model": "text-embedding-3-small",
                "data": [{"object": "embedding", "index": 0, "embedding": [3, 4]}],
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            },
        )

    async def scenario():
        async with services(monkeypatch, handler) as provider:
            return await provider.embed("blue mug")

    result = asyncio.run(scenario())
    assert result.values == (0.6, 0.8)
    assert result.model == "text-embedding-3-small"


def test_malformed_completed_conversation_is_provider_error(monkeypatch):
    payload = response()
    payload["output"] = None

    async def scenario():
        async with services(
            monkeypatch, lambda request: httpx2.Response(200, json=payload)
        ) as provider:
            with pytest.raises(ProviderError, match="invalid conversation"):
                await provider.respond(request())

    asyncio.run(scenario())


def test_saved_companion_context_is_distinct_from_current_evidence(monkeypatch):
    from dataclasses import replace

    from pragyantra.application.companion import CompanionEntry, ContextKind

    def handler(http_request):
        body = json.loads(http_request.content)
        record = json.loads(body["input"][-2]["content"].split("\n", 1)[1])
        assert record["companion"][0]["value"] == "Casey"
        assert record["companion"][1]["value"] == "A desk near a window"
        assert record["environment"]["visual"] is None
        assert "never current sensor facts" in body["instructions"]
        return httpx2.Response(200, json=response("Hi Casey."))

    async def scenario():
        async with services(monkeypatch, handler) as provider:
            await provider.respond(
                replace(
                    request(),
                    companion=(
                        CompanionEntry(ContextKind.NAME, "user", "Casey", AT),
                        CompanionEntry(
                            ContextKind.OBSERVATION, "desk", "A desk near a window", AT
                        ),
                    ),
                )
            )

    asyncio.run(scenario())
