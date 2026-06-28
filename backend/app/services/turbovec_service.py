from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sqlite3
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np

from app.core.config import settings


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TurboVecFile:
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


class HashingTextEmbedder:
    """轻量确定性向量器：用于本地演示检索，不依赖模型下载或第三方 Embedding API。"""

    def __init__(self, dim: int):
        if dim <= 0 or dim % 8 != 0:
            raise ValueError("TURBOVEC_DIM 必须是大于 0 且能被 8 整除的整数。")
        self.dim = dim

    def encode(self, texts: list[str]) -> np.ndarray:
        # 哈希向量的好处是速度快、结果稳定，适合课程演示中的小型知识库检索。
        vectors = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for feature, weight in self._features(text):
                digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
                value = int.from_bytes(digest, "little", signed=False)
                index = value % self.dim
                sign = 1.0 if (value >> 63) == 0 else -1.0
                vectors[row, index] += sign * weight
            norm = float(np.linalg.norm(vectors[row]))
            if norm > 0:
                vectors[row] /= norm
        return vectors

    def _features(self, text: str):
        clean = re.sub(r"\s+", " ", (text or "").lower()).strip()
        if not clean:
            return

        for token in re.findall(r"[a-z0-9_]{2,}", clean):
            yield f"w:{token}", 1.4

        chars = [char for char in clean if not char.isspace()]
        for char in chars:
            if "\u4e00" <= char <= "\u9fff":
                yield f"c:{char}", 0.35
        for size, weight in ((2, 1.0), (3, 0.75), (4, 0.45)):
            if len(chars) < size:
                continue
            for idx in range(0, len(chars) - size + 1):
                yield f"g{size}:{''.join(chars[idx:idx + size])}", weight


