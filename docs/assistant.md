# Assistant execution

`chat` integrates current sensory evidence, recent exchanges, explicit notes, and
a conversation provider. `demo`, `see`, and `watch` remain independent inspection
commands. Processes do not share world state. The reusable `AssistantRunner`
coordinates turns/perception; `cli/assistant.py` constructs resources, supplies
observations and formats results. See [Python embedding](embedding.md) for use
without a CLI subprocess.

Add `--interpret` for optional Jev request routing before conversation. Only
conversation and reporting the latest scene have handlers. Uncertain requests
ask for clarification; failed judgments select no behavior. See
[request interpretation](request-interpretation.md) for setup, JSON and limits.
The ordinary turn sequence below applies when routing is disabled or selects
conversation. Slash commands always bypass interpretation.

## Choose inputs

```bash
prag chat
prag chat --message 'Hello' --message 'And now?' --json
prag chat --audio data/utterance.wav --json
prag chat --voice --count 2
prag chat --camera
```

Text defaults to UTF-8 stdin. `--message` and `--audio` can repeat for finite
conversations. These modes and `--voice` are mutually exclusive. `--events` reads
structured stdin records instead; see [device events](device-protocol.md).
Linux terminal/pipe reads are cancellable without a permanently blocked `input()`
thread. Lines are limited to 16 KiB; user messages to 4,000 characters.

`--camera` (alias `--webcam`) adds an independent vision task and waits for its first result before
handling the first user turn. The camera continues capturing during conversation;
vision inference stays serial. `--vision-interval` is a delay after a result,
default five seconds, not a guaranteed rate. Chat uses independent descriptions;
the temporal experiment belongs to `watch`.

## Follow one turn

1. Acquisition creates `TextObservation` with source and acquisition time. For
   audio, transcription preserves that time and adds provider/model provenance.
2. `ConversationSession` serializes turns with a lock and takes an immutable
   `WorldState` snapshot. It retains one latest visual description and at most 32
   scalar channels, keyed by `(source, kind)`. Older/equal acquisitions cannot
   overwrite the retained value.
3. `/commands` dispatch in code. Ordinary conversation retrieves up to three
   relevant explicit notes and passes those, the snapshot, and bounded recent
   exchanges to `ConversationProvider.respond`.
4. `OpenAIServices` builds a Responses request. Context and notes are labeled as
   untrusted evidence. No model-generated function calls or physical actions are
   enabled. Returned text is validated before entering history.
5. The CLI prints immediately. `--speak` then synthesizes and plays the reply,
   chunking at whitespace into at most 1,000 characters per synthesis request.
   Output is awaited; there is no accumulating speech queue.

A snapshot records its `as_of` time and acquisition-based ages, with `current` or
`stale` per reading. Missing visual context is null. The default freshness limit
is five seconds, inclusive; set `--context-max-age` to change this policy. The
snapshot includes all acquisition/perception delay up to request start. A model
reply takes additional time: freshness is **not re-evaluated inside a generated
answer**. JSON also records `responded_at`, so do not mistake the snapshot for a
physical guarantee at playback time. This path cannot make timing-critical decisions.

JSON output records input provenance, response provenance/time, the exact sensory
snapshot supplied, and recalled note IDs. It can contain sensitive text or scene
descriptions; the application prints it rather than creating a session log.

## Commands and history

| Command | Behavior |
| --- | --- |
| `/context` | Show timestamped visual/sensor evidence and freshness |
| `/remember TEXT` | Add an explicit note, maximum 2,000 characters |
| `/recall QUERY` | Recall up to three notes; an empty query lists recent notes |
| `/forget ID` | Delete that note from the repository |
| `/reset` | Clear conversation history; retain notes and sensory state |
| `/help` | Show commands |
| `/quit`, `/exit` | Exit text input |
| `/stop` | End the local runner session; send no physical stop command |
| `/profile [KIND KEY VALUE]` | List or set explicit names, preferences or named observations |
| `/unprofile KIND KEY` | Remove explicit companion context |

`--commands-only` disables hosted capabilities and accepts deterministic commands.
It cannot combine with audio, webcam, spoken output, semantic memory or interpretation.

History retains complete exchanges within 12 turns and 24,000 characters. Failed
model responses do not enter history. `/reset` leaves history empty. Forgetting a
note does not erase text already present in recent exchanges; reset history too
when needed. Full conversation history is never persisted automatically.
Companion context is bounded separately and persists with `--memory`; see
[saved context](companion.md). Conversation JSON includes the exact saved-context
snapshot supplied to the provider, separate from current sensory evidence.

## Provider and lifecycle choices

Conversation defaults to `gpt-5.6-luna`, reasoning `none`, 512 output tokens,
`store=False`, no tools and no retries. Models and audio settings can be changed
with command flags or `.env.example` variables. The selected model must support
the requested modality/settings; the application does not silently substitute one.

Chat uses a default 30-second per-request deadline, configurable with `--timeout`.
This does not bound device acquisition, a complete voice turn, or native shutdown.
Source, conversation/vision provider and output failures stop the session. Optional
interpretation failures instead emit `provider_failure` and allow another request.
A task group cancels ongoing
foreground work if background perception fails, and cancels perception when input
ends or Ctrl+C occurs. The application runner owns that task group and input
iterator cleanup. The CLI's exit stack closes acquired resources in reverse order.
A failure during partial startup closes resources already acquired. Device
workers finish active native operations before release; blocked drivers can delay it.

There is no barge-in, parallel conversation generation, reconnect/retry loop,
identity tracking, action planner, autonomous actuation, or full environment model.
