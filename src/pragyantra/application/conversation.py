"""Coordinate turns with bounded history, sensory evidence and saved context."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from pragyantra.application.commands import run_command
from pragyantra.application.companion import (
    CompanionEntry,
    CompanionRepository,
    InMemoryCompanion,
)
from pragyantra.application.memory import (
    ChatMessage,
    ConversationHistory,
    EmbeddingProvider,
    InMemoryNotes,
    MemoryNote,
    NoteRepository,
    recall,
)
from pragyantra.application.models import TextObservation, require_aware
from pragyantra.application.world_state import EnvironmentSnapshot, WorldState


@dataclass(frozen=True, slots=True)
class ConversationRequest:
    message: TextObservation
    history: tuple[ChatMessage, ...]
    environment: EnvironmentSnapshot
    memories: tuple[MemoryNote, ...]
    companion: tuple[CompanionEntry, ...] = ()


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
    companion: tuple[CompanionEntry, ...] = ()


class ConversationSession:
    def __init__(
        self,
        provider: ConversationProvider,
        *,
        state: WorldState | None = None,
        notes: NoteRepository | None = None,
        companion: CompanionRepository | None = None,
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
        self.companion = companion if companion is not None else InMemoryCompanion()
        self.history = ConversationHistory(max_turns=max_turns)
        self.max_context_age = max_context_age
        self._now = now or (lambda: datetime.now(UTC))
        self._lock = asyncio.Lock()

    async def respond(self, message: TextObservation) -> ConversationResult:
        async with self._lock:
            at = self._now()
            require_aware(at, "session clock")
            if message.observed_at > at:
                raise ValueError("User input is ahead of the session clock")
            environment = self.state.snapshot(at=at, max_age=self.max_context_age)
            command = await run_command(
                message.text.strip(),
                environment=environment,
                notes=self.notes,
                companion=self.companion,
                history=self.history,
                embeddings=self.embeddings,
            )
            memories: tuple[MemoryNote, ...] = ()
            companion: tuple[CompanionEntry, ...] = ()
            if command is not None:
                reply = GeneratedReply(command, "builtin", "commands-v1")
            else:
                companion = self.companion.entries()
                memories = await recall(
                    self.notes, message.text[:2000], embeddings=self.embeddings
                )
                request = ConversationRequest(
                    message,
                    self.history.messages,
                    environment,
                    memories,
                    companion,
                )
                reply = await self.provider.respond(request)
            finished = self._now()
            require_aware(finished, "response clock")
            if finished < at:
                raise ValueError("Response clock moved backwards")
            if message.text.strip() != "/reset":
                self.history.append(message.text, reply.text)
            return ConversationResult(
                message, reply, environment, memories, finished, companion
            )
