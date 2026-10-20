# PragYantra

PragYantra explores software for an embodied assistant: perception, contextual
state, memory, decision-making, speech, and interfaces to physical devices.

The project is being rebuilt from a 2024 Python prototype. **The new implementation
currently contains an installable package, a lightweight CLI, and architecture
boundaries. Assistant behavior and device/model integrations are not implemented
yet.** The original code and README are preserved in [legacy/](legacy/README.md).

## Development

Use **uv** for all Python work. The initial development baseline is Python 3.12;
hardware and provider-specific dependencies will be validated as they are added.

```bash
uv sync --locked
uv run pragyantra --help
uv run pragyantra --version
uv run ruff check .
uv run ruff format --check .
uv build
```

The new package has no runtime dependencies. Development setup does not install
the archived ML stack, download model weights, open devices, or call hosted APIs.
There are no behavior tests yet; see [tests/README.md](tests/README.md).

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

These packages establish boundaries, not completed subsystems. See
[the architecture guide](docs/architecture.md) for dependency rules, hardware
boundaries, and the first proposed behavior.

Python is used for the initial application. C++ is the selected companion language
for firmware or native components when a concrete requirement justifies them.
No hardware platform or firmware project has been selected yet.

## Model deployment

Hosted APIs are acceptable for vision and other model capabilities. Local models
are also candidates. The application should consume capability interfaces rather
than provider SDK types. Implementations live in `providers/`, so selecting a
provider does not redesign the core.
Provider selection and end-to-end latency/resource measurements remain future work.

## License

See [LICENSE](LICENSE) for the existing GNU GPL version 3 license.
