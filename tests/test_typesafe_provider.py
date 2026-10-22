"""The real optional SDK over a mock transport; never a live TypeSafe request."""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx2
import pytest

from pragyantra.application.interfaces import ProviderError
from pragyantra.application.models import TextObservation
from pragyantra.application.requests import Intent
from pragyantra.providers import typesafe as module

sdk = pytest.importorskip("typesafe_sdk", reason="Run with --extra decisions")


def response(**changes):
    answer = {
        "type": "choice",
        "choice": "inspect",
        "confidence": 0.9,
        "probabilities": {
            item.value: 0.95 if item == Intent.INSPECT else 0.01 for item in Intent
        },
    }
    answer.update(changes)
    return {
        "model": "jev-1.14.0",
        "usage": {"input_tokens": 120},
        "answers": {"intent": answer},
    }


@asynccontextmanager
async def provider(monkeypatch, handler, **settings):
    original = sdk.AsyncTypeSafeClient
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    def factory(**kwargs):
        assert kwargs["retry"].max_retries == 0
        return original(**kwargs, http_client=http, base_url="https://api.typesafe.ai")

    monkeypatch.setattr(sdk, "AsyncTypeSafeClient", factory)
    try:
        async with module.typesafe_interpreter(
            api_key="test-key", **settings
        ) as client:
            yield client
    finally:
        assert http.is_closed


def message():
    return TextObservation("test", datetime.now(UTC), "What do you see?")


def test_sdk_payload_and_provenance(monkeypatch):
    def handler(request):
        assert request.url.path == "/v1/systemone"
        data = json.loads(request.content)
        assert data["model"] == "jev-1.14.0"
        assert data["state"] == {"request": "What do you see?"}
        question = data["questions"]["intent"]
        assert question["type"] == "choice" and set(question["criteria"]) == {
            item.value for item in Intent
        }
        assert "negation" in question["instructions"]
        return httpx2.Response(200, json=response())

    async def scenario():
        async with provider(monkeypatch, handler) as interpreter:
            return await interpreter.interpret(message())

    result = asyncio.run(scenario())
    assert result.intent == Intent.INSPECT and result.input_tokens == 120
    assert result.provider == "typesafe" and result.model == "jev-1.14.0"


@pytest.mark.parametrize("code", [400, 401, 403, 429, 500])
def test_http_failures_do_not_retry_or_expose_bodies(monkeypatch, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(code, json={"error": "private raw request body"})

    async def scenario():
        async with provider(monkeypatch, handler) as interpreter:
            with pytest.raises(ProviderError) as error:
                await interpreter.interpret(message())
            assert "private" not in str(error.value)

    asyncio.run(scenario())
    assert len(calls) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"choice": "arbitrary_action"},
        {"confidence": None},
        {"confidence": 2},
        {"probabilities": {"inspect": 1}},
        {"probabilities": {item.value: 0.01 for item in Intent}},
    ],
)
def test_invalid_results_never_reach_application_as_valid_intents(monkeypatch, changes):
    async def scenario():
        async with provider(
            monkeypatch, lambda req: httpx2.Response(200, json=response(**changes))
        ) as interpreter:
            with pytest.raises(ProviderError):
                await interpreter.interpret(message())

    asyncio.run(scenario())


def test_timeout_closes_client(monkeypatch):
    async def handler(request):
        await asyncio.Event().wait()

    async def scenario():
        async with provider(monkeypatch, handler, timeout=0.01) as interpreter:
            with pytest.raises(ProviderError, match="timed out"):
                await interpreter.interpret(message())

    asyncio.run(scenario())


def test_cancellation_propagates_and_closes_client(monkeypatch):
    async def scenario():
        started = asyncio.Event()

        async def handler(request):
            started.set()
            await asyncio.Event().wait()

        async def call():
            async with provider(monkeypatch, handler) as interpreter:
                await interpreter.interpret(message())

        task = asyncio.create_task(call())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "answers",
    [{}, {"intent": {"type": "refusal", "reason": "Unavailable"}}],
)
def test_missing_or_unrecognized_answers_fail_closed(monkeypatch, answers):
    payload = response()
    payload["answers"] = answers

    async def scenario():
        async with provider(
            monkeypatch, lambda req: httpx2.Response(200, json=payload)
        ) as interpreter:
            with pytest.raises(ProviderError):
                await interpreter.interpret(message())

    asyncio.run(scenario())
