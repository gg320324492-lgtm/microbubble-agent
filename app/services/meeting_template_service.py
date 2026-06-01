"""会议模板服务"""
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting_template import MeetingTemplate


async def list_templates(db: AsyncSession, include_inactive: bool = False) -> List[MeetingTemplate]:
    """列出所有模板（默认仅 active）"""
    stmt = select(MeetingTemplate).order_by(
        MeetingTemplate.is_builtin.desc(), MeetingTemplate.name
    )
    if not include_inactive:
        stmt = stmt.where(MeetingTemplate.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    return list(result.scalars().all())


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
    """更新模板（is_builtin=True 只允许改 is_active）"""
    template = await db.get(MeetingTemplate, template_id)
    if not template:
        return None
    if template.is_builtin:
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
