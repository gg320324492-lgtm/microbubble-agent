"""2026-07-02 v2 PR6-P10 — 从 /tmp/celery_cleanup_*.json 备份恢复 Celery cleanup 删除的数据

事故教训 (PR6-P9): 我误传 cleanup_old_mentions_task(retention_days=0) 删了 31 条生产
file_mentions 数据. 通过 backup_before_delete helper 自动备份到 JSON, 本脚本可单条重 INSERT.

**支持的表** (从 JSON payload.table_name 推断):
- chat_sessions (CASCADE 自动清 messages + shares, restore 只恢复 session 行)
- file_mentions (单条独立, 简单)
- drive_files (Knowledge 表, 含 file_path / mime_type / owner_id 等字段)
- folders (Folder 表)

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
# 4. 真跑
python scripts/restore_from_backup.py --apply --confirm ./backups/celery_cleanup_file_mentions_20260702_123456.json
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
BACKUP_TABLE_TO_ORM = {
    "chat_sessions": ("ChatSession", "chat_sessions"),
    "file_mentions": ("FileMention", "file_mentions"),
    "drive_files": ("Knowledge", "knowledge"),  # drive_files 备份的是 Knowledge 表
    "folders": ("Folder", "folders"),
}


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


def print_scan_summary(payload: dict, backup_path: str) -> None:
    """打印 backup 摘要 (无副作用)"""
    table_name = payload["table_name"]
    orm_info = BACKUP_TABLE_TO_ORM.get(table_name)
    print(f"📦 [SCAN] 备份文件: {backup_path}")
    print(f"   备份时间: {payload['backup_at']}")
    print(f"   逻辑表: {table_name} → ORM: {orm_info[0] if orm_info else '?'} / DB 表: {orm_info[1] if orm_info else '?'}")
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
    print(f"⚠️ [SCAN] 即将恢复 {payload['row_count']} 行到 {orm_info[1] if orm_info else '?'} 表 (INSERT, id 冲突时跳过)")


async def restore_from_backup(backup_path: str) -> int:
    """恢复备份到 DB (async), 返回实际 INSERT 行数"""
    payload = load_backup(backup_path)
    table_name = payload["table_name"]
    items = payload["items"]

    orm_info = BACKUP_TABLE_TO_ORM.get(table_name)
    if not orm_info:
        raise ValueError(f"不支持的 table_name '{table_name}' (BACKUP_TABLE_TO_ORM 缺映射)")

    orm_class_name, db_table_name = orm_info

    # 动态 import ORM model
    if orm_class_name == "ChatSession":
        from app.models.chat_history import ChatSession
        model_class = ChatSession
    elif orm_class_name == "FileMention":
        from app.models.knowledge import FileMention
        model_class = FileMention
    elif orm_class_name == "Knowledge":
        from app.models.knowledge import Knowledge
        model_class = Knowledge
    elif orm_class_name == "Folder":
        from app.models.folder import Folder
        model_class = Folder
    else:
        raise ValueError(f"ORM model 未注册: {orm_class_name}")

    # 独立 engine (与 Celery task 范式一致)
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as db:
            inserted_count = 0
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

                # INSERT ON CONFLICT (id) DO NOTHING (id 已在的跳过)
                # 用 SQL 直写避免 ORM session.add 与 sync expire 冲突
                cols = list(clean_item.keys())
                col_names = ", ".join(cols)
                placeholders = ", ".join(f":{c}" for c in cols)
                stmt = text(
                    f"INSERT INTO {db_table_name} ({col_names}) VALUES ({placeholders}) "
                    f"ON CONFLICT ({TABLE_TO_PRIMARY_KEY.get(table_name, 'id')}) DO NOTHING"
                )
                try:
                    result = await db.execute(stmt, clean_item)
                    if result.rowcount > 0:
                        inserted_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    print(f"⚠️ INSERT 失败 (id={clean_item.get('id')}): {e}")
                    skipped_count += 1

            await db.commit()
            print(f"✅ [RESTORE] 恢复完成: INSERT {inserted_count} 行, 跳过 {skipped_count} 行 (id 已存在)")
            return inserted_count
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="从 /tmp/celery_cleanup_*.json 备份恢复 Celery cleanup 删除的数据")
    parser.add_argument("backup_path", help="备份 JSON 文件路径")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--scan", action="store_true", help="只读 + 打印摘要 (无副作用)")
    g.add_argument("--apply", action="store_true", help="实际写入 DB (需要 --confirm)")
    parser.add_argument("--confirm", action="store_true", help="二次确认门 (apply 必传)")
    args = parser.parse_args()

    try:
        payload = load_backup(args.backup_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ [ERROR] {e}")
        return 1

    print_scan_summary(payload, args.backup_path)

    if args.scan:
        print("\n🟢 [SCAN] dry-run 完成 (无 DB 写入)")
        return 0

    if args.apply:
        if not args.confirm:
            print("⚠️ [DRY RUN] --apply 但未传 --confirm, 跳过写入 (用户决策防误操作)")
            return 1
        inserted = asyncio.run(restore_from_backup(args.backup_path))
        print(f"\n💡 [HINT] 建议硬刷浏览器 (Ctrl+Shift+R) 验证 UI 显示恢复的数据")
        return 0 if inserted > 0 else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())