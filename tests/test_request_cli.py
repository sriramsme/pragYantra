"""CLI wiring for opt-in interpretation; no real providers or devices."""

import json
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from pragyantra import cli
from pragyantra.application.conversation import GeneratedReply
from pragyantra.application.requests import Intent, IntentJudgment
from pragyantra.providers import openai_services, typesafe


def judgment(intent):
    return IntentJudgment(
        intent,
        tuple((item, 0.95 if item == intent else 0.01) for item in Intent),
        0.9,
        "fake",
        "test",
    )


def test_interpret_command_does_not_open_conversation_provider(monkeypatch, capsys):
    events = []

    class Interpreter:
        async def interpret(self, message):
            assert message.text == "Follow me"
            return judgment(Intent.FOLLOW)

    @asynccontextmanager
    async def provider(**kwargs):
        try:
            yield Interpreter()
        finally:
            events.append("closed")

    def forbidden(**kwargs):
        pytest.fail("Judgment-only commands must not construct OpenAI services")

    monkeypatch.setattr(typesafe, "typesafe_interpreter", provider)
    monkeypatch.setattr(openai_services, "openai_services", forbidden)
    monkeypatch.setattr(sys, "argv", ["prag", "interpret", "Follow me", "-j"])
    cli.main()
    record = json.loads(capsys.readouterr().out)
    assert (
        record["status"] == "unsupported" and record["judgment"]["intent"] == "follow"
    )
    assert events == ["closed"]


def test_opt_in_chat_preserves_judgment_and_conversation_and_slash_commands(
    monkeypatch, capsys
):
    calls, events = [], []

    class Interpreter:
        async def interpret(self, message):
            calls.append(message.text)
            return judgment(
                Intent.INSPECT if message.text == "Look around" else Intent.CONVERSATION
            )

    class Chat:
        async def respond(self, request):
            events.append("conversation")
            return GeneratedReply("Hello", "fake", "chat")

    @asynccontextmanager
    async def interpreter(**kwargs):
        try:
            yield Interpreter()
        finally:
            events.append("interpreter closed")

    @asynccontextmanager
    async def conversation(**kwargs):
        try:
            yield Chat()
        finally:
            events.append("conversation closed")

    monkeypatch.setattr(typesafe, "typesafe_interpreter", interpreter)
    monkeypatch.setattr(openai_services, "openai_services", conversation)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prag",
            "chat",
            "--interpret",
            "-m",
            "Hello",
            "-m",
            "Look around",
            "-m",
            "/context",
            "-m",
            "/stop",
            "-m",
            "not read",
            "-j",
        ],
    )
    cli.main()
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert calls == ["Hello", "Look around"]
    assert records[0]["conversation"]["model"] == "chat"
    assert records[1]["scene_status"] == "unavailable"
    assert json.loads(records[2]["text"])["visual"] is None
    assert records[3]["status"] == "stopped"
    assert events[-2:] == ["interpreter closed", "conversation closed"]


def test_commands_only_cannot_enable_hosted_interpretation(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prag", "chat", "--interpret", "--commands-only"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2


def test_evaluation_is_explicitly_live(tmp_path):
    script = Path(__file__).resolve().parents[1] / "examples/evaluate_intents.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Validated 22 cases. No API calls" in result.stdout
    assert result.stderr == ""
