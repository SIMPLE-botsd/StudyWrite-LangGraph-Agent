from __future__ import annotations

import re


def render_final_article(title: str, draft: str, rag_chunks: list[dict]) -> str:
    # 最终出口统一处理正文清理、内联引用、编号重排和脚注元数据，避免各节点各自拼接导致格式漂移。
    clean_draft = finalize_full_article(draft)
    citations = build_citation_items(rag_chunks)
    if citations:
        clean_draft = attach_inline_citations(clean_draft, citations)
        clean_draft, citations = renumber_citations_by_appearance(clean_draft, citations)

    final = f"# {title}\n\n{clean_draft}"
    citation_meta = format_citation_metadata(citations)
    if citation_meta:
        final = f"{final}\n\n{citation_meta}"
    return final


def finalize_full_article(text: str) -> str:
    # 模型只负责写正文，但仍可能带出“待补充/修改提示”等训练痕迹，落库和展示前需要收口成完整稿。
    clean = (text or "").strip()
    if not clean:
        return clean
    clean = re.sub(r"\n?#{1,6}\s*(?:📝\s*)?(?:定稿)?修改提示[\s\S]*$", "", clean, flags=re.I)
    clean = re.sub(r"\n?#{1,6}\s*(?:📚\s*)?参考文献[\s\S]*$", "", clean, flags=re.I)
    clean = re.sub(r"\n?#{1,6}\s*(?:修改说明|给同学的修改提示|待确认素材|素材补充建议)[\s\S]*$", "", clean, flags=re.I)
    clean = re.sub(r"\n?[-*]*\s*(?:📝\s*)?(?:定稿)?修改提示[:：][\s\S]*$", "", clean, flags=re.I)
    clean = re.sub(r"\n?[-*]*\s*(?:📚\s*)?参考文献(?:（[^）]*）)?[:：][\s\S]*$", "", clean, flags=re.I)
    clean = re.sub(r"[\[【（(]\s*(?:请|可|建议|此处|这里|待)\s*(?:填入|补充|替换|加入|搜索)[^\]】）)]*[\]】）)]", "", clean)
    clean = re.sub(r"\*?\s*此处可补充[^。；;\n]*(?:。)?", "", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()


def build_citation_items(chunks: list[dict]) -> list[dict]:
    # 检索服务返回的字段来源不完全一致，这里标准化为前端脚注需要的 source/content/score。
    citations = []
    seen = set()
    for chunk in chunks:
        source = chunk.get("document_name") or chunk.get("filename") or "知识库片段"
        source = str(source).strip() or "知识库片段"
        content = " ".join(str(chunk.get("content", "")).split())
        if not content:
            continue
        raw = chunk.get("raw") if isinstance(chunk.get("raw"), dict) else {}
        chunk_key = raw.get("chunk_id") or chunk.get("chunk_id") or f"{source}:{content[:120]}"
        if chunk_key in seen:
            continue
        seen.add(chunk_key)
        score = chunk.get("score")
        citations.append(
            {
                "id": len(citations) + 1,
                "source": source,
                "content": content[:420] + ("..." if len(content) > 420 else ""),
                "score": round(float(score), 3) if isinstance(score, (int, float)) else None,
            }
        )
    return citations


def attach_inline_citations(text: str, citations: list[dict]) -> str:
    if not text or not citations:
        return text
    if re.search(r"\[\^\d+\]", text):
        return text

    # 如果 LLM 没主动打脚注，就按段落和检索片段的词项重叠补标，保证 RAG 结果能被看见。
    lines = text.splitlines()
    used_counts: dict[int, int] = {int(item["id"]): 0 for item in citations}
    in_code = False
    in_notes = False

    for line_index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not stripped:
            continue
        if re.search(r"(定稿修改提示|修改提示|参考文献|知识库引用)", stripped):
            in_notes = True
        if in_notes:
            continue
        if is_citation_target(stripped):
            citation_id = best_citation_id(stripped, citations, used_counts)
            marker = f"[^{citation_id}]"
            if marker not in line:
                lines[line_index] = line.rstrip() + marker
            used_counts[citation_id] = used_counts.get(citation_id, 0) + 1

    return "\n".join(lines)


def renumber_citations_by_appearance(text: str, citations: list[dict]) -> tuple[str, list[dict]]:
    if not text or not citations:
        return text, citations

    # 用户只关心正文里的第 1、2、3 个引用，不需要看到检索返回时的原始片段顺序。
    by_old_id = {int(item["id"]): item for item in citations}
    ordered_items: list[dict] = []
    old_to_new: dict[int, int] = {}

    def replace_marker(match: re.Match) -> str:
        old_id = int(match.group(1))
        if old_id not in by_old_id:
            return match.group(0)
        if old_id not in old_to_new:
            new_id = len(old_to_new) + 1
            old_to_new[old_id] = new_id
            item = dict(by_old_id[old_id])
            item["id"] = new_id
            ordered_items.append(item)
        return f"[^{old_to_new[old_id]}]"

    renumbered_text = re.sub(r"\[\^(\d+)\]", replace_marker, text)
    return renumbered_text, ordered_items


def best_citation_id(paragraph: str, citations: list[dict], used_counts: dict[int, int]) -> int:
    # 选择引用时综合段落词项重叠、检索相关度和重复使用惩罚，让脚注尽量贴近当前段落。
    paragraph_terms = citation_terms(paragraph)
    best_id = int(citations[0]["id"])
    best_score = -1.0
    for item in citations:
        citation_id = int(item["id"])
        content_terms = citation_terms(str(item.get("content", "")))
        overlap = len(paragraph_terms & content_terms)
        base = overlap / max(len(paragraph_terms), 1)
        retrieval_score = float(item.get("score") or 0) * 0.03
        reuse_penalty = used_counts.get(citation_id, 0) * 0.08
        score = base + retrieval_score - reuse_penalty
        if score > best_score:
            best_score = score
            best_id = citation_id
    return best_id


def citation_terms(text: str) -> set[str]:
    # 中文按二字滑窗、英文按词抽取，给轻量相似度匹配一个不依赖额外模型的兜底方案。
    clean = (text or "").lower()
    terms = set(re.findall(r"[a-z][a-z0-9_-]{2,}", clean))
    for segment in re.findall(r"[\u4e00-\u9fff]+", clean):
        if len(segment) == 1:
            terms.add(segment)
            continue
        for index in range(len(segment) - 1):
            terms.add(segment[index : index + 2])
    return terms


def is_citation_target(line: str) -> bool:
    # 只给有完整论述意义的正文段落补引用，标题、列表、表格和短句不强行加脚注。
    if len(line) < 58:
        return False
    if line.startswith(("#", ">", "- ", "* ", "|", "【")):
        return False
    if re.match(r"^\d+[.、]\s*", line):
        return False
    if re.match(r"^[一二三四五六七八九十]+[、.．]\s*", line) and len(line) < 80:
        return False
    if re.search(r"\[\^\d+\]", line):
        return False
    return True


def format_citation_metadata(citations: list[dict]) -> str:
    if not citations:
        return ""
    # 使用标准 Markdown 脚注格式存储，前端预览、历史回放和纯文本复制都可以复用同一份结果。
    lines = []
    for item in citations:
        score = item.get("score")
        score_text = f" · 相关度 {score:.3f}" if isinstance(score, (int, float)) else ""
        source = str(item.get("source") or "知识库片段").replace("\n", " ").strip()
        content = str(item.get("content") or "").replace("\n", " ").strip()
        lines.append(f"[^{item['id']}]: {source}{score_text}")
        lines.append(f"    {content}")
    return "\n".join(lines)
