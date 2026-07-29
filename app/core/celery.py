from celery import Celery, signals

from app.config import settings
from app.core.request_context import set_task_id, reset_task_id

celery_app = Celery(
    "microbubble",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,  # worker OOM/重启时重新入队，避免任务静默丢失
    task_time_limit=600,  # 单 task 最长 10 分钟，硬终止失控任务
    task_soft_time_limit=540,  # 9 分钟软警告，给任务清理资源的机会
    worker_max_tasks_per_child=1000,  # 定期回收 worker，防止长期内存泄漏
    worker_prefetch_multiplier=1,
    beat_schedule={
        "check-reminders": {
            "task": "app.services.reminder_service.process_reminders_task",
            "schedule": 10.0,  # 每10秒检查一次，秒级精确提醒
        },
        "proactive-checks": {
            "task": "app.wechat.scheduler.run_proactive_checks",
            "schedule": 900.0,  # 每15分钟检查一次
        },
        "memory-maintenance": {
            "task": "app.services.memory_service.maintenance_task",
            "schedule": 3600.0,  # 每小时
        },
        "knowledge-evolution-weekly": {
            "task": "app.services.knowledge_evolution_tasks.evolve_knowledge_base",
            "schedule": 7 * 24 * 3600.0,  # 每周
        },
        "knowledge-gap-processing": {
            "task": "app.services.knowledge_evolution_tasks.process_pending_gaps",
            "schedule": 6 * 3600.0,  # 每6小时处理待填补空白
        },
        "process-pending-knowledge": {
            "task": "app.services.knowledge_polling_service.process_pending_knowledge_task",
            "schedule": float(settings.KB_POLLING_INTERVAL_SEC),  # 默认每 5 分钟，可由 env 覆盖
        },
        "knowledge-health-check": {
            "task": "app.services.knowledge_evolution_tasks.health_check_knowledge_base",
            "schedule": 12 * 3600.0,  # 每12小时
        },
        "entity-fusion-daily": {
            "task": "app.services.knowledge_evolution_tasks.fuse_entities_task",
            "schedule": 24 * 3600.0,  # 每日实体融合
        },
        "auto-purge-trash": {
            "task": "app.services.task_service.auto_purge_trash_task",
            # 2026-06-03 教训 v2：4h 调度意味着任务最坏要等 4h 才被清理，
            # 用户看到 auto_delete_at 过了但任务还在（延迟达数小时），困惑。
            # 改为 1h 调度，最大延迟 1h（retention=3天时仅 1.4% 误差），
            # 用户体验上等同于"准点清理"。权衡：每天 24 次 DB 扫描，可忽略。
            "schedule": 3600.0,  # 每1小时清理过期垃圾桶（retention=3天时）
        },
        # 2026-06-12 防御机制：每 10 分钟清理超 1h 且未收到任何 chunk 的孤儿会议
        "cleanup-orphan-meetings": {
            "task": "app.services.orphan_meeting_cleanup.cleanup_orphan_meetings",
            "schedule": 600.0,  # 10 分钟
        },
        # 2026-06-30 #043 Phase 7: chat_sessions 软删除 30 天物理清除
        # 对齐 task 垃圾桶 1h 调度频率（CLAUDE.md 2026-06-03 教训：1h 粒度是准点清理的合理上限）
        "chat-history-cleanup-soft-deleted": {
            "task": "app.services.chat_history_tasks.cleanup_soft_deleted_sessions_task",
            "schedule": 3600.0,  # 每 1 小时扫描（retention=30 天时误差 < 0.14%）
        },
        # 2026-07-01 课题组网盘 PR1: drive 文件 + 孤儿 folder 3 天物理清除
        # 对齐 task/chat 清理模式 + 1h 调度频率
        "drive-cleanup-expired": {
            "task": "app.services.drive_cleanup_tasks.cleanup_expired_drive_files_task",
            "schedule": 3600.0,  # 每 1 小时扫描（retention=3 天时误差 < 1.4%）
        },
        # W72 B-3: Drive PR5 分片上传会话 24h TTL, 每小时清临时 chunk + DB row
        "drive-chunked-upload-cleanup-hourly": {
            "task": "app.services.drive_chunked_upload_tasks.cleanup_expired_uploads_task",
            "schedule": 3600.0,
        },
        # 2026-07-02 v2 PR6-P9: file_mentions 通知 30 天物理清除
        # 一刀切 (is_read 不分), 24h 调度对齐 task 垃圾桶节奏 (CLAUDE.md 2026-06-03 教训)
        "file-mention-cleanup-old": {
            "task": "app.services.file_mention_tasks.cleanup_old_mentions_task",
            "schedule": 86400.0,  # 每 24 小时扫描 (retention=30 天时误差 < 1.4%)
        },
        # 2026-07-20 W2 T3 P2-A: chat_share 过期主动清理 (24h Redis TTL 失效 PG 行兜底)
        # 对齐 file_mention 24h 调度频率 (chat_share 本身 24h 过期, 主动清理立即生效)
        "chat-share-cleanup-expired": {
            "task": "app.services.chat_share_tasks.cleanup_expired_chat_shares_task",
            "schedule": 86400.0,  # 每 24 小时扫描 (chat_share 24h 过期语义对齐)
        },
        # 2026-07-24 W68 第 7 批 B-1: Drive v2 PR10 协同编辑 Y.Doc snapshot 周期刷盘
        "drive-collab-flush-ydoc": {
            "task": "app.services.drive_collab_tasks.flush_ydoc_state_task",
            "schedule": 30.0,  # 每 30s 把活跃文档 Y.Doc snapshot 刷盘 (设计 doc §4.2)
        },
        # 2026-07-24 W68 第 7 批 B-1: Drive v2 PR10 op log 7 天压缩 (审计窗口外删除)
        "drive-collab-compress-op-logs": {
            "task": "app.services.drive_collab_tasks.compress_op_logs_task",
            "schedule": 24 * 3600.0,  # 每天一次 (设计 doc §4.2: 凌晨 03:00 语义, beat 用间隔近似)
        },
        # 2026-07-24 W68 第 12 批 B-1: Drive v2 PR14 历史评论 path 慢速回填
        # 凌晨 02:00 低峰跑 (与 drive_collab_compress_op_logs 02:00 错开 1h)
        "drive-comments-path-backfill-daily": {
            "task": "app.services.drive_comments_path_backfill_tasks.backfill_paths_task",
            "schedule": 24 * 3600.0,  # 每天 02:00 (beat 用 24h 间隔近似)
        },
        # 2026-07-27 W71 B-3: qa-bench auto_intake_rollback daily (派生新任务, 升级 scripts/auto_intake_rollback.py CLI)
        # 对齐 drive_cleanup / file_mention 24h 调度 (rollback_count 喂 KbMonitorView, knowledge API §rollback_count)
        "qa-bench-auto-intake-rollback-daily": {
            "task": "app.services.qa_bench_tasks.auto_intake_rollback_task",
            "schedule": 24 * 3600.0,  # 每天 04:00 (beat 用 24h 间隔近似)
        },
        # W86 mini-11 D fix P1-5: audit_log 90 天物理清除 (cleanup_old_logs 之前未注册)
        # 对齐 file_mention / chat_share 24h 调度 (audit_log 默认 retention=30 天)
        "cleanup-old-audit-logs-daily": {
            "task": "app.services.audit_service.cleanup_old_logs",
            "schedule": 24 * 3600.0,  # 每天 05:00 (beat 用 24h 间隔近似)
        },
        # W89 DERIVE-04: 恢复 W86 heartbeat；W87 grand-closure merge 曾误删注册。
        "analytics-heartbeat-every-5-min": {
            "task": "app.services.analytics_tasks.analytics_heartbeat",
            "schedule": 300.0,
        },
    },
)

