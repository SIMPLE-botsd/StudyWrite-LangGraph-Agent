from __future__ import annotations

import re
from typing import Any

from app.core.config import settings
from app.memory.models import ConversationTurn, MemoryContext
from app.memory.repository import ConversationRepository


class ConversationMemoryService:
    """会话记忆服务：从 SQLite 读取上下文，并整理成 Agent 节点可直接使用的文本。"""

    def __init__(self, repository: ConversationRepository):
        self.repo = repository

    async def init(self) -> None:
        await self.repo.init()

    async def load_context(
        self,
        *,
        session_id: str,
        user_id: str,
        query: str,
        max_turns: int | None = None,
        memory_k: int | None = None,
        use_memory: bool = True,
    ) -> MemoryContext:
        max_turns = max_turns or settings.MEMORY_MAX_TURNS
        memory_k = memory_k or settings.MEMORY_TOP_K
        recent_turns = await self.repo.get_recent_turns(session_id, limit=max_turns * 2)
        long_term = []
        if use_memory:
            # 长期记忆按当前题目做轻量关键词召回，用来支持“继续写/按上次风格”等多轮需求。
            long_term = await self.repo.search_long_term_memories(user_id, query, limit=memory_k)
        return MemoryContext(
            session_id=session_id,
            user_id=user_id,
            recent_turns=recent_turns,
            long_term_memories=long_term,
        )

    def format_context_for_agent(self, context: MemoryContext) -> str:
        lines: list[str] = []
        # 写入模型前先过滤脏记忆，避免历史里的错误提示和乱码继续污染新一轮生成。
        clean_memories = [m for m in context.long_term_memories if not self._looks_like_dirty_memory(m.content)]
        if clean_memories:
            lines.append("【长期记忆摘要】")
            for item in clean_memories:
                tags = f" #{' #'.join(item.tags)}" if item.tags else ""
                lines.append(f"- {item.kind}: {self._compact_memory(item.content)}{tags}")

        if context.recent_turns:
            lines.append("【最近会话摘要】")
            for turn in context.recent_turns[-4:]:
                role = "学生" if turn.role == "user" else "智能体"
                lines.append(f"- {role}: {self._compact_memory(turn.content, 180)}")

        return "\n".join(lines)

    async def save_turn(
        self,
        *,
        session_id: str,
        user_id: str,
        feature: str,
        title: str,
        query: str,
        answer: str,
        nodes: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        # 每轮同时保存用户输入和助手输出，历史回放才能恢复完整对话与节点过程。
        await self.repo.create_session(session_id, user_id, title, feature)
        turn_index = await self.repo.get_max_turn_index(session_id) + 1
        await self.repo.add_turn(
            ConversationTurn(
                session_id=session_id,
                turn_index=turn_index,
                role="user",
                content=query,
                feature=feature,
                metadata=metadata or {},
            )
        )
        await self.repo.add_turn(
            ConversationTurn(
                session_id=session_id,
                turn_index=turn_index,
                role="assistant",
                content=answer,
                feature=feature,
                metadata=metadata or {},
                nodes=nodes or [],
            )
        )

    async def save_learning_memories(
        self,
        *,
        user_id: str,
        session_id: str,
        inputs: dict[str, Any],
        final_output: str,
    ) -> list[str]:
        memories: list[tuple[str, str, list[str]]] = []
        assignment_type = (inputs.get("assignment_type") or "").strip()
        style = (inputs.get("style") or "").strip()
        rubric_focus = (inputs.get("rubric_focus") or inputs.get("change_request") or "").strip()
        title = (inputs.get("title") or "").strip()

        if assignment_type:
            memories.append(
                (
                    "profile",
                    f"学生近期在做“{assignment_type}”类写作任务，题目为“{title or '未命名'}”。",
                    ["任务类型", assignment_type],
                )
            )
        if style:
            memories.append(("preference", f"学生偏好的写作风格是：{style}。", ["风格偏好"]))
        if rubric_focus:
            memories.append(("rule", f"写作时需要重点满足这些评分关注点：{rubric_focus}。", ["评分标准"]))
        if final_output and not self._looks_like_dirty_memory(final_output):
            preview = self._compact_memory(final_output, limit=180)
            # 长期记忆只保存摘要，不保存全文，既减少污染，也避免下轮 Prompt 过长。
            memories.append(
                (
                    "experience",
                    f"一次写作经验：围绕《{title or '未命名'}》完成过{assignment_type or '写作'}任务，产出摘要：{preview}",
                    ["历史产出", assignment_type or "写作"],
                )
            )

        saved: list[str] = []
        for kind, content, tags in memories:
            memory = await self.repo.add_long_term_memory(
                user_id=user_id,
                kind=kind,
                content=content,
                tags=tags,
                source_session_id=session_id,
                metadata={"title": title, "feature": inputs.get("feature", "")},
            )
            saved.append(memory.content)
        return saved

    async def overview(self, user_id: str) -> dict[str, Any]:
        stats = await self.repo.stats(user_id)
        sessions = await self.repo.list_sessions(user_id, limit=10)
        memories = await self.repo.list_long_term_memories(user_id, limit=20)
        return {
            "stats": stats,
            "sessions": sessions,
            "long_term_memories": [memory.__dict__ for memory in memories if not self._looks_like_dirty_memory(memory.content)],
        }

    def _compact_memory(self, text: str, limit: int = 220) -> str:
        text = re.sub(r"#+\s*(写作结果|质量自检|本次使用的记忆|记忆说明).*", "", text or "", flags=re.S)
        text = re.sub(r"【百炼云模型暂不可用.*?】", "", text, flags=re.S)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:limit] + ("..." if len(text) > limit else "")

    def _looks_like_dirty_memory(self, text: str) -> bool:
        dirty_markers = [
            "百炼云模型暂不可用",
            "本地演示模型生成",
            "????????",
            "## 本次使用的记忆",
            "涓€",
            "璇",
            "鐧",
            "鏅",
        ]
        return any(marker in (text or "") for marker in dirty_markers)
