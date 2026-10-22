# Direct image inspection

`inspect` evaluates explicit conditions directly on image pixels. It does not ask
a conversational model to write a description and then classify that description.
Image judgments remain separate from `VisualObservation` captions and physical
`SensorObservation` measurements.

```bash
prag inspect photo.jpg --condition 'Is a red mug visible?' --json
prag inspect --camera --condition 'Is the doorway visibly obstructed?' --json
```

These are model judgments about visible evidence, not physical safety checks.
The command uploads the normalized image to OpenAI. The existing image loader and
one-shot webcam adapter normalize it to at most 1024 pixels on the longest edge.
The default detail is `low`; override with `--image-detail`. File acquisition time
means when the pipeline loaded the file, not when the photograph was taken. Use
`--captured-at` when the actual historical acquisition time is known.

## Questions and batching

Repeat `--condition` to evaluate independent predicates together over one image.
For named station matching or a rubric, use `--questions questions.json`:

```json
[
  {
    "name": "target_visible",
    "instructions": "Is a red mug clearly visible?",
    "version": "1"
  },
  {
    "name": "station",
    "kind": "choice",
    "instructions": "Which described station best matches this image?",
    "options": [
      ["desk", "A wooden desk with a blue lamp"],
      ["shelf", "A metal shelf with labeled boxes"],
      ["none", "Neither station, or insufficient visible evidence"]
    ],
    "version": "1"
  },
  {
    "name": "visible_obstruction",
    "kind": "score",
    "instructions": "How much of the marked opening is visibly obstructed?",
    "options": [
      ["none", "Opening is visible and unobstructed"],
      ["partial", "Some of the opening is obscured"],
      ["full", "Most or all of the opening is obscured"]
    ],
    "version": "1"
  }
]
```

`predicate` returns its estimated probability, with no invented boolean or
confidence. `choice` returns a configured string, probability distribution and
confidence. `score` returns a probability-weighted index into the ordered levels,
plus its distribution and confidence; it is not a physical unit or measurement.
A refusal is explicit and has no invented judgment values. Missing, mismatched or
malformed answers fail the entire batch. Include an appropriate no-match option
for closed-set choices; high confidence does not establish correctness.

Question files are limited to 64 KiB. Each request accepts 1–16 uniquely named
questions, with at most 32 options per choice/score and a 32,000-character total
instruction/option budget. Definitions retain their version in the result. Change
the version when changing the meaning of a question or its options.

## Provider and freshness

The [official Decisions guide](https://developers.openai.com/api/docs/guides/decisions)
currently documents `gpt-6-luna` as the supported model for this endpoint. This is
a separate default from the user-selected `gpt-5.6-luna` conversation/description
model. Use `--model` or `PRAGYANTRA_INSPECTION_MODEL` for an explicit inspection
setting; unsupported models fail rather than silently falling back. The existing
OpenAI dependency includes Decisions support. `OPENAI_API_KEY` is required.
Default request timeout is 10 seconds, with retries disabled. No Responses-only
parameters such as `store` or reasoning settings are invented for this endpoint.

The evidence age limit is five seconds by default (`--max-age SECONDS`). Already
stale evidence skips inference. Acquisition time is preserved through inference,
and freshness is checked again when the result is consumed. A successful call can
therefore yield a stale result. JSON retains returned judgments for audit but
labels them unusable; do not treat their probabilities as current evidence.
Future acquisitions and backwards clocks are rejected.

Results retain a SHA-256 reference to the normalized image bytes, source,
acquisition/request/completion/consumption times, question definitions/versions,
actual provider/model, image detail and returned uncertainty/usage. The image bytes
are not automatically saved. A provider failure yields `provider_failure`, no
batch and no fallback. The CLI emits a nonzero exit code on provider failure.
Stale or refused results never become executable requests.

## Embed without a subprocess

```python
from datetime import UTC, datetime, timedelta
from pragyantra.application.inspection import ImageInspector, InspectionQuestion

# Host opens the provider context and supplies an acquired ImageFrame.
inspector = ImageInspector(provider, max_age=timedelta(seconds=5))
result = await inspector.inspect(
    frame, (InspectionQuestion("target", "Is the configured red marker visible?"),)
)
if result.status_at(datetime.now(UTC)) == "completed":
    judgment = result.batch.judgments[0]
    # Host policy handles refusal/uncertainty; no actuation is performed here.
```

The three files to read are `application/inspection.py` (values and evidence age),
`providers/openai_decisions.py` (SDK adapter), and `cli/inspection.py` (composition).
The library depends only on `InspectionProvider`; the host owns the client and
event loop. `AssistantRunner` still reports captions for conversational `inspect`
requests. Direct configured judgments use this separate API/command; they do not
run automatically for every frame or rewrite the scalar world-state channels.

## Evaluation and limits

```bash
uv run examples/evaluate_inspections.py
uv run examples/evaluate_inspections.py --live
```

The default validates eight synthetic shape fixtures without making API calls.
Only `--live` uploads those generated images. Each image batches a predicate,
choice and score. Reports include predicate decisions/false positives/false
negatives, station-label matches, stale results, refusals, provider failures,
median/p95 latency, usage and complete evidence records. Ambiguous, stale, refused
and failed results are excluded from accepted predicate decisions, with coverage
reported explicitly. Tests separately exercise these paths using fake providers.

For an estimate using rates you supply, add `--input-usd-per-million RATE` and
`--output-usd-per-million RATE`. The estimate covers reported usage only, with
missing-usage counts; it is not an actual bill. Intent evaluation likewise accepts
an input-token rate. See the [initial experiment](experiments/2026-10-21-direct-inspection.md).
Real objects, lighting, camera viewpoints, meaningful station confusion and repeated
trials still need a representative dataset. No tracking, navigation, reference-image
comparison or controller integration is implemented by these judgments.