# 2026-06-02 修复：autodiscover_tasks 默认 related_name='tasks'，会尝试 import
# {package}.tasks 子模块，但本项目任务直接在包内（如 post_meeting_tasks.py 不是
# tasks.py），autodiscover 静默失败导致 worker [tasks] 列表缺少任务。
# 改用显式 imports 配置，强制 worker 启动时 import 这些模块
celery_app.conf.imports = [
    "app.services.reminder_service",
    "app.services.post_meeting_tasks",
    "app.services.memory_service",
    "app.services.knowledge_evolution_tasks",
    "app.services.task_service",
    "app.services.orphan_meeting_cleanup",
    "app.services.agent_trace_tasks",  # 2026-06-12 可观测性
    "app.services.content_formatter_service",  # 2026-06-20 v28 step 18 异步重排
    "app.services.paper_layout_service",  # v28 step 105 vision 看整篇论文
    "app.services.embedding_recalc",  # v29 Qwen3-Embedding 全量重算
    "app.services.knowledge_service",  # 2026-06-29 修复 #257 异步分析
    "app.services.knowledge_polling_service",  # pending knowledge 每 5 分钟后台处理
    "app.services.chat_history_tasks",  # 2026-06-30 #043 Phase 7 软删除 30 天清理
    "app.services.drive_cleanup_tasks",  # 2026-07-01 课题组网盘 PR1 软删除 3 天清理
    "app.services.thumbnail_tasks",  # 2026-07-01 课题组网盘 PR5 缩略图生成
    "app.services.storage_tasks",  # 2026-07-01 课题组网盘 PR5 配额重算 + 分片 session 清理
    "app.services.drive_chunked_upload_tasks",  # W72 B-3 alembic 080 分片上传 24h 清理
    "app.services.file_mention_tasks",  # 2026-07-02 v2 PR6-P9 通知 30 天清理
    "app.services.chat_share_tasks",  # 2026-07-20 W2 T3 P2-A 过期 share 清理
    "app.services.drive_collab_tasks",  # 2026-07-24 W68 第 7 批 B-1 Drive v2 PR10 协同编辑刷盘
    "app.services.drive_comments_path_backfill_tasks",  # 2026-07-24 W68 第 12 批 B-1 Drive v2 PR14 path 回填
    "app.services.qa_bench_tasks",  # 2026-07-27 W71 B-3 qa-bench 7 天 auto_intake_rollback Celery task
    "app.services.audit_service",  # W86 mini-11 D fix P1-5: cleanup_old_logs 注册 Celery beat
    "app.services.analytics_tasks",  # W89 DERIVE-04: 恢复检索质量数据源心跳注册
    "app.wechat.scheduler",
]
# 保留 autodiscover_tasks 作 fallback（不传 related_name 让它能 import 主模块）
celery_app.autodiscover_tasks(
    [
        "app.services.reminder_service",
        "app.services.post_meeting_tasks",
        "app.services.memory_service",
        "app.services.knowledge_evolution_tasks",
        "app.services.task_service",
        "app.services.orphan_meeting_cleanup",
        "app.services.agent_trace_tasks",  # 2026-06-12
        "app.services.content_formatter_service",  # 2026-06-20 v28 step 18
        "app.services.paper_layout_service",  # v28 step 105
        "app.services.knowledge_service",  # 2026-06-29 修复 #257
        "app.services.knowledge_polling_service",  # pending knowledge 后台处理
        "app.services.chat_history_tasks",  # 2026-06-30 #043 Phase 7 软删除 30 天清理
        "app.services.drive_cleanup_tasks",  # 2026-07-01 课题组网盘 PR1 软删除 3 天清理
        "app.services.drive_chunked_upload_tasks",  # W72 B-3 alembic 080 分片上传清理
        "app.services.drive_collab_tasks",  # 2026-07-24 W68 第 7 批 B-1 Drive v2 PR10 协同编辑刷盘
        "app.services.drive_comments_path_backfill_tasks",  # 2026-07-24 W68 第 12 批 B-1 Drive v2 PR14 path 回填
        "app.services.qa_bench_tasks",  # 2026-07-27 W71 B-3 qa-bench 7 天 auto_intake_rollback Celery task
        "app.services.audit_service",  # W86 mini-11 D fix P1-5: cleanup_old_logs 注册
        "app.services.analytics_tasks",  # W89 DERIVE-04: 恢复检索质量数据源心跳注册
        "app.wechat.scheduler",
    ],
    related_name=None,
)


# ── W87-H-1: Celery signal 接 contextvars ─────────────────────────
# (派工 v6 §5 反馈类 20.28: task_id 必 request_id 解耦注入)
# task_prerun: 入口设 task_id (worker 进程内单 task 生命周期)
# task_postrun: 出口重置 (防御性, ContextVar 在 worker 进程 thread-local 自动失效)
# 注意: Celery prefork worker 是多进程, 每 task 自带 ContextVar 上下文
# 信号不会跨进程泄漏 — 但同一进程内串行 task 间需确保 reset, 防止上一 task 的 task_id 污染


@signals.task_prerun.connect
def _task_prerun_set_task_id(sender=None, task_id=None, **kwargs):
    """Celery task 入口设 task_id contextvars."""
    set_task_id(task_id or sender.request.id if hasattr(sender, "request") else None)


@signals.task_postrun.connect
def _task_postrun_clear_task_id(sender=None, task_id=None, **kwargs):
    """Celery task 出口清 task_id (防御性, 防止 worker 进程内 task 间污染)."""
    # 用 token reset 需要保留, 但 set(None) 更直接 (worker 进程即将执行下一 task)
    set_task_id(None)
