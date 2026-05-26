"""
Sentiment factor: contrarian scoring based on fund-level NAV volatility.
Measures fund-specific risk (not broad market sentiment) — funds with identical
market exposure but different NAV magnitudes will score differently.

Three components for wider dispersion across funds:
  1. 20-day volatility (50%) — recent price choppiness
  2. Volatility trend 10d/60d ratio (25%) — rising = fear intensifying
  3. Recent drawdown from 20-day high (25%) — distance from peak

Rationale:
  High volatility + rising volatility trend + sharp drawdown = fear
  = contrarian buy opportunity. Low vol + calming trend = complacency.

Weight in overall model: 15%
"""

import math
from typing import TypedDict


class SentimentResult(TypedDict):
    score: float
    details: dict


def calculate_sentiment(
    nav_values: list[float] | None = None,
) -> SentimentResult:
    """
    Calculate sentiment factor score using multi-window volatility analysis.
    Higher score = more fear in the market = contrarian buy opportunity.

    Three components:
      1. 20-day volatility (50%) — how choppy price action has been recently
      2. Volatility trend (25%) — 10d vs 60d vol ratio (rising = fear)
      3. Recent drawdown (25%) — distance from 20-day high
    """
    if not nav_values or len(nav_values) < 20:
        return SentimentResult(score=50.0, details={"reason": "insufficient NAV data (<20)"})

    scores = []
    details = {}

    # --- Component 1: 20-day volatility (50%) ---
    vol_20d = _calc_volatility(nav_values, 20)
    vol_pct = vol_20d * 100 if vol_20d else 0

    if vol_20d is not None and vol_20d > 0:
        # Steeper slope than before: maps 0.5%→35, 1%→45, 2%→65, 3%→85, 3.5%+→95
        vol_score = 30 + vol_pct * 20
        vol_score = max(10, min(95, vol_score))
    else:
        vol_score = 50.0
    scores.append(("vol_20d", vol_score, 0.50))
    details["vol_20d_pct"] = round(vol_pct, 2)

    # --- Component 2: Volatility trend (25%) ---
    # Rising volatility = fear intensifying = contrarian buy
    if len(nav_values) >= 60:
        vol_10d = _calc_volatility(nav_values, 10) or 0.001
        vol_60d = _calc_volatility(nav_values, 60) or 0.001
        vol_ratio = vol_10d / vol_60d  # >1 = rising, <1 = falling

        # ratio 0.5 → 20 (calming fast), 1.0 → 50 (neutral), 1.5 → 80 (spiking), 2.0+ → 95
        trend_score = 50 + (vol_ratio - 1.0) * 80
        trend_score = max(10, min(95, trend_score))
        details["vol_trend_10d_60d"] = round(vol_ratio, 2)
    else:
        trend_score = 50.0
        details["vol_trend_10d_60d"] = None
    scores.append(("vol_trend", trend_score, 0.25))

    # --- Component 3: Recent drawdown from 20-day high (25%) ---
    high_20d = max(nav_values[-20:])
    current = nav_values[-1]
    drawdown_pct = (high_20d - current) / high_20d * 100 if high_20d > 0 else 0

    # 0% dd → 30 (no fear), -2% → 46, -5% → 70, -8% → 86, -10%+ → 95
    dd_score = 30 + drawdown_pct * 8
    dd_score = max(10, min(95, dd_score))
    scores.append(("drawdown", dd_score, 0.25))
    details["drawdown_pct"] = round(drawdown_pct, 2)

    # --- Combine ---
    final_score = sum(s * w for _, s, w in scores) / sum(w for _, _, w in scores)

    return SentimentResult(
        score=round(final_score, 1),
        details={
            **details,
            "sentiment_score": round(final_score, 1),
        },
    )


def _calc_volatility(nav_values: list[float], period: int) -> float | None:
    """Calculate daily return std over the trailing `period` days."""
    if len(nav_values) < period + 1:
        return None
    returns = []
    for i in range(1, period + 1):
        prev = nav_values[-(i + 1)]
        curr = nav_values[-i]
        if prev > 0:
            returns.append((curr - prev) / prev)
    if not returns:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    return math.sqrt(variance)
