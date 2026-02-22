"""
Repository pattern for all database operations.
Each repository handles CRUD for a specific domain entity.
"""

from typing import List, Optional, Dict, Any, Sequence
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import (
    Site, Page, Link, Score, Issue, Keyword, CrawlJob,
    JobStatus, IssueSeverity
)
from core.logging import get_logger

logger = get_logger(__name__)


class SiteRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, domain: str, root_url: str, settings_data: dict = None) -> Site:
        site = Site(
            domain=domain,
            root_url=root_url,
            settings=settings_data or {}
        )
        self.db.add(site)
        await self.db.flush()
        await self.db.refresh(site)
        return site

    async def get_by_id(self, site_id: UUID) -> Optional[Site]:
        result = await self.db.execute(select(Site).where(Site.id == site_id))
        return result.scalar_one_or_none()

    async def get_by_domain(self, domain: str) -> Optional[Site]:
        result = await self.db.execute(select(Site).where(Site.domain == domain))
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 50) -> Sequence[Site]:
        result = await self.db.execute(
            select(Site).where(Site.is_active == True)
            .offset(skip).limit(limit).order_by(Site.created_at.desc())
        )
        return result.scalars().all()

    async def update(self, site_id: UUID, **kwargs) -> Optional[Site]:
        await self.db.execute(
            update(Site).where(Site.id == site_id)
            .values(**kwargs, updated_at=datetime.utcnow())
        )
        return await self.get_by_id(site_id)

    async def update_page_count(self, site_id: UUID) -> None:
        count_result = await self.db.execute(
            select(func.count(Page.id)).where(Page.site_id == site_id)
        )
        count = count_result.scalar_one()
        await self.db.execute(
            update(Site).where(Site.id == site_id)
            .values(total_pages=count, last_crawled_at=datetime.utcnow())
        )


class CrawlJobRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, site_id: UUID, max_depth: int = 5, max_pages: int = 10000,
        use_js: bool = False, respect_robots: bool = True
    ) -> CrawlJob:
        job = CrawlJob(
            site_id=site_id,
            max_depth=max_depth,
            max_pages=max_pages,
            use_js_rendering=use_js,
            respect_robots=respect_robots,
        )
        self.db.add(job)
        await self.db.flush()
        await self.db.refresh(job)
        return job

    async def get_by_id(self, job_id: UUID) -> Optional[CrawlJob]:
        result = await self.db.execute(select(CrawlJob).where(CrawlJob.id == job_id))
        return result.scalar_one_or_none()

    async def update_status(self, job_id: UUID, status: JobStatus, **kwargs) -> None:
        values = {"status": status, "updated_at": datetime.utcnow(), **kwargs}
        await self.db.execute(
            update(CrawlJob).where(CrawlJob.id == job_id).values(**values)
        )

    async def increment_crawled(self, job_id: UUID, success: bool = True) -> None:
        if success:
            await self.db.execute(
                update(CrawlJob).where(CrawlJob.id == job_id)
                .values(pages_crawled=CrawlJob.pages_crawled + 1)
            )
        else:
            await self.db.execute(
                update(CrawlJob).where(CrawlJob.id == job_id)
                .values(pages_failed=CrawlJob.pages_failed + 1)
            )

    async def get_recent_for_site(self, site_id: UUID, limit: int = 10) -> Sequence[CrawlJob]:
        result = await self.db.execute(
            select(CrawlJob).where(CrawlJob.site_id == site_id)
            .order_by(CrawlJob.created_at.desc()).limit(limit)
        )
        return result.scalars().all()


class PageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert(self, site_id: UUID, url: str, **data) -> Page:
        """Create or update a page record."""
        result = await self.db.execute(
            select(Page).where(and_(Page.site_id == site_id, Page.url == url))
        )
        page = result.scalar_one_or_none()
        if page:
            for key, value in data.items():
                setattr(page, key, value)
            page.updated_at = datetime.utcnow()
        else:
            page = Page(site_id=site_id, url=url, **data)
            self.db.add(page)
        await self.db.flush()
        await self.db.refresh(page)
        return page

    async def get_by_url(self, site_id: UUID, url: str) -> Optional[Page]:
        result = await self.db.execute(
            select(Page).where(and_(Page.site_id == site_id, Page.url == url))
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, page_id: UUID) -> Optional[Page]:
        result = await self.db.execute(select(Page).where(Page.id == page_id))
        return result.scalar_one_or_none()

    async def get_for_site(
        self, site_id: UUID, skip: int = 0, limit: int = 100,
        status_code: Optional[int] = None
    ) -> Sequence[Page]:
        query = select(Page).where(Page.site_id == site_id)
        if status_code:
            query = query.where(Page.status_code == status_code)
        result = await self.db.execute(
            query.offset(skip).limit(limit).order_by(Page.crawled_at.desc())
        )
        return result.scalars().all()

    async def count_for_site(self, site_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count(Page.id)).where(Page.site_id == site_id)
        )
        return result.scalar_one()

    async def get_pages_missing_titles(self, site_id: UUID) -> Sequence[Page]:
        result = await self.db.execute(
            select(Page).where(and_(Page.site_id == site_id, Page.title == None))
        )
        return result.scalars().all()


class LinkRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def bulk_insert(self, links: List[Dict[str, Any]]) -> None:
        """Bulk insert links for performance."""
        if not links:
            return
        self.db.add_all([Link(**link_data) for link_data in links])
        await self.db.flush()

    async def get_for_page(self, page_id: UUID) -> Sequence[Link]:
        result = await self.db.execute(
            select(Link).where(Link.source_page_id == page_id)
        )
        return result.scalars().all()

    async def count_inbound(self, page_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count(Link.id)).where(
                and_(Link.target_page_id == page_id, Link.is_internal == True)
            )
        )
        return result.scalar_one()

    async def get_broken_links(self, site_id: UUID) -> Sequence[Link]:
        result = await self.db.execute(
            select(Link).where(and_(Link.site_id == site_id, Link.is_broken == True))
        )
        return result.scalars().all()


class ScoreRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_site_score(self, site_id: UUID, crawl_job_id: UUID, scores: Dict) -> Score:
        result = await self.db.execute(
            select(Score).where(and_(Score.site_id == site_id, Score.page_id == None))
        )
        score = result.scalar_one_or_none()
        if score:
            for key, val in scores.items():
                setattr(score, key, val)
            score.scored_at = datetime.utcnow()
            score.crawl_job_id = crawl_job_id
        else:
            score = Score(site_id=site_id, crawl_job_id=crawl_job_id, **scores)
            self.db.add(score)
        await self.db.flush()
        await self.db.refresh(score)
        return score

    async def create_page_score(self, site_id: UUID, page_id: UUID, crawl_job_id: UUID, scores: Dict) -> Score:
        score = Score(site_id=site_id, page_id=page_id, crawl_job_id=crawl_job_id, **scores)
        self.db.add(score)
        await self.db.flush()
        await self.db.refresh(score)
        return score

    async def get_site_score(self, site_id: UUID) -> Optional[Score]:
        result = await self.db.execute(
            select(Score).where(and_(Score.site_id == site_id, Score.page_id == None))
            .order_by(Score.scored_at.desc())
        )
        return result.scalars().first()


class IssueRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def bulk_create(self, issues: List[Dict[str, Any]]) -> None:
        if not issues:
            return
        self.db.add_all([Issue(**issue_data) for issue_data in issues])
        await self.db.flush()

    async def get_for_site(
        self, site_id: UUID, severity: Optional[IssueSeverity] = None,
        resolved: bool = False, skip: int = 0, limit: int = 100
    ) -> Sequence[Issue]:
        query = select(Issue).where(
            and_(Issue.site_id == site_id, Issue.is_resolved == resolved)
        )
        if severity:
            query = query.where(Issue.severity == severity)
        result = await self.db.execute(
            query.offset(skip).limit(limit).order_by(Issue.created_at.desc())
        )
        return result.scalars().all()

    async def count_by_severity(self, site_id: UUID) -> Dict[str, int]:
        result = await self.db.execute(
            select(Issue.severity, func.count(Issue.id))
            .where(and_(Issue.site_id == site_id, Issue.is_resolved == False))
            .group_by(Issue.severity)
        )
        return {row[0]: row[1] for row in result.all()}

    async def delete_for_job(self, crawl_job_id: UUID) -> None:
        await self.db.execute(
            delete(Issue).where(Issue.crawl_job_id == crawl_job_id)
        )


class KeywordRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def bulk_upsert(self, site_id: UUID, keywords: List[Dict[str, Any]]) -> None:
        for kw_data in keywords:
            result = await self.db.execute(
                select(Keyword).where(
                    and_(
                        Keyword.site_id == site_id,
                        Keyword.keyword == kw_data["keyword"]
                    )
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                for k, v in kw_data.items():
                    setattr(existing, k, v)
                existing.updated_at = datetime.utcnow()
            else:
                kw = Keyword(site_id=site_id, **kw_data)
                self.db.add(kw)
        await self.db.flush()

    async def get_opportunities(
        self, site_id: UUID, limit: int = 50, min_score: float = 0.0
    ) -> Sequence[Keyword]:
        result = await self.db.execute(
            select(Keyword).where(
                and_(
                    Keyword.site_id == site_id,
                    Keyword.is_opportunity == True,
                    Keyword.opportunity_score >= min_score
                )
            ).order_by(Keyword.opportunity_score.desc()).limit(limit)
        )
        return result.scalars().all()

    async def get_all_for_site(self, site_id: UUID, limit: int = 500) -> Sequence[Keyword]:
        result = await self.db.execute(
            select(Keyword).where(Keyword.site_id == site_id)
            .order_by(Keyword.frequency.desc()).limit(limit)
        )
        return result.scalars().all()