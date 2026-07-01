"""Folder REST API (PR2.4)

端点:
  POST   /api/v1/folders              → 创建
  GET    /api/v1/folders              → 列 (含分页 + visibility 过滤)
  GET    /api/v1/folders/tree         → 树形结构 (按 owner 分组, 顶级优先)
  GET    /api/v1/folders/{id}         → 详情
  PUT    /api/v1/folders/{id}         → 改名/移动/改 visibility
  DELETE /api/v1/folders/{id}         → 软删
  POST   /api/v1/folders/{id}/restore → 恢复 (3 天保留期内)
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.folder import Folder
from app.models.member import Member
from app.services.folder_service import FolderService, FolderServiceError

router = APIRouter(prefix="/folders", tags=["网盘文件夹"])


# === Pydantic schemas ===

class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    parent_id: Optional[int] = None
    visibility: str = "team"  # private | team | public


class FolderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    parent_id: Optional[int] = None  # 0 = move to root
    visibility: Optional[str] = None


class FolderItem(BaseModel):
    id: int
    name: str
    parent_id: Optional[int]
    owner_id: int
    visibility: str
    path: str
    depth: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    deleted_at: Optional[str] = None

    class Config:
        from_attributes = True


class FolderListResponse(BaseModel):
    items: List[FolderItem]
    total: int
    page: int
    page_size: int


def _to_item(f: Folder) -> FolderItem:
    return FolderItem(
        id=f.id,
        name=f.name,
        parent_id=f.parent_id,
        owner_id=f.owner_id,
        visibility=f.visibility,
        path=f.path,
        depth=f.depth,
        created_at=str(f.created_at) if f.created_at else None,
        updated_at=str(f.updated_at) if f.updated_at else None,
        deleted_at=str(f.deleted_at) if f.deleted_at else None,
    )


# === CRUD ===

@router.post("", response_model=FolderItem, status_code=201)
async def create_folder(
    payload: FolderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """创建 folder (顶级或子级)

    Body: {name, parent_id?, visibility?}
    Returns: 201 + FolderItem
    """
    svc = FolderService(db)
    try:
        f = await svc.create_folder(
            name=payload.name,
            owner_id=current_user.id,
            parent_id=payload.parent_id,
            visibility=payload.visibility,
        )
    except FolderServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    return _to_item(f)


@router.get("", response_model=FolderListResponse)
async def list_folders(
    parent_id: Optional[int] = Query(None, description="父 folder id (None=全部)"),
    visibility: Optional[str] = Query(None, description="private|team|public"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    include_deleted: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """列 folder (按 current_user 越权过滤: private 仅 owner 可见)

    Query: parent_id, visibility, page, page_size
    """
    svc = FolderService(db)
    items, total = await svc.list_folders(
        current_user_id=current_user.id,
        parent_id=parent_id,
        visibility_filter=visibility,
        include_deleted=include_deleted,
        page=page,
        page_size=page_size,
    )
    return FolderListResponse(
        items=[_to_item(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/tree")
async def get_folder_tree(
    root_id: Optional[int] = Query(None, description="根 folder id (None=顶级全部)"),
    max_depth: int = Query(5, ge=1, le=5),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """树形结构 (递归, 最多 max_depth 层)

    用于 DesktopDriveView 左侧 FolderTree 组件
    返回: [{id, name, depth, children: [...]}]
    """
    svc = FolderService(db)

    # BFS 收集
    async def _build_tree(parent_id: Optional[int], current_depth: int) -> list:
        if current_depth > max_depth:
            return []
        children = await svc.list_children(folder_id=parent_id, include_deleted=False)
        # 越权过滤
        visible = [
            c for c in children
            if c.visibility != "private" or c.owner_id == current_user.id
        ]
        result = []
        for c in visible:
            result.append({
                "id": c.id,
                "name": c.name,
                "parent_id": c.parent_id,
                "owner_id": c.owner_id,
                "visibility": c.visibility,
                "depth": c.depth,
                "path": c.path,
                "children": await _build_tree(c.id, current_depth + 1),
            })
        return result

    tree = await _build_tree(root_id, 1 if root_id else 0)
    return {"tree": tree, "max_depth": max_depth}


@router.get("/{folder_id}", response_model=FolderItem)
async def get_folder(
    folder_id: int,
    include_deleted: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """folder 详情 + 越权检查"""
    svc = FolderService(db)
    f = await svc.get_folder(folder_id, include_deleted=include_deleted)
    if f is None:
        raise HTTPException(status_code=404, detail=f"folder {folder_id} 不存在")
    # 越权检查: private 非 owner 不可见
    if f.visibility == "private" and f.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此 folder")
    return _to_item(f)


@router.put("/{folder_id}", response_model=FolderItem)
async def update_folder(
    folder_id: int,
    payload: FolderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """更新 folder (rename / move / change visibility)

    Body: {name?, parent_id?, visibility?}
    """
    svc = FolderService(db)
    try:
        f = await svc.update_folder(
            folder_id,
            current_user_id=current_user.id,
            name=payload.name,
            visibility=payload.visibility,
            parent_id=payload.parent_id,
        )
    except FolderServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    if f is None:
        raise HTTPException(status_code=404, detail="folder 不存在或非 owner")
    return _to_item(f)


@router.delete("/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """软删 folder (有未删子 folder/file 时 400)"""
    svc = FolderService(db)
    try:
        ok = await svc.soft_delete_folder(folder_id, current_user_id=current_user.id)
    except FolderServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="folder 不存在或非 owner")
    return


@router.post("/{folder_id}/restore", response_model=FolderItem)
async def restore_folder(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """恢复软删 folder (3 天保留期内, owner only)"""
    svc = FolderService(db)
    f = await svc.restore_folder(folder_id, current_user_id=current_user.id)
    if f is None:
        raise HTTPException(status_code=404, detail="folder 不存在或非 owner")
    return _to_item(f)


# ============================================================
# v2 PR2: folder 回收站列表端点 (与文件回收站对称)
# ============================================================


@router.get("/trash/list", response_model=FolderListResponse)
async def list_trash_folders(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """列回收站中的 folder (deleted_at IS NOT NULL, 仅 owner)."""
    svc = FolderService(db)
    items, total = await svc.list_trash_folders(
        current_user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return FolderListResponse(
        items=[_to_item(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
    )
