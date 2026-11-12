"""网盘配额显示下线 (2026-11-12 主指挥拍板「去掉配额显示」) 的结构守卫 + 行为测试。

背景: 侧栏徽章写「全组已用 20.8 GB / 10.0 GB」, 但口径其实是**当前登录成员**
的 drive_used_bytes/drive_quota_bytes (默认 10GiB), 既不是全组真实用量, 又会在
软件库 128GB 入库后永久爆红。主指挥选择去掉配额显示。

两条不变量:
  ① 界面不再渲染「/ 上限」与配额进度条, 也不再为徽章发 GET /storage-quota;
  ② 后端 check_quota 恒放行 (用户不存在仍拒绝), 否则界面说不限、上传却 413。
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("SKIP_DB_SETUP", "1")

# ⚠️ 前端源码的结构断言放在 web/src 的 vitest 里 —— 容器内 /app/web 是
#    镜像构建时的旧副本 (类 20.220 已记), 在后端 pytest 里读它必然读到旧版。


@pytest.mark.asyncio(loop_scope="function")
async def test_check_quota_always_allows_existing_user(monkeypatch):
    from app.services.drive_service import DriveService

    user = MagicMock()
    user.drive_used_bytes = 999 * 1024 ** 3   # 远超旧的 10GiB 线
    user.drive_quota_bytes = 10 * 1024 ** 3
    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = user
    db = MagicMock()
    db.execute = AsyncMock(return_value=fake_result)
    svc = DriveService(db)
    allowed, used_after, quota = await svc.check_quota(3, 12 * 1024 ** 3)
    assert allowed is True
    assert used_after == 999 * 1024 ** 3 + 12 * 1024 ** 3
    assert quota == 10 * 1024 ** 3  # 仍返回统计值, 但不参与判定


@pytest.mark.asyncio(loop_scope="function")
async def test_check_quota_still_rejects_missing_user():
    from app.services.drive_service import DriveService

    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = None
    db = MagicMock()
    db.execute = AsyncMock(return_value=fake_result)
    svc = DriveService(db)
    assert (await svc.check_quota(999999, 1))[0] is False
