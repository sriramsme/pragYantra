# Architecture foundation

Status: first simulated behavior implemented and tested. The replacement maintains
one latest visual observation and responds to touch using a deterministic policy.
An image-file path now obtains a description through OpenAI behind a vision
interface and feeds it into the same behavior. Provider HTTP handling is tested
with mocked responses; a manual live API smoke test and a documented three-image
check succeeded, while systematic evaluation remains outstanding. An optional
webcam adapter has one-shot and continuous modes. A manual one-shot webcam smoke
test succeeded; continuous mode has automated tests and a reported successful
manual smoke test. Duration, device details, and timings were not recorded.
Persistent memory, actuation, and multimodal sensor multiplexing are not implemented.

## Decisions made

- Keep the 2024 prototype in `legacy/`, outside the new package and its tooling.
  It is a reference rather than a runtime dependency.
- Use Python with `uv` for the application. Start with Python 3.12 as a development
  baseline, not a claim that hardware deployments have been verified.
- Use C++ for firmware/native components when required; do not add a speculative
  firmware tree before hardware and an actual responsibility are selected.
- Permit hosted vision and other model APIs. Offline operation is not a universal
  requirement; providers and available capabilities should be explicit.
- Keep one application package initially. Separate processes or services need a
  demonstrated isolation, deployment, or performance requirement.

## Responsibilities and imports

| Package/module | Owns | May import internally |
| --- | --- | --- |
| `inputs` | Camera, microphone, sensor, and simulated acquisition | Application models and interfaces |
| `application` | Shared values/interfaces, world state, perception, behaviors, lifecycle | Other application modules |
| `outputs` | Speech playback, actuation, and simulated execution | Application models and interfaces |
| `providers` | Third-party APIs and external model/service implementations | Application models and interfaces |
| `cli.py` | Configuration, component construction, launcher | All four packages |

Application code receives implementations through construction; it does not find
them through global registries or import concrete inputs, outputs, or providers.
Keep shared values and contracts in `application/models.py` and
`application/interfaces.py` as behaviors need them. Prefer small Python protocols
and dataclasses. Do not predefine a large hierarchy of abstract base classes or a
universal plugin system.

Keep modules grouped by capability as they arrive, for example
`inputs/vision/`, `outputs/speech/`, and `providers/<service>/`. These are
illustrative future paths, not packages to populate with empty placeholders now.
Input and output implementations receive provider capabilities through application
interfaces; they do not import concrete provider clients. `cli.py` constructs and
connects implementations. Keep tests organized by behavior or component, with
integration tests clearly separated when real providers and devices are introduced.

The input/application/output organization describes responsibilities rather than
a single synchronous pass. Inputs may arrive at different rates, world state
persists across events, and outputs may be interrupted. Make those semantics
explicit when implementing state and runtime coordination.

## Perception and hosted providers

Separate acquisition from interpretation: a camera supplies a frame; a vision
provider interprets it. Likewise, audio acquisition, speech recognition, and speech
output have different responsibilities. Device acquisition belongs in `inputs/`,
interpretation is coordinated by `application/`, and third-party inference clients
belong in `providers/`. Speech synthesis can use a provider while playback remains
an output responsibility. Providers do not select overall application behavior or
directly control devices.

The first vision contract is `VisionProvider.describe(ImageFrame)`, returning a
`SceneDescription`. `application/perception.py` turns it into a visual observation
without changing acquisition time. The OpenAI implementation lives in
`providers/openai.py`; the image-file loader lives in `inputs/image.py`. See
[the execution walkthrough](vision.md).
`inputs/webcam.py` acquires laptop/USB camera frames and uses the same
normalization helper and `ImageFrame` value as the file loader. OpenCV remains
optional and confined to acquisition. A future Pi-specific adapter can replace
that acquisition step; see [webcam execution and limits](webcam.md).

For continuous observation, `WebcamStream` implements `ImageSource.read`. It
drains capture on one device-owning worker and replaces a single pending raw frame.
`VisualObservationLoop` handles one interpretation at a time, updates `WorldState`,
and yields timestamped visual events. The CLI prints each event and then the loop
waits its configured interval. Source/provider contexts belong to startup wiring.
This is a dedicated visual inspection path; the existing touch-driven
`AssistantRuntime` remains the separate simulated multimodal entry point. Neither
command shares state with another process or stores a history on disk. Prior
descriptions are not included in model prompts.

