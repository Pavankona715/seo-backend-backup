"""
SQLAlchemy ORM models for the SEO platform.
All models use async-compatible asyncpg driver.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, JSON, Enum, Index, UniqueConstraint, BigInteger
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid
import enum


class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IssueSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Site(Base):
    """Represents a crawled website/domain."""
    __tablename__ = "sites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(String(255), unique=True, nullable=False, index=True)
    root_url = Column(String(2048), nullable=False)
    sitemap_url = Column(String(2048), nullable=True)
    robots_txt = Column(Text, nullable=True)
    last_crawled_at = Column(DateTime, nullable=True)
    total_pages = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    pages = relationship("Page", back_populates="site", cascade="all, delete-orphan")
    crawl_jobs = relationship("CrawlJob", back_populates="site", cascade="all, delete-orphan")
    scores = relationship("Score", back_populates="site", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="site", cascade="all, delete-orphan")
    keywords = relationship("Keyword", back_populates="site", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_sites_domain", "domain"),
        Index("idx_sites_last_crawled", "last_crawled_at"),
    )


class CrawlJob(Base):
    """Tracks crawl job execution and progress."""
    __tablename__ = "crawl_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    celery_task_id = Column(String(255), nullable=True, index=True)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)
    max_depth = Column(Integer, default=5)
    max_pages = Column(Integer, default=10000)
    use_js_rendering = Column(Boolean, default=False)
    respect_robots = Column(Boolean, default=True)
    pages_crawled = Column(Integer, default=0)
    pages_failed = Column(Integer, default=0)
    pages_queued = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    site = relationship("Site", back_populates="crawl_jobs")

    __table_args__ = (
        Index("idx_crawl_jobs_site_status", "site_id", "status"),
        Index("idx_crawl_jobs_created_at", "created_at"),
    )


class Page(Base):
    """Represents a crawled and analyzed web page."""
    __tablename__ = "pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    crawl_job_id = Column(UUID(as_uuid=True), ForeignKey("crawl_jobs.id", ondelete="SET NULL"), nullable=True)
    url = Column(String(2048), nullable=False, index=True)
    canonical_url = Column(String(2048), nullable=True)
    status_code = Column(Integer, nullable=True)
    depth = Column(Integer, default=0)
    is_indexable = Column(Boolean, default=True)
    is_canonical = Column(Boolean, default=True)

    # SEO Data
    title = Column(String(512), nullable=True)
    title_length = Column(Integer, nullable=True)
    meta_description = Column(Text, nullable=True)
    meta_description_length = Column(Integer, nullable=True)
    meta_robots = Column(String(255), nullable=True)
    canonical_tag = Column(String(2048), nullable=True)
    h1_tags = Column(ARRAY(Text), default=list)
    h2_tags = Column(ARRAY(Text), default=list)
    h3_tags = Column(ARRAY(Text), default=list)
    h4_tags = Column(ARRAY(Text), default=list)
    h5_tags = Column(ARRAY(Text), default=list)
    h6_tags = Column(ARRAY(Text), default=list)

    # Content Metrics
    word_count = Column(Integer, default=0)
    content_text = Column(Text, nullable=True)
    reading_time_seconds = Column(Integer, default=0)
    text_html_ratio = Column(Float, default=0.0)
    language = Column(String(10), nullable=True)

    # Technical Signals
    load_time_ms = Column(Integer, nullable=True)
    page_size_bytes = Column(BigInteger, nullable=True)
    has_schema_markup = Column(Boolean, default=False)
    schema_types = Column(ARRAY(String), default=list)
    has_open_graph = Column(Boolean, default=False)
    has_twitter_card = Column(Boolean, default=False)
    has_hreflang = Column(Boolean, default=False)
    is_https = Column(Boolean, default=False)
    has_viewport_meta = Column(Boolean, default=False)

    # Images
    total_images = Column(Integer, default=0)
    images_missing_alt = Column(Integer, default=0)
    images_with_alt = Column(Integer, default=0)

    # Links
    internal_links_count = Column(Integer, default=0)
    external_links_count = Column(Integer, default=0)
    broken_links_count = Column(Integer, default=0)

    # Structured data - raw extraction
    structured_data = Column(JSON, default=dict)
    open_graph_data = Column(JSON, default=dict)
    twitter_card_data = Column(JSON, default=dict)
    keyword_frequencies = Column(JSON, default=dict)
    entities = Column(JSON, default=list)

    # Crawl meta
    crawled_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    site = relationship("Site", back_populates="pages")
    outgoing_links = relationship(
        "Link", foreign_keys="Link.source_page_id",
        back_populates="source_page", cascade="all, delete-orphan"
    )
    incoming_links = relationship(
        "Link", foreign_keys="Link.target_page_id",
        back_populates="target_page"
    )
    scores = relationship("Score", back_populates="page", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="page", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("site_id", "url", name="uq_pages_site_url"),
        Index("idx_pages_site_id", "site_id"),
        Index("idx_pages_status_code", "status_code"),
        Index("idx_pages_depth", "depth"),
        Index("idx_pages_crawled_at", "crawled_at"),
    )


class Link(Base):
    """Represents a hyperlink between pages (internal link graph)."""
    __tablename__ = "links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    source_page_id = Column(UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    target_page_id = Column(UUID(as_uuid=True), ForeignKey("pages.id", ondelete="SET NULL"), nullable=True)
    target_url = Column(String(2048), nullable=False)
    anchor_text = Column(Text, nullable=True)
    is_internal = Column(Boolean, default=True)
    is_nofollow = Column(Boolean, default=False)
    is_broken = Column(Boolean, default=False)
    link_type = Column(String(50), default="hyperlink")  # hyperlink, image, canonical, redirect
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    source_page = relationship("Page", foreign_keys=[source_page_id], back_populates="outgoing_links")
    target_page = relationship("Page", foreign_keys=[target_page_id], back_populates="incoming_links")

    __table_args__ = (
        Index("idx_links_site_id", "site_id"),
        Index("idx_links_source_page", "source_page_id"),
        Index("idx_links_target_page", "target_page_id"),
        Index("idx_links_is_broken", "is_broken"),
    )


class Score(Base):
    """SEO score breakdown for a site or page."""
    __tablename__ = "scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    page_id = Column(UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), nullable=True)
    crawl_job_id = Column(UUID(as_uuid=True), ForeignKey("crawl_jobs.id", ondelete="SET NULL"), nullable=True)

    # Overall
    overall_score = Column(Float, default=0.0)

    # Component scores
    technical_score = Column(Float, default=0.0)
    content_score = Column(Float, default=0.0)
    authority_score = Column(Float, default=0.0)
    linking_score = Column(Float, default=0.0)
    ai_visibility_score = Column(Float, default=0.0)

    # Sub-scores (JSON for extensibility)
    technical_breakdown = Column(JSON, default=dict)
    content_breakdown = Column(JSON, default=dict)
    linking_breakdown = Column(JSON, default=dict)

    scored_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    site = relationship("Site", back_populates="scores")
    page = relationship("Page", back_populates="scores")

    __table_args__ = (
        Index("idx_scores_site_id", "site_id"),
        Index("idx_scores_page_id", "page_id"),
        Index("idx_scores_overall", "overall_score"),
    )


class Issue(Base):
    """SEO issue detected on a site or page."""
    __tablename__ = "issues"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    page_id = Column(UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), nullable=True)
    crawl_job_id = Column(UUID(as_uuid=True), ForeignKey("crawl_jobs.id", ondelete="SET NULL"), nullable=True)

    issue_type = Column(String(100), nullable=False, index=True)
    severity = Column(Enum(IssueSeverity), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=True)
    fix_instructions = Column(Text, nullable=True)
    impact_description = Column(Text, nullable=True)
    affected_element = Column(Text, nullable=True)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    site = relationship("Site", back_populates="issues")
    page = relationship("Page", back_populates="issues")

    __table_args__ = (
        Index("idx_issues_site_id", "site_id"),
        Index("idx_issues_severity", "severity"),
        Index("idx_issues_type", "issue_type"),
        Index("idx_issues_resolved", "is_resolved"),
    )


class Keyword(Base):
    """Keyword opportunities computed for a site."""
    __tablename__ = "keywords"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    page_id = Column(UUID(as_uuid=True), ForeignKey("pages.id", ondelete="SET NULL"), nullable=True)
    crawl_job_id = Column(UUID(as_uuid=True), ForeignKey("crawl_jobs.id", ondelete="SET NULL"), nullable=True)

    keyword = Column(String(512), nullable=False, index=True)
    frequency = Column(Integer, default=0)
    density = Column(Float, default=0.0)
    estimated_volume = Column(Integer, default=0)
    estimated_difficulty = Column(Float, default=0.0)
    estimated_ctr = Column(Float, default=0.0)
    current_rank = Column(Integer, nullable=True)
    rank_gap = Column(Integer, nullable=True)
    opportunity_score = Column(Float, default=0.0)
    is_opportunity = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    site = relationship("Site", back_populates="keywords")

    __table_args__ = (
        Index("idx_keywords_site_id", "site_id"),
        Index("idx_keywords_opportunity_score", "opportunity_score"),
        Index("idx_keywords_keyword", "keyword"),
    )