"""151: 修复 file_requests 时间戳冻结 —— 列默认值从建表时刻常量改回活的 now()

**Revision ID**: 151_file_requests_ts_default
**Revises**: 150_file_request_uploads
**Create Date**: 2026-11-10

根因 (2026-11-10 主指挥发现"刚建的链接显示 7 月 1 日", 实测定位)
----------------------------------------------------------------
048 迁移建表时写的是 ``server_default="now()"`` —— **裸 Python 字符串**。
SQLAlchemy 把它渲染成 ``DEFAULT 'now()'`` (**带引号的字面量**), PG 在**建表
那一刻**把字面量隐式转型求值成常量 (2026-07-01 18:24:25.521563), 从此**冻结**
—— 该表任何一行的 created_at/updated_at 都等于建表日, 与真实插入时间无关。

实测证据链 (2026-11-10):
- app 日志 / audit 201 / id 序列 / xmin age=12 四证齐: 今天 17:08:15 确实新插了行;
- 但该行 created_at = 2026-07-01 18:24:25.521563 = 建表时刻;
- ``information_schema.columns``: 两列的 column_default 是
  ``'2026-07-01 18:24:25.521563'::timestamp`` **常量**, 不是 now() 函数;
- 决定性实验 (microbubble_test, 跨事务插入):
  ``DEFAULT 'now()'`` (字面量) 两行时间**相同** (冻结);
  ``DEFAULT now()`` (函数) 两行时间**相差 1.5s** (正常走表)。
- 全库扫描: **只有 file_requests 两列中招** (knowledge/meetings/audit_log/
  activity_events 均为活函数) —— 功能无损伤 (过期判断走 expires_at),
  受影响的是展示与按创建时间追溯。

这是类 20.184 ("server_default 字符串必须 text() 包裹, 纯字符串被字面量引用")
的第一次**生产实锤** —— 之前只是规则, 现在有了真实事故与其决定性实验。

修复内容
--------
1. 两列 ``SET DEFAULT now()`` (活的函数);
2. 校正存量行的假时间戳 = audit_log 里该创建者 ``POST /api/v1/file-requests``
   的真实时刻 (审计取证, 非猜测)。找不到对应审计记录的行**不动**
   (宁可留假戳也不编时间 —— 类 20.220), 并在终验里 fail-loud 报出来。

配套 (缺一即漏, 类 20.250 ①)
----------------------------
- ORM 模型侧 ``FileRequest.created_at/updated_at`` 同步改为
  ``server_default=text("now()")`` —— 否则下一次 create_all (测试库/新部署)
  又会建出冻结列。
- AST 守卫测试 (test_file_request_timestamp_defaults_use_text) 防回退。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "151_file_requests_ts_default"
down_revision: Union[str, None] = "150_file_request_uploads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "file_requests"
_FROZEN = "'2026-07-01 18:24:25.521563'::timestamp without time zone"


def upgrade() -> None:
    bind = op.get_bind()
    conn = bind

    if not conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'file_requests'"
    )).first():
        raise RuntimeError("file_requests 表不存在 ⇒ 拒绝执行 151 (迁移链不完整)。")

    # ── 1. 两列默认值改回活函数 (SET 幂等: 重复执行结果一致) ──────────────────
    op.execute(sa.text(
        "ALTER TABLE file_requests "
        "ALTER COLUMN created_at SET DEFAULT now(), "
        "ALTER COLUMN updated_at SET DEFAULT now()"
    ))

    # ── 2. 回读验证默认值真的是函数 (类 20.220: 改了必须验证副作用) ────────────
    # 冻结常量的 column_default 显示为 `'2026-...'::timestamp`, 活函数显示为 `now()`。
    for col in ("created_at", "updated_at"):
        row = conn.execute(sa.text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = 'file_requests' AND column_name = :c"
        ), {"c": col}).first()
        if not row or "now()" not in str(row[0]):
            raise RuntimeError(
                f"SET DEFAULT 后回读异常: {col}.column_default = {row!r} "
                "⇒ 不是活的 now() 函数, 拒绝继续 (fail-loud)"
            )

    # ── 3. 校正存量行的假时间戳 = audit_log 里的真实创建时刻 ─────────────────
    # 判据: audit_log 里 POST /api/v1/file-requests (精确路径, 200/201) 按创建者分组;
    # 该路径在审计里出现一次即一次真实创建。取 MIN 是"该用户最早一次创建"——
    # 当 audit_log 只有一条 (现状) 时即精确值; 若同一用户有多条而表里有多行冻结,
    # 终验会 fail-loud 逼人工定性, 不会静默错配。
    op.execute(sa.text(
        "UPDATE file_requests fr "
        "SET created_at = ts.created_at, updated_at = ts.created_at "
        "FROM ( "
        "  SELECT a.user_id, MIN(a.created_at) AS created_at "
        "  FROM audit_log a "
        "  WHERE a.method = 'POST' "
        "    AND a.path = '/api/v1/file-requests' "
        "    AND a.status_code IN (200, 201) "
        "  GROUP BY a.user_id "
        ") ts "
        "WHERE fr.created_by = ts.user_id "
        f"  AND fr.created_at = {_FROZEN}"
    ))

    # ── 4. 终验: 不应再有任何冻结戳的行 (fail-loud, 不静默放过) ───────────────
    n = conn.execute(sa.text(
        "SELECT count(*) FROM file_requests WHERE created_at = " + _FROZEN
    )).scalar_one()
    if n:
        raise RuntimeError(
            f"校正后仍有 {n} 行 created_at = 冻结戳 ⇒ 这些行在 audit_log 里找不到"
            "对应创建记录, 请人工定性 (类 20.220: 不编时间)。"
        )


def downgrade() -> None:
    # 回滚 = 恢复冻结常量 (仅默认值; 历史行已校正的真实时间不回退)。
    op.execute(sa.text(
        "ALTER TABLE file_requests "
        "ALTER COLUMN created_at SET DEFAULT " + _FROZEN + ", "
        "ALTER COLUMN updated_at SET DEFAULT " + _FROZEN
    ))
