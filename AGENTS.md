# Working on PragYantra

## Project context

PragYantra is being rebuilt from a 2024 multimodal assistant prototype. The aim is
software for an embodied assistant that perceives, maintains context, decides, and
interacts with physical devices. The original prototype did not produce completed
hardware integration or a functioning humanoid robot.

No hardware target, robot form factor, controller, or transport has been selected.
Raspberry Pi deployment is a candidate, not a tested capability. Hardware
integration should follow concrete requirements and independently tested interfaces.

Favor working milestones and reproducible evidence. Document design decisions,
tradeoffs, experiments, and limitations. Distinguish implemented capabilities from
proposed work; do not invent results or performance measurements.

## Chosen direction

- Python for the initial application; C++ for firmware/native components when a
  requirement justifies them, interoperating with vendor C APIs as appropriate.
  Do not introduce firmware or a C++ tree merely to include the language.
- **Always use `uv` for Python**: interpreter/environment management, dependencies,
  scripts, tools, and tests. Use `uv add`, `uv sync`, and `uv run`; never standalone
  pip or global Python installs. Keep `pyproject.toml` and `uv.lock` in sync.
- The initial development interpreter is Python 3.12 (`.python-version`). Validate
  provider dependencies and ARM support as integrations are added; do not assume
  the host environment establishes hardware compatibility.
- Hosted APIs are acceptable for vision and other model capabilities. Local models
  remain an option. Offline-only operation is not a universal requirement.
- Decision models such as Jev and OpenAI Decisions are candidates for bounded
  semantic judgments. Keep known rules/calculations in code, evaluate judgments
  on representative inputs, and use generative models when the behavior needs them.
  OpenAI Responses vision is integrated behind `VisionProvider`; decision-model
  providers are not integrated yet.

## Current repository

- `src/pragyantra/`: replacement package with a simulation, image-file vision,
  and optional one-shot/continuous laptop/USB webcam input.
  `inputs/` acquires observations; `application/` owns shared values/interfaces,
  world state, behaviors, and lifecycle; `outputs/` executes speech/device requests;
  `providers/` wraps third-party APIs and external model/service implementations.
  Root `cli.py` wires components and exposes the launcher.
- `docs/architecture.md`: responsibilities, dependency rules, deployment boundaries,
  and current behavior/limitations. Keep it aligned with the implementation.
- `docs/vision.md`: step-by-step image execution, configuration, and timing limits.
- `docs/webcam.md`: optional camera setup, observation loop, and capture limits.
- `tests/`: behavior, timing, lifecycle, image validation, mocked SDK, and CLI tests.
- `legacy/`: original application, requirements, scripts, README, notebook, and
  architecture image. It is reference material, excluded from the new package and
  linting. Its local `AGENTS.md` contains the historical audit.
- Root `README.md`: current setup and implementation status. Root `LICENSE`:
  existing GNU GPL version 3 license; preserve licensing and attribution.

## Architecture rules

Keep shared values and capability interfaces inside application modules as needed.
Inputs, outputs, and providers depend on those values/interfaces. Application code
must not import concrete inputs, outputs, providers, model SDKs, hardware libraries,
or the legacy tree. Root `cli.py` may import all four packages to construct them.
Inputs/outputs receive provider capabilities through interfaces rather than
importing concrete providers. This is an ongoing system with asynchronous inputs
and persistent world state, not a mandatory single synchronous pipeline.

Use small protocols and typed values as behaviors need them. Keep API clients,
authentication, SDK objects, timeouts, and response parsing in providers; keep
device setup in inputs/outputs and supply configuration through startup wiring.
Separate sensor acquisition from perception. Imports must not open devices, load
weights, start threads, or call APIs. Manage lifecycle explicitly.

Start with one package, not speculative services or a universal plugin framework.
Keep modules grouped by capability when they grow. Do not add large placeholder
hierarchies or recreate every legacy feature. The archive may be deleted once its
useful behavior and historical references have been reviewed.

The first behavior uses simulated visual and touch observations: a touch requests
current visual context, with explicit unavailable/stale handling. Run it with
`uv run pragyantra demo` or add `--json` for response evidence. It uses a logical
clock and records text rather than producing audio. It does not recognize images.
World state retains one latest acquired scene; it is not a complete world model.

`uv run --env-file .env pragyantra see IMAGE --json` reads and normalizes a local
image and explicitly sends it to OpenAI. The provider uses Responses with
`gpt-5.6-luna` by default, low image detail, no reasoning, a short output limit,
`store=False`, and no automatic retries. These are configurable engineering choices,
not measured accuracy or performance claims. API credentials stay in environment
variables or ignored `.env`; `.env.example` contains placeholders only.

