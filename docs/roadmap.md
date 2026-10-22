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

Bounded request interpretation is opt in; typed robot behavior requests remain
planned. Conversation uses explicit commands and a generative provider without
model-generated tool execution.

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

**First slice implemented:** optional TypeSafe Jev interpretation selects among
`conversation`, `inspect`, `follow`, `run_named_mission`, `remember`, and `unknown`.
Only conversation and reporting an existing current scene have handlers. The other
action intents return unsupported; uncertainty asks for clarification and provider
failure selects no behavior. See [request interpretation](request-interpretation.md).

A model-selected intent is not an executable request. Application code must
validate capability, known mission/target identifiers, bounded arguments and
ambiguity before producing a typed behavior request. Rover accepts/rejects that
request using its own state, ownership and execution policy. Distinguish unclear
input, unsupported requests, refusal and provider failure. Do not turn failures
into accepted requests or conversational claims of execution.

Explicit control commands bypass semantic inference. Rover must enforce stop and
command expiry independently of a blocked conversation/provider call. TypeSafe's
[function-selection cookbook](https://docs.typesafe.ai/cookbooks/function_calling)
is the design reference. The optional SDK is integrated for closed-set selection;
no free-text argument extractor or typed robot behavior request exists yet.

Completion criterion: representative requests produce validated outcomes,
ambiguity has a defined response and failures cannot produce executable requests.
Fake-provider/SDK tests cover those software paths. The initial live 22-case
synthetic check recorded 21 matching intents and one invalid result rejected
without a route. Broader independent evaluation remains outstanding.

## C — Direct inspection judgments

**Implemented:** explicit target/condition predicates, named-station choices and
ordered scores directly over images, exposed through `ImageInspector` and
`prag inspect`. OpenAI's
[Decisions documentation](https://developers.openai.com/api/docs/guides/decisions)
defines the integrated provider contract. No conversation caption is used as a
substitute for pixels. See [inspection](inspection.md).

Measurements, model judgments and generated descriptions remain distinct values.
Judgments need evidence references, acquisition/completion times, question/criteria
version, provider/model and the uncertainty fields actually returned. Check age
when consuming a result, including delay after inference. Scalar measurement
channels must not silently hold inferred facts.

Completion criterion: stale results can be rejected and image judgments can be
evaluated independently of conversational wording.

Tests establish pre-call, post-call and delayed-consumption stale rejection, future
evidence rejection, refusal/invalid/error handling and SDK payload/cleanup. The
[live eight-image check](experiments/2026-10-21-direct-inspection.md) exercised all
three question types with synthetic shapes; real station/object accuracy remains
unmeasured. Conversational `inspect` retains its existing latest-caption behavior;
configured direct questions use the separate command/library API.

## D — Companion context

**Implemented:** explicit notes plus bounded names/preferences and named
observations, using opt-in SQLite persistence in chat. `profile` and `/profile`
provide deterministic set/list/delete operations; conversation receives a separate
saved-context snapshot. See [companion context](companion.md).
Station coordinates, routes and robot calibration belong in Rover. Add a separate
reference-image artifact mechanism
only when a comparison feature requires it.

Completion criterion: explicit personalization survives restart and remains
separate from current sensory evidence.

Cross-process tests and a [synthetic live interaction](experiments/2026-10-21-companion.md)
verify persistence and use of the saved name. Current visual/scalar evidence stays
independent. No image-comparison feature was introduced, so no artifact store is
needed for this milestone.

## E — Evaluation throughout

**Existing foundation:** normal tests use fake providers, synthetic images/audio,
logical clocks and guarded device/network access. Live hosted smoke checks are
recorded separately. A curated text fixture and explicit live Jev evaluation
script accompany B; an eight-image synthetic fixture/script accompanies C. See the
[first request experiment](experiments/2026-10-21-request-interpretation.md).
Inspection reports false positives/negatives, decision coverage, station matches,
refusals/failures/stale results, median/p95 latency and usage. Optional supplied
rates estimate cost for reported usage; the live inspection write-up also records
a base-rate estimate per batch, with billing and hardware timing limits explicit.

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

## Current boundary

The A–E software foundation is implemented and locally validated. Continuing
evaluation on real observations is ongoing engineering work, not evidence of a
finished robot. Following, mission execution, physical transport and typed rover
behavior requests require concrete rover interfaces and remain outside this
foundation. No hardware target or reference-image comparison feature was selected.

Validation on October 21, 2026: 301 automated tests passed with all extras, including
against the built wheel outside the checkout; the base wheel passed 275 with two
optional modules skipped. Ruff, package build, CLI/demo and offline example checks
passed. See the [test map](../tests/README.md). These are local software checks;
there is no CI workflow or new physical-device validation.
