# This ensures the Celery app is loaded when Django starts,
# so @shared_task decorators in other apps can reference it.
from config.celery import app as celery_app

__all__ = ["celery_app"]
