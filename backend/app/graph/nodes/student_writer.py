from __future__ import annotations

import json
import re
from statistics import mean

from app.core.config import settings
from app.core.llm_factory import invoke_text
from app.graph.states import StudentWritingState
from app.graph.utils.citations import render_final_article
from app.memory import get_memory_service
from app.services.knowledge_service import knowledge_service
from app.services.writing_knowledge import format_guide, get_assignment_guide


def _inputs(state: StudentWritingState) -> dict:
    return state.get("inputs", {})


def _clean(text: str, limit: int = 1200) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit] + ("..." if len(text) > limit else "")


def _query_from_inputs(inputs: dict) -> str:
    keys = ["title", "assignment_type", "task_description", "materials", "content", "change_request"]
    return "\n".join(str(inputs.get(key, "")).strip() for key in keys if str(inputs.get(key, "")).strip())


def _display_query_from_inputs(inputs: dict, rag_chunks: list[dict] | None = None) -> str:
    # 会话历史展示依赖这份结构化文本；不要只保存检索 query，否则刷新后会丢失功能、字数和知识库标签。
    feature = inputs.get("feature", "generate_assignment")
    is_polish = feature == "polish_assignment"
    lines = [
        f"功能：{'文章润色' if is_polish else '生成文章'}",
        f"标题：{inputs.get('title', '未命名写作任务')}",
        f"类型：{inputs.get('assignment_type', '润色修改' if is_polish else '课程论文')}",
    ]
    word_count = str(inputs.get("word_count", "")).strip()
    if word_count:
        lines.append(f"字数：{word_count}")
    lines.extend(
        [
            f"深度打磨：{'开启' if inputs.get('deep_polish') else '关闭'}",
            f"要求：{inputs.get('change_request') or inputs.get('task_description') or '根据输入完成写作。'}",
        ]
    )
    if is_polish:
        lines.append(f"原文：{inputs.get('content', '')}")
    else:
        lines.append(f"内容/资料：{inputs.get('materials', '')}")
    knowledge_label = _knowledge_label_from_inputs(inputs, rag_chunks or [])
    if knowledge_label:
        lines.append(f"知识库：{knowledge_label}")
    return "\n".join(lines)


def _knowledge_label_from_inputs(inputs: dict, rag_chunks: list[dict]) -> str:
    if not inputs.get("use_rag"):
        return ""
    names = [
        str(name).strip()
        for name in inputs.get("rag_dataset_names", [])
        if str(name).strip()
    ]
    if not names:
        seen = set()
        for chunk in rag_chunks:
            name = str(chunk.get("document_name") or chunk.get("filename") or "").strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    if names:
        return "、".join(names[:3]) + (" 等" if len(names) > 3 else "")
    return "已启用知识库"


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
            rag_result = await knowledge_service.retrieve(
                query,
                inputs.get("rag_dataset_ids", []),
                top_k=int(inputs.get("rag_top_k", settings.RAGFLOW_DEFAULT_TOP_K)),
            )
            rag_chunks = rag_result.get("chunks", [])
            rag_context = knowledge_service.format_chunks(rag_chunks)
            if rag_context:
                # 把切片编号和标注规则一起交给模型，后续 render 节点会再兜底补齐缺失脚注。
                citation_guide = (
                    "引用规则：检索结果按 1、2、3 编号。正文中如果使用了某条切片的信息，"
                    "请在对应句子或段落末尾标注 [^编号]，不要在文末单独堆砌引用列表。"
                )
                guide = f"{guide}\n\n{citation_guide}\n\n{rag_context}"
            else:
                guide = f"{guide}\n\n{knowledge_service.empty_message()}"
        except Exception as exc:
            guide = f"{guide}\n\n{knowledge_service.error_message(exc)}"
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
    final = render_final_article(title, state.get("draft", ""), state.get("rag_chunks", []))
    return {"final_output": final}


async def save_memory_node(state: StudentWritingState) -> dict:
    inputs = _inputs(state)
    service = get_memory_service()
    final_output = state.get("final_output", "") or state.get("draft", "")
    draft_output = state.get("draft", "") or final_output
    query = _display_query_from_inputs(inputs, state.get("rag_chunks", []))
    saved: list[str] = []
    if inputs.get("use_memory", True):
        # 先写长期记忆，再保存会话轮次，这样节点记录里能展示真实的记忆写入结果。
        saved = await service.save_learning_memories(
            user_id=inputs.get("user_id", "student-demo"),
            session_id=inputs.get("session_id", "demo-session"),
            inputs=inputs,
            final_output=draft_output,
        )
        memory_writeback = f"会话历史已保存，已写入 {len(saved)} 条长期记忆。"
    else:
        memory_writeback = "会话历史已保存，本次未写入长期记忆。"

    state_for_records = dict(state)
    state_for_records["memory_writeback"] = memory_writeback
    await service.save_turn(
        session_id=inputs.get("session_id", "demo-session"),
        user_id=inputs.get("user_id", "student-demo"),
        feature=inputs.get("feature", "generate_assignment"),
        title=inputs.get("title", "未命名写作任务"),
        query=query,
        answer=final_output,
        nodes=_build_node_records(state_for_records),
        metadata={"scores": state.get("critique_scores", {})},
    )
    return {"memory_writeback": memory_writeback, "saved_memories": saved}


