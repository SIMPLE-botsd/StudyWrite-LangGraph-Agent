from __future__ import annotations

import json
import re
from statistics import mean

from app.core.config import settings
from app.core.llm_factory import invoke_text
from app.graph.states import StudentWritingState
from app.memory import get_memory_service
from app.services.ragflow_service import format_rag_chunks, ragflow_service
from app.services.writing_knowledge import format_guide, get_assignment_guide


def _inputs(state: StudentWritingState) -> dict:
    return state.get("inputs", {})


def _clean(text: str, limit: int = 1200) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit] + ("..." if len(text) > limit else "")


def _query_from_inputs(inputs: dict) -> str:
    keys = ["title", "assignment_type", "task_description", "materials", "content", "change_request", "reference_text"]
    return "\n".join(str(inputs.get(key, "")).strip() for key in keys if str(inputs.get(key, "")).strip())


async def recall_memory_node(state: StudentWritingState) -> dict:
    inputs = _inputs(state)
    if not inputs.get("use_memory", True):
        return {"memory_context": "本次请求未启用记忆。", "recalled_memories": []}

    service = get_memory_service()
    context = await service.load_context(
        session_id=inputs.get("session_id", "demo-session"),
        user_id=inputs.get("user_id", "student-demo"),
        query=_query_from_inputs(inputs),
        memory_k=int(inputs.get("memory_k", settings.MEMORY_TOP_K)),
        use_memory=True,
    )
    formatted = service.format_context_for_agent(context)
    recalled = [memory.content for memory in context.long_term_memories]
    if not formatted:
        formatted = "暂无可召回的历史记忆，将根据当前输入完成写作。"
    return {"memory_context": formatted, "recalled_memories": recalled}


async def analyze_assignment_node(state: StudentWritingState) -> dict:
    inputs = _inputs(state)
    feature = inputs.get("feature", "generate_assignment")
    title = inputs.get("title", "未命名写作任务")
    assignment_type = inputs.get("assignment_type", "课程论文")
    task = inputs.get("task_description") or inputs.get("change_request") or "根据输入完成写作。"
    memory_context = state.get("memory_context", "")

    base_brief = (
        f"任务类型：{assignment_type}\n"
        f"标题：{title}\n"
        f"工作流模式：{feature}\n"
        f"写作要求：{_clean(task, 600)}\n"
        f"目标风格：{inputs.get('style', '清晰、正式、学生化')}\n"
        f"字数要求：{inputs.get('word_count', '按任务需要')}\n"
        f"记忆状态：{'已召回历史上下文' if memory_context and '暂无' not in memory_context else '无历史上下文'}"
    )
    if inputs.get("use_llm"):
        brief = await invoke_text(
            "你是课程作业写作智能体的任务分析节点。请准确拆解题目，不要直接写正文。",
            (
                "请把下面写作任务拆解为：写作目标、核心问题、必须使用的材料、评分风险、建议策略。\n\n"
                f"{base_brief}\n\n长期/短期记忆：\n{memory_context}"
            ),
            temperature=0.1,
        )
    else:
        brief = base_brief
    return {"brief": brief}


async def retrieve_knowledge_node(state: StudentWritingState) -> dict:
    inputs = _inputs(state)
    assignment_type = inputs.get("assignment_type", "课程论文")
    rubric_focus = inputs.get("rubric_focus", "")
    guide = format_guide(assignment_type, rubric_focus)
    materials = _clean(inputs.get("materials", ""), 900)
    if materials:
        guide = f"{guide}\n\n用户材料摘要：{materials}"
    rag_chunks = []
    if inputs.get("use_rag"):
        query = inputs.get("rag_query") or _query_from_inputs(inputs)
        try:
            rag_result = await ragflow_service.retrieve(
                query,
                inputs.get("rag_dataset_ids", []),
                top_k=int(inputs.get("rag_top_k", settings.RAGFLOW_DEFAULT_TOP_K)),
            )
            rag_chunks = rag_result.get("chunks", [])
            rag_context = format_rag_chunks(rag_chunks)
            if rag_context:
                guide = f"{guide}\n\n{rag_context}"
            else:
                guide = f"{guide}\n\nRAGFlow 知识库未检索到可用片段，请优先使用用户材料和本地写作指南。"
        except Exception as exc:
            guide = f"{guide}\n\nRAGFlow 检索暂不可用：{exc}"
    return {"knowledge_context": guide, "rag_chunks": rag_chunks}


