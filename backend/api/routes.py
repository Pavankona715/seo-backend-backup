"""
FastAPI route handlers for all SEO platform API endpoints.
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import tldextract

from database.session import get_db
from database.repositories import (
    SiteRepository, CrawlJobRepository, PageRepository,
    IssueRepository, KeywordRepository, ScoreRepository
)
from database.models import IssueSeverity
from workers.crawl_worker import run_crawl_job
from api.schemas import (
    CrawlRequest, CrawlResponse, ReportResponse, PageDetail, PageSummary,
    IssuesResponse, IssueCountBySeverity, OpportunitiesResponse,
    ScoreSchema, CrawlJobSchema, SiteSchema, IssueSchema, KeywordSchema,
)
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ============================================================
# CRAWL ENDPOINTS
# ============================================================

@router.post(
    "/crawl",
    response_model=CrawlResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a new website crawl",
    tags=["Crawl"],
)
async def start_crawl(
    request: CrawlRequest,
    db: AsyncSession = Depends(get_db),
) -> CrawlResponse:
    """
    Initiates an async crawl job for the specified URL.
    Returns immediately with a job_id to track progress.
    """
    # Extract domain from URL
    ext = tldextract.extract(request.url)
    domain = f"{ext.domain}.{ext.suffix}"
    if ext.subdomain:
        domain = f"{ext.subdomain}.{domain}"

    site_repo = SiteRepository(db)
    crawl_repo = CrawlJobRepository(db)

    # Get or create site
    site = await site_repo.get_by_domain(domain)
    if not site:
        site = await site_repo.create(
            domain=domain,
            root_url=request.url,
        )
        logger.info(f"Created new site: {domain}")

    # Check for active running job
    recent_jobs = await crawl_repo.get_recent_for_site(site.id, limit=1)
    if recent_jobs and recent_jobs[0].status.value == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A crawl is already running for {domain}. Job ID: {recent_jobs[0].id}"
        )

    # Create crawl job record
    job = await crawl_repo.create(
        site_id=site.id,
        max_depth=request.max_depth,
        max_pages=request.max_pages,
        use_js=request.use_js_rendering,
        respect_robots=request.respect_robots,
    )

    # Dispatch Celery task
    celery_task = run_crawl_job.apply_async(
        args=[str(job.id), str(site.id)],
        queue="crawl",
    )

    # Update job with task ID
    await crawl_repo.update_status(
        job.id,
        job.status,
        celery_task_id=celery_task.id,
    )

    logger.info(f"Crawl job {job.id} dispatched for {domain}", task_id=celery_task.id)

    return CrawlResponse(
        job_id=job.id,
        site_id=site.id,
        status="pending",
        message=f"Crawl job started for {domain}. Track progress using the job_id.",
        domain=domain,
    )


@router.get(
    "/crawl/job/{job_id}",
    response_model=CrawlJobSchema,
    summary="Get crawl job status",
    tags=["Crawl"],
)
async def get_crawl_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CrawlJobSchema:
    """Get the status and progress of a crawl job."""
    repo = CrawlJobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Crawl job {job_id} not found")
    return job


# ============================================================
# REPORT ENDPOINTS
# ============================================================

@router.get(
    "/report/{domain}",
    response_model=ReportResponse,
    summary="Get SEO report for a domain",
    tags=["Reports"],
)
async def get_report(
    domain: str,
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    """
    Returns a comprehensive SEO report for a domain including:
    - Site info and crawl status
    - Aggregate SEO scores
    - Issue summary by severity
    - Top keyword opportunities
    - Recent crawl job info
    """
    site_repo = SiteRepository(db)
    site = await site_repo.get_by_domain(domain)
    if not site:
        raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found. Start a crawl first.")

    score_repo = ScoreRepository(db)
    issue_repo = IssueRepository(db)
    kw_repo = KeywordRepository(db)
    crawl_repo = CrawlJobRepository(db)
    page_repo = PageRepository(db)

    score = await score_repo.get_site_score(site.id)
    issue_counts = await issue_repo.count_by_severity(site.id)
    top_opportunities = await kw_repo.get_opportunities(site.id, limit=10)
    recent_jobs = await crawl_repo.get_recent_for_site(site.id, limit=1)
    page_count = await page_repo.count_for_site(site.id)

    severity_counts = IssueCountBySeverity(
        critical=issue_counts.get(IssueSeverity.CRITICAL, 0),
        high=issue_counts.get(IssueSeverity.HIGH, 0),
        medium=issue_counts.get(IssueSeverity.MEDIUM, 0),
        low=issue_counts.get(IssueSeverity.LOW, 0),
        info=issue_counts.get(IssueSeverity.INFO, 0),
    )

    return ReportResponse(
        domain=domain,
        site=site,
        score=score,
        issue_summary=severity_counts,
        recent_job=recent_jobs[0] if recent_jobs else None,
        top_opportunities=top_opportunities,
        pages_overview={
            "total_pages": page_count,
            "last_crawled": site.last_crawled_at.isoformat() if site.last_crawled_at else None,
        },
    )


# ============================================================
# PAGE ENDPOINTS
# ============================================================

@router.get(
    "/pages/{domain}",
    summary="List all pages for a domain",
    tags=["Pages"],
)
async def list_pages(
    domain: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    status_code: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Returns paginated list of crawled pages for a domain."""
    site_repo = SiteRepository(db)
    site = await site_repo.get_by_domain(domain)
    if not site:
        raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")

    page_repo = PageRepository(db)
    pages = await page_repo.get_for_site(site.id, skip=skip, limit=limit, status_code=status_code)
    total = await page_repo.count_for_site(site.id)

    return {
        "domain": domain,
        "total": total,
        "skip": skip,
        "limit": limit,
        "pages": [PageSummary.model_validate(p) for p in pages],
    }


