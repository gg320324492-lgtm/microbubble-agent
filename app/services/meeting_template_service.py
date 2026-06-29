"""会议模板服务"""
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting_template import MeetingTemplate


async def list_templates(
    db: AsyncSession,
    include_inactive: bool = False,
    search: Optional[str] = None,
    type_filter: Optional[str] = None,    # 'builtin' | 'custom' | None(全部)
    status_filter: Optional[str] = None,  # 'active' | 'inactive' | None(全部)
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[MeetingTemplate], int]:
    """列出模板 (v77 P2.6-G.2 支持 search/filter/pagination)

    Args:
        include_inactive: 是否包含 is_active=False (默认 False 保持向后兼容)
        search: 按 name ILIKE 模糊匹配 (PostgreSQL 大小写不敏感,中文模糊匹配原生支持)
        type_filter: 'builtin' | 'custom' | None(全部)
        status_filter: 'active' | 'inactive' | None(全部)
        page: 1-based 页码
        page_size: 每页条数 (默认 20)

    Returns:
        (items, total) - items 是当页列表,total 是总条数 (分页前的总数)
    """
    query = select(MeetingTemplate)
    count_query = select(func.count(MeetingTemplate.id))

    # 应用 include_inactive 过滤
    if not include_inactive:
        query = query.where(MeetingTemplate.is_active == True)  # noqa: E712
        count_query = count_query.where(MeetingTemplate.is_active == True)  # noqa: E712

    # 应用 search 过滤 (按 name ILIKE 模糊匹配)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(MeetingTemplate.name.ilike(search_pattern))
        count_query = count_query.where(MeetingTemplate.name.ilike(search_pattern))

    # 应用 type_filter
    if type_filter == 'builtin':
        query = query.where(MeetingTemplate.is_builtin == True)  # noqa: E712
        count_query = count_query.where(MeetingTemplate.is_builtin == True)  # noqa: E712
    elif type_filter == 'custom':
        query = query.where(MeetingTemplate.is_builtin == False)  # noqa: E712
        count_query = count_query.where(MeetingTemplate.is_builtin == False)  # noqa: E712

    # 应用 status_filter (与 include_inactive 协同: include_inactive 是粗粒度,status_filter 是细粒度)
    if status_filter == 'active':
        query = query.where(MeetingTemplate.is_active == True)  # noqa: E712
        count_query = count_query.where(MeetingTemplate.is_active == True)  # noqa: E712
    elif status_filter == 'inactive':
        query = query.where(MeetingTemplate.is_active == False)  # noqa: E712
        count_query = count_query.where(MeetingTemplate.is_active == False)  # noqa: E712

    # 排序 + 分页
    query = query.order_by(
        MeetingTemplate.is_builtin.desc(), MeetingTemplate.name
    )
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # 执行查询
    items_result = await db.execute(query)
    items = items_result.scalars().all()
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    return list(items), total


async def get_template(db: AsyncSession, template_id: int) -> Optional[MeetingTemplate]:
    """获取单个模板"""
    return await db.get(MeetingTemplate, template_id)


async def create_template(db: AsyncSession, **kwargs) -> MeetingTemplate:
    """创建用户自定义模板"""
    template = MeetingTemplate(**kwargs)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


async def update_template(db: AsyncSession, template_id: int, **kwargs) -> Optional[MeetingTemplate]:
    """更新模板。

    builtin 保护规则（v77 P2.6-F.5 修正注释与实现一致）:
      - builtin 永远禁止改 name (内置模板名字是身份标识)
      - builtin 永远禁止改 is_builtin (防止变 custom)
      - builtin 允许改 is_active / description / agenda / default_* (用户可定制 builtin 的细节)
      - custom 无任何字段限制（用户自己的模板）

    返回 None 表示: 模板不存在 OR builtin 尝试改 name/is_builtin。
    """
    template = await db.get(MeetingTemplate, template_id)
    if not template:
        return None
    if template.is_builtin:
        # builtin 永远禁止改 name 和 is_builtin
        if "name" in kwargs or "is_builtin" in kwargs:
            return None
    for k, v in kwargs.items():
        if v is not None:
            setattr(template, k, v)
    await db.commit()
    return template


async def delete_template(db: AsyncSession, template_id: int) -> bool:
    """删除模板（is_builtin=True 不可删）"""
    template = await db.get(MeetingTemplate, template_id)
    if not template or template.is_builtin:
        return False
    await db.delete(template)
    await db.commit()
    return True


async def clone_template(
    db: AsyncSession,
    source_id: int,
    current_user_id: Optional[int] = None,
) -> Optional[MeetingTemplate]:
    """v77 P2.6-F.5: 一键复制 builtin 为 custom 副本

    行为:
      - 复制 source 的所有非元字段（name/title_template/description/agenda/default_*）
      - 强制 is_builtin=False, is_active=True（custom 总是 active）
      - cloned_from_id=source.id 记录复制追溯
      - name 加 "(副本)" 后缀（避免与 source 名字冲突，用户可编辑改名）
      - created_by = current_user_id (NULL 也允许)

    返回 None 表示 source_id 不存在。
    """
    source = await db.get(MeetingTemplate, source_id)
    if not source:
        return None
    clone = MeetingTemplate(
        name=f"{source.name} (副本)",
        title_template=source.title_template,
        description=source.description,
        # JSON 列浅拷贝（PostgreSQL JSONB 共享引用但不深 mutate 源；测试中 mutate clone.agenda 不影响 source）
        agenda=list(source.agenda) if source.agenda else None,
        default_duration_minutes=source.default_duration_minutes,
        default_participant_ids=list(source.default_participant_ids) if source.default_participant_ids else None,
        default_location=source.default_location,
        is_builtin=False,
        is_active=True,
        cloned_from_id=source.id,
        created_by=current_user_id,
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    return clone


def apply_template_to_meeting_data(
    template: MeetingTemplate,
    meeting_data: dict,
    participant_ids: Optional[list] = None,
    title: Optional[str] = None,
) -> dict:
    """将模板字段填入会议数据"""
    data = dict(meeting_data)
    if template.title_template and not data.get("title"):
        rendered = template.title_template.format(
            date=datetime.now().strftime("%Y-%m-%d"),
            project_name="新项目",
        )
        data["title"] = title or rendered
    if template.description and not data.get("description"):
        data["description"] = template.description
    if template.agenda and not data.get("agenda"):
        data["agenda"] = template.agenda
    if template.default_duration_minutes and not data.get("end_time"):
        start = data.get("start_time")
        if start:
            data["end_time"] = start + timedelta(minutes=template.default_duration_minutes)
    if participant_ids is None and template.default_participant_ids:
        data["participant_ids"] = template.default_participant_ids
    elif participant_ids is not None:
        data["participant_ids"] = participant_ids
    if template.default_location and not data.get("location"):
        data["location"] = template.default_location
    return data