async def plan_outline_node(state: StudentWritingState) -> dict:
    inputs = _inputs(state)
    assignment_type = inputs.get("assignment_type", "课程论文")
    guide = get_assignment_guide(assignment_type)
    sections = guide["structure"]
    title = inputs.get("title", "未命名写作任务")

    if inputs.get("use_llm"):
        outline = await invoke_text(
            "你是课程作业提纲规划节点。请输出结构化提纲，每一级都说明该写什么。",
            (
                f"任务分析：\n{state.get('brief', '')}\n\n"
                f"写作知识：\n{state.get('knowledge_context', '')}\n\n"
                "请生成适合作业提交的提纲，包含标题、段落安排、每段论点、材料使用建议。"
            ),
            temperature=0.2,
        )
        return {"outline": outline}

    outline_lines = [f"《{title}》写作提纲"]
    for idx, section in enumerate(sections, start=1):
        outline_lines.append(f"{idx}. {section}：围绕题目要求展开，保留可替换的课程材料或案例。")
    outline_lines.append("检查点：每个主体段落都包含观点、证据、分析和过渡。")
    return {"outline": "\n".join(outline_lines)}


async def write_draft_node(state: StudentWritingState) -> dict:
    inputs = _inputs(state)
    if inputs.get("use_llm"):
        return {"draft": await _llm_write(state)}

    feature = inputs.get("feature", "generate_assignment")
    if feature == "polish_assignment":
        draft = _polish_text(inputs)
    elif feature == "imitate_assignment":
        draft = _imitate_text(inputs)
    else:
        draft = _generate_text(inputs, state)
    return {"draft": draft, "revision_count": state.get("revision_count", 0)}


async def evaluate_draft_node(state: StudentWritingState) -> dict:
    draft = state.get("draft", "") or ""
    inputs = _inputs(state)
    if inputs.get("use_llm"):
        return await _llm_evaluate(state)

    scores = _score_draft(draft, inputs)
    avg = mean(scores.values()) if scores else 0
    issues = []
    if scores["structure"] < 7.2:
        issues.append("结构层级还不够清楚，需要增强标题、段落或过渡。")
    if scores["task_fit"] < 7.2:
        issues.append("与题目要求的对应关系还可以再明确。")
    if scores["evidence"] < 7.2:
        issues.append("材料支撑偏弱，建议补入课程概念、数据或具体案例。")
    if scores["academic_tone"] < 7.2:
        issues.append("表达需要更像课程作业，减少口号式或随意表述。")
    if scores["originality"] < 7.2:
        issues.append("需要加入个人分析，降低模板感。")
    if not issues:
        issues.append("质量达到当前阈值，可以进入最终整理。")

    critique = (
        f"平均分：{avg:.1f}/10\n"
        + "\n".join(f"- {name}: {score:.1f}" for name, score in scores.items())
        + "\n\n修改建议：\n"
        + "\n".join(f"- {issue}" for issue in issues)
    )
    return {"critique": critique, "critique_scores": scores, "prev_scores": state.get("critique_scores", {})}


async def revise_draft_node(state: StudentWritingState) -> dict:
    draft = state.get("draft", "") or ""
    inputs = _inputs(state)
    revision_count = int(state.get("revision_count", 0)) + 1
    if inputs.get("use_llm"):
        revised = await invoke_text(
            "你是课程作业修订节点。请根据质量评估改写正文，保持学生本人可理解、可继续编辑。",
            (
                f"原稿：\n{draft}\n\n"
                f"评估意见：\n{state.get('critique', '')}\n\n"
                "请输出修订后的完整正文，不要只列建议。"
            ),
            temperature=0.25,
        )
        return {"draft": revised, "revision_count": revision_count}

    addition = (
        "\n\n【修订补强】\n"
        f"结合评分关注点“{inputs.get('rubric_focus', '结构完整、论证清楚')}”，本文需要把观点和材料进一步绑定。"
        "建议在主体段落中补入课堂概念、调查数据或读书摘录，并说明这些材料如何支持中心判断。"
    )
    return {"draft": draft + addition, "revision_count": revision_count}


