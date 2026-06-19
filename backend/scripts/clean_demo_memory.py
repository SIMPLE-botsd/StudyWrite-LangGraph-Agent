from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings


def main() -> None:
    db_path = settings.MEMORY_DB_PATH
    if not db_path.exists():
        print(f"memory db not found: {db_path}")
        return

    with sqlite3.connect(db_path) as conn:
        before_memories = conn.execute("SELECT COUNT(*) FROM long_term_memories").fetchone()[0]
        before_turns = conn.execute("SELECT COUNT(*) FROM conversation_turns").fetchone()[0]
        conn.execute(
            """
            DELETE FROM long_term_memories
            WHERE user_id = 'student-demo'
               OR content LIKE '%百炼云模型暂不可用%'
               OR content LIKE '%本地演示模型生成%'
               OR content LIKE '%????????%'
               OR content LIKE '%## 本次使用的记忆%'
               OR content LIKE '%涓€%'
               OR content LIKE '%璇%'
               OR content LIKE '%鐧%'
               OR content LIKE '%鏅%'
            """
        )
        conn.execute(
            """
            DELETE FROM conversation_turns
            WHERE session_id IN ('coursework-demo', 'verify-session', 'bailian-fallback-check')
               OR content LIKE '%百炼云模型暂不可用%'
               OR content LIKE '%本地演示模型生成%'
               OR content LIKE '%????????%'
               OR content LIKE '%## 本次使用的记忆%'
            """
        )
        after_memories = conn.execute("SELECT COUNT(*) FROM long_term_memories").fetchone()[0]
        after_turns = conn.execute("SELECT COUNT(*) FROM conversation_turns").fetchone()[0]

    print(f"long_term_memories: {before_memories} -> {after_memories}")
    print(f"conversation_turns: {before_turns} -> {after_turns}")


if __name__ == "__main__":
    main()
