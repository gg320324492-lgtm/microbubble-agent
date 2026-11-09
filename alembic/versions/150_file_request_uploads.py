"""150: 外部收件的大文件分片上传 (新表 + FileRequest 安全闸列)

**Revision ID**: 150_file_request_uploads
**Revises**: 149_meetings_pk_fk
**Create Date**: 2026-11-09

背景
----
主指挥需求: 外部人员（**无账号、不应看到团队任何数据**）上传 10GB 级视频，画质无损。
取证结论（详见 CLAUDE.md 类 20.242 同族的"状态字段说谎"纪律）:

- "无损"本来就成立 —— drive 通路是纯字节拼接, 全链路无转码, 唯一 ffmpeg 是抽首帧
  生成独立的缩略图对象, 不改写源文件。
- 10GB **传不进去**, 卡在: 三处各硬编码的 2 GiB 闸、`total_chunks ≤ 2000`
  (5 MiB × 2000 = 9.77 GiB)、FileRequest 的 500 MB 单请求闸、成员配额默认刚好
  10 GiB、以及**合并阶段把整份文件读进 Python 内存** (app 容器 mem_limit=8g ⇒ OOMKill)。

本迁移只解决两件必须由 schema 承载的事:

1. **``file_request_uploads`` 新表** —— 匿名分片会话。
   不复用 ``drive_chunked_uploads`` 的理由 (写在模型 docstring 里, 此处摘要):
   ① 那张表的 ``user_id`` 是 ``members.id`` 的 NOT NULL 外键, 而外部收件人没有账号,
      塞 created_by 进去会抹掉"谁在传"这个事实;
   ② 生命周期不同 (本表随 FileRequest CASCADE);
   ③ 安全闸不同 (受请求级三重闸约束)。
   ⚠️ 表里**只**存会话元数据与片号, 字节在 MinIO staging 前缀; 合并走服务端
   ``compose_object``, Python 侧 0 内存 —— 这是 10GB 可行的根因。

2. **``file_requests`` 加四道闸** —— 现状 FileRequest 只有一个自增的
   ``submission_count``, **没有**提交次数上限、**没有**累计总量上限、
   扩展名白名单未配即不限。匿名 token 一旦外泄 = 任何人可无限灌本机磁盘,
   所以这三道闸是本次的**前置条件**, 不是后续优化。

   列语义:
   - ``max_submissions``     最多提交几个文件 (NULL = 不限, 但创建端点默认给 5)
   - ``max_total_bytes``     本请求累计占盘上限 (NULL = 不限, 默认给 30 GiB)
   - ``used_bytes``           已落地字节累计 (完成时 +, 失败/删除不回冲 —— 见下)
   - ``auto_close_on_limit`` 达到 max_submissions 后自动 is_active=false

``used_bytes`` 为什么不回冲
--------------------------
回冲要在删除路径上再做一套记账, 而"回冲后又能继续灌"正总量闸想防的事;
收件链接本来就是一次性的（72h 默认），保守计**已用掉的盘**比"当前净占盘"更合适。
显式说明以免后来者当 bug 修。

幂等性
------
建表 / 加列 / 建索引都先查 ``sa.inspect(bind)``, 已存在则跳过 ⇒ 可重放。
(生产曾因 ``pg_dump --data-only`` 恢复丢掉 schema, 幂等是硬要求 —— 见 149 的教训。)

fail-loud
---------
若 ``file_requests`` 表不存在 ⇒ raise, 不静默跳过 (静默会让"迁移成功"与"闸生效"脱钩)。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "150_file_request_uploads"
down_revision: Union[str, None] = "149_meetings_pk_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE = "file_request_uploads"

#: (列名, DDL 片段) —— file_requests 上的四道闸
_REQUEST_COLUMNS = [
    ("max_submissions", "INTEGER"),
    ("max_total_bytes", "BIGINT"),
    ("used_bytes", "BIGINT NOT NULL DEFAULT 0"),
    ("auto_close_on_limit", "BOOLEAN NOT NULL DEFAULT true"),
]


def _existing_columns(insp, table: str) -> set:
    if not insp.has_table(table):
        return set()
    return {c["name"] for c in insp.get_columns(table)}


#: 本迁移新建表 FK 引用的父表 —— 生产库因 pg_dump --data-only 恢复丢过全部约束
#  (类 20.256: 188 表仅 7 张有 PK)。FK 需要被引用列有 PK/唯一约束, 否则
#  PG 报 "no unique constraint matching given keys" —— 149 给 meetings 补 PK
#  正是同一批问题, 当时只补了 meetings, file_requests 与 knowledge 仍裸奔。
#  ⇒ 必须先给这两张父表补 PK, 才能建 file_request_uploads。
_PARENT_TABLES_NEEDING_PK = ("file_requests", "knowledge")


def _assert_id_integrity(conn, table: str) -> None:
    """加 PK 的前置断言: id 无重复、无 NULL —— **fail-loud, 不静默跳过**。
    静默跳过会留下"迁移成功但 FK 建不上、app 启动 create_all 崩溃"的假状态
    (类 20.220)。"""
    row = conn.execute(sa.text(
        "SELECT count(*) AS total, count(DISTINCT id) AS dist, "
        "count(*) FILTER (WHERE id IS NULL) AS nulls FROM {t}".format(t=table)
    )).one()
    dups = row.total - row.dist
    if dups or row.nulls:
        raise RuntimeError(
            "%s.id 不满足主键前置条件: 重复=%d NULL=%d (共 %d 行) "
            "⇒ 拒绝加 PK, 请先人工定性 (绝不在迁移里默默删行)" % (
                table, dups, row.nulls, row.total)
        )


def _ensure_pk(conn, table: str) -> None:
    """给 table.id 补主键, 幂等: 已有 PK 就跳过。"""
    has_pk = conn.execute(sa.text(
        "SELECT 1 FROM pg_constraint WHERE conrelid = '{t}'::regclass "
        "AND contype = 'p'".format(t=table)
    )).first()
    if has_pk:
        return
    _assert_id_integrity(conn, table)
    conn.execute(sa.text(
        'ALTER TABLE {t} ADD CONSTRAINT pk_{t} PRIMARY KEY (id)'.format(t=table)
    ))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("file_requests"):
        raise RuntimeError(
            "file_requests 表不存在 ⇒ 拒绝执行 150。"
            "该表由 048_drive_requests_audit 建立, 缺失说明迁移链不完整, "
            "静默跳过会留下'迁移成功但安全闸没生效'的假状态。"
        )

    # ── 0. 先补两张父表的 PK, 否则下面的 FK 建不上 (类 20.256) ──────────────
    for parent in _PARENT_TABLES_NEEDING_PK:
        if not insp.has_table(parent):
            raise RuntimeError(
                "被引用父表 %s 不存在 ⇒ 拒绝执行 150 (FK 无目标, 静默建表只会"
                "留下没有外键约束的孤儿表)。" % parent
            )
        _ensure_pk(bind, parent)
    insp = sa.inspect(bind)  # 补完 PK 重新获取

    # ── 1. 会话表 ────────────────────────────────────────────────────────────
    if not insp.has_table(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("upload_id", sa.String(length=64), nullable=False),
            sa.Column("request_id", sa.Integer(), nullable=False),
            sa.Column("uploader_name", sa.String(length=200), nullable=True),
            sa.Column("filename", sa.String(length=500), nullable=False),
            sa.Column("file_size", sa.BigInteger(), nullable=False),
            sa.Column("chunk_size", sa.Integer(), nullable=False),
            sa.Column("total_chunks", sa.Integer(), nullable=False),
            sa.Column(
                "uploaded_chunks",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            ),
            sa.Column("checksum", sa.String(length=64), nullable=True),
            sa.Column("verified_sha256", sa.String(length=64), nullable=True),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("knowledge_id", sa.Integer(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column(
                "created_at", sa.DateTime(), nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at", sa.DateTime(), nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["request_id"], ["file_requests.id"],
                name="fk_fr_uploads_request", ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["knowledge_id"], ["knowledge.id"],
                name="fk_fr_uploads_knowledge", ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_file_request_uploads"),
            sa.UniqueConstraint("upload_id", name="uq_file_request_uploads_upload_id"),
            sa.CheckConstraint(
                "file_size > 0", name="ck_file_request_uploads_file_size"),
            sa.CheckConstraint(
                "chunk_size > 0", name="ck_file_request_uploads_chunk_size"),
            sa.CheckConstraint(
                "total_chunks >= 1 AND total_chunks <= 10000",
                name="ck_file_request_uploads_total_chunks"),
            sa.CheckConstraint(
                "status IN ('pending','uploading','completed','aborted','expired')",
                name="ck_file_request_uploads_status"),
        )
        insp = sa.inspect(bind)  # 重新获取, 下面建索引要认这张新表

    # ── 2. FileRequest 的三道闸 + 记账列 ─────────────────────────────────────
    have = _existing_columns(insp, "file_requests")
    for name, ddl in _REQUEST_COLUMNS:
        if name in have:
            continue
        op.execute(sa.text(f'ALTER TABLE file_requests ADD COLUMN "{name}" {ddl}'))

    # ── 3. 索引 ──────────────────────────────────────────────────────────────
    idx_have = {i["name"] for i in insp.get_indexes(_TABLE)}
    _INDEXES = [
        ("ix_file_request_uploads_request_id", ["request_id"]),
        ("ix_file_request_uploads_status", ["status"]),
        ("ix_file_request_uploads_expires_at", ["expires_at"]),
    ]
    for name, cols in _INDEXES:
        if name in idx_have:
            continue
        op.create_index(name, _TABLE, cols, unique=False)
    # upload_id 唯一性由表级 UniqueConstraint 保证; PG 会为它建唯一索引,
    # 不再重复建 —— 但**显式确认它存在**, 否则匿名侧可枚举。
    _uniq = {
        c["name"] for c in sa.inspect(bind).get_unique_constraints(_TABLE)
    }
    if not any("upload_id" in (c or "") for c in _uniq):
        # 唯一约束名可能不同, 用索引层再核一遍
        _all_idx = sa.inspect(bind).get_indexes(_TABLE)
        covered = any(
            i.get("unique") and i.get("column_names") == ["upload_id"]
            for i in _all_idx
        )
        if not covered:
            op.create_index(
                "ix_file_request_uploads_upload_id_uniq",
                _TABLE, ["upload_id"], unique=True,
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table(_TABLE):
        for name in (
            "ix_file_request_uploads_expires_at",
            "ix_file_request_uploads_status",
            "ix_file_request_uploads_request_id",
            "ix_file_request_uploads_upload_id_uniq",
        ):
            if name in {i["name"] for i in insp.get_indexes(_TABLE)}:
                op.drop_index(name, table_name=_TABLE)
        op.drop_table(_TABLE)

    have = _existing_columns(insp, "file_requests")
    for name, _ddl in reversed(_REQUEST_COLUMNS):
        if name not in have:
            continue
        op.execute(sa.text(f'ALTER TABLE file_requests DROP COLUMN "{name}"'))
