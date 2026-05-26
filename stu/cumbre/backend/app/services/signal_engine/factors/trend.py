"""
Trend factor: calculates scores based on moving average systems and price deviation.

MA20/MA60 crossover: golden cross = buy, death cross = sell
Price deviation: % distance from MA20
"""

import math
from typing import TypedDict


class TrendResult(TypedDict):
    score: float        # 0-100
    details: dict


def calculate_trend(nav_values: list[float]) -> TrendResult:
    """
    Calculate trend factor score from NAV history.
    Higher score = stronger buy signal.

    Scoring logic:
    - MA20 vs MA60 crossover (golden cross = buy)
    - Price position relative to MA bands
    - Recent price deviation from MA (oversold = buy, overbought = sell)
    """
    if len(nav_values) < 60:
        return TrendResult(score=50.0, details={"reason": "insufficient data"})

    ma20 = _sma(nav_values, 20)
    ma60 = _sma(nav_values, 60)
    current = nav_values[-1]

    # MA crossover score (40% of trend score)
    # MA20 above MA60 = bullish, below = bearish
    ma_ratio = (ma20 - ma60) / ma60 * 100 if ma60 != 0 else 0
    crossover_score = _normalize(ma_ratio, -10, 10, 50)  # wide range to avoid saturation

    # Price vs MA20 deviation (30% of trend score)
    deviation = (current - ma20) / ma20 * 100 if ma20 != 0 else 0
    # Negative deviation (price below MA20) = oversold = buy signal
    # Positive deviation (price above MA20) = overbought = sell signal
    dev_score = _normalize(-deviation, -10, 10, 50)

    # Short-term trend strength (30% of trend score)
    if len(nav_values) >= 10:
        ma5 = _sma(nav_values, 5)
        short_trend = (ma5 - ma20) / ma20 * 100 if ma20 != 0 else 0
    else:
        short_trend = 0
    short_score = _normalize(short_trend, -3, 3, 50)

    # Combined score
    final_score = crossover_score * 0.4 + dev_score * 0.3 + short_score * 0.3

    return TrendResult(
        score=round(final_score, 1),
        details={
            "ma20": round(ma20, 4),
            "ma60": round(ma60, 4),
            "crossover_pct": round(ma_ratio, 2),
            "deviation_pct": round(deviation, 2),
            "crossover_score": round(crossover_score, 1),
            "deviation_score": round(dev_score, 1),
            "short_term_score": round(short_score, 1),
        },
    )


def _sma(values: list[float], period: int) -> float:
    """Simple Moving Average of the last `period` values."""
    if len(values) < period:
        return values[-1] if values else 0
    return sum(values[-period:]) / period


def _normalize(value: float, low: float, high: float, center: float = 50) -> float:
    """Map a value to a score (0-100) where value=0 → center score."""
    if value >= high:
        return 100.0
    if value <= low:
        return 0.0
    if value >= 0:
        return center + (value / high) * (100 - center) if high != 0 else center
    else:
        return center + (value / low) * center if low != 0 else center
