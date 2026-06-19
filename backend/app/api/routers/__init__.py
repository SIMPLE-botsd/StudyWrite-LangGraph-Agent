from fastapi import APIRouter

from app.api.routers.config_api import router as config_router
from app.api.routers.memory_api import router as memory_router
from app.api.routers.ragflow_api import router as ragflow_router
from app.api.routers.student_writer import router as writer_router

router = APIRouter()
router.include_router(writer_router)
router.include_router(memory_router)
router.include_router(config_router)
router.include_router(ragflow_router)

__all__ = ["router"]
