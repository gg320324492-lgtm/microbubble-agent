"""任务 API 集成测试"""

import pytest


class TestTaskAPI:
    """任务端点集成测试"""

    @pytest.mark.asyncio
    async def test_create_task(self, client, auth_headers):
        """POST /api/v1/tasks 创建任务"""
        resp = await client.post(
            "/api/v1/tasks",
            json={"title": "集成测试任务", "priority": "high"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "集成测试任务"

    @pytest.mark.asyncio
    async def test_list_tasks_pagination(self, client, auth_headers):
        """GET /api/v1/tasks 分页格式"""
        # 先创建几个任务
        for i in range(5):
            await client.post(
                "/api/v1/tasks",
                json={"title": f"任务{i}"},
                headers=auth_headers,
            )

        resp = await client.get(
            "/api/v1/tasks?page=1&page_size=3",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "pagination" in data
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 3

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, client, auth_headers):
        """GET /api/v1/tasks/99999 返回统一 404 格式"""
        resp = await client.get("/api/v1/tasks/99999", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "TASK_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_unauthorized(self, client):
        """无 token 返回统一 401 格式"""
        resp = await client.get("/api/v1/tasks")
        assert resp.status_code == 401
        data = resp.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_soft_delete_and_restore(self, client, auth_headers):
        """DELETE + POST /restore 完整流程"""
        # 创建
        create_resp = await client.post(
            "/api/v1/tasks",
            json={"title": "待删除"},
            headers=auth_headers,
        )
        task_id = create_resp.json()["id"]

        # 软删除
        del_resp = await client.delete(f"/api/v1/tasks/{task_id}", headers=auth_headers)
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted_at"] is not None

        # 恢复
        restore_resp = await client.post(
            f"/api/v1/tasks/{task_id}/restore", headers=auth_headers,
        )
        assert restore_resp.status_code == 200
        assert restore_resp.json()["deleted_at"] is None
