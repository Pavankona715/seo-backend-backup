"""
Custom exception classes for the SEO platform.
"""

from typing import Any, Optional


class SEOPlatformError(Exception):
    """Base exception for all platform errors."""

    def __init__(self, message: str, detail: Optional[Any] = None):
        self.message = message
        self.detail = detail
        super().__init__(message)


class CrawlerError(SEOPlatformError):
    """Raised when crawler encounters an unrecoverable error."""
    pass


class CrawlerRateLimitError(CrawlerError):
    """Raised when rate limit is exceeded."""
    pass


class CrawlerBlockedError(CrawlerError):
    """Raised when crawler is blocked by the target site."""
    pass


class AnalyzerError(SEOPlatformError):
    """Raised when analyzer fails to process a page."""
    pass


class ScorerError(SEOPlatformError):
    """Raised when scorer encounters an error."""
    pass


class DatabaseError(SEOPlatformError):
    """Raised when a database operation fails."""
    pass


class ValidationError(SEOPlatformError):
    """Raised when input validation fails."""
    pass


class JobNotFoundError(SEOPlatformError):
    """Raised when a crawl job is not found."""
    pass


class DomainNotFoundError(SEOPlatformError):
    """Raised when a domain/site is not found."""
    pass


class AuthenticationError(SEOPlatformError):
    """Raised when authentication fails."""
    pass


class RateLimitError(SEOPlatformError):
    """Raised when API rate limit is exceeded."""

    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")