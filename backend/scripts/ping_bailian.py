from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.llm_factory import get_model_status, invoke_text


async def main() -> None:
    status = get_model_status()
    print({**status, "has_api_key": bool(status.get("has_api_key"))})
    if not status.get("has_api_key"):
        raise SystemExit("DASHSCOPE_API_KEY is not configured")
    text = await invoke_text(
        "你是一个中文写作助手。",
        "用一句话说明你已连接百炼云模型。",
        temperature=0.1,
        allow_fallback=False,
    )
    print(text[:300])


if __name__ == "__main__":
    asyncio.run(main())
