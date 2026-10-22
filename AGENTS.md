# Working on PragYantra

## Project context and scope

PragYantra modernizes a 2024 multimodal assistant prototype into software for an
embodied assistant: perceiving, maintaining context, conversing, remembering and
interacting through explicit interfaces. The original prototype did not complete
hardware integration or build a functioning humanoid robot. Its source/audit remain
in Git; see `docs/history.md` and `docs/legacy-retirement.md`.

No hardware target, robot form factor, controller, electrical interface or
transport has been selected. Raspberry Pi is a candidate, not a tested deployment.
Keep deadline-sensitive control and device limits local to the eventual controller.
Consult datasheets/official documentation before implementing physical interfaces.
Do not add C++/firmware scaffolding without a concrete responsibility.

Favor incremental working milestones, measured evidence, explicit tradeoffs and
honest limitations. Never present plans, fake-device tests or smoke checks as a
completed robot, model accuracy result or real-time hardware validation.

## Environment and chosen direction

- **Always use uv for Python**: interpreters, environments, dependencies, scripts,
  tools and tests. Use `uv add`, `uv sync`, `uv run`; never standalone pip/global
  Python installs. Keep `pyproject.toml` and `uv.lock` in sync.
- Python 3.12 is the development interpreter (`.python-version`); C++ is the
  companion language for justified firmware/native work, using vendor C APIs
  where appropriate. Host tests do not establish ARM dependency support.
- Hosted APIs are acceptable; local models remain an option, not an offline-only
  requirement. Current OpenAI defaults are user-selected `gpt-5.6-luna` for
  vision/conversation, `gpt-4o-mini-transcribe`, `gpt-4o-mini-tts`/`coral`, and
  optional `text-embedding-3-small`. Do not silently replace requested models.
- Consult live official provider documentation for version-dependent integrations.
  SDKs/authentication/deadlines/response parsing belong in providers.
- Jev request interpretation is opt in (`decisions` extra, `jev-1.14.0` default).
  OpenAI Decisions implements direct image judgments with its separate documented
  `gpt-6-luna` default; conversation/description defaults remain unchanged. Keep known
  rules/calculations in code and evaluate any semantic judgment on representative
  inputs. Generative conversation is appropriate when behavior requires it.

## Repository and dependency rules

- `src/pragyantra/application/`: shared typed values/protocols, state, perception,
  conversation, memory policies, deterministic actions, runtime.
- `inputs/`: acquisition, normalization, endpointing and device-event parsing.
- `outputs/`: audio playback/artifacts and simulated output.
- `providers/`: OpenAI inference/Decisions, optional TypeSafe and SQLite persistence.
- `cli/`: startup composition, arguments, task/resource ownership. The launcher
  remains `pragyantra.cli:main` for both `prag` and `pragyantra`; command-family
  modules keep wiring readable. `.env` loads from the current directory at command
  execution, before model defaults: flags > shell > env file > defaults. Never
  search ancestors or load credentials on import/help/version. `--env-file` and
  `--no-env` work before/after commands. See `docs/cli.md`.
- `tests/`: deterministic component, SDK contract, lifecycle and CLI coverage.
- `docs/`: architecture, execution guides, history, retirement audit and experiments.
- Root `LICENSE`: existing GNU GPL version 3; preserve licensing and attribution.

Application code must not import concrete inputs/outputs/providers, SDKs, hardware
libraries or historical code. Inputs/outputs/providers depend on application
values/interfaces; inputs and outputs receive provider capabilities by protocol.
Only startup wiring imports all four packages. Keep small protocols and dataclasses
where behaviors need them, not a universal registry/plugin/service framework.
Imports must not open devices, load weights, start threads or call APIs. Manage
resources explicitly and separate acquisition from perception.

## Implemented behavior and constraints

`demo` uses a logical clock, simulated visual/touch observations and recorded text.
Touch requests current visual context with missing/stale handling. `see` normalizes
a PNG/JPEG/WebP file or captures one webcam frame, then explicitly uploads it to
OpenAI. `watch` continuously interprets selected webcam frames. `chat` integrates
text/audio input, optional background vision, scalar sensor events, bounded history,
explicit notes and optional speech. `application/runner.py:AssistantRunner`
coordinates typed input/results and optional background vision for both the CLI
and library hosts. Host code opens/closes provider/device contexts; the runner
owns its task group and active input iterator cleanup. It never constructs clients,
loads .env, prints or takes ownership of an event loop. See `docs/embedding.md` and
`examples/embed_assistant.py`. `listen`, `speak`, `devices`, `memory` and `calc`
provide focused entry points. Bare `listen` selects microphone; bare `speak TEXT`
selects playback. `--camera`/`--webcam` accept an optional index (default 0), and
`--memory` an optional path (data/notes.sqlite); these capabilities remain opt in.
See README and execution guides for flags.

Keep these semantics unless a requirement explicitly changes them:

- `WorldState` retains one newest acquired scene and at most 32 scalar channels.
  It is not tracking, mapping, identity recognition or a complete world model.
  Preserve acquisition/receipt/snapshot/response distinctions. Reject future
  evidence; older/equal acquisitions do not replace new ones. Freshness includes
  perception delay up to snapshot time; generated replies add unbounded semantic
  delay and do not re-evaluate wording at playback.
