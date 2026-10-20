# Architecture foundation

Status: initial package structure. No perception, memory, behavior engine, model
provider, or hardware integration has been implemented in the replacement yet.

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

Add the first vision contract when implementing a specific task, such as scene
description. Define the input/output the application actually needs rather than
wrapping every API feature. Normalize results into shared application values;
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
and device constraints belong in code. No provider is selected or required by the
scaffold, and importing the package must not create clients or perform I/O.

## Hardware boundary

The application should work against simulated inputs before receiving real devices.
A Linux Raspberry Pi is a possible host; a microcontroller is a separate possible
controller. The hardware configuration and communication protocol are undecided.

If a controller is added, keep deadline-sensitive acquisition/control and device
limits local to it. Define observations and bounded commands at the communication
boundary. Higher-level inference may select goals or actions without becoming a
dependency of the physical control loop. Evaluate ARM dependency availability and
resource use on the selected target before claiming deployment support.

## First proposed behavior

1. Simulated visual observations update current state.
2. A simulated touch requests the latest visual context.
3. A simulated output receives a response, or an explicit unavailable/stale result.
4. Record enough timing and source information to explain the result.

Verify normal behavior, missing/stale inputs, and clean shutdown before attaching
devices. Start with deterministic behavior; add decision-model judgments where the
chosen behavior requires semantic interpretation. Grow memory, asynchronous
scheduling, and persistence from demonstrated needs.

## Legacy retirement

The original files are preserved without code edits. Their relative layout is
unchanged, but they are not tested against modern dependencies. Consult
`legacy/AGENTS.md` for the audit. Do not import them from the new package. Delete
the archive when its useful behavior and historical references have been reviewed;
Git history will continue to preserve the original implementation.
