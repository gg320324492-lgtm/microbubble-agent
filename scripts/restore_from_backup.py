"""2026-07-02 v2 PR6-P10 — 从 /tmp/celery_cleanup_*.json 备份恢复 Celery cleanup 删除的数据

事故教训 (PR6-P9): 我误传 cleanup_old_mentions_task(retention_days=0) 删了 31 条生产
file_mentions 数据. 通过 backup_before_delete helper 自动备份到 JSON, 本脚本可单条重 INSERT.

**支持的表** (从 JSON payload.table_name 推断, 可被 --table 覆盖):
- chat_sessions (CASCADE 自动清 messages + shares, restore 只恢复 session 行)
- file_mentions (单条独立, 简单)
- drive_files (Knowledge 表, 含 file_path / mime_type / owner_id 等字段)
- folders (Folder 表)

**2026-07-02 v2 PR6-P10 增量: --table 显式指定**
- 用途: 跨表恢复 / JSON 内 table_name 字段错 / 未来表 rename 兼容
- 行为: 覆盖 payload['table_name'], 走与 JSON 内字段不同的 ORM model + DB 表
- 警告: 与 JSON 内 table_name 不一致时打印 ⚠️ 警告 (仍允许, 用户显式决策)
- 验证: --table 必须在 BACKUP_TABLE_TO_ORM.keys() 里, 否则 fail fast 列出合法选项
- 注意: items 字段必须与目标表 columns 兼容 (否则 INSERT 失败, 走 try/except skipped_count += 1)

**2026-07-02 v2 PR6-P10+ 增量: --columns 显式指定部分字段**
- 用途: partial INSERT (只 INSERT 指定列, 其他列走 DB default)
  - 旧备份字段不全 (PR6-P10 之前的备份可能缺新加的 vision 列)
  - 想保留现有 DB 其他字段 (只覆盖部分, 例如只更新 is_read)
  - 想用备份数据打补丁 (e.g. --columns=id,is_read)
- 行为: 只 INSERT --columns 指定的列, 其他列用 DB default (NULL / NOT NULL 报缺列错)
- 验证: --columns 必须在目标 ORM 表的 columns 里, 否则 fail fast 列出合法列
- 注意: --columns 必须包含 id 列 (主键 ON CONFLICT 依赖), 否则 fail fast
- 兼容: 不传 --columns → 全字段 INSERT (PR6-P10 行为, 向后兼容)

**2026-07-02 v2 PR6-P11+ 增量: --upsert flag 切 INSERT ON CONFLICT DO UPDATE 模式**
- 用途: 行已存在时用 backup 数据覆盖 (而非 DO NOTHING 跳过)
  - 事故回滚: 中间手动加的行也能被 backup 覆盖恢复 (不只补"已删的")
  - 跨会话同步: 用最新 backup 把 DB 同步到 backup 状态
  - 配合 --columns: UPSERT partial 语义 (只 UPDATE 指定列, 其他列保留 DB 当前值)
- 行为: INSERT ... ON CONFLICT (id) DO UPDATE SET col1=EXCLUDED.col1, col2=EXCLUDED.col2, ...
- 警告: --upsert 无 --columns 时会覆盖**全部列** (中间手动修改会被破坏), 强烈建议配合 --columns
- 验证: --upsert 是 boolean flag, 不需要 validation (true/false)
- 兼容: 不传 --upsert → DO NOTHING (PR6-P10+ 行为, 向后兼容)

**模式**:
- --scan: 读 JSON → 打印将恢复的 N 行 + 目标表 + 字段预览 (无副作用)
- --apply --confirm: 二次确认门 + 实际写回 DB (INSERT ON CONFLICT DO NOTHING)

**使用示例**:
```bash
# 1. 列出所有可用备份
docker exec microbubble-agent-app-1 ls /tmp/celery_cleanup_*.json
# 2. 拷贝到宿主机
docker cp microbubble-agent-app-1:/tmp/celery_cleanup_file_mentions_20260702_123456.json ./backups/
# 3. 干跑预览
python scripts/restore_from_backup.py --scan ./backups/celery_cleanup_file_mentions_20260702_123456.json
# 4. 真跑 (全字段, PR6-P10 行为)
python scripts/restore_from_backup.py --apply --confirm ./backups/celery_cleanup_file_mentions_20260702_123456.json
# 5. (可选) --table 覆盖: 未来表 rename / JSON 内字段错时用
python scripts/restore_from_backup.py --scan --table=folders ./backups/celery_cleanup_legacy.json
# 6. (可选) --columns 部分字段: 旧备份缺列 / 想保留现有其他列
python scripts/restore_from_backup.py --apply --confirm \
  --columns=id,file_id,context,mentioned_user_id \
  ./backups/celery_cleanup_file_mentions_20260701.json
# 7. (可选) --table + --columns 组合: 跨表 + 部分字段
python scripts/restore_from_backup.py --apply --confirm \
  --table=file_mentions --columns=id,file_id \
  ./backups/celery_cleanup_legacy.json
# 8. (PR6-P11+) --upsert 切 ON CONFLICT DO UPDATE 模式 (行已存在时覆盖)
python scripts/restore_from_backup.py --apply --confirm --upsert \
  ./backups/celery_cleanup_file_mentions_20260701.json
# 9. (PR6-P11+) --upsert + --columns 完美打补丁: 只 UPDATE 指定列, 其他列保留 DB 当前值
python scripts/restore_from_backup.py --apply --confirm --upsert \
  --columns=id,is_read,read_at \
  ./backups/celery_cleanup_file_mentions_20260701.json
# 10. (PR6-P11+) --upsert + --table + --columns 三连: 跨表 + 覆盖 + 部分字段
python scripts/restore_from_backup.py --apply --confirm --upsert \
  --table=folders --columns=id,name,parent_id \
  ./backups/celery_cleanup_legacy.json
```
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Optional

# 让脚本可独立 import app.* (与 migrate_kb_dedup_titles.py 范式一致)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings


TABLE_TO_PRIMARY_KEY = {
    "chat_sessions": "id",
    "file_mentions": "id",
    "drive_files": "id",  # backup table_name=knowledge 模型, 但 backup JSON 标 table_name="drive_files"
    "folders": "id",
}

# backup JSON 中 table_name 字段 → ORM model 类 + 实际表名
# 2026-07-02 v2 PR6-P10+ 增量: 模型类在首次访问时动态 import (避免顶层 import 拖慢启动)
BACKUP_TABLE_TO_ORM = {
    "chat_sessions": ("ChatSession", "chat_sessions"),
    "file_mentions": ("FileMention", "file_mentions"),
    "drive_files": ("Knowledge", "knowledge"),  # drive_files 备份的是 Knowledge 表
    "folders": ("Folder", "folders"),
}


def _get_model_class(orm_class_name: str):
    """按 ORM class name 动态 import + 返回 model class

    铁律:
    1. 动态 import 而非模块顶层 import: 因为 Celery / asyncio / app.config 启动开销大,
       顶层 import 会让 --help / --scan 这些无副作用命令也走完启动流程 (慢 + 可能失败)
    2. OR 名称 whitelist: 防止外部传入任意字符串触发任意 import (安全)
    """
    if orm_class_name == "ChatSession":
        from app.models.chat_history import ChatSession
        return ChatSession
    elif orm_class_name == "FileMention":
        from app.models.knowledge import FileMention
        return FileMention
    elif orm_class_name == "Knowledge":
        from app.models.knowledge import Knowledge
        return Knowledge
    elif orm_class_name == "Folder":
        from app.models.folder import Folder
        return Folder
    else:
        raise ValueError(f"ORM model 未注册: {orm_class_name} (BACKUP_TABLE_TO_ORM 缺映射)")


def get_table_columns(table_name: str) -> list[str]:
    """返回目标表的所有 ORM 列名 (用于 --columns validation)

    Args:
        table_name: BACKUP_TABLE_TO_ORM key (chat_sessions / file_mentions / drive_files / folders)

    Returns:
        list[str]: ORM 列名列表, e.g. ['id', 'file_id', 'context', 'created_at', ...]

    Raises:
        ValueError: table_name 不在 BACKUP_TABLE_TO_ORM 里
    """
    orm_info = BACKUP_TABLE_TO_ORM.get(table_name)
    if not orm_info:
        raise ValueError(
            f"不支持的 table_name '{table_name}' (BACKUP_TABLE_TO_ORM 缺映射). "
            f"可选: {list(BACKUP_TABLE_TO_ORM.keys())}"
        )
    orm_class_name, _ = orm_info
    model_class = _get_model_class(orm_class_name)
    return [col.name for col in model_class.__table__.columns]


def load_backup(backup_path: str) -> dict:
    """读 JSON 备份 + 简单防御性校验"""
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"备份文件不存在: {backup_path}")
    with open(backup_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    # 防御性: payload 必须含必需字段
    required_keys = ["backup_at", "table_name", "row_count", "items"]
    for key in required_keys:
        if key not in payload:
            raise ValueError(f"备份文件 {backup_path} 缺必需字段 '{key}' (PR6-P10 之前的备份可能不兼容)")
    if not isinstance(payload["items"], list):
        raise ValueError(f"备份文件 {backup_path} items 字段不是 list")
    return payload


def print_scan_summary(
    payload: dict,
    backup_path: str,
    original_table_name: Optional[str] = None,
    partial_columns: Optional[list[str]] = None,
    upsert_mode: bool = False,
) -> None:
    """打印 backup 摘要 (无副作用)

    Args:
        payload: load_backup 返回的 dict
        backup_path: 备份文件路径 (用于打印)
        original_table_name: JSON 原始 table_name (与 payload['table_name'] 不同时打印 override 警告)
        partial_columns: 部分列模式指定列 (PR6-P10+ --columns), None=全字段模式
        upsert_mode: PR6-P11+ --upsert flag, True=DO UPDATE 模式 (行已存在时覆盖)
    """
    table_name = payload["table_name"]
    orm_info = BACKUP_TABLE_TO_ORM.get(table_name)
    print(f"📦 [SCAN] 备份文件: {backup_path}")
    print(f"   备份时间: {payload['backup_at']}")
    if original_table_name and original_table_name != table_name:
        # 2026-07-02 v2 PR6-P10 增量: --table 覆盖时显式标记 override, 防静默改目标表
        print(f"   逻辑表: {table_name} → ORM: {orm_info[0] if orm_info else '?'} / DB 表: {orm_info[1] if orm_info else '?'}  ⚠️ 覆盖自 JSON 原始 table_name={original_table_name}")
    else:
        print(f"   逻辑表: {table_name} → ORM: {orm_info[0] if orm_info else '?'} / DB 表: {orm_info[1] if orm_info else '?'}")
    # 2026-07-02 v2 PR6-P10+ 增量: partial columns 模式显式标记, 防静默部分字段 INSERT
    if partial_columns is not None:
        print(f"   列模式: ⚠️ partial ({len(partial_columns)} 列) = {partial_columns} (其他列走 DB default)")
    else:
        print(f"   列模式: 全部列 (PR6-P10 默认行为)")
    # 2026-07-02 v2 PR6-P11+ 增量: upsert 模式显式标记, 防静默覆盖 DB 已有行
    if upsert_mode:
        print(f"   冲突策略: ⚠️ UPSERT (ON CONFLICT DO UPDATE) — 行已存在时用 backup 数据覆盖")
        if partial_columns is None:
            print(f"   ⚠️ 警告: --upsert 缺 --columns 时会覆盖全部列 (中间手动修改会被破坏), 强烈建议配合 --columns")
    else:
        print(f"   冲突策略: DO NOTHING (PR6-P10+ 默认行为) — 行已存在时跳过")
    print(f"   行数: {payload['row_count']}")
    print(f"   清理策略: {payload.get('meta', {}).get('strategy', 'N/A')}")
    print(f"   cutoff: {payload.get('meta', {}).get('cutoff_date', 'N/A')}")
    print()
    print(f"   前 3 行预览:")
    for idx, item in enumerate(payload["items"][:3]):
        preview_keys = list(item.keys())[:8]
        preview_str = ", ".join(f"{k}={item[k]}" for k in preview_keys)
        print(f"     [{idx+1}] {preview_str}{'...' if len(item) > 8 else ''}")
    if len(payload["items"]) > 3:
        print(f"     ... ({len(payload['items']) - 3} more)")
    print()
    if upsert_mode:
        print(f"⚠️ [SCAN] 即将 UPSERT {payload['row_count']} 行到 {orm_info[1] if orm_info else '?'} 表 (id 冲突时用 backup 数据覆盖)")
    else:
        print(f"⚠️ [SCAN] 即将恢复 {payload['row_count']} 行到 {orm_info[1] if orm_info else '?'} 表 (INSERT, id 冲突时跳过)")


async def restore_from_backup(
    backup_path: str,
    payload: Optional[dict] = None,
    columns: Optional[list[str]] = None,
    upsert: bool = False,
) -> int:
    """恢复备份到 DB (async), 返回实际 INSERT/UPDATE 行数

    Args:
        backup_path: 备份 JSON 文件路径 (用于日志)
        payload: 预加载的 backup dict (--table override 时传入, 避免重新 load 丢覆盖)
                 None 时内部调 load_backup 读盘
        columns: 部分字段模式 (PR6-P10+ --columns), 只 INSERT 指定列
                 None=全字段 INSERT (PR6-P10 默认行为)
                 list=partial mode, 只 INSERT 这些列 (其他列走 DB default)
        upsert: PR6-P11+ --upsert flag, True=ON CONFLICT DO UPDATE 模式
                (行已存在时用 backup 数据覆盖)
                False=ON CONFLICT DO NOTHING (PR6-P10+ 默认行为)
    """
    if payload is None:
        payload = load_backup(backup_path)
    table_name = payload["table_name"]
    items = payload["items"]

    orm_info = BACKUP_TABLE_TO_ORM.get(table_name)
    if not orm_info:
        raise ValueError(f"不支持的 table_name '{table_name}' (BACKUP_TABLE_TO_ORM 缺映射)")

    orm_class_name, db_table_name = orm_info
    model_class = _get_model_class(orm_class_name)

    # 独立 engine (与 Celery task 范式一致)
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as db:
            inserted_count = 0
            updated_count = 0
            skipped_count = 0
            for item in items:
                # 防御性: 把 ISO datetime 转回 datetime 对象 (PG TIMESTAMP 列要求)
                clean_item = {}
                for k, v in item.items():
                    if isinstance(v, str) and v and k.endswith("_at"):
                        # 尝试 ISO 解析 (含 'T' 或 ' ')
                        try:
                            clean_item[k] = datetime.fromisoformat(v.replace(" ", "T") if " " in v and "T" not in v else v)
                        except (ValueError, AttributeError):
                            clean_item[k] = v
                    else:
                        clean_item[k] = v

                # 2026-07-02 v2 PR6-P10+ 增量: partial columns 模式过滤字段
                if columns is not None:
                    # 只保留 --columns 指定的列 (其他列丢弃, 走 DB default)
                    clean_item = {k: v for k, v in clean_item.items() if k in columns}
                    # 防御性: id 列必须在 columns 里 (主键 ON CONFLICT 依赖)
                    pk = TABLE_TO_PRIMARY_KEY.get(table_name, "id")
                    if pk not in clean_item:
                        # 不 raise, 跳过这一行 (partial mode 用户明确意图)
                        print(f"⚠️ INSERT 跳过 (id 列 '{pk}' 不在 --columns): {clean_item}")
                        skipped_count += 1
                        continue

                # INSERT ON CONFLICT (id) DO NOTHING (id 已在的跳过)
                # OR PR6-P11+: ON CONFLICT (id) DO UPDATE SET col=EXCLUDED.col
                # 用 SQL 直写避免 ORM session.add 与 sync expire 冲突
                cols = list(clean_item.keys())
                col_names = ", ".join(cols)
                placeholders = ", ".join(f":{c}" for c in cols)
                pk = TABLE_TO_PRIMARY_KEY.get(table_name, "id")
                if upsert:
                    # 2026-07-02 v2 PR6-P11+ 增量: DO UPDATE SET 全列 (partial mode 时只 UPDATE partial 列)
                    # PK 列不 SET (会被 PG 自动跳过), 所以可以安全 SET 所有 cols
                    update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != pk)
                    stmt = text(
                        f"INSERT INTO {db_table_name} ({col_names}) VALUES ({placeholders}) "
                        f"ON CONFLICT ({pk}) DO UPDATE SET {update_set}"
                    )
                else:
                    stmt = text(
                        f"INSERT INTO {db_table_name} ({col_names}) VALUES ({placeholders}) "
                        f"ON CONFLICT ({pk}) DO NOTHING"
                    )
                try:
                    result = await db.execute(stmt, clean_item)
                    # PR6-P11+ 增量: 区分 INSERT/UPDATE/SKIP
                    # rowcount 在 DO NOTHING 模式下: 1=实际 INSERT, 0=conflict 跳过
                    # rowcount 在 DO UPDATE 模式下: 2=UPDATE (1 INSERT row + 1 UPDATE row), 1=INSERT
                    # (PG 行为: DO UPDATE 时 rowcount=2, 因为更新一行算 2 个 affected row)
                    # DO NOTHING 时 rowcount=0
                    if upsert:
                        if result.rowcount == 2:
                            updated_count += 1  # 行已存在, 走 DO UPDATE
                        elif result.rowcount == 1:
                            inserted_count += 1  # 新行, INSERT 成功
                        else:
                            skipped_count += 1  # 不期望情况
                    else:
                        if result.rowcount > 0:
                            inserted_count += 1
                        else:
                            skipped_count += 1
                except Exception as e:
                    print(f"⚠️ INSERT/UPDATE 失败 (id={clean_item.get('id')}): {e}")
                    skipped_count += 1

            await db.commit()
            if upsert:
                print(f"✅ [RESTORE] UPSERT 完成: 新增 {inserted_count} 行, 更新 {updated_count} 行, 跳过 {skipped_count} 行")
            else:
                print(f"✅ [RESTORE] 恢复完成: INSERT {inserted_count} 行, 跳过 {skipped_count} 行 (id 已存在)")
            return inserted_count + updated_count
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="从 /tmp/celery_cleanup_*.json 备份恢复 Celery cleanup 删除的数据")
    parser.add_argument("backup_path", help="备份 JSON 文件路径")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--scan", action="store_true", help="只读 + 打印摘要 (无副作用)")
    g.add_argument("--apply", action="store_true", help="实际写入 DB (需要 --confirm)")
    parser.add_argument("--confirm", action="store_true", help="二次确认门 (apply 必传)")
    # 2026-07-02 v2 PR6-P10 增量: 显式指定目标表, 覆盖 JSON 内 table_name
    # 用途: 跨表恢复 / JSON 内字段错 / 未来表 rename 兼容
    parser.add_argument(
        "--table",
        help=(
            f"显式指定目标表 (覆盖 JSON 内的 table_name). "
            f"可选: {', '.join(BACKUP_TABLE_TO_ORM.keys())}. "
            f"覆盖时与 JSON 字段不一致会打 ⚠️ 警告"
        ),
    )
    # 2026-07-02 v2 PR6-P10+ 增量: 显式指定部分字段, 只 INSERT 这些列 (其他列走 DB default)
    # 用途: 旧备份字段不全 / 想保留现有 DB 其他列 (打补丁模式)
    # 注意: 必须包含主键列 (id), 否则 fail fast
    parser.add_argument(
        "--columns",
        help=(
            f"显式指定要 INSERT 的列 (逗号分隔). "
            f"只 INSERT 指定列, 其他列走 DB default. "
            f"必须包含主键列 (id). 列必须在目标 ORM 表里, 否则 fail fast"
        ),
    )
    # 2026-07-02 v2 PR6-P11+ 增量: --upsert flag 切 INSERT ON CONFLICT DO UPDATE 模式
    # 用途: 行已存在时用 backup 数据覆盖 (事故回滚 / 跨会话同步)
    # 推荐配合 --columns: 只 UPDATE 指定列, 其他列保留 DB 当前值
    parser.add_argument(
        "--upsert",
        action="store_true",
        help=(
            "切换为 ON CONFLICT DO UPDATE 模式. 行已存在时用 backup 数据覆盖. "
            "强烈建议配合 --columns 避免覆盖全部列 (会破坏中间手动修改)"
        ),
    )
    args = parser.parse_args()

    try:
        payload = load_backup(args.backup_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ [ERROR] {e}")
        return 1

    # 2026-07-02 v2 PR6-P10 增量: --table override 逻辑
    # 铁律: 1) 必须在 BACKUP_TABLE_TO_ORM 里 (fail fast)
    #       2) 与 JSON 原始字段不一致时必打 ⚠️ 警告 (不静默)
    #       3) 覆盖后 payload 仍能正确推断 ORM model + DB 表
    original_table_name = payload.get("table_name")
    if args.table:
        if args.table not in BACKUP_TABLE_TO_ORM:
            print(f"❌ [ERROR] --table 指定的表 '{args.table}' 不在支持列表")
            print(f"   可选: {list(BACKUP_TABLE_TO_ORM.keys())}")
            return 1
        if args.table != original_table_name:
            print(
                f"⚠️ [WARN] --table={args.table} 与 JSON 内的 table_name={original_table_name} 不一致"
            )
            print(
                f"   用 --table 指定值覆盖 JSON 字段 (items 字段必须与目标表 columns 兼容, 否则 INSERT 会失败)"
            )
        else:
            # 相同, 显式传 --table 但没差异, 静默不警告 (用户显式表达一致意图)
            pass
        # 覆盖 payload 字段 (in-memory, 不改 JSON 文件)
        payload["table_name"] = args.table

    # 2026-07-02 v2 PR6-P10+ 增量: --columns 解析 + validation
    # 铁律: 1) 必须在目标 ORM 表的 columns 里 (fail fast 列合法列)
    #       2) 必须包含主键列 (id) (主键 ON CONFLICT 依赖)
    #       3) 解析顺序: 先 --table (决定目标表), 再 --columns (按目标表的 columns 验证)
    partial_columns: Optional[list[str]] = None
    if args.columns:
        try:
            valid_columns = get_table_columns(payload["table_name"])
        except ValueError as e:
            print(f"❌ [ERROR] {e}")
            return 1
        # 解析 + 去重 + strip
        requested = [c.strip() for c in args.columns.split(",") if c.strip()]
        # 去重 (保持顺序, 避免重复列导致 INSERT 错)
        seen = set()
        requested = [c for c in requested if not (c in seen or seen.add(c))]
        # validation 1: 列必须在 ORM 表里
        invalid = [c for c in requested if c not in valid_columns]
        if invalid:
            print(f"❌ [ERROR] --columns 指定的列 {invalid} 不在表 '{payload['table_name']}' 里")
            print(f"   合法列 ({len(valid_columns)} 列): {valid_columns}")
            return 1
        # validation 2: 必须包含主键列 (id)
        pk = TABLE_TO_PRIMARY_KEY.get(payload["table_name"], "id")
        if pk not in requested:
            print(f"❌ [ERROR] --columns 必须包含主键列 '{pk}' (INSERT ON CONFLICT 依赖)")
            print(f"   当前 --columns: {requested}")
            print(f"   提示: 加 '{pk}' 到 --columns, 例: --columns={pk},{','.join(c for c in requested if c != pk)}")
            return 1
        partial_columns = requested

    print_scan_summary(
        payload,
        args.backup_path,
        original_table_name=original_table_name,
        partial_columns=partial_columns,
        upsert_mode=args.upsert,
    )

    if args.scan:
        print("\n🟢 [SCAN] dry-run 完成 (无 DB 写入)")
        return 0

    if args.apply:
        if not args.confirm:
            print("⚠️ [DRY RUN] --apply 但未传 --confirm, 跳过写入 (用户决策防误操作)")
            return 1
        # 2026-07-02 v2 PR6-P11+ 增量: --upsert 透传到 restore_from_backup
        inserted = asyncio.run(
            restore_from_backup(
                args.backup_path,
                payload=payload,
                columns=partial_columns,
                upsert=args.upsert,
            )
        )
        print(f"\n💡 [HINT] 建议硬刷浏览器 (Ctrl+Shift+R) 验证 UI 显示恢复的数据")
        return 0 if inserted > 0 else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())