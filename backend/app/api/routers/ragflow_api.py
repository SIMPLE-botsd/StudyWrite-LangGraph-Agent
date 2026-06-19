from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.schemas import ApiResponse, RagflowCreateDatasetRequest, RagflowRetrieveRequest
from app.services.ragflow_service import RagflowFile, RagflowNotConfigured, ragflow_service

router = APIRouter(prefix="/ragflow", tags=["RAGFlow Knowledge"])


@router.get("/status")
async def ragflow_status():
    return ApiResponse(message="ragflow status", data=ragflow_service.status())


@router.get("/datasets")
async def ragflow_datasets():
    return ApiResponse(message="ragflow datasets", data=await _safe_call(ragflow_service.list_datasets))


@router.post("/datasets")
async def ragflow_create_dataset(payload: RagflowCreateDatasetRequest):
    data = await _safe_call(ragflow_service.create_dataset, payload.name, payload.description)
    return ApiResponse(message="ragflow dataset created", data=data)


@router.post("/documents")
async def ragflow_upload_document(
    dataset_id: str = Form(...),
    file: UploadFile = File(...),
):
    content = await file.read()
    data = await _safe_call(
        ragflow_service.upload_document,
        dataset_id,
        RagflowFile(
            filename=file.filename or "upload.txt",
            content=content,
            content_type=file.content_type or "application/octet-stream",
        ),
    )
    return ApiResponse(message="ragflow document uploaded", data=data)


@router.post("/retrieve")
async def ragflow_retrieve(payload: RagflowRetrieveRequest):
    data = await _safe_call(
        ragflow_service.retrieve,
        payload.question,
        payload.dataset_ids,
        top_k=payload.top_k,
    )
    return ApiResponse(message="ragflow retrieval", data=data)


@router.post("/initialize-writing")
async def ragflow_initialize_writing():
    data = await _safe_call(ragflow_service.initialize_writing_datasets)
    return ApiResponse(message="ragflow writing datasets initialized", data=data)


async def _safe_call(func, *args, **kwargs):
    try:
        return await func(*args, **kwargs)
    except RagflowNotConfigured as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
