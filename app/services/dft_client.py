r"""dft-service HTTP 客户端 — 2026-08-30 DFT 系统外置到 E:\dft-service 后的接缝

计算实现全部迁到独立服务 (Gaussian/GROMACS/MACE/PySCF/Psi4), 本项目只剩:
- agent @tool (app/agent/tools/dft_tools.py): 提交 + 轮询 + 富文本块
- API 薄代理 (app/api/v1/dft.py): 前端 /dft 页面无感迁移

服务地址/鉴权见 settings.DFT_SERVICE_URL / DFT_SERVICE_API_KEY。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger("microbubble.dft_client")

# 轮询间隔 (服务端 driver 都是分钟级任务, 秒级轮询足够)
_POLL_INTERVAL_S = 3.0
# 共享 AsyncClient (单事件循环内复用连接池; 进程生命周期 = 客户端生命周期)
_client: Optional[httpx.AsyncClient] = None


def _headers() -> dict[str, str]:
    key = settings.DFT_SERVICE_API_KEY
    return {"X-API-Key": key} if key else {}


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=5.0),
            headers=_headers(),
        )
    return _client


def service_url(path: str) -> str:
    return f"{settings.DFT_SERVICE_URL.rstrip('/')}{path}"


def _unavailable(exc: Exception) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "error_msg": (
            f"dft-service 不可达 ({settings.DFT_SERVICE_URL}) — "
            "请在计算服务器上启动 dft-service: "
            "cd E:\\dft-service && .venv\\Scripts\\python run.py"
        ),
        "detail": repr(exc),
    }


async def dft_get(path: str) -> dict[str, Any]:
    """GET 转发 (tools/status/result/jobs); 永不抛异常"""
    try:
        r = await get_client().get(service_url(path))
        r.raise_for_status()
        return r.json()
    except Exception as e:  # noqa: BLE001 — 业务层把异常包成 dict
        logger.warning("dft_service GET %s failed: %r", path, e)
        return _unavailable(e)


async def dft_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST 转发 (提交任务); 永不抛异常"""
    try:
        r = await get_client().post(service_url(path), json=payload)
        r.raise_for_status()
        return r.json()
    except Exception as e:  # noqa: BLE001
        logger.warning("dft_service POST %s failed: %r", path, e)
        return _unavailable(e)


async def submit_and_wait(
    endpoint: str, payload: dict[str, Any], timeout_s: float,
) -> dict[str, Any]:
    """提交任务 + 轮询到终态 — 保持外置前 @tool 的同步语义 (LLM 直接拿结果)

    - endpoint: gaussian / gromacs / mace / pyscf / psi4
    - 超时返回 status=timeout + task_id (任务仍在服务端继续跑, 可拿 id 再查)
    """
    task = await dft_post(f"/dft/{endpoint}", payload)
    if task.get("status") == "unavailable":
        return task
    task_id = task.get("task_id")
    if not task_id:
        return {
            "status": "failed",
            "error_msg": f"dft-service 返回异常: {task}",
        }

    deadline = time.monotonic() + max(timeout_s, 10.0)
    while time.monotonic() < deadline:
        rec = await dft_get(f"/dft/result/{task_id}")
        status = rec.get("status")
        if status == "unavailable":
            return rec
        if status not in ("queued", "running", None):
            result = rec.get("result") or {}
            result.setdefault("task_id", task_id)
            return result
        await asyncio.sleep(_POLL_INTERVAL_S)

    return {
        "status": "timeout",
        "task_id": task_id,
        "error_msg": (
            f"等待 {timeout_s:.0f}s 未完成 — 任务仍在服务端运行, "
            "稍后可用 task_id 查询 /dft/result/{task_id}"
        ),
    }


async def aclose() -> None:
    """进程退出/测试清理用"""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
