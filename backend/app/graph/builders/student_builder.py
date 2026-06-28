from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.builders.base import BaseGraphBuilder
from app.graph.nodes import (
    analyze_assignment_node,
    evaluate_draft_node,
    plan_outline_node,
    recall_memory_node,
    render_node,
    retrieve_knowledge_node,
    revise_draft_node,
    save_memory_node,
    write_draft_node,
)
from app.graph.states import StudentWritingState


def route_after_write(state: StudentWritingState) -> str:
    # “深度打磨”开启时才进入评估和修订，否则直接整理结果，减少普通生成的等待时间。
    return "evaluate_draft" if state.get("inputs", {}).get("deep_polish") else "render"


class StudentWritingGraphBuilder(BaseGraphBuilder):
    def get_node_name_map(self) -> dict[str, str]:
        return {
            "recall_memory": "读取短期与长期记忆",
            "analyze_assignment": "理解作业要求",
            "retrieve_knowledge": "匹配写作知识",
            "plan_outline": "规划文章提纲",
            "write_draft": "生成完整正文",
            "evaluate_draft": "质量评估",
            "revise_draft": "深度修订",
            "render": "整理最终结果",
            "save_memory": "写入长期记忆",
        }

    def get_output_map(self) -> dict[str, str]:
        return {
            "recall_memory": "memory_context",
            "analyze_assignment": "brief",
            "retrieve_knowledge": "knowledge_context",
            "plan_outline": "outline",
            "write_draft": "draft",
            "evaluate_draft": "critique",
            "revise_draft": "draft",
            "render": "final_output",
            "save_memory": "memory_writeback",
        }

    def _build_graph(self, compile_with_checkpointer: bool = True):
        workflow = StateGraph(StudentWritingState)
        # 主链路：记忆召回 -> 任务理解 -> 知识检索 -> 提纲 -> 正文 -> 可选评估修订 -> 渲染 -> 保存。
        workflow.add_node("recall_memory", recall_memory_node)
        workflow.add_node("analyze_assignment", analyze_assignment_node)
        workflow.add_node("retrieve_knowledge", retrieve_knowledge_node)
        workflow.add_node("plan_outline", plan_outline_node)
        workflow.add_node("write_draft", write_draft_node)
        workflow.add_node("evaluate_draft", evaluate_draft_node)
        workflow.add_node("revise_draft", revise_draft_node)
        workflow.add_node("render", render_node)
        workflow.add_node("save_memory", save_memory_node)

        workflow.add_edge(START, "recall_memory")
        workflow.add_edge("recall_memory", "analyze_assignment")
        workflow.add_edge("analyze_assignment", "retrieve_knowledge")
        workflow.add_edge("retrieve_knowledge", "plan_outline")
        workflow.add_edge("plan_outline", "write_draft")
        workflow.add_conditional_edges(
            "write_draft",
            route_after_write,
            {"evaluate_draft": "evaluate_draft", "render": "render"},
        )
        workflow.add_conditional_edges(
            "evaluate_draft",
            lambda _state: "revise_draft",
            {"revise_draft": "revise_draft", "render": "render"},
        )
        workflow.add_edge("revise_draft", "render")
        workflow.add_edge("render", "save_memory")
        workflow.add_edge("save_memory", END)

        if compile_with_checkpointer:
            return workflow.compile(checkpointer=self.checkpointer)
        return workflow.compile()
