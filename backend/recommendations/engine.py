"""
Recommendation Engine.
Detects SEO issues and generates actionable recommendations.
Each recommendation has: issue, reason, fix, impact, priority.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from analyzer.analyzer import AnalyzedPage
from core.logging import get_logger

logger = get_logger(__name__)


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Recommendation:
    """A single SEO recommendation."""
    issue_type: str
    severity: str
    title: str
    description: str
    recommendation: str
    fix_instructions: str
    impact_description: str
    affected_element: Optional[str] = None
    page_url: Optional[str] = None


class RecommendationEngine:
    """
    Generates prioritized SEO recommendations from analyzed page data.
    Covers technical, content, and linking issues.
    """

    def generate_page_recommendations(self, page: AnalyzedPage) -> List[Recommendation]:
        """Generate all recommendations for a single page."""
        recommendations: List[Recommendation] = []

        recommendations.extend(self._check_title(page))
        recommendations.extend(self._check_meta_description(page))
        recommendations.extend(self._check_headings(page))
        recommendations.extend(self._check_content(page))
        recommendations.extend(self._check_images(page))
        recommendations.extend(self._check_technical(page))
        recommendations.extend(self._check_structured_data(page))
        recommendations.extend(self._check_links(page))

        # Tag each recommendation with the page URL
        for rec in recommendations:
            rec.page_url = page.url

        return recommendations

    def generate_site_recommendations(
        self, pages: List[AnalyzedPage], site_stats: Dict[str, Any]
    ) -> List[Recommendation]:
        """Generate site-wide recommendations based on aggregate data."""
        recommendations: List[Recommendation] = []

        total_pages = len(pages)
        if total_pages == 0:
            return recommendations

        # Count pages with issues
        pages_no_title = sum(1 for p in pages if not p.title)
        pages_no_meta = sum(1 for p in pages if not p.meta_description)
        pages_no_h1 = sum(1 for p in pages if not p.h1_tags)
        pages_missing_alt = sum(1 for p in pages if p.images_missing_alt > 0)
        pages_no_schema = sum(1 for p in pages if not p.has_schema_markup)
        pages_thin_content = sum(1 for p in pages if p.word_count < 300)
        pages_not_https = sum(1 for p in pages if not p.is_https)

        pct_no_title = (pages_no_title / total_pages) * 100
        pct_no_meta = (pages_no_meta / total_pages) * 100

        if pages_not_https > 0:
            recommendations.append(Recommendation(
                issue_type="https_mixed",
                severity=Priority.CRITICAL,
                title=f"{pages_not_https} pages not served over HTTPS",
                description=(
                    f"{pages_not_https} of {total_pages} pages are not using HTTPS. "
                    "HTTPS is a confirmed Google ranking factor."
                ),
                recommendation="Migrate all pages to HTTPS and implement 301 redirects from HTTP.",
                fix_instructions=(
                    "1. Obtain an SSL certificate (Let's Encrypt is free)\n"
                    "2. Configure your web server to redirect all HTTP to HTTPS\n"
                    "3. Update all internal links to use HTTPS\n"
                    "4. Update your sitemap and Google Search Console"
                ),
                impact_description="HTTPS is a direct ranking signal. Migration improves trust and rankings.",
                affected_element=f"{pages_not_https} pages"
            ))

        if pct_no_title > 5:
            recommendations.append(Recommendation(
                issue_type="missing_titles_bulk",
                severity=Priority.CRITICAL,
                title=f"{pages_no_title} pages missing title tags ({pct_no_title:.0f}%)",
                description="Title tags are one of the most critical on-page SEO factors.",
                recommendation="Add unique, descriptive title tags to all pages.",
                fix_instructions=(
                    "1. Audit all pages missing titles\n"
                    "2. Write unique titles (50-60 characters)\n"
                    "3. Include primary keyword near the beginning\n"
                    "4. Add brand name at the end: 'Primary Keyword - Brand Name'"
                ),
                impact_description="Title tags directly influence click-through rates and rankings.",
                affected_element=f"{pages_no_title} pages"
            ))

        if pct_no_meta > 10:
            recommendations.append(Recommendation(
                issue_type="missing_meta_bulk",
                severity=Priority.HIGH,
                title=f"{pages_no_meta} pages missing meta descriptions ({pct_no_meta:.0f}%)",
                description="Meta descriptions influence click-through rates from search results.",
                recommendation="Write compelling meta descriptions for all important pages.",
                fix_instructions=(
                    "1. Write unique meta descriptions (150-160 characters)\n"
                    "2. Include target keyword naturally\n"
                    "3. Add a call-to-action where appropriate\n"
                    "4. Make each description unique to the page content"
                ),
                impact_description="Better meta descriptions improve CTR, driving more organic traffic.",
                affected_element=f"{pages_no_meta} pages"
            ))

        if pages_thin_content > total_pages * 0.3:
            recommendations.append(Recommendation(
                issue_type="thin_content_bulk",
                severity=Priority.HIGH,
                title=f"{pages_thin_content} pages have thin content (<300 words)",
                description=(
                    f"{pages_thin_content} pages have fewer than 300 words. "
                    "Thin content can trigger Google Panda penalties."
                ),
                recommendation="Either expand thin content or consolidate/remove low-value pages.",
                fix_instructions=(
                    "1. Identify which thin pages have search value\n"
                    "2. Expand valuable pages to 800+ words\n"
                    "3. Consolidate related thin pages into comprehensive guides\n"
                    "4. Use noindex on unavoidable thin pages (e.g., tag pages)"
                ),
                impact_description="Content depth is strongly correlated with ranking ability.",
                affected_element=f"{pages_thin_content} pages"
            ))

        if pages_no_schema > total_pages * 0.8:
            recommendations.append(Recommendation(
                issue_type="missing_schema_bulk",
                severity=Priority.MEDIUM,
                title="Most pages lack structured data / schema markup",
                description=(
                    f"Only {total_pages - pages_no_schema} of {total_pages} pages have schema markup. "
                    "Schema helps search engines understand your content."
                ),
                recommendation="Implement appropriate schema.org markup across your site.",
                fix_instructions=(
                    "1. Add Organization or WebSite schema to homepage\n"
                    "2. Add Article/BlogPosting schema to blog posts\n"
                    "3. Add FAQPage schema to FAQ pages\n"
                    "4. Add BreadcrumbList to improve sitelinks\n"
                    "5. Validate with Google's Rich Results Test"
                ),
                impact_description="Schema markup enables rich results, improving visibility and CTR.",
                affected_element=f"{pages_no_schema} pages"
            ))

        return recommendations

    # ---- Individual page checks ----

    def _check_title(self, page: AnalyzedPage) -> List[Recommendation]:
        recs = []
        if not page.title:
            recs.append(Recommendation(
                issue_type="missing_title",
                severity=Priority.CRITICAL,
                title="Missing title tag",
                description="This page has no <title> tag. Title tags are critical for SEO and click-through rates.",
                recommendation="Add a unique, descriptive title tag (50-60 characters) with the primary keyword.",
                fix_instructions=(
                    "Add <title>Your Primary Keyword - Brand Name</title> in the <head> section.\n"
                    "Keep it between 50-60 characters for optimal display in search results."
                ),
                impact_description="Critical: Missing title severely impacts ranking ability.",
                affected_element="<title>"
            ))
        elif page.title_length > 60:
            recs.append(Recommendation(
                issue_type="title_too_long",
                severity=Priority.MEDIUM,
                title=f"Title too long ({page.title_length} characters)",
                description=(
                    f"Title tag is {page.title_length} chars. Google truncates titles over 60 characters "
                    "in search results, reducing click-through rates."
                ),
                recommendation="Shorten the title to 50-60 characters while retaining the primary keyword.",
                fix_instructions=f"Current: '{page.title}'\nReduce to 50-60 characters, keeping the primary keyword near the start.",
                impact_description="Shorter titles display fully in SERPs, improving CTR.",
                affected_element=f"<title>{page.title}</title>"
            ))
        elif page.title_length < 30:
            recs.append(Recommendation(
                issue_type="title_too_short",
                severity=Priority.MEDIUM,
                title=f"Title too short ({page.title_length} characters)",
                description="Short titles miss keyword opportunities and may appear less relevant to search engines.",
                recommendation="Expand the title to 50-60 characters with descriptive keywords.",
                fix_instructions="Add more descriptive keywords and context to the title.",
                impact_description="Properly-lengthed titles maximize SERP real estate and keyword targeting.",
                affected_element=f"<title>{page.title}</title>"
            ))
        return recs

    def _check_meta_description(self, page: AnalyzedPage) -> List[Recommendation]:
        recs = []
        if not page.meta_description:
            recs.append(Recommendation(
                issue_type="missing_meta_description",
                severity=Priority.HIGH,
                title="Missing meta description",
                description="No meta description found. Google may generate a poor auto-snippet for this page.",
                recommendation="Write a compelling meta description (150-160 chars) with a call-to-action.",
                fix_instructions='Add <meta name="description" content="Your description here..."> in the <head>.',
                impact_description="Meta descriptions control your SERP snippet and heavily influence CTR.",
                affected_element='<meta name="description">'
            ))
        elif page.meta_description_length > 160:
            recs.append(Recommendation(
                issue_type="meta_description_too_long",
                severity=Priority.LOW,
                title=f"Meta description too long ({page.meta_description_length} chars)",
                description="Google truncates descriptions over 160 characters in search results.",
                recommendation="Shorten to 150-160 characters, keeping the most important information first.",
                fix_instructions=f"Trim to under 160 chars. Current length: {page.meta_description_length}.",
                impact_description="Prevents truncation in SERPs, showing the full value proposition.",
                affected_element='<meta name="description">'
            ))
        return recs

    def _check_headings(self, page: AnalyzedPage) -> List[Recommendation]:
        recs = []
        h1_count = len(page.h1_tags)
        if h1_count == 0:
            recs.append(Recommendation(
                issue_type="missing_h1",
                severity=Priority.HIGH,
                title="Missing H1 tag",
                description="No H1 heading found. H1 is the primary signal for page topic to search engines.",
                recommendation="Add one H1 tag containing the primary keyword for this page.",
                fix_instructions="Add <h1>Your Primary Keyword</h1> as the main heading on the page.",
                impact_description="H1 is a strong relevance signal. Missing it reduces ranking potential.",
                affected_element="<h1>"
            ))
        elif h1_count > 1:
            recs.append(Recommendation(
                issue_type="multiple_h1",
                severity=Priority.MEDIUM,
                title=f"Multiple H1 tags ({h1_count} found)",
                description=f"Found {h1_count} H1 tags. Best practice is exactly one H1 per page.",
                recommendation="Consolidate to a single H1 tag. Use H2-H6 for subheadings.",
                fix_instructions=f"H1 tags found: {page.h1_tags[:3]}. Keep the most descriptive one, convert others to H2.",
                impact_description="Multiple H1s dilute the page's topic signal.",
                affected_element="<h1>"
            ))
        return recs

    def _check_content(self, page: AnalyzedPage) -> List[Recommendation]:
        recs = []
        if page.word_count < 300 and page.is_indexable:
            severity = Priority.HIGH if page.word_count < 150 else Priority.MEDIUM
            recs.append(Recommendation(
                issue_type="thin_content",
                severity=severity,
                title=f"Thin content ({page.word_count} words)",
                description=(
                    f"Page has only {page.word_count} words. Pages with less than 300 words "
                    "are considered thin content and may struggle to rank."
                ),
                recommendation="Expand content to at least 800 words with valuable, relevant information.",
                fix_instructions=(
                    "1. Research what users searching for this topic want to know\n"
                    "2. Add comprehensive answers to common questions\n"
                    "3. Include relevant examples, data, and visuals\n"
                    "4. Aim for 800-2000 words for competitive topics"
                ),
                impact_description="Content depth is strongly correlated with ranking ability.",
                affected_element="page body"
            ))
        return recs

    def _check_images(self, page: AnalyzedPage) -> List[Recommendation]:
        recs = []
        if page.images_missing_alt > 0:
            severity = Priority.HIGH if page.images_missing_alt > 5 else Priority.MEDIUM
            recs.append(Recommendation(
                issue_type="images_missing_alt",
                severity=severity,
                title=f"{page.images_missing_alt} images missing alt text",
                description=(
                    f"{page.images_missing_alt} of {page.total_images} images have no alt attribute. "
                    "Alt text is critical for accessibility and image SEO."
                ),
                recommendation="Add descriptive alt text to all images, using keywords where natural.",
                fix_instructions=(
                    "1. Add alt='Descriptive text about image' to each img tag\n"
                    "2. For decorative images, use alt=''\n"
                    "3. Include target keywords naturally in key image alt texts\n"
                    "4. Keep alt text under 125 characters"
                ),
                impact_description="Alt text improves image rankings, accessibility, and is an on-page signal.",
                affected_element="<img> tags"
            ))
        return recs

    def _check_technical(self, page: AnalyzedPage) -> List[Recommendation]:
        recs = []
        if not page.is_https:
            recs.append(Recommendation(
                issue_type="not_https",
                severity=Priority.CRITICAL,
                title="Page not served over HTTPS",
                description="This page is served over HTTP. HTTPS is a ranking factor and builds user trust.",
                recommendation="Migrate to HTTPS with a valid SSL certificate.",
                fix_instructions=(
                    "1. Install an SSL certificate (Let's Encrypt is free)\n"
                    "2. Redirect HTTP to HTTPS via server config\n"
                    "3. Update all internal links to HTTPS\n"
                    "4. Update canonical tags, sitemaps, and Search Console"
                ),
                impact_description="HTTPS is a direct Google ranking signal. Critical for security and trust.",
                affected_element="URL scheme"
            ))

        if not page.has_viewport_meta:
            recs.append(Recommendation(
                issue_type="missing_viewport",
                severity=Priority.HIGH,
                title="Missing viewport meta tag",
                description="No viewport meta tag found. This makes the page non-mobile-friendly.",
                recommendation='Add <meta name="viewport" content="width=device-width, initial-scale=1">',
                fix_instructions='Add <meta name="viewport" content="width=device-width, initial-scale=1"> in <head>.',
                impact_description="Mobile-friendliness is a major ranking factor. Missing viewport hurts mobile rankings.",
                affected_element='<meta name="viewport">'
            ))

        if page.load_time_ms > 3000 and page.load_time_ms > 0:
            recs.append(Recommendation(
                issue_type="slow_page_load",
                severity=Priority.HIGH,
                title=f"Slow page load time ({page.load_time_ms}ms)",
                description=(
                    f"Page took {page.load_time_ms}ms to load. "
                    "Core Web Vitals (LCP) should be under 2500ms."
                ),
                recommendation="Optimize page performance: compress images, minify assets, use a CDN.",
                fix_instructions=(
                    "1. Compress and resize images (use WebP format)\n"
                    "2. Enable gzip/brotli compression on server\n"
                    "3. Minify CSS, JS, and HTML\n"
                    "4. Use a CDN for static assets\n"
                    "5. Implement browser caching\n"
                    "6. Reduce server response time (TTFB < 200ms)"
                ),
                impact_description="Page speed is a direct ranking factor and impacts user experience.",
                affected_element="page load performance"
            ))
        return recs

    def _check_structured_data(self, page: AnalyzedPage) -> List[Recommendation]:
        recs = []
        if not page.has_schema_markup:
            recs.append(Recommendation(
                issue_type="missing_schema",
                severity=Priority.MEDIUM,
                title="No structured data / schema markup",
                description=(
                    "No schema.org markup found. Schema helps search engines understand "
                    "your content and can unlock rich results."
                ),
                recommendation="Add appropriate schema.org markup (Article, Product, FAQ, etc.).",
                fix_instructions=(
                    "1. Identify the most appropriate schema type for this page\n"
                    "2. Implement JSON-LD in the <head> section\n"
                    "3. Validate using Google's Rich Results Test\n"
                    "4. Monitor for rich result impressions in Search Console"
                ),
                impact_description="Schema markup can significantly improve CTR via rich results.",
                affected_element="<script type='application/ld+json'>"
            ))
        if not page.has_open_graph:
            recs.append(Recommendation(
                issue_type="missing_open_graph",
                severity=Priority.LOW,
                title="Missing Open Graph tags",
                description="No Open Graph meta tags found. These control how the page appears when shared on social media.",
                recommendation="Add og:title, og:description, og:image, and og:url meta tags.",
                fix_instructions=(
                    "Add to <head>:\n"
                    "<meta property='og:title' content='Page Title'>\n"
                    "<meta property='og:description' content='Description'>\n"
                    "<meta property='og:image' content='https://example.com/image.jpg'>\n"
                    "<meta property='og:url' content='https://example.com/page'>"
                ),
                impact_description="Improves social sharing appearance, driving referral traffic.",
                affected_element="Open Graph meta tags"
            ))
        return recs

    def _check_links(self, page: AnalyzedPage) -> List[Recommendation]:
        recs = []
        if page.internal_links_count == 0 and page.word_count > 100:
            recs.append(Recommendation(
                issue_type="no_internal_links",
                severity=Priority.MEDIUM,
                title="No outgoing internal links",
                description=(
                    "This page has no internal links to other pages. "
                    "Internal links pass PageRank and help users navigate."
                ),
                recommendation="Add 3-5 relevant internal links to related content on your site.",
                fix_instructions=(
                    "1. Identify 3-5 related pages on your site\n"
                    "2. Add contextual links with descriptive anchor text\n"
                    "3. Avoid generic anchor text like 'click here'\n"
                    "4. Link to both category pages and individual articles"
                ),
                impact_description="Internal links distribute PageRank and improve crawlability.",
                affected_element="<a href> tags"
            ))
        return recs