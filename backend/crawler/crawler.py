"""
Async web crawler engine using Playwright and httpx.
Supports JS rendering, robots.txt compliance, sitemap detection,
depth tracking, and concurrent crawling with rate limiting.
"""

import asyncio
import time
import re
from collections import deque
from typing import Optional, Set, Dict, Any, List, Tuple
from urllib.parse import urljoin, urlparse, urlunparse
from uuid import UUID

import httpx
import tldextract
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, BrowserContext, Page as PlaywrightPage
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.config import settings
from core.logging import get_logger
from core.exceptions import CrawlerError, CrawlerBlockedError
from crawler.robots import RobotsChecker
from crawler.sitemap import SitemapParser
from crawler.rate_limiter import DomainRateLimiter

logger = get_logger(__name__)


class CrawlResult:
    """Result of crawling a single URL."""

    def __init__(
        self,
        url: str,
        final_url: str,
        status_code: int,
        html: str,
        headers: Dict[str, str],
        load_time_ms: int,
        page_size_bytes: int,
        error: Optional[str] = None,
    ):
        self.url = url
        self.final_url = final_url
        self.status_code = status_code
        self.html = html
        self.headers = headers
        self.load_time_ms = load_time_ms
        self.page_size_bytes = page_size_bytes
        self.error = error
        self.is_success = error is None and 200 <= status_code < 400


