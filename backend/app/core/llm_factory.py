from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import settings

logger = logging.getLogger(__name__)

_last_invocation_status: dict[str, str | bool] = {
    "used_llm": False,
    "used_fallback": False,
    "last_error": "",
    "last_model": settings.MODEL_NAME,
    "last_provider": settings.LLM_PROVIDER,
}


class LocalDeepPenWriter:
    """本地兜底模型：外部 LLM 不可用时仍能完整演示工作流。"""

    async def ainvoke(self, messages):
        system_text = getattr(messages[0], "content", "") if messages else ""
        user_text = getattr(messages[-1], "content", "") if messages else ""
        return type("LocalMessage", (), {"content": self._respond(system_text, user_text)})()

    def _respond(self, system_prompt: str, user_prompt: str) -> str:
        system_prompt = system_prompt.strip()
        user_prompt = user_prompt.strip()
        title = self._extract_field(user_prompt, "标题") or "课程写作练习"

        if "表单规划助手" in system_prompt or "严格输出 JSON" in system_prompt:
            return json.dumps(
                {
                    "title": "生成式人工智能辅助学习的边界与方法",
                    "assignment_type": "课程论文",
                    "task_description": "结合课程讨论和个人学习经验，分析生成式人工智能在资料检索、观点形成和作业写作中的作用，并提出合理使用建议。",
                    "materials": "课堂讨论指出：AI 可以提升检索和写作效率，但也可能带来资料误判、表达同质化和原创性风险。学生需要保留人工判断、核查来源，并记录自己的修改过程。",
                    "style": "清晰、正式、学生化",
                    "word_count": "1200",
                    "academic_level": "本科课程作业",
                    "rubric_focus": "观点明确，结构完整，材料支撑充分，体现个人反思，避免直接照搬 AI 输出。",
                    "content": "现在很多同学会使用生成式人工智能辅助学习。它确实能提高效率，但如果完全依赖，也会让我们忽视资料判断和独立思考。",
                },
                ensure_ascii=False,
            )

        if "质量评估节点" in system_prompt or "\"scores\"" in user_prompt:
            return json.dumps(
                {
                    "scores": {
                        "structure": 8.0,
                        "task_fit": 8.0,
                        "evidence": 7.6,
                        "academic_tone": 7.8,
                        "originality": 7.5,
                    },
                    "critique": "文章结构基本完整，能够围绕题目展开。建议进一步强化段落之间的逻辑衔接和个人分析。",
                },
                ensure_ascii=False,
            )

        if "任务分析节点" in system_prompt:
            return (
                "写作目标：围绕题目形成一篇结构完整、观点明确的课程作业。\n"
                "核心问题：说明主题的现实意义、主要影响和合理建议。\n"
                "材料使用：优先结合课堂讨论、个人学习经历和真实案例。\n"
                "评分风险：避免空泛套话、资料来源不清和 AI 痕迹过重。\n"
                "建议策略：采用“背景说明 - 多角度分析 - 个人反思 - 建议总结”的结构。"
            )

        if "提纲规划节点" in system_prompt:
            return (
                f"# 《{title}》写作提纲\n\n"
                "1. 引言：说明选题背景和讨论价值。\n"
                "2. 主体一：分析现象或问题的主要表现。\n"
                "3. 主体二：结合材料说明影响、原因或机制。\n"
                "4. 主体三：提出个人反思和改进建议。\n"
                "5. 结论：总结观点，回到中心论点。"
            )

        if "修订节点" in system_prompt:
            return (
                f"# {title}\n\n"
                "## 修订稿\n\n"
                "本文在原有基础上进一步强化了结构层次和材料支撑。文章先说明问题背景，再结合课程材料展开分析，最后回到个人学习经验提出建议。\n\n"
                "在写作过程中，需要把观点、材料和分析放在同一段落中，避免只罗列结论，并通过清晰的过渡保持文章整体连贯。"
            )

        return (
            f"# {title}\n\n"
            "## 引言\n\n"
            "随着相关技术和学习方式的变化，学生在完成课程任务时不仅需要关注效率，也需要保持独立判断和规范表达。本文围绕题目要求，结合课堂讨论和个人学习经验展开分析。\n\n"
            "## 主要分析\n\n"
            "首先，技术工具可以帮助学生更快地整理资料、形成初步框架，并发现自己原本忽略的问题。但如果只依赖工具给出的结论，学生容易忽视资料可信度、论证过程和个人理解。\n\n"
            "其次，课程作业的价值不只在于完成文本，更在于训练问题意识、材料整合和逻辑表达。因此，写作时应把工具输出作为参考材料，而不是直接替代自己的思考。\n\n"
            "## 个人反思\n\n"
            "在实际学习中，我认为合理的做法是先独立理解题目，再使用工具辅助检索和梳理，最后由自己完成判断、修改和引用核查。这样既能提升效率，也能保留学习过程中的主动性。\n\n"
            "## 结论\n\n"
            "总体来看，工具可以成为课程学习的辅助力量，但不能替代学生的分析能力和学术规范意识。只有把效率提升与独立判断结合起来，学生才能真正把技术转化为稳定的学习能力。"
        )

    def _extract_field(self, text: str, field: str) -> str:
        match = re.search(rf"{field}[：:]\s*(.+)", text)
        if not match and field == "标题":
            match = re.search(r"题目[：:]\s*(.+)", text)
        if not match:
            return ""
        return match.group(1).splitlines()[0].strip()


