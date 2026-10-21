"""Persistence, query bounds, timestamp filters, and forget semantics."""

from datetime import UTC, datetime, timedelta

import pytest

from pragyantra.application.memory import ConversationHistory, InMemoryNotes
from pragyantra.providers.memory import SQLiteNotes

AT = datetime(2026, 10, 20, tzinfo=UTC)


@pytest.fixture(params=["memory", "sqlite"])
def notes(request, tmp_path):
    if request.param == "memory":
        yield InMemoryNotes(capacity=3)
    else:
        with SQLiteNotes(tmp_path / "notes.sqlite", capacity=3) as repository:
            yield repository


def test_note_lookup_time_filter_and_forget(notes):
    old = notes.add("The red mug is on the desk", at=AT)
    newer = notes.add("The blue mug is in the cupboard", at=AT + timedelta(days=1))
    assert {note.id for note in notes.search("mug")} == {old.id, newer.id}
    assert notes.search("cupboard")[0] == newer
    assert notes.search("mug", since=AT + timedelta(hours=1)) == (newer,)
    assert notes.search("mug", until=AT) == (old,)
    assert notes.forget(old.id)
    assert not notes.forget(old.id)
    assert notes.search("red") == ()


def test_bounds_reject_before_storage_or_search(notes):
    with pytest.raises(ValueError):
        notes.add(" ", at=AT)
    with pytest.raises(ValueError):
        notes.add("x" * 2001, at=AT)
    for index in range(3):
        notes.add(str(index), at=AT)
    with pytest.raises(ValueError, match="full"):
        notes.add("overflow", at=AT)
    with pytest.raises(ValueError):
        notes.search("x", limit=101)
    with pytest.raises(ValueError):
        notes.search("x", since=AT + timedelta(days=1), until=AT)


def test_sqlite_reopening_and_literal_query_text(tmp_path):
    path = tmp_path / "notes.sqlite"
    with SQLiteNotes(path) as notes:
        original = notes.add("A cupboard with blue mugs", at=AT)
    with SQLiteNotes(path) as reopened:
        assert reopened.search("blue")[0] == original
        assert reopened.search('" OR 1=1; DROP TABLE notes; --') == ()
        assert reopened.search("cupboard")[0] == original
    with pytest.raises(ValueError, match="not open"):
        reopened.search("blue")


def test_history_evicts_whole_exchanges_at_character_bound():
    history = ConversationHistory(max_turns=10, max_chars=20000)
    history.append("a" * 4000, "b" * 16000)
    history.append("new", "response")
    assert [entry.text for entry in history.messages] == ["new", "response"]


def test_semantic_recall_matches_meaning_and_filters_incompatible_vectors(notes):
    from pragyantra.application.memory import TextEmbedding

    mug = notes.add(
        "The ceramic vessel is blue", at=AT, embedding=TextEmbedding("test", (3.0, 4.0))
    )
    notes.add("Unrelated", at=AT, embedding=TextEmbedding("other", (3.0, 4.0)))
    notes.add("No vector", at=AT)
    assert notes.search("mug") == ()
    assert notes.semantic_search(TextEmbedding("test", (0.6, 0.8))) == (mug,)
    assert notes.semantic_search(TextEmbedding("test", (1.0, 0.0, 0.0))) == ()
    assert notes.semantic_search(TextEmbedding("test", (-0.6, -0.8))) == ()
    assert (
        notes.semantic_search(
            TextEmbedding("test", (3, 4)), since=AT + timedelta(seconds=1)
        )
        == ()
    )
    assert notes.search("!!!") == ()
    assert len(notes.search("")) == 3


def test_sqlite_embeddings_survive_reopen_and_invalid_storage_fails(tmp_path):
    import sqlite3

    from pragyantra.application.memory import TextEmbedding

    path = tmp_path / "vectors.sqlite"
    vector = TextEmbedding("test", (1.0, 0.0))
    with SQLiteNotes(path) as notes:
        original = notes.add("A ceramic vessel", at=AT, embedding=vector)
    with SQLiteNotes(path) as notes:
        assert notes.semantic_search(vector) == (original,)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE notes SET embedding_json='[NaN, 0]'")
    with SQLiteNotes(path) as notes:
        with pytest.raises(ValueError, match="Invalid stored"):
            notes.semantic_search(vector)


def test_reject_unrelated_database_and_preserve_schema_one_notes(tmp_path):
    import sqlite3

    unrelated = tmp_path / "other.sqlite"
    with sqlite3.connect(unrelated) as db:
        db.execute("CREATE TABLE other(value TEXT)")
    with pytest.raises(ValueError, match="not a PragYantra"):
        with SQLiteNotes(unrelated):
            pass
    old = tmp_path / "old.sqlite"
    with sqlite3.connect(old) as db:
        db.executescript("""
            PRAGMA application_id=1347569497;
            PRAGMA user_version=1;
            CREATE TABLE notes(id INTEGER PRIMARY KEY AUTOINCREMENT,
                               text TEXT NOT NULL,created_at TEXT NOT NULL);
        """)
        db.execute(
            "INSERT INTO notes(text,created_at) VALUES(?,?)",
            ("Old memory", AT.isoformat()),
        )
    with SQLiteNotes(old) as notes:
        assert notes.search("Old")[0].text == "Old memory"


@pytest.mark.parametrize(
    "values", [(0, 0), (float("nan"), 1), (True, 1), (), (float("inf"),)]
)
def test_invalid_embedding_rejected(values):
    from pragyantra.application.memory import TextEmbedding

    with pytest.raises(ValueError):
        TextEmbedding("test", values)
