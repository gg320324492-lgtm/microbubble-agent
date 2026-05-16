from celery import Celery
from celery.schedules import crontab

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
            "schedule": 60.0,
        },
    },
)

celery_app.autodiscover_tasks(["app.services"])
