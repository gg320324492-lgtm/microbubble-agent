"""课题组网盘 Agent 工具 (PR2.9)

新增 2 个工具:
- list_drive_files: 列网盘文件 (供 Agent 在对话中查询"我有哪些 PPT")
- search_my_files: 搜我自己的 drive 文件 (按 title/file_name 关键词)

**关键隐私边界**:
- drive 模式 Agent 可见 (但 search_knowledge 看不到, PR2.10 加硬过滤)
- private 文件: Agent 只能看到自己创建的 (通过 ctx.user_id 限定)
- team/public: Agent 可见全员上传的
"""
import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool
from app.services.drive_service import DriveService

logger = logging.getLogger("microbubble.agent.tools.drive")


# === list_drive_files ===

class ListDriveFilesInput(BaseModel):
    folder_id: Optional[int] = Field(
        None, description="父 folder id (None=顶级, 0=全部)",
    )
    visibility: Optional[str] = Field(
        None, description="private|team|public (None=全部, 含 private 仅 owner 自己的)",
    )
    page: int = Field(1, ge=1, description="页码 1-based")
    page_size: int = Field(20, ge=1, le=50, description="每页条数")


class DriveFileSummary(BaseModel):
    id: int
    title: str
    file_name: str
    file_type: str
    visibility: str
    folder_id: Optional[int] = None
    created_at: Optional[str] = None
    download_count: int = 0


class ListDriveFilesOutput(BaseModel):
    items: List[DriveFileSummary]
    total: int
    page: int
    page_size: int
    rich_block_type: str = "drive_file_list"


@tool(
    name="list_drive_files",
    description=(
        "列课题组网盘文件 (Agent 工具).\n"
        "适用场景: 用户问'我有哪些 PPT'/'组会资料在哪'/'昨天上传的报告'.\n"
        "返回文件列表 (id, title, file_name, visibility, download_count).\n"
        "隐私边界: private 文件仅 owner 可见 (即 current_user), team/public 全员可见.\n"
        "注意: drive 文件不入知识库向量索引 (storage_mode='drive'), 搜不到要走本工具."
    ),
    input_model=ListDriveFilesInput,
    output_model=ListDriveFilesOutput,
)
async def list_drive_files(input: ListDriveFilesInput, ctx: ToolContext) -> dict:
    """列 drive 文件 (含越权过滤)"""
    if not ctx.db or not ctx.user_id:
        return {"items": [], "total": 0, "page": input.page, "page_size": input.page_size,
                "rich_block_type": "drive_file_list", "status": "error", "message": "无法识别用户"}

    svc = DriveService(ctx.db)
    items, total = await svc.list_files(
        current_user_id=ctx.user_id,
        folder_id=input.folder_id if input.folder_id != 0 else None,
        visibility_filter=input.visibility,
        storage_mode="drive",
        include_deleted=False,
        page=input.page,
        page_size=input.page_size,
    )
    return {
        "items": [
            {
                "id": x.id,
                "title": x.title,
                "file_name": x.file_name or "",
                "file_type": x.file_type or "",
                "visibility": x.visibility,
                "folder_id": x.folder_id,
                "created_at": str(x.created_at) if x.created_at else None,
                "download_count": x.download_count or 0,
            }
            for x in items
        ],
        "total": total,
        "page": input.page,
        "page_size": input.page_size,
        "rich_block_type": "drive_file_list",
    }


# === search_my_files ===

class SearchMyFilesInput(BaseModel):
    query: str = Field(..., min_length=1, description="搜索关键词 (匹配 title 或 file_name, ILIKE)")
    top_k: int = Field(10, ge=1, le=50, description="返回前 N 条")
    visibility: Optional[str] = Field(
        None, description="private|team|public (None=全部)",
    )


class SearchMyFilesOutput(BaseModel):
    items: List[DriveFileSummary]
    total: int
    rich_block_type: str = "drive_file_list"


@tool(
    name="search_my_files",
    description=(
        "按 title / file_name 关键词搜索我自己的 drive 文件.\n"
        "适用场景: '找一下上次上传的论文'/'PPT 里提到臭氧的有哪些'.\n"
        "区别 list_drive_files: 本工具走 ILIKE 模糊搜索, 不只是时间排序.\n"
        "隐私边界: 仅搜当前用户的文件 (created_by=current_user), 不能搜别人的."
    ),
    input_model=SearchMyFilesInput,
    output_model=SearchMyFilesOutput,
)
async def search_my_files(input: SearchMyFilesInput, ctx: ToolContext) -> dict:
    """搜我自己的 drive 文件 (按 title/file_name ILIKE 匹配)"""
    if not ctx.db or not ctx.user_id:
        return {"items": [], "total": 0, "rich_block_type": "drive_file_list",
                "status": "error", "message": "无法识别用户"}

    from sqlalchemy import and_, or_, select, func

    from app.models.knowledge import Knowledge

    pattern = f"%{input.query}%"
    stmt = select(Knowledge).where(
        Knowledge.storage_mode == "drive",
        Knowledge.deleted_at.is_(None),
        Knowledge.created_by == ctx.user_id,
        or_(
            Knowledge.title.ilike(pattern),
            Knowledge.file_name.ilike(pattern),
        ),
    )
    if input.visibility:
        stmt = stmt.where(Knowledge.visibility == input.visibility)
    stmt = stmt.order_by(Knowledge.created_at.desc()).limit(input.top_k)

    result = await ctx.db.execute(stmt)
    items = list(result.scalars().all())

    return {
        "items": [
            {
                "id": x.id,
                "title": x.title,
                "file_name": x.file_name or "",
                "file_type": x.file_type or "",
                "visibility": x.visibility,
                "folder_id": x.folder_id,
                "created_at": str(x.created_at) if x.created_at else None,
                "download_count": x.download_count or 0,
            }
            for x in items
        ],
        "total": len(items),
        "rich_block_type": "drive_file_list",
    }
