from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.memory import get_memory_service
from app.models.schemas import ApiResponse, MemoryCreateRequest

router = APIRouter(prefix="/memory", tags=["Memory"])


@router.get("/overview")
async def memory_overview(user_id: str = Query("student-demo")):
    data = await get_memory_service().overview(user_id)
    return ApiResponse(message="memory overview", data=data)


@router.get("/sessions")
async def sessions(
    user_id: str = Query("student-demo"),
    limit: int = Query(20, ge=1, le=100),
    query: str = Query(""),
    include_deleted: bool = Query(False),
):
    rows = await get_memory_service().repo.list_sessions(
        user_id,
        limit=limit,
        query=query,
        include_deleted=include_deleted,
    )
    return ApiResponse(message="session list", data=rows)


@router.get("/sessions/{session_id}")
async def session_detail(
    session_id: str,
    user_id: str = Query("student-demo"),
    include_deleted: bool = Query(True),
):
    repo = get_memory_service().repo
    session = await repo.get_session(user_id, session_id, include_deleted=include_deleted)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已被删除")
    turns = await repo.get_session_turns(user_id, session_id, include_deleted=include_deleted)
    return ApiResponse(
        message="session detail",
        data={
            "session": session,
            "turns": [turn.__dict__ for turn in turns],
        },
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user_id: str = Query("student-demo")):
    ok = await get_memory_service().repo.soft_delete_session(user_id, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(message="session soft deleted", data={"session_id": session_id})


@router.post("/sessions/{session_id}/restore")
async def restore_session(session_id: str, user_id: str = Query("student-demo")):
    ok = await get_memory_service().repo.restore_session(user_id, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(message="session restored", data={"session_id": session_id})


@router.get("/search")
async def search_memory(
    user_id: str = Query("student-demo"),
    query: str = Query(""),
    limit: int = Query(20, ge=1, le=100),
    include_deleted: bool = Query(False),
):
    service = get_memory_service()
    sessions = await service.repo.list_sessions(
        user_id,
        limit=limit,
        query=query,
        include_deleted=include_deleted,
    )
    memories = await service.repo.search_long_term_memories(user_id, query, limit=min(limit, 20))
    return ApiResponse(
        message="memory search",
        data={
            "sessions": sessions,
            "long_term_memories": [memory.__dict__ for memory in memories],
        },
    )


@router.get("/long-term")
async def long_term_memories(user_id: str = Query("student-demo"), limit: int = Query(50, ge=1, le=100)):
    rows = await get_memory_service().repo.list_long_term_memories(user_id, limit=limit)
    return ApiResponse(message="long-term memories", data=[row.__dict__ for row in rows])


@router.post("/long-term")
async def create_long_term_memory(payload: MemoryCreateRequest):
    memory = await get_memory_service().repo.add_long_term_memory(
        user_id=payload.user_id,
        kind=payload.kind,
        content=payload.content,
        tags=payload.tags,
        source_session_id=payload.source_session_id,
        metadata=payload.metadata,
    )
    return ApiResponse(message="memory created", data=memory.__dict__)
