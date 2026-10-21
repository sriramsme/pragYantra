# Working context and explicit memory

These are three distinct kinds of state:

| State | Lifetime and bound | Purpose |
| --- | --- | --- |
| `WorldState` | Current process; one visual scene and 32 scalar channels | Latest acquired sensory evidence, with freshness |
| `ConversationHistory` | Current session; 12 complete exchanges / 24,000 characters | Recent conversational continuity |
| Explicit notes | In-memory by default, or SQLite when selected; 1,000 notes | User-directed persistence and recall |

The assistant does not automatically turn transcripts, images, or statements in
model replies into durable facts. Explicit notes are untrusted remembered text,
not proof that a statement is true or a physical observation is still current.

## Keyword recall: default, local

```bash
prag memory --database data/notes.sqlite add 'The blue mug belongs to Alex'
prag memory --database data/notes.sqlite search mug
prag memory --database data/notes.sqlite list --limit 10
prag memory --database data/notes.sqlite search mug --since 2026-10-20T00:00:00Z
prag memory --database data/notes.sqlite forget 1
prag chat --memory data/notes.sqlite
```

Standalone `memory` operations never call a hosted API. In chat, `/remember`,
`/recall`, and `/forget` use the selected repository. Without `--memory`, notes
last only for the session. Ordinary conversation retrieves at most three matching
notes; JSON records their IDs. A missing match supplies no notes.

Notes contain an ID, text, timezone-aware creation time, and an optional embedding.
Text is limited to 2,000 characters; queries to 2,000 characters and the first 20
unique Unicode word terms. SQLite FTS5 ranks keyword hits, then creation time/ID;
the in-memory test repository uses overlap count, then time/ID. These are different
ranking methods, not a promise of identical ordering. Empty queries list recent
notes; punctuation-only queries produce no matches. Date filters are inclusive.
Search result limits are 1–100; chat uses three.

The SQLite provider owns connection lifetime and schema migration. It uses an
application ID, a versioned schema, parameterized queries, FTS insert/delete
triggers and a transaction around capacity checks/insertion. Embeddings are
validated JSON arrays, never pickle. Existing legacy HDF5/pickle stores are **not
imported**; reconstruct reviewed notes through explicit commands instead.

## Semantic recall: opt in

```bash
prag chat --memory data/notes.sqlite --semantic-memory \
  --message '/remember The blue mug belongs to Alex' \
  --message 'Who owns the blue drinking vessel?' --json
```

This makes an embedding API request for each new explicit note and each nonempty
recall/conversation query. The default is `text-embedding-3-small`; override with
`--embedding-model` or `PRAGYANTRA_EMBEDDING_MODEL`. The normal keyword mode makes
no embedding requests. See the official [embedding guide](https://developers.openai.com/api/docs/guides/embeddings).

The application normalizes finite, nonzero vectors (maximum 4,096 dimensions) and
compares cosine similarity across at most 1,000 notes. It only compares matching
model names and dimensions. Results need similarity at least 0.3 and are capped at
three in chat. This threshold is an initial heuristic, not calibrated relevance
or confidence. Similarity does not validate a remembered statement.

Only notes created with semantic mode have vectors. Older keyword-only notes are
not silently uploaded or backfilled, and incompatible model vectors are excluded.
Changing the embedding model requires deliberately re-adding notes for that model;
the default semantic mode does not fall back to keyword hits. Failed embeddings
stop the turn and do not store a partial note. Retrieval quality needs a larger
representative evaluation; one synthetic smoke example establishes integration only.

Database files contain personal text and derived vectors in plain local storage,
without encryption. They are not shared across sessions unless the same path is
chosen. `.gitignore` excludes `data/`; other locations remain the operator's
responsibility. `/forget` removes a row and its retrieval index entry, but does
not promise forensic deletion of SQLite free pages, backups, prior terminal output
or existing conversation history. `/reset` clears recent exchanges without
removing notes or sensory context. No long-term summarizer or forgetting scheduler
is implemented.
