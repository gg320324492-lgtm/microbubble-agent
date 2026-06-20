from celery import Celery

from app.config import settings

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
        "app.wechat.scheduler",
    ],
    related_name=None,
)
