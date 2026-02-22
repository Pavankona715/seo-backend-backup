"""
SEO Scorer module.
Computes technical, content, authority, linking, and AI visibility scores
for pages and aggregates them into a site-level score.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from core.config import settings
from core.logging import get_logger
from analyzer.analyzer import AnalyzedPage

logger = get_logger(__name__)


@dataclass
class PageScore:
    """Computed scores for a single page."""
    overall_score: float = 0.0
    technical_score: float = 0.0
    content_score: float = 0.0
    authority_score: float = 0.0
    linking_score: float = 0.0
    ai_visibility_score: float = 0.0
    technical_breakdown: Dict[str, Any] = field(default_factory=dict)
    content_breakdown: Dict[str, Any] = field(default_factory=dict)
    linking_breakdown: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SiteScore:
    """Aggregated score for an entire site."""
    overall_score: float = 0.0
    technical_score: float = 0.0
    content_score: float = 0.0
    authority_score: float = 0.0
    linking_score: float = 0.0
    ai_visibility_score: float = 0.0
    technical_breakdown: Dict[str, Any] = field(default_factory=dict)
    content_breakdown: Dict[str, Any] = field(default_factory=dict)
    linking_breakdown: Dict[str, Any] = field(default_factory=dict)
    page_count: int = 0


def clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))


class SEOScorer:
    """
    Computes multi-dimensional SEO scores.

    Score weights:
    - Technical: 35%  (crawlability, indexability, performance, HTTPS, etc.)
    - Content: 30%    (word count, title/meta quality, headings, readability)
    - Authority: 20%  (inbound links, link diversity, anchor text)
    - Linking: 10%    (internal linking structure, orphan pages)
    - AI Visibility: 5% (schema markup, structured data, entity clarity)
    """

    def score_page(self, page: AnalyzedPage, inbound_link_count: int = 0) -> PageScore:
        """Compute all scores for a single page."""
        score = PageScore()

        tech_score, tech_breakdown = self._score_technical(page)
        content_score, content_breakdown = self._score_content(page)
        linking_score, linking_breakdown = self._score_linking(page, inbound_link_count)
        authority_score = self._score_authority(inbound_link_count)
        ai_score = self._score_ai_visibility(page)

        score.technical_score = clamp(tech_score)
        score.content_score = clamp(content_score)
        score.authority_score = clamp(authority_score)
        score.linking_score = clamp(linking_score)
        score.ai_visibility_score = clamp(ai_score)
        score.technical_breakdown = tech_breakdown
        score.content_breakdown = content_breakdown
        score.linking_breakdown = linking_breakdown

        score.overall_score = clamp(
            score.technical_score * settings.SCORE_TECHNICAL_WEIGHT +
            score.content_score * settings.SCORE_CONTENT_WEIGHT +
            score.authority_score * settings.SCORE_AUTHORITY_WEIGHT +
            score.linking_score * settings.SCORE_LINKING_WEIGHT +
            score.ai_visibility_score * settings.SCORE_AI_VISIBILITY_WEIGHT
        )

        return score

    def _score_technical(self, page: AnalyzedPage) -> Tuple[float, Dict]:
        """
        Technical SEO score (0-100):
        - HTTPS (+10)
        - Indexability (+15)
        - Status code 200 (+10)
        - Viewport meta (+5)
        - Page speed (<1s=10, <2s=7, <3s=5, <5s=2) (+10)
        - Page size (<500KB=10, <1MB=7, <2MB=3) (+10)
        - Canonical tag set (+5)
        - Meta robots not blocking (+10)
        - Hreflang (if multi-lang) (+5)
        - Has schema markup (+10)
        - Open Graph present (+5)
        - Twitter Card present (+5)
        """
        score = 0.0
        breakdown = {}

        # HTTPS
        https_pts = 10 if page.is_https else 0
        score += https_pts
        breakdown["https"] = {"score": https_pts, "max": 10, "value": page.is_https}

        # Status code
        status_pts = 10 if page.status_code == 200 else (5 if 200 < page.status_code < 400 else 0)
        score += status_pts
        breakdown["status_code"] = {"score": status_pts, "max": 10, "value": page.status_code}

        # Indexability
        index_pts = 15 if page.is_indexable else 0
        score += index_pts
        breakdown["indexable"] = {"score": index_pts, "max": 15, "value": page.is_indexable}

        # Viewport meta
        viewport_pts = 5 if page.has_viewport_meta else 0
        score += viewport_pts
        breakdown["viewport"] = {"score": viewport_pts, "max": 5, "value": page.has_viewport_meta}

        # Load time
        lt = page.load_time_ms
        if lt <= 1000:
            lt_pts = 10
        elif lt <= 2000:
            lt_pts = 7
        elif lt <= 3000:
            lt_pts = 5
        elif lt <= 5000:
            lt_pts = 2
        else:
            lt_pts = 0
        score += lt_pts
        breakdown["load_time"] = {"score": lt_pts, "max": 10, "value": lt}

        # Page size
        size_kb = (page.page_size_bytes or 0) / 1024
        if size_kb < 500:
            size_pts = 10
        elif size_kb < 1024:
            size_pts = 7
        elif size_kb < 2048:
            size_pts = 3
        else:
            size_pts = 0
        score += size_pts
        breakdown["page_size"] = {"score": size_pts, "max": 10, "value": round(size_kb, 1)}

        # Canonical
        canonical_pts = 5 if page.canonical_tag else 0
        score += canonical_pts
        breakdown["canonical"] = {"score": canonical_pts, "max": 5, "value": bool(page.canonical_tag)}

        # Schema markup
        schema_pts = 10 if page.has_schema_markup else 0
        score += schema_pts
        breakdown["schema_markup"] = {
            "score": schema_pts, "max": 10,
            "value": page.schema_types if page.has_schema_markup else []
        }

        # Open Graph
        og_pts = 5 if page.has_open_graph else 0
        score += og_pts
        breakdown["open_graph"] = {"score": og_pts, "max": 5, "value": page.has_open_graph}

        # Twitter Card
        tc_pts = 5 if page.has_twitter_card else 0
        score += tc_pts
        breakdown["twitter_card"] = {"score": tc_pts, "max": 5, "value": page.has_twitter_card}

        # Hreflang
        hl_pts = 5 if page.has_hreflang else 0
        score += hl_pts
        breakdown["hreflang"] = {"score": hl_pts, "max": 5, "value": page.has_hreflang}

        # Normalize to 100
        max_possible = 90.0
        normalized = (score / max_possible) * 100
        return normalized, breakdown

    def _score_content(self, page: AnalyzedPage) -> Tuple[float, Dict]:
        """
        Content quality score (0-100):
        - Title exists and optimal length (50-60 chars) (+20)
        - Meta description exists and optimal length (150-160 chars) (+15)
        - H1 exists (exactly one) (+15)
        - H2s present (+5)
        - Word count (>=1500 ideal) (+20)
        - Images have alt text (+10)
        - Text/HTML ratio (+10)
        - Keyword density in range (+5)
        """
        score = 0.0
        breakdown = {}

        # Title
        if page.title:
            if 50 <= page.title_length <= 60:
                title_pts = 20
            elif 30 <= page.title_length <= 70:
                title_pts = 15
            elif page.title_length > 0:
                title_pts = 8
            else:
                title_pts = 0
        else:
            title_pts = 0
        score += title_pts
        breakdown["title"] = {
            "score": title_pts, "max": 20,
            "value": page.title, "length": page.title_length
        }

        # Meta description
        if page.meta_description:
            if 150 <= page.meta_description_length <= 160:
                desc_pts = 15
            elif 100 <= page.meta_description_length <= 180:
                desc_pts = 10
            else:
                desc_pts = 5
        else:
            desc_pts = 0
        score += desc_pts
        breakdown["meta_description"] = {
            "score": desc_pts, "max": 15,
            "length": page.meta_description_length
        }

        # H1 tag (exactly one is ideal)
        h1_count = len(page.h1_tags)
        if h1_count == 1:
            h1_pts = 15
        elif h1_count > 1:
            h1_pts = 8  # Multiple H1s is suboptimal
        else:
            h1_pts = 0
        score += h1_pts
        breakdown["h1"] = {"score": h1_pts, "max": 15, "count": h1_count, "tags": page.h1_tags}

        # H2 tags
        h2_pts = 5 if len(page.h2_tags) >= 2 else (2 if len(page.h2_tags) == 1 else 0)
        score += h2_pts
        breakdown["h2"] = {"score": h2_pts, "max": 5, "count": len(page.h2_tags)}

        # Word count
        wc = page.word_count
        if wc >= 1500:
            wc_pts = 20
        elif wc >= 800:
            wc_pts = 15
        elif wc >= 400:
            wc_pts = 10
        elif wc >= 200:
            wc_pts = 5
        else:
            wc_pts = 0
        score += wc_pts
        breakdown["word_count"] = {"score": wc_pts, "max": 20, "value": wc}

        # Image alt text coverage
        if page.total_images > 0:
            alt_ratio = page.images_with_alt / page.total_images
            alt_pts = round(alt_ratio * 10)
        else:
            alt_pts = 10  # No images = not penalized
        score += alt_pts
        breakdown["image_alt"] = {
            "score": alt_pts, "max": 10,
            "total": page.total_images,
            "missing": page.images_missing_alt
        }

        # Text/HTML ratio (>= 0.3 is good)
        ratio = page.text_html_ratio
        if ratio >= 0.3:
            ratio_pts = 10
        elif ratio >= 0.15:
            ratio_pts = 5
        else:
            ratio_pts = 0
        score += ratio_pts
        breakdown["text_ratio"] = {"score": ratio_pts, "max": 10, "value": ratio}

        # Normalize to 100
        max_possible = 95.0
        normalized = (score / max_possible) * 100
        return normalized, breakdown

    def _score_linking(self, page: AnalyzedPage, inbound_count: int) -> Tuple[float, Dict]:
        """
        Internal linking score (0-100).
        - Has outgoing internal links (+30)
        - Reasonable number of outbound links (+20)
        - Has inbound links (from other pages) (+50)
        """
        score = 0.0
        breakdown = {}

        # Outgoing internal links
        out_count = page.internal_links_count
        if out_count >= 5:
            out_pts = 30
        elif out_count >= 2:
            out_pts = 20
        elif out_count >= 1:
            out_pts = 10
        else:
            out_pts = 0
        score += out_pts
        breakdown["outgoing_internal"] = {"score": out_pts, "max": 30, "count": out_count}

        # Reasonable outbound count (not link spam)
        if 1 <= out_count <= 50:
            ratio_pts = 20
        elif out_count > 100:
            ratio_pts = 5
        else:
            ratio_pts = 0
        score += ratio_pts
        breakdown["link_count_quality"] = {"score": ratio_pts, "max": 20}

        # Inbound links
        if inbound_count >= 10:
            in_pts = 50
        elif inbound_count >= 5:
            in_pts = 35
        elif inbound_count >= 2:
            in_pts = 20
        elif inbound_count >= 1:
            in_pts = 10
        else:
            in_pts = 0
        score += in_pts
        breakdown["inbound_links"] = {"score": in_pts, "max": 50, "count": inbound_count}

        return score, breakdown

    def _score_authority(self, inbound_link_count: int) -> float:
        """
        Authority score based on internal link graph.
        (In production this would incorporate external backlink data.)
        """
        if inbound_link_count >= 50:
            return 90.0
        elif inbound_link_count >= 20:
            return 75.0
        elif inbound_link_count >= 10:
            return 60.0
        elif inbound_link_count >= 5:
            return 45.0
        elif inbound_link_count >= 2:
            return 30.0
        elif inbound_link_count >= 1:
            return 15.0
        return 5.0

    def _score_ai_visibility(self, page: AnalyzedPage) -> float:
        """
        AI Visibility score - how well-structured the page is for AI systems.
        Factors: schema markup, clear entities, FAQ/HowTo schema, clear headings.
        """
        score = 0.0

        # Schema markup presence
        if page.has_schema_markup:
            score += 40
            # Bonus for specific high-value schema types
            high_value_schemas = {"FAQPage", "HowTo", "Article", "Product", "LocalBusiness"}
            matching = set(page.schema_types) & high_value_schemas
            score += len(matching) * 10

        # Clear heading structure
        if len(page.h1_tags) == 1:
            score += 15
        if len(page.h2_tags) >= 2:
            score += 15

        # Open Graph (helps AI understand content)
        if page.has_open_graph:
            score += 10

        # Good content length for AI training signals
        if page.word_count >= 1000:
            score += 10

        return clamp(score)

    def aggregate_site_score(self, page_scores: List[PageScore]) -> SiteScore:
        """Aggregate individual page scores into a site-level score."""
        if not page_scores:
            return SiteScore()

        site_score = SiteScore()
        site_score.page_count = len(page_scores)

        site_score.overall_score = round(sum(p.overall_score for p in page_scores) / len(page_scores), 2)
        site_score.technical_score = round(sum(p.technical_score for p in page_scores) / len(page_scores), 2)
        site_score.content_score = round(sum(p.content_score for p in page_scores) / len(page_scores), 2)
        site_score.authority_score = round(sum(p.authority_score for p in page_scores) / len(page_scores), 2)
        site_score.linking_score = round(sum(p.linking_score for p in page_scores) / len(page_scores), 2)
        site_score.ai_visibility_score = round(sum(p.ai_visibility_score for p in page_scores) / len(page_scores), 2)

        # Aggregate breakdowns
        site_score.technical_breakdown = self._aggregate_breakdowns(
            [p.technical_breakdown for p in page_scores]
        )
        site_score.content_breakdown = self._aggregate_breakdowns(
            [p.content_breakdown for p in page_scores]
        )
        site_score.linking_breakdown = self._aggregate_breakdowns(
            [p.linking_breakdown for p in page_scores]
        )

        return site_score

    def _aggregate_breakdowns(self, breakdowns: List[Dict]) -> Dict:
        """Compute average scores across all page breakdowns."""
        if not breakdowns:
            return {}
        aggregated = {}
        for breakdown in breakdowns:
            for key, data in breakdown.items():
                if key not in aggregated:
                    aggregated[key] = {"scores": [], "max": data.get("max", 0)}
                aggregated[key]["scores"].append(data.get("score", 0))
        return {
            key: {
                "avg_score": round(sum(v["scores"]) / len(v["scores"]), 2),
                "max": v["max"],
                "pct": round((sum(v["scores"]) / len(v["scores"])) / max(v["max"], 1) * 100, 1),
            }
            for key, v in aggregated.items()
        }