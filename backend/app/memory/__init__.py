from __future__ import annotations

from app.memory.repository import ConversationRepository
from app.memory.service import ConversationMemoryService

_memory_service: ConversationMemoryService | None = None


def get_memory_service() -> ConversationMemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = ConversationMemoryService(ConversationRepository())
    return _memory_service


async def init_database() -> None:
    await get_memory_service().init()


__all__ = ["ConversationRepository", "ConversationMemoryService", "get_memory_service", "init_database"]
