# Temporal context experiment

Status: implemented with logical-clock, CLI, and mocked SDK tests. Live operation,
accuracy, and latency of this mode have not been evaluated. Independent-frame
description remains the default.

## Run it

```bash
uv run --extra webcam --env-file .env pragyantra watch \
  --temporal-context --context-max-gap 30 --interval 5 --count 3 --json
```

Without `--temporal-context`, the command uses the original independent-image
prompt. `--context-max-gap` requires that flag and defaults to 30 seconds when
temporal context is enabled. It is an experiment setting, not a measured sensor
requirement. Each cycle still sends one current image in one Responses request;
the prior description adds text input tokens. No API conversation or response ID
is carried between requests.

## Follow one cycle

1. `VisualObservationLoop` asks its `ImageSource` for a frame. Before interpreting
   it, the loop examines the latest successful observation in `WorldState`.
2. Context is eligible only when the source matches, capture time advances, the
   acquisition-time gap is at most the configured limit (inclusive), and the prior
   description is at most 1,000 characters. A first frame has no prior context.
   Ineligible context is omitted, not truncated. Current-image interpretation
   proceeds independently when context is omitted.
3. The loop constructs `PreviousSceneContext`: a frozen, flat snapshot of the
   prior description, source, acquisition time, provider/model, and gap. It has
   no reference to that observation's own context, images, or history.
4. `perceive_image` passes this optional value through `VisionProvider.describe`.
   Source/time consistency is validated before the provider is called. A future
   provider must support this optional contract or explicitly reject it.
5. OpenAI receives the previous description and gap as labeled, untrusted JSON
   data alongside the current image. Additional instructions prioritize visible
   current evidence and request only a current-scene description, without a change
   narrative. They prohibit carrying forward unseen objects or claiming identity
   continuity, motion, or causes from the text summary alone.
6. A successful `VisualObservation` records the exact context supplied. The loop
   updates its latest scene and prints the observation. Failures stop the loop
   without recording a new scene, as in independent mode.

The gap is `current_frame.observed_at - previous_scene.observed_at`, not the
configured interval or the difference between model response times. For example,
two seconds of inference followed by a five-second wait can result in an
approximately seven-second acquisition gap. Recorded-file timestamps can describe
historical scenes: the gap policy does not establish freshness relative to now.
The webcam timestamps are host read-start times, with the buffering limitations
described in the [webcam guide](webcam.md).

## Inspect the evidence

`watch --json` includes `previous_context`:

- `null` for independent mode, the first frame, or omitted context;
- otherwise, the actual prior `description`, `source`, `observed_at`,
  `gap_seconds`, `provider`, and `model`.

This records requested context, not proof that a model attended to it or followed
every instruction. The current description still belongs to the current frame's
timestamp; the earlier timestamp remains separate. Previous images are not sent.

The prompt and retained context records are bounded, but semantic errors can still
propagate through successive descriptions. A flat snapshot prevents a nested
history in memory; it does not guarantee an error cannot persist in later text.

## Evaluate before changing defaults

Use the same recorded frames and capture timestamps for both modes, with the
same model and detail. Independently judge visible facts before comparing outputs.
Include unchanged scenes, objects entering/leaving the view, occlusion, camera
movement, and a deliberately incorrect previous description. Check for both useful
continuity and invented or retained details. Record exact context, omissions,
latency, and token usage if evaluating cost. The current webcam command alone does
not provide a recorded-sequence replay harness; two separate live runs are not a
controlled comparison.

Normal tests verify selection, timestamps, bounded metadata, payload shape, and
unchanged independent prompting without paid calls or hardware. They do not
establish improvement in model quality, resistance to misleading context, object
tracking, or motion estimation. This experiment does not implement change events
or a persistent world history.
