"""Explicit chat commands; generated replies never enter this path."""

import json

from pragyantra.application.companion import (
    CompanionEntry,
    CompanionRepository,
    ContextKind,
)
from pragyantra.application.memory import (
    MAX_NOTE_CHARS,
    ConversationHistory,
    EmbeddingProvider,
    NoteRepository,
    recall,
)
from pragyantra.application.world_state import EnvironmentSnapshot

HELP = (
    "Commands: /context, /remember TEXT, /recall QUERY, "
    "/forget ID, /profile [KIND KEY VALUE], /unprofile KIND KEY, /reset, /help, "
    "/quit. /stop ends an AssistantRunner session. "
    "Other input starts a conversation unless request interpretation is enabled."
)


async def run_command(
    text: str,
    *,
    environment: EnvironmentSnapshot,
    notes: NoteRepository,
    companion: CompanionRepository,
    history: ConversationHistory,
    embeddings: EmbeddingProvider | None = None,
) -> str | None:
    """Return a command reply, or None for ordinary conversation.

    The session supplies its frozen evidence and stores and handles one turn at
    a time. Commands can use optional embeddings; they never call conversation
    or devices.
    """
    if not text.startswith("/"):
        return None
    command, _, argument = text.partition(" ")
    argument = argument.strip()
    if command == "/profile":
        if not argument:
            records = [entry.to_record() for entry in companion.entries()]
            text = json.dumps(records, ensure_ascii=False)
            if len(text) > 12000:
                # Keep a full store readable within the existing reply bound.
                records = [
                    dict(
                        row,
                        value=row["value"][:40],
                        truncated=len(row["value"]) > 40,
                    )
                    for row in records
                ]
                text = json.dumps(records, ensure_ascii=False)
            return text
        parts = argument.split(maxsplit=2)
        if len(parts) != 3:
            raise ValueError("Use /profile KIND KEY VALUE")
        companion.set(
            CompanionEntry(ContextKind(parts[0]), parts[1], parts[2], environment.as_of)
        )
        return "Saved explicit companion context."
    if command == "/unprofile":
        parts = argument.split()
        if len(parts) != 2:
            raise ValueError("Use /unprofile KIND KEY")
        return (
            "Context removed."
            if companion.delete(ContextKind(parts[0]), parts[1])
            else "No matching context."
        )
    if command == "/help":
        return HELP
    if command == "/context":
        return json.dumps(environment.to_record(), ensure_ascii=False)
    if command == "/remember":
        if not argument or len(argument) > MAX_NOTE_CHARS:
            raise ValueError("Memory requires 1–2000 characters")
        embedding = await embeddings.embed(argument) if embeddings is not None else None
        note = notes.add(argument, at=environment.as_of, embedding=embedding)
        return f"Remembered note {note.id}: {note.text}"
    if command == "/recall":
        matches = await recall(notes, argument, embeddings=embeddings)
        return (
            "\n".join(
                f"[{note.id}] {note.created_at.isoformat()} {note.text}"
                for note in matches
            )
            or "No matching memories."
        )
    if command == "/forget":
        if not argument.isdecimal() or int(argument) <= 0:
            raise ValueError("Use /forget with a positive note ID")
        return "Note forgotten." if notes.forget(int(argument)) else "Note not found."
    if command == "/reset":
        history.clear()
        return (
            "Conversation history cleared. "
            "Explicit notes and sensory context are retained."
        )
    return f"Unknown command. {HELP}"
