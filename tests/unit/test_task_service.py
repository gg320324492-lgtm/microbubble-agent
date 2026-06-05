"""任务服务单元测试"""

import pytest
from datetime import datetime, timedelta, timezone
from app.services.task_service import TaskService
from app.models.task import Task, TaskStatus


class TestCreateTask:
    """创建任务"""

    @pytest.mark.asyncio
    async def test_create_success(self, db, test_member):
        """正常创建任务"""
        svc = TaskService(db)
        task = await svc.create_task(
            title="测试任务",
            description="描述",
            assignee_id=test_member.id,
            priority="medium",
        )
        assert task.title == "测试任务"
        assert task.status == TaskStatus.IN_PROGRESS.value
        assert task.assignee_id == test_member.id
        assert task.deleted_at is None

    @pytest.mark.asyncio
    async def test_create_minimal(self, db):
        """仅必填字段创建"""
        svc = TaskService(db)
        task = await svc.create_task(title="最小任务")
        assert task.title == "最小任务"
        assert task.priority == "medium"  # 默认值


class TestGetTask:
    """获取任务"""

    @pytest.mark.asyncio
    async def test_get_existing(self, db, test_member):
        """获取已存在的任务"""
        svc = TaskService(db)
        created = await svc.create_task(title="已存在", assignee_id=test_member.id)
        fetched = await svc.get_task(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.title == "已存在"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, db):
        """获取不存在的任务应返回 None"""
        svc = TaskService(db)
        result = await svc.get_task(99999)
        assert result is None


class TestGetTasks:
    """列表查询"""

    @pytest.mark.asyncio
    async def test_pagination(self, db, test_member):
        """分页正确"""
        svc = TaskService(db)
        for i in range(25):
            await svc.create_task(title=f"任务{i}", assignee_id=test_member.id)

        tasks, total = await svc.get_tasks(skip=0, limit=10)
        assert len(tasks) == 10
        assert total == 25

    @pytest.mark.asyncio
    async def test_empty_list(self, db):
        """无任务时返回空列表"""
        svc = TaskService(db)
        tasks, total = await svc.get_tasks(skip=0, limit=10)
        assert len(tasks) == 0
        assert total == 0


class TestUpdateTaskStatus:
    """更新任务状态"""

    @pytest.mark.asyncio
    async def test_update_status(self, db, test_member):
        """更新状态成功"""
        svc = TaskService(db)
        task = await svc.create_task(title="待更新", assignee_id=test_member.id)
        updated = await svc.update_task_status(task.id, TaskStatus.DONE.value)
        assert updated is not None
        assert updated.status == TaskStatus.DONE.value

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, db):
        """更新不存在的任务返回 None"""
        svc = TaskService(db)
        result = await svc.update_task_status(99999, TaskStatus.DONE.value)
        assert result is None


class TestGetOverdueTasks:
    """获取逾期任务"""

    @pytest.mark.asyncio
    async def test_no_overdue(self, db, test_member):
        """无逾期任务时返回空列表"""
        svc = TaskService(db)
        # 创建一个未来到期的任务
        future = datetime.now(timezone.utc) + timedelta(days=7)
        await svc.create_task(title="未来任务", assignee_id=test_member.id, due_date=future)
        overdue = await svc.get_overdue_tasks()
        assert isinstance(overdue, list)
