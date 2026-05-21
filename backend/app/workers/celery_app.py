from celery import Celery
from kombu import Queue

from app.core.config import settings

celery_app = Celery(
    "gstsense",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.scan_tasks",
        "app.workers.itc_tasks",
        "app.workers.notice_tasks",
        "app.workers.report_tasks",
        "app.workers.scheduler",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_queues=(
        Queue("high_priority"),  # CA firm and Growth plan scans
        Queue("normal"),         # SMB plan scans
        Queue("low"),            # Notifications and PDF generation
    ),
    task_default_queue="normal",
    task_routes={
        "app.workers.scan_tasks.process_scan_task": {"queue": "normal"},
        "app.workers.itc_tasks.process_itc_task": {"queue": "normal"},
        "app.workers.notice_tasks.generate_notice_draft_task": {"queue": "normal"},
        "app.workers.scheduler.send_filing_reminders": {"queue": "low"},
        "app.workers.scheduler.reset_invoice_counts": {"queue": "low"},
        "app.workers.scheduler.update_compliance_scores": {"queue": "low"},
        "app.workers.scheduler.process_monthly_payouts": {"queue": "low"},
        "app.workers.report_tasks.generate_bulk_ca_report_task": {"queue": "low"},
    },
    worker_max_tasks_per_child=50,
    task_soft_time_limit=240,
    task_time_limit=300,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    redbeat_redis_url=settings.REDIS_URL,
)
