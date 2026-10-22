"""Explicit companion context survives restart without becoming sensor evidence."""

import asyncio
import json
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import pytest

from pragyantra.application.companion import (
    CompanionEntry,
    ContextKind,
    InMemoryCompanion,
)
from pragyantra.application.conversation import ConversationSession, GeneratedReply
from pragyantra.application.memory import TextEmbedding
from pragyantra.application.models import TextObservation
from pragyantra.providers.memory import SQLiteNotes

AT = datetime(2026, 10, 21, tzinfo=UTC)


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    if request.param == "memory":
        yield InMemoryCompanion()
    else:
        with SQLiteNotes(tmp_path / "notes.sqlite") as notes:
            yield notes.companion


def test_bounded_upsert_delete_and_old_updates(store):
    for i in range(32):
        store.set(
            CompanionEntry(
                ContextKind.OBSERVATION,
                f"station_{i}",
                "A saved description, not a current measurement",
                AT,
            )
        )
    with pytest.raises(ValueError, match="full"):
        store.set(CompanionEntry(ContextKind.NAME, "user", "Casey", AT))
    store.set(
        CompanionEntry(
            ContextKind.OBSERVATION, "station_0", "Updated", AT + timedelta(seconds=1)
        )
    )
    with pytest.raises(ValueError, match="older"):
        store.set(CompanionEntry(ContextKind.OBSERVATION, "station_0", "Old", AT))
    assert len(store.entries()) == 32
    assert store.delete(ContextKind.OBSERVATION, "station_0")
    assert not store.delete(ContextKind.OBSERVATION, "station_0")


def test_migrate_schema_two_and_reopen_without_changing_notes(tmp_path):
    path = tmp_path / "old.sqlite"
    with SQLiteNotes(path) as notes:
        note = notes.add(
            "Existing note", at=AT, embedding=TextEmbedding("fake", (1, 0))
        )
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE companion_context")
        db.execute("PRAGMA user_version=2")
    entry = CompanionEntry(
        ContextKind.PREFERENCE, "interaction_style", "Brief explanations", AT
    )
    with SQLiteNotes(path) as notes:
        assert notes.search("") == (note,)
        assert notes.companion.entries() == ()
        notes.companion.set(entry)
        context = notes.companion
    with pytest.raises(ValueError, match="not open"):
        context.entries()
    with SQLiteNotes(path) as notes:
        assert notes.companion.entries() == (entry,)
        assert notes.search("") == (note,)


def test_profile_commands_and_conversation_separate_context_from_sensors():
    calls = []

    class Conversation:
        async def respond(self, request):
            calls.append(request)
            return GeneratedReply("Hello Casey", "fake", "test")

    async def scenario():
        session = ConversationSession(Conversation(), now=lambda: AT)
        for text in (
            "/profile name user Casey",
            "/profile preference style concise",
            "/profile observation desk blue mug by a lamp",
        ):
            await session.respond(TextObservation("test", AT, text))
        assert calls == []
        await session.respond(TextObservation("test", AT, "Hello"))
        request = calls[0]
        assert len(request.companion) == 3 and request.memories == ()
        assert request.environment.visual is None and request.environment.sensors == ()
        await session.respond(TextObservation("test", AT, "/reset"))
        assert session.history.messages == ()
        assert len(session.companion.entries()) == 3
        await session.respond(TextObservation("test", AT, "/unprofile name user"))
        assert len(session.companion.entries()) == 2

    asyncio.run(scenario())


def test_cli_profile_persists_across_processes_and_chat_uses_same_database(tmp_path):
    path = tmp_path / "notes.sqlite"

    def run(*args):
        return subprocess.run(
            [sys.executable, "-m", "pragyantra", "--no-env", *args],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )

    run("profile", "--database", str(path), "set", "name", "user", "Casey")
    result = json.loads(run("profile", "--database", str(path), "list").stdout)
    assert result[0]["value"] == "Casey"
    chat = json.loads(
        run(
            "chat", "--commands-only", "--memory", str(path), "-m", "/profile", "-j"
        ).stdout
    )
    assert json.loads(chat["text"])[0]["value"] == "Casey"
    assert json.loads(
        run("profile", "--database", str(path), "delete", "name", "user").stdout
    )["deleted"]


def test_context_validation():
    for key, value in (("bad key", "x"), ("ok", ""), ("ok", "x" * 513)):
        with pytest.raises(ValueError):
            CompanionEntry(ContextKind.NAME, key, value, AT)


def test_full_profile_listing_respects_reply_budget_without_changing_stored_values():
    async def scenario():
        class NoCalls:
            async def respond(self, request):
                pytest.fail("Called model")

        context = InMemoryCompanion()
        # JSON control escapes stress the rendered-character bound too.
        for i in range(32):
            context.set(
                CompanionEntry(
                    ContextKind.OBSERVATION,
                    f"k{i:02d}" + "x" * 61,
                    "\x00" * 511 + "x",
                    AT,
                )
            )
        session = ConversationSession(NoCalls(), companion=context, now=lambda: AT)
        result = await session.respond(TextObservation("test", AT, "/profile"))
        assert len(result.reply.text) <= 16000
        records = json.loads(result.reply.text)
        assert len(records) == 32 and all(row["truncated"] for row in records)
        assert all(len(entry.value) == 512 for entry in context.entries())

    asyncio.run(scenario())
