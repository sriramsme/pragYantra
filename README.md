# PragYantra

PragYantra is software for an embodied assistant: seeing, hearing, conversation,
memory, and a boundary for physical sensors. It is a modernization of a personal
2024 prototype, written in Python with explicit application and device interfaces.

The assistant can converse using typed text or transcribed audio, use background
webcam descriptions and timestamped sensor readings as context, and synthesize
spoken replies. Explicit notes support persistent keyword recall and optional
semantic recall. Calculations and memory commands run in application code.

The software has automated integration/lifecycle tests and live hosted-service
smoke checks. Microphone/speaker operation and Raspberry Pi deployment still need
validation on actual devices. No robot, actuator controller, object tracker, or
hard real-time behavior is claimed. See [verification evidence](docs/legacy-retirement.md).

## Setup

Use **uv** for all Python work. Development uses Python 3.12.

```bash
uv sync --locked
uv run pragyantra --help
uv run pragyantra demo --json
```

For hosted capabilities, copy `.env.example` to `.env` and fill `OPENAI_API_KEY`.
Credentials and runtime data are ignored by Git. Setup and CLI help do not contact
services, download model weights, or open devices.

## Start with text

```bash
uv run --env-file .env pragyantra chat
uv run --env-file .env pragyantra chat --message 'Hello' --message 'What can you perceive?' --json
```

Use `/help` for commands and `/quit` to exit. Local commands work without a key:

```bash
uv run pragyantra chat --commands-only \
  --message '/calc sqrt(16) + 2**3' \
  --message '/remember The blue mug belongs to Alex' \
  --message '/recall mug' --json
```

Conversation history is bounded and held in memory. Add `--memory data/notes.sqlite`
to persist **explicit notes**; transcripts and full conversations are not saved.
Add `--semantic-memory` to embed new notes and queries through OpenAI instead of
keyword recall. See [assistant execution](docs/assistant.md) and [memory](docs/memory.md).

## See

```bash
uv run --env-file .env pragyantra see /path/to/image.png --json
uv run --extra webcam --env-file .env pragyantra see --webcam 0 --json
uv run --extra webcam --env-file .env pragyantra watch --interval 5 --count 3 --json
```

File and webcam inputs share normalization and the `ImageFrame` boundary. Vision
uses `gpt-5.6-luna` with low detail by default. `watch` prints descriptions; its
opt-in `--temporal-context` experiment supplies one prior description and its
acquisition-time gap. Quality improvement has not been established.

To converse with background visual context:

```bash
uv run --extra webcam --env-file .env pragyantra chat --webcam 0
```

The first turn waits for an initial visual result. Subsequent vision runs
independently of conversation, with one pending camera frame and serial vision
requests. Selected frames are uploaded to OpenAI. See [vision](docs/vision.md),
[webcam lifecycle](docs/webcam.md), and [temporal context](docs/temporal-context.md).

## Hear and speak

File-based audio needs no audio-device dependency:

```bash
uv run --env-file .env pragyantra speak 'Hello from PragYantra.' --output data/hello.wav
uv run --env-file .env pragyantra listen data/hello.wav --json
uv run --env-file .env pragyantra chat --audio data/hello.wav --json
```

For local microphone/speaker access, install the optional `audio` extra and system
PortAudio; see [audio setup and limits](docs/audio.md).

```bash
uv run --extra audio pragyantra devices
uv run --extra audio --env-file .env pragyantra chat --voice
uv run --extra audio --extra webcam --env-file .env pragyantra chat --voice --webcam 0
```

Speech is AI-generated. Voice turns are half duplex: the microphone closes before
transcription, reasoning, and playback; it reopens after playback. Say “stop
PragYantra” or press Ctrl+C to stop. Noise, endpointing, actual device timing, and
sustained reliability still need hardware evaluation. This is not streaming audio
or speech interruption.

## Sensors and hardware

`chat --events` accepts versioned JSON lines for text, touch, and scalar sensor
readings. Units and acquisition timestamps are explicit. This provides a testable
software boundary for a future embedded controller without selecting hardware or
a transport prematurely. See the [device protocol](docs/device-protocol.md) and
[deployment notes](docs/deployment.md).

Python owns the current application. C++ is the companion language for firmware
or native components when a concrete requirement justifies it. Keep timing-sensitive
control and physical device limits local to the eventual controller.

## Repository map

```text
src/pragyantra/
  application/    Typed values/interfaces, world state, conversation, memory, policies
  inputs/         File/webcam/audio/console acquisition, endpointing, device events
  outputs/        PCM playback, WAV saving, simulated responses
  providers/      OpenAI inference and SQLite persistence
  cli/            Configuration, component construction, command handlers
  __main__.py     Python module entry point
tests/            Deterministic behavior, SDK contracts, CLI and lifecycle tests
docs/             Execution guides, design choices, experiments and limitations
```

Read [the architecture guide](docs/architecture.md) for responsibilities and data
flow. The retired prototype remains available in Git; its audit and attribution
are preserved in [project history](docs/history.md).

## Development checks

```bash
uv sync --locked --all-extras
uv run --locked --all-extras pytest -q
uv run ruff check .
uv run ruff format --check .
uv build
```

Normal tests use synthetic frames/audio, fake devices, temporary databases, and
mock HTTP transports. They require no keys, paid calls, downloads, or physical
hardware. See [the test map](tests/README.md). Hosted providers are replaceable
through small protocols; local inference and decision-model providers are not
implemented yet.

## License

See [LICENSE](LICENSE) for the existing GNU GPL version 3 license.
