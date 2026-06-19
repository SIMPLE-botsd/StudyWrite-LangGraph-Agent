from __future__ import annotations

import json
import re

from fastapi import APIRouter, Request

from app.core.llm_factory import invoke_text
from app.models.schemas import (
    ApiResponse,
    AssignmentSuggestion,
    AssignmentSuggestionRequest,
    ImitateWritingRequest,
    PolishWritingRequest,
    StudentWritingRequest,
)
from app.utils.request_utils import handle_workflow_request
from app.utils.workflow_registry import student_writing_workflow

router = APIRouter(tags=["Student Writing Agent"])


@router.post("/student_writer")
async def generate_assignment(payload: StudentWritingRequest, request: Request):
    return await handle_workflow_request(
        feature="generate_assignment",
        payload_dict=payload.dict(),
        http_request=request,
        workflow=student_writing_workflow,
    )


@router.post("/polish_writer")
async def polish_assignment(payload: PolishWritingRequest, request: Request):
    return await handle_workflow_request(
        feature="polish_assignment",
        payload_dict=payload.dict(),
        http_request=request,
        workflow=student_writing_workflow,
    )


@router.post("/imitate_writer")
async def imitate_assignment(payload: ImitateWritingRequest, request: Request):
    return await handle_workflow_request(
        feature="imitate_assignment",
        payload_dict=payload.dict(),
        http_request=request,
        workflow=student_writing_workflow,
    )


@router.post("/assignment_suggestion")
async def assignment_suggestion(payload: AssignmentSuggestionRequest):
    try:
        prompt = (
            "请为一个学生写作智能体生成一组表单参数，严格输出 JSON，不要 Markdown。"
            "JSON 字段必须包含：title, assignment_type, task_description, materials, style, "
            "word_count, academic_level, rubric_focus, content, reference_text。\n\n"
            f"当前模式：{payload.mode}\n"
            f"当前题目：{payload.current_title or '请你自主拟定一个适合课程大作业展示的题目'}\n"
            f"当前任务类型：{payload.assignment_type}\n\n"
            "要求：题目适合大学课程作业；作业要求具体；评分关注点可用于指导生成；"
            "如果模式是 polish，请 content 给一段可润色原文；如果模式是 imitate，请 reference_text 给一段可仿写范文。"
        )
        raw = await invoke_text(
            "你是课程作业写作智能体的表单规划助手。必须只返回合法 JSON，不要解释，不要 Markdown 代码块。",
            prompt,
            temperature=0.45,
        )
        data = _parse_suggestion_json(raw, payload)
    except Exception as exc:
        data = _default_suggestion(payload)
        data["rubric_focus"] = data["rubric_focus"] + f"（智能填入已使用兜底模板：{type(exc).__name__}）"
    try:
        suggestion = AssignmentSuggestion(**_normalize_suggestion(data, payload))
    except Exception as exc:
        data = _default_suggestion(payload)
        data["rubric_focus"] = data["rubric_focus"] + f"（智能填入已使用兜底模板：{type(exc).__name__}）"
        suggestion = AssignmentSuggestion(**data)
    return ApiResponse(message="assignment suggestion", data=suggestion.model_dump())


def _parse_suggestion_json(raw: str, payload: AssignmentSuggestionRequest) -> dict:
    defaults = _default_suggestion(payload)
    try:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        candidate = match.group(0) if match else raw
        candidate = candidate.strip().strip("`")
        data = json.loads(candidate)
    except Exception:
        data = {}
    defaults.update({key: value for key, value in data.items() if value is not None and str(value).strip()})
    return defaults


def _normalize_suggestion(data: dict, payload: AssignmentSuggestionRequest) -> dict:
    defaults = _default_suggestion(payload)
    normalized = dict(defaults)
    for key in defaults:
        value = data.get(key, defaults[key])
        normalized[key] = _stringify_suggestion_value(value)
    return normalized


def _stringify_suggestion_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(f"- {_stringify_suggestion_value(item)}" for item in value if item is not None).strip()
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            item_text = _stringify_suggestion_value(item)
            if item_text:
                lines.append(f"{key}: {item_text}")
        return "\n".join(lines).strip()
    return str(value).strip()


def _default_suggestion(payload: AssignmentSuggestionRequest) -> dict:
    if payload.mode == "polish":
        return {
            "title": payload.current_title or "课程作业表达润色",
            "assignment_type": "润色修改",
            "task_description": "在不改变原意的基础上，增强段落逻辑、学术表达和过渡衔接。",
            "materials": "",
            "style": "自然、严谨、学生化",
            "word_count": "800",
            "academic_level": "本科课程作业",
            "rubric_focus": "保留原意，逻辑更清楚，表达更正式，避免空泛套话。",
            "content": "人工智能现在很流行，很多同学都会用它写作业。它有好处也有坏处，所以我们要正确看待。",
            "reference_text": "",
        }
    if payload.mode == "imitate":
        return {
            "title": payload.current_title or "深度学习习惯的培养",
            "assignment_type": "仿写练习",
            "task_description": "仿照参考文本的论述结构，围绕大学生深度学习习惯展开一篇短文。",
            "materials": "",
            "style": "结构清晰、表达自然、学生化",
            "word_count": "1000",
            "academic_level": "本科课程作业",
            "rubric_focus": "只迁移结构和节奏，不复制原句；主题明确，有个人理解。",
            "content": "",
            "reference_text": "学习并不是简单地接收结论，而是在不断提问、验证和修正中形成自己的理解。真正有效的学习，需要把外部信息转化为个人能够解释、使用和反思的知识。",
        }
    defaults = {
        "title": payload.current_title or "人工智能对大学学习方式的影响",
        "assignment_type": payload.assignment_type or "课程论文",
        "task_description": "结合课堂讨论和个人学习体验，分析生成式人工智能对大学生学习方式的影响，并提出合理使用建议。",
        "materials": "课堂提到：AI 可以提升资料检索和初稿生成效率，但也可能造成依赖、误判资料可信度、削弱原创思考。",
        "style": "清晰、正式、学生化",
        "word_count": "1200",
        "academic_level": "本科课程作业",
        "rubric_focus": "观点明确，论证有材料支撑，体现个人反思，避免直接照搬 AI 输出。",
        "content": "人工智能现在很流行，很多同学都会用它写作业。它有好处也有坏处，所以我们要正确看待。",
        "reference_text": "学习并不是简单地接收结论，而是在不断提问、验证和修正中形成自己的理解。",
    }
    return defaults
