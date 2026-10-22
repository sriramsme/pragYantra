# Tests

Run the tests from the repository root:

```bash
uv run pytest -q
```

- `test_visual_context.py`: missing/current/stale responses, acquisition and
  processing time, delayed observations, receipt ordering, and empty input.
- `test_runtime_lifecycle.py`: input/output failures, partial startup, and
  cancellation. Tests use async context managers and explicit synchronization;
  they do not simulate time with wall-clock sleeps.
- `test_cli.py`: runnable JSON evidence, freshness/source argument validation,
  webcam wiring, and missing optional dependency errors.
- `test_image_input.py`: format/content validation, size limits, orientation,
  metadata removal, transparency, and capture-time semantics.
- `test_openai_vision.py`: actual SDK requests over an in-memory HTTP transport,
  response normalization, refusals, timeouts, cancellation, and sanitized errors.
- `test_webcam_input.py`: real OpenCV conversion on synthetic pixels, fake camera
  read/open failures, timestamp semantics, and device release. Run with
  `uv run --locked --extra webcam pytest -q`; base tests skip this optional module.
- `test_webcam_stream.py`: latest pending frame replacement, device thread
  ownership, startup/read failure, cancellation, and release order using fake
  devices. Runs without OpenCV and uses events rather than wall-clock sleeps.
- `test_observation_loop.py`: serial inference, pacing after output, bounded
  counts, context updates, acquisition timing, and cancellation with logical clocks.
- `test_watch_cli.py`: output visible before the next request, finite completion,
  failure cleanup without retries, interval/count validation, and temporal-context
  options/evidence.
- `test_temporal_context.py`: opt-in selection, acquisition-time gaps, size/source/
  time boundaries, flat context snapshots, and validation before provider calls.
  The mocked SDK tests also check labeled context data and unchanged baseline prompts.

Use simulated observations, fake providers, and temporary storage for normal tests.
They should run without model downloads, credentials, network access, or devices.
Pytest and the SDK-compatible HTTP test transport are development dependencies
managed through `uv`. Async tests use the
standard-library event loop; no additional async test plugin is needed.

Provider/device integration tests must be explicitly selected and document their
setup and any API costs. Live checks use explicitly selected example scripts
outside pytest. SDK contract tests
make no network calls. Test collection is scoped to `tests/`,
without collecting historical code.

## Assistant, audio, memory and device boundaries

- `test_conversation.py`: sensory snapshots, recalled notes, bounded complete
  exchanges, deterministic commands, failed-turn atomicity and semantic recall.
- `test_notes.py`: in-memory/SQLite repositories, reopen, date bounds, forget,
  capacity, safe query text, schema migration and embedding compatibility/validation.
- `test_audio.py`: WAV/PCM validation, acquisition timestamps, energy endpointing,
  pre-roll, noise bursts and bounded utterances using synthetic samples.
- `test_audio_devices.py`: fake PortAudio capture/playback, overflow, failed start,
  cancellation and device close; no real microphones or speakers.
- `test_console.py`: cancellable pipe reads and restoration of stdin flags.
- `test_device_events.py`: strict version/type/field/unit/value/time validation.
- `test_openai_services.py`: actual SDK over mock HTTP for conversation, ASR, PCM
  synthesis and embeddings, with errors/timeouts and explicit request settings.
- `test_assistant_cli.py`: subprocess note persistence/recall and JSONL events;
  integrated fake camera + audio + conversation + speech, half-duplex ordering,
  startup/perception/output failure and cancellation cleanup.

A synthetic paid-service smoke check is documented in
[the experiment log](../docs/experiments/2026-10-20-assistant-smoke.md); it is not
an automatically executed test or evidence of physical audio-device performance.

- `test_cli_environment.py`: installed executable aliases, dotenv scope/precedence,
  alternate/no env files, lightweight help, camera/memory defaults and audio mode
  selection with fake handlers. `conftest.py` blocks real sockets and audio devices,
  disables project dotenv loading and removes ambient OpenAI/TypeSafe keys for normal tests;
  configuration tests explicitly enable only temporary env fixtures.

- `test_assistant_runner.py`: programmatic typed observations/results, initial
  vision readiness, concurrent perception with frozen conversational snapshots,
  output backpressure, caller-owned resources, input iterator cleanup, startup and
  mid-turn failure, cancellation, simultaneous errors and sequential reuse. The
  runnable embedding example is also checked without credentials or hardware.

- `test_request_interpretation.py`: typed judgments, uncertainty/capability rules,
  post-interpretation scene freshness, no fallback/history on failure, slash-command
  bypass, local `/stop` stream cleanup and cancellation using fake judgments.
- `test_typesafe_provider.py`: real optional SDK over mock HTTP; payload/provenance,
  invalid/missing answers, sanitized errors, no retries, timeout/cancellation and
  client cleanup. Run with `--extra decisions`; base tests skip this module.
- `test_request_cli.py`: standalone judgments without OpenAI construction, opt-in
  chat routing, result JSON, shutdown and credential-free evaluation fixture loading.

`fixtures/intent_requests.json` contains curated synthetic cases. Validate them
with `uv run examples/evaluate_intents.py`; only explicit `--live` calls TypeSafe.
See [the live experiment](../docs/experiments/2026-10-21-request-interpretation.md).
Fake-provider tests establish handling rules, not Jev accuracy.

- `test_inspection.py`: independent image judgment types, strict distributions,
  pre-call/post-call/consumption freshness, evidence provenance, errors/cancellation.
- `test_openai_decisions.py`: actual SDK over mock HTTP, batched predicate/choice/
  score payloads, malformed/refused responses, no retries, timeouts and cleanup.
- `test_inspection_cli.py`: normalized synthetic image input, question-file
  validation and failure before device acquisition.
- `test_companion.py`: bounded in-memory/SQLite context, update/delete, old-update
  rejection, schema-2 migration, resource lifetime and cross-process persistence.
  Conversation provider tests verify saved context stays distinct from sensors.
- `test_evaluation.py`: offline image-fixture validation and error/coverage/latency/
  cost calculations with synthetic records. `evaluate_inspections.py --live` is
  deliberately outside normal test execution; see [the log](../docs/experiments/2026-10-21-direct-inspection.md).
