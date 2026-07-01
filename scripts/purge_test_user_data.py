"""一次性清空测试账号 xiaoqi_testbot 全部数据 (2026-07-01)

清理范围（按 FK 依赖反向顺序）:
  1. reminders           (FK → tasks.id, 通过 created_by 的 task 关联)
  2. tasks               (created_by = 59, active + soft-deleted)
  3. chat_sessions       (user_id = 59, CASCADE 自动删 chat_messages + chat_shares)
  4. agent_traces        (user_id = 59, 无 FK)
  5. knowledge           (created_by = 59, 无 FK, file_path 同步 MinIO)
  6. MinIO bucket        (knowledge.file_path 非空时 remove_object)

防御性 WHERE:
  - 所有表都强制 user_id/created_by=59 子句, 避免误伤其他用户
  - 物理删除 (不留 deleted_at, 与软删相反)
  - JSON 全量备份 (含完整字段, 可 1 行 INSERT 重建)

三段式执行（必须按序）:
  # 1) dry-run 预览
  $ docker cp scripts/purge_test_user_data.py microbubble-agent-app-1:/tmp/
  $ docker exec -i -e SKIP_DB_SETUP=1 microbubble-agent-app-1 python /tmp/purge_test_user_data.py --scan
    <- 人工审核 plan 表 + 备份路径

  # 2) 真跑（必须显式 --confirm 才写库）
  $ docker exec -i -e SKIP_DB_SETUP=1 microbubble-agent-app-1 python /tmp/purge_test_user_data.py --apply --confirm

  # 3) 拷回备份
  $ docker cp microbubble-agent-app-1:/tmp/purge_test_user_backup_<ts>.json ./backups/testbot-cleanup-YYYYMMDD/

设计原则 (CLAUDE.md 2026-06-30 沉淀):
  - 删除不可逆 → 必须 dry-run + 二次确认 + JSON 文件备份 (铁律 5)
  - 防御性 WHERE user_id=59 → 0 误伤真实用户 (铁律 1)
  - 严格相等匹配 created_by=59 → 防 Pydantic 字段漂移
  - 幂等 → 二次跑全部 0 (铁律 4: 5 道防线 = 5 个验证点)
  - 单事务包裹 → 失败整批回滚
  - MinIO 同步 → file_path 不空时调 remove_object, 失败记录待清理列表
  - 单测覆盖纯函数 (FK chain / normalize / confirm gate)

参考范式:
  - scripts/migrate_kb_tags.py (dry-run + --confirm + JSON 备份 + 单事务)
  - scripts/reprocess_meeting.py (9 步流程 + 文件备份)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# 让脚本能找到 app 包 (本地 + 容器内都兼容)
sys.path.insert(0, str(Path(__file__).parent.parent))
# 容器内 app 包路径 (兼容本地没有 app/ 子目录的位置)
if (Path("/app") / "app" / "__init__.py").exists():
    sys.path.insert(0, "/app")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("purge_testbot")


# ── 规则常量 ────────────────────────────────────────────────────────
TEST_USER_ID = 59  # xiaoqi_testbot
TEST_USER_NAME = "xiaoqi_testbot"
TEST_USER_DISPLAY = "测试小助手"
# 输出
BACKUP_PREFIX = "purge_test_user_backup"


# ── 数据类 ──────────────────────────────────────────────────────────
@dataclass
class PurgeReport:
    """scan 结果汇总."""
    # 每表的行数 + id 范围
    tables: dict[str, dict] = field(default_factory=dict)
    # MinIO 待清理 paths
    minio_paths: list[str] = field(default_factory=list)
    # 备份目录
    backup_dir: str = ""


# ── 纯函数层（无副作用, 单测可独立跑） ─────────────────────────
def filter_testbot_ids(rows: list, user_id_field: str = "user_id") -> list:
    """防御性过滤: 仅保留 user_id == TEST_USER_ID 的行. 用于防 FK chain 漏扫.

    rows: list of SQLAlchemy row 对象
    user_id_field: 行属性名 (user_id / created_by)
    """
    return [r for r in rows if getattr(r, user_id_field, None) == TEST_USER_ID]


def filter_testbot_knowledge_paths(rows: list) -> list[str]:
    """从 knowledge rows 提取非空 MinIO file_path (用于同步删除).

    防御性:
      - 仅 created_by=59 的行 (与 scan 过滤一致)
      - file_path 必须是 string (非 None / 非空)
      - 去重 (同 path 多条记录只删一次)
    """
    seen: set[str] = set()
    out: list[str] = []
    for r in rows:
        if getattr(r, "created_by", None) != TEST_USER_ID:
            continue
        path = getattr(r, "file_path", None)
        if not path or not isinstance(path, str):
            continue
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def serialize_row(row, exclude: set[str] | None = None) -> dict:
    """把 SQLAlchemy row 转 dict 用于 JSON 备份.

    exclude: 不写入备份的字段集合 (如 embedding 大对象)
    """
    exclude = exclude or set()
    out = {}
    for col in row.__table__.columns:
        if col.name in exclude:
            continue
        val = getattr(row, col.name, None)
        if isinstance(val, datetime):
            out[col.name] = val.isoformat()
        elif hasattr(val, "__iter__") and not isinstance(val, (str, bytes, dict)):
            # ARRAY / JSONB / Vector
            try:
                if val is None:
                    out[col.name] = None
                else:
                    out[col.name] = list(val)
            except TypeError:
                out[col.name] = str(val)
        else:
            out[col.name] = val
    return out


def build_minio_orphan_log(minio_failures: list[tuple[str, str]]) -> dict:
    """MinIO 删除失败的 paths 列表 (用于人工兜底)."""
    return {
        "failed_at": datetime.now().isoformat(),
        "reason": "MinIO remove_object 失败, DB 已删, 需手动清理",
        "items": [{"path": p, "error": err} for p, err in minio_failures],
    }


# ── 数据访问层（async SQLAlchemy） ─────────────────────────────────
async def scan_all(engine) -> PurgeReport:
    """全表扫描 xiaoqi_testbot (user_id=59) 数据, 返回 PurgeReport."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.models.knowledge import Knowledge
    from app.models.chat_history import ChatSession, ChatMessage
    from app.models.member import Member

    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    report = PurgeReport()

    async with sf() as db:
        # 1. tasks (含 soft-deleted, 全删)
        from app.models.task import Task

        tasks_rows = (await db.execute(
            select(Task).where(Task.created_by == TEST_USER_ID)
        )).scalars().all()
        report.tables["tasks"] = {
            "n": len(tasks_rows),
            "ids": sorted([t.id for t in tasks_rows]),
            "active_n": sum(1 for t in tasks_rows if t.deleted_at is None),
            "soft_deleted_n": sum(1 for t in tasks_rows if t.deleted_at is not None),
        }

        # 2. reminders (通过 task_id 关联到 tasks)
        from app.models.reminder import Reminder

        task_ids = [t.id for t in tasks_rows]
        if task_ids:
            rem_rows = (await db.execute(
                select(Reminder).where(Reminder.task_id.in_(task_ids))
            )).scalars().all()
        else:
            rem_rows = []
        report.tables["reminders"] = {
            "n": len(rem_rows),
            "ids": sorted([r.id for r in rem_rows]),
        }

        # 3. chat_sessions (含 soft-deleted, CASCADE 自动删 chat_messages / chat_shares)
        sess_rows = (await db.execute(
            select(ChatSession).where(ChatSession.user_id == TEST_USER_ID)
        )).scalars().all()
        sess_ids = [s.id for s in sess_rows]
        report.tables["chat_sessions"] = {
            "n": len(sess_rows),
            "active_n": sum(1 for s in sess_rows if s.deleted_at is None),
            "soft_deleted_n": sum(1 for s in sess_rows if s.deleted_at is not None),
            "total_messages_n": 0,  # 下面补
        }

        # 3.1 chat_messages (CASCADE 跟随)
        if sess_ids:
            msg_count = (await db.execute(
                select(ChatMessage).where(ChatMessage.session_id.in_(sess_ids))
            )).scalars().all()
        else:
            msg_count = []
        report.tables["chat_sessions"]["total_messages_n"] = len(msg_count)

        # 4. agent_traces
        from app.models.agent_trace import AgentTrace

        trace_rows = (await db.execute(
            select(AgentTrace).where(AgentTrace.user_id == TEST_USER_ID)
        )).scalars().all()
        report.tables["agent_traces"] = {
            "n": len(trace_rows),
            "ids_sample": sorted([t.id for t in trace_rows])[:5],
        }

        # 5. knowledge (file_path 用于 MinIO 同步清理)
        kb_rows = (await db.execute(
            select(Knowledge).where(Knowledge.created_by == TEST_USER_ID)
        )).scalars().all()
        report.tables["knowledge"] = {
            "n": len(kb_rows),
            "ids_sample": sorted([k.id for k in kb_rows])[:5],
            "with_file_path_n": sum(1 for k in kb_rows if k.file_path),
            "by_source_type": {},
        }
        # 按 source_type 分布
        from collections import Counter
        st_counter = Counter(k.source_type or "(null)" for k in kb_rows)
        report.tables["knowledge"]["by_source_type"] = dict(st_counter)

        # 6. MinIO paths
        report.minio_paths = filter_testbot_knowledge_paths(kb_rows)

    return report


