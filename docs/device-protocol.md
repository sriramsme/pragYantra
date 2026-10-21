# Device observation boundary

No controller, transport, wiring or electrical interface has been selected.
Version-1 JSON lines provide a software boundary that a future controller bridge
can target. Stdin is a local trusted-producer interface, not an authenticated
network service or a hard real-time bus.

```bash
prag chat --commands-only --events --json
```

Send one JSON object per UTF-8 line (timestamps below are examples; use actual
acquisition times from a synchronized host clock):

```json
{"version":1,"type":"sensor","source":"controller","observed_at":"2026-10-20T10:00:00-05:00","kind":"temperature","value":23.5,"unit":"degC"}
{"version":1,"type":"text","source":"operator","observed_at":"2026-10-20T10:00:01-05:00","text":"/context"}
{"version":1,"type":"touch","source":"controller","observed_at":"2026-10-20T10:00:02-05:00"}
```

A sensor event updates `WorldState` without model inference. A text event runs a
conversation turn or `/command`. A touch requests the latest visual context using
the deterministic missing/current/stale behavior. To combine these records with
background vision and hosted conversation, omit `--commands-only` and add
`--camera` with the webcam extra and credentials.

## Schema and validation

Every event requires exactly `version`, `type`, `source`, and `observed_at`, plus
the fields for its type. Unknown or missing fields fail; there is no implicit
version conversion. Version must be integer 1, not a boolean or float.

| Type | Additional fields | Bounds |
| --- | --- | --- |
| `sensor` | `kind`, `value`, `unit` | Kind 1–64 chars, finite numeric value (not bool), unit 1–16 chars |
| `text` | `text` | Nonempty, at most 4,000 chars |
| `touch` | None | Source and timestamp only |

Sources are nonempty and at most 80 characters. Lines are at most 16 KiB.
Timestamps require an explicit timezone and must not be ahead of the processing
clock. Channels are keyed by source/kind; at most 32 are retained. Old/equal
acquisitions do not overwrite new readings. Units are explicit metadata; there
is no conversion, calibration, dimensional analysis or automatic validation
against a component's physical range.

The stdin reader uses bounded buffering and awaits handling each record. While a
conversation or spoken output is busy, later stdin events wait; they are not
processed as an independent priority stream. OS/reader backpressure limits
buffering, but no freshness or delivery deadline is guaranteed. Put high-rate
sampling, feedback control, interlocks and actuator limits in the controller.

Scalar temperature/force/etc. are observations only. There is no built-in unit
ontology, map, people counter, location model or actuator command protocol. A
scalar touch sensor can use `sensor`; a `touch` event specifically triggers the
visual-context behavior. No free-form model response is interpreted as a device
command. Future transport adapters should preserve typed values and acquisition
time, define queue/clock/error semantics, and validate against official component
documentation before any physical interface is implemented.
