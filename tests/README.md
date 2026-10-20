# Tests

No behavior tests exist yet because the new implementation is a package scaffold.
Add focused tests with the first implemented behavior rather than tests for empty
packages or the CLI help text.

Use simulated observations, fake providers, and temporary storage for normal tests.
They should run without model downloads, credentials, network access, or devices.
Introduce pytest through `uv add --dev pytest` when those tests are added.

Provider/device integration tests must be explicitly selected and document their
setup and any API costs. Keep the legacy prototype outside test collection.
