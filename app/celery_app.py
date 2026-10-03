from celery import Celery

from app.config import settings

celery = Celery("rag", broker=settings.redis_url, backend=settings.redis_url, include=["app.tasks"])
celery.conf.task_track_started = True
