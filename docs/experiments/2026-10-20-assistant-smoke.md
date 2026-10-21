# Synthetic assistant service smoke check — October 20, 2026

Executed at `2026-10-21T02:15:29.835839+00:00` (October 20 US/Central), on the
Linux development host using the configured OpenAI key. Only invented test text
and synthesized audio were submitted. No microphone, camera, speakers, personal
recordings or personal memory were used. The calls incurred normal API usage;
no dollar estimate or billing measurement was recorded.

## Procedure and observed output

A temporary-directory script used `openai_services` and `ConversationSession`:

1. Synthesize “The blue mug is on the desk. PragYantra can hear and speak.” using
   `gpt-4o-mini-tts`, voice `coral`, PCM output; serialize the returned clip to WAV.
   Wall elapsed: **1.219 s**. Generated audio duration: **5.1 s**.
2. Transcribe that clip using `gpt-4o-mini-transcribe`. Wall elapsed: **1.453 s**.
   Text: “The blue mug is on the desk. Pragyantra can hear and speak.”
3. With semantic memory enabled, explicitly remember “The blue mug belongs to
   Alex”, then ask “Who owns the blue drinking vessel?”. The query retrieved
   note ID 1 using `text-embedding-3-small`; `gpt-5.6-luna` replied:
   “The blue mug belongs to Alex.” Query embedding plus conversation elapsed:
   **2.151 s**. Note embedding time was not recorded separately.

Before this successful run, a WAV synthesis attempt failed validation because its
streaming header did not carry a final duration. The provider now requests raw
PCM and constructs valid WAV artifacts locally. File input retains strict WAV
length validation. SDK tests assert the PCM request format and output rate.

## Reproduce the file-based path

Use a new output path; generation, transcription and conversation incur API usage:

```bash
uv run --env-file .env pragyantra speak \
  'The blue mug is on the desk. PragYantra can hear and speak.' \
  --output data/synthetic-smoke.wav
uv run --env-file .env pragyantra listen data/synthetic-smoke.wav --json
uv run --env-file .env pragyantra chat --audio data/synthetic-smoke.wav --json
uv run --env-file .env pragyantra chat --semantic-memory \
  --message '/remember The blue mug belongs to Alex' \
  --message 'Who owns the blue drinking vessel?' --json
```

The recorded timings above are from direct provider/session calls, not these CLI
commands, and exclude process startup. The successful run validates a narrow live
service integration. It does not establish ASR accuracy on real speech/noise,
spoken audio quality, general retrieval relevance, sustained operation, hardware
capture/playback, end-to-end turn latency, real-time control, or Pi compatibility.
Normal automated tests use fake services/devices and do not run this experiment.
