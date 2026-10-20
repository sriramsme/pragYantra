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
  failure cleanup without retries, and interval/count validation.

Use simulated observations, fake providers, and temporary storage for normal tests.
They should run without model downloads, credentials, network access, or devices.
Pytest and the SDK-compatible HTTP test transport are development dependencies
managed through `uv`. Async tests use the
standard-library event loop; no additional async test plugin is needed.

Provider/device integration tests must be explicitly selected and document their
setup and any API costs. No live integration tests exist yet. SDK contract tests
make no network calls. Test collection is scoped to `tests/`,
keeping the legacy prototype outside normal runs.
