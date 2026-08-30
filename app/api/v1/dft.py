"""DFT/MD FastAPI 路由 — 2026-08-30 起为独立 dft-service (E:\dft-service) 的薄代理

计算实现已全部外置; 本路由只做:
- 转发前端 /dft 页面的请求 (axios 无感迁移, 路径形状不变)
- 注入 X-API-Key 与 submitter (microbubble:user_id)

端点:
- GET  /dft/tools              服务端 5 后端健康状态
- POST /dft/{tool}             提交任务 (gaussian/gromacs/mace/pyscf/psi4/auto)
- GET  /dft/status/{task_id}   查状态
- GET  /dft/result/{task_id}   拿结果 (持久化在 dft-service 的 SQLite)
- GET  /dft/jobs               任务列表
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_optional
from app.models.member import Member
from app.services import dft_client

logger = logging.getLogger("microbubble.api.dft")
router = APIRouter(prefix="/dft", tags=["DFT/MD 计算"])

# 允许代理的提交端点 (白名单, 防路径穿越/误代理)
_SUBMIT_TOOLS = {"gaussian", "gromacs", "mace", "pyscf", "psi4", "auto"}


def _submitter(user: Optional[Member]) -> Optional[str]:
    return f"microbubble:{user.id}" if user else None


@router.get("/tools")
async def list_dft_tools():
    """服务端 5 工具健康状态 (透传)"""
    return await dft_client.dft_get("/dft/tools")


@router.post("/{tool}")
async def submit_dft_task(
    tool: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[Member] = Depends(get_current_user_optional),
):
    """提交 DFT 任务 (透传到 dft-service, 立即返回 task_id)"""
    if tool not in _SUBMIT_TOOLS:
        return {"status": "failed", "error_msg": f"unknown dft tool: {tool}"}
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if user:
        payload["submitter"] = _submitter(user)
    return await dft_client.dft_post(f"/dft/{tool}", payload)


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """查任务状态 (dft-service 内存 miss 自动回退其 SQLite, 重启不丢)"""
    return await dft_client.dft_get(f"/dft/status/{task_id}")


@router.get("/result/{task_id}")
async def get_task_result(task_id: str):
    """拿任务结果"""
    return await dft_client.dft_get(f"/dft/result/{task_id}")


@router.get("/jobs")
async def list_dft_jobs(
    tool: Optional[str] = None, status: Optional[str] = None,
    limit: int = 50, offset: int = 0,
):
    """任务列表 (透传过滤/分页参数)"""
    query = f"?limit={limit}&offset={offset}"
    if tool:
        query += f"&tool={tool}"
    if status:
        query += f"&status={status}"
    return await dft_client.dft_get(f"/dft/jobs{query}")
