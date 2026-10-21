# Audio acquisition, recognition, and output

File audio and hosted services have automated tests and a
[synthetic live smoke check](experiments/2026-10-20-assistant-smoke.md).
Actual microphone/speaker operation has not been manually validated in this rebuild.
The endpoint detector is a configurable energy heuristic, not neural speech recognition.

See [CLI installation](cli.md) for the `prag` command and automatic `.env` loading.

## Without devices

```bash
prag speak 'Hello from PragYantra.' --output data/hello.wav
prag listen data/hello.wav --json
prag chat --audio data/hello.wav --json
```

Speech is AI-generated. `speak --output` requires a new path and never overwrites
an existing file. Add `--play` to play generated speech, or `chat --speak` to speak
text/file-based conversation replies. Saving/playing synthesized audio and
acquiring audio are separate from the hosted model calls.

File input accepts uncompressed 16-bit PCM WAV, mono/stereo, 8–48 kHz, up to 60
seconds and 20 MiB. Unsupported, empty, oversized, or truncated inputs fail before
transcription. File timestamps mean pipeline acquisition, not original recording
time. Recordings are not committed or retained automatically.

## With devices

Install system PortAudio using your OS package manager, then:

```bash
# After the one-time tool installation in the CLI guide:
prag devices
prag listen --json
prag chat --voice
```

`devices` enumerates available devices without recording or playing anything.
Select numeric indices using `--input-device` and `--output-device`. Device access
needs the appropriate OS/session permissions. The adapter lazily imports
`sounddevice`; WAV file commands need neither it nor PortAudio. See
[deployment prerequisites](deployment.md) before trying a new host.

Voice input/output is half duplex. Capture opens only while listening, then closes
before ASR, conversation and synthesis/playback. It reopens after speech finishes,
which prevents the assistant from transcribing its own output through an open
microphone. This does not cancel room reverberation or provide acoustic echo
cancellation. Other people and environmental noise can trigger endpointing.
Say “stop PragYantra” or “quit PragYantra” as the entire recognized utterance to
exit without generating another reply; Ctrl+C also cancels.

## Boundaries and endpointing

- `application/audio.py:AudioClip` holds immutable PCM16 bytes, rate, channels,
  source and acquisition time, with bounded validation and WAV serialization.
- `inputs/microphone.py` owns one input stream on a worker thread. Its callback
  places fixed 20 ms mono blocks into a bounded queue of 64 blocks (about 1.28 s).
  Overflow/status errors fail without uploading the damaged utterance.
- `inputs/vad.py:UtteranceSegmenter` computes normalized RMS. By default it needs
  120 ms consecutive blocks above 0.015, keeps 200 ms pre-roll, and ends after
  700 ms below threshold or around 15 s total. At most one extra block can cross
  the configured maximum. Isolated noise bursts do not start an utterance.
- `--energy-threshold`, `--silence-duration`, `--utterance-limit` and
  `--sample-rate` configure acquisition. `--listen-timeout` bounds the whole
  listening attempt, including a partial utterance (default 30 s, maximum 300 s).
  These are tunable choices, not measured microphone accuracy or timing guarantees.
- Timestamps estimate host callback arrival minus one block duration, not calibrated
  ADC exposure time. OS buffering and clock changes affect accuracy.
- `providers/openai_services.py` transcribes bounded WAV with
  `gpt-4o-mini-transcribe`. It synthesizes with `gpt-4o-mini-tts`, voice `coral`,
  requesting raw 24 kHz mono signed 16-bit little-endian PCM. The application wraps
  PCM in a valid WAV when saving. See official [transcription](https://developers.openai.com/api/docs/guides/speech-to-text)
  and [speech synthesis](https://developers.openai.com/api/docs/guides/text-to-speech) documentation.
- `outputs/audio.py` plays PCM in roughly 100 ms chunks on an owned worker and
  closes after completion/failure/cancellation. Cancellation waits for active
  native calls. A blocked PortAudio call can delay cleanup; there is no hard deadline.

Speech responses are buffered before playback. Each service request has a timeout
and no automatic retries. The decoded audio value is capped at five minutes and
20 MiB; this is validation after the SDK receives the response, not a network
stream byte limit. Provider failure stops the command. Local neural ASR/TTS,
streaming partial transcripts/audio, speech interruption, denoising, and automatic
microphone calibration are not implemented. Current native adapters target
little-endian hosts; Raspberry Pi compatibility/performance remains untested.
