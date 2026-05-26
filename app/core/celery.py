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
    },
)

celery_app.autodiscover_tasks(
    [
        "app.services.reminder_service",
        "app.wechat.scheduler",
        "app.services.memory_service",
        "app.services.knowledge_evolution_tasks",
    ]
)