@router.get(
    "/page/{page_id}",
    response_model=PageDetail,
    summary="Get detailed SEO data for a specific page",
    tags=["Pages"],
)
async def get_page(
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> PageDetail:
    """Returns complete SEO analysis data for a single page."""
    page_repo = PageRepository(db)
    page = await page_repo.get_by_id(page_id)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page {page_id} not found")
    return page


# ============================================================
# ISSUES ENDPOINTS
# ============================================================

@router.get(
    "/issues/{domain}",
    response_model=IssuesResponse,
    summary="Get all SEO issues for a domain",
    tags=["Issues"],
)
async def get_issues(
    domain: str,
    severity: Optional[str] = Query(None, description="Filter by severity: critical, high, medium, low, info"),
    resolved: bool = Query(False, description="Include resolved issues"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> IssuesResponse:
    """
    Returns all detected SEO issues for a domain.
    Filterable by severity and resolution status.
    """
    site_repo = SiteRepository(db)
    site = await site_repo.get_by_domain(domain)
    if not site:
        raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")

    issue_repo = IssueRepository(db)

    severity_enum = None
    if severity:
        try:
            severity_enum = IssueSeverity(severity.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid severity '{severity}'. Use: critical, high, medium, low, info"
            )

    issues = await issue_repo.get_for_site(
        site.id, severity=severity_enum, resolved=resolved,
        skip=skip, limit=limit
    )
    issue_counts = await issue_repo.count_by_severity(site.id)

    total = sum(issue_counts.values())

    return IssuesResponse(
        domain=domain,
        total_issues=total,
        counts_by_severity=IssueCountBySeverity(
            critical=issue_counts.get(IssueSeverity.CRITICAL, 0),
            high=issue_counts.get(IssueSeverity.HIGH, 0),
            medium=issue_counts.get(IssueSeverity.MEDIUM, 0),
            low=issue_counts.get(IssueSeverity.LOW, 0),
            info=issue_counts.get(IssueSeverity.INFO, 0),
        ),
        issues=[IssueSchema.model_validate(i) for i in issues],
    )


# ============================================================
# OPPORTUNITIES ENDPOINTS
# ============================================================

@router.get(
    "/opportunities/{domain}",
    response_model=OpportunitiesResponse,
    summary="Get keyword opportunities for a domain",
    tags=["Keywords"],
)
async def get_opportunities(
    domain: str,
    min_score: float = Query(0.0, ge=0.0, description="Minimum opportunity score"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> OpportunitiesResponse:
    """
    Returns keyword opportunities ranked by opportunity score.
    Opportunity Score = Volume × CTR × RankGap ÷ Difficulty
    """
    site_repo = SiteRepository(db)
    site = await site_repo.get_by_domain(domain)
    if not site:
        raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")

    kw_repo = KeywordRepository(db)
    opportunities = await kw_repo.get_opportunities(site.id, limit=limit, min_score=min_score)
    all_keywords = await kw_repo.get_all_for_site(site.id, limit=500)

    return OpportunitiesResponse(
        domain=domain,
        total_keywords=len(all_keywords),
        opportunities=[KeywordSchema.model_validate(kw) for kw in opportunities],
    )


# ============================================================
# SITES ENDPOINTS
# ============================================================

@router.get(
    "/sites",
    response_model=List[SiteSchema],
    summary="List all tracked sites",
    tags=["Sites"],
)
async def list_sites(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> List[SiteSchema]:
    """Returns all tracked sites."""
    repo = SiteRepository(db)
    sites = await repo.get_all(skip=skip, limit=limit)
    return sites


@router.get(
    "/sites/{site_id}",
    response_model=SiteSchema,
    summary="Get site by ID",
    tags=["Sites"],
)
async def get_site(
    site_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SiteSchema:
    """Get a single site by ID."""
    repo = SiteRepository(db)
    site = await repo.get_by_id(site_id)
    if not site:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return site


@router.get(
    "/scores/{domain}",
    response_model=ScoreSchema,
    summary="Get SEO scores for a domain",
    tags=["Scores"],
)
async def get_scores(
    domain: str,
    db: AsyncSession = Depends(get_db),
) -> ScoreSchema:
    """Returns the latest SEO score breakdown for a domain."""
    site_repo = SiteRepository(db)
    site = await site_repo.get_by_domain(domain)
    if not site:
        raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")

    score_repo = ScoreRepository(db)
    score = await score_repo.get_site_score(site.id)
    if not score:
        raise HTTPException(status_code=404, detail=f"No scores found for '{domain}'. Run a crawl first.")
    return score