"""Startup wiring for integrated text/voice conversation and background vision."""

import asyncio
import json
import sys
from contextlib import AsyncExitStack
from datetime import UTC, datetime

from pragyantra.application.conversation import ConversationResult, ConversationSession
from pragyantra.application.models import TextObservation
from pragyantra.application.requests import RequestResult, RequestRouter
from pragyantra.application.runner import AssistantResult, AssistantRunner
from pragyantra.cli.records import text_record
from pragyantra.cli.requests import request_record
from pragyantra.inputs.console import ConsoleInput
from pragyantra.inputs.events import parse_event


class CommandsOnly:
    async def respond(self, request):
        raise ValueError(
            "Conversation needs a provider; try /help in commands-only mode"
        )


def result_record(result: ConversationResult) -> dict[str, object]:
    return {
        "kind": "conversation",
        "text": result.reply.text,
        "provider": result.reply.provider,
        "model": result.reply.model,
        "input": text_record(result.message),
        "responded_at": result.responded_at.isoformat(),
        "environment": result.environment.to_record(),
        "memory_ids": [note.id for note in result.memories],
        "companion": [entry.to_record() for entry in result.companion],
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
            companion=notes.companion if notes is not None else None,
            embeddings=services if args.semantic_memory else None,
            max_context_age=args.context_max_age,
        )
        router = None
        if args.interpret:
            from pragyantra.providers.typesafe import typesafe_interpreter

            interpreter = await stack.enter_async_context(
                typesafe_interpreter(
                    model=args.decision_model,
                    timeout=args.decision_timeout.total_seconds(),
                )
            )
            router = RequestRouter(interpreter)
        source = None
        if args.webcam is not None:
            from pragyantra.inputs.webcam import WebcamStream

            source = await stack.enter_async_context(WebcamStream(args.webcam))
        console = None
        if not (args.message or args.audio or args.voice):
            console = await stack.enter_async_context(ConsoleInput())

        async def output(result: AssistantResult):
            if isinstance(result, RequestResult):
                record = request_record(result)
                if result.conversation is not None:
                    record["conversation"] = result_record(result.conversation)
            else:
                record = (
                    result_record(result)
                    if isinstance(result, ConversationResult)
                    else {
                        "kind": "touch_response",
                        "text": result.text,
                        "status": result.status.value,
                        "responded_at": result.responded_at.isoformat(),
                    }
                )
            text = record["text"]
            if args.json:
                print(json.dumps(record, ensure_ascii=False), flush=True)
            else:
                print(f"PragYantra: {text}", flush=True)
            if args.speak:
                from pragyantra.outputs.audio import speak_text

                await speak_text(text, services, device=args.output_device)

        async def observations():
            if args.message:
                for text in args.message:
                    if text.strip() in ("/quit", "/exit"):
                        break
                    yield TextObservation("console.argument", datetime.now(UTC), text)
                return
            if args.audio:
                from pragyantra.inputs.audio import load_audio

                for path in args.audio:
                    clip = await asyncio.to_thread(load_audio, path)
                    yield await services.transcribe(clip)
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
                    yield message
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
                yield event

        runner = AssistantRunner(
            session,
            router=router,
            image_source=source,
            vision=services.vision if source is not None else None,
            vision_interval=args.vision_interval,
        )
        try:
            await runner.run(observations(), on_result=output)
        except ExceptionGroup as errors:
            error = errors.exceptions[0]
            while isinstance(error, ExceptionGroup):
                error = error.exceptions[0]
            raise error from None
