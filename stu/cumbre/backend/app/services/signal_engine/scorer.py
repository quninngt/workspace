"""
Signal scorer: combines all factor scores into a final signal.

Factor weights:
- Valuation: 15% — NAV-based proxy (52-week range + short-term reversal)
- Trend: 10% — MA20/MA60 crossover + price deviation (minimized in current market)
- Momentum: 30% — RSI(14) + MACD(12,26,9) (biggest differentiator)
- Quality: 30% — Fund size + max drawdown + NAV consistency
- Sentiment: 15% — Fund-level volatility contrarian signal

Signal levels:
- S (strong buy): ≥ 80
- A (buy): 65-79
- B (hold): 40-64
- C (sell): 25-39
- D (strong sell): < 25
"""

from typing import TypedDict


FACTOR_WEIGHTS = {
    "valuation": 0.15,   # — some spread (26-73)
    "trend": 0.10,       # — minimized: uniformly bullish in current market
    "momentum": 0.30,    # — biggest differentiator (19-77, if including extremes)
    "quality": 0.30,     # — good spread (32-88)
    "sentiment": 0.15,   # — moderate spread (30-72)
}


class SignalResult(TypedDict):
    score: float
    level: str          # S/A/B/C/D
    action: str         # buy/hold/sell
    factors: dict       # individual factor scores
    details: dict       # factor details


def compute_signal(
    factor_scores: dict[str, float],
    weights: dict[str, float] | None = None,
    thresholds: dict[str, float] | None = None,
) -> SignalResult:
    """
    Combine factor scores into a final signal.
    factor_scores: dict with keys 'valuation', 'trend', 'momentum', 'quality', 'sentiment'
    weights: optional override for FACTOR_WEIGHTS
    thresholds: optional override for level boundaries {S, A, B, C}
    """
    active_weights = weights or FACTOR_WEIGHTS
    t = thresholds or {"S": 80, "A": 65, "B": 40, "C": 25}

    weighted_sum = 0
    total_weight = 0
    factor_details = {}

    for factor, weight in active_weights.items():
        score = factor_scores.get(factor)
        if score is not None:
            weighted_sum += score * weight
            total_weight += weight
            factor_details[factor] = round(score, 1)

    if total_weight == 0:
        return SignalResult(
            score=50.0,
            level="B",
            action="hold",
            factors=factor_details,
            details={"reason": "no factor data"},
        )

    # Normalize in case some factors are missing
    if total_weight < 1.0:
        final_score = weighted_sum / total_weight
    else:
        final_score = weighted_sum

    final_score = max(0, min(100, final_score))

    # Determine level and action
    if final_score >= t["S"]:
        level = "S"
        action = "buy"
    elif final_score >= t["A"]:
        level = "A"
        action = "buy"
    elif final_score >= t["B"]:
        level = "B"
        action = "hold"
    elif final_score >= t["C"]:
        level = "C"
        action = "sell"
    else:
        level = "D"
        action = "sell"

    return SignalResult(
        score=round(final_score, 1),
        level=level,
        action=action,
        factors=factor_details,
        details={"weights_applied": active_weights, "thresholds": t},
    )
