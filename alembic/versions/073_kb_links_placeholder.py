"""W68 第 10 批 B-4: kb_links 表 (2026-07-24) — 072 后续迁移

## 背景

072 迁移已包含 kb_closed_loop_log + kb_links 两张表 (同 migration 部署).
本迁移 073 是**占位后续迁移**, 给 W69/W70 后续派工用 (例如增加 kb_links 索引 / 分区 /
或 KB 闭环 dashboard 配套表). 当前仅占位 + 接续 alembic 链, 不增加实际 schema.

## 占位原因

- W68 第 10 批 B-4 实际只在 072 加了 2 张表, 073 留作**未来扩展点**
- 不为空迁移加 placeholder (避免 alembic 空操作噪声)
- 但 071 提到的 B-3 knowledge_rejected_retry 还没派工, 073 顺位占位避免未来串单链断裂

## 下接

- W69 第 1 批: 接 073 加 kb_links 分区 / 索引 / 抽检 dashboard 配套表
- W69 第 2 批: 接 074 加 KB 闭环审计 dashboard 持久化

## 实施纪律

- 0 production code 改动铁律 (W68 第 10 批): 占位迁移, 不动老路径
- W68 第 3 批串单链纪律: down_revision 接 072_kb_closed_loop (B-4 本体), 串单链
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "073_kb_links_placeholder"
down_revision: Union[str, None] = "072_kb_closed_loop"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # 占位: 不增加 schema, 仅 alembic 链占位
    # W69 第 1 批如果需要给 kb_links 加 GIN 索引 / 分区 / 配套表, 在这里实施
    pass


def downgrade() -> None:
    # 占位: 无 schema 可降级
    pass