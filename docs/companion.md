# Explicit companion context

Companion context holds names, interaction preferences and named observations you
explicitly save. It supplements free-text notes. It is separate from current
visual/sensor evidence and has no routing, actuator or calibration authority.

```bash
prag profile set name user Casey
prag profile set preference interaction_style 'Keep replies concise'
prag profile set observation desk 'Wooden desk with a blue lamp'
prag profile list
prag chat --memory
prag profile delete observation desk
```

The standalone `profile` command stores entries in `data/notes.sqlite` by default.
Use `profile --database PATH ...` and `chat --memory PATH` for another database.
These local commands need no API key. Names such as Casey here are synthetic
examples. Do not commit real personal context or the runtime database.

Within chat, the same explicit operations are available:

```text
/profile name user Casey
/profile preference interaction_style Keep replies concise
/profile observation desk Wooden desk with a blue lamp
/profile
/unprofile observation desk
```

Without `--memory`, chat keeps context only for that session. With `--memory`,
SQLite preserves it across restarts alongside notes. `/reset` clears conversation
history while retaining saved context and notes. Slash commands bypass Jev and
do not require generation; natural-language note saving remains unsupported by
the request router. No transcript mining or implicit preference extraction occurs.

Entries use `(kind, key)` as their identity and retain their explicit update time.
There are at most 32 entries total, each with a short key and up to 512 value
characters. Updating an entry replaces its value; older updates are rejected.
Deleting a context entry does not erase it from earlier in-memory conversation
turns; use `/reset` too when needed. Notes and context have independent capacities.
If `/profile` would exceed the chat reply budget, it shows 40-character value
previews with an explicit `truncated` flag. Standalone `profile list` returns full
entries; stored values and the conversation snapshot are not truncated.

Before conversational generation, `ConversationSession` takes a bounded companion
snapshot and supplies it separately from the environment and retrieved notes.
The OpenAI adapter labels it as user-saved context, never current sensory facts.
Conversation JSON retains exactly that companion snapshot. A saved description of
a desk does not establish that the desk is currently visible, located nearby or
unchanged. Names are preferences/context, not visual identity recognition.

Read `application/companion.py` for the values and in-memory implementation,
`providers/companion.py` for SQLite operations, and the profile branches in
`application/commands.py` for deterministic commands. `SQLiteNotes.companion`
shares its owning connection; closing the note store also ends context access.
Schema version 3 adds a companion table while preserving existing version 1/2
notes and embeddings. No legacy Python serialization is loaded.

Station coordinates, routes, controller limits and robot calibration belong in
Prag Rover. This feature saves text descriptions only. It does not add image
collections or a reference-image artifact store; those should be introduced only
for an actual comparison feature. The [synthetic live check](experiments/2026-10-21-companion.md)
documents one persisted-name interaction, not a broad personalization evaluation.
