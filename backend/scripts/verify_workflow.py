from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.graph.registry import registry
from app.memory import init_database


async def main() -> None:
    await init_database()
    builder = registry.get_workflow("generate_assignment")
    payload = {
        "feature": "generate_assignment",
        "session_id": "verify-session",
        "user_id": "student-demo",
        "title": "人工智能对大学学习方式的影响",
        "assignment_type": "课程论文",
        "task_description": "结合课堂讨论分析影响并提出建议。",
        "materials": "AI 可以辅助检索资料，但也可能造成依赖。",
        "style": "清晰、正式、学生化",
        "word_count": "800",
        "rubric_focus": "观点明确，材料支撑。",
        "use_memory": True,
        "use_llm": False,
        "memory_k": 3,
    }
    final_seen = False
    async for chunk in builder.process(payload):
        print(f"{chunk['node']}: {chunk['event']}")
        if chunk.get("node") == "render" and chunk.get("typy") == "result":
            final_seen = True
    if not final_seen:
        raise SystemExit("workflow did not produce final render")
    print("workflow ok")


if __name__ == "__main__":
    asyncio.run(main())
