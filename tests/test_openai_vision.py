"""Exercise the real SDK over an in-memory HTTP transport; never call OpenAI."""

import asyncio
import base64
import json
from contextlib import asynccontextmanager
from io import BytesIO

import httpx2
import pytest
from PIL import Image

from pragyantra.application.interfaces import VisionError
from pragyantra.application.perception import perceive_image
from pragyantra.inputs.image import load_image
from pragyantra.providers import openai as provider_module
from pragyantra.providers.openai import openai_vision


def response_body(
    *, status="completed", text="A red rectangular image.", refusal=False
):
    content = (
        {"type": "refusal", "refusal": "Cannot describe this image."}
        if refusal
        else {"type": "output_text", "text": text, "annotations": []}
    )
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 0,
        "status": status,
        "model": "gpt-5.6-luna-test",
        "output": [
            {
                "type": "message",
                "id": "msg_test",
                "status": "completed",
                "role": "assistant",
                "content": [content],
            }
        ],
    }


@asynccontextmanager
async def mocked_provider(monkeypatch, handler, *, timeout=20, **settings):
    client_type = provider_module.AsyncOpenAI
    transport = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    def client_factory(**kwargs):
        assert kwargs["max_retries"] == 0
        return client_type(
            **kwargs, http_client=transport, base_url="https://api.openai.com/v1"
        )

    monkeypatch.setattr(provider_module, "AsyncOpenAI", client_factory)
    try:
        async with openai_vision(
            api_key="test-key", timeout=timeout, **settings
        ) as provider:
            yield provider
    finally:
        # The actual provider context must close the injected HTTP client.
        assert transport.is_closed


def test_image_request_and_normalized_result(image_path, monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx2.Response(200, json=response_body())

    frame = load_image(image_path)

    async def scenario():
        async with mocked_provider(monkeypatch, handler) as provider:
            return await perceive_image(frame, provider)

    observation = asyncio.run(scenario())
    assert observation.observed_at == frame.observed_at
    assert observation.source == frame.source
    assert observation.provider == "openai"
    assert observation.model == "gpt-5.6-luna-test"
    assert observation.image_detail == "low"
    assert observation.description == "A red rectangular image."
    assert len(requests) == 1
    assert requests[0].url.path == "/v1/responses"
    body = json.loads(requests[0].content)
    assert body["model"] == "gpt-5.6-luna"
    assert body["store"] is False
    assert body["max_output_tokens"] == 256
    assert body["reasoning"]["effort"] == "none"
    image_part = body["input"][0]["content"][1]
    assert image_part["detail"] == "low"
    assert image_part["image_url"].startswith("data:image/jpeg;base64,")
    encoded = image_part["image_url"].split(",", 1)[1]
    with Image.open(BytesIO(base64.b64decode(encoded))) as decoded:
        assert decoded.size == (80, 40)


@pytest.mark.parametrize("detail", ["low", "high", "auto", "original"])
def test_detail_is_sent_and_preserved(image_path, monkeypatch, detail):
    def handler(request):
        body = json.loads(request.content)
        assert body["input"][0]["content"][1]["detail"] == detail
        return httpx2.Response(200, json=response_body())

    async def scenario():
        async with mocked_provider(
            monkeypatch, handler, image_detail=detail
        ) as provider:
            observation = await perceive_image(load_image(image_path), provider)
            assert observation.image_detail == detail

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "payload",
    [
        response_body(status="incomplete"),
        response_body(text=" "),
        response_body(refusal=True),
    ],
)
def test_incomplete_empty_or_refused_descriptions_are_not_observations(
    image_path, monkeypatch, payload
):
    async def scenario():
        async with mocked_provider(
            monkeypatch, lambda request: httpx2.Response(200, json=payload)
        ) as provider:
            with pytest.raises(VisionError):
                await provider.describe(load_image(image_path))

    asyncio.run(scenario())


@pytest.mark.parametrize("code", [401, 429, 500])
def test_api_errors_are_sanitized_and_not_retried(image_path, monkeypatch, code):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx2.Response(
            code, json={"error": {"message": "sensitive-error-body"}}
        )

    async def scenario():
        async with mocked_provider(monkeypatch, handler) as provider:
            with pytest.raises(VisionError) as error:
                await provider.describe(load_image(image_path))
            assert "sensitive-error-body" not in str(error.value)

    asyncio.run(scenario())
    assert len(requests) == 1


def test_request_deadline_closes_client(image_path, monkeypatch):
    async def handler(request):
        await asyncio.Event().wait()

    async def scenario():
        async with mocked_provider(monkeypatch, handler, timeout=0.02) as provider:
            with pytest.raises(VisionError, match="timed out"):
                await provider.describe(load_image(image_path))

    asyncio.run(scenario())


def test_cancellation_propagates_and_closes_client(image_path, monkeypatch):
    async def scenario():
        entered = asyncio.Event()

        async def handler(request):
            entered.set()
            await asyncio.Event().wait()

        async with mocked_provider(monkeypatch, handler) as provider:
            task = asyncio.create_task(provider.describe(load_image(image_path)))
            await asyncio.wait_for(entered.wait(), timeout=2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(scenario())


def test_missing_key_is_actionable_without_request(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    async def scenario():
        with pytest.raises(VisionError, match="OPENAI_API_KEY"):
            async with openai_vision():
                pytest.fail("A provider without credentials must not start")

    asyncio.run(scenario())
