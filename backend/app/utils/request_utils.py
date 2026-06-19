from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse


def error_response(message: str, status_code: int = 500):
    return JSONResponse(
        {"status": "error", "message": message, "data": None},
        status_code=status_code,
    )


async def handle_workflow_request(
    *,
    feature: str,
    payload_dict: dict[str, Any],
    http_request: Request,
    workflow,
):
    inputs = dict(payload_dict)
    inputs["feature"] = feature
    inputs["message_id"] = str(uuid.uuid4())
    is_stream = bool(inputs.pop("is_stream", True))

    if not is_stream:
        try:
            chunks = []
            final_text = ""
            async for chunk in workflow.process(inputs):
                chunks.append(chunk)
                if chunk.get("typy") == "result":
                    final_text = chunk.get("text", final_text)
            return JSONResponse(
                {
                    "status": "success",
                    "message": "workflow completed",
                    "message_id": inputs["message_id"],
                    "data": {"final_text": final_text, "chunks": chunks},
                }
            )
        except Exception as exc:
            return error_response(f"工作流执行失败：{exc}")

    async def event_stream():
        try:
            async for chunk in workflow.process(inputs):
                if await http_request.is_disconnected():
                    return
                chunk["message_id"] = inputs["message_id"]
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        except Exception as exc:
            error_chunk = {
                "node": "workflow",
                "event": "error",
                "state": "done",
                "typy": "error",
                "text": f"工作流执行失败：{exc}",
                "message_id": inputs["message_id"],
            }
            yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
