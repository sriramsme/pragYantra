# Embed the assistant in Python

`application/runner.py:AssistantRunner` runs typed input handling and optional
background vision without invoking the CLI or a subprocess. The existing CLI now
uses this same runner. It does not select hardware, construct API clients, load
`.env`, print output, install signal handlers, or start its own event loop.

## Run the complete example

From the repository checkout:

```bash
uv run examples/embed_assistant.py
```

Expected output:

```text
Fixture reply: A solid blue square.
Image source closed: True
```

[The example](../examples/embed_assistant.py) generates a blue image in memory,
uses fake vision/conversation providers and supplies a typed text observation.
It makes no hosted calls and accesses no real camera/microphone. Its description
is fixture data, not evidence of image-recognition quality.

## Construct a runner

The essential shape is:

```python
from pragyantra.application.runner import AssistantRunner

# The host constructs a ConversationSession and opens its providers/source.
async with image_source_context as images:
    runner = AssistantRunner(
        session,
        image_source=images,
        vision=vision_provider,
    )
    await runner.run(observations(), on_result=receive)
```

`observations()` is an async iterable of `AssistantInput`; `receive(result)` is
an async function taking `AssistantResult`. The complete runnable example defines
both. The host awaits `run` inside its existing event loop. Background image input
is optional; supply both `image_source` and `vision`, or omit both.

| Input value | Handling / result |
| --- | --- |
| `TextObservation` | Conversation or an existing explicit command → `ConversationResult` |
| `TextObservation` with optional `router` | Natural request → `RequestResult`; slash commands bypass routing |
| Exact `/stop` text | Emit stopped `RequestResult`, then end the run |
| `SensorObservation` | Update the latest scalar channel; no emitted result |
| `VisualObservation` | Update already-interpreted scene evidence; no emitted result |
| `TouchObservation` | Apply the freshness policy → `ContextResponse` |

Results are typed Python values. The host decides whether to display, serialize,
persist, synthesize or transmit them. The runner does not keep a result history
or output queue. Awaited output applies backpressure to foreground input. If an
output callback plays speech, the next input is not requested until it finishes.

For opt-in interpretation, open a `RequestInterpreter` provider in the host, wrap
it with `RequestRouter`, and pass `router=router` to `AssistantRunner`. Keep that
context open until `run` finishes. The application router depends only on the
protocol; see [request interpretation](request-interpretation.md). It reports
invalid/service judgments as typed results and can accept the next observation.
With injected clocks, supply the same clock to the router, session and runner.

## Ownership and shutdown

| Resource / work | Owner |
| --- | --- |
| Provider clients, camera/device contexts, database, transport | Host; open before `run`, close after it finishes |
| Conversation history and world state | Supplied `ConversationSession` |
| Foreground handling and background perception tasks | Runner |
| Active input iterator | Runner closes it if it offers `aclose` |
| Input resources acquired inside an async generator | Generator's `finally` / context managers |
| Rendering, playback and output resources | Host's awaited result callback and contexts |

A configured camera produces one visual result before the runner starts consuming
foreground input. Perception then continues independently, with serial requests
and the existing delay after each result. It updates `session.state`; a running
conversation retains the snapshot taken at its request start. There is no temporal
prompt context in this path; that remains opt in on standalone `watch`.

Input EOF completes normally. Input, capture, perception, generation or output
failure ends the run. Background failure cancels a blocked input/turn/output;
foreground completion/failure cancels perception. The runner waits for its task
group and closes an active input generator before returning. Cancellation propagates.
A single error propagates directly; multiple task failures remain an
`ExceptionGroup`, so a library caller can inspect every error. The CLI retains
its existing concise error presentation.

The runner deliberately leaves supplied provider/device/database contexts open.
Wrap the awaited call in the host's `async with` / exit stack so those contexts
also close after failure or cancellation. An input iterator without `aclose` has
no extra cleanup contract; its external resources must be managed by the host.
A failed `__aenter__` remains the resource implementation's cleanup responsibility.
Native driver operations can still delay cancellation and release.

Concurrent calls to the same runner are rejected. Sequential runs are allowed and
retain the supplied session's history/state; a camera-enabled run waits for a new
initial visual result each time. Use separate sessions/runners for independent
conversations. The host remains responsible for admission/backpressure if serving
many callers; this API does not create an unbounded request queue.

## Timing, audio and integration limits

Input acquisition times are preserved and future observations are rejected.
The runner accepts `now` and `sleep` functions for deterministic tests; pass the
same clock to `ConversationSession` when injecting one. Existing freshness and
snapshot semantics apply. See [assistant execution](assistant.md).

For audio, the host acquires `AudioClip` and uses `TranscriptionProvider` to obtain
`TextObservation` before yielding it. A result callback can use a speech provider
and output adapter. These remain separate capabilities; the runner does not assume
local PortAudio, phone playback, or a specific transport. The CLI supplies its
existing half-duplex implementation without changing audio behavior.

A rover gateway can supply an `ImageSource`, translate telemetry into observations,
and receive typed results. This milestone adds no network camera transport,
mission execution, priority stop channel, actuator access,
or hard real-time guarantees. Foreground sensor events still wait behind busy
turns/output. Rover motion supervision and stopping must be independent of this
conversational stream. See the [implementation roadmap](roadmap.md).
