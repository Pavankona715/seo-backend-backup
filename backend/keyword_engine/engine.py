"""
Keyword Engine module.
Computes keyword opportunities using:
  Opportunity Score = Volume × CTR × RankGap ÷ Difficulty

Also aggregates keywords across all pages of a site to find
the most impactful keyword opportunities.
"""

import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter

from core.logging import get_logger

logger = get_logger(__name__)

# CTR curve based on typical organic search position CTR data
POSITION_CTR_MAP = {
    1: 0.284,
    2: 0.152,
    3: 0.099,
    4: 0.073,
    5: 0.058,
    6: 0.046,
    7: 0.036,
    8: 0.031,
    9: 0.027,
    10: 0.024,
    11: 0.018,
    12: 0.015,
    13: 0.013,
    14: 0.011,
    15: 0.009,
    20: 0.006,
    30: 0.003,
    50: 0.001,
}


def get_ctr_for_position(position: int) -> float:
    """Get estimated CTR for a given search position."""
    if position <= 0:
        return 0.0
    if position in POSITION_CTR_MAP:
        return POSITION_CTR_MAP[position]
    # Interpolate for positions not in map
    if position > 50:
        return 0.0005
    # Linear interpolation between known positions
    positions = sorted(POSITION_CTR_MAP.keys())
    for i in range(len(positions) - 1):
        p1, p2 = positions[i], positions[i + 1]
        if p1 <= position <= p2:
            ctr1, ctr2 = POSITION_CTR_MAP[p1], POSITION_CTR_MAP[p2]
            ratio = (position - p1) / (p2 - p1)
            return ctr1 + ratio * (ctr2 - ctr1)
    return 0.001


def compute_opportunity_score(
    volume: int,
    ctr: float,
    rank_gap: int,
    difficulty: float,
) -> float:
    """
    Compute keyword opportunity score.
    Formula: Opportunity = Volume × CTR × RankGap ÷ Difficulty

    - volume: estimated monthly search volume
    - ctr: click-through rate for target position (0.0-1.0)
    - rank_gap: positions to climb (e.g., currently rank 15, target rank 3 = gap of 12)
    - difficulty: keyword difficulty (1-100, higher = harder)

    Returns a score normalized to 0-100.
    """
    if difficulty <= 0:
        difficulty = 1.0
    if volume <= 0 or ctr <= 0 or rank_gap <= 0:
        return 0.0

    raw_score = (volume * ctr * rank_gap) / difficulty
    # Normalize: log scale to compress the range
    normalized = min(100.0, math.log1p(raw_score) * 8)
    return round(normalized, 2)


@dataclass
class KeywordOpportunity:
    """A keyword with computed opportunity data."""
    keyword: str
    frequency: int = 0
    density: float = 0.0
    estimated_volume: int = 0
    estimated_difficulty: float = 50.0
    estimated_ctr: float = 0.0
    current_rank: Optional[int] = None
    rank_gap: Optional[int] = None
    opportunity_score: float = 0.0
    is_opportunity: bool = False
    page_urls: List[str] = field(default_factory=list)


class KeywordEngine:
    """
    Aggregates keywords from all pages and computes opportunity scores.
    In production, volume and difficulty data would come from an external
    API (e.g., DataForSEO, Semrush, Ahrefs). Here we use heuristic estimation.
    """

    def __init__(self, target_rank: int = 3):
        self.target_rank = target_rank  # Position we're aiming to rank at

    def aggregate_site_keywords(
        self, page_keyword_data: List[Tuple[str, Dict[str, int]]]
    ) -> List[KeywordOpportunity]:
        """
        Aggregate keyword frequencies across all pages.

        Args:
            page_keyword_data: List of (page_url, keyword_frequencies) tuples

        Returns:
            List of KeywordOpportunity objects with opportunity scores
        """
        # Aggregate frequencies across all pages
        keyword_pages: Dict[str, List[str]] = {}
        total_freq: Counter = Counter()

        total_words = 0
        for page_url, kw_freq in page_keyword_data:
            for keyword, count in kw_freq.items():
                if keyword not in keyword_pages:
                    keyword_pages[keyword] = []
                keyword_pages[keyword].append(page_url)
                total_freq[keyword] += count
                total_words += count

        opportunities = []
        for keyword, freq in total_freq.most_common(500):
            # Filter very short or numeric-only keywords
            if len(keyword) < 3 or keyword.isdigit():
                continue

            # Estimate metrics (in production, use API)
            estimated_volume = self._estimate_volume(keyword, freq)
            estimated_difficulty = self._estimate_difficulty(keyword)
            current_rank = self._estimate_current_rank(keyword, freq)
            target_ctr = get_ctr_for_position(self.target_rank)

            rank_gap = None
            if current_rank and current_rank > self.target_rank:
                rank_gap = current_rank - self.target_rank

            opportunity_score = 0.0
            if rank_gap and rank_gap > 0:
                opportunity_score = compute_opportunity_score(
                    volume=estimated_volume,
                    ctr=target_ctr,
                    rank_gap=rank_gap,
                    difficulty=estimated_difficulty,
                )

            density = (freq / max(total_words, 1)) * 100

            opp = KeywordOpportunity(
                keyword=keyword,
                frequency=freq,
                density=round(density, 4),
                estimated_volume=estimated_volume,
                estimated_difficulty=estimated_difficulty,
                estimated_ctr=target_ctr,
                current_rank=current_rank,
                rank_gap=rank_gap,
                opportunity_score=opportunity_score,
                is_opportunity=opportunity_score > 15.0,
                page_urls=keyword_pages.get(keyword, [])[:5],
            )
            opportunities.append(opp)

        # Sort by opportunity score
        opportunities.sort(key=lambda x: x.opportunity_score, reverse=True)
        return opportunities

    def _estimate_volume(self, keyword: str, site_frequency: int) -> int:
        """
        Heuristic volume estimation.
        In production: replace with DataForSEO or Google Keyword Planner API.
        """
        word_count = len(keyword.split())
        base_volume = 1000

        # Longer keywords (long-tail) typically have lower volume
        if word_count == 1:
            multiplier = 10
        elif word_count == 2:
            multiplier = 4
        elif word_count == 3:
            multiplier = 2
        else:
            multiplier = 1

        # Higher site frequency suggests more important/common topic
        freq_bonus = min(site_frequency * 50, 5000)
        return int(base_volume * multiplier + freq_bonus)

    def _estimate_difficulty(self, keyword: str) -> float:
        """
        Heuristic difficulty estimation.
        In production: replace with Semrush/Ahrefs API.
        """
        word_count = len(keyword.split())

        # Short head terms are harder; long-tail is easier
        if word_count == 1:
            return 75.0
        elif word_count == 2:
            return 55.0
        elif word_count == 3:
            return 40.0
        else:
            return 25.0

    def _estimate_current_rank(self, keyword: str, site_frequency: int) -> Optional[int]:
        """
        Heuristic rank estimation.
        In production: replace with rank tracking API or Google Search Console data.
        """
        if site_frequency >= 50:
            return 8
        elif site_frequency >= 20:
            return 15
        elif site_frequency >= 10:
            return 25
        elif site_frequency >= 5:
            return 40
        else:
            return 60