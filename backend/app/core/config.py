from __future__ import annotations

import os
from pathlib import Path


def load_env_file() -> None:
    """Load backend/.env without adding an extra runtime dependency."""

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file()


class Settings:
    """Runtime settings kept intentionally simple for a student project demo."""

    PROJECT_NAME = "DeepPen LangGraph Agent"
    DESCRIPTION = "面向学生课程大作业的 LangGraph 写作智能体，内置短期记忆和长期记忆。"
    VERSION = "0.1.0"
    PREFIX_API = "/writeapi/v1"

    BASE_DIR = Path(__file__).resolve().parents[2]
    DATA_DIR = Path(os.getenv("STUDYWRITE_DATA_DIR", BASE_DIR / "data"))
    MEMORY_DB_PATH = Path(os.getenv("STUDYWRITE_MEMORY_DB", DATA_DIR / "student_writer.sqlite3"))

    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "bailian")
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
    BAILIAN_API_KEY = os.getenv("BAILIAN_API_KEY", "")
    BAILIAN_BASE_URL = os.getenv(
        "BAILIAN_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
    MODEL_NAME = os.getenv("MODEL_NAME", "qwen3.6-flash-2026-04-16")
    MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.25"))
    MODEL_TIMEOUT_SECONDS = float(os.getenv("MODEL_TIMEOUT_SECONDS", "90"))
    ALLOW_LOCAL_FALLBACK = os.getenv("ALLOW_LOCAL_FALLBACK", "true").lower() in {"1", "true", "yes", "on"}

    @property
    def active_api_key(self) -> str:
        if self.LLM_PROVIDER.lower() in {"bailian", "dashscope", "model_studio"}:
            return self.DASHSCOPE_API_KEY or self.BAILIAN_API_KEY or self.OPENAI_API_KEY
        return self.OPENAI_API_KEY

    @property
    def active_base_url(self) -> str:
        if self.LLM_PROVIDER.lower() in {"bailian", "dashscope", "model_studio"}:
            return self.BAILIAN_BASE_URL
        return self.OPENAI_BASE_URL

    @property
    def model_config_summary(self) -> dict[str, str | bool]:
        return {
            "provider": self.LLM_PROVIDER,
            "model": self.MODEL_NAME,
            "base_url": self.active_base_url,
            "has_api_key": bool(self.active_api_key),
            "allow_local_fallback": self.ALLOW_LOCAL_FALLBACK,
        }

    MAX_REVISIONS = int(os.getenv("MAX_REVISIONS", "2"))
    PASS_SCORE = float(os.getenv("PASS_SCORE", "7.2"))
    MEMORY_MAX_TURNS = int(os.getenv("MEMORY_MAX_TURNS", "4"))
    MEMORY_TOP_K = int(os.getenv("MEMORY_TOP_K", "5"))

    KNOWLEDGE_BACKEND = os.getenv("KNOWLEDGE_BACKEND", "local_turbovec")

    RAGFLOW_BASE_URL = os.getenv("RAGFLOW_BASE_URL", "https://cloud.ragflow.io").rstrip("/")
    RAGFLOW_API_KEY = os.getenv("RAGFLOW_API_KEY", "")
    RAGFLOW_TIMEOUT_SECONDS = float(os.getenv("RAGFLOW_TIMEOUT_SECONDS", "60"))
    RAGFLOW_DEFAULT_TOP_K = int(os.getenv("RAGFLOW_DEFAULT_TOP_K", "6"))
    RAGFLOW_DEFAULT_DATASET_IDS = [
        item.strip()
        for item in os.getenv("RAGFLOW_DEFAULT_DATASET_IDS", "").split(",")
        if item.strip()
    ]

    @property
    def ragflow_config_summary(self) -> dict[str, str | bool | int]:
        return {
            "base_url": self.RAGFLOW_BASE_URL,
            "has_api_key": bool(self.RAGFLOW_API_KEY),
            "default_dataset_count": len(self.RAGFLOW_DEFAULT_DATASET_IDS),
            "default_top_k": self.RAGFLOW_DEFAULT_TOP_K,
        }

    @staticmethod
    def _path_env(name: str, default: Path) -> Path:
        value = os.getenv(name, "").strip()
        return Path(value) if value else default

    TURBOVEC_DB_PATH = _path_env.__func__("TURBOVEC_DB_PATH", DATA_DIR / "turbovec_knowledge.sqlite3")
    TURBOVEC_INDEX_PATH = _path_env.__func__("TURBOVEC_INDEX_PATH", DATA_DIR / "turbovec_index.tvim")
    TURBOVEC_SOURCE_PATH = os.getenv("TURBOVEC_SOURCE_PATH", "")
    TURBOVEC_DIM = int(os.getenv("TURBOVEC_DIM", "512"))
    TURBOVEC_BIT_WIDTH = int(os.getenv("TURBOVEC_BIT_WIDTH", "4"))
    TURBOVEC_CHUNK_SIZE = int(os.getenv("TURBOVEC_CHUNK_SIZE", "900"))
    TURBOVEC_CHUNK_OVERLAP = int(os.getenv("TURBOVEC_CHUNK_OVERLAP", "120"))
    TURBOVEC_DEFAULT_TOP_K = int(os.getenv("TURBOVEC_DEFAULT_TOP_K", str(RAGFLOW_DEFAULT_TOP_K)))
    TURBOVEC_DEFAULT_DATASET_IDS = [
        item.strip()
        for item in os.getenv("TURBOVEC_DEFAULT_DATASET_IDS", "").split(",")
        if item.strip()
    ]

    CORS_ORIGINS = [
        item.strip()
        for item in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if item.strip()
    ]


settings = Settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