Define the input/output the application actually needs rather than wrapping every
API feature. Normalize results into shared application values;
keep SDK objects, authentication, retries, timeouts, and service-specific response
parsing in providers, with credentials supplied through startup configuration.
Local inference implementations can also live in providers behind the same
capability interfaces. Provider implementations need not have identical modalities
or capabilities: expose unsupported operations rather than silently emulating them.

Record observation source and acquisition time. Processing completion time is a
different fact, especially for hosted inference. Discard or handle stale results
explicitly. Configure request timeouts, bounded work, and failure behavior as each
integration is implemented. Evaluate latency and accuracy on representative inputs.

Decision models can provide bounded semantic judgments; generative models can
provide conversation and open-ended reasoning. Known thresholds, calculations,
and device constraints belong in code. The simulation does not require a provider,
and importing the package must not create clients or perform I/O.

## Hardware boundary

The application should work against simulated inputs before receiving real devices.
A Linux Raspberry Pi is a possible host; a microcontroller is a separate possible
controller. The hardware configuration and communication protocol are undecided.

If a controller is added, keep deadline-sensitive acquisition/control and device
limits local to it. Define observations and bounded commands at the communication
boundary. Higher-level inference may select goals or actions without becoming a
dependency of the physical control loop. Evaluate ARM dependency availability and
resource use on the selected target before claiming deployment support.

## First implemented behavior

Run `uv run pragyantra demo` or add `--json` for response evidence.

- `application/models.py`: immutable visual/touch observations, a delivery envelope,
  and responses containing status and supporting visual evidence. Acquisition,
  receipt, and response time are separate. Timestamps require timezones.
- `application/world_state.py`: retain the latest acquired visual observation.
  Older results cannot replace it; equal acquisition times keep the first result.
  This is one scene context, not object tracking or a full environment model.
- `application/behavior.py`: a touch requests current context. A description is
  usable when its acquisition age at response time is at most the configured
  threshold. Missing or stale observations produce explicit fallback responses;
  stale descriptions remain available as evidence, not as current output wording.
- `application/interfaces.py`: async observation-source and response-output
  protocols. Resource ownership uses asynchronous context managers.
- `application/runtime.py`: process one event stream, update context, and deliver
  responses. Use an injected clock, defaulting to UTC wall time. Enter and release
  input/output contexts even on processing errors, partial startup, or cancellation.
- `inputs/simulated.py`: finite replay with a logical clock and cancellation
  checkpoints. It includes a delayed older scene and needs no real-time waits.
- `outputs/simulated.py`: record response requests in memory. This is a finite
  simulation/test tool, not production storage or actual speech playback.

The demo returns unavailable, current, and stale responses with the default
five-second threshold. That threshold illustrates policy; it is not a measured
hardware requirement. The core has no model-provider dependency for this rule.

### Timing and scope limits

All timestamps must share a comparable clock. An observation cannot be delivered
before acquisition, an event cannot arrive ahead of the processing clock, and
delivery envelopes must be in nondecreasing receipt order. Acquisition order may
differ due to inference latency. Freshness includes processing delay; recent
delivery does not make an old camera frame fresh. Clock synchronization across
devices is not implemented.

The runner awaits each response before consuming the next event. It does not yet
multiplex live sensors, schedule inference in parallel, interrupt speech, or enforce
general device queue bounds/timeouts. The continuous webcam adapter has its own
latest-frame slot, but does not multiplex observations into this runner. Those
responsibilities must be designed as more adapters are integrated; simulation does not establish control-loop
timing or real-time performance. Output delivery is not retried automatically.

Tests cover freshness boundaries, missing input, delayed/out-of-order acquisition,
invalid timing, and cleanup on completion, input/output errors, partial startup,
and cancellation. No accuracy, hardware, or hosted-service results are claimed.

The image-file command now provides an acquisition/perception path behind an
application interface; its touch and output remain simulated. Unlike the default
demo, it uses the real clock and includes inference time in freshness. The
[first live check](experiments/2026-10-20-vision-smoke.md) records three public images.
One-shot and continuous laptop/USB acquisition have successful manual smoke tests.
Pacing and failure handling also have automated tests; next steps include sustained
capture, timing measurements, and representative scenes on the tested device.
Add decision-model judgments when a behavior requires
semantic interpretation. Grow memory and scheduling from demonstrated needs.

## Legacy retirement

The original files are preserved without code edits. Their relative layout is
unchanged, but they are not tested against modern dependencies. Consult
`legacy/AGENTS.md` for the audit. Do not import them from the new package. Delete
the archive when its useful behavior and historical references have been reviewed;
Git history will continue to preserve the original implementation.
