"""会议模板服务测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_list_templates_exclude_inactive():
    """list_templates 默认不返回 is_active=False (v77 P2.6-G.2: 返回 (items, total) tuple)"""
    db = MagicMock()
    # v77 P2.6-G.2: list_templates 现在返回 (items, total) tuple
    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = []
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    db.execute = AsyncMock(side_effect=[items_result, count_result])

    from app.services.meeting_template_service import list_templates

    items, total = await list_templates(db, include_inactive=False)
    assert db.execute.called
    assert items == []
    assert total == 0


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


# v77 P2.6-G.2: list_templates 扩参测试 (search / type_filter / status_filter / pagination)


@pytest.mark.asyncio
async def test_list_templates_search_模糊匹配():
    """list_templates search 参数按 name ILIKE 模糊匹配"""
    from app.services.meeting_template_service import list_templates
    from app.models.meeting_template import MeetingTemplate

    db = MagicMock()
    # 第一次 execute 返回 items, 第二次 (count) 返回 total
    builtin1 = MagicMock(spec=MeetingTemplate)
    builtin1.name = "组会"
    builtin2 = MagicMock(spec=MeetingTemplate)
    builtin2.name = "组内讨论"

    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = [builtin1, builtin2]
    count_result = MagicMock()
    count_result.scalar.return_value = 2

    db.execute = AsyncMock(side_effect=[items_result, count_result])

    items, total = await list_templates(db, include_inactive=True, search="组")
    assert total == 2
    assert len(items) == 2
    # 验证 execute 被调用 2 次 (items + count)
    assert db.execute.call_count == 2
    # 验证传入的 select 对象包含 search pattern (含 search 的 where 子句)
    # 通过 select.compile() 验证
    from sqlalchemy.dialects import postgresql
    select_call_arg = db.execute.call_args_list[0].args[0]
    compiled = str(select_call_arg.compile(dialect=postgresql.dialect()))
    assert "ILIKE" in compiled.upper() or "ilike" in compiled.lower()


@pytest.mark.asyncio
async def test_list_templates_type_filter_builtin():
    """list_templates type_filter='builtin' 只返回 builtin 模板"""
    from app.services.meeting_template_service import list_templates
    from app.models.meeting_template import MeetingTemplate

    db = MagicMock()
    builtin1 = MagicMock(spec=MeetingTemplate)
    builtin1.is_builtin = True
    builtin1.name = "组会"

    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = [builtin1]
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    db.execute = AsyncMock(side_effect=[items_result, count_result])

    items, total = await list_templates(db, include_inactive=True, type_filter='builtin')
    assert all(t.is_builtin for t in items)
    # 验证 SQL 包含 is_builtin WHERE 子句
    from sqlalchemy.dialects import postgresql
    select_call_arg = db.execute.call_args_list[0].args[0]
    compiled = str(select_call_arg.compile(dialect=postgresql.dialect()))
    assert "is_builtin" in compiled.lower()


@pytest.mark.asyncio
async def test_list_templates_type_filter_custom():
    """list_templates type_filter='custom' 只返回 custom 模板"""
    from app.services.meeting_template_service import list_templates
    from app.models.meeting_template import MeetingTemplate

    db = MagicMock()
    custom1 = MagicMock(spec=MeetingTemplate)
    custom1.is_builtin = False
    custom1.name = "我的组会"

    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = [custom1]
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    db.execute = AsyncMock(side_effect=[items_result, count_result])

    items, total = await list_templates(db, include_inactive=True, type_filter='custom')
    assert all(not t.is_builtin for t in items)


@pytest.mark.asyncio
async def test_list_templates_status_filter_inactive():
    """list_templates status_filter='inactive' 只返回 is_active=False"""
    from app.services.meeting_template_service import list_templates
    from app.models.meeting_template import MeetingTemplate

    db = MagicMock()
    inactive1 = MagicMock(spec=MeetingTemplate)
    inactive1.is_active = False
    inactive1.name = "已禁用模板"

    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = [inactive1]
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    db.execute = AsyncMock(side_effect=[items_result, count_result])

    items, total = await list_templates(
        db, include_inactive=True, status_filter='inactive'
    )
    assert all(not t.is_active for t in items)


@pytest.mark.asyncio
async def test_list_templates_pagination():
    """list_templates 分页正确性 (page1 + page2 不重叠)"""
    from app.services.meeting_template_service import list_templates
    from app.models.meeting_template import MeetingTemplate

    # Page 1 数据
    db1 = MagicMock()
    p1_t1 = MagicMock(spec=MeetingTemplate)
    p1_t1.id = 1
    p1_t2 = MagicMock(spec=MeetingTemplate)
    p1_t2.id = 2

    p1_items = MagicMock()
    p1_items.scalars.return_value.all.return_value = [p1_t1, p1_t2]
    p1_count = MagicMock()
    p1_count.scalar.return_value = 4
    db1.execute = AsyncMock(side_effect=[p1_items, p1_count])

    page1, total1 = await list_templates(db1, include_inactive=True, page=1, page_size=2)
    assert len(page1) == 2
    assert total1 == 4

    # Page 2 数据 (与 page1 不重叠)
    db2 = MagicMock()
    p2_t1 = MagicMock(spec=MeetingTemplate)
    p2_t1.id = 3
    p2_t2 = MagicMock(spec=MeetingTemplate)
    p2_t2.id = 4

    p2_items = MagicMock()
    p2_items.scalars.return_value.all.return_value = [p2_t1, p2_t2]
    p2_count = MagicMock()
    p2_count.scalar.return_value = 4
    db2.execute = AsyncMock(side_effect=[p2_items, p2_count])

    page2, total2 = await list_templates(db2, include_inactive=True, page=2, page_size=2)
    assert len(page2) == 2
    assert total2 == 4
    # page1 和 page2 的 id 不重叠
    p1_ids = {t.id for t in page1}
    p2_ids = {t.id for t in page2}
    assert p1_ids.isdisjoint(p2_ids)
    # 验证 SQL 包含 LIMIT/OFFSET 子句 (page_size=2, page=2 → offset=2 limit=2)
    from sqlalchemy.dialects import postgresql
    select_call_arg = db2.execute.call_args_list[0].args[0]
    compiled = str(select_call_arg.compile(dialect=postgresql.dialect()))
    assert "LIMIT" in compiled.upper() or "limit" in compiled.lower()
    assert "OFFSET" in compiled.upper() or "offset" in compiled.lower()


# v77 P2.6-G.2: 批量操作测试 (batch_toggle_active + batch_delete_templates)


@pytest.mark.asyncio
async def test_batch_toggle_active_builtin_允许():
    """batch_toggle_active builtin 模板可以批量 toggle (与 F.5 单条一致)"""
    from app.services.meeting_template_service import batch_toggle_active
    from app.models.meeting_template import MeetingTemplate

    db = MagicMock()
    builtin1 = MagicMock(spec=MeetingTemplate)
    builtin1.id = 1
    builtin1.is_builtin = True
    builtin1.is_active = True

    builtin2 = MagicMock(spec=MeetingTemplate)
    builtin2.id = 2
    builtin2.is_builtin = True
    builtin2.is_active = True

    result = MagicMock()
    result.scalars.return_value.all.return_value = [builtin1, builtin2]
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()

    count = await batch_toggle_active(db, [1, 2], is_active=False)

    # 验证更新条数
    assert count == 2
    # 验证 builtin.is_active 已被设为 False
    assert builtin1.is_active is False
    assert builtin2.is_active is False
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_batch_toggle_active_custom_支持():
    """batch_toggle_active custom 模板可批量 toggle"""
    from app.services.meeting_template_service import batch_toggle_active
    from app.models.meeting_template import MeetingTemplate

    db = MagicMock()
    custom1 = MagicMock(spec=MeetingTemplate)
    custom1.id = 10
    custom1.is_builtin = False
    custom1.is_active = False

    result = MagicMock()
    result.scalars.return_value.all.return_value = [custom1]
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()

    count = await batch_toggle_active(db, [10], is_active=True)
    assert count == 1
    assert custom1.is_active is True


@pytest.mark.asyncio
async def test_batch_toggle_active_empty_ids():
    """batch_toggle_active 空 ids 列表直接返回 0"""
    from app.services.meeting_template_service import batch_toggle_active

    db = MagicMock()

    count = await batch_toggle_active(db, [], is_active=True)
    assert count == 0
    # 不应查 DB / commit
    db.execute.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_batch_delete_builtin_跳过():
    """batch_delete_templates builtin 自动跳过 + 返回 skipped_builtin 列表"""
    from app.services.meeting_template_service import batch_delete_templates
    from app.models.meeting_template import MeetingTemplate

    db = MagicMock()
    builtin1 = MagicMock(spec=MeetingTemplate)
    builtin1.id = 1
    builtin1.is_builtin = True
    custom1 = MagicMock(spec=MeetingTemplate)
    custom1.id = 10
    custom1.is_builtin = False

    result = MagicMock()
    result.scalars.return_value.all.return_value = [builtin1, custom1]
    db.execute = AsyncMock(return_value=result)
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    deleted, skipped = await batch_delete_templates(db, [1, 10])

    # custom 删了, builtin 跳过
    assert deleted == 1
    assert skipped == [1]
    # 验证 db.delete 只调一次 (custom)
    assert db.delete.call_count == 1
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_batch_delete_all_builtin_skipped():
    """batch_delete_templates 全 builtin 时 deleted=0, skipped=全部"""
    from app.services.meeting_template_service import batch_delete_templates
    from app.models.meeting_template import MeetingTemplate

    db = MagicMock()
    builtin1 = MagicMock(spec=MeetingTemplate)
    builtin1.id = 1
    builtin1.is_builtin = True
    builtin2 = MagicMock(spec=MeetingTemplate)
    builtin2.id = 2
    builtin2.is_builtin = True

    result = MagicMock()
    result.scalars.return_value.all.return_value = [builtin1, builtin2]
    db.execute = AsyncMock(return_value=result)
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    deleted, skipped = await batch_delete_templates(db, [1, 2])

    assert deleted == 0
    assert sorted(skipped) == [1, 2]
    # 不应调 db.delete (全部 builtin 跳过)
    db.delete.assert_not_called()


@pytest.mark.asyncio
async def test_batch_delete_empty_ids():
    """batch_delete_templates 空 ids 列表直接返回 (0, [])"""
    from app.services.meeting_template_service import batch_delete_templates

    db = MagicMock()

    deleted, skipped = await batch_delete_templates(db, [])
    assert deleted == 0
    assert skipped == []
    db.execute.assert_not_called()
    db.commit.assert_not_called()
