"""Explicit user-saved context; never a claim about current sensory evidence."""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pragyantra.application.models import require_aware

MAX_ENTRIES = 32


class ContextKind(StrEnum):
    NAME = "name"
    PREFERENCE = "preference"
    OBSERVATION = "observation"


@dataclass(frozen=True, slots=True)
class CompanionEntry:
    kind: ContextKind
    key: str
    value: str
    updated_at: datetime

    def __post_init__(self):
        if not isinstance(self.kind, ContextKind):
            raise ValueError("Context kind must be name, preference or observation")
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", self.key):
            raise ValueError("Context key must be a short identifier")
        if not self.value.strip() or len(self.value) > 512:
            raise ValueError("Context value requires 1–512 characters")
        require_aware(self.updated_at, "context update time")

    def to_record(self):
        return {
            "kind": self.kind.value,
            "key": self.key,
            "value": self.value,
            "updated_at": self.updated_at.isoformat(),
        }


class CompanionRepository(Protocol):
    def set(self, entry: CompanionEntry) -> None: ...
    def entries(self) -> tuple[CompanionEntry, ...]: ...
    def delete(self, kind: ContextKind, key: str) -> bool: ...


class InMemoryCompanion:
    def __init__(self):
        self._entries = {}

    def set(self, entry: CompanionEntry):
        key = (entry.kind, entry.key)
        if key not in self._entries and len(self._entries) >= MAX_ENTRIES:
            raise ValueError("Companion context is full; remove an entry first")
        previous = self._entries.get(key)
        if previous and entry.updated_at < previous.updated_at:
            raise ValueError("Context update is older than the saved entry")
        self._entries[key] = entry

    def entries(self) -> tuple[CompanionEntry, ...]:
        return tuple(self._entries[key] for key in sorted(self._entries))

    def delete(self, kind: ContextKind, key: str) -> bool:
        return self._entries.pop((kind, key), None) is not None