- Images normalize to at most 1024 pixels on the longest edge. Provider detail
  changes API preprocessing, not that normalization limit. File acquisition is not
  the historical photo capture time unless explicitly supplied. No confidence is
  invented. Vision uses low detail/no reasoning/short output/store=False/no retries.
- Continuous camera capture owns open/read/release on one worker, replaces one
  pending raw frame, and normalizes only selected frames. Vision inference is
  serial, paced after result handling. Native driver calls can delay shutdown.
- `watch --temporal-context` is opt in. Pass one flat previous scene only for the
  same source, advancing acquisition time, gap <=30 s by default, description
  <=1000 chars. Never nest context or use response time as frame gap. Label prior
  text as untrusted; current image wins. No quality improvement has been shown.
- The reusable runner runs foreground turns plus optional background vision in a task group and
  waits for the first visual result at startup. Failures stop/cancel siblings;
  context managers release resources on completion, partial startup and failure.
  Stdin sensor records wait behind foreground turns/output; no priority sensor
  multiplexer, parallel conversation, automatic reconnect or retries exist.
- Voice is half duplex: input closes before ASR, conversation and playback. A
  64-block microphone queue fails on overflow. RMS endpointing is a heuristic,
  not neural VAD. PCM/WAV limits and timeouts are explicit; no barge-in. Synthesis
  requests PCM to avoid streaming WAV headers; native adapters assume little-endian
  hosts. Speech is disclosed as AI-generated. Device operations can delay cancellation.
- History is bounded to complete exchanges (12 turns/24,000 chars). Notes are
  explicit, <=2000 chars, <=1000 records; SQLite persistence is opt in. Default
  recall is local keywords; opt-in semantic mode embeds new notes/queries, compares
  matching model/dimensions, and has an unevaluated 0.3 cosine threshold. No
  automatic transcript persistence, legacy pickle loading or silent backfill.
- Deterministic commands dispatch in code; generated conversation has no tools or
  actuator authority. Device JSONL is a strict version-1 observation boundary with
  explicit units/timestamps, not a selected physical transport or controller.
- `RequestRouter` optionally interprets natural requests. Only conversation and
  latest-scene reporting have handlers. Follow/mission/natural remember are
  unsupported; slash commands bypass Jev. Low confidence/probability asks for
  clarification; invalid/service failures emit provider_failure without fallback
  or a history entry. Inspection checks freshness after interpretation. Judgment
  provenance/distribution and acquisition/completion times remain explicit.
  Thresholds are initial policy, not calibrated accuracy. `/stop` ends only the
  local runner and waits behind foreground work/initial vision; it is no physical
  stop guarantee. See `docs/request-interpretation.md`.
- `ImageInspector` evaluates 1–16 configured predicate/choice/score questions over
  one image through `InspectionProvider`. It preserves a normalized-byte evidence
  hash, acquisition/request/completion times, definitions/versions, provider/model
  and returned uncertainty/usage. Check `status_at` when consuming: pre-call stale
  evidence skips inference; post-call/queued delay can stale a successful result.
  Refusals remain explicit, malformed batches fail closed, no captions or scalar
  channels carry these judgments. `inspect` is explicit; no per-frame automatic
  judgment fan-out, robot actions or reference-image store exists.
- Companion entries are explicit names/preferences/named observations, at most 32
  keys with 512-character values. `profile` and `/profile` update them; `--memory`
  persists chat context via schema-3 SQLite alongside preserved notes/embeddings.
  Snapshots sent to conversation remain separate from current sensory evidence.
  No automatic extraction, station coordinates, calibration or image collections.

Manual file/webcam vision smoke checks were reported successful on October 20,
2026. The synthetic hosted TTS/ASR/semantic-conversation check also passed; see
`docs/experiments/`. Actual microphone/speaker operation, sustained capture,
representative model evaluation, control timing and Pi deployment remain unverified.
The first 22-case synthetic live Jev check is recorded separately in
`docs/experiments/2026-10-21-request-interpretation.md`; it is not representative
robot-command or hardware validation.
Synthetic Decisions and companion-persistence live checks are also documented in
the October 21 experiment logs. Their simple inputs do not establish real object,
station or broad personalization accuracy. Evaluation scripts default to offline
validation; `--live` explicitly selects hosted calls.
Keep all status documentation aligned with new evidence and limitations.

## Validation and data handling

```bash
uv sync --locked --all-extras
uv run pragyantra --help
uv run pragyantra --version
uv run pragyantra demo --json
uv run --locked --all-extras pytest -q
uv run ruff check .
uv run ruff format --check .
uv build
git diff --check
```

Use focused tests for implemented behavior, fake services/devices, synthetic
pixels/audio, temporary databases, logical clocks and explicit synchronization.
Normal tests need no credentials, hardware, paid calls or downloads. Base tests
skip optional OpenCV capture conversion; all-extras runs include it. Async tests
use `asyncio.run`. Do not test empty scaffolding or invent performance numbers.
Report verification and outstanding hardware/model checks accurately.

Keep credentials, weights, recordings and personal memory out of commits.
`.env`, `.env.*` except `.env.example`, `models/`, `memory_stream/`, `data/`, and
`*.pkl` are ignored. Filesystem-action tests operate only on temporary fixtures.
Never run historical installers or load legacy serialized Python objects. No CI
workflow exists; local automated checks and documented manual experiments are
separate evidence.