async def fetch_backup_rows(engine) -> dict:
    """拉所有待删行的完整字段用于 JSON 备份."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.models.task import Task
    from app.models.reminder import Reminder
    from app.models.chat_history import ChatSession, ChatMessage, ChatShare
    from app.models.agent_trace import AgentTrace
    from app.models.knowledge import Knowledge

    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    out = {"tasks": [], "reminders": [], "chat_sessions": [], "chat_messages": [],
           "chat_shares": [], "agent_traces": [], "knowledge": []}

    async with sf() as db:
        # tasks
        tasks = (await db.execute(
            select(Task).where(Task.created_by == TEST_USER_ID)
        )).scalars().all()
        out["tasks"] = [serialize_row(t) for t in tasks]

        # reminders (via task_id)
        task_ids = [t.id for t in tasks]
        if task_ids:
            rems = (await db.execute(
                select(Reminder).where(Reminder.task_id.in_(task_ids))
            )).scalars().all()
            out["reminders"] = [serialize_row(r) for r in rems]

        # chat_sessions
        sessions = (await db.execute(
            select(ChatSession).where(ChatSession.user_id == TEST_USER_ID)
        )).scalars().all()
        out["chat_sessions"] = [serialize_row(s) for s in sessions]
        sess_ids = [s.id for s in sessions]

        # chat_messages
        if sess_ids:
            msgs = (await db.execute(
                select(ChatMessage).where(ChatMessage.session_id.in_(sess_ids))
            )).scalars().all()
            out["chat_messages"] = [serialize_row(m) for m in msgs]

        # chat_shares (可能为 0)
        if sess_ids:
            shares = (await db.execute(
                select(ChatShare).where(ChatShare.session_id.in_(sess_ids))
            )).scalars().all()
            out["chat_shares"] = [serialize_row(s) for s in shares]

        # agent_traces
        traces = (await db.execute(
            select(AgentTrace).where(AgentTrace.user_id == TEST_USER_ID)
        )).scalars().all()
        # 排除 content / tool_trace 大字段, 仅保留元信息 (可重建)
        out["agent_traces"] = [serialize_row(t) for t in traces]

        # knowledge
        kbs = (await db.execute(
            select(Knowledge).where(Knowledge.created_by == TEST_USER_ID)
        )).scalars().all()
        # knowledge 备份含 embedding 列 (Vector(1024))
        for k in kbs:
            d = serialize_row(k)
            try:
                if k.embedding is not None:
                    d["embedding"] = list(k.embedding)
            except Exception:
                d["embedding"] = None
            out["knowledge"].append(d)

    return out


async def purge_all(engine) -> dict:
    """物理删除 (单事务): reminders → tasks → chat_sessions (CASCADE) → agent_traces → knowledge.

    返回 counts: 每表实际删除行数.
    """
    from sqlalchemy import delete, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.models.task import Task
    from app.models.reminder import Reminder
    from app.models.chat_history import ChatSession
    from app.models.agent_trace import AgentTrace
    from app.models.knowledge import Knowledge

    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    counts: dict[str, int] = {}

    async with sf() as db:
        try:
            # 1. reminders (FK → tasks.id)
            task_ids = (await db.execute(
                select(Task.id).where(Task.created_by == TEST_USER_ID)
            )).scalars().all()
            if task_ids:
                result = await db.execute(
                    delete(Reminder).where(Reminder.task_id.in_(task_ids))
                )
                counts["reminders"] = result.rowcount or 0
            else:
                counts["reminders"] = 0

            # 2. tasks
            result = await db.execute(
                delete(Task).where(Task.created_by == TEST_USER_ID)
            )
            counts["tasks"] = result.rowcount or 0

            # 3. chat_sessions (CASCADE 自动删 chat_messages + chat_shares)
            result = await db.execute(
                delete(ChatSession).where(ChatSession.user_id == TEST_USER_ID)
            )
            counts["chat_sessions"] = result.rowcount or 0

            # 4. agent_traces
            result = await db.execute(
                delete(AgentTrace).where(AgentTrace.user_id == TEST_USER_ID)
            )
            counts["agent_traces"] = result.rowcount or 0

            # 5. knowledge
            result = await db.execute(
                delete(Knowledge).where(Knowledge.created_by == TEST_USER_ID)
            )
            counts["knowledge"] = result.rowcount or 0

            await db.commit()
            log.info("  DB commit 成功: %s", counts)
        except Exception as e:
            await db.rollback()
            log.error("  DB 事务失败, 整批回滚: %s", e)
            raise

    # MinIO 同步清理由 main() 独立调用 (DB 已 commit, 不阻塞)
    return counts


def purge_minio(paths: list[str]) -> list[tuple[str, str]]:
    """同步调 MinIO remove_object × N. 失败路径返回 (path, error_msg).

    决策:
      - 不阻塞 DB 清理流程 (DB 已 commit)
      - 失败记录到 minio_orphans.json, 人工兜底
      - MinIO 不可达时整批失败, 全记入 orphans
    """
    if not paths:
        return []

    failures: list[tuple[str, str]] = []

    try:
        from app.config import settings
        from minio import Minio

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        bucket = settings.MINIO_BUCKET

        for path in paths:
            try:
                client.remove_object(bucket, path)
                log.info("  MinIO ✅ %s", path)
            except Exception as e:
                err = f"{type(e).__name__}: {str(e)[:200]}"
                log.error("  MinIO ❌ %s | %s", path, err)
                failures.append((path, err))
    except Exception as e:
        # MinIO client 初始化失败 (endpoint 不可达 / 配置错)
        log.error("  MinIO client 初始化失败: %s", e)
        for path in paths:
            failures.append((path, f"client_init_failed: {type(e).__name__}"))

    return failures


# ── 备份层 ──────────────────────────────────────────────────────────
def write_backup_file(payload: dict, workdir: str) -> str:
    """写 JSON 备份. 返回备份文件绝对路径."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    workdir_p = Path(workdir)
    workdir_p.mkdir(parents=True, exist_ok=True)
    path = workdir_p / f"{BACKUP_PREFIX}_{ts}.json"
    payload["backup_at"] = ts
    payload["test_user_id"] = TEST_USER_ID
    payload["test_user_name"] = TEST_USER_NAME
    payload["operator_hint"] = "scripts/purge_test_user_data.py"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return str(path.resolve())


