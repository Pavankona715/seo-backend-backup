"""
SEO Analyzer module.
Extracts all SEO signals from HTML pages:
- Titles, meta descriptions, headings
- Schema markup (JSON-LD, Microdata, RDFa)
- Open Graph and Twitter Card data
- Alt tags, image analysis
- Word counts, entities
- Keyword frequency analysis
- Internal/external link analysis
- Technical signals
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup, Tag
import extruct
import trafilatura
from collections import Counter

from core.logging import get_logger
from crawler.crawler import CrawlResult

logger = get_logger(__name__)

# Common English stop words for keyword extraction
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "into", "through", "during",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "shall", "can", "need", "dare", "ought", "used", "it", "its", "this",
    "that", "these", "those", "i", "me", "my", "we", "our", "you", "your",
    "he", "his", "she", "her", "they", "their", "what", "which", "who",
    "when", "where", "why", "how", "all", "each", "every", "both", "few",
    "more", "most", "other", "some", "such", "no", "not", "only", "same",
    "so", "than", "too", "very", "just", "also", "as", "if", "then",
}

# Schema.org types that matter for SEO
SEO_SCHEMA_TYPES = {
    "Article", "NewsArticle", "BlogPosting", "WebPage", "Product",
    "LocalBusiness", "Organization", "Person", "Event", "FAQPage",
    "HowTo", "Review", "AggregateRating", "BreadcrumbList", "Recipe",
    "VideoObject", "ImageObject", "SoftwareApplication", "Course",
}


class AnalyzedPage:
    """Container for all analyzed SEO data from a page."""

    def __init__(self):
        # Basic SEO
        self.url: str = ""
        self.canonical_url: Optional[str] = None
        self.status_code: int = 0
        self.title: Optional[str] = None
        self.title_length: int = 0
        self.meta_description: Optional[str] = None
        self.meta_description_length: int = 0
        self.meta_robots: Optional[str] = None
        self.canonical_tag: Optional[str] = None
        self.is_indexable: bool = True
        self.is_canonical: bool = True

        # Headings
        self.h1_tags: List[str] = []
        self.h2_tags: List[str] = []
        self.h3_tags: List[str] = []
        self.h4_tags: List[str] = []
        self.h5_tags: List[str] = []
        self.h6_tags: List[str] = []

        # Content
        self.word_count: int = 0
        self.content_text: str = ""
        self.reading_time_seconds: int = 0
        self.text_html_ratio: float = 0.0
        self.language: Optional[str] = None

        # Technical
        self.load_time_ms: int = 0
        self.page_size_bytes: int = 0
        self.is_https: bool = False
        self.has_viewport_meta: bool = False

        # Structured data
        self.has_schema_markup: bool = False
        self.schema_types: List[str] = []
        self.structured_data: Dict = {}
        self.has_open_graph: bool = False
        self.open_graph_data: Dict = {}
        self.has_twitter_card: bool = False
        self.twitter_card_data: Dict = {}
        self.has_hreflang: bool = False

        # Images
        self.total_images: int = 0
        self.images_missing_alt: int = 0
        self.images_with_alt: int = 0

        # Links
        self.internal_links: List[Dict] = []
        self.external_links: List[Dict] = []
        self.internal_links_count: int = 0
        self.external_links_count: int = 0

        # NLP / Keywords
        self.keyword_frequencies: Dict[str, int] = {}
        self.entities: List[Dict] = []

        # Raw data
        self.raw_html: str = ""
        self.headers: Dict = {}


class SEOAnalyzer:
    """
    Extracts and analyzes all SEO signals from a crawled page.
    Produces a structured AnalyzedPage object.
    """

    def __init__(self, base_domain: str):
        self.base_domain = base_domain

    def analyze(self, crawl_result: CrawlResult, depth: int = 0) -> AnalyzedPage:
        """
        Main analysis method. Takes a CrawlResult and returns an AnalyzedPage.
        All extraction is synchronous for CPU-bound work.
        """
        page = AnalyzedPage()
        page.url = crawl_result.url
        page.status_code = crawl_result.status_code
        page.load_time_ms = crawl_result.load_time_ms
        page.page_size_bytes = crawl_result.page_size_bytes
        page.is_https = crawl_result.url.startswith("https://")
        page.headers = crawl_result.headers
        page.raw_html = crawl_result.html

        if not crawl_result.html:
            return page

        soup = BeautifulSoup(crawl_result.html, "lxml")

        self._extract_basic_seo(page, soup, crawl_result.final_url)
        self._extract_headings(page, soup)
        self._extract_content(page, soup, crawl_result.html)
        self._extract_images(page, soup)
        self._extract_links(page, soup, crawl_result.final_url)
        self._extract_structured_data(page, soup, crawl_result.html, crawl_result.final_url)
        self._extract_social_meta(page, soup)
        self._extract_technical_signals(page, soup)
        self._compute_keyword_frequencies(page)

        return page

    def _extract_basic_seo(self, page: AnalyzedPage, soup: BeautifulSoup, page_url: str) -> None:
        """Extract title, meta tags, canonical, robots directives."""
        # Title
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            page.title = title_tag.string.strip()[:512]
            page.title_length = len(page.title)

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": re.compile("description", re.I)})
        if meta_desc and meta_desc.get("content"):
            page.meta_description = meta_desc["content"].strip()
            page.meta_description_length = len(page.meta_description)

        # Meta robots
        meta_robots = soup.find("meta", attrs={"name": re.compile("robots", re.I)})
        if meta_robots and meta_robots.get("content"):
            page.meta_robots = meta_robots["content"].lower().strip()
            page.is_indexable = "noindex" not in page.meta_robots

        # Canonical tag
        canonical = soup.find("link", attrs={"rel": "canonical"})
        if canonical and canonical.get("href"):
            page.canonical_tag = canonical["href"].strip()
            page.canonical_url = page.canonical_tag
            # Check if canonical points elsewhere
            if page.canonical_tag and page.canonical_tag != page_url:
                page.is_canonical = False

        # Language
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            page.language = html_tag["lang"][:10]

        # Hreflang
        hreflang_tags = soup.find_all("link", attrs={"hreflang": True})
        page.has_hreflang = len(hreflang_tags) > 0

    def _extract_headings(self, page: AnalyzedPage, soup: BeautifulSoup) -> None:
        """Extract all heading tags H1-H6."""
        for level in range(1, 7):
            tags = soup.find_all(f"h{level}")
            texts = [tag.get_text(strip=True)[:255] for tag in tags if tag.get_text(strip=True)]
            setattr(page, f"h{level}_tags", texts)

    def _extract_content(self, page: AnalyzedPage, soup: BeautifulSoup, raw_html: str) -> None:
        """Extract readable text content and compute metrics."""
        # Use trafilatura for high-quality text extraction
        extracted = trafilatura.extract(raw_html, include_comments=False, include_tables=True)
        if extracted:
            page.content_text = extracted
            words = extracted.split()
            page.word_count = len(words)
            # Average reading speed: 200-250 words per minute
            page.reading_time_seconds = max(1, int((page.word_count / 225) * 60))

        # Text/HTML ratio
        html_length = len(raw_html)
        if html_length > 0:
            text_length = len(soup.get_text())
            page.text_html_ratio = round(text_length / html_length, 3)

    def _extract_images(self, page: AnalyzedPage, soup: BeautifulSoup) -> None:
        """Analyze all images for alt text presence."""
        images = soup.find_all("img")
        page.total_images = len(images)
        page.images_missing_alt = 0
        page.images_with_alt = 0

        for img in images:
            alt = img.get("alt", None)
            if alt is None or alt.strip() == "":
                page.images_missing_alt += 1
            else:
                page.images_with_alt += 1

    def _extract_links(self, page: AnalyzedPage, soup: BeautifulSoup, page_url: str) -> None:
        """Extract and classify all links as internal or external."""
        base_parsed = urlparse(page_url)
        base_netloc = base_parsed.netloc.replace("www.", "")

        for tag in soup.find_all("a", href=True):
            href = tag.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                continue

            absolute_url = urljoin(page_url, href)
            parsed = urlparse(absolute_url)
            if parsed.scheme not in ("http", "https"):
                continue

            anchor_text = tag.get_text(strip=True)[:255]
            is_nofollow = "nofollow" in tag.get("rel", [])
            target_netloc = parsed.netloc.replace("www.", "")
            is_internal = target_netloc == base_netloc

            link_data = {
                "url": absolute_url,
                "anchor_text": anchor_text,
                "is_nofollow": is_nofollow,
                "is_internal": is_internal,
            }

            if is_internal:
                page.internal_links.append(link_data)
            else:
                page.external_links.append(link_data)

        page.internal_links_count = len(page.internal_links)
        page.external_links_count = len(page.external_links)

    def _extract_structured_data(
        self, page: AnalyzedPage, soup: BeautifulSoup, raw_html: str, page_url: str
    ) -> None:
        """Extract JSON-LD, Microdata, and RDFa structured data."""
        try:
            data = extruct.extract(
                raw_html,
                base_url=page_url,
                syntaxes=["json-ld", "microdata", "opengraph", "rdfa"],
                uniform=True,
            )
            if data.get("json-ld") or data.get("microdata") or data.get("rdfa"):
                page.has_schema_markup = True
                page.structured_data = {
                    "json_ld": data.get("json-ld", []),
                    "microdata": data.get("microdata", []),
                    "rdfa": data.get("rdfa", []),
                }
                # Extract schema types
                schema_types = set()
                for item in data.get("json-ld", []):
                    if isinstance(item, dict):
                        t = item.get("@type", "")
                        if isinstance(t, list):
                            schema_types.update(t)
                        elif t:
                            schema_types.add(t)
                page.schema_types = list(schema_types & SEO_SCHEMA_TYPES)
        except Exception as e:
            logger.warning(f"Structured data extraction failed for {page.url}: {e}")

    def _extract_social_meta(self, page: AnalyzedPage, soup: BeautifulSoup) -> None:
        """Extract Open Graph and Twitter Card metadata."""
        og_data = {}
        for tag in soup.find_all("meta", property=re.compile("^og:", re.I)):
            prop = tag.get("property", "").replace("og:", "")
            content = tag.get("content", "")
            if prop and content:
                og_data[prop] = content

        if og_data:
            page.has_open_graph = True
            page.open_graph_data = og_data

        twitter_data = {}
        for tag in soup.find_all("meta", attrs={"name": re.compile("^twitter:", re.I)}):
            name = tag.get("name", "").replace("twitter:", "")
            content = tag.get("content", "")
            if name and content:
                twitter_data[name] = content

        if twitter_data:
            page.has_twitter_card = True
            page.twitter_card_data = twitter_data

    def _extract_technical_signals(self, page: AnalyzedPage, soup: BeautifulSoup) -> None:
        """Extract technical SEO signals like viewport meta."""
        viewport = soup.find("meta", attrs={"name": re.compile("viewport", re.I)})
        page.has_viewport_meta = viewport is not None

    def _compute_keyword_frequencies(self, page: AnalyzedPage) -> None:
        """Compute keyword frequency distribution from content text."""
        if not page.content_text:
            return

        # Clean and tokenize
        text = page.content_text.lower()
        text = re.sub(r"[^a-z0-9\s\-']", " ", text)
        tokens = text.split()

        # Filter stop words and short tokens
        meaningful_tokens = [
            t.strip("'-")
            for t in tokens
            if len(t) > 2 and t not in STOP_WORDS and t.strip("'-")
        ]

        # Count unigrams
        unigram_counts = Counter(meaningful_tokens)

        # Count bigrams
        bigrams = [
            f"{meaningful_tokens[i]} {meaningful_tokens[i+1]}"
            for i in range(len(meaningful_tokens) - 1)
        ]
        bigram_counts = Counter(bigrams)

        # Combine, keeping top 200
        combined = {}
        for term, count in unigram_counts.most_common(150):
            combined[term] = count
        for term, count in bigram_counts.most_common(50):
            if count >= 2:  # Only include bigrams that appear multiple times
                combined[term] = count

        page.keyword_frequencies = combined