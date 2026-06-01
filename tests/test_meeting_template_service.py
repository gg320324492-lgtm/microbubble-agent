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
