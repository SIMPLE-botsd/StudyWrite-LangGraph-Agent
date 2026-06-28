from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings


class RagflowNotConfigured(RuntimeError):
    pass


@dataclass
class RagflowFile:
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


class RagflowService:
    """RAGFlow HTTP 代理层：浏览器不直接接触 API Key，便于安全演示和统一异常处理。"""

    def __init__(self):
        self.base_url = settings.RAGFLOW_BASE_URL
        self.api_key = settings.RAGFLOW_API_KEY
        self.timeout = settings.RAGFLOW_TIMEOUT_SECONDS

    def status(self) -> dict[str, Any]:
        return settings.ragflow_config_summary

    async def list_datasets(self, page: int = 1, page_size: int = 100) -> list[dict[str, Any]]:
        payload = await self._request(
            "GET",
            "/api/v1/datasets",
            params={"page": page, "page_size": page_size},
        )
        rows = self._extract_list(payload)
        return [self._normalize_dataset(item) for item in rows]

    async def create_dataset(self, name: str, description: str = "") -> dict[str, Any]:
        payload = await self._request(
            "POST",
            "/api/v1/datasets",
            json={"name": name, "description": description},
        )
        data = self._extract_data(payload)
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            data = {"id": str(data), "name": name, "description": description}
        return self._normalize_dataset(data)

    async def upload_document(self, dataset_id: str, file: RagflowFile) -> dict[str, Any]:
        files = {"file": (file.filename, file.content, file.content_type)}
        payload = await self._request(
            "POST",
            f"/api/v1/datasets/{dataset_id}/documents",
            files=files,
        )
        data = self._extract_data(payload)
        docs = data if isinstance(data, list) else [data]
        normalized_docs = [self._normalize_document(doc) for doc in docs if doc]
        document_ids = [doc["id"] for doc in normalized_docs if doc.get("id")]
        parse_result = None
        if document_ids:
            # RAGFlow 上传后需要显式触发解析，解析完成后才能参与后续检索。
            parse_result = await self.parse_documents(dataset_id, document_ids)
        return {"documents": normalized_docs, "parse": parse_result}

    async def parse_documents(self, dataset_id: str, document_ids: list[str]) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/datasets/{dataset_id}/chunks",
            json={"document_ids": document_ids},
        )

    async def retrieve(
        self,
        question: str,
        dataset_ids: list[str],
        *,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        clean_ids = [item for item in dataset_ids if item]
        if not clean_ids:
            clean_ids = settings.RAGFLOW_DEFAULT_DATASET_IDS
        if not clean_ids:
            return {"chunks": [], "message": "未选择 RAGFlow 知识库。"}

        # 这里保持 RAGFlow 原生 retrieval 入参，返回后再标准化成项目内部的 chunk 结构。
        body = {
            "question": question,
            "dataset_ids": clean_ids,
            "top_k": top_k or settings.RAGFLOW_DEFAULT_TOP_K,
        }
        payload = await self._request("POST", "/api/v1/retrieval", json=body)
        data = self._extract_data(payload)
        chunks = self._extract_chunks(data)
        return {
            "chunks": [self._normalize_chunk(chunk) for chunk in chunks],
            "raw_count": len(chunks),
        }

    async def initialize_writing_datasets(self) -> list[dict[str, Any]]:
        created = []
        for seed in _writing_dataset_seeds():
            dataset = await self._find_or_create_dataset(seed["name"], seed["description"])
            file = RagflowFile(
                filename=f"{seed['name']}.md",
                content=seed["content"].encode("utf-8"),
                content_type="text/markdown",
            )
            upload = await self.upload_document(dataset["id"], file)
            created.append({"dataset": dataset, "upload": upload})
        return created

    async def _find_or_create_dataset(self, name: str, description: str) -> dict[str, Any]:
        try:
            for dataset in await self.list_datasets():
                if dataset.get("name") == name:
                    return dataset
        except Exception:
            pass
        return await self.create_dataset(name, description)

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        if not self.api_key:
            raise RagflowNotConfigured("RAGFLOW_API_KEY 未配置，请先在 backend/.env 中填写 RAGFlow API Key。")
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        # Key 只在后端请求头中使用，前端接口和浏览器日志都不会暴露真实密钥。
        headers["Authorization"] = f"Bearer {self.api_key}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, url, headers=headers, **kwargs)
        if response.status_code >= 400:
            detail = response.text[:500]
            raise RuntimeError(f"RAGFlow 请求失败：{response.status_code} {detail}")
        if not response.content:
            return {}
        payload = response.json()
        if isinstance(payload, dict) and payload.get("code") not in (None, 0):
            raise RuntimeError(str(payload.get("message") or payload))
        return payload

    def _extract_data(self, payload: Any) -> Any:
        if isinstance(payload, dict):
            return payload.get("data", payload)
        return payload

    def _extract_list(self, payload: Any) -> list[Any]:
        data = self._extract_data(payload)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("items", "datasets", "docs", "documents", "chunks"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []

    def _extract_chunks(self, data: Any) -> list[Any]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("chunks", "items", "records", "data"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
            doc_aggs = data.get("doc_aggs")
            if isinstance(doc_aggs, list):
                return doc_aggs
        return []

    def _normalize_dataset(self, item: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            return {"id": str(item), "name": str(item), "description": ""}
        return {
            "id": str(item.get("id") or item.get("dataset_id") or ""),
            "name": str(item.get("name") or item.get("title") or "未命名知识库"),
            "description": str(item.get("description") or item.get("desc") or ""),
            "document_count": item.get("document_count") or item.get("doc_num") or item.get("documents_count") or 0,
            "chunk_count": item.get("chunk_count") or item.get("chunk_num") or 0,
            "raw": item,
        }

    def _normalize_document(self, item: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            return {"id": str(item), "name": str(item)}
        return {
            "id": str(item.get("id") or item.get("document_id") or ""),
            "name": str(item.get("name") or item.get("filename") or item.get("file_name") or "未命名文档"),
            "status": item.get("status") or item.get("run") or "",
            "raw": item,
        }

    def _normalize_chunk(self, item: Any) -> dict[str, Any]:
        # 不同版本 RAGFlow 字段名略有差异，统一字段后 Agent 和引用模块才能稳定复用。
        if not isinstance(item, dict):
            return {"content": str(item), "score": 0, "document_name": ""}
        content = (
            item.get("content")
            or item.get("text")
            or item.get("chunk")
            or item.get("answer")
            or item.get("important_keywords")
            or ""
        )
        if isinstance(content, (list, dict)):
            content = json.dumps(content, ensure_ascii=False)
        return {
            "content": str(content),
            "score": item.get("similarity") or item.get("score") or item.get("vector_similarity") or 0,
            "document_name": item.get("document_name") or item.get("doc_name") or item.get("name") or "",
            "dataset_id": item.get("dataset_id") or item.get("kb_id") or "",
            "raw": item,
        }


def format_rag_chunks(chunks: list[dict[str, Any]], limit: int = 6) -> str:
    if not chunks:
        return ""
    lines = ["RAGFlow 知识库检索结果："]
    for index, chunk in enumerate(chunks[:limit], start=1):
        content = " ".join(str(chunk.get("content", "")).split())
        if len(content) > 520:
            content = content[:520] + "..."
        source = chunk.get("document_name") or "知识库片段"
        score = chunk.get("score")
        score_text = f"，相关度 {score:.3f}" if isinstance(score, (int, float)) else ""
        lines.append(f"{index}. 来源：{source}{score_text}\n   {content}")
    return "\n".join(lines)


def _writing_dataset_seeds() -> list[dict[str, str]]:
    seed_dir = Path(__file__).resolve().parents[2] / "ragflow_seed"
    return [
        {
            "name": "大学课程论文写作方法库",
            "description": "课程论文选题、论点、结构和论证方法。",
            "content": (seed_dir / "course_paper_guide.md").read_text(encoding="utf-8"),
        },
        {
            "name": "实验报告与实践报告写作库",
            "description": "实验报告、社会实践报告和数据分析写作规范。",
            "content": (seed_dir / "report_guide.md").read_text(encoding="utf-8"),
        },
        {
            "name": "AI学习方式与学术规范素材库",
            "description": "生成式 AI 学习场景、风险分析和学术诚信写作素材。",
            "content": (seed_dir / "ai_learning_ethics.md").read_text(encoding="utf-8"),
        },
    ]


ragflow_service = RagflowService()
