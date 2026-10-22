# Initial live request-interpretation check

Run on October 21, 2026 (US/Central); the result timestamp is October 22 in UTC.
This was an explicitly selected paid TypeSafe call sequence using synthetic text.
No personal conversations, camera images, microphone input or robot hardware were
used. This is an initial integration check, not a representative accuracy study.

## Configuration and reproduction

- Python 3.12, `typesafe-sdk` 0.7.5, requested/returned model `jev-1.14.0`.
- Question `intent-v1`; six options in `providers/typesafe.py`.
- `tests/fixtures/intent_requests.json`: 22 curated cases, one call per case.
- Confidence >=0.7 and selected probability >=0.75; these thresholds were not
  tuned against this result. Default 10-second deadline, no automatic retries.

```bash
uv run --locked --extra decisions examples/evaluate_intents.py --live
```

The ignored local `.env` supplied the key. The
[recorded JSON](2026-10-21-request-interpretation.json) preserves every synthetic
input, expected label, observed outcome, uncertainty and elapsed time.

## Observed results

| Measurement | Result |
| --- | --- |
| Cases | 22 |
| Matching expected intents | 21 |
| Invalid/provider outcomes | 1 |
| Incorrect accepted conversation/inspection routes | 0 |
| Clarification outcomes | 0 |
| Median elapsed time | 0.147819 seconds |
| p95 elapsed time, nearest rank | 0.493297 seconds |
| Reported input tokens | 12,181 across 21 valid responses |
| Actual billed cost | Not measured |

All 21 validated responses matched the curated expected labels. The remaining
case, “Take a new photograph and save it.” (expected `unknown`), produced an
invalid-judgment error and was rejected. Its raw response was not retained, so the
specific validation failure is unknown. There was no accepted behavior on error.

A separate manual follow-up of only that same synthetic request returned a valid
`unknown` judgment: selected probability approximately 0.93, confidence 0.92,
reported input tokens 581. This follow-up is not substituted into the original
22-case result. No prompt or validation policy was relaxed to accept the failure.
The application still has no retry policy.

A separate live CLI check used
`prag chat --interpret --message 'What do you see?' --message '/stop' --json`.
It returned an `inspect` result with explicitly unavailable visual evidence
(no camera was selected), followed by a local stopped result with no judgment.
The installed command exited successfully. No OpenAI inference or device access
was needed for this check.

Local validation also passed: 258 tests with all optional dependencies, including
from the built wheel outside the checkout; base-wheel tests passed 232 with two
optional modules skipped. Ruff, package build and whitespace checks passed.

## Interpretation and remaining work

This establishes live authentication, payload/response compatibility on successful
calls and fail-closed handling of one invalid response. The 22 hand-written cases
were used while designing the criteria, so they are not an independent test set.
No uncertain case triggered clarification in this run; deterministic fake-provider
tests cover that branch, but live ambiguity behavior needs broader examples.

Elapsed times include the provider call and application parsing from this host;
the first case includes initial connection overhead. They do not include OpenAI
conversation, acquisition, speech, robot transport or physical response, and are
not real-time guarantees. Reported token usage excludes the invalid case; billing
and cost per complete behavior remain unmeasured. Repeat trials, independent
requests, ambiguous references and operational failure rates remain to be evaluated.
