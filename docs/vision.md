# Image-file vision: one execution

Status: implemented with mocked API tests and a successful manual live API smoke
test. A [three-image check](experiments/2026-10-20-vision-smoke.md) records actual
descriptions and timing; systematic evaluation remains outstanding. This path
reads an image file; the optional [webcam adapter](webcam.md) now provides another
acquisition path. Touch and text output remain simulated.

## Run it

```bash
uv sync --locked
cp .env.example .env
# Fill OPENAI_API_KEY in .env using your editor.
uv run --env-file .env pragyantra see /path/to/image.png --json
```

The command sends a normalized copy of the selected image to OpenAI. You can also
set `OPENAI_API_KEY` in the shell instead of using an env file. No credentials are
required for `demo` or tests. A missing key produces an actionable error.

## Follow the data

1. `cli/__init__.py` selects `see` and calls `cli/vision.py:see`. It loads the heavier image
   and SDK modules only for this command.
2. `inputs/image.py:load_image` reads PNG/JPEG/WebP bytes, validates the decoded
   image, applies orientation, and reduces the longest edge to at most 1024 pixels.
   It composites transparency on white and encodes a JPEG without original
   metadata. The original file is never modified.
3. The resulting `ImageFrame` carries bytes, MIME type, source, and acquisition
   time. The loader does not know which provider will interpret it.
4. `providers/openai.py:openai_vision` opens the SDK client using the API key. The
   CLI passes this provider to `application/perception.py:perceive_image`, which
   only knows the `VisionProvider` interface.
5. `OpenAIVision.describe` submits an image and a short description request through
   the Responses API. It handles SDK errors and validates completion/refusal/empty
   output. It returns a plain `SceneDescription`, not an SDK object.
6. `perceive_image` creates a `VisualObservation` preserving the image's source and
   acquisition time, plus the provider/model and requested image detail that
   produced its interpretation.
7. The CLI feeds that observation and a simulated touch into the existing runtime.
   This path uses the real clock, not the demo's logical clock. The behavior checks
   freshness and the recording output captures the response.
8. The CLI prints the response, or JSON evidence when `--json` is selected.

To add another provider, implement `VisionProvider.describe` and wire it at startup.
Image loading, world state, and touch behavior should not need provider-specific
changes. `inputs/webcam.py` already supplies the same frame value for a single
laptop/USB camera capture; camera acquisition and perception remain separate.

## Timing is part of the behavior

By default, the frame timestamp means acquisition from the file into this pipeline.
It does not establish when the photograph was originally taken, or prove that it
describes the current physical environment. File modification time and EXIF dates
are not silently treated as reliable capture times.

If the actual capture time is known, supply it explicitly:

```bash
uv run --env-file .env pragyantra see image.jpg \
  --captured-at 2026-10-20T10:00:00-05:00 --json
```

The default freshness threshold remains five seconds, inclusive. File decoding,
normalization, inference, and processing delay count toward age. Slow inference
can therefore produce a `stale` response. The description remains in JSON evidence,
but is not worded as current visual context. Change the policy explicitly with
`--max-visual-age SECONDS` when your experiment justifies a different threshold.

## Current provider settings and limits

- Default model: `gpt-5.6-luna`, selected as a low-cost starting point, not based on a
  project benchmark. Override with `--model` or `PRAGYANTRA_VISION_MODEL`.
- Image detail: `low`, appropriate for initial coarse scene descriptions. Override
  with `--image-detail high`, `auto`, or `original`. Fine text, small objects, and
  precise counting may need more detail. These options control API preprocessing:
  the loader still limits the uploaded copy to a 1024-pixel longest edge, including
  with `original`. The selected detail is retained in JSON provenance.
- Reasoning effort: `none`. If changing models, select a compatible effort with
  `--reasoning-effort`. The 256-token output cap includes any reasoning tokens;
  higher efforts may require a different output budget in the provider.
- One response candidate, at most 256 output tokens, no tools, `store=False`.
- A 20-second overall inference deadline and SDK timeout, with automatic retries
  disabled. Set `--timeout SECONDS` to change the deadline. Cancellation propagates
  and closes the client; errors do not become successful observations.
- At most 10 MiB compressed input and 16 megapixels decoded. Animated images and
  other formats are rejected before constructing a provider. Normalization bounds
  upload size and strips original metadata, but the visible image content is sent.
- The small live check records descriptions and timing, without establishing
  general accuracy, billed cost, timing guarantees, edge deployment, or hardware
  capability. A description is an interpretation; provenance is recorded without
  inventing a confidence value.

As checked on October 20, 2026, published standard model rates were $0.20 per
million input tokens and $1.20 per million output tokens. For a square 1024-pixel
upload, the documented 32-pixel patch rules and 1.2 multiplier give these estimates:

| API detail | Processed dimensions | Image input tokens | Image input cost |
| --- | --- | --- | --- |
| `low` | 512 × 512 | 308 | $0.0000616 |
| `high`, `original`, `auto` | 1024 × 1024 | 1229 | $0.0002458 |

These figures exclude the text prompt and generated output. They are estimates
from published rules, not measured usage. Check the current
[model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna) and
[vision guide](https://developers.openai.com/api/docs/guides/images-vision) before
using them for an experiment budget.
