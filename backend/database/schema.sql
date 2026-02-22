-- SEO Intelligence Platform - Full SQL Schema
-- Version: 1.0.0
-- Database: PostgreSQL 15+

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- ENUM TYPES
-- ============================================================

CREATE TYPE job_status AS ENUM (
    'pending', 'running', 'paused', 'completed', 'failed', 'cancelled'
);

CREATE TYPE issue_severity AS ENUM (
    'critical', 'high', 'medium', 'low', 'info'
);

-- ============================================================
-- SITES TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS sites (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain          VARCHAR(255) NOT NULL UNIQUE,
    root_url        VARCHAR(2048) NOT NULL,
    sitemap_url     VARCHAR(2048),
    robots_txt      TEXT,
    last_crawled_at TIMESTAMP,
    total_pages     INTEGER DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    settings        JSONB DEFAULT '{}',
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sites_domain ON sites (domain);
CREATE INDEX idx_sites_last_crawled ON sites (last_crawled_at);
CREATE INDEX idx_sites_is_active ON sites (is_active);

-- ============================================================
-- CRAWL JOBS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS crawl_jobs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id         UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    celery_task_id  VARCHAR(255),
    status          job_status DEFAULT 'pending' NOT NULL,
    max_depth       INTEGER DEFAULT 5,
    max_pages       INTEGER DEFAULT 10000,
    use_js_rendering BOOLEAN DEFAULT FALSE,
    respect_robots  BOOLEAN DEFAULT TRUE,
    pages_crawled   INTEGER DEFAULT 0,
    pages_failed    INTEGER DEFAULT 0,
    pages_queued    INTEGER DEFAULT 0,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    error_message   TEXT,
    config          JSONB DEFAULT '{}',
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_crawl_jobs_site_status ON crawl_jobs (site_id, status);
CREATE INDEX idx_crawl_jobs_celery_task ON crawl_jobs (celery_task_id);
CREATE INDEX idx_crawl_jobs_created_at ON crawl_jobs (created_at DESC);

-- ============================================================
-- PAGES TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS pages (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id                 UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    crawl_job_id            UUID REFERENCES crawl_jobs(id) ON DELETE SET NULL,
    url                     VARCHAR(2048) NOT NULL,
    canonical_url           VARCHAR(2048),
    status_code             INTEGER,
    depth                   INTEGER DEFAULT 0,
    is_indexable            BOOLEAN DEFAULT TRUE,
    is_canonical            BOOLEAN DEFAULT TRUE,

    -- SEO Signals
    title                   VARCHAR(512),
    title_length            INTEGER,
    meta_description        TEXT,
    meta_description_length INTEGER,
    meta_robots             VARCHAR(255),
    canonical_tag           VARCHAR(2048),
    h1_tags                 TEXT[],
    h2_tags                 TEXT[],
    h3_tags                 TEXT[],
    h4_tags                 TEXT[],
    h5_tags                 TEXT[],
    h6_tags                 TEXT[],

    -- Content Metrics
    word_count              INTEGER DEFAULT 0,
    content_text            TEXT,
    reading_time_seconds    INTEGER DEFAULT 0,
    text_html_ratio         FLOAT DEFAULT 0.0,
    language                VARCHAR(10),

    -- Technical Signals
    load_time_ms            INTEGER,
    page_size_bytes         BIGINT,
    has_schema_markup       BOOLEAN DEFAULT FALSE,
    schema_types            TEXT[],
    has_open_graph          BOOLEAN DEFAULT FALSE,
    has_twitter_card        BOOLEAN DEFAULT FALSE,
    has_hreflang            BOOLEAN DEFAULT FALSE,
    is_https                BOOLEAN DEFAULT FALSE,
    has_viewport_meta       BOOLEAN DEFAULT FALSE,

    -- Images
    total_images            INTEGER DEFAULT 0,
    images_missing_alt      INTEGER DEFAULT 0,
    images_with_alt         INTEGER DEFAULT 0,

    -- Links
    internal_links_count    INTEGER DEFAULT 0,
    external_links_count    INTEGER DEFAULT 0,
    broken_links_count      INTEGER DEFAULT 0,

    -- Structured Data (JSONB for fast querying)
    structured_data         JSONB DEFAULT '{}',
    open_graph_data         JSONB DEFAULT '{}',
    twitter_card_data       JSONB DEFAULT '{}',
    keyword_frequencies     JSONB DEFAULT '{}',
    entities                JSONB DEFAULT '[]',

    -- Meta
    crawled_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW(),

    UNIQUE (site_id, url)
);

CREATE INDEX idx_pages_site_id ON pages (site_id);
CREATE INDEX idx_pages_status_code ON pages (status_code);
CREATE INDEX idx_pages_depth ON pages (depth);
CREATE INDEX idx_pages_crawled_at ON pages (crawled_at DESC);
CREATE INDEX idx_pages_word_count ON pages (word_count);
CREATE INDEX idx_pages_url_trgm ON pages USING gin (url gin_trgm_ops);

-- ============================================================
-- LINKS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS links (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id         UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    source_page_id  UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    target_page_id  UUID REFERENCES pages(id) ON DELETE SET NULL,
    target_url      VARCHAR(2048) NOT NULL,
    anchor_text     TEXT,
    is_internal     BOOLEAN DEFAULT TRUE,
    is_nofollow     BOOLEAN DEFAULT FALSE,
    is_broken       BOOLEAN DEFAULT FALSE,
    link_type       VARCHAR(50) DEFAULT 'hyperlink',
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_links_site_id ON links (site_id);
CREATE INDEX idx_links_source_page ON links (source_page_id);
CREATE INDEX idx_links_target_page ON links (target_page_id);
CREATE INDEX idx_links_is_broken ON links (is_broken) WHERE is_broken = TRUE;
CREATE INDEX idx_links_is_internal ON links (is_internal);

-- ============================================================
-- SCORES TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS scores (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id                 UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    page_id                 UUID REFERENCES pages(id) ON DELETE CASCADE,
    crawl_job_id            UUID REFERENCES crawl_jobs(id) ON DELETE SET NULL,
    overall_score           FLOAT DEFAULT 0.0,
    technical_score         FLOAT DEFAULT 0.0,
    content_score           FLOAT DEFAULT 0.0,
    authority_score         FLOAT DEFAULT 0.0,
    linking_score           FLOAT DEFAULT 0.0,
    ai_visibility_score     FLOAT DEFAULT 0.0,
    technical_breakdown     JSONB DEFAULT '{}',
    content_breakdown       JSONB DEFAULT '{}',
    linking_breakdown       JSONB DEFAULT '{}',
    scored_at               TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_scores_site_id ON scores (site_id);
CREATE INDEX idx_scores_page_id ON scores (page_id);
CREATE INDEX idx_scores_overall ON scores (overall_score DESC);

-- ============================================================
-- ISSUES TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS issues (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id             UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    page_id             UUID REFERENCES pages(id) ON DELETE CASCADE,
    crawl_job_id        UUID REFERENCES crawl_jobs(id) ON DELETE SET NULL,
    issue_type          VARCHAR(100) NOT NULL,
    severity            issue_severity NOT NULL,
    title               VARCHAR(512) NOT NULL,
    description         TEXT NOT NULL,
    recommendation      TEXT,
    fix_instructions    TEXT,
    impact_description  TEXT,
    affected_element    TEXT,
    is_resolved         BOOLEAN DEFAULT FALSE,
    resolved_at         TIMESTAMP,
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_issues_site_id ON issues (site_id);
CREATE INDEX idx_issues_severity ON issues (severity);
CREATE INDEX idx_issues_type ON issues (issue_type);
CREATE INDEX idx_issues_resolved ON issues (is_resolved);
CREATE INDEX idx_issues_page_id ON issues (page_id);

-- ============================================================
-- KEYWORDS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS keywords (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id             UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    page_id             UUID REFERENCES pages(id) ON DELETE SET NULL,
    crawl_job_id        UUID REFERENCES crawl_jobs(id) ON DELETE SET NULL,
    keyword             VARCHAR(512) NOT NULL,
    frequency           INTEGER DEFAULT 0,
    density             FLOAT DEFAULT 0.0,
    estimated_volume    INTEGER DEFAULT 0,
    estimated_difficulty FLOAT DEFAULT 0.0,
    estimated_ctr       FLOAT DEFAULT 0.0,
    current_rank        INTEGER,
    rank_gap            INTEGER,
    opportunity_score   FLOAT DEFAULT 0.0,
    is_opportunity      BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_keywords_site_id ON keywords (site_id);
CREATE INDEX idx_keywords_opportunity_score ON keywords (opportunity_score DESC);
CREATE INDEX idx_keywords_keyword ON keywords (keyword);
CREATE INDEX idx_keywords_is_opportunity ON keywords (is_opportunity) WHERE is_opportunity = TRUE;

-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_sites_updated_at
    BEFORE UPDATE ON sites
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_crawl_jobs_updated_at
    BEFORE UPDATE ON crawl_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pages_updated_at
    BEFORE UPDATE ON pages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_keywords_updated_at
    BEFORE UPDATE ON keywords
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();