from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class StudentWritingState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    inputs: dict[str, Any]

    memory_context: Optional[str]
    recalled_memories: list[str]
    brief: Optional[str]
    knowledge_context: Optional[str]
    rag_chunks: list[dict[str, Any]]
    outline: Optional[str]
    draft: Optional[str]
    critique: Optional[str]
    critique_scores: dict[str, float]
    prev_scores: dict[str, float]
    revision_count: int
    final_output: Optional[str]
    memory_writeback: Optional[str]
    saved_memories: list[str]
