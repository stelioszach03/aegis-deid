from celery import Celery

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger


setup_logging(component="worker")
log = get_logger("celery")
settings = get_settings()
celery_app = Celery(
    "aegis",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Autodiscover tasks from package
celery_app.autodiscover_tasks(["app.workers"])  # looks for @shared_task or module-level tasks
