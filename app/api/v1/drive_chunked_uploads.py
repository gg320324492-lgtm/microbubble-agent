"""Drive chunked upload API (W72 B-3, Alembic 080).

All rows are scoped by the JWT user's id. Chunk payloads are raw bytes; SHA256 is supplied in
the ``X-Chunk-SHA256`` header so multipart/base64 overhead is avoided.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.drive_files import DriveFileItem, _to_item
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.services.drive_chunked_upload_service import (
    DEFAULT_CHUNK_SIZE,
    DriveChunkedUploadError,
    DriveChunkedUploadService,
)

router = APIRouter(prefix="/drive/chunked-uploads", tags=["网盘分片上传"])


class ChunkedUploadInitRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=500)
    file_size: int = Field(..., gt=0)
    chunk_size: int = Field(DEFAULT_CHUNK_SIZE, ge=256 * 1024, le=32 * 1024 * 1024)
    parent_id: Optional[int] = None
    checksum: Optional[str] = Field(None, min_length=64, max_length=64)


class ChunkedUploadCompleteRequest(BaseModel):
    final_checksum: Optional[str] = Field(None, min_length=64, max_length=64)
    visibility: str = Field("team", pattern="^(private|team|public)$")
    is_team_shared: bool = False


class ChunkedUploadResponse(BaseModel):
    upload_id: str
    filename: str
    file_size: int
    chunk_size: int
    total_chunks: int
    uploaded_chunks: List[int]
    status: str
    expires_at: str


def _response(upload) -> ChunkedUploadResponse:
    return ChunkedUploadResponse(
        upload_id=upload.upload_id,
        filename=upload.filename,
        file_size=upload.file_size,
        chunk_size=upload.chunk_size,
        total_chunks=upload.total_chunks,
        uploaded_chunks=list(upload.uploaded_chunks or []),
        status=upload.status,
        expires_at=upload.expires_at.isoformat(),
    )


def _raise_service_error(exc: DriveChunkedUploadError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/init", response_model=ChunkedUploadResponse, status_code=status.HTTP_201_CREATED)
async def init_chunked_upload(
    body: ChunkedUploadInitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    service = DriveChunkedUploadService(db)
    try:
        upload = await service.init_upload(
            user_id=current_user.id,
            parent_id=body.parent_id,
            filename=body.filename,
            file_size=body.file_size,
            chunk_size=body.chunk_size,
            checksum=body.checksum,
        )
    except DriveChunkedUploadError as exc:
        _raise_service_error(exc)
    return _response(upload)


@router.get("/{upload_id}", response_model=ChunkedUploadResponse)
async def get_chunked_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    service = DriveChunkedUploadService(db)
    try:
        upload = await service.get_upload(upload_id, current_user.id)
    except DriveChunkedUploadError as exc:
        _raise_service_error(exc)
    return _response(upload)


@router.put("/{upload_id}/chunks/{chunk_index}", response_model=ChunkedUploadResponse)
async def put_chunk(
    upload_id: str,
    chunk_index: int,
    request: Request,
    x_chunk_sha256: Optional[str] = Header(None, alias="X-Chunk-SHA256"),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    service = DriveChunkedUploadService(db)
    try:
        upload = await service.upload_chunk(
            upload_id=upload_id,
            user_id=current_user.id,
            chunk_index=chunk_index,
            chunk_data=await request.body(),
            checksum=x_chunk_sha256,
        )
    except DriveChunkedUploadError as exc:
        _raise_service_error(exc)
    return _response(upload)


@router.post("/{upload_id}/complete", response_model=DriveFileItem)
async def complete_chunked_upload(
    upload_id: str,
    body: ChunkedUploadCompleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    service = DriveChunkedUploadService(db)
    try:
        drive_file = await service.complete_upload(
            upload_id=upload_id,
            user_id=current_user.id,
            final_checksum=body.final_checksum,
            visibility=body.visibility,
            is_team_shared=body.is_team_shared,
        )
    except DriveChunkedUploadError as exc:
        _raise_service_error(exc)
    return _to_item(drive_file)


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def abort_chunked_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    service = DriveChunkedUploadService(db)
    try:
        deleted = await service.abort_upload(upload_id=upload_id, user_id=current_user.id)
    except DriveChunkedUploadError as exc:
        _raise_service_error(exc)
    if not deleted:
        raise HTTPException(status_code=404, detail="上传会话不存在")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
