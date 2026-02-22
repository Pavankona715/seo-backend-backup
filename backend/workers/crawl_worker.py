"""
Crawl worker - orchestrates the full crawl → analyze → score → recommend pipeline.
Runs as a Celery task with full async support via asyncio.
"""

import asyncio
import json
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from celery import Task
from celery.utils.log import get_task_logger

from workers.celery_app import celery_app
from database.session import get_db_context
from database.repositories import (
    SiteRepository, CrawlJobRepository, PageRepository,
    LinkRepository, ScoreRepository, IssueRepository, KeywordRepository
)
from database.models import JobStatus, IssueSeverity
from crawler.crawler import AsyncCrawler, CrawlResult
from analyzer.analyzer import SEOAnalyzer
from scorer.scorer import SEOScorer, PageScore
from recommendations.engine import RecommendationEngine
from keyword_engine.engine import KeywordEngine
from core.config import settings
from core.logging import get_logger

logger = get_task_logger(__name__)


class CrawlTask(Task):
    """Base task with shared resources."""
    abstract = True


@celery_app.task(
    bind=True,
    base=CrawlTask,
    name="workers.crawl_worker.run_crawl_job",
    queue="crawl",
    max_retries=1,
    soft_time_limit=7200,  # 2 hour soft limit
    time_limit=7500,       # 2h05 hard limit
)
def run_crawl_job(self, crawl_job_id: str, site_id: str) -> Dict[str, Any]:
    """
    Main crawl job task. Orchestrates the complete SEO analysis pipeline:
    1. Crawl all pages
    2. Analyze each page (SEO extraction)
    3. Score pages individually
    4. Generate recommendations / issues
    5. Compute keyword opportunities
    6. Aggregate site-level scores
    """
    return asyncio.get_event_loop().run_until_complete(
        _run_crawl_job_async(self, crawl_job_id, site_id)
    )


