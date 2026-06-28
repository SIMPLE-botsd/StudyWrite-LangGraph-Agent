from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.services.ragflow_service import RagflowFile, format_rag_chunks, ragflow_service
from app.services.turbovec_service import TurboVecFile, format_turbovec_chunks, turbovec_service


@dataclass
class KnowledgeFile:
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


class KnowledgeService:
    """知识库统一入口：对上层隐藏 RAGFlow 与本地 TurboVec 的差异。"""

    @property
    def backend(self) -> str:
        return settings.KNOWLEDGE_BACKEND

    def _use_turbovec(self) -> bool:
        # 课程演示优先保证离线可跑，本地 TurboVec/SQLite 后端不依赖外部知识库服务。
        return self.backend.lower() in {"turbovec", "local_turbovec", "local", "sqlite"}

    def status(self) -> dict[str, Any]:
        data = turbovec_service.status() if self._use_turbovec() else ragflow_service.status()
        data["knowledge_backend"] = self.backend
        return data

    async def list_datasets(self) -> list[dict[str, Any]]:
        if self._use_turbovec():
            return await turbovec_service.list_datasets()
        return await ragflow_service.list_datasets()

    async def create_dataset(self, name: str, description: str = "") -> dict[str, Any]:
        if self._use_turbovec():
            return await turbovec_service.create_dataset(name, description)
        return await ragflow_service.create_dataset(name, description)

    async def upload_document(self, dataset_id: str, file: KnowledgeFile) -> dict[str, Any]:
        # 上传接口只接收统一文件对象，具体如何解析、切片和建索引交给当前知识库后端。
        if self._use_turbovec():
            return await turbovec_service.upload_document(
                dataset_id,
                TurboVecFile(
                    filename=file.filename,
                    content=file.content,
                    content_type=file.content_type,
                ),
            )
        return await ragflow_service.upload_document(
            dataset_id,
            RagflowFile(
                filename=file.filename,
                content=file.content,
                content_type=file.content_type,
            ),
        )

    async def retrieve(self, question: str, dataset_ids: list[str], *, top_k: int | None = None) -> dict[str, Any]:
        if self._use_turbovec():
            return await turbovec_service.retrieve(question, dataset_ids, top_k=top_k)
        return await ragflow_service.retrieve(question, dataset_ids, top_k=top_k)

    async def initialize_writing_datasets(self) -> list[dict[str, Any]]:
        if self._use_turbovec():
            return await turbovec_service.initialize_writing_datasets()
        return await ragflow_service.initialize_writing_datasets()

    def format_chunks(self, chunks: list[dict[str, Any]], limit: int = 6) -> str:
        # Graph 节点只需要可放进 Prompt 的文本，上下游不直接依赖某个检索服务的原始字段。
        if self._use_turbovec():
            return format_turbovec_chunks(chunks, limit=limit)
        return format_rag_chunks(chunks, limit=limit)

    def empty_message(self) -> str:
        if self._use_turbovec():
            return "本地 TurboVec 知识库未检索到可用片段，请优先使用用户材料和本地写作指南。"
        return "RAGFlow 知识库未检索到可用片段，请优先使用用户材料和本地写作指南。"

    def error_message(self, exc: Exception) -> str:
        if self._use_turbovec():
            return f"本地 TurboVec 检索暂不可用：{exc}"
        return f"RAGFlow 检索暂不可用：{exc}"


knowledge_service = KnowledgeService()
