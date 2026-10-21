"""SQLite note storage with bounded, parameterized lexical retrieval."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

from pragyantra.application.memory import (
    MemoryNote,
    TextEmbedding,
    rank_semantic,
    search_terms,
    validate_search,
)


class SQLiteNotes:
    def __init__(self, path: Path, *, capacity: int = 1000) -> None:
        if not 1 <= capacity <= 1000:
            raise ValueError("Memory capacity must be between 1 and 1000")
        self.path = path
        self._capacity = capacity
        self._db: sqlite3.Connection | None = None

    def __enter__(self) -> Self:
        if self._db is not None:
            raise ValueError("Memory repository is already open")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path)
        try:
            application = db.execute("PRAGMA application_id").fetchone()[0]
            tables = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            if application != 0x50524759 and (application != 0 or tables):
                raise ValueError("This is not a PragYantra memory database")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2):
                raise ValueError("Unsupported memory schema version")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                    text, content='notes', content_rowid='id'
                );
                CREATE TRIGGER IF NOT EXISTS notes_insert AFTER INSERT ON notes BEGIN
                    INSERT INTO notes_fts(rowid,text) VALUES(new.id,new.text);
                END;
                CREATE TRIGGER IF NOT EXISTS notes_delete AFTER DELETE ON notes BEGIN
                    INSERT INTO notes_fts(notes_fts,rowid,text)
                    VALUES('delete',old.id,old.text);
                END;
                PRAGMA application_id = 1347569497;
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(notes)")}
            with db:
                if "embedding_model" not in columns:
                    db.execute("ALTER TABLE notes ADD COLUMN embedding_model TEXT")
                    db.execute("ALTER TABLE notes ADD COLUMN embedding_json TEXT")
                if version < 2:
                    db.execute("INSERT INTO notes_fts(notes_fts) VALUES('rebuild')")
                db.execute("PRAGMA user_version = 2")
            self._db = db
            return self
        except BaseException:
            db.close()
            raise

    def _connection(self) -> sqlite3.Connection:
        if self._db is None:
            raise ValueError("Memory repository is not open")
        return self._db

    @staticmethod
    def _note(row) -> MemoryNote:
        embedding = None
        if row[3] is not None or row[4] is not None:
            try:
                if not isinstance(row[4], str) or len(row[4]) > 131072:
                    raise ValueError("Embedding exceeds storage bounds")
                values = json.loads(row[4])
                if not isinstance(values, list):
                    raise ValueError("Embedding requires a JSON array")
                embedding = TextEmbedding(row[3], tuple(values))
            except (TypeError, AttributeError, ValueError) as exc:
                raise ValueError("Invalid stored memory embedding") from exc
        return MemoryNote(row[0], row[1], datetime.fromisoformat(row[2]), embedding)

    def add(
        self, text: str, *, at: datetime, embedding: TextEmbedding | None = None
    ) -> MemoryNote:
        candidate = MemoryNote(1, text.strip(), at, embedding)
        db = self._connection()
        with db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT COUNT(*) FROM notes").fetchone()[0] >= self._capacity:
                raise ValueError("Memory is full; forget a note before adding another")
            cursor = db.execute(
                "INSERT INTO notes(text,created_at,embedding_model,embedding_json) "
                "VALUES(?,?,?,?)",
                (
                    candidate.text,
                    at.astimezone(UTC).isoformat(),
                    embedding.model if embedding else None,
                    json.dumps(embedding.values) if embedding else None,
                ),
            )
        return MemoryNote(cursor.lastrowid, candidate.text, at, embedding)

    def search(
        self,
        query: str,
        *,
        limit: int = 3,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> tuple[MemoryNote, ...]:
        validate_search(limit, since, until)
        terms = search_terms(query)
        db = self._connection()
        if query.strip() and not terms:
            return ()
        where, values = [], []
        for operator, date in ((">=", since), ("<=", until)):
            if date is not None:
                where.append(f"n.created_at {operator} ?")
                values.append(date.astimezone(UTC).isoformat())
        if terms:
            where.append("notes_fts MATCH ?")
            values.append(" OR ".join(f'"{term}"' for term in terms))
        select = (
            "SELECT n.id,n.text,n.created_at,n.embedding_model,n.embedding_json "
            "FROM notes n"
        )
        if terms:
            select += " JOIN notes_fts ON notes_fts.rowid=n.id"
        if where:
            select += " WHERE " + " AND ".join(where)
        select += (
            " ORDER BY "
            + ("bm25(notes_fts), " if terms else "")
            + "n.created_at DESC, n.id DESC LIMIT ?"
        )
        return tuple(self._note(row) for row in db.execute(select, (*values, limit)))

    def semantic_search(
        self,
        query: TextEmbedding,
        *,
        limit: int = 3,
        since: datetime | None = None,
        until: datetime | None = None,
        min_similarity: float = 0.3,
    ) -> tuple[MemoryNote, ...]:
        db = self._connection()
        rows = db.execute(
            "SELECT id,text,created_at,embedding_model,embedding_json FROM notes "
            "WHERE embedding_model=? LIMIT 1001",
            (query.model,),
        ).fetchall()
        if len(rows) > 1000:
            raise ValueError("Stored memory exceeds the 1000-note search bound")
        return rank_semantic(
            (self._note(row) for row in rows),
            query,
            limit=limit,
            since=since,
            until=until,
            min_similarity=min_similarity,
        )

    def forget(self, note_id: int) -> bool:
        db = self._connection()
        with db:
            return db.execute("DELETE FROM notes WHERE id=?", (note_id,)).rowcount > 0

    def __exit__(self, *args) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None