def _build_node_records(state: StudentWritingState) -> list[dict]:
    # 历史会话回放依赖这份节点快照，避免刷新后只剩最终文章，看不出 Agent 的执行过程。
    inputs = _inputs(state)
    details = _node_detail_map(state)
    records = [
        ("recall_memory", "读取记忆", "已读取短期与长期记忆"),
        ("analyze_assignment", "理解要求", "已拆解写作目标、材料要求和评分风险"),
        (
            "retrieve_knowledge",
            "匹配知识",
            f"已匹配 {len(state.get('rag_chunks', []))} 条知识库片段"
            if inputs.get("use_rag")
            else "已准备本地写作知识",
        ),
        ("plan_outline", "规划提纲", "文章结构与段落安排已完成"),
        ("write_draft", "生成正文", "完整正文已生成"),
    ]
    if inputs.get("deep_polish"):
        records.extend(
            [
                ("evaluate_draft", "质量评估", "已完成结构、契合度和表达质量检查"),
                ("revise_draft", "深度修订", "已根据评估意见完成修订"),
            ]
        )
    records.extend(
        [
            ("render", "整理结果", "最终 Markdown 已整理完成"),
            ("save_memory", "写入记忆", "会话与写作偏好已保存"),
        ]
    )
    return [
        {
            "id": node_id,
            "node": node_id,
            "name": name,
            "state": "done",
            "text": text,
            "detail": details.get(node_id, ""),
        }
        for node_id, name, text in records
    ]


def _node_detail_map(state: StudentWritingState) -> dict[str, str]:
    # 节点详情展示“传给下一步的真实内容”，而不是空泛说明，方便演示时展开检查每一步。
    rag_chunks = state.get("rag_chunks", [])
    return {
        "recall_memory": state.get("memory_context", "") or "暂无可召回记忆，该节点向下游传递空记忆上下文。",
        "analyze_assignment": state.get("brief", "") or "该节点未返回任务分析内容。",
        "retrieve_knowledge": _knowledge_detail(state.get("knowledge_context", ""), rag_chunks),
        "plan_outline": state.get("outline", "") or "该节点未返回提纲内容。",
        "write_draft": state.get("draft", "") or "该节点未返回正文内容。",
        "evaluate_draft": state.get("critique", "") or "该节点未返回质量评估内容。",
        "revise_draft": state.get("draft", "") or "该节点未返回修订稿内容。",
        "render": state.get("final_output", "") or "该节点未返回最终 Markdown。",
        "save_memory": state.get("memory_writeback", "") or "该节点未返回记忆写入结果。",
    }


def _knowledge_detail(knowledge_context: str, rag_chunks: list[dict]) -> str:
    # 知识匹配节点同时展示写作指导和实际命中的文件片段，避免只看到“本地知识库”这类泛化文本。
    parts = [knowledge_context or "该节点未返回知识上下文。"]
    if rag_chunks:
        parts.append("\n【检索片段】")
        for index, chunk in enumerate(rag_chunks, start=1):
            source = chunk.get("document_name") or chunk.get("dataset_name") or "知识库片段"
            content = " ".join(str(chunk.get("content", "")).split())
            parts.append(f"{index}. {source}\n{content}")
    return "\n".join(parts)


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
        f"{'可使用的材料包括：' + materials if materials else '本文将结合课程常见讨论与学习场景展开分析。'}\n\n"
        "三、个人思考\n"
        "作为课程作业，文章不只要复述资料，还需要体现学生自己的理解。\n\n"
        "四、结论\n"
        "最终稿应回到中心论点，形成清晰、完整、可直接阅读的结论。"
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


async def _llm_write(state: StudentWritingState) -> str:
    inputs = _inputs(state)
    feature = inputs.get("feature", "generate_assignment")
    if feature == "polish_assignment":
        task_prompt = (
            f"原文：\n{inputs.get('content', '')}\n\n"
            f"润色要求：{inputs.get('change_request', '')}\n"
            "请保留原意，直接输出润色后的完整正文，不要输出修改说明、待补充项或写作建议。"
        )
    else:
        task_prompt = (
            "请直接生成一篇完整课程作业正文。"
            "不要输出修改提示、参考文献占位、待补充清单、写作说明或‘请填入’内容。"
            "如果缺少用户真实经历，请用自然的学生化概括表达完成论证，不要留下占位符。"
            "如果使用了知识库检索结果，请在对应句子或段落末尾使用 [^编号] 标注来源。"
        )

    system = (
        "你是一个帮助学生完成课程写作训练的中文智能体。"
        "要求：输出完整正文；不编造具体文献；不输出占位符、修改提示、参考文献占位或待补充清单。"
        "文章应像学生本人可以继续提交前微调的完整稿，而不是半成品。"
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
