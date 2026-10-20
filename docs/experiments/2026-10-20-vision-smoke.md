# Image-file vision smoke check — October 20, 2026

## Setup

Code: `f897746` (`Add OpenAI image-file vision integration`). Three sequential
live requests used `gpt-5.6-luna`, `low` image detail, `none` reasoning effort,
the default 256-token output cap, 20-second timeout, and five-second freshness
threshold. Each request started a separate CLI process; no retries were performed.
The model received the normalized image and the application's description prompt,
without sample names or expected descriptions in its prompt.

The samples come from scikit-image's public example data, pinned to `v0.25.2`:

| Sample | Source | SHA-256 of downloaded bytes |
| --- | --- | --- |
| Coffee | [coffee.png](https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/coffee.png) | `cc02f8ca188b167c775a7101b5d767d1e71792cf762c33d6fa15a4599b5a8de7` |
| Astronaut | [astronaut.png](https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/astronaut.png) | `88431cd9653ccd539741b555fb0a46b61558b301d4110412b5bc28b5e3ea6cb5` |
| Rocket | [rocket.jpg](https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/rocket.jpg) | `c2dd0de7c538df8d111e479619b129464d0269d0ae5fd18ca91d33a7fdfea95c` |

The photographs are not included in this repository. Their context and attribution
are described in the [scikit-image data documentation](https://scikit-image.org/docs/stable/api/skimage.data.html).
These are familiar public examples, not a held-out dataset.

## Results

| Sample | Full command time (s) | Acquisition-to-response age (s) | Status |
| --- | ---: | ---: | --- |
| Coffee | 3.515 | 2.743 | `current` |
| Astronaut | 2.655 | 1.884 | `current` |
| Rocket | 2.871 | 2.115 | `current` |

Full command time uses a monotonic clock around a subprocess running
`python -m pragyantra` from the uv-managed environment. It includes process startup,
imports, image loading, client setup, the network request, and output. It excludes
image download and uv startup. Acquisition-to-response age is the JSON field
`visual_age_seconds`, calculated from UTC timestamps; it includes image processing,
client setup, inference/network delay, and application processing. Neither column
isolates model inference latency.

The exact returned scene descriptions were:

- **Coffee:** A small cup of coffee sits on a red saucer atop a wooden table, with
  a metal spoon resting beside it.
- **Astronaut:** A smiling woman in an orange astronaut suit stands indoors beside
  a large black helmet, with an American flag and a space shuttle model visible in
  the background. She appears to be posing for a formal portrait.
- **Rocket:** A white rocket stands vertically on a launch pad at dusk, surrounded
  by tall metal lattice towers and bright floodlights. No people are clearly visible.

Inspection of the source images supports the main objects and settings in each
description. The portrait wording is a plausible interpretation, not a measured
physical state. The output did not name the person or claim a launch was occurring.

All requests completed successfully and their acquisition-to-response ages fell
within the existing freshness policy. Touch and output were simulated throughout.

## Reproduction and limits

Download the pinned samples to a local scratch directory, then run each with:

```bash
uv run --env-file .env pragyantra see /path/to/sample.png \
  --model gpt-5.6-luna --image-detail low --json
```

This sends the image to OpenAI and incurs API charges. A new run can return
different wording, latency, and freshness status. The JSON age is available without
additional tooling; full command timing needs a monotonic timer around the process.

There was one request per image and no detail-level comparison, repeated trials,
adverse conditions, or independent scoring. The run did not record API token usage
or billed cost. It establishes a small working baseline, not an accuracy rate,
latency percentile, deterministic deadline, or hardware deployment result. No camera
or media device was exposed in this development environment.

Next validation should use the selected camera and representative scenes, including
motion and low light. Capture timing, buffering, and resource cleanup need testing
on that device before claiming live visual awareness.