async def render_node(state: StudentWritingState) -> dict:
    inputs = _inputs(state)
    title = inputs.get("title", "未命名写作任务")
    final = (
        f"# {title}\n\n"
        f"## 写作结果\n{state.get('draft', '')}\n\n"
        f"## 质量自检\n{state.get('critique', '')}"
    )
    return {"final_output": final}


async def save_memory_node(state: StudentWritingState) -> dict:
    inputs = _inputs(state)
    if not inputs.get("use_memory", True):
        return {"memory_writeback": "本次未写入长期记忆。", "saved_memories": []}

    service = get_memory_service()
    final_output = state.get("final_output", "") or state.get("draft", "")
    draft_output = state.get("draft", "") or final_output
    query = _query_from_inputs(inputs)
    await service.save_turn(
        session_id=inputs.get("session_id", "demo-session"),
        user_id=inputs.get("user_id", "student-demo"),
        feature=inputs.get("feature", "generate_assignment"),
        title=inputs.get("title", "未命名写作任务"),
        query=query,
        answer=final_output,
        nodes=[],
        metadata={"scores": state.get("critique_scores", {})},
    )
    saved = await service.save_learning_memories(
        user_id=inputs.get("user_id", "student-demo"),
        session_id=inputs.get("session_id", "demo-session"),
        inputs=inputs,
        final_output=draft_output,
    )
    return {"memory_writeback": f"已写入 {len(saved)} 条长期记忆。", "saved_memories": saved}


def _generate_text(inputs: dict, state: StudentWritingState) -> str:
    title = inputs.get("title", "未命名写作任务")
    assignment_type = inputs.get("assignment_type", "课程论文")
    task = _clean(inputs.get("task_description", ""), 900)
    materials = _clean(inputs.get("materials", ""), 900)
    outline = state.get("outline", "")
    memory_hint = "会延续历史偏好的表达方式。" if state.get("recalled_memories") else "本次以当前要求为主。"

    return (
        f"围绕《{title}》这一{assignment_type}任务，本文可以从问题背景、核心分析和学习收获三个层面展开。"
        f"{memory_hint}\n\n"
        "一、问题背景\n"
        f"本次作业要求是：{task or '围绕课程主题形成一篇结构完整的文章'}。"
        "写作时首先需要把题目中的关键词转化为可以分析的问题，而不是直接堆砌结论。\n\n"
        "二、核心分析\n"
        f"根据提纲安排：\n{outline}\n"
        "主体部分应采用“观点 - 材料 - 分析”的段落方式。"
        f"{'可使用的材料包括：' + materials if materials else '后续可补入课堂笔记、案例或数据。'}\n\n"
        "三、个人思考\n"
        "作为课程作业，文章不只要复述资料，还需要体现学生自己的理解。\n\n"
        "四、结论\n"
        "最终稿应补足真实资料来源，并按老师要求统一格式。"
    )


def _polish_text(inputs: dict) -> str:
    content = _clean(inputs.get("content", ""), 3000)
    change_request = inputs.get("change_request", "提升逻辑与表达")
    style = inputs.get("style", "自然、严谨、学生化")
    sentences = [item.strip() for item in re.split(r"[。！？\n]+", content) if item.strip()]
    if not sentences:
        sentences = ["原文内容较少，需要先补充主要观点和材料。"]
    rebuilt = "。".join(sentences)
    return f"【润色目标】{change_request}；目标风格：{style}。\n\n{rebuilt}。\n\n【结构优化】\n上文已保留原意，并调整为更连贯的课程作业语气。"


def _imitate_text(inputs: dict) -> str:
    reference = _clean(inputs.get("reference_text", ""), 1200)
    task = _clean(inputs.get("task_description", ""), 900)
    title = inputs.get("title", "仿写练习")
    sentence_count = max(3, len(re.split(r"[。！？]", reference)) - 1)
    return (
        f"《{title}》\n\n"
        "【范文结构识别】参考文本整体呈现为“提出背景 - 展开分析 - 总结升华”的结构，"
        f"句群数量约为 {sentence_count} 个，适合迁移结构但不应复制原句。\n\n"
        "【仿写初稿】\n"
        f"围绕新任务“{task}”，文章可以先交代问题背景，再说明它与课程学习之间的关系。"
        "主体分析中保留范文由浅入深的推进方式，但替换为自己的事实、课程概念和个人判断。"
    )