class AsyncCrawler:
    """
    Production-grade async web crawler with:
    - Concurrent page fetching (configurable concurrency)
    - JS rendering via Playwright
    - robots.txt compliance
    - Sitemap-based URL discovery
    - Canonical URL normalization
    - Depth-limited crawling
    - Per-domain rate limiting
    - Retry logic with exponential backoff
    """

    def __init__(
        self,
        start_url: str,
        site_id: UUID,
        crawl_job_id: UUID,
        max_depth: int = 5,
        max_pages: int = 10000,
        use_js_rendering: bool = False,
        respect_robots: bool = True,
        max_concurrent: int = 20,
        rate_limit_rps: float = 5.0,
        on_page_crawled=None,
    ):
        self.start_url = start_url
        self.site_id = site_id
        self.crawl_job_id = crawl_job_id
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.use_js_rendering = use_js_rendering
        self.respect_robots = respect_robots
        self.max_concurrent = min(max_concurrent, settings.CRAWLER_MAX_CONCURRENT)
        self.rate_limit_rps = rate_limit_rps
        self.on_page_crawled = on_page_crawled  # async callback

        parsed = urlparse(start_url)
        self.base_domain = parsed.netloc
        self.scheme = parsed.scheme
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"

        ext = tldextract.extract(start_url)
        self.registered_domain = f"{ext.domain}.{ext.suffix}"

        self.visited_urls: Set[str] = set()
        self.queued_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()
        self.url_queue: deque = deque()
        self.semaphore = asyncio.Semaphore(self.max_concurrent)

        self.robots_checker: Optional[RobotsChecker] = None
        self.rate_limiter = DomainRateLimiter(rate_limit_rps)
        self._browser: Optional[Browser] = None
        self._playwright = None
        self._http_client: Optional[httpx.AsyncClient] = None

        self.stats = {
            "pages_crawled": 0,
            "pages_failed": 0,
            "start_time": None,
            "end_time": None,
        }

    async def __aenter__(self):
        await self._setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._teardown()

    async def _setup(self) -> None:
        """Initialize HTTP client and optionally Playwright."""
        headers = {
            "User-Agent": settings.CRAWLER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.CRAWLER_REQUEST_TIMEOUT),
            follow_redirects=True,
            max_redirects=5,
            headers=headers,
            limits=httpx.Limits(max_keepalive_connections=50, max_connections=100),
        )

        if self.use_js_rendering:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=settings.PLAYWRIGHT_HEADLESS,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            logger.info("Playwright browser initialized")

        if self.respect_robots:
            self.robots_checker = RobotsChecker(self.base_url, self._http_client)
            await self.robots_checker.fetch()

    async def _teardown(self) -> None:
        """Clean up resources."""
        if self._http_client:
            await self._http_client.aclose()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def normalize_url(self, url: str) -> Optional[str]:
        """Normalize a URL: remove fragments, trailing slashes, normalize scheme."""
        if not url:
            return None
        try:
            parsed = urlparse(url)
            # Strip fragments
            normalized = urlunparse(parsed._replace(fragment=""))
            # Strip trailing slash (except root)
            if normalized.endswith("/") and parsed.path != "/":
                normalized = normalized.rstrip("/")
            return normalized
        except Exception:
            return None

    def is_internal_url(self, url: str) -> bool:
        """Check if a URL belongs to the same registered domain."""
        try:
            ext = tldextract.extract(url)
            target_domain = f"{ext.domain}.{ext.suffix}"
            return target_domain == self.registered_domain
        except Exception:
            return False

    def is_crawlable_url(self, url: str) -> bool:
        """Filter out non-HTML resources and unwanted URL patterns."""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        excluded_extensions = {
            ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
            ".pdf", ".zip", ".tar", ".gz", ".mp4", ".mp3", ".avi",
            ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
            ".xlsx", ".docx", ".pptx", ".csv",
        }
        path_lower = parsed.path.lower()
        if any(path_lower.endswith(ext) for ext in excluded_extensions):
            return False

        excluded_patterns = ["wp-json", "wp-admin", ".xml", "feed/", "/api/", "/__", "/cdn-cgi/"]
        if any(p in url.lower() for p in excluded_patterns):
            return False

        return True

    def extract_links(self, html: str, page_url: str) -> List[str]:
        """Extract all hyperlinks from HTML."""
        soup = BeautifulSoup(html, "lxml")
        links = []
        for tag in soup.find_all("a", href=True):
            href = tag.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                continue
            absolute = urljoin(page_url, href)
            normalized = self.normalize_url(absolute)
            if normalized:
                links.append(normalized)
        return links

    @retry(
        stop=stop_after_attempt(settings.CRAWLER_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    )
    async def _fetch_with_http(self, url: str) -> CrawlResult:
        """Fetch a URL using httpx."""
        start = time.time()
        try:
            response = await self._http_client.get(url)
            load_time = int((time.time() - start) * 1000)
            html = response.text
            return CrawlResult(
                url=url,
                final_url=str(response.url),
                status_code=response.status_code,
                html=html,
                headers=dict(response.headers),
                load_time_ms=load_time,
                page_size_bytes=len(response.content),
            )
        except Exception as e:
            load_time = int((time.time() - start) * 1000)
            return CrawlResult(
                url=url, final_url=url, status_code=0,
                html="", headers={}, load_time_ms=load_time,
                page_size_bytes=0, error=str(e),
            )

    async def _fetch_with_playwright(self, url: str) -> CrawlResult:
        """Fetch a URL using Playwright (JS rendering)."""
        start = time.time()
        context: Optional[BrowserContext] = None
        try:
            context = await self._browser.new_context(
                user_agent=settings.CRAWLER_USER_AGENT,
                java_script_enabled=True,
            )
            page: PlaywrightPage = await context.new_page()
            response = await page.goto(
                url,
                wait_until="networkidle",
                timeout=settings.CRAWLER_JS_RENDER_TIMEOUT,
            )
            await asyncio.sleep(0.5)  # Allow late JS execution
            html = await page.content()
            final_url = page.url
            load_time = int((time.time() - start) * 1000)
            status = response.status if response else 200
            return CrawlResult(
                url=url, final_url=final_url, status_code=status,
                html=html, headers=dict(response.headers) if response else {},
                load_time_ms=load_time, page_size_bytes=len(html.encode()),
            )
        except Exception as e:
            load_time = int((time.time() - start) * 1000)
            return CrawlResult(
                url=url, final_url=url, status_code=0,
                html="", headers={}, load_time_ms=load_time,
                page_size_bytes=0, error=str(e),
            )
        finally:
            if context:
                await context.close()

    async def _fetch_url(self, url: str) -> CrawlResult:
        """Fetch a URL using the configured method."""
        if self.use_js_rendering:
            return await self._fetch_with_playwright(url)
        return await self._fetch_with_http(url)

    async def _crawl_page(self, url: str, depth: int) -> Tuple[Optional[CrawlResult], List[str]]:
        """Crawl a single page and extract discovered links."""
        async with self.semaphore:
            await self.rate_limiter.acquire(self.base_domain)

            if self.respect_robots and self.robots_checker:
                if not self.robots_checker.is_allowed(url):
                    logger.debug(f"Blocked by robots.txt: {url}")
                    return None, []

            result = await self._fetch_url(url)
            discovered_links = []

            if result.is_success and result.html:
                raw_links = self.extract_links(result.html, result.final_url)
                for link in raw_links:
                    if self.is_internal_url(link) and self.is_crawlable_url(link):
                        discovered_links.append(link)

            return result, discovered_links

    async def crawl(self) -> Dict[str, Any]:
        """
        Main crawl loop. BFS crawl starting from start_url.
        Returns statistics about the crawl.
        """
        self.stats["start_time"] = time.time()
        logger.info(f"Starting crawl of {self.start_url}", max_depth=self.max_depth, max_pages=self.max_pages)

        # Discover URLs from sitemap first
        sitemap_parser = SitemapParser(self.base_url, self._http_client)
        sitemap_urls = await sitemap_parser.fetch_all()
        logger.info(f"Found {len(sitemap_urls)} URLs from sitemap")

        # Initialize queue
        initial_urls = [self.normalize_url(self.start_url)] + [
            u for u in sitemap_urls if self.is_internal_url(u) and self.is_crawlable_url(u)
        ]
        for url in initial_urls:
            if url and url not in self.queued_urls:
                self.url_queue.append((url, 0))
                self.queued_urls.add(url)

        # BFS crawl with concurrent workers
        while self.url_queue and self.stats["pages_crawled"] < self.max_pages:
            batch = []
            while self.url_queue and len(batch) < self.max_concurrent:
                item = self.url_queue.popleft()
                url, depth = item
                if url not in self.visited_urls:
                    batch.append((url, depth))
                    self.visited_urls.add(url)

            if not batch:
                break

            tasks = [self._crawl_page(url, depth) for url, depth in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result_data in enumerate(results):
                url, depth = batch[i]

                if isinstance(result_data, Exception):
                    logger.error(f"Exception crawling {url}: {result_data}")
                    self.failed_urls.add(url)
                    self.stats["pages_failed"] += 1
                    continue

                crawl_result, discovered_links = result_data

                if crawl_result is None:
                    continue

                if crawl_result.is_success:
                    self.stats["pages_crawled"] += 1
                else:
                    self.stats["pages_failed"] += 1
                    self.failed_urls.add(url)

                # Invoke callback for processing
                if self.on_page_crawled:
                    try:
                        await self.on_page_crawled(crawl_result, depth)
                    except Exception as e:
                        logger.error(f"Callback error for {url}: {e}", exc_info=True)

                # Enqueue discovered links if within depth limit
                if depth < self.max_depth:
                    for link in discovered_links:
                        normalized = self.normalize_url(link)
                        if normalized and normalized not in self.queued_urls and normalized not in self.visited_urls:
                            self.url_queue.append((normalized, depth + 1))
                            self.queued_urls.add(normalized)

            logger.info(
                f"Progress: crawled={self.stats['pages_crawled']}, "
                f"failed={self.stats['pages_failed']}, "
                f"queued={len(self.url_queue)}"
            )

        self.stats["end_time"] = time.time()
        duration = self.stats["end_time"] - self.stats["start_time"]
        logger.info(
            f"Crawl complete for {self.start_url}",
            pages_crawled=self.stats["pages_crawled"],
            pages_failed=self.stats["pages_failed"],
            duration_seconds=round(duration, 2),
        )
        return self.stats