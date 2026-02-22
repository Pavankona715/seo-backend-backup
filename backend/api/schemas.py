"""
Pydantic schemas for API request/response validation.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, HttpUrl, Field, field_validator


# ============================================================
# Request Schemas
# ============================================================

class CrawlRequest(BaseModel):
    url: str = Field(..., description="Starting URL to crawl")
    max_depth: int = Field(5, ge=1, le=10, description="Maximum crawl depth")
    max_pages: int = Field(1000, ge=1, le=50000, description="Maximum pages to crawl")
    use_js_rendering: bool = Field(False, description="Use Playwright for JS rendering")
    respect_robots: bool = Field(True, description="Respect robots.txt")
    rate_limit_rps: float = Field(5.0, ge=0.1, le=50.0, description="Requests per second")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            v = f"https://{v}"
        return v.rstrip("/")


# ============================================================
# Response Schemas
# ============================================================

class SiteSchema(BaseModel):
    id: UUID
    domain: str
    root_url: str
    sitemap_url: Optional[str] = None
    last_crawled_at: Optional[datetime] = None
    total_pages: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CrawlJobSchema(BaseModel):
    id: UUID
    site_id: UUID
    celery_task_id: Optional[str] = None
    status: str
    max_depth: int
    max_pages: int
    use_js_rendering: bool
    respect_robots: bool
    pages_crawled: int
    pages_failed: int
    pages_queued: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CrawlResponse(BaseModel):
    job_id: UUID
    site_id: UUID
    status: str
    message: str
    domain: str


class PageSummary(BaseModel):
    id: UUID
    url: str
    status_code: Optional[int] = None
    title: Optional[str] = None
    word_count: int
    depth: int
    is_indexable: bool
    internal_links_count: int
    crawled_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PageDetail(BaseModel):
    id: UUID
    url: str
    canonical_url: Optional[str] = None
    status_code: Optional[int] = None
    depth: int
    is_indexable: bool
    is_canonical: bool
    title: Optional[str] = None
    title_length: int
    meta_description: Optional[str] = None
    meta_description_length: int
    meta_robots: Optional[str] = None
    h1_tags: List[str] = []
    h2_tags: List[str] = []
    h3_tags: List[str] = []
    word_count: int
    reading_time_seconds: int
    text_html_ratio: float
    language: Optional[str] = None
    load_time_ms: Optional[int] = None
    page_size_bytes: Optional[int] = None
    has_schema_markup: bool
    schema_types: List[str] = []
    has_open_graph: bool
    has_twitter_card: bool
    has_hreflang: bool
    is_https: bool
    has_viewport_meta: bool
    total_images: int
    images_missing_alt: int
    images_with_alt: int
    internal_links_count: int
    external_links_count: int
    keyword_frequencies: Dict[str, int] = {}
    crawled_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ScoreBreakdownItem(BaseModel):
    avg_score: float
    max: float
    pct: float


class ScoreSchema(BaseModel):
    id: UUID
    site_id: UUID
    page_id: Optional[UUID] = None
    overall_score: float
    technical_score: float
    content_score: float
    authority_score: float
    linking_score: float
    ai_visibility_score: float
    technical_breakdown: Dict[str, Any] = {}
    content_breakdown: Dict[str, Any] = {}
    linking_breakdown: Dict[str, Any] = {}
    scored_at: datetime

    class Config:
        from_attributes = True


class IssueSchema(BaseModel):
    id: UUID
    site_id: UUID
    page_id: Optional[UUID] = None
    issue_type: str
    severity: str
    title: str
    description: str
    recommendation: Optional[str] = None
    fix_instructions: Optional[str] = None
    impact_description: Optional[str] = None
    affected_element: Optional[str] = None
    is_resolved: bool
    created_at: datetime

    class Config:
        from_attributes = True


class IssueCountBySeverity(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class IssuesResponse(BaseModel):
    domain: str
    total_issues: int
    counts_by_severity: IssueCountBySeverity
    issues: List[IssueSchema]


class KeywordSchema(BaseModel):
    id: UUID
    keyword: str
    frequency: int
    density: float
    estimated_volume: int
    estimated_difficulty: float
    estimated_ctr: float
    current_rank: Optional[int] = None
    rank_gap: Optional[int] = None
    opportunity_score: float
    is_opportunity: bool

    class Config:
        from_attributes = True


class OpportunitiesResponse(BaseModel):
    domain: str
    total_keywords: int
    opportunities: List[KeywordSchema]


class ReportResponse(BaseModel):
    domain: str
    site: SiteSchema
    score: Optional[ScoreSchema] = None
    issue_summary: IssueCountBySeverity
    recent_job: Optional[CrawlJobSchema] = None
    top_opportunities: List[KeywordSchema] = []
    pages_overview: Dict[str, Any] = {}


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    redis: str
    celery: str


class PaginatedResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[Any]


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    status_code: int