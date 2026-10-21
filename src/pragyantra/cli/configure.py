"""Command definitions for assistant, audio, local memory, and calculations."""

import os
from datetime import timedelta
from pathlib import Path


def add_commands(commands, *, duration, count, timestamp, camera_index):
    chat = commands.add_parser(
        "chat", help="Converse using text, audio, current vision and explicit memories"
    )
    sources = chat.add_mutually_exclusive_group()
    sources.add_argument(
        "--message", action="append", help="Text turn; repeat for a finite conversation"
    )
    sources.add_argument(
        "--audio",
        type=Path,
        action="append",
        help="WAV turn; repeat for a finite conversation",
    )
    sources.add_argument(
        "--voice",
        action="store_true",
        help="Listen and speak in half-duplex voice turns",
    )
    chat.add_argument(
        "--events",
        action="store_true",
        help="Read version-1 JSONL text/sensor/touch events from stdin",
    )
    chat.add_argument(
        "--commands-only",
        action="store_true",
        help="Local /commands only; no hosted providers or credentials",
    )
    chat.add_argument(
        "--memory", type=Path, help="Persist explicit notes in this SQLite file"
    )
    chat.add_argument(
        "--semantic-memory",
        action="store_true",
        help="Use hosted embeddings for new explicit notes and recall",
    )
    chat.add_argument(
        "--embedding-model",
        default=os.getenv("PRAGYANTRA_EMBEDDING_MODEL", "text-embedding-3-small"),
    )
    chat.add_argument(
        "--webcam",
        type=camera_index,
        help="Enable background visual context from this camera",
    )
    chat.add_argument(
        "--vision-interval",
        type=duration,
        default=timedelta(seconds=5),
        metavar="SECONDS",
    )
    chat.add_argument(
        "--context-max-age",
        type=duration,
        default=timedelta(seconds=5),
        metavar="SECONDS",
    )
    chat.add_argument(
        "--model", default=os.getenv("PRAGYANTRA_CHAT_MODEL", "gpt-5.6-luna")
    )
    chat.add_argument("--vision-model", default=os.getenv("PRAGYANTRA_VISION_MODEL"))
    chat.add_argument("--count", type=count, help="Stop after this many voice turns")
    chat.add_argument(
        "--speak", action="store_true", help="Speak replies using AI-generated speech"
    )
    listen = commands.add_parser(
        "listen", help="Transcribe one WAV file or microphone utterance"
    )
    listen.add_argument("file", type=Path, nargs="?")
    listen.add_argument("--microphone", action="store_true")
    speak = commands.add_parser(
        "speak", help="Generate AI speech as WAV and/or play it"
    )
    speak.add_argument("text")
    speak.add_argument(
        "--output", type=Path, help="New WAV file; existing files are never overwritten"
    )
    speak.add_argument(
        "--play",
        action="store_true",
        help="Play AI-generated speech through an audio device",
    )
    for command in (chat, listen, speak):
        command.add_argument(
            "--timeout", type=duration, default=timedelta(seconds=30), metavar="SECONDS"
        )
    for command in (chat, listen):
        command.add_argument(
            "--transcription-model",
            default=os.getenv(
                "PRAGYANTRA_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"
            ),
        )
        command.add_argument("--input-device", type=camera_index)
        command.add_argument(
            "--sample-rate",
            type=int,
            choices=[8000, 16000, 24000, 44100, 48000],
            default=16000,
        )
        command.add_argument("--energy-threshold", type=float, default=0.015)
        command.add_argument(
            "--listen-timeout",
            type=duration,
            default=timedelta(seconds=30),
            metavar="SECONDS",
        )
        command.add_argument(
            "--utterance-limit",
            type=duration,
            default=timedelta(seconds=15),
            metavar="SECONDS",
        )
        command.add_argument(
            "--silence-duration",
            type=duration,
            default=timedelta(seconds=0.7),
            metavar="SECONDS",
        )
        command.add_argument("--json", action="store_true")
    for command in (chat, speak):
        command.add_argument(
            "--speech-model",
            default=os.getenv("PRAGYANTRA_SPEECH_MODEL", "gpt-4o-mini-tts"),
        )
        command.add_argument(
            "--voice-name", default=os.getenv("PRAGYANTRA_VOICE", "coral")
        )
        command.add_argument("--output-device", type=camera_index)
    commands.add_parser(
        "devices", help="List audio devices without recording or playback"
    )
    calc = commands.add_parser(
        "calc", help="Evaluate bounded arithmetic locally, without model inference"
    )
    calc.add_argument("expression")
    memory = commands.add_parser(
        "memory", help="Manage explicit local notes; no hosted API"
    )
    memory.add_argument("--database", type=Path, default=Path("data/notes.sqlite"))
    operations = memory.add_subparsers(dest="operation", required=True)
    add = operations.add_parser("add")
    add.add_argument("text")
    forget = operations.add_parser("forget")
    forget.add_argument("id", type=count)
    for name in ("search", "list"):
        search = operations.add_parser(name)
        if name == "search":
            search.add_argument("query")
        search.add_argument("--limit", type=count, default=10)
        search.add_argument("--since", type=timestamp)
        search.add_argument("--until", type=timestamp)


def validate(args, parser):
    if args.command == "listen" and (args.file is not None) == args.microphone:
        parser.error("listen requires either a WAV file or --microphone")
    if args.command == "speak" and not (args.output or args.play):
        parser.error("speak requires --output PATH and/or --play")
    if args.command == "chat":
        if args.events and (args.message or args.audio or args.voice):
            parser.error(
                "--events reads stdin; do not combine it with another input source"
            )
        if args.commands_only and (
            args.audio
            or args.voice
            or args.speak
            or args.webcam is not None
            or args.semantic_memory
        ):
            parser.error(
                "--commands-only does not use hosted audio, vision, or embeddings"
            )
        if args.count is not None and not args.voice:
            parser.error(
                "--count is for voice turns; text/audio arguments define finite turns"
            )
        args.speak = args.speak or args.voice
