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
setup and any API costs. No live integration tests exist yet. SDK contract tests
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
- `test_assistant_cli.py`: subprocess note persistence/calculation and JSONL events;
  integrated fake camera + audio + conversation + speech, half-duplex ordering,
  startup/perception/output failure and cancellation cleanup.

A synthetic paid-service smoke check is documented in
[the experiment log](../docs/experiments/2026-10-20-assistant-smoke.md); it is not
an automatically executed test or evidence of physical audio-device performance.
