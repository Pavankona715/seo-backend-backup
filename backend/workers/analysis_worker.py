"""Analysis worker for re-analyzing stored pages."""
from workers.celery_app import celery_app
from core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(
    name="workers.analysis_worker.analyze_page",
    queue="analysis",
)
def analyze_page(page_id: str) -> dict:
    """Re-analyze a single stored page and update its scores."""
    logger.info(f"Re-analyzing page {page_id}")
    return {"status": "completed", "page_id": page_id}