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
            "schedule": 6 * 3600.0,  # 每6小时清理过期垃圾桶
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
    "app.wechat.scheduler",
]
# 保留 autodiscover_tasks 作 fallback（不传 related_name 让它能 import 主模块）
celery_app.autodiscover_tasks(
    [
        "app.services.reminder_service",
        "app.services.post_meeting_tasks",
        "app.services.memory_service",
        "app.services.knowledge_evolution_tasks",
        "app.wechat.scheduler",
    ],
    related_name=None,
)
