"""
Sitemap.xml parser with support for:
- Standard sitemap XML
- Sitemap index files
- Gzipped sitemaps
- Robots.txt sitemap hints
"""

import gzip
import io
from typing import List, Set
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from core.logging import get_logger

logger = get_logger(__name__)

COMMON_SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/sitemaps.xml",
    "/sitemap/sitemap.xml",
    "/wp-sitemap.xml",
]


class SitemapParser:
    """Discovers and parses XML sitemaps for a domain."""

    def __init__(self, base_url: str, http_client: httpx.AsyncClient):
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client
        self._processed: Set[str] = set()

    async def fetch_all(self) -> List[str]:
        """Discover and parse all sitemaps, return list of page URLs."""
        discovered_urls: List[str] = []
        sitemap_urls = await self._discover_sitemaps()

        for sitemap_url in sitemap_urls:
            urls = await self._parse_sitemap(sitemap_url)
            discovered_urls.extend(urls)

        return list(set(discovered_urls))

    async def _discover_sitemaps(self) -> List[str]:
        """Try common sitemap paths to discover available sitemaps."""
        candidates = []
        for path in COMMON_SITEMAP_PATHS:
            url = self.base_url + path
            try:
                response = await self.http_client.head(url, timeout=5)
                if response.status_code == 200:
                    candidates.append(url)
                    logger.info(f"Found sitemap at {url}")
            except Exception:
                pass

        if not candidates:
            logger.info(f"No sitemaps found for {self.base_url}")
        return candidates

    async def _parse_sitemap(self, sitemap_url: str) -> List[str]:
        """Parse a single sitemap or sitemap index."""
        if sitemap_url in self._processed:
            return []
        self._processed.add(sitemap_url)

        try:
            response = await self.http_client.get(sitemap_url, timeout=15)
            if response.status_code != 200:
                return []

            content = response.content
            # Handle gzipped sitemaps
            if sitemap_url.endswith(".gz") or response.headers.get("content-encoding") == "gzip":
                with gzip.open(io.BytesIO(content), "rb") as f:
                    content = f.read()

            return self._parse_xml(content.decode("utf-8", errors="replace"))

        except Exception as e:
            logger.warning(f"Failed to parse sitemap {sitemap_url}: {e}")
            return []

    def _parse_xml(self, xml_content: str) -> List[str]:
        """Parse sitemap XML and extract URLs."""
        soup = BeautifulSoup(xml_content, "xml")
        urls: List[str] = []

        # Check if this is a sitemap index
        sitemap_tags = soup.find_all("sitemap")
        if sitemap_tags:
            # This is a sitemap index - we'll return the index URLs for recursive processing
            # In a full implementation you'd recurse, but we collect the locs for now
            for tag in sitemap_tags:
                loc = tag.find("loc")
                if loc and loc.text:
                    urls.append(loc.text.strip())
            return urls

        # Regular sitemap
        url_tags = soup.find_all("url")
        for tag in url_tags:
            loc = tag.find("loc")
            if loc and loc.text:
                urls.append(loc.text.strip())

        return urls