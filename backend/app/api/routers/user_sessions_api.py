from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.memory import get_memory_service
from app.models.schemas import ApiResponse

router = APIRouter(prefix="/users/{user_id}/sessions", tags=["User Sessions"])


@router.get("")
async def list_user_sessions(
    user_id: str,
    limit: int = Query(40, ge=1, le=100),
    query: str = Query(""),
    include_deleted: bool = Query(False),
    deleted_only: bool = Query(False),
):
    # 左侧会话列表只读取未删除会话；需要回收站时通过 include_deleted/deleted_only 控制。
    rows = await get_memory_service().repo.list_sessions(
        user_id=user_id,
        limit=limit,
        query=query,
        include_deleted=include_deleted,
        deleted_only=deleted_only,
    )
    return ApiResponse(message="用户会话列表", data=rows)


@router.get("/{session_id}")
async def get_user_session(
    user_id: str,
    session_id: str,
    include_deleted: bool = Query(True),
):
    repo = get_memory_service().repo
    session = await repo.get_session(user_id, session_id, include_deleted=include_deleted)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已被删除")
    turns = await repo.get_session_turns(user_id, session_id, include_deleted=include_deleted)
    return ApiResponse(
        message="用户会话详情",
        data={
            "session": session,
            "turns": [turn.__dict__ for turn in turns],
        },
    )


@router.delete("/{session_id}")
async def soft_delete_user_session(user_id: str, session_id: str):
    # 给用户提供软删除能力，不物理删除对话和生成文章，便于误删恢复和答辩检查数据。
    ok = await get_memory_service().repo.soft_delete_session(user_id, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(message="会话已移入回收站", data={"session_id": session_id, "deleted": True})


@router.post("/{session_id}/restore")
async def restore_user_session(user_id: str, session_id: str):
    ok = await get_memory_service().repo.restore_session(user_id, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(message="会话已恢复", data={"session_id": session_id, "deleted": False})
