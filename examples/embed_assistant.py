"""Run with uv run examples/embed_assistant.py. Synthetic image and fake providers.

No API key, network, microphone, camera, or subprocess is used. The host owns the
image source context; the runner owns concurrent tasks and consumes typed inputs.
"""

import asyncio
from datetime import UTC, datetime

from PIL import Image

from pragyantra.application.conversation import (
    ConversationResult,
    ConversationSession,
    GeneratedReply,
)
from pragyantra.application.models import SceneDescription, TextObservation
from pragyantra.application.runner import AssistantResult, AssistantRunner
from pragyantra.inputs.image import frame_from_image


class SyntheticImages:
    async def __aenter__(self):
        self.open = True
        return self

    async def read(self):
        if not self.open:
            raise RuntimeError("Image source is closed")
        return frame_from_image(
            Image.new("RGB", (64, 64), "blue"),
            source="example.synthetic",
            observed_at=datetime.now(UTC),
        )

    async def __aexit__(self, *args):
        self.open = False


class ExampleVision:
    async def describe(self, frame):
        # This is a fixture description, not image recognition.
        return SceneDescription("A solid blue square.", "example", "fake-vision")


class ExampleConversation:
    async def respond(self, request):
        visual = request.environment.visual
        text = visual.description if visual else "No visual evidence supplied."
        return GeneratedReply(f"Fixture reply: {text}", "example", "fake-conversation")


async def messages():
    yield TextObservation("example.user", datetime.now(UTC), "What do you see?")


async def receive(result: AssistantResult):
    text = result.reply.text if isinstance(result, ConversationResult) else result.text
    print(text)


async def main():
    session = ConversationSession(ExampleConversation())
    async with SyntheticImages() as images:
        runner = AssistantRunner(session, image_source=images, vision=ExampleVision())
        await runner.run(messages(), on_result=receive)
    print(f"Image source closed: {not images.open}")


if __name__ == "__main__":
    asyncio.run(main())