Image acquisition, the provider contract, and interpretation-to-observation mapping
are separate. Provider/model and requested image detail are retained without
inventing confidence. `--image-detail` changes provider preprocessing; the file
loader still normalizes uploads to at most 1024 pixels on the longest edge.
For files, the default timestamp is pipeline acquisition, not the photo's historical
capture time; `--captured-at` accepts a known time. This path uses the real clock,
preserves acquisition time through inference, and retains simulated touch/output.
A manual live API smoke test and a three-image check succeeded on October 20,
2026. `docs/experiments/2026-10-20-vision-smoke.md` records descriptions, sources,
and timing; systematic accuracy and latency evaluation remain outstanding.
No Google Cloud setup is required by the current implementation.

`uv run --extra webcam --env-file .env pragyantra see --webcam 0 --json` captures
one frame through `inputs/webcam.py`. OpenCV is optional and imported on capture,
not at module import. File and webcam adapters share image normalization and
return `ImageFrame`; future camera adapters should preserve that boundary. The
webcam is released before inference, including on acquisition/normalization errors.
Its timestamp is host read-start, not sensor exposure time; buffering can conceal
older frames. Blocking driver calls can delay cancellation and release, and the
provider timeout does not bound acquisition. Automated tests use synthetic pixels
and fake devices. A manual webcam smoke test was reported successful on October 20,
2026; device details, repeated-run reliability, and capture timing were not recorded.

`uv run --extra webcam --env-file .env pragyantra watch --interval 5 --count 3 --json`
uses `WebcamStream` and `application/observation_loop.py:VisualObservationLoop`.
One camera worker owns open/read/release; a producer replaces one pending raw
frame while inference or pacing is busy. Only selected frames are normalized.
The application consumes `ImageSource` and `VisionProvider`, performs serial
inference, preserves acquisition/receipt timing, and retains latest context in
`WorldState`. The interval is a delay after result handling, not a fixed rate.
CLI output streams immediately without retaining a response history. A finite
count stops normally; omitting it runs until Ctrl+C. Errors stop without retries.
Cleanup stops the producer, waits for active device work, releases on the same
worker, and joins it. Driver calls can delay shutdown. Continuous operation has
automated tests and a successful manual smoke test reported on October 20, 2026;
test duration, device details, settings, and timings were not recorded. Prior descriptions are not
fed back into prompts; temporal context remains a separate candidate experiment.
This path inspects observations directly rather than simulating touch requests.

The runtime consumes one async stream and awaits each output. Resource contexts
close on completion, failure, and cancellation. Live sensor multiplexing, parallel
inference, and speech interruption are not implemented. The webcam has one pending
frame slot; other device queue policies remain undefined. Define those semantics
when adding adapters. Preserve acquisition/receipt/response
time distinctions; freshness must include inference and processing delay.

For hardware, state assumptions and consult datasheets/official documentation
before committing to electrical interfaces. Keep deadline-sensitive control and
physical device limits local; higher-level inference may select goals/actions.
Consult live provider documentation before implementing version-dependent APIs.

## Development and validation

From the repository root:

```bash
uv sync --locked
uv run pragyantra --help
uv run pragyantra --version
uv run pragyantra demo
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv build
```

Runtime dependencies are OpenAI and Pillow. Ruff, pytest, and an SDK-compatible
mock HTTP transport are development tools; no CI workflow has been added.
OpenCV is in the optional `webcam` extra. Run `uv run --locked --extra webcam pytest -q`
to include synthetic OpenCV capture tests; base tests skip that optional module.
Add focused tests for implemented behavior,
using fake providers/devices and temporary storage so normal tests need no
credentials, hardware, paid calls, or downloads. Async tests use `asyncio.run` and
logical clocks rather than wall-clock sleeps. Do not test empty scaffolding just
to increase test counts. Introduce additional tools through `uv` when needed.

Keep edits scoped. Run relevant checks and `git diff --check`; report what was
verified and what remains untested. Never claim package checks validate an actual
robot, model accuracy, control timing, or edge deployment. Keep documentation
honest about implemented, experimental, and planned capabilities.

Keep credentials, weights, recordings, and personal memory out of commits.
`.env`, `.env.*` (except `.env.example`), `models/`, `memory_stream/`, `data/`, and
`*.pkl` are ignored. Exercise filesystem actions only against temporary fixtures.
