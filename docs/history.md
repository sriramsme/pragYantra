# Project history and attribution

PragYantra began as a personal Python multimodal assistant prototype in 2024.
Its original README described the name as a combination of “Prag” (intelligent
or wise) and “Yantra” (machine or robot), expressing an interest in intelligent
machines. The ambition included embodied intelligence; the prototype did not
complete hardware integration or build a functioning humanoid robot.

The modernization preserves that direction while replacing its software foundation.
The repository's GNU GPL version 3 license remains unchanged.

## Recover the original work

The original tree is in Git at `a782251`. The intact archive, including original
README, architecture image, notebook and audit, is at `0436c32`:

- [Original archived README](https://github.com/sriramsme/pragYantra/blob/0436c32/legacy/README.md)
- [Original architecture image](https://github.com/sriramsme/pragYantra/blob/0436c32/legacy/arch.jpg)
- [Historical audit](https://github.com/sriramsme/pragYantra/blob/0436c32/legacy/AGENTS.md)

Inspect without checking out or executing it:

```bash
git show 0436c32:legacy/README.md
git show 0436c32:legacy/AGENTS.md
```

Historical installation commands and offline/realtime claims are not current
instructions or verified capabilities. Do not run the old dependency installers
or load its pickle/HDF5 memory stores as part of the new application.

## Audit findings retained

`core/manas.py` coordinated threaded live hearing, captions, text generation and
speech. Whisper/Silero VAD, image captioning, pyttsx3/ElevenLabs/MMS, local GGUF
and LangChain/Groq implementations were closely coupled to startup and lifecycle.
Constructors could load weights, initialize devices or call services; even help
imported heavyweight optional dependencies.

Sensory buffers supplied short-term context. `LiveMemory` was constructed but the
main loop read live wrappers rather than retrieving persistent memory. Separate
vector/summarization/HDF5 code was experimental, used pickle, and was not wired
into the main assistant. The action dispatcher and parameter extraction were also
separate experiments. Weather/news/etc. actions were mostly print-only stubs;
desktop file operations could really overwrite/delete files. CrewAI wrappers,
face attributes and OCR/detection demos were not required by the main loop.

The old requirements mixed obsolete pins and unpinned packages, missed imported
dependencies, and had no established compatible interpreter or automated suite.
The offline flag did not enforce network isolation; model loaders could download
assets. A VGGish helper referenced an uninitialized model; demos had stale calls.
The rebuild replaces useful behavior, retires disconnected/unsafe placeholders,
and records that distinction in [the retirement audit](legacy-retirement.md).

## Original model acknowledgements

These references were credited by the original README. They describe historical
experiments, not dependencies or performance evidence for the current application:

- NLP Connect (2022), *vit-gpt2-image-captioning*, revision `0e334c7`, Hugging Face,
  DOI `10.57967/hf/0222`: <https://huggingface.co/nlpconnect/vit-gpt2-image-captioning>.
- Vineel Pratap and collaborators (2023), *Scaling Speech Technology to 1,000+
  Languages* (MMS), arXiv. Full author citation remains in the historical README.
- Minghao Li and collaborators (2021), *TrOCR: Transformer-based Optical Character
  Recognition with Pre-trained Models*, arXiv `2109.10282`.
