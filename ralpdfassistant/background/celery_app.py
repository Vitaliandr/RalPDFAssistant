from celery import Celery

from ralpdfassistant.settings import settings

celery = Celery(
    "ralpdfassistant",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["ralpdfassistant.background.tasks"],
)
celery.conf.task_track_started = True
#иначе celery 6 перестанет ждать брокер при старте, а redis в compose поднимается позже
celery.conf.broker_connection_retry_on_startup = True
