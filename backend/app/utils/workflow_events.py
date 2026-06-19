from __future__ import annotations

from typing import Any


def build_workflow_chunk(node: str, event: str, text: str, typy: str = "think") -> dict[str, Any]:
    state_map = {
        "start": "start",
        "text_chunk": "loading",
        "result": "done",
        "error": "done",
    }
    return {
        "node": node,
        "event": event,
        "state": state_map.get(event, "done"),
        "typy": typy,
        "text": text,
    }


def workflow_start(node: str, text: str, typy: str = "think") -> dict[str, Any]:
    return build_workflow_chunk(node, "start", text, typy)


def workflow_loading(node: str, text: str, typy: str = "think") -> dict[str, Any]:
    return build_workflow_chunk(node, "text_chunk", text, typy)


def workflow_done(node: str, text: str, typy: str = "think") -> dict[str, Any]:
    return build_workflow_chunk(node, "result", text, typy)


def workflow_error(node: str, text: str, typy: str = "error") -> dict[str, Any]:
    return build_workflow_chunk(node, "error", text, typy)
