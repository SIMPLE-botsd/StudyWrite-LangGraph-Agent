from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.memory.models import ConversationTurn, LongTermMemory


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationRepository:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path or settings.MEMORY_DB_PATH)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    def _init_sync(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT,
                    feature TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    deleted_at TEXT
                );

                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    feature TEXT,
                    metadata_json TEXT,
                    nodes_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES conversation_sessions(session_id)
                );

                CREATE INDEX IF NOT EXISTS idx_turns_session
                    ON conversation_turns(session_id, turn_index, role);

                CREATE TABLE IF NOT EXISTS long_term_memories (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags_json TEXT,
                    source_session_id TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_memories_user
                    ON long_term_memories(user_id, kind, updated_at);
                """
            )
            self._ensure_column(conn, "conversation_sessions", "deleted_at", "TEXT")

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

    async def create_session(self, session_id: str, user_id: str, title: str, feature: str) -> None:
        await asyncio.to_thread(self._create_session_sync, session_id, user_id, title, feature)

    def _create_session_sync(self, session_id: str, user_id: str, title: str, feature: str) -> None:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversation_sessions(session_id, user_id, title, feature, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    user_id=excluded.user_id,
                    title=COALESCE(NULLIF(excluded.title, ''), conversation_sessions.title),
                    feature=excluded.feature,
                    updated_at=excluded.updated_at,
                    deleted_at=NULL
                """,
                (session_id, user_id, title, feature, now, now),
            )

    async def get_max_turn_index(self, session_id: str) -> int:
        return await asyncio.to_thread(self._get_max_turn_index_sync, session_id)

    def _get_max_turn_index_sync(self, session_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(turn_index), 0) AS max_turn FROM conversation_turns WHERE session_id=?",
                (session_id,),
            ).fetchone()
            return int(row["max_turn"] or 0)

    async def add_turn(self, turn: ConversationTurn) -> None:
        await asyncio.to_thread(self._add_turn_sync, turn)

    def _add_turn_sync(self, turn: ConversationTurn) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversation_turns(
                    session_id, turn_index, role, content, feature,
                    metadata_json, nodes_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn.session_id,
                    turn.turn_index,
                    turn.role,
                    turn.content,
                    turn.feature,
                    json.dumps(turn.metadata, ensure_ascii=False),
                    json.dumps(turn.nodes, ensure_ascii=False),
                    turn.created_at or utc_now(),
                ),
            )
            conn.execute(
                "UPDATE conversation_sessions SET updated_at=? WHERE session_id=?",
                (utc_now(), turn.session_id),
            )

    async def get_recent_turns(self, session_id: str, limit: int = 8) -> list[ConversationTurn]:
        return await asyncio.to_thread(self._get_recent_turns_sync, session_id, limit)

    def _get_recent_turns_sync(self, session_id: str, limit: int) -> list[ConversationTurn]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM conversation_turns
                WHERE session_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        turns = [self._row_to_turn(row) for row in rows]
        return list(reversed(turns))

    async def list_sessions(
        self,
        user_id: str,
        limit: int = 20,
        *,
        query: str = "",
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_sessions_sync, user_id, limit, query, include_deleted)

    def _list_sessions_sync(self, user_id: str, limit: int, query: str, include_deleted: bool) -> list[dict[str, Any]]:
        filters = ["s.user_id=?"]
        params: list[Any] = [user_id]
        if not include_deleted:
            filters.append("s.deleted_at IS NULL")
        if query.strip():
            filters.append(
                """
                (
                    s.title LIKE ?
                    OR s.session_id LIKE ?
                    OR EXISTS (
                        SELECT 1 FROM conversation_turns t
                        WHERE t.session_id=s.session_id AND t.content LIKE ?
                    )
                )
                """
            )
            like = f"%{query.strip()}%"
            params.extend([like, like, like])
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    s.session_id,
                    s.user_id,
                    s.title,
                    s.feature,
                    s.created_at,
                    s.updated_at,
                    s.deleted_at,
                    COUNT(t.id) AS turn_count,
                    MAX(CASE WHEN t.role='user' THEN t.content ELSE '' END) AS last_user_message,
                    MAX(CASE WHEN t.role='assistant' THEN t.content ELSE '' END) AS last_assistant_message
                FROM conversation_sessions s
                LEFT JOIN conversation_turns t ON t.session_id=s.session_id
                WHERE {" AND ".join(filters)}
                GROUP BY s.session_id
                ORDER BY s.updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._session_row_to_dict(row) for row in rows]

    async def get_session(self, user_id: str, session_id: str, *, include_deleted: bool = True) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_session_sync, user_id, session_id, include_deleted)

    def _get_session_sync(self, user_id: str, session_id: str, include_deleted: bool) -> dict[str, Any] | None:
        filters = ["s.user_id=?", "s.session_id=?"]
        params: list[Any] = [user_id, session_id]
        if not include_deleted:
            filters.append("s.deleted_at IS NULL")
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT
                    s.session_id,
                    s.user_id,
                    s.title,
                    s.feature,
                    s.created_at,
                    s.updated_at,
                    s.deleted_at,
                    COUNT(t.id) AS turn_count,
                    MAX(CASE WHEN t.role='user' THEN t.content ELSE '' END) AS last_user_message,
                    MAX(CASE WHEN t.role='assistant' THEN t.content ELSE '' END) AS last_assistant_message
                FROM conversation_sessions s
                LEFT JOIN conversation_turns t ON t.session_id=s.session_id
                WHERE {" AND ".join(filters)}
                GROUP BY s.session_id
                """,
                params,
            ).fetchone()
        return self._session_row_to_dict(row) if row else None

    async def get_session_turns(self, user_id: str, session_id: str, *, include_deleted: bool = True) -> list[ConversationTurn]:
        return await asyncio.to_thread(self._get_session_turns_sync, user_id, session_id, include_deleted)

    def _get_session_turns_sync(self, user_id: str, session_id: str, include_deleted: bool) -> list[ConversationTurn]:
        filters = ["s.user_id=?", "s.session_id=?"]
        params: list[Any] = [user_id, session_id]
        if not include_deleted:
            filters.append("s.deleted_at IS NULL")
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT t.*
                FROM conversation_turns t
                JOIN conversation_sessions s ON t.session_id=s.session_id
                WHERE {" AND ".join(filters)}
                ORDER BY t.turn_index ASC, t.id ASC
                """,
                params,
            ).fetchall()
        return [self._row_to_turn(row) for row in rows]

    async def soft_delete_session(self, user_id: str, session_id: str) -> bool:
        return await asyncio.to_thread(self._set_session_deleted_sync, user_id, session_id, utc_now())

    async def restore_session(self, user_id: str, session_id: str) -> bool:
        return await asyncio.to_thread(self._set_session_deleted_sync, user_id, session_id, None)

    def _set_session_deleted_sync(self, user_id: str, session_id: str, deleted_at: str | None) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE conversation_sessions
                SET deleted_at=?, updated_at=?
                WHERE user_id=? AND session_id=?
                """,
                (deleted_at, utc_now(), user_id, session_id),
            )
            return cursor.rowcount > 0

    async def add_long_term_memory(
        self,
        *,
        user_id: str,
        kind: str,
        content: str,
        tags: list[str] | None = None,
        source_session_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> LongTermMemory:
        return await asyncio.to_thread(
            self._add_long_term_memory_sync,
            user_id,
            kind,
            content,
            tags or [],
            source_session_id,
            metadata or {},
        )

    def _add_long_term_memory_sync(
        self,
        user_id: str,
        kind: str,
        content: str,
        tags: list[str],
        source_session_id: str,
        metadata: dict[str, Any],
    ) -> LongTermMemory:
        now = utc_now()
        memory = LongTermMemory(
            id=str(uuid.uuid4()),
            user_id=user_id,
            kind=kind,
            content=content.strip(),
            tags=tags,
            source_session_id=source_session_id,
            metadata=metadata,
            created_at=now,
            updated_at=now,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO long_term_memories(
                    id, user_id, kind, content, tags_json,
                    source_session_id, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.id,
                    memory.user_id,
                    memory.kind,
                    memory.content,
                    json.dumps(memory.tags, ensure_ascii=False),
                    memory.source_session_id,
                    json.dumps(memory.metadata, ensure_ascii=False),
                    memory.created_at,
                    memory.updated_at,
                ),
            )
        return memory

    async def list_long_term_memories(self, user_id: str, limit: int = 50) -> list[LongTermMemory]:
        return await asyncio.to_thread(self._list_long_term_memories_sync, user_id, limit)

    def _list_long_term_memories_sync(self, user_id: str, limit: int) -> list[LongTermMemory]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM long_term_memories
                WHERE user_id=?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [self._row_to_memory(row) for row in rows]

    async def search_long_term_memories(self, user_id: str, query: str, limit: int = 5) -> list[LongTermMemory]:
        memories = await self.list_long_term_memories(user_id, limit=120)
        query_terms = set(self._tokenize(query))
        if not query_terms:
            return memories[:limit]
        scored: list[LongTermMemory] = []
        for memory in memories:
            haystack = " ".join([memory.content, " ".join(memory.tags), memory.kind])
            terms = set(self._tokenize(haystack))
            overlap = len(query_terms & terms)
            if overlap == 0:
                continue
            memory.score = overlap / max(len(query_terms), 1)
            scored.append(memory)
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]

    async def stats(self, user_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._stats_sync, user_id)

    def _stats_sync(self, user_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            session_count = conn.execute(
                "SELECT COUNT(*) AS c FROM conversation_sessions WHERE user_id=? AND deleted_at IS NULL",
                (user_id,),
            ).fetchone()["c"]
            turn_count = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM conversation_turns t
                JOIN conversation_sessions s ON t.session_id=s.session_id
                WHERE s.user_id=? AND s.deleted_at IS NULL
                """,
                (user_id,),
            ).fetchone()["c"]
            rows = conn.execute(
                """
                SELECT kind, COUNT(*) AS c
                FROM long_term_memories
                WHERE user_id=?
                GROUP BY kind
                """,
                (user_id,),
            ).fetchall()
        return {
            "session_count": session_count,
            "turn_count": turn_count,
            "memory_count_by_kind": {row["kind"]: row["c"] for row in rows},
        }

    def _session_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["title"] = self._repair_mojibake(item.get("title") or "")
        for key in ("last_user_message", "last_assistant_message"):
            item[key] = self._compact(item.get(key) or "", 180)
        item["deleted"] = bool(item.get("deleted_at"))
        return item

    def _row_to_turn(self, row: sqlite3.Row) -> ConversationTurn:
        return ConversationTurn(
            session_id=row["session_id"],
            turn_index=int(row["turn_index"]),
            role=row["role"],
            content=self._repair_mojibake(row["content"]),
            feature=row["feature"] or "",
            metadata=json.loads(row["metadata_json"] or "{}"),
            nodes=json.loads(row["nodes_json"] or "[]"),
            created_at=row["created_at"] or "",
        )

    def _row_to_memory(self, row: sqlite3.Row) -> LongTermMemory:
        return LongTermMemory(
            id=row["id"],
            user_id=row["user_id"],
            kind=row["kind"],
            content=self._repair_mojibake(row["content"]),
            tags=[self._repair_mojibake(tag) for tag in json.loads(row["tags_json"] or "[]")],
            source_session_id=row["source_session_id"] or "",
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )

    def _tokenize(self, text: str) -> list[str]:
        text = (text or "").lower()
        rough = []
        buff = []
        for char in text:
            if char.isalnum() or "\u4e00" <= char <= "\u9fff":
                buff.append(char)
            elif buff:
                rough.append("".join(buff))
                buff = []
        if buff:
            rough.append("".join(buff))
        tokens = set(rough)
        for word in rough:
            if len(word) > 2 and any("\u4e00" <= ch <= "\u9fff" for ch in word):
                tokens.update(word[i : i + 2] for i in range(len(word) - 1))
        return list(tokens)

    def _compact(self, text: str, limit: int = 180) -> str:
        text = self._repair_mojibake(text)
        text = " ".join((text or "").split())
        return text[:limit] + ("..." if len(text) > limit else "")

    def _repair_mojibake(self, text: str) -> str:
        if not text or not any(marker in text for marker in ("ä", "å", "è", "ç", "ã", "â")):
            return text or ""
        try:
            repaired = text.encode("latin1").decode("utf-8")
        except UnicodeError:
            return text
        old_cjk = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
        new_cjk = sum(1 for char in repaired if "\u4e00" <= char <= "\u9fff")
        return repaired if new_cjk > old_cjk else text
