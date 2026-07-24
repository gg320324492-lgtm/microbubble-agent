"""v2 PR10: drive_documents + drive_doc_op_logs 表 (2026-07-24, W68 第 5 批骨架)

背景:
- Drive v2 PR9 已实现 drive_file_versions (顺序版本历史) + drive_comments (评论 thread)
- 本 PR 启动 CRDT 协同编辑骨架 (PR8g 落地第一步), W68 第 5 批仅调研 + 空表, **不**实施 WS
- Yjs 系 CRDT 用二进制 state vector 存最新 Y.Doc, 客户端连接时反序列化

设计:
- 2 张新表 (同 migration):
  * drive_documents: 文件 ↔ Y.Doc 状态 (1:1, file_id UNIQUE)
    - ydoc_state: LargeBinary, Y.Doc 字节快照 (pycrdt.Doc.get_state() 输出)
    - ops_count: 累计应用 op 数
    - version_number: save_version 计数器 (与 drive_file_versions.version_number 解耦)
    - active_users: 实时房间人数 (best-effort, 30s 刷盘)
  * drive_doc_op_logs: 增量 op 日志 (1:N, 用于审计 / 撤销 / 崩溃恢复)
    - op: LargeBinary, 单次 Yjs update 字节
    - client_id: 发起 op 的 Yjs client_id (uint32, 存 BIGINT 兼容)
    - user_id: 操作者 (FK to members)
    - 7 天后由 Celery compress_op_logs_task 合并到 ydoc_state 后删除

依赖: knowledge 表必须存在 (FK), drive_file_versions (063) 已存在 (无强依赖, 仅逻辑引用)
下接: PR10 WS 端点 (W69) + Redis pub/sub (W70) + 编辑器集成 (W71)

回滚策略: 直接 DROP TABLE (无外部 FK 引用, 无其他 alembic 引用本 migration)

实施纪律:
- 0 production code 改动铁律 (W68 第 5 批): 本表暂不部署, 仅作 schema 备案
- W69 派工时必须明确 down_revision 接续 (W68 第 3 批 062/063 双头事故教训, CLAUDE.md 已沉淀)
- 1:N 关系, file_id 上加 UNIQUE 约束 (1 个文件最多 1 个 Y.Doc)
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "064_drive_documents"
down_revision: Union[str, None] = "063_drive_file_versions"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # ===== drive_documents =====
    op.create_table(
        "drive_documents",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "file_id",
            sa.Integer(),
            sa.ForeignKey("knowledge.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            comment="Knowledge.id — 1:1 关系, UNIQUE 约束保证 1 文件最多 1 个 Y.Doc",
        ),
        sa.Column(
            "ydoc_state",
            sa.LargeBinary(),
            nullable=False,
            server_default=sa.text("''::bytea"),
            comment="Y.Doc 二进制 state vector (pycrdt.Doc.get_state() 输出, 0 字节 = 空 doc)",
        ),
        sa.Column(
            "ops_count",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="累计应用 op 数 (用于 UI 展示 '已编辑 N 次')",
        ),
        sa.Column(
            "version_number",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="save_version 计数器 (与 drive_file_versions.version_number 解耦)",
        ),
        sa.Column(
            "active_users",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="实时房间人数 (best-effort, collab-gateway 30s 周期刷盘)",
        ),
        sa.Column(
            "last_edited_by",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="SET NULL"),
            nullable=True,
            comment="最近编辑者 member.id",
        ),
        sa.Column(
            "last_edited_at",
            sa.DateTime(),
            nullable=True,
            comment="最近编辑时间",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # 索引: file_id UNIQUE 已由 unique=True 创建
    # 索引: last_edited_by 单列 — 按编辑者查询
    op.create_index(
        "ix_drive_documents_last_edited_by",
        "drive_documents",
        ["last_edited_by"],
        unique=False,
    )

    # ===== drive_doc_op_logs =====
    op.create_table(
        "drive_doc_op_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, index=True),
        sa.Column(
            "file_id",
            sa.Integer(),
            sa.ForeignKey("knowledge.id", ondelete="CASCADE"),
            nullable=False,
            comment="Knowledge.id — N:1 关系",
        ),
        sa.Column(
            "op",
            sa.LargeBinary(),
            nullable=False,
            comment="单次 Yjs update 字节 (典型 5-200 字节)",
        ),
        sa.Column(
            "client_id",
            sa.BigInteger(),
            nullable=False,
            comment="发起 op 的 Yjs client_id (uint32, 存 BIGINT 兼容)",
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="SET NULL"),
            nullable=True,
            comment="操作者 member.id (nullable: 匿名 / system flush)",
        ),
        sa.Column(
            "applied_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # 索引: (file_id, applied_at) 复合 — 增量同步 + 7 天压缩
    op.create_index(
        "ix_drive_doc_op_logs_file_time",
        "drive_doc_op_logs",
        ["file_id", "applied_at"],
        unique=False,
    )
    # 索引: user_id 单列 — 按用户查
    op.create_index(
        "ix_drive_doc_op_logs_user",
        "drive_doc_op_logs",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_drive_doc_op_logs_user", table_name="drive_doc_op_logs")
    op.drop_index("ix_drive_doc_op_logs_file_time", table_name="drive_doc_op_logs")
    op.drop_table("drive_doc_op_logs")

    op.drop_index("ix_drive_documents_last_edited_by", table_name="drive_documents")
    op.drop_table("drive_documents")
