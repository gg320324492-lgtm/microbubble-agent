"""DFT/MD FastAPI 路由 — Phase 5 集成

端点:
- POST /dft/gaussian            提交 Gaussian 任务 (异步 → task_id)
- POST /dft/gromacs             提交 GROMACS MD 任务
- POST /dft/mace                提交 MACE 优化任务
- POST /dft/pyscf               提交 PySCF 任务
- GET  /dft/status/{task_id}    查任务状态
- GET  /dft/result/{task_id}    拿任务结果
- GET  /dft/tools               健康检查 (所有工具)

异步策略: asyncio.create_task + 内存 dict 缓存 (status/result)。
生产建议替换 Celery, 但本任务保持简单。
任务结果也落 dft_jobs 表 (alembic 099) 持久化。
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_optional
from app.models.member import Member

logger = logging.getLogger("microbubble.api.dft")
router = APIRouter(prefix="/dft", tags=["DFT/MD 计算"])


# ------------------------------------------------------------------
# 内存任务状态 (per-process), 持久化靠 dft_jobs 表
# ------------------------------------------------------------------
_TASKS: dict[str, dict[str, Any]] = {}


def _task_id() -> str:
    return uuid.uuid4().hex[:16]


async def _run_and_store(
    task_id: str,
    tool: str,
    coro_factory,
    user_id: Optional[int],
    db_factory,
    smiles: str,
    params: dict,
) -> None:
    """后台跑任务, 结果落 dft_jobs 表。"""
    _TASKS[task_id] = {
        "task_id": task_id, "tool": tool, "status": "running",
        "smiles": smiles, "params": params,
        "submit_time": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
    }
    try:
        result = await coro_factory()
        _TASKS[task_id]["status"] = result.get("status", "completed")
        _TASKS[task_id]["result"] = result
        _TASKS[task_id]["finish_time"] = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        logger.exception("DFT task %s failed", task_id)
        _TASKS[task_id]["status"] = "failed"
        _TASKS[task_id]["result"] = {"error_msg": repr(e)}
        _TASKS[task_id]["finish_time"] = datetime.now(timezone.utc).isoformat()

    # 落 dft_jobs (best-effort, 失败仅 log)
    try:
        from app.models.dft_job import DFTJob
        async with db_factory() as session:
            row = DFTJob(
                id=task_id,
                user_id=user_id or 0,
                tool=tool,
                smiles=smiles,
                params=params,
                status=_TASKS[task_id]["status"],
                result=_TASKS[task_id].get("result"),
                log_path=(_TASKS[task_id].get("result") or {}).get("log_path"),
                submit_time=datetime.fromisoformat(
                    _TASKS[task_id]["submit_time"].replace("Z", "+00:00")
                ),
                finish_time=datetime.fromisoformat(
                    _TASKS[task_id]["finish_time"].replace("Z", "+00:00")
                ),
            )
            session.add(row)
            await session.commit()
    except Exception:
        logger.exception("Failed to persist DFT job %s to DB", task_id)


# ------------------------------------------------------------------
# Pydantic models
# ------------------------------------------------------------------
class GaussianRequest(BaseModel):
    smiles: str = Field(..., min_length=1)
    xc: str = "B3LYP"
    basis: str = "6-31G(d)"
    job: str = "opt"
    solvent: str = "water"
    timeout_s: float = Field(7200.0, ge=10.0)


class GromacsRequest(BaseModel):
    smiles: str = Field(..., min_length=1)
    n_molecules: int = Field(100, ge=1)
    box_nm: float = Field(3.0, gt=0.0)
    time_ns: float = Field(1.0, gt=0.0)
    temperature_K: float = Field(300.0, ge=0.0)


class MaceRequest(BaseModel):
    smiles: str = Field(..., min_length=1)
    fmax_ev_A: float = Field(0.05, gt=0.0)
    max_steps: int = Field(200, ge=1)
    model: str = "medium"
    save_trajectory: bool = False


class PySCFRequest(BaseModel):
    smiles: str = Field(..., min_length=1)
    method: str = "B3LYP"
    basis: str = "6-31G*"
    operation: str = "energy"
    charge: int = 0
    spin: int = 0


class TaskIdResponse(BaseModel):
    task_id: str
    status: str
    submit_time: str
    tool: str


# ------------------------------------------------------------------
# 端点
# ------------------------------------------------------------------
@router.post("/gaussian", response_model=TaskIdResponse)
async def submit_gaussian(
    req: GaussianRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: Optional[Member] = Depends(get_current_user_optional),
):
    """提交 Gaussian DFT 任务 (异步, 立即返回 task_id)"""
    from app.services.dft.gaussian_runner import run_gaussian_async

    task_id = _task_id()
    _TASKS[task_id] = {
        "task_id": task_id, "tool": "gaussian", "status": "queued",
        "smiles": req.smiles, "params": req.dict(),
        "submit_time": datetime.now(timezone.utc).isoformat(),
        "user_id": user.id if user else None,
    }

    async def _runner():
        return await run_gaussian_async(
            smiles=req.smiles, xc=req.xc, basis=req.basis,
            job=req.job, solvent=req.solvent, timeout_s=req.timeout_s,
            job_id=task_id,
        )

    background_tasks.add_task(_run_and_store, task_id, "gaussian",
                              _runner, user.id if user else None,
                              _session_factory, req.smiles, req.dict())
    return TaskIdResponse(
        task_id=task_id, status="queued",
        submit_time=_TASKS[task_id]["submit_time"], tool="gaussian",
    )


@router.post("/gromacs", response_model=TaskIdResponse)
async def submit_gromacs(
    req: GromacsRequest,
    background_tasks: BackgroundTasks,
    user: Optional[Member] = Depends(get_current_user_optional),
):
    """提交 GROMACS MD 任务 (异步)"""
    from app.services.dft.gromacs_runner import submit_gromacs_async

    task_id = _task_id()
    _TASKS[task_id] = {
        "task_id": task_id, "tool": "gromacs", "status": "queued",
        "smiles": req.smiles, "params": req.dict(),
        "submit_time": datetime.now(timezone.utc).isoformat(),
        "user_id": user.id if user else None,
    }

    async def _runner():
        return await submit_gromacs_async(
            smiles=req.smiles, n_molecules=req.n_molecules,
            box_nm=req.box_nm, time_ns=req.time_ns,
            temperature_K=req.temperature_K, job_id=task_id,
        )

    background_tasks.add_task(_run_and_store, task_id, "gromacs",
                              _runner, user.id if user else None,
                              _session_factory, req.smiles, req.dict())
    return TaskIdResponse(
        task_id=task_id, status="queued",
        submit_time=_TASKS[task_id]["submit_time"], tool="gromacs",
    )


@router.post("/mace", response_model=TaskIdResponse)
async def submit_mace(
    req: MaceRequest,
    background_tasks: BackgroundTasks,
    user: Optional[Member] = Depends(get_current_user_optional),
):
    """提交 MACE 优化任务 (异步)"""
    from app.services.dft.mace_runner import mace_relax_async

    task_id = _task_id()
    _TASKS[task_id] = {
        "task_id": task_id, "tool": "mace", "status": "queued",
        "smiles": req.smiles, "params": req.dict(),
        "submit_time": datetime.now(timezone.utc).isoformat(),
        "user_id": user.id if user else None,
    }

    async def _runner():
        return await mace_relax_async(
            smiles=req.smiles, fmax_ev_A=req.fmax_ev_A,
            max_steps=req.max_steps, model=req.model,
            save_trajectory=req.save_trajectory, job_id=task_id,
        )

    background_tasks.add_task(_run_and_store, task_id, "mace",
                              _runner, user.id if user else None,
                              _session_factory, req.smiles, req.dict())
    return TaskIdResponse(
        task_id=task_id, status="queued",
        submit_time=_TASKS[task_id]["submit_time"], tool="mace",
    )


@router.post("/pyscf", response_model=TaskIdResponse)
async def submit_pyscf(
    req: PySCFRequest,
    background_tasks: BackgroundTasks,
    user: Optional[Member] = Depends(get_current_user_optional),
):
    """提交 PySCF 任务 (异步)"""
    from app.services.dft.multimodel_runner import run_pyscf_async

    task_id = _task_id()
    _TASKS[task_id] = {
        "task_id": task_id, "tool": "pyscf", "status": "queued",
        "smiles": req.smiles, "params": req.dict(),
        "submit_time": datetime.now(timezone.utc).isoformat(),
        "user_id": user.id if user else None,
    }

    async def _runner():
        return await run_pyscf_async(
            smiles=req.smiles, method=req.method, basis=req.basis,
            operation=req.operation, charge=req.charge, spin=req.spin,
            job_id=task_id,
        )

    background_tasks.add_task(_run_and_store, task_id, "pyscf",
                              _runner, user.id if user else None,
                              _session_factory, req.smiles, req.dict())
    return TaskIdResponse(
        task_id=task_id, status="queued",
        submit_time=_TASKS[task_id]["submit_time"], tool="pyscf",
    )


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """查任务状态 (内存 dict, 跨进程不可见 — 查持久化结果用 /result)"""
    if task_id not in _TASKS:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    rec = _TASKS[task_id]
    return {
        "task_id": task_id,
        "status": rec.get("status"),
        "tool": rec.get("tool"),
        "submit_time": rec.get("submit_time"),
        "finish_time": rec.get("finish_time"),
    }


@router.get("/result/{task_id}")
async def get_task_result(task_id: str):
    """拿任务结果 (内存 → DB 回退)"""
    if task_id in _TASKS:
        rec = _TASKS[task_id]
        if rec.get("status") in ("running", "queued"):
            return {
                "task_id": task_id, "status": rec["status"],
                "message": "task still running",
            }
        return {
            "task_id": task_id, "status": rec["status"],
            "result": rec.get("result"),
            "submit_time": rec.get("submit_time"),
            "finish_time": rec.get("finish_time"),
        }
    # 内存丢失, 查 DB
    try:
        from app.models.dft_job import DFTJob
        from sqlalchemy import select
        async with _session_factory() as session:
            row = await session.get(DFTJob, task_id)
            if row is None:
                raise HTTPException(status_code=404,
                                    detail=f"task {task_id} not in DB")
            return {
                "task_id": task_id, "status": row.status,
                "result": row.result,
                "submit_time": row.submit_time.isoformat() if row.submit_time else None,
                "finish_time": row.finish_time.isoformat() if row.finish_time else None,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB query failed: {e}")


@router.get("/tools")
async def list_dft_tools():
    """检查所有工具健康状态"""
    from app.services.dft.tool_definitions import list_available_dft_tools
    return list_available_dft_tools()


# ------------------------------------------------------------------
# session factory helper (avoid import-time cycle)
# ------------------------------------------------------------------
async def _session_factory() -> AsyncSession:
    """新建一个 session (Background task 用的, 不复用 request session)"""
    from app.core.database import async_session
    return async_session()
