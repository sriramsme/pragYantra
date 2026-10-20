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
  No provider has been selected or integrated yet.

## Current repository

- `src/pragyantra/`: installable replacement package; currently a scaffold only.
  `inputs/` acquires observations; `application/` owns shared values/interfaces,
  world state, behaviors, and lifecycle; `outputs/` executes speech/device requests;
  `providers/` wraps third-party APIs and external model/service implementations.
  Root `cli.py` wires components and exposes the launcher.
- `docs/architecture.md`: responsibilities, dependency rules, deployment boundaries,
  and the first proposed behavior. Keep it aligned with the implementation.
- `tests/`: testing guidance; no behavior tests yet.
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

The first proposed behavior uses simulated visual and touch observations: a touch
requests current visual context, with explicit unavailable/stale handling. It has
not been implemented. Add real devices and providers after independently testing
that path. Define freshness, timeouts, bounded work, and shutdown when implementing
concurrent components. Distinguish acquisition time from processing completion.

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
uv run ruff check .
uv run ruff format --check .
uv build
```

The package currently has no runtime dependencies. Ruff is the development tool;
no test runner or CI workflow has been added. Add focused tests for implemented
behavior, using fake providers/devices and temporary storage so normal tests need
no credentials, hardware, paid calls, or downloads. Do not test empty scaffolding
just to increase test counts. Introduce test tools through `uv` when needed.

Keep edits scoped. Run relevant checks and `git diff --check`; report what was
verified and what remains untested. Never claim package checks validate an actual
robot, model accuracy, control timing, or edge deployment. Keep documentation
honest about implemented, experimental, and planned capabilities.

Keep credentials, weights, recordings, and personal memory out of commits.
`.env`, `.env.*` (except `.env.example`), `models/`, `memory_stream/`, `data/`, and
`*.pkl` are ignored. Exercise filesystem actions only against temporary fixtures.
