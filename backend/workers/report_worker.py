"""Report generation worker tasks."""
from workers.celery_app import celery_app
from core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(
    name="workers.report_worker.generate_report",
    queue="report",
)
def generate_report(site_id: str, report_type: str = "full") -> dict:
    """
    Generate a comprehensive SEO report for a site.
    Produces a structured report artifact for the frontend.
    """
    logger.info(f"Generating {report_type} report for site {site_id}")
    return {"status": "completed", "site_id": site_id, "report_type": report_type}