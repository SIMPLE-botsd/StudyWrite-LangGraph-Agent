from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ragflow_service import RagflowNotConfigured, ragflow_service


async def main() -> None:
    try:
        results = await ragflow_service.initialize_writing_datasets()
    except RagflowNotConfigured as exc:
        raise SystemExit(str(exc))
    for item in results:
        dataset = item["dataset"]
        docs = item["upload"].get("documents", [])
        doc_names = ", ".join(doc.get("name", "") for doc in docs) or "无文档"
        print(f"{dataset['name']} ({dataset['id']}): {doc_names}")
    print("RAGFlow writing knowledge bases initialized.")


if __name__ == "__main__":
    asyncio.run(main())
