"""149: 恢复 ``meetings`` 主键 + 指向它的三个外键 (幂等, 可重放, fail-loud)

**Revision ID**: 149_meetings_pk_fk
**Revises**: 148_cluster_adjudications
**Create Date**: 2026-10-31

背景 (类 20.256, 主指挥 2026-10-31 拍板)
--------------------------------------
生产库曾在一次 ``pg_dump --data-only`` 的恢复中丢掉全部 schema 约束 —— 实测
188 张表只有 7 张有主键, 且恰好全是近期由 alembic 建的; 其余 181 张表 (含
``meetings``) **有数据无约束**。``meetings`` 无主键 ⇒ PG 拒绝为引用它的外键建
约束 ⇒ 148 号迁移当时建不了 FK (其 docstring 记录了该原因)。

主指挥拍板的范围: **只补 ``meetings`` 一张 + 恢复指向它的三个外键**,
其余 180+ 张表一律不动 (那是 187 表级别的动作, 另行立项)。
补约束必须落在迁移链里 —— 手工 ALTER 活不过下一次 fixture 重建
(``scripts/dump_prod_to_fixture.sh`` 用 ``--data-only``, 重建即丢约束)。

前置断言 (fail-loud, 不静默跳过)
--------------------------------
- ``meetings.id`` 有重复或 NULL ⇒ **raise** (主键加不上; 静默跳过会留下假成功)。
- 任一引用表存在孤儿行 (``meeting_id`` 指向不存在的会议) ⇒ **raise 并列出孤儿**,
  **谁也不许在迁移里默默删数据** (孤儿定性是主指挥的裁决, 不是迁移的)。
  实测前置状态: participants 104 行 / 段级裁决 406 行 / 簇级裁决 0 行, 孤儿均 0。

幂等性
------
每一步先查 ``pg_constraint`` / ``pg_indexes``, 已存在则跳过 ⇒ 可重放。

级联语义 (主指挥问过, 理由在此写明)
----------------------------------
- ``meeting_participants`` → **CASCADE**: 参会者名单是会议的附属数据,
  会议删除后没有独立价值; ORM 语义本来就是级联 (``app/models/meeting.py:111``)。
- ``meeting_speaker_adjudications`` / ``meeting_cluster_adjudications`` → **RESTRICT**:
  裁决是人工听辨的**不可再生成果** (逐段听辨以小时计, 删了就得重听;
  类 20.244 记过"重标会把刚修好的 bug 装回去"的同型风险) —— 误删会议不应
  连带销毁裁决。合法删除路径 (``app/api/v1/meeting.py``) 已在删会议前**显式**
  清这两表 ⇒ RESTRICT 只拦"没走正常路径的意外删除"。
  ⚠️ 146 号迁移当初把段级裁决建成 CASCADE; 149 改为 RESTRICT 是主指挥
  2026-10-31 的裁定, 模型侧已同步 (测试库 create_all 与生产一致)。

``meeting_processing_runs`` **故意不加 FK**: 实测有 1 条孤儿 (run 72 →
meeting 260, 2026-10-26 initial 处理中会议被删, run 已 error 终态) —— 该残留
该不该删属主指挥裁决; 定性前不给这张表加约束。

回滚
----
``downgrade()`` 逐项反向 (全部带存在性守卫); 独立 SQL 见
``scripts/db/rollback_149_meetings_pk_fk.sql``。
执行前 schema 备份: ``data/backups/pre149_schema_20261031.sql``;
前置约束快照: ``data/backups/pre149_state_20261031.json``。

⚠️ revision id 17 字符 ≤ 32 (CI 的 alembic_version.version_num 是 VARCHAR(32), 类 20.227)。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "149_meetings_pk_fk"
down_revision: Union[str, None] = "148_cluster_adjudications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: (表, 约束名, ondelete) —— 顺序即创建顺序
_FKS = [
    ("meeting_participants", "fk_mpt_meeting", "CASCADE"),
    ("meeting_speaker_adjudications", "fk_msa_meeting", "RESTRICT"),
    ("meeting_cluster_adjudications", "fk_mca_meeting", "RESTRICT"),
]

#: 模型侧声明、生产库因 --data-only 丢失的索引 (149 顺带补回)
_INDEXES = [
    ("meeting_speaker_adjudications", "ix_meeting_speaker_adjudications_meeting_id",
     ["meeting_id"]),
    ("meeting_speaker_adjudications", "idx_msa_meeting_start",
     ["meeting_id", "seg_start"]),
]


def _assert_meetings_id_integrity(conn) -> None:
    row = conn.execute(sa.text(
        "SELECT count(*) AS total, count(DISTINCT id) AS distinct_ids, "
        "count(*) FILTER (WHERE id IS NULL) AS null_ids FROM meetings")).one()
    dups = row.total - row.distinct_ids
    if dups or row.null_ids:
        raise RuntimeError(
            "meetings.id 不满足主键前置条件: 重复=%d NULL=%d (共 %d 行) "
            "⇒ 拒绝加主键, 请先人工定性" % (dups, row.null_ids, row.total))


def _assert_no_orphans(conn, table: str) -> None:
    rows = conn.execute(sa.text(
        "SELECT id, meeting_id FROM {t} WHERE meeting_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM meetings m WHERE m.id = {t}.meeting_id) "
        "ORDER BY id".format(t=table))).fetchall()
    if rows:
        detail = ", ".join("(id=%s meeting_id=%s)" % (r.id, r.meeting_id) for r in rows[:20])
        raise RuntimeError(
            "%s 存在 %d 条孤儿行 (meeting_id 指向不存在的会议): %s%s ⇒ 拒绝加外键; "
            "孤儿定性属主指挥裁决, 不要在迁移里删" % (
                table, len(rows), detail, " ..." if len(rows) > 20 else ""))


def _has_pk(conn, table: str) -> bool:
    return bool(conn.execute(sa.text(
        "SELECT 1 FROM pg_constraint WHERE conrelid = to_regclass(:t) "
        "AND contype = 'p' LIMIT 1"), {"t": table}).scalar())


def _has_fk(conn, table: str, name: str) -> bool:
    return bool(conn.execute(sa.text(
        "SELECT 1 FROM pg_constraint WHERE conrelid = to_regclass(:t) "
        "AND conname = :n AND contype = 'f' LIMIT 1"), {"t": table, "n": name}).scalar())


def _has_index(conn, table: str, name: str) -> bool:
    return bool(conn.execute(sa.text(
        "SELECT 1 FROM pg_indexes WHERE tablename = :t AND indexname = :n LIMIT 1"),
        {"t": table, "n": name}).scalar())


def upgrade() -> None:
    conn = op.get_bind()
    _assert_meetings_id_integrity(conn)

    if not _has_pk(conn, "meetings"):
        op.execute("ALTER TABLE meetings ADD CONSTRAINT meetings_pkey PRIMARY KEY (id)")

    for table, name, ondelete in _FKS:
        _assert_no_orphans(conn, table)
        if not _has_fk(conn, table, name):
            op.create_foreign_key(name, table, "meetings", ["meeting_id"], ["id"],
                                  ondelete=ondelete)

    for table, name, cols in _INDEXES:
        if not _has_index(conn, table, name):
            op.create_index(name, table, cols)


def downgrade() -> None:
    conn = op.get_bind()
    # 反向顺序: 先索引, 再外键, 最后主键 (全部带存在性守卫 ⇒ 幂等)
    for table, name, _cols in reversed(_INDEXES):
        if _has_index(conn, table, name):
            op.drop_index(name, table_name=table)
    for table, name, _ondelete in reversed(_FKS):
        if _has_fk(conn, table, name):
            op.drop_constraint(name, table, type_="foreignkey")
    if _has_pk(conn, "meetings"):
        op.execute("ALTER TABLE meetings DROP CONSTRAINT meetings_pkey")
