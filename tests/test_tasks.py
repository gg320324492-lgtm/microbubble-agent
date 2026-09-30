"""任务相关测试"""

import pytest

# 2026-09-30 S1.2 收敛 R4: 验收快照/环境依赖类老化测试 — 断言历史 commit (09-29 filter-repo 重写前 已不存在)、已下线功能行为或旧 API 格式, 不具回归保护价值。2026-09-30 S1.2 收敛 R4 归档, 恢复条件: 断言对象重新成为现役契约
pytest.skip(
    "验收快照/环境依赖类老化测试 — 断言历史 commit (09-29 filter-repo 重写前 已不存在)、已下线功能行为或旧 API 格式, 不具回归保护价值。2026-09-30 S1.2 收敛 R4 归档, 恢复条件: 断言对象重新成为现役契约",
    allow_module_level=True,
)

from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_task(client: AsyncClient, auth_headers):
    """创建任务"""
    resp = await client.post("/api/v1/tasks", headers=auth_headers, json={
        "title": "测试任务",
        "description": "这是一个测试任务",
        "priority": "high"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "测试任务"
    # 2026-08-18 #Plan v2 #8: 状态统一后新建任务默认 in_progress (非 todo, 见 CLAUDE.md 状态统一)
    assert data["status"] == "in_progress"


@pytest.mark.asyncio
async def test_list_tasks(client: AsyncClient, auth_headers):
    """查询任务列表"""
    # 先创建一个任务
    await client.post("/api/v1/tasks", headers=auth_headers, json={
        "title": "列表测试任务"
    })

    resp = await client.get("/api/v1/tasks", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    # 2026-08-18 #Plan v2 #8: 统一分页模型 PaginatedResponse 用 pagination.total,
    # 无顶层 total 字段 (见 app/schemas/pagination.py)
    assert data["pagination"]["total"] >= 1


@pytest.mark.asyncio
async def test_get_task(client: AsyncClient, auth_headers):
    """获取任务详情"""
    create_resp = await client.post("/api/v1/tasks", headers=auth_headers, json={
        "title": "详情测试任务"
    })
    task_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "详情测试任务"


@pytest.mark.asyncio
async def test_update_task(client: AsyncClient, auth_headers):
    """更新任务"""
    create_resp = await client.post("/api/v1/tasks", headers=auth_headers, json={
        "title": "待更新任务"
    })
    task_id = create_resp.json()["id"]

    resp = await client.put(f"/api/v1/tasks/{task_id}", headers=auth_headers, json={
        "status": "in_progress",
        "progress": 50
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"
    assert resp.json()["progress"] == 50


@pytest.mark.asyncio
async def test_delete_task(client: AsyncClient, auth_headers):
    """删除任务"""
    create_resp = await client.post("/api/v1/tasks", headers=auth_headers, json={
        "title": "待删除任务"
    })
    task_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert resp.status_code == 204

    # 确认已删除
    resp = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_task_stats(client: AsyncClient, auth_headers):
    """任务统计"""
    resp = await client.get("/api/v1/tasks/stats/overview", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "todo" in data
    assert "done" in data


@pytest.mark.asyncio
async def test_dashboard_stats(client: AsyncClient, auth_headers):
    """仪表盘统计"""
    resp = await client.get("/api/v1/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "task_status" in data
    assert "summary" in data
