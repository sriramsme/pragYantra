# Implementation direction

PragYantra supplies reusable perception, semantic judgments and interaction.
Prag Rover supplies embodiment, robot-specific execution and physical validation.
The current integration point is the [application runner](embedding.md).

Intended flow:

```text
Text / audio / images / sensor observations
                    ↓
          Timestamped application state
                    ↓
       Bounded semantic judgments
                    ↓
      Application rules and behavior selection
                    ↓
Conversation, observation results, or a typed behavior request
```

The judgment/behavior-request stages are planned. Existing conversation uses
explicit commands and a generative provider without model-generated tool execution.

## A — Embed existing capabilities

**Implemented:** `AssistantRunner` consumes typed observations, coordinates optional
background vision with the supplied session, and awaits typed result handling.
The CLI uses it; `examples/embed_assistant.py` demonstrates Python embedding with
synthetic images and fake providers. Tests cover readiness, concurrent perception,
backpressure, context, failure, cancellation, iterator cleanup and host ownership.

Completion criterion: a small program supplies an image source/text observations,
receives results and shuts down cleanly without a CLI subprocess. This is software
integration evidence, not a rover deployment or hardware validation.

## B — First decision-model behavior

**Planned:** request interpretation using a bounded vocabulary such as
`conversation`, `inspect`, `follow`, `run_named_mission`, `remember`, and `unknown`.
Start with one working behavior/provider; add capabilities when they exist.

A model-selected intent is not an executable request. Application code must
validate capability, known mission/target identifiers, bounded arguments and
ambiguity before producing a typed behavior request. Rover accepts/rejects that
request using its own state, ownership and execution policy. Distinguish unclear
input, unsupported requests, refusal and provider failure. Do not turn failures
into accepted requests or conversational claims of execution.

Explicit control commands bypass semantic inference. Rover must enforce stop and
command expiry independently of a blocked conversation/provider call. TypeSafe's
[function-selection cookbook](https://docs.typesafe.ai/cookbooks/function_calling)
is a design reference for known handlers and closed-set arguments; it is not an
integrated dependency or a general free-text argument extractor.

Completion criterion: representative requests produce validated outcomes,
ambiguity has a defined response and failures cannot produce executable requests.

## C — Direct inspection judgments

**Planned:** target visibility, named-station matching and specific inspection
conditions over image evidence. OpenAI's
[Decisions documentation](https://developers.openai.com/api/docs/guides/decisions)
is a candidate provider reference; no decision provider is integrated yet.

Measurements, model judgments and generated descriptions remain distinct values.
Judgments need evidence references, acquisition/completion times, question/criteria
version, provider/model and the uncertainty fields actually returned. Check age
when consuming a result, including delay after inference. Scalar measurement
channels must not silently hold inferred facts.

Completion criterion: stale results can be rejected and image judgments can be
evaluated independently of conversational wording.

## D — Companion context

**Partly available:** explicit notes already persist through SQLite with optional
semantic recall. Structured names/preferences, interaction style and named
observations remain future behavior. Station coordinates, routes and robot
calibration belong in Rover. Add a separate reference-image artifact mechanism
only when a comparison feature requires it.

Completion criterion: explicit personalization survives restart and remains
separate from current sensory evidence.

## E — Evaluation throughout

**Existing foundation:** normal tests use fake providers, synthetic images/audio,
logical clocks and guarded device/network access. Live hosted smoke checks are
recorded separately. Decision-model evaluation remains planned alongside B/C.

Build representative text cases and recorded/synthetic image fixtures. Include
negation, quoted/hypothetical commands, missing targets and compound requests.
Measure intent-selection errors and incorrect accepted behavior requests,
inspection false positives/negatives, median/tail latency, timeouts/refusals,
stale rejection and cost per behavior. Use labeled cases to select thresholds;
provider uncertainty fields are not proof of correctness or permission to act.

Batch independent questions when useful; dependent questions may need later
requests and new evidence. Do not run every judgment for every observation.
Normal tests remain credential-free; live provider evaluations must be selected
explicitly and record inputs, settings, outcomes and limits.
