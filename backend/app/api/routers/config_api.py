from __future__ import annotations

from fastapi import APIRouter

from app.core.llm_factory import get_model_status
from app.models.schemas import ApiResponse

router = APIRouter(prefix="/model", tags=["Model Config"])


@router.get("/config")
async def model_config():
    return ApiResponse(message="model config", data=get_model_status())
