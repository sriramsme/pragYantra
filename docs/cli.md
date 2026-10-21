# Command-line use

The short command is `prag`. `pragyantra` remains an equivalent executable.

## Install the local checkout once

From the repository root:

```bash
uv tool install --editable '.[audio,webcam]' --python 3.12
cp .env.example .env
# Fill in your key with your editor.
prag --help
```

uv installs both executables in its tool directory, using an isolated environment.
Editable installation follows source edits in this checkout. Re-run the install
command when dependencies/entry points change; tool resolution is separate from
the project's lockfile. Audio also requires system PortAudio; see [audio setup](audio.md).
If your shell cannot find the executable, check `uv tool dir --bin` and your PATH.
See the [uv tools documentation](https://docs.astral.sh/uv/concepts/tools/).

For development with the locked project environment instead:

```bash
uv sync --locked --all-extras
uv run --all-extras prag chat --voice --camera
```

`uv run` does not include optional extras automatically. Installing the tool with
the extras once avoids repeating those flags for daily use. No command downloads
missing optional dependencies automatically.

## Everyday commands

```bash
prag chat                                # text conversation
prag chat -m 'Hello'                      # one text turn
prag chat --voice                        # microphone and spoken replies
prag chat --voice --camera               # voice with background visual context
prag chat --memory                       # persist explicit notes in data/notes.sqlite
prag see photo.jpg                       # describe a file
prag see --camera                        # describe one frame from camera 0
prag watch -n 3                          # three continuous camera descriptions
prag listen                              # transcribe one microphone utterance
prag listen recording.wav                # transcribe a WAV file
prag speak 'Hello'                        # synthesize and play
prag speak 'Hello' -o data/hello.wav       # save WAV without playback
prag devices                             # enumerate audio devices
prag calc 'sqrt(16) + 2**3'               # local arithmetic
prag demo -j                             # simulation as JSON lines
```

`--camera` defaults to index 0; use `--camera 2` to select another camera.
`--webcam` remains an alias. `--memory` defaults to `data/notes.sqlite` only when
present; omit it for session-only notes or give an explicit path. `-m`, `-n`,
`-o`, `-j`, and `-V` abbreviate message, count, output, JSON, and version where
applicable. Existing long flags and `uv run pragyantra ...` continue to work.

No command defaults to camera capture or voice conversation just because the
program was launched without arguments: bare `prag` displays help. Explicit
`listen` requests the microphone; explicit `speak TEXT` requests synthesis/playback.
Passing a WAV to `listen` or an output file to `speak` selects the file-based path.
Device and provider lifecycle/freshness rules are unchanged.

## Configuration

The CLI automatically reads **only `.env` in the current working directory** when
running a command. It does not search parents or the source checkout from an
unrelated directory. A missing default file is fine. Help/version do not read it.

Precedence is **command flags → existing shell variables → env file → defaults**.
Quotes, comments, `export`, and `${NAME}` expansion follow
[python-dotenv](https://bbc2.github.io/python-dotenv/). File values do not replace
existing environment variables. Values are never printed by configuration loading.

```bash
prag --env-file staging.env chat
prag chat --env-file staging.env          # same behavior
prag --no-env chat                        # shell configuration only
prag chat --model another-model           # explicit setting wins
```

`--env-file` and `--no-env` are mutually exclusive and may appear before/after a
command. An explicitly selected file must exist and be readable UTF-8. Use the
standard `--` separator for positional text beginning with option names.

Keep credentials in ignored `.env` or the shell; `.env.example` has placeholders
and model defaults. The application never creates a credential file automatically.
See [assistant](assistant.md), [vision](vision.md), [webcam](webcam.md),
[audio](audio.md), and [memory](memory.md) guides for capability details.
