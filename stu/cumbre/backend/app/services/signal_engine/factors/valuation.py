"""
Valuation factor: scores based on NAV position relative to its own historical range.
Uses 52-week percentile rank as a proxy when fund-level PE/PB is unavailable.

Fundamentals:
- NAV near 52-week low → potentially undervalued → buy signal
- NAV near 52-week high → potentially overvalued → cautious/sell
"""

from typing import TypedDict


class ValuationResult(TypedDict):
    score: float
    details: dict


def calculate_valuation(
    pe_percentile: float | None = None,
    pb_percentile: float | None = None,
    nav_values: list[float] | None = None,
) -> ValuationResult:
    """
    Calculate valuation factor score.
    Uses PE/PB percentile data when available (preferred).
    Falls back to NAV 52-week range percentile + short-term reversal.

    Args:
        pe_percentile: PE percentile (0-100, 0 = cheapest)
        pb_percentile: PB percentile (0-100, 0 = cheapest)
        nav_values: NAV history for range/reversal proxy
    """
    scores_used = []
    details = {}

    # PE percentile: lower = cheaper = higher score
    if pe_percentile is not None:
        pe_score = 95 - pe_percentile * 0.9
        pe_score = max(5, min(95, pe_score))
        scores_used.append(pe_score)
        details["pe_percentile"] = pe_percentile

    # PB percentile: same logic
    if pb_percentile is not None:
        pb_score = 95 - pb_percentile * 0.9
        pb_score = max(5, min(95, pb_score))
        scores_used.append(pb_score)
        details["pb_percentile"] = pb_percentile

    # NAV-based proxy when no PE/PB data
    if not scores_used and nav_values and len(nav_values) >= 60:
        # Metric 1: Position within 52-week range (60% of NAV score)
        # Normalizes across funds — naturally produces 0-100 distribution
        lookback = min(252, len(nav_values))
        recent = nav_values[-lookback:]
        high_52w = max(recent)
        low_52w = min(recent)
        current = nav_values[-1]

        if high_52w > low_52w:
            # Invert: low position = cheap = high score
            range_pos = (current - low_52w) / (high_52w - low_52w)
            range_score = 85 - range_pos * 70  # maps: 0%→85, 50%→50, 100%→15
            range_score = max(10, min(90, range_score))
        else:
            range_score = 50.0

        # Metric 2: Short-term reversal (40% of NAV score)
        # 5-day return: sharp drop = oversold = buy signal
        if len(nav_values) >= 5:
            ret_5d = (current - nav_values[-5]) / nav_values[-5] * 100
            # Center at 0%: negative return → higher score
            rev_score = 50 - ret_5d * 1.5
            rev_score = max(5, min(95, rev_score))
        else:
            rev_score = 50.0

        nav_score = range_score * 0.6 + rev_score * 0.4
        scores_used.append(nav_score)
        details["nav_52w_range_pct"] = round((current - low_52w) / (high_52w - low_52w) * 100, 1) if high_52w > low_52w else 50
        details["short_term_reversal_5d"] = round(ret_5d, 2) if len(nav_values) >= 5 else None

    if not scores_used:
        return ValuationResult(score=50.0, details={"reason": "no valuation data"})

    final_score = sum(scores_used) / len(scores_used)

    return ValuationResult(
        score=round(final_score, 1),
        details={
            **details,
            "valuation_score": round(final_score, 1),
        },
    )
