"""Explicit long-term notes and bounded conversational working memory."""

import math
import re
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from pragyantra.application.models import require_aware

MAX_NOTE_CHARS = 2000


@dataclass(frozen=True, slots=True)
class TextEmbedding:
    model: str
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.model.strip() or not 1 <= len(self.values) <= 4096:
            raise ValueError("Embedding needs a model and 1–4096 dimensions")
        try:
            valid = all(
                type(x) in (int, float) and math.isfinite(x) for x in self.values
            )
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError("Embedding values must be finite numbers")
        norm = math.hypot(*self.values)
        if not math.isfinite(norm) or norm == 0:
            raise ValueError("Embedding must have finite nonzero length")
        object.__setattr__(self, "values", tuple(x / norm for x in self.values))


class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> TextEmbedding: ...


@dataclass(frozen=True, slots=True)
class MemoryNote:
    id: int
    text: str
    created_at: datetime
    embedding: TextEmbedding | None = None

    def __post_init__(self) -> None:
        require_aware(self.created_at, "memory creation time")
        if self.id <= 0 or not self.text.strip() or len(self.text) > MAX_NOTE_CHARS:
            raise ValueError("Memory requires a positive ID and 1–2000 text characters")


class NoteRepository(Protocol):
    def add(
        self, text: str, *, at: datetime, embedding: TextEmbedding | None = None
    ) -> MemoryNote: ...
    def search(
        self,
        query: str,
        *,
        limit: int = 3,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> tuple[MemoryNote, ...]: ...
    def semantic_search(
        self,
        query: TextEmbedding,
        *,
        limit: int = 3,
        since: datetime | None = None,
        until: datetime | None = None,
        min_similarity: float = 0.3,
    ) -> tuple[MemoryNote, ...]: ...
    def forget(self, note_id: int) -> bool: ...


async def recall(
    notes: NoteRepository,
    query: str,
    *,
    embeddings: EmbeddingProvider | None = None,
) -> tuple[MemoryNote, ...]:
    """Use the same bounded recall policy for commands and conversation."""
    if embeddings is not None and query.strip():
        embedding = await embeddings.embed(query)
        return notes.semantic_search(embedding, limit=3)
    return notes.search(query, limit=3)


def search_terms(query: str) -> tuple[str, ...]:
    if len(query) > 2000:
        raise ValueError("Memory query exceeds 2000 characters")
    return tuple(dict.fromkeys(re.findall(r"\w+", query.casefold())))[:20]


def validate_search(limit: int, since: datetime | None, until: datetime | None) -> None:
    if not 1 <= limit <= 100:
        raise ValueError("Memory search limit must be between 1 and 100")
    for date in (since, until):
        if date is not None:
            require_aware(date, "memory filter time")
    if since is not None and until is not None and since > until:
        raise ValueError("Memory start time must not exceed end time")


class InMemoryNotes:
    def __init__(self, capacity: int = 1000) -> None:
        if not 1 <= capacity <= 1000:
            raise ValueError("Memory capacity must be between 1 and 1000")
        self._capacity = capacity
        self._notes: dict[int, MemoryNote] = {}
        self._next_id = 1

    def add(
        self, text: str, *, at: datetime, embedding: TextEmbedding | None = None
    ) -> MemoryNote:
        if len(self._notes) >= self._capacity:
            raise ValueError("Memory is full; forget a note before adding another")
        note = MemoryNote(self._next_id, text.strip(), at, embedding)
        self._notes[note.id] = note
        self._next_id += 1
        return note

    def search(
        self,
        query: str,
        *,
        limit: int = 3,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> tuple[MemoryNote, ...]:
        validate_search(limit, since, until)
        terms = set(search_terms(query))
        if query.strip() and not terms:
            return ()
        hits = []
        for note in self._notes.values():
            if since is not None and note.created_at < since:
                continue
            if until is not None and note.created_at > until:
                continue
            words = set(re.findall(r"\w+", note.text.casefold()))
            score = len(terms.intersection(words))
            if not terms or score:
                hits.append((score, note.created_at, note.id, note))
        hits.sort(key=lambda hit: hit[:3], reverse=True)
        return tuple(hit[3] for hit in hits[:limit])

    def semantic_search(
        self,
        query: TextEmbedding,
        *,
        limit: int = 3,
        since: datetime | None = None,
        until: datetime | None = None,
        min_similarity: float = 0.3,
    ) -> tuple[MemoryNote, ...]:
        return rank_semantic(
            self._notes.values(),
            query,
            limit=limit,
            since=since,
            until=until,
            min_similarity=min_similarity,
        )

    def forget(self, note_id: int) -> bool:
        return self._notes.pop(note_id, None) is not None


def rank_semantic(
    notes: Iterable[MemoryNote],
    query: TextEmbedding,
    *,
    limit: int = 3,
    since: datetime | None = None,
    until: datetime | None = None,
    min_similarity: float = 0.3,
) -> tuple[MemoryNote, ...]:
    validate_search(limit, since, until)
    if not math.isfinite(min_similarity) or not -1 <= min_similarity <= 1:
        raise ValueError("Minimum cosine similarity must be between -1 and 1")
    hits = []
    for note in notes:
        embedding = note.embedding
        if (
            embedding is None
            or embedding.model != query.model
            or len(embedding.values) != len(query.values)
        ):
            continue
        if since is not None and note.created_at < since:
            continue
        if until is not None and note.created_at > until:
            continue
        score = sum(a * b for a, b in zip(embedding.values, query.values, strict=True))
        if score >= min_similarity:
            hits.append((score, note.created_at, note.id, note))
    hits.sort(key=lambda hit: hit[:3], reverse=True)
    return tuple(hit[3] for hit in hits[:limit])


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    text: str


class ConversationHistory:
    """Retain complete exchanges within both a turn and character budget."""

    def __init__(self, max_turns: int = 12, max_chars: int = 24000) -> None:
        if max_turns <= 0 or max_chars < 20000:
            raise ValueError(
                "History needs positive turns and at least 20000 characters"
            )
        self._max_turns = max_turns
        self._max_chars = max_chars
        self._turns: deque[tuple[ChatMessage, ChatMessage]] = deque()
        self._chars = 0

    @property
    def messages(self) -> tuple[ChatMessage, ...]:
        return tuple(message for turn in self._turns for message in turn)

    def append(self, user: str, assistant: str) -> None:
        size = len(user) + len(assistant)
        if size > self._max_chars:
            raise ValueError("Exchange exceeds history character budget")
        self._turns.append(
            (ChatMessage("user", user), ChatMessage("assistant", assistant))
        )
        self._chars += size
        while len(self._turns) > self._max_turns or self._chars > self._max_chars:
            self._chars -= sum(len(message.text) for message in self._turns.popleft())

    def clear(self) -> None:
        self._turns.clear()
        self._chars = 0