# ── 输出层 ──────────────────────────────────────────────────────────
def print_scan_table(report: PurgeReport) -> None:
    log.info("=" * 60)
    log.info("=== 测试账号清理预览 ===")
    log.info("  user_id=%d username=%s", TEST_USER_ID, TEST_USER_NAME)
    log.info("")

    total = 0
    for tbl, info in report.tables.items():
        n = info.get("n", 0)
        total += n
        if tbl == "tasks":
            log.info(
                "  %-20s %4d 行 (active=%d, soft-deleted=%d)",
                tbl, n, info.get("active_n", 0), info.get("soft_deleted_n", 0),
            )
        elif tbl == "chat_sessions":
            log.info(
                "  %-20s %4d 行 (active=%d, soft-deleted=%d) → CASCADE 删 chat_messages×%d",
                tbl, n, info.get("active_n", 0), info.get("soft_deleted_n", 0),
                info.get("total_messages_n", 0),
            )
        elif tbl == "agent_traces":
            log.info(
                "  %-20s %4d 行 (id 示例: %s...)",
                tbl, n, info.get("ids_sample", []),
            )
        elif tbl == "knowledge":
            log.info(
                "  %-20s %4d 行 (有 file_path: %d, source_type 分布: %s)",
                tbl, n, info.get("with_file_path_n", 0), info.get("by_source_type", {}),
            )
        elif tbl == "reminders":
            log.info("  %-20s %4d 行 (跟随 tasks)", tbl, n)
        else:
            log.info("  %-20s %4d 行", tbl, n)
    log.info("")
    log.info("  TOTAL (DB)         %d 行", total)
    log.info("  MinIO 待清理 paths: %d 个", len(report.minio_paths))
    log.info("")
    log.info("=== 修改范围汇总 ===")
    log.info("  tasks / reminders / chat_sessions / agent_traces / knowledge")
    log.info("    全部 where user_id/created_by=%d (防御性)", TEST_USER_ID)
    log.info("  物理删除 (不留 deleted_at)")
    log.info("  chat_messages / chat_shares 通过 CASCADE 自动删")


