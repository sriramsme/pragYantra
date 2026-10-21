"""Exercise real CLI configuration with fake execution and temporary env files."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from pragyantra import cli


@pytest.fixture
def configured_cli(tmp_path, monkeypatch, no_live_io):
    # The suite disables dotenv globally; these tests opt into temporary files.
    monkeypatch.delenv("PYTHON_DOTENV_DISABLED", raising=False)
    monkeypatch.delenv("PRAGYANTRA_CHAT_MODEL", raising=False)
    monkeypatch.delenv("PRAGYANTRA_ENV_TEST", raising=False)
    monkeypatch.chdir(tmp_path)
    captured = []

    async def run(args):
        captured.append((args, os.getenv("PRAGYANTRA_ENV_TEST")))

    from pragyantra.cli import assistant

    monkeypatch.setattr(assistant, "run_assistant", run)
    return tmp_path, captured


def invoke(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["prag", *args])
    cli.main()


def test_dotenv_sets_defaults_before_parsing_and_is_scoped(configured_cli, monkeypatch):
    directory, captured = configured_cli
    (directory / ".env").write_text(
        'PRAGYANTRA_CHAT_MODEL="file-model"\nexport PRAGYANTRA_ENV_TEST=from-file\n'
    )
    invoke(monkeypatch, "chat", "-m", "Hello")
    assert captured[0][0].model == "file-model"
    assert captured[0][1] == "from-file"
    assert "PRAGYANTRA_ENV_TEST" not in os.environ
    assert "PRAGYANTRA_CHAT_MODEL" not in os.environ


def test_shell_then_command_line_override_dotenv(configured_cli, monkeypatch):
    directory, captured = configured_cli
    (directory / ".env").write_text("PRAGYANTRA_CHAT_MODEL=file-model\n")
    monkeypatch.setenv("PRAGYANTRA_CHAT_MODEL", "shell-model")
    invoke(monkeypatch, "chat", "-m", "Hello")
    invoke(monkeypatch, "chat", "-m", "Hello", "--model", "flag-model")
    assert [args.model for args, _ in captured] == ["shell-model", "flag-model"]
    assert os.environ["PRAGYANTRA_CHAT_MODEL"] == "shell-model"


@pytest.mark.parametrize("position", ["before", "after"])
def test_selected_env_file_works_on_either_side_of_command(
    configured_cli, monkeypatch, position
):
    directory, captured = configured_cli
    (directory / ".env").write_text("PRAGYANTRA_CHAT_MODEL=wrong-file\n")
    (directory / "custom.env").write_text("PRAGYANTRA_CHAT_MODEL=selected-model\n")
    option = ["--env-file", "custom.env"]
    command = ["chat", "-m", "Hello"]
    invoke(
        monkeypatch, *(option + command if position == "before" else command + option)
    )
    assert captured[0][0].model == "selected-model"


def test_no_env_keeps_shell_and_does_not_search_parent(configured_cli, monkeypatch):
    directory, captured = configured_cli
    (directory / ".env").write_text("PRAGYANTRA_CHAT_MODEL=parent-model\n")
    invoke(monkeypatch, "chat", "--no-env", "-m", "Hello")
    child = directory / "child"
    child.mkdir()
    monkeypatch.chdir(child)
    invoke(monkeypatch, "chat", "-m", "Hello")
    assert [args.model for args, _ in captured] == ["gpt-5.6-luna"] * 2


def test_required_env_file_and_invalid_utf8_fail_without_contents(
    configured_cli, monkeypatch, capsys
):
    directory, _ = configured_cli
    (directory / "bad.env").write_bytes(b"PRIVATE_VALUE=\xff\xfe")
    for filename in ("missing.env", "bad.env"):
        with pytest.raises(SystemExit) as error:
            invoke(monkeypatch, "chat", "--env-file", filename, "-m", "Hello")
        assert error.value.code == 2
        output = capsys.readouterr().err
        assert "Cannot read env file" in output
        assert "PRIVATE_VALUE" not in output


def test_help_and_version_do_not_require_or_open_env_files(configured_cli, monkeypatch):
    directory, _ = configured_cli
    (directory / ".env").mkdir()
    for arguments in [
        ("--help",),
        ("chat", "--help"),
        ("-V",),
        ("--env-file", "missing.env", "chat", "--help"),
    ]:
        with pytest.raises(SystemExit) as error:
            invoke(monkeypatch, *arguments)
        assert error.value.code == 0


def test_camera_memory_and_short_message_flags(configured_cli, monkeypatch):
    _, captured = configured_cli
    invoke(monkeypatch, "chat", "--camera", "--memory", "-m", "Hello", "-j")
    args = captured[0][0]
    assert args.webcam == 0
    assert args.memory == Path("data/notes.sqlite")
    assert args.message == ["Hello"] and args.json
    invoke(monkeypatch, "chat", "--webcam", "2", "--memory", "other.sqlite", "-m", "Hi")
    assert captured[1][0].webcam == 2
    assert captured[1][0].memory == Path("other.sqlite")


def test_audio_commands_select_devices_without_redundant_flags(monkeypatch):
    from pragyantra.cli import audio

    seen = []

    async def execute(args):
        seen.append(args)

    monkeypatch.setattr(audio, "listen", execute)
    monkeypatch.setattr(audio, "speak", execute)
    invoke(monkeypatch, "listen")
    invoke(monkeypatch, "listen", "recording.wav")
    invoke(monkeypatch, "speak", "Hello")
    invoke(monkeypatch, "speak", "Hello", "-o", "hello.wav")
    assert seen[0].microphone
    assert not seen[1].microphone
    assert seen[2].play
    assert not seen[3].play and seen[3].output == Path("hello.wav")


@pytest.mark.parametrize("executable", ["prag", "pragyantra"])
def test_both_installed_entry_points_name_themselves(executable):
    result = subprocess.run(
        [executable, "--help"], capture_output=True, text=True, check=True
    )
    assert result.stdout.startswith(f"usage: {executable} ")
    assert "--env-file" in result.stdout
    assert "Examples:" in result.stdout
    assert result.stderr == ""


def test_literal_help_after_separator_still_loads_env(configured_cli, monkeypatch):
    directory, _ = configured_cli
    (directory / ".env").write_text("PRAGYANTRA_ENV_TEST=loaded\n")
    seen = []
    from pragyantra.cli import audio

    async def execute(args):
        seen.append((args.text, os.getenv("PRAGYANTRA_ENV_TEST")))

    monkeypatch.setattr(audio, "speak", execute)
    invoke(monkeypatch, "speak", "--", "--help")
    assert seen == [("--help", "loaded")]


def test_failed_env_load_restores_partial_values(configured_cli, monkeypatch, capsys):
    directory, _ = configured_cli
    (directory / ".env").write_bytes(b"PRAGYANTRA_ENV_TEST=temporary\nBAD=\x00\n")
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "chat", "-m", "Hello")
    assert error.value.code == 2
    assert "PRAGYANTRA_ENV_TEST" not in os.environ
    assert "BAD=" not in capsys.readouterr().err
