"""会议服务单元测试"""

import pytest
from datetime import datetime, timedelta, timezone
from app.services.meeting_service import MeetingService


class TestCreateMeeting:
    """创建会议"""

    @pytest.mark.asyncio
    async def test_create_success(self, db, test_member):
        """正常创建会议"""
        svc = MeetingService(db)
        meeting = await svc.create_meeting(
            title="测试会议",
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            created_by=test_member.id,
        )
        assert meeting.title == "测试会议"
        assert meeting.status == "scheduled"
        assert meeting.created_by == test_member.id

    @pytest.mark.asyncio
    async def test_create_with_agenda(self, db, test_member):
        """带议程创建"""
        svc = MeetingService(db)
        meeting = await svc.create_meeting(
            title="有议程的会议",
            agenda=["议题一", "议题二"],
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            created_by=test_member.id,
        )
        assert meeting.agenda == ["议题一", "议题二"]

    @pytest.mark.asyncio
    async def test_create_with_participants(self, db, test_member, admin_member):
        """带参会人创建"""
        svc = MeetingService(db)
        meeting = await svc.create_meeting(
            title="多人会议",
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            participant_ids=[test_member.id, admin_member.id],
            created_by=test_member.id,
        )
        assert meeting.title == "多人会议"


class TestGetMeeting:
    """获取会议"""

    @pytest.mark.asyncio
    async def test_get_existing(self, db, test_member):
        """获取已存在的会议"""
        svc = MeetingService(db)
        created = await svc.create_meeting(
            title="已存在",
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            created_by=test_member.id,
        )
        fetched = await svc.get_meeting(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.title == "已存在"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, db):
        """获取不存在的会议返回 None"""
        svc = MeetingService(db)
        result = await svc.get_meeting(99999)
        assert result is None


class TestListMeetings:
    """列表查询"""

    @pytest.mark.asyncio
    async def test_pagination(self, db, test_member):
        """分页正确"""
        svc = MeetingService(db)
        for i in range(25):
            await svc.create_meeting(
                title=f"会议{i}",
                start_time=datetime.now(timezone.utc) + timedelta(hours=i),
                created_by=test_member.id,
            )

        meetings, total = await svc.get_meetings(skip=0, limit=10)
        assert len(meetings) == 10
        assert total == 25

    @pytest.mark.asyncio
    async def test_empty_list(self, db):
        """无会议时返回空列表"""
        svc = MeetingService(db)
        meetings, total = await svc.get_meetings(skip=0, limit=10)
        assert len(meetings) == 0
        assert total == 0


class TestUpdateMeeting:
    """更新会议"""

    @pytest.mark.asyncio
    async def test_update_title(self, db, test_member):
        """更新标题"""
        svc = MeetingService(db)
        meeting = await svc.create_meeting(
            title="原标题",
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            created_by=test_member.id,
        )
        updated = await svc.update_meeting(meeting.id, title="新标题")
        assert updated is not None
        assert updated.title == "新标题"

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, db):
        """更新不存在的会议返回 None"""
        svc = MeetingService(db)
        result = await svc.update_meeting(99999, title="不存在")
        assert result is None


class TestDeleteMeeting:
    """删除会议"""

    @pytest.mark.asyncio
    async def test_delete_existing(self, db, test_member):
        """删除已存在的会议"""
        svc = MeetingService(db)
        meeting = await svc.create_meeting(
            title="待删除",
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            created_by=test_member.id,
        )
        result = await svc.delete_meeting(meeting.id)
        assert result is True

        # 验证已删除
        fetched = await svc.get_meeting(meeting.id)
        assert fetched is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db):
        """删除不存在的会议返回 False"""
        svc = MeetingService(db)
        result = await svc.delete_meeting(99999)
        assert result is False
