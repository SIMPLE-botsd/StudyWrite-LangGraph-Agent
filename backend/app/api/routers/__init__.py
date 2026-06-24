from fastapi import APIRouter

from app.api.routers.config_api import router as config_router
from app.api.routers.memory_api import router as memory_router
from app.api.routers.ragflow_api import router as ragflow_router
from app.api.routers.student_writer import router as writer_router
from app.api.routers.user_sessions_api import router as user_sessions_router

router = APIRouter()
router.include_router(writer_router)
router.include_router(memory_router)
router.include_router(config_router)
router.include_router(ragflow_router)
router.include_router(user_sessions_router)

__all__ = ["router"]
