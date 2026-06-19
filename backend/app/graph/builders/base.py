from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.utils.workflow_events import workflow_done, workflow_error, workflow_start


class BaseGraphBuilder:
    def __init__(self):
        self.checkpointer = InMemorySaver()
        self.app = self._build_graph()

    def _build_graph(self, compile_with_checkpointer: bool = True):
        raise NotImplementedError

    def get_node_name_map(self) -> dict[str, str]:
        return {}

    def get_output_map(self) -> dict[str, str]:
        return {}

    def initial_message(self, inputs: dict[str, Any]) -> str:
        return (
            inputs.get("title")
            or inputs.get("task_description")
            or inputs.get("change_request")
            or "新的写作任务"
        )

    async def process(self, inputs: dict[str, Any]):
        session_id = inputs.get("session_id", "demo-session") or "demo-session"
        config = {"configurable": {"thread_id": session_id}}
        initial_state = {
            "inputs": inputs,
            "messages": [HumanMessage(content=self.initial_message(inputs))],
            "revision_count": 0,
        }

        node_name_map = self.get_node_name_map()
        output_map = self.get_output_map()
        final_output = ""
        active_runs: set[str] = set()
        emitted_starts: set[str] = set()

        try:
            async for event in self.app.astream_events(initial_state, config=config, version="v2"):
                kind = event.get("event")
                node_id = event.get("metadata", {}).get("langgraph_node")
                if node_id not in node_name_map:
                    continue
                run_id = event.get("run_id", "")

                display_name = node_name_map[node_id]
                if kind == "on_chain_start":
                    if node_id in emitted_starts:
                        continue
                    if run_id:
                        active_runs.add(run_id)
                    emitted_starts.add(node_id)
                    yield workflow_start(node_id, f"正在执行：{display_name}")

                elif kind == "on_chain_end":
                    if run_id and run_id not in active_runs:
                        continue
                    output = event.get("data", {}).get("output", {})
                    field = output_map.get(node_id)
                    text = self._extract_text(output, field)
                    if not text and field:
                        continue
                    if node_id == "render" and text:
                        final_output = text
                    if run_id:
                        active_runs.discard(run_id)
                    emitted_starts.discard(node_id)
                    yield workflow_done(
                        node_id,
                        text or f"{display_name}已完成",
                        typy="result" if node_id == "render" else "think",
                    )

            if not final_output:
                state = await self.app.aget_state(config)
                final_output = state.values.get("final_output", "")
                if final_output:
                    yield workflow_done("render", final_output, typy="result")
        except Exception as exc:
            yield workflow_error("workflow", f"工作流执行失败：{exc}", typy="error")
            raise

    def _extract_text(self, output: Any, field: str | None) -> str:
        if not output:
            return ""
        if field and isinstance(output, dict) and field in output:
            return self._stringify(output[field])
        if isinstance(output, dict):
            for value in output.values():
                if isinstance(value, dict) and field and field in value:
                    return self._stringify(value[field])
            return self._stringify(output)
        return self._stringify(output)

    def _stringify(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, indent=2)
