from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


class LocalStudyWriter:
    """Deterministic fallback model so the project can demo without paid API keys."""

    async def ainvoke(self, messages):
        user_text = "\n".join(getattr(message, "content", str(message)) for message in messages)
        return type("LocalMessage", (), {"content": self._respond(user_text)})()

    def _respond(self, prompt: str) -> str:
        prompt = prompt.strip()
        return (
            "这是本地演示模型生成的可编辑文本。\n\n"
            "1. 先拆解题目要求，明确写作对象、评分维度和材料依据。\n"
            "2. 再围绕中心论点组织段落，每段保留论点、证据、分析三个要素。\n"
            "3. 最后检查结构完整性、学术表达和原创性风险。\n\n"
            f"参考输入摘要：{prompt[:260]}"
        )


def get_chat_model(temperature: float = 0.2):
    provider = settings.LLM_PROVIDER.lower()
    api_key = settings.active_api_key
    base_url = settings.active_base_url

    if provider in {"bailian", "dashscope", "model_studio", "openai"} and api_key:
        try:
            from langchain_openai import ChatOpenAI

            kwargs = {
                "model": settings.MODEL_NAME,
                "temperature": temperature,
                "api_key": api_key,
                "timeout": settings.MODEL_TIMEOUT_SECONDS,
            }
            if base_url:
                kwargs["base_url"] = base_url
            return ChatOpenAI(**kwargs)
        except Exception as exc:
            logger.warning("Failed to initialize chat model, using local fallback: %s", exc)
            return LocalStudyWriter()
    return LocalStudyWriter()


async def invoke_text(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    *,
    allow_fallback: bool | None = None,
) -> str:
    if allow_fallback is None:
        allow_fallback = settings.ALLOW_LOCAL_FALLBACK
    model = get_chat_model(temperature=temperature)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    try:
        response = await model.ainvoke(messages)
        return getattr(response, "content", str(response)).strip()
    except Exception as exc:
        if not allow_fallback:
            raise
        logger.warning("LLM invocation failed, using local fallback: %s", exc)
        fallback = await LocalStudyWriter().ainvoke(messages)
        return (
            "【百炼云模型暂不可用，已自动使用本地演示逻辑。"
            "请检查百炼额度、免费额度限制或模型权限。】\n\n"
            + getattr(fallback, "content", str(fallback)).strip()
        )


def get_model_status() -> dict[str, str | bool]:
    return {
        **settings.model_config_summary,
        "runtime": "bailian-compatible" if settings.active_api_key else "local-fallback",
    }
