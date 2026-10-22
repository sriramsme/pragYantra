"""Companion context on the connection owned by SQLiteNotes."""

from datetime import UTC, datetime

from pragyantra.application.companion import MAX_ENTRIES, CompanionEntry, ContextKind


class SQLiteCompanion:
    def __init__(self, connection):
        self._connection = connection

    def set(self, entry: CompanionEntry):
        db = self._connection()
        with db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT updated_at FROM companion_context WHERE kind=? AND key=?",
                (entry.kind.value, entry.key),
            ).fetchone()
            if previous:
                if entry.updated_at < datetime.fromisoformat(previous[0]):
                    raise ValueError("Context update is older than the saved entry")
            elif (
                db.execute("SELECT COUNT(*) FROM companion_context").fetchone()[0]
                >= MAX_ENTRIES
            ):
                raise ValueError("Companion context is full; remove an entry first")
            db.execute(
                "INSERT INTO companion_context(kind,key,value,updated_at) "
                "VALUES(?,?,?,?) ON CONFLICT(kind,key) DO UPDATE SET "
                "value=excluded.value, updated_at=excluded.updated_at",
                (
                    entry.kind.value,
                    entry.key,
                    entry.value,
                    entry.updated_at.astimezone(UTC).isoformat(),
                ),
            )

    def entries(self) -> tuple[CompanionEntry, ...]:
        rows = (
            self._connection()
            .execute(
                "SELECT kind,key,value,updated_at FROM companion_context "
                "ORDER BY kind,key LIMIT 33"
            )
            .fetchall()
        )
        if len(rows) > MAX_ENTRIES:
            raise ValueError("Stored companion context exceeds the entry limit")
        return tuple(
            CompanionEntry(ContextKind(kind), key, value, datetime.fromisoformat(at))
            for kind, key, value, at in rows
        )

    def delete(self, kind: ContextKind, key: str) -> bool:
        db = self._connection()
        with db:
            return (
                db.execute(
                    "DELETE FROM companion_context WHERE kind=? AND key=?",
                    (kind.value, key),
                ).rowcount
                > 0
            )
