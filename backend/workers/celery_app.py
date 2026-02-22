"""
Celery application configuration for async task processing.
Handles crawl job orchestration, analysis, and scoring tasks.
"""

from celery import Celery
from core.config import settings

celery_app = Celery(
    "seo_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "workers.crawl_worker",
        "workers.analysis_worker",
        "workers.report_worker",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task routing
    task_routes={
        "workers.crawl_worker.run_crawl_job": {"queue": "crawl"},
        "workers.analysis_worker.analyze_page": {"queue": "analysis"},
        "workers.report_worker.generate_report": {"queue": "report"},
    },

    # Worker settings
    worker_max_tasks_per_child=settings.CELERY_MAX_TASKS_PER_CHILD,
    worker_prefetch_multiplier=1,  # Fair task distribution
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,

    # Task settings
    task_acks_late=True,  # Acknowledge after completion (safe for retries)
    task_reject_on_worker_lost=True,
    task_track_started=True,

    # Result settings
    result_expires=86400,  # 24 hours

    # Retry settings
    task_default_retry_delay=30,
    task_max_retries=3,

    # Queues
    task_default_queue="default",
    task_queues={
        "crawl": {"exchange": "crawl", "binding_key": "crawl"},
        "analysis": {"exchange": "analysis", "binding_key": "analysis"},
        "report": {"exchange": "report", "binding_key": "report"},
        "default": {"exchange": "default", "binding_key": "default"},
    },

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,

    # Beat schedule (periodic tasks)
    beat_schedule={},
)