# Legacy retirement audit

Status: retired. The useful assistant behavior now has independent replacements;
the archived implementation and obsolete requirements/installers have been removed
from the working tree. The original source is preserved at Git commit `a782251`,
and the intact archive/audit at `0436c32`. See [history and attribution](history.md).

Removal does not mean every disconnected experiment was recreated or that a robot
was completed. The decisions below distinguish replacements from intentional
retirement and name the evidence and limits.

## Behavior mapping

| Legacy responsibility | Replacement / retirement decision | Evidence |
| --- | --- | --- |
| `core/manas.py`: combine hearing, vision, recent exchanges and respond | Integrated `ConversationSession` and chat wiring, shared world state, bounded exchanges, provider contracts | `test_conversation.py`, combined camera/audio/reply/speech and cancellation cases in `test_assistant_cli.py` |
| `core/vision.py`, `aid_vision.py`: continuous captions | File/webcam adapters, latest-frame buffering, serial interpretation, acquisition provenance; optional bounded temporal context in `watch` | Vision/input/stream/observation-loop tests; reported manual one-shot/continuous webcam checks; public-image experiment |
| `core/hear.py`, `aid_hear.py`: capture, endpointing, transcription | Bounded microphone input, energy endpointing, WAV files, transcription protocol/provider | `test_audio.py`, `test_audio_devices.py`, `test_openai_services.py`; synthetic live ASR check |
| `core/speech.py`, `aid_speech.py`: synthesis/playback and input pause | Separate synthesis/playback; half-duplex capture closes before inference/output; explicit cancellation | Fake PortAudio and half-duplex tests; live synthetic synthesis check; actual audio devices untested |
| `memory/memory.py`: sensory buffers | Latest timestamped world state, freshness snapshots and bounded recent conversation | Sensor ordering/capacity, visual freshness and conversation tests |
| `memory_store.py`, `vector_utils/`: experimental persistence/retrieval | Explicit notes with SQLite FTS keyword recall and opt-in embedding/cosine recall; inclusive time filters, reopen/delete, safe JSON vectors | `test_notes.py`, semantic session/SDK tests, live paraphrased retrieval; no legacy store import |
| `text_to_action/`: disconnected semantic dispatch/NER/math | Explicit application commands for context and memory; the briefly retained calculator was removed October 22, 2026 | Real CLI/subprocess checks; historical AST tests remain in Git; no generated code execution |
| `actions/on_device.py`: unrestricted desktop file operations | Retired: disconnected from the assistant and unrelated to controller actuation | Historical audit; no replacement desktop-file authority claimed |
| `miscellaneous.py`: weather/news/music/etc. placeholders | Retired: print-only placeholders did not implement those services | Historical audit; no service claims in current package |
| `helper_agents/`: separate CrewAI wrappers / empty researcher | Conversation provider supplies useful dialogue; redundant wrappers/empty delegation retired | Integrated conversation tests and live reply |
| `detect.py`, `face.py`, OCR/detection demos | Separate unused heuristics/demos retired; current scene descriptions are not classifier/biometric parity | No identity/attribute recognition or standalone OCR accuracy claims |
| Local GGUF/Hugging Face, ElevenLabs, Groq implementations | Retired provider choices; current OpenAI implementations are behind capability protocols | SDK tests/live hosted checks; no offline-AI claim or automatic weight downloads |
| Bootstrap installers and downloads | uv package/lock, optional device extras, lightweight help and reproducible installation | Locked sync, wheel/sdist build and clean wheel execution without extras |
| README, architecture image, citations, notebook | Historical artifacts retained in Git; current docs preserve source links, audit and original acknowledgements | `docs/history.md`; original license unchanged |

## Completed deletion gates

- Integrated text/audio conversation uses a timestamped sensory snapshot, recalled
  notes and bounded history; failures do not append failed model exchanges.
- File audio can be synthesized, serialized, transcribed and used for conversation
  without a microphone/speaker. Capture/playback have synthetic-device tests for
  overflow, failed starts, completion and cancellation.
- Persistent keyword/semantic notes survive reopening, reject invalid data and
  incompatible vectors, respect capacity/query bounds and time filters, and
  delete from retrieval. No pickle, implicit downloads or old serialized state.
- Deterministic commands run through the public CLI/session path.
- Combined lifecycle tests cover startup failure, perception failure, speech
  failure, cancellation and reverse-order resource cleanup. Camera queues,
  microphone queue, history, notes and retrieved context are bounded.
- Existing simulation, image vision, continuous camera and temporal-context tests
  continue to pass. Package code has no archive imports or runtime dependency.
- Execution guides, architecture, hardware/deployment limits, experiments and
  historical attribution describe actual behavior and intentional retirements.
- After deletion: base/all-extras checks, build and installed wheel execution
  verify that the package does not require archived files.

## Recorded verification

On the Linux development host, October 20, 2026 US/Central:

- Locked base environment: **178 passed, one optional OpenCV module skipped**.
- All-extras suite: **189 passed**, including the final scalar-boundary checks.
- Ruff lint/format and `git diff --check` passed; wheel and sdist built successfully.
- A clean installed wheel outside the checkout passed help/version, JSON simulation,
  local assistant commands and persisted/reopened note recall, without webcam,
  audio or development extras. The full suite also passed against the installed
  wheel outside the checkout: 178 base tests (one optional module skipped) and
  189 all-extras tests.
- [Public-image vision check](experiments/2026-10-20-vision-smoke.md) and user-reported
  webcam smoke checks establish narrow observed operation; webcam device details,
  sustained-run duration and capture timing were not recorded.
- [Synthetic live service check](experiments/2026-10-20-assistant-smoke.md) passed
  TTS, ASR, semantic recall and conversation using invented text/synthesized audio.

These are software/service integration results, not systematic accuracy or latency
benchmarks. Real microphone/speaker validation, noisy-speech endpointing evaluation,
sustained capture/shutdown reliability, semantic relevance evaluation, resource
measurements, ARM/Pi deployment and physical hardware/control integration remain
outstanding. A functioning humanoid or real-time actuator loop is not claimed or
required to retire obsolete software.
