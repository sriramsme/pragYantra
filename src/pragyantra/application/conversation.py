"""Conversation coordinates bounded history, sensory evidence and explicit actions."""

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from pragyantra.application.actions import calculate
from pragyantra.application.memory import (
    ChatMessage,
    ConversationHistory,
    EmbeddingProvider,
    InMemoryNotes,
    MemoryNote,
    NoteRepository,
)
from pragyantra.application.models import TextObservation, require_aware
from pragyantra.application.world_state import EnvironmentSnapshot, WorldState


@dataclass(frozen=True, slots=True)
class ConversationRequest:
    message: TextObservation
    history: tuple[ChatMessage, ...]
    environment: EnvironmentSnapshot
    memories: tuple[MemoryNote, ...]


@dataclass(frozen=True, slots=True)
class GeneratedReply:
    text: str
    provider: str
    model: str

    def __post_init__(self) -> None:
        if not self.text.strip() or len(self.text) > 16000:
            raise ValueError("Reply requires 1–16000 characters")
        if not self.provider.strip() or not self.model.strip():
            raise ValueError("Reply provenance is required")


class ConversationProvider(Protocol):
    async def respond(self, request: ConversationRequest) -> GeneratedReply: ...


@dataclass(frozen=True, slots=True)
class ConversationResult:
    message: TextObservation
    reply: GeneratedReply
    environment: EnvironmentSnapshot
    memories: tuple[MemoryNote, ...]
    responded_at: datetime


HELP = (
    "Commands: /context, /calc EXPRESSION, /remember TEXT, /recall QUERY, "
    "/forget ID, /reset, /help, /quit. Other input starts a conversation."
)


class ConversationSession:
    def __init__(
        self,
        provider: ConversationProvider,
        *,
        state: WorldState | None = None,
        notes: NoteRepository | None = None,
        max_context_age: timedelta = timedelta(seconds=5),
        now=None,
        max_turns: int = 12,
        embeddings: EmbeddingProvider | None = None,
    ) -> None:
        if max_context_age <= timedelta(0):
            raise ValueError("Maximum context age must be positive")
        self.embeddings = embeddings
        self.provider = provider
        self.state = state if state is not None else WorldState()
        self.notes = notes if notes is not None else InMemoryNotes()
        self.history = ConversationHistory(max_turns=max_turns)
        self.max_context_age = max_context_age
        self._now = now or (lambda: datetime.now(UTC))
        self._lock = asyncio.Lock()

    async def _command(self, text: str, environment: EnvironmentSnapshot) -> str | None:
        if not text.startswith("/"):
            return None
        command, _, argument = text.partition(" ")
        argument = argument.strip()
        if command == "/help":
            return HELP
        if command == "/context":
            return json.dumps(environment.to_record(), ensure_ascii=False)
        if command == "/calc":
            return str(calculate(argument))
        if command == "/remember":
            if not argument or len(argument) > 2000:
                raise ValueError("Memory requires 1–2000 characters")
            embedding = (
                await self.embeddings.embed(argument) if self.embeddings else None
            )
            note = self.notes.add(argument, at=environment.as_of, embedding=embedding)
            return f"Remembered note {note.id}: {note.text}"
        if command == "/recall":
            notes = await self._recall(argument)
            return (
                "\n".join(
                    f"[{note.id}] {note.created_at.isoformat()} {note.text}"
                    for note in notes
                )
                or "No matching memories."
            )
        if command == "/forget":
            if not argument.isdecimal() or int(argument) <= 0:
                raise ValueError("Use /forget with a positive note ID")
            return (
                "Note forgotten."
                if self.notes.forget(int(argument))
                else "Note not found."
            )
        if command == "/reset":
            self.history.clear()
            return (
                "Conversation history cleared. "
                "Explicit notes and sensory context are retained."
            )
        return f"Unknown command. {HELP}"

    async def _recall(self, query: str) -> tuple[MemoryNote, ...]:
        if self.embeddings is not None and query.strip():
            embedding = await self.embeddings.embed(query)
            return self.notes.semantic_search(embedding, limit=3)
        return self.notes.search(query, limit=3)

    async def respond(self, message: TextObservation) -> ConversationResult:
        async with self._lock:
            at = self._now()
            require_aware(at, "session clock")
            if message.observed_at > at:
                raise ValueError("User input is ahead of the session clock")
            environment = self.state.snapshot(at=at, max_age=self.max_context_age)
            command = await self._command(message.text.strip(), environment)
            memories: tuple[MemoryNote, ...] = ()
            if command is not None:
                reply = GeneratedReply(command, "builtin", "commands-v1")
            else:
                memories = await self._recall(message.text[:2000])
                request = ConversationRequest(
                    message, self.history.messages, environment, memories
                )
                reply = await self.provider.respond(request)
            finished = self._now()
            require_aware(finished, "response clock")
            if finished < at:
                raise ValueError("Response clock moved backwards")
            if message.text.strip() != "/reset":
                self.history.append(message.text, reply.text)
            return ConversationResult(message, reply, environment, memories, finished)
