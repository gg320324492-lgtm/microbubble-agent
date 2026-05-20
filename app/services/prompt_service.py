"""提示词模板服务"""

import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_template import PromptTemplate

logger = logging.getLogger("microbubble.prompt")


class PromptTemplateService:
    """提示词模板管理服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_template(self, name: str = "default") -> Optional[str]:
        """获取指定名称的活跃模板内容"""
        result = await self.db.execute(
            select(PromptTemplate).where(
                PromptTemplate.name == name,
                PromptTemplate.is_active == True
            )
        )
        template = result.scalar_one_or_none()
        return template.template if template else None

    async def save_template(self, name: str, template: str, created_by: int) -> PromptTemplate:
        """保存模板（如果同名模板存在则更新版本）"""
        result = await self.db.execute(
            select(PromptTemplate).where(PromptTemplate.name == name)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.template = template
            existing.version = (existing.version or 1) + 1
            existing.created_by = created_by
            existing.is_active = True
            await self.db.commit()
            await self.db.refresh(existing)
            logger.info(f"更新提示词模板: {name} v{existing.version}")
            return existing
        else:
            new_template = PromptTemplate(
                name=name,
                template=template,
                created_by=created_by,
                is_active=True,
                version=1,
            )
            self.db.add(new_template)
            await self.db.commit()
            await self.db.refresh(new_template)
            logger.info(f"创建提示词模板: {name}")
            return new_template

    async def list_templates(self):
        """列出所有模板"""
        result = await self.db.execute(
            select(PromptTemplate).order_by(PromptTemplate.name)
        )
        return result.scalars().all()

    async def deactivate_template(self, name: str) -> bool:
        """停用指定模板"""
        result = await self.db.execute(
            select(PromptTemplate).where(PromptTemplate.name == name)
        )
        template = result.scalar_one_or_none()
        if template:
            template.is_active = False
            await self.db.commit()
            return True
        return False
