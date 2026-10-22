# Initial live direct-inspection check

Run October 21, 2026 (US/Central; October 22 UTC) with Python 3.12, OpenAI SDK
3.35.1, Decisions `gpt-6-luna`, low image detail, a 10-second provider deadline,
five-second evidence age and no retries. All inputs were generated colored shapes.
No camera, microphone, personal images, robot or physical stations were involved.

Reproduce with:

```bash
uv run --locked --all-extras examples/evaluate_inspections.py --live
```

`tests/fixtures/inspection_cases.json` defines eight red/blue/gray/empty images.
The script regenerates 200×200 images, normalizes them through the normal loader
boundary and asks three questions in each call: red-shape visibility, a synthetic
station choice (red/blue/none), and an ordered red-coverage score. Scores are
retained and validated against their distributions; no score-accuracy claim is made.

| Measurement | Observed result |
| --- | --- |
| Image batches / questions | 8 / 24 |
| Accepted predicate decisions | 8 |
| Predicate false positives / false negatives | 0 / 0 |
| Matching synthetic station labels | 8 / 8 |
| Stale / provider failures / refusals | 0 / 0 / 0 |
| Median elapsed time per batch | 0.2835045 s |
| p95 elapsed time, nearest rank | 1.28481 s |
| Reported input / output tokens | 4,048 / 0 |
| Missing usage records | 0 |
| Actual billed cost | Not measured |

The [recorded JSON](2026-10-21-direct-inspection.json) preserves all evidence hashes,
times, definitions, labels, distributions and usage. Image detail was configured
as low for this run; it is also retained explicitly in batch records going forward.

The [official Decisions pricing](https://developers.openai.com/api/docs/guides/decisions)
checked October 21 quotes a base input rate of $0.10 per million and no output
charge. Applying that base rate to the reported usage estimates **$0.0004048 total**,
or **$0.0000506 per three-question image batch**. This is arithmetic over reported
usage, not a billing observation, and does not account for regional premiums.
The raw run omitted rate flags and therefore correctly leaves its cost estimate
null. Rates can be supplied explicitly for future reports.

A separate CLI invocation on a temporary solid-red PNG returned `completed`, low
image detail and a red-visible probability of 1.0. The image was deleted after
the check. This verifies command composition separately from the eight-case batch
result; it is not added to those accuracy/latency counts.

These fixtures establish successful image uploads, batching, all three response
types and evidence bookkeeping. Their simple geometry does not establish accuracy
for real objects/stations, robustness to lighting/occlusion, calibrated thresholds
or hardware response times. The sample contains no uncertain/refused/stale live
outcomes; normal tests cover those software handling paths. Timing includes image
construction and provider/parsing work on this host, including first-connection
overhead, and excludes camera acquisition, speech, transport and actuation.