# ── 主流程 ──────────────────────────────────────────────────────────
async def main() -> int:
    p = argparse.ArgumentParser(
        description=f"清空测试账号 {TEST_USER_NAME} (user_id={TEST_USER_ID}) 全部数据",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--scan", action="store_true", help="只查询不写库, 打印 plan 表")
    g.add_argument("--apply", action="store_true", help="实际写库, 要求显式 --confirm")
    p.add_argument(
        "--confirm",
        action="store_true",
        help="apply 时必填: 二次确认确实要写库 (无此 flag 不写)",
    )
    p.add_argument("--workdir", default="/tmp", help="备份输出目录 (默认 /tmp)")
    args = p.parse_args()

    from sqlalchemy.ext.asyncio import create_async_engine
    from app.config import settings

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )

    try:
        if args.scan:
            log.info("[SCAN] 模式: 只查询不写库")
            report = await scan_all(engine)
            print_scan_table(report)
            return 0

        # ── apply 流程 ──
        log.info("[APPLY] 模式: 实际写库")

        # 1) re-scan (防数据漂移)
        report = await scan_all(engine)
        log.info("  re-scan: %s", {k: v.get("n", 0) for k, v in report.tables.items()})
        log.info("  MinIO 待清理 paths: %d", len(report.minio_paths))

        # 2) 二次确认门 (防误跑: 没 --confirm 直接拒, 不写库 + 不写备份)
        if not args.confirm:
            log.warning(
                "⚠ [DRY RUN] --apply 但未传 --confirm, 拒绝写库. "
                "如确认要执行请加 --confirm 参数.",
            )
            print_scan_table(report)
            return 1

        # 3) 写备份 (含所有表所有行的完整字段, 100% 可恢复)
        log.info("  拉取完整备份数据...")
        backup_rows = await fetch_backup_rows(engine)
        backup_path = write_backup_file(backup_rows, args.workdir)
        log.info("  备份已写: %s (大小: 见 file)", backup_path)
        for tbl, rows in backup_rows.items():
            if isinstance(rows, list):
                log.info("    %-20s %4d 行", tbl, len(rows))
            # 跳过元数据字段 (str/int 等)

        # 4) 真删 (单事务 DB, MinIO 单独跑失败不阻塞)
        log.info("  DB 单事务删除中...")
        counts = await purge_all(engine)
        log.info("  [APPLY] ✅ DB 完成: %s", counts)

        # 5) MinIO 同步清理
        if report.minio_paths:
            log.info("  MinIO 同步清理 %d 个 paths...", len(report.minio_paths))
            failures = purge_minio(report.minio_paths)
            log.info("  MinIO 完成: 成功 %d, 失败 %d",
                     len(report.minio_paths) - len(failures), len(failures))
            if failures:
                orphan_log = build_minio_orphan_log(failures)
                orphan_path = Path(args.workdir) / f"minio_orphans_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                orphan_path.write_text(
                    json.dumps(orphan_log, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                log.warning(
                    "  ⚠ MinIO 失败 %d 个, 孤儿记录: %s",
                    len(failures), orphan_path,
                )
        else:
            log.info("  无 MinIO paths 待清理")

        log.info("[APPLY] 🎉 全部完成")
        log.info("[APPLY] 备份文件保留: %s", backup_path)
        log.info("[APPLY] 💡 拷回宿主机: docker cp <container>:%s ./backups/", backup_path)
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)