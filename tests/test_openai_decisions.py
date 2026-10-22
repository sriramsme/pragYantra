"""Real Decisions SDK contract over mock HTTP; no credentials or network."""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx2
import pytest

from pragyantra.application.inspection import InspectionQuestion, QuestionKind
from pragyantra.application.interfaces import ProviderError
from pragyantra.application.models import ImageFrame
from pragyantra.providers import openai_decisions as module

QUESTIONS = (
    InspectionQuestion("visible", "Is a red shape visible?"),
    InspectionQuestion(
        "station",
        "Choose station",
        QuestionKind.CHOICE,
        (("red", "Red"), ("none", "Other")),
    ),
    InspectionQuestion(
        "coverage",
        "Red coverage",
        QuestionKind.SCORE,
        (("empty", "No red"), ("full", "All red")),
    ),
)
FRAME = ImageFrame("fixture", datetime(2026, 10, 21, tzinfo=UTC), b"synthetic pixels")


def response():
    return {
        "model": "gpt-6-luna",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
            "input_tokens_details": {"cache_write_tokens": 0, "cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
        "answers": [
            {"name": "visible", "type": "predicate", "probability": 0.9},
            {
                "name": "station",
                "type": "choice",
                "choice": "red",
                "confidence": 0.8,
                "probabilities": [
                    {"value": "red", "probability": 0.9},
                    {"value": "none", "probability": 0.1},
                ],
            },
            {
                "name": "coverage",
                "type": "score",
                "score": 0.9,
                "confidence": 0.8,
                "probabilities": [
                    {"label": "empty", "value": 0, "probability": 0.1},
                    {"label": "full", "value": 1, "probability": 0.9},
                ],
            },
        ],
    }


@asynccontextmanager
async def provider(monkeypatch, handler, **settings):
    original = module.AsyncOpenAI
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    def factory(**kwargs):
        assert kwargs["max_retries"] == 0
        return original(
            **kwargs, http_client=http, base_url="https://api.openai.com/v1"
        )

    monkeypatch.setattr(module, "AsyncOpenAI", factory)
    try:
        async with module.openai_decisions(api_key="test", **settings) as instance:
            yield instance
    finally:
        assert http.is_closed


def test_image_batch_payload_and_typed_provenance(monkeypatch):
    def handler(request):
        assert request.url.path == "/v1/decisions"
        body = json.loads(request.content)
        assert body["model"] == "gpt-6-luna"
        image = body["input"][0]["content"][1]
        assert image["image_url"].startswith("data:image/jpeg;base64,")
        assert image["detail"] == "low"
        assert [q["type"] for q in body["questions"]] == [
            "predicate",
            "choice",
            "score",
        ]
        assert body["questions"][1]["choices"][0]["value"] == "red"
        assert body["questions"][2]["levels"][0]["label"] == "empty"
        assert "tools" not in body and "store" not in body
        return httpx2.Response(200, json=response())

    async def scenario():
        async with provider(monkeypatch, handler) as instance:
            return await instance.evaluate(FRAME, QUESTIONS)

    batch = asyncio.run(scenario())
    assert batch.input_tokens == 100 and batch.output_tokens == 20
    assert batch.provider == "openai" and batch.model == "gpt-6-luna"
    assert batch.judgments[0].probability == 0.9
    assert batch.judgments[1].value == "red" and batch.judgments[2].value == 0.9


@pytest.mark.parametrize(
    "mutation",
    ["missing", "name", "type", "probability", "choice", "distribution", "index"],
)
def test_malformed_answers_fail_closed(monkeypatch, mutation):
    payload = response()
    if mutation == "missing":
        payload["answers"].pop()
    elif mutation == "name":
        payload["answers"][0]["name"] = "other"
    elif mutation == "type":
        payload["answers"][0]["type"] = "mystery"
    elif mutation == "probability":
        payload["answers"][0]["probability"] = 2
    elif mutation == "choice":
        payload["answers"][1]["choice"] = "invented"
    elif mutation == "distribution":
        payload["answers"][1]["probabilities"].pop()
    else:
        payload["answers"][2]["probabilities"][0]["value"] = -1

    async def scenario():
        async with provider(
            monkeypatch, lambda req: httpx2.Response(200, json=payload)
        ) as instance:
            with pytest.raises(ProviderError):
                await instance.evaluate(FRAME, QUESTIONS)

    asyncio.run(scenario())


def test_refusal_is_retained_without_inventing_a_probability(monkeypatch):
    payload = response()
    payload["answers"][0] = {"name": "visible", "type": "refusal"}

    async def scenario():
        async with provider(
            monkeypatch, lambda req: httpx2.Response(200, json=payload)
        ) as instance:
            return await instance.evaluate(FRAME, QUESTIONS)

    batch = asyncio.run(scenario())
    assert batch.judgments[0].refused and batch.judgments[0].probability is None
    assert not batch.judgments[1].refused


@pytest.mark.parametrize("code", [401, 403, 429, 500])
def test_http_failure_is_sanitized_and_not_retried(monkeypatch, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx2.Response(code, json={"error": {"message": "private details"}})

    async def scenario():
        async with provider(monkeypatch, handler) as instance:
            with pytest.raises(ProviderError) as error:
                await instance.evaluate(FRAME, QUESTIONS)
            assert "private" not in str(error.value)

    asyncio.run(scenario())
    assert len(calls) == 1


def test_timeout_releases_client(monkeypatch):
    async def scenario():
        entered = asyncio.Event()

        async def handler(request):
            entered.set()
            await asyncio.Event().wait()

        async with provider(monkeypatch, handler, timeout=0.01) as instance:
            with pytest.raises(ProviderError, match="timed out"):
                await instance.evaluate(FRAME, QUESTIONS)

    asyncio.run(scenario())


def test_cancellation_releases_client(monkeypatch):

    async def cancellation():
        entered = asyncio.Event()

        async def handler(request):
            entered.set()
            await asyncio.Event().wait()

        async def run():
            async with provider(monkeypatch, handler) as instance:
                await instance.evaluate(FRAME, QUESTIONS)

        task = asyncio.create_task(run())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancellation())
