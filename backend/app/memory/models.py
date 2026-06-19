from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversationTurn:
    session_id: str
    turn_index: int
    role: str
    content: str
    feature: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    nodes: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""


@dataclass
class LongTermMemory:
    id: str
    user_id: str
    kind: str
    content: str
    tags: list[str] = field(default_factory=list)
    source_session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    score: float = 0.0


@dataclass
class MemoryContext:
    session_id: str
    user_id: str
    recent_turns: list[ConversationTurn] = field(default_factory=list)
    long_term_memories: list[LongTermMemory] = field(default_factory=list)
