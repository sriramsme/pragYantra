# PragYantra

PragYantra explores software for an embodied assistant: perception, contextual
state, memory, decision-making, speech, and interfaces to physical devices.

The project is being rebuilt from a 2024 Python prototype. **The new implementation
has a tested simulation and an image-file vision path using OpenAI. Visual
observations update current context, and touch events request a description with
missing/stale handling. Camera hardware and speech synthesis are not connected
yet; a manual live API smoke test passed, while systematic accuracy and latency
evaluation remain outstanding.** The original code and
README are preserved in [legacy/](legacy/README.md).

## Development

Use **uv** for all Python work. The initial development baseline is Python 3.12;
hardware and provider-specific dependencies will be validated as they are added.

```bash
uv sync --locked
uv run pragyantra --help
uv run pragyantra --version
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv build
```

The runtime dependencies are Pillow for image validation/normalization and the
OpenAI SDK for hosted vision. Setup does not install the archived ML stack,
download model weights, open devices, or call hosted APIs. Normal tests use
simulated I/O, logical clocks, and mocked HTTP transports; see
[tests/README.md](tests/README.md).

## Run the simulation

```bash
uv run pragyantra demo
uv run pragyantra demo --json
```

The default scenario produces:

```text
[unavailable] I don't have a visual observation yet.
[current] The latest visual observation describes: A mug and a notebook are on a desk.
[stale] My last visual observation is too old to describe now.
```

These are scripted observations, not actual scene recognition. Simulated time
advances without waiting; the command records text responses rather than playing
audio. JSON lines include the touch source/time, visual evidence, response time,
and visual age. An older visual result delivered late is ignored.

`--max-visual-age SECONDS` changes the freshness threshold (default: 5 seconds,
inclusive). The threshold is a demo policy, not an experimentally established
sensor requirement. Increasing it can change the final response to `current`.

## Describe an image

```bash
cp .env.example .env
# Fill in OPENAI_API_KEY, then:
uv run --env-file .env pragyantra see /path/to/image.png --json
```

This explicitly sends a normalized image to OpenAI and reuses the existing
behavior with a simulated touch. The default model is `gpt-5.6-luna`; override it
with `--model` or `PRAGYANTRA_VISION_MODEL`. Image detail defaults to `low`; use
`--image-detail high`, `auto`, or `original` to compare. No key is needed for the
simulation or tests. The five-second freshness policy includes inference latency.

See [the vision walkthrough](docs/vision.md) for each execution step, timing
semantics, provider settings, limits, and setup. Loading an old photo does not
establish awareness of the current physical surroundings.

## Repository layout

```text
src/pragyantra/
  inputs/         Cameras, microphones, sensors, and simulated observations
  application/    Shared models, interfaces, world state, and behavior coordination
  outputs/        Speech, actuators, and simulated actions
  providers/      Third-party APIs and external model/service implementations
  cli.py          Startup wiring and the development CLI
  __main__.py     Python module entry point
tests/            Tests added alongside implemented behaviors
docs/             Architecture and engineering decisions
legacy/           Archived prototype; excluded from the new package and linting
```

These packages establish boundaries around the initial simulated behavior. See
[the architecture guide](docs/architecture.md) for dependency rules, hardware
boundaries, and current limitations.

Python is used for the initial application. C++ is the selected companion language
for firmware or native components when a concrete requirement justifies them.
No hardware platform or firmware project has been selected yet.

## Model deployment

Hosted APIs are acceptable for vision and other model capabilities. Local models
are also candidates. The application should consume capability interfaces rather
than provider SDK types. Implementations live in `providers/`, so selecting a
provider does not redesign the core.
OpenAI is the first implemented provider. Other providers and end-to-end
latency/resource measurements remain future work.

## License

See [LICENSE](LICENSE) for the existing GNU GPL version 3 license.
