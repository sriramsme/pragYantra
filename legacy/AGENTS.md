# Archived prototype

This directory preserves the original 2024 implementation and documentation.
Treat it as reference material. Do not import it from `src/pragyantra/`, modernize
its dependency stack by default, or silently run its installers. Keep historical
files unchanged unless a task specifically concerns the archive.

## Historical map

- `main.py`: CLI validation, environment loading, startup, and shutdown.
- `core/manas.py`: `Manas` coordinates threaded hearing, vision, and speech;
  local GGUF inference uses llama-cpp-python, hosted inference uses LangChain/Groq.
- `core/hear.py`, `core/vision.py`, `core/speech.py`: live wrappers. Implementations
  in `core/utils/aid_hear.py`, `aid_vision.py`, and `aid_speech.py` use Whisper,
  Silero VAD, image captioning, pyttsx3, ElevenLabs, and Facebook MMS.
- `memory/memory.py`: timestamped sensory buffers. `Manas` constructs `LiveMemory`
  but reads context from live wrappers rather than persistent memory retrieval.
- `vector_utils/` and `memory/memory_store.py`: experimental embeddings,
  summarization, HDF5 storage, and timestamped memory; separate from the main loop.
- `text_to_action/`: embedding-based action selection and NER/LLM parameter
  extraction, not connected to `Manas`. Miscellaneous actions are mostly stubs;
  on-device actions include real filesystem operations.
- `helper_agents/personal_assistant/`: separate CrewAI experiment.
  `helper_agents/researcher/crew.py` is empty.
- `setup.py` is an executable bootstrap script, not Python package metadata.
  Both it and `setup.sh` install dependencies and download models; the shell
  script also invokes sudo/apt. They bypass the required uv workflow.

## Known limitations from the initial audit

- Requirements mix old pins and unpinned ML libraries. There is no established
  compatible Python version, automated test suite, CI, or lint configuration.
- Requirements do not explicitly cover all imported dependencies, including
  deepface, librosa, spacy, deepdiff, pydantic, groq, nltk, and dateutil. Some can
  arrive transitively; spaCy's model is a separate asset.
- `--offline_mode` selects the interpreter without enforcing no network access.
  Hugging Face and Whisper loaders can fetch missing assets; Silero VAD uses
  `torch.hub.load(..., force_reload=True)`.
- The CLI's offline-mode help disagrees with the flag default: actual default is
  online. Groq requires `GROQ_API_KEY`; ElevenLabs requires `SPEECH_KEY`.
- The downloader does not supply the local interpreter's required GGUF file.
- Constructors load models, initialize audio, or make hosted calls. Even CLI help
  imports third-party libraries; startup is not a lightweight validation check.
- Several module demos have stale constructor calls. The VGGish embedding function
  references an uninitialized model.
- `VectorStore` constructs a T5 summarizer and pickles payloads inside HDF5 under
  `memory_stream/`. Load only trusted stores. No persistent memory is connected to
  the main conversation loop.
- Thread lifecycle, buffers, speech interruption, and transcription pause/resume
  are coupled. Filesystem actions can delete or overwrite data.

Original paths assume execution from this directory and runtime assets/log folders
beneath it. The original README's commands are historical, not verified setup.
If reproduction is specifically needed, work from `legacy/` in a separate uv
virtual environment (`uv venv`, `uv pip install -r requirements.txt`, then
`uv run --no-project python main.py ...`). This still needs compatibility work,
model assets, devices, credentials where applicable, and runtime directories.
Do not run the original pip-based bootstrap scripts.