def get_chat_model(temperature: float = 0.2):
    provider = settings.LLM_PROVIDER.lower()
    api_key = settings.active_api_key
    base_url = settings.active_base_url

    if provider in {"bailian", "dashscope", "model_studio", "openai"} and api_key:
        try:
            from langchain_openai import ChatOpenAI

            # 百炼云使用 OpenAI 兼容接口，因此同一套 ChatOpenAI 封装可以切换不同模型。
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
            _last_invocation_status.update(
                {
                    "used_llm": False,
                    "used_fallback": True,
                    "last_error": f"模型初始化失败：{exc}",
                    "last_model": settings.MODEL_NAME,
                    "last_provider": settings.LLM_PROVIDER,
                }
            )
            return LocalDeepPenWriter()
    return LocalDeepPenWriter()


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
    # 所有节点都通过统一入口调用模型，方便记录“是否真的调用 LLM”和最后一次错误。
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    try:
        response = await model.ainvoke(messages)
        used_fallback = isinstance(model, LocalDeepPenWriter)
        _last_invocation_status.update(
            {
                "used_llm": not used_fallback,
                "used_fallback": used_fallback,
                "last_error": "",
                "last_model": settings.MODEL_NAME,
                "last_provider": settings.LLM_PROVIDER,
            }
        )
        return getattr(response, "content", str(response)).strip()
    except Exception as exc:
        if not allow_fallback:
            # 关闭兜底时把异常抛给上层，适合调试百炼云 Key、模型权限和网络问题。
            _last_invocation_status.update(
                {
                    "used_llm": False,
                    "used_fallback": False,
                    "last_error": str(exc),
                    "last_model": settings.MODEL_NAME,
                    "last_provider": settings.LLM_PROVIDER,
                }
            )
            raise
        logger.warning("LLM invocation failed, using local fallback: %s", exc)
        fallback = await LocalDeepPenWriter().ainvoke(messages)
        _last_invocation_status.update(
            {
                "used_llm": False,
                "used_fallback": True,
                "last_error": str(exc),
                "last_model": settings.MODEL_NAME,
                "last_provider": settings.LLM_PROVIDER,
            }
        )
        return (
            "【百炼云模型暂不可用，已自动使用本地演示逻辑。"
            "请检查百炼额度、免费额度限制或模型权限。】\n\n"
            + getattr(fallback, "content", str(fallback)).strip()
        )


def get_model_status() -> dict[str, str | bool]:
    runtime = "openai-compatible" if settings.active_api_key else "local-fallback"
    if settings.LLM_PROVIDER:
        runtime = f"{settings.LLM_PROVIDER}-compatible" if settings.active_api_key else "local-fallback"
    return {
        **settings.model_config_summary,
        "runtime": runtime,
        **_last_invocation_status,
    }