async def _run_crawl_job_async(task, crawl_job_id: str, site_id: str) -> Dict[str, Any]:
    """Async implementation of the crawl job."""
    job_uuid = UUID(crawl_job_id)
    site_uuid = UUID(site_id)

    async with get_db_context() as db:
        crawl_repo = CrawlJobRepository(db)
        site_repo = SiteRepository(db)

        # Update job status to running
        await crawl_repo.update_status(
            job_uuid,
            JobStatus.RUNNING,
            started_at=datetime.utcnow(),
            celery_task_id=task.request.id,
        )

        site = await site_repo.get_by_id(site_uuid)
        if not site:
            await crawl_repo.update_status(
                job_uuid, JobStatus.FAILED,
                error_message="Site not found"
            )
            return {"status": "failed", "error": "Site not found"}

        job = await crawl_repo.get_by_id(job_uuid)
        if not job:
            return {"status": "failed", "error": "Job not found"}

    analyzer = SEOAnalyzer(base_domain=site.domain)
    scorer = SEOScorer()
    rec_engine = RecommendationEngine()

    # Shared state across pages (needs thread-safe access in async context)
    analyzed_pages = []
    all_page_scores = []
    all_issues = []
    all_links = []

    async def on_page_crawled(crawl_result: CrawlResult, depth: int) -> None:
        """Callback invoked for each successfully crawled page."""
        nonlocal analyzed_pages, all_page_scores, all_issues

        # Analyze page
        analyzed = analyzer.analyze(crawl_result, depth)

        async with get_db_context() as db:
            page_repo = PageRepository(db)
            link_repo = LinkRepository(db)
            crawl_r = CrawlJobRepository(db)

            # Upsert page record
            page = await page_repo.upsert(
                site_id=site_uuid,
                url=analyzed.url,
                crawl_job_id=job_uuid,
                canonical_url=analyzed.canonical_url,
                status_code=analyzed.status_code,
                depth=depth,
                is_indexable=analyzed.is_indexable,
                is_canonical=analyzed.is_canonical,
                title=analyzed.title,
                title_length=analyzed.title_length,
                meta_description=analyzed.meta_description,
                meta_description_length=analyzed.meta_description_length,
                meta_robots=analyzed.meta_robots,
                canonical_tag=analyzed.canonical_tag,
                h1_tags=analyzed.h1_tags,
                h2_tags=analyzed.h2_tags,
                h3_tags=analyzed.h3_tags,
                h4_tags=analyzed.h4_tags,
                h5_tags=analyzed.h5_tags,
                h6_tags=analyzed.h6_tags,
                word_count=analyzed.word_count,
                content_text=analyzed.content_text[:50000] if analyzed.content_text else None,
                reading_time_seconds=analyzed.reading_time_seconds,
                text_html_ratio=analyzed.text_html_ratio,
                language=analyzed.language,
                load_time_ms=analyzed.load_time_ms,
                page_size_bytes=analyzed.page_size_bytes,
                has_schema_markup=analyzed.has_schema_markup,
                schema_types=analyzed.schema_types,
                has_open_graph=analyzed.has_open_graph,
                has_twitter_card=analyzed.has_twitter_card,
                has_hreflang=analyzed.has_hreflang,
                is_https=analyzed.is_https,
                has_viewport_meta=analyzed.has_viewport_meta,
                total_images=analyzed.total_images,
                images_missing_alt=analyzed.images_missing_alt,
                images_with_alt=analyzed.images_with_alt,
                internal_links_count=analyzed.internal_links_count,
                external_links_count=analyzed.external_links_count,
                structured_data=analyzed.structured_data,
                open_graph_data=analyzed.open_graph_data,
                twitter_card_data=analyzed.twitter_card_data,
                keyword_frequencies=analyzed.keyword_frequencies,
            )

            # Store links
            if analyzed.internal_links:
                link_records = [
                    {
                        "site_id": site_uuid,
                        "source_page_id": page.id,
                        "target_url": link["url"],
                        "anchor_text": link.get("anchor_text", ""),
                        "is_internal": True,
                        "is_nofollow": link.get("is_nofollow", False),
                    }
                    for link in analyzed.internal_links[:200]  # Cap per page
                ]
                await link_repo.bulk_insert(link_records)

            # Score the page
            page_score = scorer.score_page(analyzed, inbound_link_count=0)

            # Generate recommendations (issues)
            page_recs = rec_engine.generate_page_recommendations(analyzed)
            issue_records = [
                {
                    "site_id": site_uuid,
                    "page_id": page.id,
                    "crawl_job_id": job_uuid,
                    "issue_type": rec.issue_type,
                    "severity": IssueSeverity(rec.severity.value if hasattr(rec.severity, 'value') else rec.severity),
                    "title": rec.title,
                    "description": rec.description,
                    "recommendation": rec.recommendation,
                    "fix_instructions": rec.fix_instructions,
                    "impact_description": rec.impact_description,
                    "affected_element": rec.affected_element,
                }
                for rec in page_recs
            ]

            issue_repo = IssueRepository(db)
            await issue_repo.bulk_create(issue_records)

            # Update crawl progress
            await crawl_r.increment_crawled(job_uuid, success=True)

        analyzed_pages.append(analyzed)
        all_page_scores.append(page_score)

        logger.info(f"Analyzed: {analyzed.url} | Score: {page_score.overall_score:.1f}")

    # Run the crawler
    try:
        async with AsyncCrawler(
            start_url=site.root_url,
            site_id=site_uuid,
            crawl_job_id=job_uuid,
            max_depth=job.max_depth,
            max_pages=job.max_pages,
            use_js_rendering=job.use_js_rendering,
            respect_robots=job.respect_robots,
            max_concurrent=settings.CRAWLER_MAX_CONCURRENT // 4,
            rate_limit_rps=settings.CRAWLER_RATE_LIMIT_RPS,
            on_page_crawled=on_page_crawled,
        ) as crawler:
            stats = await crawler.crawl()

        # Post-crawl: aggregate scores and keyword opportunities
        async with get_db_context() as db:
            site_repo = SiteRepository(db)
            score_repo = ScoreRepository(db)
            kw_repo = KeywordRepository(db)
            crawl_repo = CrawlJobRepository(db)
            issue_repo = IssueRepository(db)

            # Aggregate site score
            site_score = scorer.aggregate_site_score(all_page_scores)
            await score_repo.upsert_site_score(
                site_uuid, job_uuid,
                {
                    "overall_score": site_score.overall_score,
                    "technical_score": site_score.technical_score,
                    "content_score": site_score.content_score,
                    "authority_score": site_score.authority_score,
                    "linking_score": site_score.linking_score,
                    "ai_visibility_score": site_score.ai_visibility_score,
                    "technical_breakdown": site_score.technical_breakdown,
                    "content_breakdown": site_score.content_breakdown,
                    "linking_breakdown": site_score.linking_breakdown,
                }
            )

            # Compute keyword opportunities
            kw_engine = KeywordEngine()
            page_kw_data = [(p.url, p.keyword_frequencies) for p in analyzed_pages if p.keyword_frequencies]
            opportunities = kw_engine.aggregate_site_keywords(page_kw_data)

            kw_records = [
                {
                    "keyword": opp.keyword,
                    "frequency": opp.frequency,
                    "density": opp.density,
                    "estimated_volume": opp.estimated_volume,
                    "estimated_difficulty": opp.estimated_difficulty,
                    "estimated_ctr": opp.estimated_ctr,
                    "current_rank": opp.current_rank,
                    "rank_gap": opp.rank_gap,
                    "opportunity_score": opp.opportunity_score,
                    "is_opportunity": opp.is_opportunity,
                    "crawl_job_id": job_uuid,
                }
                for opp in opportunities[:300]
            ]
            await kw_repo.bulk_upsert(site_uuid, kw_records)

            # Generate site-wide recommendations
            site_recs = rec_engine.generate_site_recommendations(analyzed_pages, {})
            site_issue_records = [
                {
                    "site_id": site_uuid,
                    "crawl_job_id": job_uuid,
                    "issue_type": rec.issue_type,
                    "severity": IssueSeverity(rec.severity.value if hasattr(rec.severity, 'value') else rec.severity),
                    "title": rec.title,
                    "description": rec.description,
                    "recommendation": rec.recommendation,
                    "fix_instructions": rec.fix_instructions,
                    "impact_description": rec.impact_description,
                    "affected_element": rec.affected_element,
                }
                for rec in site_recs
            ]
            await issue_repo.bulk_create(site_issue_records)

            # Update site stats
            await site_repo.update_page_count(site_uuid)

            # Mark job complete
            await crawl_repo.update_status(
                job_uuid,
                JobStatus.COMPLETED,
                completed_at=datetime.utcnow(),
                pages_crawled=stats["pages_crawled"],
                pages_failed=stats["pages_failed"],
            )

        logger.info(
    f"Crawl job {crawl_job_id} completed | pages_crawled={stats['pages_crawled']} site_score={site_score.overall_score:.1f}"
)
        return {
            "status": "completed",
            "pages_crawled": stats["pages_crawled"],
            "pages_failed": stats["pages_failed"],
            "site_score": site_score.overall_score,
        }

    except Exception as e:
        logger.error(f"Crawl job {crawl_job_id} failed: {e}", exc_info=True)
        async with get_db_context() as db:
            crawl_repo = CrawlJobRepository(db)
            await crawl_repo.update_status(
                job_uuid,
                JobStatus.FAILED,
                completed_at=datetime.utcnow(),
                error_message=str(e)[:2000],
            )
        raise