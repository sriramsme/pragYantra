# Bounded request interpretation

Request interpretation is an opt-in step before ordinary conversation. Jev selects
an intent; application code decides which existing behavior can handle it. It
does not generate tool calls, arguments, code or robot commands.

## Try it

Install the optional dependency and add `TYPESAFE_API_KEY` to your ignored `.env`:

```bash
uv tool install --editable '.[audio,webcam,decisions]' --python 3.12
prag interpret 'What do you see?' --json
prag chat --interpret --camera
```

For locked development, use `uv sync --locked --all-extras` and
`uv run --extra decisions prag interpret 'What do you see?' --json`.
The standalone `interpret` command only returns a judgment and proposed handling
status. It does not open a camera, construct an OpenAI client or perform a behavior.
`chat --interpret` routes text, transcribed audio and text events through that same
interpretation. Ordinary `chat` keeps its existing behavior.

The default is `jev-1.14.0`. Override with `--decision-model` or
`PRAGYANTRA_DECISION_MODEL`. Chat uses `--decision-timeout` (default 10 seconds);
standalone interpretation uses `--timeout`. Retries are disabled. Conversation,
vision and audio still use their existing OpenAI providers and settings. Chat
therefore needs both keys; the standalone judgment command only needs TypeSafe.
`--commands-only` cannot combine with `--interpret`.

## Read these three files

1. `application/requests.py` defines `IntentJudgment`, `RequestResult`, the small
   interpreter protocol, and `RequestRouter`. The router applies thresholds and
   selects a supported handler using ordinary Python conditions.
2. `providers/typesafe.py` defines the six options, calls the SDK, validates the
   response and converts it into application values. SDK details stay here.
3. `application/runner.py` accepts an optional router. Exact `/stop` and other
   slash commands bypass semantic interpretation. `cli/assistant.py` constructs
   the optional provider/router and renders results.

```text
TextObservation → Jev judgment → application rules → typed RequestResult
                                      ├─ conversation → existing session
                                      └─ inspect → current scene snapshot
```

The provider judges only the current request text. It does not receive conversation
history, notes or images. References that need earlier turns can require
clarification; no multi-turn intent-resolution mechanism has been implemented.

## Supported outcomes

| Selected intent | Application behavior when sufficiently certain |
| --- | --- |
| `conversation` | Existing conversation provider, history and note recall |
| `inspect` | Report the latest visual description, or explicit stale/missing evidence |
| `follow` | `unsupported`; no executable request |
| `run_named_mission` | `unsupported`; no mission selection or executable request |
| `remember` | `unsupported`; suggest the deterministic `/remember TEXT` command |
| `unknown` | Explain that no single supported request was identified |

The initial policy requires confidence >=0.7 and selected probability >=0.75.
Below either threshold the status is `needs_clarification`. These are starting
values, not calibrated guarantees. TypeSafe's confidence is derived from its
probability distribution; it is not an independent quality measurement or
permission to act. See the official [Choice](https://docs.typesafe.ai/primitives/choice)
and [confidence](https://docs.typesafe.ai/confidence) documentation.

An inspection reads existing scene evidence **after** interpretation completes,
so Jev latency counts toward freshness. It does not capture a new frame, answer an
arbitrary visual question or judge an image directly. Without background vision or
host-supplied visual evidence, the result is unavailable. This is separate from
the planned direct image judgments in Phase C. Inspection does not add a synthetic
conversation exchange or touch event.

## Failure, provenance and control

Validated judgments retain all six probabilities, confidence, provider, actual
response model, question version (`intent-v1`) and input-token usage when supplied.
Results retain input acquisition/provenance, judgment completion and response time.
Inspection also retains the exact environment snapshot and scene status; routed
conversation retains its existing full result. CLI JSON exposes these fields.

An API error, timeout or invalid answer produces `provider_failure`, with no
generative fallback, selected behavior or history entry. The stream can accept
another request. Missing configuration fails startup. Cancellation propagates;
ordinary conversation, background perception and output failures still terminate
the runner. No documented refusal-specific answer is assumed: missing or
unrecognized answer shapes fail validation.

Exact `/stop` ends the local runner session after emitting a stopped result and
closing its input iterator/background task. It sends no rover command. It runs
in the serial foreground stream, waits behind a current turn/output and, with a
camera, behind initial visual readiness. It is **not** a priority stop channel or
an emergency stop. Rover must independently enforce physical stopping and expiry.
All slash commands bypass Jev; generated conversation has no actuator authority.

## Evaluate explicitly

```bash
# Validate the curated cases locally; no API calls.
uv run examples/evaluate_intents.py
# Explicit paid evaluation of synthetic text only.
uv run --extra decisions examples/evaluate_intents.py --live
```

`tests/fixtures/intent_requests.json` contains 22 labeled cases, including negation,
quotations, hypotheticals, compound requests and unsupported actions. The live
script reports per-case outcomes, invalid/service failures, incorrect accepted
routes, clarification count, median/p95 latency and reported input tokens. Dollar
cost is left unknown rather than inferred from a billing balance. It does not
exercise OpenAI conversation, images, audio devices or robot execution.

Normal tests use fake judgments and the real SDK over mocked HTTP. They establish
policy, payload and cleanup behavior; they do not measure model accuracy. The
[first live experiment](experiments/2026-10-21-request-interpretation.md) records
the small initial evaluation and its limitations. Broader independent cases and
repeated trials are needed before selecting thresholds for deployment.
