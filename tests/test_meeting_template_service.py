"""会议模板服务测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_list_templates_exclude_inactive():
    """list_templates 默认不返回 is_active=False"""
    db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    from app.services.meeting_template_service import list_templates

    result = await list_templates(db, include_inactive=False)
    assert db.execute.called
    assert result == []


@pytest.mark.asyncio
async def test_get_template_returns_none_when_not_found():
    """get_template 不存在时返回 None"""
    db = MagicMock()
    db.get = AsyncMock(return_value=None)

    from app.services.meeting_template_service import get_template

    result = await get_template(db, template_id=999)
    assert result is None


@pytest.mark.asyncio
async def test_create_template_basic():
    """create_template 基本创建"""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    from app.services.meeting_template_service import create_template

    await create_template(
        db,
        name="测试模板",
        agenda=["议题1"],
        default_duration_minutes=30,
        created_by=1,
        is_builtin=False,
        is_active=True,
    )

    db.add.assert_called_once()
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_template_builtin_rejected():
    """update_template 内置模板 name 不可改"""
    db = MagicMock()
    template = MagicMock()
    template.is_builtin = True
    db.get = AsyncMock(return_value=template)

    from app.services.meeting_template_service import update_template

    result = await update_template(db, template_id=1, name="改改名")
    assert result is None


@pytest.mark.asyncio
async def test_delete_template_builtin_rejected():
    """delete_template 内置模板不可删"""
    db = MagicMock()
    template = MagicMock()
    template.is_builtin = True
    db.get = AsyncMock(return_value=template)

    from app.services.meeting_template_service import delete_template

    result = await delete_template(db, template_id=1)
    assert result is False


def test_apply_template_to_meeting_data_fills_title():
    """apply_template_to_meeting_data 自动填 title"""
    tpl = MagicMock()
    tpl.title_template = "组会 - {date}"
    tpl.description = None
    tpl.agenda = None
    tpl.default_duration_minutes = None
    tpl.default_location = None
    tpl.default_participant_ids = None

    from app.services.meeting_template_service import apply_template_to_meeting_data

    result = apply_template_to_meeting_data(
        tpl, meeting_data={"title": "", "start_time": None}
    )
    assert "组会" in result["title"]


# v77 P2.6-F.5: clone_template 3 个测试

@pytest.mark.asyncio
async def test_clone_template_basic():
    """clone_template 基本复制（builtin → custom 副本含 "(副本)" 后缀）"""
    from app.services.meeting_template_service import clone_template
    from app.models.meeting_template import MeetingTemplate

    db = MagicMock()
    source = MagicMock(spec=MeetingTemplate)
    source.id = 5
    source.name = "组会"
    source.title_template = "组会 - {date}"
    source.description = "组内周会"
    source.agenda = ["议题1", "议题2"]
    source.default_duration_minutes = 60
    source.default_participant_ids = [1, 2, 3]
    source.default_location = "会议室A"
    db.get = AsyncMock(return_value=source)
    db.add = MagicMock()
    db.commit = AsyncMock()

    # 让 db.refresh 设置返回 source 的拷贝
    async def fake_refresh(obj):
        obj.id = 99
    db.refresh = AsyncMock(side_effect=fake_refresh)

    result = await clone_template(db, source_id=5, current_user_id=42)

    # 验证返回值
    assert result.id == 99
    # 验证 db.add 被调用 1 次
    db.add.assert_called_once()
    added_obj = db.add.call_args[0][0]
    # 验证 clone 字段正确
    assert added_obj.name == "组会 (副本)"
    assert added_obj.is_builtin is False
    assert added_obj.is_active is True
    assert added_obj.cloned_from_id == 5
    assert added_obj.created_by == 42
    assert added_obj.title_template == "组会 - {date}"
    assert added_obj.description == "组内周会"
    assert added_obj.default_duration_minutes == 60
    assert added_obj.default_location == "会议室A"
    # 验证浅拷贝 (新建 list 而非共享引用)
    assert added_obj.agenda == ["议题1", "议题2"]
    assert added_obj.agenda is not source.agenda
    assert added_obj.default_participant_ids is not source.default_participant_ids
    # 验证 commit + refresh
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(result)


@pytest.mark.asyncio
async def test_clone_template_nonexistent_source():
    """clone_template source_id 不存在时返回 None"""
    from app.services.meeting_template_service import clone_template

    db = MagicMock()
    db.get = AsyncMock(return_value=None)

    result = await clone_template(db, source_id=9999, current_user_id=1)
    assert result is None
    # 不应 commit / add
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_clone_template_agenda_independence():
    """clone_template 修改 clone.agenda 不影响 source.agenda（浅拷贝独立性）"""
    from app.services.meeting_template_service import clone_template
    from app.models.meeting_template import MeetingTemplate

    db = MagicMock()
    source = MagicMock(spec=MeetingTemplate)
    source.id = 7
    source.name = "立项会"
    source.title_template = None
    source.description = None
    source.agenda = ["原始议题1", "原始议题2"]  # 真实 list
    source.default_duration_minutes = 90
    source.default_participant_ids = None
    source.default_location = None
    db.get = AsyncMock(return_value=source)
    db.add = MagicMock()
    db.commit = AsyncMock()

    async def fake_refresh(obj):
        obj.id = 100
    db.refresh = AsyncMock(side_effect=fake_refresh)

    result = await clone_template(db, source_id=7, current_user_id=2)
    added_obj = db.add.call_args[0][0]

    # 修改 clone.agenda 不应影响 source.agenda
    added_obj.agenda.append("新增议题")
    assert source.agenda == ["原始议题1", "原始议题2"], "source.agenda 不应被 clone 修改影响"
    assert added_obj.agenda == ["原始议题1", "原始议题2", "新增议题"]
