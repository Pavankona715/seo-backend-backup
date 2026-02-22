"""
Robots.txt fetcher and compliance checker.
Respects crawl-delay directives and disallow rules.
"""

from typing import Optional
import httpx
from robotexclusionrulesparser import RobotExclusionRulesParser
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class RobotsChecker:
    """Fetches and parses robots.txt for a domain."""

    def __init__(self, base_url: str, http_client: httpx.AsyncClient):
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client
        self._parser: Optional[RobotExclusionRulesParser] = None
        self.crawl_delay: float = 0.0
        self.raw_content: Optional[str] = None
        self._fetched = False

    async def fetch(self) -> None:
        """Fetch and parse robots.txt from the domain."""
        robots_url = f"{self.base_url}/robots.txt"
        try:
            response = await self.http_client.get(robots_url, timeout=10)
            if response.status_code == 200:
                self.raw_content = response.text
                self._parser = RobotExclusionRulesParser()
                self._parser.parse(self.raw_content)
                # Extract crawl-delay
                for line in self.raw_content.splitlines():
                    if line.lower().startswith("crawl-delay:"):
                        try:
                            delay = float(line.split(":", 1)[1].strip())
                            self.crawl_delay = max(0.0, delay)
                        except ValueError:
                            pass
                logger.info(f"robots.txt fetched from {robots_url}", crawl_delay=self.crawl_delay)
            else:
                logger.info(f"No robots.txt found at {robots_url} (status={response.status_code})")
        except Exception as e:
            logger.warning(f"Failed to fetch robots.txt from {robots_url}: {e}")
        finally:
            self._fetched = True

    def is_allowed(self, url: str) -> bool:
        """Check if the given URL is allowed by robots.txt."""
        if not self._fetched or self._parser is None:
            return True
        try:
            return self._parser.is_allowed(settings.CRAWLER_USER_AGENT, url)
        except Exception:
            return True

    def get_sitemaps(self) -> list:
        """Extract Sitemap directives from robots.txt."""
        sitemaps = []
        if self.raw_content:
            for line in self.raw_content.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    sitemaps.append(sitemap_url)
        return sitemaps