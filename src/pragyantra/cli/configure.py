"""Command definitions for assistant, perception, audio and explicit memory."""

import os
from datetime import timedelta
from pathlib import Path


def add_commands(commands, *, duration, count, timestamp, camera_index):
    inspect = commands.add_parser(
        "inspect", help="Judge image conditions directly with OpenAI Decisions"
    )
    inspect.add_argument("image", type=Path, nargs="?")
    inspect.add_argument("--camera", "--webcam", type=camera_index, nargs="?", const=0)
    inspect.add_argument("--condition", action="append", default=[], metavar="TEXT")
    inspect.add_argument("--questions", type=Path, help="JSON question definitions")
    inspect.add_argument("--captured-at", type=timestamp)
    inspect.add_argument("--max-age", type=duration, default=timedelta(seconds=5))
    inspect.add_argument("--timeout", type=duration, default=timedelta(seconds=10))
    inspect.add_argument(
        "--model", default=os.getenv("PRAGYANTRA_INSPECTION_MODEL", "gpt-6-luna")
    )
    inspect.add_argument(
        "--image-detail", choices=["low", "high", "auto", "original"], default="low"
    )
    inspect.add_argument("-j", "--json", action="store_true")
    chat = commands.add_parser(
        "chat",
        usage="%(prog)s [OPTIONS]",
        help="Converse using text, audio, current vision and explicit memories",
    )
    inputs = chat.add_argument_group("Input")
    context = chat.add_argument_group("Context and memory")
    session = chat.add_argument_group("Session")
    chat_models = chat.add_argument_group("Models")
    chat_output = chat.add_argument_group("Output")
    sources = inputs.add_mutually_exclusive_group()
    sources.add_argument(
        "-m",
        "--message",
        action="append",
        metavar="TEXT",
        help="Text turn; repeat for a finite conversation",
    )
    sources.add_argument(
        "--audio",
        metavar="WAV",
        type=Path,
        action="append",
        help="WAV turn; repeat for a finite conversation",
    )
    sources.add_argument(
        "--voice",
        action="store_true",
        help="Listen and speak in half-duplex voice turns",
    )
    inputs.add_argument(
        "--events",
        action="store_true",
        help="Read version-1 JSONL text/sensor/touch events from stdin",
    )
    session.add_argument(
        "--interpret",
        action="store_true",
        help="Route natural requests through Jev (opt in)",
    )
    chat_models.add_argument(
        "--decision-model",
        default=os.getenv("PRAGYANTRA_DECISION_MODEL", "jev-1.14.0"),
        help="Jev request-interpretation model",
    )
    chat_models.add_argument(
        "--decision-timeout",
        type=duration,
        default=timedelta(seconds=10),
        metavar="SECONDS",
    )
    session.add_argument(
        "--commands-only",
        action="store_true",
        help="Local /commands only; no hosted providers or credentials",
    )
    context.add_argument(
        "--memory",
        type=Path,
        nargs="?",
        const=Path("data/notes.sqlite"),
        metavar="PATH",
        help="Persist notes (default path: data/notes.sqlite)",
    )
    context.add_argument(
        "--semantic-memory",
        action="store_true",
        help="Use hosted embeddings for new explicit notes and recall",
    )
    chat_models.add_argument(
        "--embedding-model",
        default=os.getenv("PRAGYANTRA_EMBEDDING_MODEL", "text-embedding-3-small"),
        help="Embedding model used by --semantic-memory",
    )
    context.add_argument(
        "--camera",
        "--webcam",
        dest="webcam",
        nargs="?",
        const=0,
        type=camera_index,
        metavar="INDEX",
        help="Enable background vision (default camera: 0)",
    )
    context.add_argument(
        "--vision-interval",
        help="Delay after a visual result in seconds (default: 5)",
        type=duration,
        default=timedelta(seconds=5),
        metavar="SECONDS",
    )
    context.add_argument(
        "--context-max-age",
        help="Sensory freshness limit in seconds (default: 5)",
        type=duration,
        default=timedelta(seconds=5),
        metavar="SECONDS",
    )
    chat_models.add_argument(
        "--model",
        default=os.getenv("PRAGYANTRA_CHAT_MODEL", "gpt-5.6-luna"),
        help="Conversation model; also set by PRAGYANTRA_CHAT_MODEL",
    )
    chat_models.add_argument(
        "--vision-model", default=os.getenv("PRAGYANTRA_VISION_MODEL")
    )
    session.add_argument(
        "-n", "--count", type=count, help="Stop after this many voice turns"
    )
    chat_output.add_argument(
        "--speak", action="store_true", help="Speak replies using AI-generated speech"
    )
    interpret = commands.add_parser(
        "interpret", help="Judge a request without running a behavior"
    )
    interpret.add_argument("text")
    interpret.add_argument(
        "--decision-model", default=os.getenv("PRAGYANTRA_DECISION_MODEL", "jev-1.14.0")
    )
    interpret.add_argument("--timeout", type=duration, default=timedelta(seconds=10))
    interpret.add_argument("-j", "--json", action="store_true")
    listen = commands.add_parser(
        "listen", help="Transcribe one WAV file or microphone utterance"
    )
    listen.add_argument(
        "file",
        type=Path,
        nargs="?",
        metavar="WAV",
        help="WAV file; otherwise listen to the microphone",
    )
    listen.add_argument(
        "--microphone",
        action="store_true",
        help="Listen to the microphone (default when no WAV is given)",
    )
    speak = commands.add_parser(
        "speak", help="Generate AI speech as WAV and/or play it"
    )
    speak.add_argument("text")
    speak.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="WAV",
        help="New WAV file; existing files are never overwritten",
    )
    speak.add_argument(
        "--play",
        action="store_true",
        help="Play speech (default when no output file is given)",
    )
    models = {
        chat: chat_models,
        listen: listen.add_argument_group("Models"),
        speak: speak.add_argument_group("Models"),
    }
    outputs = {
        chat: chat_output,
        listen: listen.add_argument_group("Output"),
        speak: speak.add_argument_group("Audio output"),
    }
    for command in (chat, listen, speak):
        models[command].add_argument(
            "--timeout", type=duration, default=timedelta(seconds=30), metavar="SECONDS"
        )
    for command in (chat, listen):
        audio = command.add_argument_group("Audio input")
        models[command].add_argument(
            "--transcription-model",
            default=os.getenv(
                "PRAGYANTRA_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"
            ),
        )
        audio.add_argument("--input-device", type=camera_index)
        audio.add_argument(
            "--sample-rate",
            type=int,
            choices=[8000, 16000, 24000, 44100, 48000],
            default=16000,
        )
        audio.add_argument("--energy-threshold", type=float, default=0.015)
        audio.add_argument(
            "--listen-timeout",
            type=duration,
            default=timedelta(seconds=30),
            metavar="SECONDS",
        )
        audio.add_argument(
            "--utterance-limit",
            type=duration,
            default=timedelta(seconds=15),
            metavar="SECONDS",
        )
        audio.add_argument(
            "--silence-duration",
            type=duration,
            default=timedelta(seconds=0.7),
            metavar="SECONDS",
        )
        outputs[command].add_argument(
            "-j", "--json", action="store_true", help="Print machine-readable JSON"
        )
    for command in (chat, speak):
        models[command].add_argument(
            "--speech-model",
            default=os.getenv("PRAGYANTRA_SPEECH_MODEL", "gpt-4o-mini-tts"),
        )
        models[command].add_argument(
            "--voice-name", default=os.getenv("PRAGYANTRA_VOICE", "coral")
        )
        outputs[command].add_argument("--output-device", type=camera_index)
    commands.add_parser(
        "devices", help="List audio devices without recording or playback"
    )
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

    profile = commands.add_parser(
        "profile", help="Manage explicit saved companion context"
    )
    profile.add_argument("--database", type=Path, default=Path("data/notes.sqlite"))
    profile_ops = profile.add_subparsers(dest="operation", required=True)
    setting = profile_ops.add_parser("set")
    setting.add_argument("kind", choices=["name", "preference", "observation"])
    setting.add_argument("key")
    setting.add_argument("value")
    deleting = profile_ops.add_parser("delete")
    deleting.add_argument("kind", choices=["name", "preference", "observation"])
    deleting.add_argument("key")
    profile_ops.add_parser("list")


def validate(args, parser):
    if args.command == "inspect":
        if (args.image is None) == (args.camera is None):
            parser.error("inspect requires an image file or --camera")
        if args.camera is not None and args.captured_at is not None:
            parser.error("--captured-at applies only to image files")
        if not args.condition and args.questions is None:
            parser.error("inspect requires --condition or --questions")
    if args.command == "listen":
        if args.file is not None and args.microphone:
            parser.error("Choose a WAV file or --microphone, not both")
        args.microphone = args.file is None
    if args.command == "speak" and args.output is None:
        args.play = True
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
            or args.interpret
        ):
            parser.error(
                "--commands-only does not use hosted audio, vision, embeddings, "
                "or request interpretation"
            )
        if args.count is not None and not args.voice:
            parser.error(
                "--count is for voice turns; text/audio arguments define finite turns"
            )
        args.speak = args.speak or args.voice
