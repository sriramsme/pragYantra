"""Startup wiring for integrated text/voice conversation and background vision."""

import asyncio
import json
import sys
from contextlib import AsyncExitStack
from datetime import UTC, datetime

from pragyantra.application.behavior import DescribeOnTouch
from pragyantra.application.conversation import ConversationSession
from pragyantra.application.models import (
    SensorObservation,
    TextObservation,
    TouchObservation,
)
from pragyantra.application.observation_loop import VisualObservationLoop
from pragyantra.inputs.console import ConsoleInput
from pragyantra.inputs.events import parse_event


class CommandsOnly:
    async def respond(self, request):
        raise ValueError(
            "Conversation needs a provider; use /commands in commands-only mode"
        )


def result_record(result):
    return {
        "kind": "conversation",
        "text": result.reply.text,
        "provider": result.reply.provider,
        "model": result.reply.model,
        "input": {
            "source": result.message.source,
            "observed_at": result.message.observed_at.isoformat(),
            "text": result.message.text,
            "provider": result.message.provider,
            "model": result.message.model,
        },
        "responded_at": result.responded_at.isoformat(),
        "environment": result.environment.to_record(),
        "memory_ids": [note.id for note in result.memories],
    }


async def run_assistant(args):
    from pragyantra.providers.memory import SQLiteNotes

    if args.speak:
        print("Speech output is AI-generated.", file=sys.stderr, flush=True)
    async with AsyncExitStack() as stack:
        services = None
        if not args.commands_only:
            from pragyantra.providers.openai_services import openai_services

            services = await stack.enter_async_context(
                openai_services(
                    model=args.model,
                    transcription_model=args.transcription_model,
                    speech_model=args.speech_model,
                    voice=args.voice_name,
                    embedding_model=args.embedding_model,
                    vision_model=args.vision_model,
                    timeout=args.timeout.total_seconds(),
                )
            )
        notes = stack.enter_context(SQLiteNotes(args.memory)) if args.memory else None
        session = ConversationSession(
            services or CommandsOnly(),
            notes=notes,
            embeddings=services if args.semantic_memory else None,
            max_context_age=args.context_max_age,
        )
        source = None
        if args.webcam is not None:
            from pragyantra.inputs.webcam import WebcamStream

            source = await stack.enter_async_context(WebcamStream(args.webcam))
        console = None
        if not (args.message or args.audio or args.voice):
            console = await stack.enter_async_context(ConsoleInput())

        vision_ready = asyncio.Event()

        async def observe():
            observer = VisualObservationLoop(args.vision_interval, state=session.state)
            async for _ in observer.observations(source, services.vision):
                vision_ready.set()

        async def output(record):
            text = record["text"]
            if args.json:
                print(json.dumps(record, ensure_ascii=False), flush=True)
            else:
                print(f"PragYantra: {text}", flush=True)
            if args.speak:
                from pragyantra.outputs.audio import speak_text

                await speak_text(text, services, device=args.output_device)

        async def handle(event):
            at = datetime.now(UTC)
            if event.observed_at > at:
                raise ValueError("Input event is ahead of the session clock")
            if isinstance(event, SensorObservation):
                session.state.observe(event)
            elif isinstance(event, TouchObservation):
                response = DescribeOnTouch(args.context_max_age).respond(
                    session.state, event, at=at
                )
                await output(
                    {
                        "kind": "touch_response",
                        "text": response.text,
                        "status": response.status.value,
                        "responded_at": response.responded_at.isoformat(),
                    }
                )
            else:
                await output(result_record(await session.respond(event)))

        async def foreground():
            if args.message:
                for text in args.message:
                    if text.strip() in ("/quit", "/exit"):
                        break
                    await handle(
                        TextObservation("console.argument", datetime.now(UTC), text)
                    )
                return
            if args.audio:
                from pragyantra.inputs.audio import load_audio

                for path in args.audio:
                    clip = await asyncio.to_thread(load_audio, path)
                    await handle(await services.transcribe(clip))
                return
            if args.voice:
                from pragyantra.inputs.microphone import record_microphone

                completed = 0
                while args.count is None or completed < args.count:
                    print("Listening…", file=sys.stderr, flush=True)
                    clip = await record_microphone(
                        device=args.input_device,
                        idle_timeout=args.listen_timeout.total_seconds(),
                        sample_rate=args.sample_rate,
                        threshold=args.energy_threshold,
                        max_seconds=args.utterance_limit.total_seconds(),
                        silence_seconds=args.silence_duration.total_seconds(),
                    )
                    message = await services.transcribe(clip)
                    if message.text.casefold().strip(" .!?") in (
                        "stop pragyantra",
                        "quit pragyantra",
                    ):
                        break
                    await handle(message)
                    completed += 1
                return
            while (line := await console.read()) is not None:
                if not line:
                    continue
                if line in ("/quit", "/exit"):
                    break
                event = (
                    parse_event(line)
                    if args.events
                    else TextObservation("console", datetime.now(UTC), line)
                )
                await handle(event)

        try:
            async with asyncio.TaskGroup() as group:
                background = group.create_task(observe()) if source else None
                try:
                    if background:
                        await vision_ready.wait()
                    await foreground()
                finally:
                    if background:
                        background.cancel()
        except ExceptionGroup as errors:
            error = errors.exceptions[0]
            while isinstance(error, ExceptionGroup):
                error = error.exceptions[0]
            raise error from None