async def _llm_write(state: StudentWritingState) -> str:
    inputs = _inputs(state)
    feature = inputs.get("feature", "generate_assignment")
    if feature == "polish_assignment":
        task_prompt = (
            f"原文：\n{inputs.get('content', '')}\n\n"
            f"润色要求：{inputs.get('change_request', '')}\n"
            "请保留原意，输出润色后的完整文本，并在末尾给出简短修改说明。"
        )
    elif feature == "imitate_assignment":
        task_prompt = (
            f"参考范文：\n{inputs.get('reference_text', '')}\n\n"
            f"新任务：{inputs.get('task_description', '')}\n"
            f"仿写程度：{inputs.get('imitation_degree', '')}\n"
            "请只迁移结构和表达节奏，不复制范文原句，输出新文章初稿。"
        )
    else:
        task_prompt = "请生成课程作业可编辑初稿，正文要完整，有段落层次，并提醒学生补充真实来源。"

    system = (
        "你是一个帮助学生完成课程写作训练的中文智能体。"
        "要求：不编造具体文献；可以提示补充真实材料；输出像学生自己能继续修改的初稿。"
    )
    user = (
        f"任务信息：{state.get('brief', '')}\n\n"
        f"参考知识：{state.get('knowledge_context', '')}\n\n"
        f"记忆上下文：{state.get('memory_context', '')}\n\n"
        f"提纲：\n{state.get('outline', '')}\n\n"
        f"{task_prompt}"
    )
    return await invoke_text(system, user, temperature=settings.MODEL_TEMPERATURE)


async def _llm_evaluate(state: StudentWritingState) -> dict:
    inputs = _inputs(state)
    raw = await invoke_text(
        "你是课程作业质量评估节点。请严格按 JSON 输出，不要添加多余文本。",
        (
            "请评估下面初稿，输出 JSON："
            "{\"scores\":{\"structure\":数字,\"task_fit\":数字,\"evidence\":数字,"
            "\"academic_tone\":数字,\"originality\":数字},\"critique\":\"中文评语\"}。"
            "分数范围 0-10。\n\n"
            f"题目：{inputs.get('title', '')}\n"
            f"评分关注：{inputs.get('rubric_focus', '')}\n"
            f"初稿：\n{state.get('draft', '')}"
        ),
        temperature=0.1,
    )
    try:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        data = json.loads(match.group(0) if match else raw)
        scores = {
            key: float(data.get("scores", {}).get(key, 0))
            for key in ["structure", "task_fit", "evidence", "academic_tone", "originality"]
        }
        critique = str(data.get("critique", "")).strip()
    except Exception:
        scores = _score_draft(state.get("draft", "") or "", inputs)
        critique = raw
    formatted = (
        "\n".join(f"- {name}: {score:.1f}" for name, score in scores.items())
        + "\n\n修改建议：\n"
        + critique
    )
    return {"critique": formatted, "critique_scores": scores, "prev_scores": state.get("critique_scores", {})}


def _score_draft(draft: str, inputs: dict) -> dict[str, float]:
    length = len(draft)
    has_sections = draft.count("\n\n") >= 3 or "一、" in draft
    has_material = bool(inputs.get("materials")) or any(word in draft for word in ["材料", "案例", "数据", "课堂", "观察"])
    has_task = bool(inputs.get("title")) and inputs.get("title", "")[:6] in draft
    scores = {
        "structure": 8.0 if has_sections else 6.5,
        "task_fit": 8.2 if has_task else 7.0,
        "evidence": 8.0 if has_material else 6.6,
        "academic_tone": 8.1 if length > 500 else 6.8,
        "originality": 7.8 if "个人" in draft or "自己" in draft else 6.9,
    }
    if length > 1200:
        scores = {key: min(9.0, value + 0.3) for key, value in scores.items()}
    return scores