class TurboVecKnowledgeService:
    """本地知识库服务：SQLite 存元数据和切片，TurboVec/NumPy 负责相似度检索。"""

    def __init__(self):
        self.db_path = settings.TURBOVEC_DB_PATH
        self.index_path = settings.TURBOVEC_INDEX_PATH
        self.dim = settings.TURBOVEC_DIM
        self.bit_width = settings.TURBOVEC_BIT_WIDTH
        self.embedder = HashingTextEmbedder(self.dim)
        self._lock = RLock()
        self._index: Any | None = None
        self._index_count = -1
        self._id_map_index = self._load_index_class()

    def _load_index_class(self):
        # TurboVec 是可选增强；导入失败时继续使用 NumPy 兜底，保证知识库功能不瘫痪。
        source_path = str(settings.TURBOVEC_SOURCE_PATH or "").strip()
        if source_path:
            source = Path(source_path).expanduser()
            if source.exists() and str(source) not in sys.path:
                sys.path.insert(0, str(source))
        try:
            from turbovec import IdMapIndex

            return IdMapIndex
        except Exception:
            return None

    @property
    def turbovec_available(self) -> bool:
        return self._id_map_index is not None

    def status(self) -> dict[str, Any]:
        self._init_sync()
        datasets = self._list_datasets_sync()
        return {
            "base_url": "local:turbovec",
            "has_api_key": True,
            "default_dataset_count": len(settings.TURBOVEC_DEFAULT_DATASET_IDS),
            "default_top_k": settings.TURBOVEC_DEFAULT_TOP_K,
            "backend": "turbovec",
            "engine": "turbovec" if self.turbovec_available else "numpy-fallback",
            "turbovec_available": self.turbovec_available,
            "dataset_count": len(datasets),
            "index_path": str(self.index_path),
            "db_path": str(self.db_path),
            "dim": self.dim,
            "bit_width": self.bit_width,
        }

    async def list_datasets(self, page: int = 1, page_size: int = 100) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_datasets_sync, page, page_size)

    async def create_dataset(self, name: str, description: str = "") -> dict[str, Any]:
        return await asyncio.to_thread(self._create_dataset_sync, name, description)

    async def upload_document(self, dataset_id: str, file: TurboVecFile) -> dict[str, Any]:
        # SQLite 操作和索引重建放到线程里执行，避免阻塞 FastAPI 的事件循环。
        return await asyncio.to_thread(self._upload_document_sync, dataset_id, file)

    async def retrieve(
        self,
        question: str,
        dataset_ids: list[str],
        *,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._retrieve_sync, question, dataset_ids, top_k or settings.TURBOVEC_DEFAULT_TOP_K)

    async def initialize_writing_datasets(self) -> list[dict[str, Any]]:
        from app.services.ragflow_service import _writing_dataset_seeds

        created = []
        for seed in _writing_dataset_seeds():
            dataset = await self.create_dataset(seed["name"], seed["description"])
            upload = await self.upload_document(
                dataset["id"],
                TurboVecFile(
                    filename=f"{seed['name']}.md",
                    content=seed["content"].encode("utf-8"),
                    content_type="text/markdown",
                ),
            )
            created.append({"dataset": dataset, "upload": upload})
        return created

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sync(self) -> None:
        with self._connect() as conn:
            # 三张表对应“知识库 - 文档 - 切片”，满足课程要求中的资料存储和检索链路。
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS turbovec_datasets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS turbovec_documents (
                    id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    content_type TEXT,
                    content_hash TEXT NOT NULL,
                    char_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(dataset_id) REFERENCES turbovec_datasets(id)
                );

                CREATE TABLE IF NOT EXISTS turbovec_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    char_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(dataset_id) REFERENCES turbovec_datasets(id),
                    FOREIGN KEY(document_id) REFERENCES turbovec_documents(id)
                );

                CREATE INDEX IF NOT EXISTS idx_turbovec_chunks_dataset
                    ON turbovec_chunks(dataset_id, id);

                CREATE INDEX IF NOT EXISTS idx_turbovec_chunks_document
                    ON turbovec_chunks(document_id, chunk_index);
                """
            )

    def _list_datasets_sync(self, page: int = 1, page_size: int = 100) -> list[dict[str, Any]]:
        self._init_sync()
        offset = max(page - 1, 0) * page_size
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    d.id,
                    d.name,
                    d.description,
                    d.created_at,
                    d.updated_at,
                    COUNT(DISTINCT doc.id) AS document_count,
                    COUNT(c.id) AS chunk_count
                FROM turbovec_datasets d
                LEFT JOIN turbovec_documents doc ON doc.dataset_id=d.id
                LEFT JOIN turbovec_chunks c ON c.dataset_id=d.id
                GROUP BY d.id
                ORDER BY d.updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (page_size, offset),
            ).fetchall()
        return [self._dataset_row_to_dict(row) for row in rows]

    def _create_dataset_sync(self, name: str, description: str = "") -> dict[str, Any]:
        self._init_sync()
        clean_name = (name or "本地知识库").strip()
        now = _utc_now()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM turbovec_datasets WHERE name=?",
                (clean_name,),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE turbovec_datasets SET description=COALESCE(NULLIF(?, ''), description), updated_at=? WHERE id=?",
                    (description, now, existing["id"]),
                )
                row = conn.execute("SELECT * FROM turbovec_datasets WHERE id=?", (existing["id"],)).fetchone()
            else:
                dataset_id = f"local-{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """
                    INSERT INTO turbovec_datasets(id, name, description, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (dataset_id, clean_name, description, now, now),
                )
                row = conn.execute("SELECT * FROM turbovec_datasets WHERE id=?", (dataset_id,)).fetchone()
        return self._dataset_row_to_dict(row)

    def _upload_document_sync(self, dataset_id: str, file: TurboVecFile) -> dict[str, Any]:
        self._init_sync()
        if not dataset_id:
            dataset = self._create_dataset_sync("默认本地知识库", "DeepPen 本地 TurboVec 知识库")
            dataset_id = dataset["id"]
        self._ensure_dataset_exists(dataset_id)

        # 上传后立即完成解码、切片、去重写库和索引重建，前端无需再触发额外解析步骤。
        text = self._decode_file(file.content)
        chunks = self._split_text(text)
        content_hash = hashlib.sha256(file.content).hexdigest()
        document_id = hashlib.sha256(f"{dataset_id}:{file.filename}:{content_hash}".encode("utf-8")).hexdigest()[:24]
        now = _utc_now()

        with self._connect() as conn:
            conn.execute("DELETE FROM turbovec_chunks WHERE document_id=?", (document_id,))
            conn.execute(
                """
                INSERT INTO turbovec_documents(
                    id, dataset_id, filename, content_type, content_hash,
                    char_count, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    filename=excluded.filename,
                    content_type=excluded.content_type,
                    content_hash=excluded.content_hash,
                    char_count=excluded.char_count,
                    updated_at=excluded.updated_at
                """,
                (
                    document_id,
                    dataset_id,
                    file.filename,
                    file.content_type,
                    content_hash,
                    len(text),
                    now,
                    now,
                ),
            )
            conn.executemany(
                """
                INSERT INTO turbovec_chunks(dataset_id, document_id, chunk_index, content, char_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (dataset_id, document_id, index, chunk, len(chunk), now)
                    for index, chunk in enumerate(chunks, start=1)
                ],
            )
            conn.execute("UPDATE turbovec_datasets SET updated_at=? WHERE id=?", (now, dataset_id))

        self._rebuild_index_sync()
        return {
            "documents": [
                {
                    "id": document_id,
                    "dataset_id": dataset_id,
                    "name": file.filename,
                    "status": "indexed",
                    "chunk_count": len(chunks),
                }
            ],
            "parse": {
                "backend": "turbovec",
                "engine": "turbovec" if self.turbovec_available else "numpy-fallback",
                "chunk_count": len(chunks),
            },
        }

    def _retrieve_sync(self, question: str, dataset_ids: list[str], top_k: int) -> dict[str, Any]:
        self._init_sync()
        clean_ids = [item for item in dataset_ids if item]
        if not clean_ids:
            clean_ids = settings.TURBOVEC_DEFAULT_DATASET_IDS
        # 先按知识库范围取候选切片，再做向量检索，避免不同数据集之间互相污染引用来源。
        candidates = self._load_candidate_chunks(clean_ids)
        if not candidates:
            return {
                "chunks": [],
                "raw_count": 0,
                "message": "本地知识库还没有可检索的切片，请先上传资料或初始化写作库。",
            }

        if self.turbovec_available:
            chunks = self._retrieve_with_turbovec(question, candidates, top_k)
            engine = "turbovec"
        else:
            chunks = self._retrieve_with_numpy(question, candidates, top_k)
            engine = "numpy-fallback"

        return {
            "chunks": chunks,
            "raw_count": len(chunks),
            "engine": engine,
            "message": f"本地 {engine} 检索完成。",
        }

    def _retrieve_with_turbovec(self, question: str, candidates: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        self._ensure_index_ready()
        if self._index is None:
            return self._retrieve_with_numpy(question, candidates, top_k)

        # allowlist 限定本次选择的数据集，索引可以全量复用，查询时仍能做到按库过滤。
        query_vector = self.embedder.encode([question])
        allowlist = np.array([item["id"] for item in candidates], dtype=np.uint64)
        if len(allowlist) == 0:
            return []
        scores, ids = self._index.search(query_vector, k=max(1, top_k), allowlist=allowlist)
        score_list = scores[0].tolist() if len(scores) else []
        id_list = ids[0].tolist() if len(ids) else []
        by_id = {int(item["id"]): item for item in candidates}
        results = []
        for score, chunk_id in zip(score_list, id_list):
            item = by_id.get(int(chunk_id))
            if item:
                results.append(self._chunk_to_result(item, float(score), "turbovec"))
        return results

    def _retrieve_with_numpy(self, question: str, candidates: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        # NumPy 兜底走同一套哈希向量，虽然不如专门索引快，但小规模资料演示足够稳定。
        query_vector = self.embedder.encode([question])[0]
        doc_vectors = self.embedder.encode([item["content"] for item in candidates])
        scores = doc_vectors @ query_vector
        order = np.argsort(-scores)[: max(1, top_k)]
        return [
            self._chunk_to_result(candidates[int(index)], float(scores[int(index)]), "numpy-fallback")
            for index in order
        ]

    def _ensure_index_ready(self) -> None:
        if not self.turbovec_available:
            return
        with self._lock:
            # 用切片总数判断索引是否过期，上传文档后会自动触发重建。
            total = self._chunk_count_sync()
            if self._index is not None and self._index_count == total:
                return
            if self.index_path.exists():
                try:
                    loaded = self._id_map_index.load(str(self.index_path))
                    if len(loaded) == total:
                        self._index = loaded
                        self._index_count = total
                        return
                except Exception:
                    pass
            self._rebuild_index_sync()

    def _rebuild_index_sync(self) -> None:
        if not self.turbovec_available:
            return
        with self._lock:
            rows = self._load_all_chunks()
            index = self._id_map_index(dim=self.dim, bit_width=self.bit_width)
            if rows:
                vectors = self.embedder.encode([row["content"] for row in rows])
                ids = np.array([int(row["id"]) for row in rows], dtype=np.uint64)
                index.add_with_ids(vectors, ids)
                index.prepare()
                self.index_path.parent.mkdir(parents=True, exist_ok=True)
                index.write(str(self.index_path))
            self._index = index
            self._index_count = len(rows)

    def _load_all_chunks(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    c.id, c.dataset_id, c.document_id, c.chunk_index, c.content,
                    d.name AS dataset_name, doc.filename AS document_name
                FROM turbovec_chunks c
                JOIN turbovec_datasets d ON d.id=c.dataset_id
                JOIN turbovec_documents doc ON doc.id=c.document_id
                ORDER BY c.id ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def _load_candidate_chunks(self, dataset_ids: list[str]) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if dataset_ids:
            placeholders = ",".join("?" for _ in dataset_ids)
            where = f"WHERE c.dataset_id IN ({placeholders})"
            params.extend(dataset_ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    c.id, c.dataset_id, c.document_id, c.chunk_index, c.content,
                    d.name AS dataset_name, doc.filename AS document_name
                FROM turbovec_chunks c
                JOIN turbovec_datasets d ON d.id=c.dataset_id
                JOIN turbovec_documents doc ON doc.id=c.document_id
                {where}
                ORDER BY c.id ASC
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def _chunk_count_sync(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM turbovec_chunks").fetchone()
        return int(row["c"] or 0)

    def _ensure_dataset_exists(self, dataset_id: str) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM turbovec_datasets WHERE id=?", (dataset_id,)).fetchone()
        if not row:
            raise ValueError("本地知识库不存在，请先刷新或初始化知识库。")

    def _decode_file(self, content: bytes) -> str:
        for encoding in ("utf-8", "utf-8-sig", "gb18030"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="ignore")

    def _split_text(self, text: str) -> list[str]:
        clean = re.sub(r"\r\n?", "\n", text or "")
        clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
        if not clean:
            return ["空文档。"]

        chunk_size = settings.TURBOVEC_CHUNK_SIZE
        overlap = min(settings.TURBOVEC_CHUNK_OVERLAP, chunk_size // 3)
        chunks: list[str] = []
        start = 0
        while start < len(clean):
            end = min(start + chunk_size, len(clean))
            if end < len(clean):
                # 优先在换行或句号处分块，降低引用片段被截断到半句话的概率。
                boundary = max(clean.rfind("\n", start, end), clean.rfind("。", start, end))
                if boundary > start + chunk_size * 0.55:
                    end = boundary + 1
            chunk = clean[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(clean):
                break
            start = max(end - overlap, start + 1)
        return chunks

    def _dataset_row_to_dict(self, row: sqlite3.Row | None) -> dict[str, Any]:
        if not row:
            return {}
        data = dict(row)
        data.setdefault("document_count", 0)
        data.setdefault("chunk_count", 0)
        data["raw"] = {"backend": "turbovec"}
        return data

    def _chunk_to_result(self, item: dict[str, Any], score: float, engine: str) -> dict[str, Any]:
        return {
            "content": item.get("content", ""),
            "score": score,
            "document_name": item.get("document_name") or "本地文档",
            "dataset_id": item.get("dataset_id") or "",
            "raw": {
                "backend": "turbovec",
                "engine": engine,
                "chunk_id": item.get("id"),
                "chunk_index": item.get("chunk_index"),
                "dataset_name": item.get("dataset_name"),
            },
        }


def format_turbovec_chunks(chunks: list[dict[str, Any]], limit: int = 6) -> str:
    if not chunks:
        return ""
    lines = ["本地 TurboVec 知识库检索结果："]
    for index, chunk in enumerate(chunks[:limit], start=1):
        content = " ".join(str(chunk.get("content", "")).split())
        if len(content) > 520:
            content = content[:520] + "..."
        source = chunk.get("document_name") or "本地知识库片段"
        score = chunk.get("score")
        score_text = f"，相关度 {score:.3f}" if isinstance(score, (int, float)) else ""
        raw = chunk.get("raw") if isinstance(chunk.get("raw"), dict) else {}
        engine = raw.get("engine", "turbovec")
        lines.append(f"{index}. 来源：{source}{score_text}，引擎：{engine}\n   {content}")
    return "\n".join(lines)


turbovec_service = TurboVecKnowledgeService()
