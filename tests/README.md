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
- `test_cli.py`: runnable JSON evidence and freshness argument validation.
- `test_image_input.py`: format/content validation, size limits, orientation,
  metadata removal, transparency, and capture-time semantics.
- `test_openai_vision.py`: actual SDK requests over an in-memory HTTP transport,
  response normalization, refusals, timeouts, cancellation, and sanitized errors.

Use simulated observations, fake providers, and temporary storage for normal tests.
They should run without model downloads, credentials, network access, or devices.
Pytest and the SDK-compatible HTTP test transport are development dependencies
managed through `uv`. Async tests use the
standard-library event loop; no additional async test plugin is needed.

Provider/device integration tests must be explicitly selected and document their
setup and any API costs. No live integration tests exist yet. SDK contract tests
make no network calls. Test collection is scoped to `tests/`,
keeping the legacy prototype outside normal runs.
