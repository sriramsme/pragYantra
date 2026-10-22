# Synthetic companion persistence and routed conversation check

On October 21, 2026 (US/Central), a temporary SQLite database was populated through
separate `profile set` CLI processes with the synthetic name Casey and preference
“One brief sentence.” A later process ran `chat --interpret --memory PATH` with
“Hello! Please greet me by my saved name.” The temporary database was deleted after
the check. No personal context, device input or automatic transcript storage was used.

Observed behavior:

- Jev `jev-1.14.0` selected `conversation`.
- Application rules handed the request to the existing `gpt-5.6-luna` conversation
  provider with both persisted companion entries, separate from sensory evidence.
- The reply was “Hello, Casey!”
- Conversation JSON retained the exact companion snapshot used; the visual field
  was unavailable and scalar channels were empty.

The [synthetic result](2026-10-21-companion.json) records the judgment, reply and
context snapshot. This is one successful integration/persistence check, not a
representative personalization study, latency benchmark or proof that generated
conversation will always follow preferences. Deterministic tests cover replacement,
deletion, capacity, stale updates, schema migration and keeping saved observations
separate from current sensor state.
