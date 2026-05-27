"""种子数据服务 — 内置公式库幂等初始化"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.formula_category import FormulaCategory
from app.models.knowledge_formula import KnowledgeFormula
from app.seed.formula_library import CATEGORIES, FORMULA_LIBRARY

logger = logging.getLogger("microbubble.seeder")


async def seed_formula_library(db: AsyncSession):
    """幂等初始化内置公式库。仅在首次运行时插入数据。"""
    # 检查是否已初始化
    result = await db.execute(select(func.count(FormulaCategory.id)))
    category_count = result.scalar() or 0
    if category_count > 0:
        return

    logger.info("开始初始化内置公式库...")

    # 1. 插入分类
    name_to_id = {}
    # 先插入顶层分类
    for cat in CATEGORIES:
        if cat["parent"] is None:
            obj = FormulaCategory(
                name=cat["name"],
                display_name=cat["display_name"],
                description=cat["description"],
                icon=cat["icon"],
                sort_order=cat["sort"],
            )
            db.add(obj)
            await db.flush()
            name_to_id[cat["name"]] = obj.id

    # 再插入子分类
    for cat in CATEGORIES:
        if cat["parent"] is not None:
            obj = FormulaCategory(
                name=cat["name"],
                display_name=cat["display_name"],
                description=cat["description"],
                icon=cat["icon"],
                parent_id=name_to_id.get(cat["parent"]),
                sort_order=cat["sort"],
            )
            db.add(obj)
            await db.flush()
            name_to_id[cat["name"]] = obj.id

    # 2. 插入内置公式
    for f_data in FORMULA_LIBRARY:
        formula = KnowledgeFormula(
            knowledge_id=None,
            name=f_data["name"],
            formula_latex=f_data["formula_latex"],
            formula_python=f_data["formula_python"],
            variables=f_data["variables"],
            result_unit=f_data["result_unit"],
            conditions=f_data.get("conditions", ""),
            domain=f_data.get("category_name", ""),
            confidence=0.9,
            source_type="builtin",
            category_id=name_to_id.get(f_data["category_name"]),
            is_active=True,
        )
        db.add(formula)

    await db.commit()
    logger.info(f"内置公式库初始化完成: {len(CATEGORIES)} 分类, {len(FORMULA_LIBRARY)} 公式")
