"""knowledge.file_request_id — 外部收件归属到文件请求

Revision ID: 152_knowledge_file_request_id
Revises: 151_file_requests_ts_default

背景 (2026-11-10, 主指挥要求「文件请求点进去能看收到的文件」):
- 收件落盘时只在 content 里写 `[file_request] token=xxxxxxxx*** uploader=...`,
  没有可查询的外键 ⇒ 前端无法可靠列出"这个请求收到了哪些文件"。
- content 是给人看的归属标记, 不是数据关联 (类 20.225: 注释里谈论 X ≠ 用 X);
  改文案、去掉标记、或同名 token 前缀即失效。
- 本迁移落一个**真列** + 索引 + FK (ON DELETE SET NULL), 并把存量行按
  `[file_request] token=<前8位>***` 回填 (只在唯一命中时回填, 有歧义的行保持 NULL)。

幂等性: 列已存在则跳过 add_column; 索引/FK 同理 (inspector 判断)。
"""
from alembic import op
import sqlalchemy as sa

revision = "152_knowledge_file_request_id"
down_revision = "151_file_requests_ts_default"
branch_labels = None
depends_on = None


def _has_column(conn, table: str, column: str) -> bool:
    insp = sa.inspect(conn)
    return any(c["name"] == column for c in insp.get_columns(table))


def _has_index(conn, table: str, index: str) -> bool:
    insp = sa.inspect(conn)
    return any(i["name"] == index for i in insp.get_indexes(table))


def _has_fk(conn, table: str, name: str) -> bool:
    insp = sa.inspect(conn)
    return any(fk.get("name") == name for fk in insp.get_foreign_keys(table))


def upgrade() -> None:
    conn = op.get_bind()

    if not _has_column(conn, "knowledge", "file_request_id"):
        op.add_column("knowledge", sa.Column("file_request_id", sa.Integer(), nullable=True))

    if not _has_index(conn, "knowledge", "ix_knowledge_file_request_id"):
        op.create_index(
            "ix_knowledge_file_request_id", "knowledge", ["file_request_id"]
        )

    if not _has_fk(conn, "knowledge", "fk_knowledge_file_request_id"):
        # file_requests 的 PK 由 150 保证 (该类 20.256 的约束普查已做)
        op.create_foreign_key(
            "fk_knowledge_file_request_id",
            "knowledge",
            "file_requests",
            ["file_request_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # 存量回填: content 标记里的 token 前 8 位匹配; 仅当该前缀只对应**一个**请求时回填,
    # 前缀有歧义 (理论上 8 hex 碰撞) 就保持 NULL —— 宁可少关联, 不要关联错 (类 20.242 ②)。
    conn.execute(
        sa.text(
            """
            WITH pref AS (
                SELECT LEFT(token, 8) AS p, MIN(id) AS rid, COUNT(*) AS n
                FROM file_requests
                GROUP BY LEFT(token, 8)
            )
            UPDATE knowledge k
            SET file_request_id = pref.rid
            FROM pref
            WHERE pref.n = 1
              AND k.file_request_id IS NULL
              AND k.storage_mode = 'drive'
              AND k.content LIKE ('[file_request] token=' || pref.p || '***%')
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    if _has_fk(conn, "knowledge", "fk_knowledge_file_request_id"):
        op.drop_constraint("fk_knowledge_file_request_id", "knowledge", type_="foreignkey")
    if _has_index(conn, "knowledge", "ix_knowledge_file_request_id"):
        op.drop_index("ix_knowledge_file_request_id", table_name="knowledge")
    if _has_column(conn, "knowledge", "file_request_id"):
        op.drop_column("knowledge", "file_request_id")
