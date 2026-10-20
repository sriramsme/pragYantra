# Webcam input

Status: implemented with synthetic-frame tests and a successful manual webcam
smoke test of one-shot capture reported on October 20, 2026. Device details, command settings, and
timings were not recorded. This establishes basic operation on the tested setup;
longer-running reliability and other camera/OS combinations remain unevaluated.
Continuous mode also has automated tests and a successful manual smoke test
reported on October 20, 2026. Its duration, device details, settings, and timings
were not recorded; this does not establish sustained reliability or timing bounds.

## Run it

```bash
uv sync --locked --extra webcam
uv run --locked --extra webcam --env-file .env pragyantra see --webcam 0 --json
```

This opens camera index 0, reads one frame, releases the camera, and sends the
normalized frame to OpenAI. It uses the same model, detail, timeout, freshness,
and output options as file input. It neither saves a photograph nor displays a
preview. Touch and text output remain simulated. Each invocation makes at most
one vision request. Continuous observation is a separate explicit `watch` command.

Use another nonnegative index if needed. An image path and `--webcam` are mutually
exclusive. `--captured-at` applies only to image files.

OpenCV is an optional dependency in the `webcam` extra. File vision and the demo
do not need it. The headless package provides capture and conversion without GUI
dependencies; see the [package documentation](https://pypi.org/project/opencv-python-headless/).
Use the `--extra webcam` flag for webcam commands so uv includes that dependency.

## Follow the boundary

1. `cli.py` chooses file or webcam acquisition. It runs the blocking acquisition
   function in a worker thread.
2. `inputs/webcam.py:capture_webcam` uses a private blocking `_Webcam` session.
   It imports OpenCV only when called, opens the
   selected camera, checks its frame, and converts OpenCV BGR pixels to RGB.
3. `inputs/image.py:frame_from_image` normalizes either adapter's decoded image:
   at most 16 megapixels, a 1024-pixel longest edge, JPEG encoding, and no original
   metadata. The file adapter also checks compressed size and format before this.
4. The webcam adapter returns an `ImageFrame` with source `webcam:INDEX` and a UTC
   read-start timestamp. The one-shot function's `finally` block releases the camera on success or
   failure, before the CLI opens the provider.
5. The existing perception, world state, touch behavior, and output path run
   without changes. The [vision walkthrough](vision.md) describes those steps.

The OpenCV calls follow its [VideoCapture interface](https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html).
Neither application code nor model providers import OpenCV or select a camera.
A future `inputs/pi_camera.py` can use a different camera library and return the
same `ImageFrame`. No Pi-specific adapter or deployment claim is included yet.

## Continuous observation

```bash
uv run --extra webcam --env-file .env pragyantra watch \
  --webcam 0 --interval 5 --count 3 --json
```

This opens one camera and one provider client for the whole session. It interprets
three selected frames and stops. Omit `--count` to run until Ctrl+C (exit code 130).
Each selected frame is sent to OpenAI and incurs API charges. The same `--model`,
`--image-detail`, `--reasoning-effort`, and `--timeout` options as `see` apply.

The execution path has three responsibilities:

1. **Capture:** `inputs/webcam.py:WebcamStream` opens, reads, and releases the camera
   on a single dedicated worker. A background async task continuously drains that
   worker's reads into one pending raw-frame slot. New frames replace unconsumed
   ones. No growing capture queue, video file, or frame history is retained.
2. **Interpretation and context:** `application/observation_loop.py:VisualObservationLoop`
   requests a frame through `ImageSource.read`, then calls the existing perception
   function through `VisionProvider`. Only the selected frame is normalized and
   JPEG encoded. Acquisition time survives inference; the returned observation
   records receipt time and updates the existing `WorldState`. The application
   knows neither OpenCV nor the hosted SDK.
3. **Inspection output:** `cli.py:_watch` prints each event immediately and flushes
   stdout. JSON includes the description, source, acquisition/receipt timestamps,
   age, provider, model, and detail. Text mode shows age alongside the description.
   Output does not accumulate in a recording list. This is observation inspection;
   it does not generate simulated touches or run touch-triggered speech behavior.

`--interval` is the positive delay **after a result is handled**, not frames per
second or a periodic deadline. A two-second acquisition/inference cycle plus a
five-second interval takes at least seven seconds before the next selection.
There are no overlapping model requests or catch-up bursts. Capture continues
during inference and the interval, so the next selection uses the latest pending
frame. The raw slot is bounded to one; a selected frame being normalized and a
driver read in progress can also hold pixel buffers temporarily.

The JSON age includes processing/inference delay. `watch` reports observations
without asserting that they describe the present instant; it does not apply the
touch behavior's five-second freshness policy. `WorldState` retains the newest
acquired scene. Context is in memory and disappears when the process ends.

Previous descriptions are **not** sent back to the model. Temporal interpretation
is a candidate experiment: supply at most one previous description, mark it as an
earlier interpretation, and calculate the gap from acquisition times. Compare that
against this independent-frame baseline on the same recorded sequence before
making it a default. Text summaries alone do not establish object identity or
motion, and feeding erroneous summaries back can propagate mistakes.

Provider failure stops the command without retrying. A camera error is delivered
on the next frame read; a request already interpreting an earlier valid frame can
finish first. Context changes only on a successful interpretation. On normal
completion, failure, or cancellation, the CLI closes the camera stream and provider
contexts. The stream stops its producer, queues release behind any active driver
operation, and joins its worker. It never releases the camera concurrently with
an active read. OpenCV calls that block can still delay shutdown as described below.

## Timing and device limits

The timestamp is taken immediately before reading a frame, so read and processing
delay count toward the five-second freshness policy. It is not an exposure
timestamp: driver buffering can make a frame older than the recorded host time.
This distinction needs measurement on the selected hardware before relying on
freshness for physical interaction.

OpenCV open/read calls are blocking and backend-dependent. The CLI's `--timeout`
bounds the hosted vision request, not camera acquisition. Cancelling an awaiting
worker thread cannot interrupt an in-progress driver call; shutdown and release
can be delayed until that call returns or raises. This adapter provides no hard
capture deadline.

The adapter reads the first frame without an exposure warm-up policy or camera
property overrides. Lighting, focus, exposure settling, and buffering need testing
on the actual device. A failed open/read produces an error before any API request.
Check the index, camera permissions, and whether another application holds it. In
a VM, container, or WSL environment, the camera must also be exposed there.

## Validation

```bash
uv run --locked --extra webcam pytest -q
```

Tests use real OpenCV color conversion and Pillow normalization on synthetic
pixels, with fake device open/read/release operations. They cover BGR/RGB order,
size limits, read-start timing, resource release on failures/interruption,
argument validation, and reuse of the existing provider/behavior path. Default
tests also check a useful error when the optional dependency is missing.
Continuous-mode tests use fake devices and logical clocks to verify replacement
of pending frames, serial inference, pacing after output, immediate output,
finite counts, partial startup failure, and cancellation without racing release.
Normal tests make no camera captures or API requests.

Basic physical capture was reported successful in the manual smoke test. Device
disconnect behavior, exposure settling, repeated-run reliability, and driver
shutdown timing still require evaluation. OpenCV wheel availability does not
establish that a particular Raspberry Pi camera or OS is supported.
