# PragYantra

PragYantra is software for an embodied assistant: seeing, hearing, conversation,
memory, and a boundary for physical sensors. It is a modernization of a personal
2024 prototype, written in Python with explicit application and device interfaces.

The assistant can converse using typed text or transcribed audio, use background
webcam descriptions and timestamped sensor readings as context, and synthesize
spoken replies. Explicit notes support persistent keyword recall and optional
semantic recall. Calculations and memory commands run in application code.
Explicit names/preferences supplement notes, and direct image inspections return
bounded predicates, choices or scores independently of generated conversation.

The software has automated integration/lifecycle tests and live hosted-service
smoke checks. Microphone/speaker operation and Raspberry Pi deployment still need
validation on actual devices. No robot, actuator controller, object tracker, or
hard real-time behavior is claimed. See [verification evidence](docs/legacy-retirement.md).

## Setup

Use **uv** for all Python work. Development uses Python 3.12.

```bash
uv tool install --editable '.[audio,webcam]' --python 3.12
prag --help
prag demo --json
```

For hosted capabilities, copy `.env.example` to `.env` and fill `OPENAI_API_KEY`.
`.env` in the current directory loads automatically; shell variables take
precedence. Use `--env-file PATH` or `--no-env` to override this.
Credentials and runtime data are ignored by Git. Setup and CLI help do not contact
inference services, download model weights, or open devices. The installation
provides both `prag` and `pragyantra`; see [CLI setup and configuration](docs/cli.md)
for locked development commands and optional dependencies.

## Start with text

```bash
prag chat
prag chat --message 'Hello' --message 'What can you perceive?' --json
```

Use `/help` for commands and `/quit` to exit. Local commands work without a key:

```bash
prag chat --commands-only \
  --message '/calc sqrt(16) + 2**3' \
  --message '/remember The blue mug belongs to Alex' \
  --message '/recall mug' --json
```

Conversation history is bounded and held in memory. Add `--memory`
to persist **explicit notes**; transcripts and full conversations are not saved.
Add `--semantic-memory` to embed new notes and queries through OpenAI instead of
keyword recall. See [assistant execution](docs/assistant.md) and [memory](docs/memory.md).

## Interpret requests with Jev

Optional request interpretation lets code route natural requests to conversation
or reporting the latest scene. Install the `decisions` extra and add
`TYPESAFE_API_KEY` to `.env`:

```bash
uv tool install --editable '.[audio,webcam,decisions]' --python 3.12
prag interpret 'What do you see?' --json
prag chat --interpret --camera
```

`interpret` only shows a judgment; `chat --interpret` uses it. Following, missions
and natural-language note saving return an unsupported result. Ambiguity asks for
clarification; provider failures select no behavior. `/stop` ends the local session
without calling Jev or sending robot commands. See
[request interpretation](docs/request-interpretation.md) for the three core files,
policy, evaluation and limits.

## See

```bash
prag see /path/to/image.png --json
prag see --camera --json
prag watch --interval 5 --count 3 --json
```

File and webcam inputs share normalization and the `ImageFrame` boundary. Vision
uses `gpt-5.6-luna` with low detail by default. `watch` prints descriptions; its
opt-in `--temporal-context` experiment supplies one prior description and its
acquisition-time gap. Quality improvement has not been established.

To converse with background visual context:

```bash
prag chat --camera
```

The first turn waits for an initial visual result. Subsequent vision runs
independently of conversation, with one pending camera frame and serial vision
requests. Selected frames are uploaded to OpenAI. See [vision](docs/vision.md),
[webcam lifecycle](docs/webcam.md), and [temporal context](docs/temporal-context.md).

## Inspect image evidence directly

```bash
prag inspect photo.jpg --condition 'Is a red mug visible?' --json
prag inspect --camera --condition 'Is the configured marker visible?' --json
```

This uses the separate OpenAI Decisions endpoint (`gpt-6-luna`), preserving the
existing conversation/description model. It returns model judgments with evidence
references, acquisition times and uncertainty, rejecting stale evidence. Multiple
conditions share one image request. Named station choices and ordered rubrics use
`--questions FILE`; see [direct inspection](docs/inspection.md).

## Save companion context

```bash
prag profile set name user Casey
prag profile set preference interaction_style 'Keep replies concise'
prag chat --memory
```

These explicit entries persist alongside notes when the same database is selected.
Named observations remain saved text, separate from what sensors currently show.
See [companion context](docs/companion.md) for `/profile` commands and limits.

## Hear and speak

File-based audio needs no audio-device dependency:

```bash
prag speak 'Hello from PragYantra.' --output data/hello.wav
prag listen data/hello.wav --json
prag chat --audio data/hello.wav --json
```

The installation above includes audio support. Microphone/speaker access also
requires system PortAudio; see [audio setup and limits](docs/audio.md).

```bash
prag devices
prag chat --voice
prag chat --voice --camera
```

Speech is AI-generated. Voice turns are half duplex: the microphone closes before
transcription, reasoning, and playback; it reopens after playback. Say “stop
PragYantra” or press Ctrl+C to stop. Noise, endpointing, actual device timing, and
sustained reliability still need hardware evaluation. This is not streaming audio
or speech interruption.

## Embed in another Python application

`AssistantRunner` accepts typed observations and an optional image source, shares
context with `ConversationSession`, and delivers typed results to an async callback.
It manages concurrent tasks while the host owns provider/device resources.

```bash
uv run examples/embed_assistant.py
```

This runnable example uses a synthetic image and fake providers, with no hardware,
credentials or subprocess. See [Python embedding](docs/embedding.md) and the
[implementation roadmap](docs/roadmap.md) for the integration contract and next steps.

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
  providers/      OpenAI inference, optional TypeSafe judgments, SQLite persistence
  cli/            Configuration, component construction, command handlers
  __main__.py     Python module entry point
examples/         Small runnable examples using public application interfaces
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
through small protocols. TypeSafe request interpretation is opt in; direct image
judgments use OpenAI Decisions. Local inference remains unimplemented. Explicit
evaluation scripts default to offline fixture validation; select `--live` to call
providers. See [inspection evaluation](docs/inspection.md#evaluation-and-limits).

## License

See [LICENSE](LICENSE) for the existing GNU GPL version 3 license.
